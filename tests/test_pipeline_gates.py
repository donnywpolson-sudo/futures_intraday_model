from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pipeline_gates import (
    check_upstream_manifest,
    file_sha256,
    resolve_upstream_manifest_gate,
)


def _write_output(root: Path, market: str = "ES", year: int = 2024) -> Path:
    path = root / market / f"{year}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture-output")
    return path


def _write_manifest(
    path: Path,
    output_root: Path,
    output_path: Path,
    *,
    status: str = "PASS",
    failure_count: int = 0,
    warning_count: int = 0,
    profile: str = "research",
    resolved_profile: str = "research_resolved",
    output_hash: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "upstream",
        "status": status,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "output_root": output_root.as_posix(),
        "warning_count": warning_count,
        "failure_count": failure_count,
        "failures": [] if failure_count == 0 else ["failed"],
        "summary": {"fail_count": failure_count, "warn_count": warning_count},
        "output_file_hashes": {
            output_path.as_posix(): output_hash if output_hash is not None else file_sha256(output_path)
        },
        "outputs": [
            {
                "market": "ES",
                "year": 2024,
                "status": status,
                "warning_count": warning_count,
                "failure_count": failure_count,
                "failures": [] if failure_count == 0 else ["failed"],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _check(manifest_path: Path, output_root: Path):
    return check_upstream_manifest(
        manifest_path=manifest_path,
        expected_stage="upstream",
        expected_profile="research",
        expected_resolved_profile="research_resolved",
        expected_output_root=output_root,
        expected_market_years=[("ES", 2024)],
        gate_name="test_gate",
    )


def test_upstream_manifest_gate_requires_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "out"

    check = _check(tmp_path / "missing.json", output_root)

    assert not check.passed
    assert any("missing" in failure for failure in check.failures)


def test_upstream_manifest_gate_accepts_complete_pass_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    output_path = _write_output(output_root)
    manifest_path = _write_manifest(tmp_path / "manifest.json", output_root, output_path)

    check = _check(manifest_path, output_root)

    assert check.passed
    assert check.evidence["status"] == "PASS"


def test_upstream_manifest_gate_rejects_warn_or_fail_status(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    output_path = _write_output(output_root)
    warn_manifest = _write_manifest(
        tmp_path / "warn.json",
        output_root,
        output_path,
        status="WARN",
        warning_count=1,
    )
    fail_manifest = _write_manifest(
        tmp_path / "fail.json",
        output_root,
        output_path,
        status="FAIL",
        failure_count=1,
    )

    assert any("status" in failure for failure in _check(warn_manifest, output_root).failures)
    assert any("failure_count" in failure for failure in _check(fail_manifest, output_root).failures)


def test_upstream_manifest_gate_rejects_scope_and_root_mismatches(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    output_path = _write_output(output_root)
    manifest_path = _write_manifest(
        tmp_path / "manifest.json",
        output_root,
        output_path,
        profile="other",
        resolved_profile="other_resolved",
    )

    failures = _check(manifest_path, tmp_path / "different_out").failures

    assert any("profile" in failure for failure in failures)
    assert any("resolved_profile" in failure for failure in failures)
    assert any("output_root" in failure for failure in failures)


def test_upstream_manifest_gate_rejects_missing_or_stale_output_hash(tmp_path: Path) -> None:
    output_root = tmp_path / "out"
    output_path = _write_output(output_root)
    missing_hash_manifest = _write_manifest(
        tmp_path / "missing_hash.json",
        output_root,
        output_path,
    )
    payload = json.loads(missing_hash_manifest.read_text(encoding="utf-8"))
    payload["output_file_hashes"] = {}
    missing_hash_manifest.write_text(json.dumps(payload), encoding="utf-8")

    stale_hash_manifest = _write_manifest(
        tmp_path / "stale_hash.json",
        output_root,
        output_path,
        output_hash="0" * 64,
    )

    assert any("hash missing" in failure for failure in _check(missing_hash_manifest, output_root).failures)
    assert any("hash stale" in failure for failure in _check(stale_hash_manifest, output_root).failures)


def test_auto_upstream_manifest_gate_finds_custom_reports_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "out"
    output_path = _write_output(output_root)
    custom_manifest = _write_manifest(
        tmp_path / "reports" / "custom_phase" / "manifest.json",
        output_root,
        output_path,
    )

    check = resolve_upstream_manifest_gate(
        manifest_arg="auto",
        default_manifest_path=tmp_path / "reports" / "default" / "manifest.json",
        search_name="manifest.json",
        expected_stage="upstream",
        expected_profile="research",
        expected_resolved_profile="research_resolved",
        expected_output_root=output_root,
        expected_market_years=[("ES", 2024)],
        gate_name="test_gate",
    )

    assert check.passed
    assert check.evidence["auto_discovered"] is True
    assert check.evidence["manifest_path"] == custom_manifest.relative_to(tmp_path).as_posix()
