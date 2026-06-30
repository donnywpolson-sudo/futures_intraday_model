from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import check_phase2_manifest_trust as gate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(
    tmp_path: Path,
    *,
    pairs: list[tuple[str, int]] | None = None,
    git_commit: str = "old-head",
) -> dict[str, Path]:
    pairs = pairs or [("ES", 2020), ("CL", 2021)]
    data_manifest_path = tmp_path / "configs" / "data_manifest.yaml"
    canonical_root = tmp_path / scope_gate.CANONICAL_ROOT_REL
    reports_root = tmp_path / scope_gate.REPORTS_ROOT_REL
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    build_script = tmp_path / "scripts" / "phase2_causal_base" / "build_causal_base_data.py"
    _write_text(
        data_manifest_path,
        "\n".join(["canonical_paths:", f"  causal_parquet_pattern: {scope_gate.TARGET_CANONICAL_PATTERN}"]),
    )
    _write_text(profile_config, "default_profile: tier_3_research\n")
    _write_text(build_script, "print('builder')\n")

    input_hashes: dict[str, str] = {}
    output_hashes: dict[str, str] = {}
    outputs: list[dict[str, object]] = []
    for market, year in pairs:
        input_rel = f"data/raw/{market}/{year}.parquet"
        output_rel = f"{scope_gate.CANONICAL_ROOT_REL}/{market}/{year}.parquet"
        input_path = tmp_path / input_rel
        output_path = tmp_path / output_rel
        _write_text(input_path, f"input {market} {year}\n")
        _write_text(output_path, f"output {market} {year}\n")
        input_hashes[input_rel] = scope_gate.sha256_file(input_path)
        output_hashes[output_rel] = scope_gate.sha256_file(output_path)
        outputs.append(
            {
                "market": market,
                "year": year,
                "input_path": input_rel,
                "output_path": output_rel,
            }
        )

    _write_json(
        reports_root / "causal_base_manifest.json",
        {
            "status": "PASS",
            "generated_at": "2026-06-30T00:00:00Z",
            "git_commit": git_commit,
            "script_path": "scripts/phase2_causal_base/build_causal_base_data.py",
            "script_hash": scope_gate.sha256_file(build_script),
            "config_hash": scope_gate.sha256_file(profile_config),
            "input_root": "data/raw",
            "output_root": scope_gate.CANONICAL_ROOT_REL,
            "reports_root": scope_gate.REPORTS_ROOT_REL,
            "input_file_hashes": input_hashes,
            "output_file_hashes": output_hashes,
            "market_year_include_count": len(pairs),
            "requested_market_years": [{"market": market, "year": year} for market, year in pairs],
            "outputs": outputs,
        },
    )
    _write_json(
        reports_root / "causal_base_validation.json",
        {
            "status": "PASS",
            "files": [{"market": market, "year": year} for market, year in pairs],
            "summary": {
                "file_count": len(pairs),
                "pass_count": len(pairs),
                "fail_count": 0,
                "local_trade_ohlcv_gap_gate_status": "NOT_RUN",
            },
        },
    )
    return {
        "repo_root": tmp_path,
        "data_manifest_path": data_manifest_path,
        "canonical_root": canonical_root,
        "reports_root": reports_root,
        "phase2_manifest_path": reports_root / "causal_base_manifest.json",
        "phase2_validation_path": reports_root / "causal_base_validation.json",
        "profile_config_path": profile_config,
        "build_script_path": build_script,
    }


def _read_manifest(paths: dict[str, Path]) -> dict[str, object]:
    return json.loads(paths["phase2_manifest_path"].read_text(encoding="utf-8"))


def _write_manifest(paths: dict[str, Path], manifest: dict[str, object]) -> None:
    _write_json(paths["phase2_manifest_path"], manifest)


def _evaluate(paths: dict[str, Path], *, expected_count: int = 2):
    return gate.evaluate_trust(
        repo_root=paths["repo_root"],
        data_manifest_path=paths["data_manifest_path"],
        canonical_root=paths["canonical_root"],
        reports_root=paths["reports_root"],
        phase2_manifest_path=paths["phase2_manifest_path"],
        phase2_validation_path=paths["phase2_validation_path"],
        profile_config_path=paths["profile_config_path"],
        build_script_path=paths["build_script_path"],
        expected_count=expected_count,
        feature_cols=["feature_return_1m"],
        git_head="current-head",
        staged_names=[],
        scoped_status_lines=[],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_trusts_stale_commit_when_material_hashes_match(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path))

    assert report["summary"]["status"] == gate.STATUS_GO
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["input_hash_count"] == 2
    assert report["summary"]["output_hash_count"] == 2
    assert report["warnings"][0]["code"] == gate.WARN_GIT_COMMIT_STALE


def test_fails_script_hash_mismatch(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    manifest = _read_manifest(paths)
    manifest["script_hash"] = "bad-script-hash"
    _write_manifest(paths, manifest)

    report = _evaluate(paths)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "manifest_script_hash_matches_current"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_config_hash_mismatch(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    manifest = _read_manifest(paths)
    manifest["config_hash"] = "bad-config-hash"
    _write_manifest(paths, manifest)

    report = _evaluate(paths)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "manifest_config_hash_matches_current"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_input_hash_mismatch(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write_text(paths["repo_root"] / "data/raw/ES/2020.parquet", "changed input\n")

    report = _evaluate(paths)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["input_hash_mismatch_count"] == 1
    assert any(
        check["name"] == "current_input_hashes_match_manifest"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_missing_input_file(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    (paths["repo_root"] / "data/raw/ES/2020.parquet").unlink()

    report = _evaluate(paths)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["input_hash_missing_count"] == 1


def test_fails_output_hash_mismatch(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write_text(
        paths["repo_root"] / scope_gate.CANONICAL_ROOT_REL / "ES" / "2020.parquet",
        "changed output\n",
    )

    report = _evaluate(paths)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["output_hash_mismatch_count"] == 1
    assert any(
        check["name"] == "current_output_hashes_match_manifest"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_validation_count_mismatch(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write_json(
        paths["phase2_validation_path"],
        {
            "status": "PASS",
            "files": [{"market": "ES", "year": 2020}],
            "summary": {
                "file_count": 1,
                "pass_count": 1,
                "fail_count": 0,
                "local_trade_ohlcv_gap_gate_status": "NOT_RUN",
            },
        },
    )

    report = _evaluate(paths)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "validation_count_consistency"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_when_scope_gate_rejects_forbidden_rows(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, pairs=[("ES", 2020), ("6M", 2012), ("CL", 2025)])

    report = _evaluate(paths, expected_count=3)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(check["name"] == "scope_gate_passed" for check in report["checks"] if check["status"] == "FAIL")
