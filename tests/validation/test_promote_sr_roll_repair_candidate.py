from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.phase2_causal_base.build_causal_base_data import raw_alignment_guard_failures
from scripts.validation import promote_sr_roll_repair_candidate as promoter


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_candidate_file(root: Path, market: str, year: int, content: bytes) -> dict[str, object]:
    path = root / market / f"{year}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "market": market,
        "year": year,
        "status": "PASS",
        "output_path": path.as_posix(),
        "output_hash": _sha256(path),
        "candidate_rows": 3,
        "maturity_backstep_count": 0,
    }


def _manifest(candidate_root: Path, outputs: list[dict[str, object]]) -> dict[str, object]:
    return {
        "stage": "sr_front_contract_candidate_build",
        "status": "PASS",
        "source_audit": {"profile": "tier_3"},
        "candidate_dbn_root": (candidate_root / "dbn").as_posix(),
        "sidecar_dbn_root": (candidate_root / "dbn").as_posix(),
        "definition_dbn_root": (candidate_root / "dbn").as_posix(),
        "status_dbn_root": (candidate_root / "dbn").as_posix(),
        "statistics_dbn_root": (candidate_root / "dbn").as_posix(),
        "raw_alignment_status": "PASS",
        "output_count": len(outputs),
        "outputs": outputs,
        "excluded_market_years": [
            {"market": "SR3", "year": 2018, "reason": "explicit_candidate_exclusion"}
        ],
        "failures": [],
    }


def _readiness(selected_count: int, *, status: str = "PASS") -> dict[str, object]:
    blocked = status != "PASS"
    return {
        "stage": "phase2_readiness_summary",
        "status": status,
        "profile": "tier_3",
        "resolved_profile": "tier_3_research",
        "selected_market_year_count": selected_count,
        "checked_market_year_count": selected_count,
        "pending_market_year_count": 0,
        "blocker_count": 1 if blocked else 0,
        "failure_count": 0,
        "failures": [],
    }


def test_promotes_only_manifest_outputs_and_writes_phase2_alignment(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    raw_root = tmp_path / "data" / "raw"
    outputs = [
        _write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018"),
        _write_candidate_file(candidate_root, "SR1", 2019, b"sr1-2019"),
        _write_candidate_file(candidate_root, "SR3", 2019, b"sr3-2019"),
    ]
    excluded_target = raw_root / "SR3" / "2018.parquet"
    excluded_target.parent.mkdir(parents=True, exist_ok=True)
    excluded_target.write_bytes(b"do-not-touch")

    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    alignment_path = tmp_path / "reports" / "promoted_alignment.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=alignment_path,
    )

    assert report["status"] == "PASS"
    assert report["promoted_count"] == 3
    assert (raw_root / "SR1" / "2018.parquet").read_bytes() == b"sr1-2018"
    assert (raw_root / "SR1" / "2019.parquet").read_bytes() == b"sr1-2019"
    assert (raw_root / "SR3" / "2019.parquet").read_bytes() == b"sr3-2019"
    assert excluded_target.read_bytes() == b"do-not-touch"

    alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
    assert alignment["status"] == "PASS"
    assert alignment["raw_root"] == raw_root.as_posix()
    assert alignment["market_years"] == [
        {"market": "SR1", "year": 2018},
        {"market": "SR1", "year": 2019},
        {"market": "SR3", "year": 2019},
    ]

    config = tmp_path / "configs" / "alpha_tiered.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "\n".join(
            [
                "profiles:",
                "  tier_3:",
                "    markets: [SR1, SR3]",
                "    years: [2018, 2019]",
            ]
        ),
        encoding="utf-8",
    )
    assert raw_alignment_guard_failures(
        report_path=alignment_path,
        raw_root=raw_root,
        profile="tier_3",
        profile_config_path=config,
    ) == []


def test_refuses_failed_readiness_without_copying(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    raw_root = tmp_path / "data" / "raw"
    outputs = [_write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018")]
    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs), status="FAIL"))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=tmp_path / "reports" / "alignment.json",
    )

    assert report["status"] == "FAIL"
    assert "readiness summary status is 'FAIL', not PASS" in report["failures"]
    assert not (raw_root / "SR1" / "2018.parquet").exists()


def test_refuses_missing_expected_exclusion_without_copying(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    raw_root = tmp_path / "data" / "raw"
    outputs = [_write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018")]
    manifest = _manifest(candidate_root, outputs)
    manifest["excluded_market_years"] = []
    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    _write_json(manifest_path, manifest)
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=tmp_path / "reports" / "alignment.json",
    )

    assert report["status"] == "FAIL"
    assert "candidate manifest missing expected exclusions: SR3:2018" in report["failures"]
    assert not (raw_root / "SR1" / "2018.parquet").exists()


def test_refuses_stale_candidate_hash_without_copying(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    raw_root = tmp_path / "data" / "raw"
    outputs = [_write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018")]
    outputs[0]["output_hash"] = "0" * 64
    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=tmp_path / "reports" / "alignment.json",
    )

    assert report["status"] == "FAIL"
    assert any("candidate output hash mismatch" in failure for failure in report["failures"])
    assert not (raw_root / "SR1" / "2018.parquet").exists()


def test_refuses_output_for_excluded_market_year(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    raw_root = tmp_path / "data" / "raw"
    outputs = [_write_candidate_file(candidate_root, "SR3", 2018, b"sr3-2018")]
    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=tmp_path / "reports" / "alignment.json",
    )

    assert report["status"] == "FAIL"
    assert "candidate output includes excluded market-year: SR3 2018" in report["failures"]
    assert not (raw_root / "SR3" / "2018.parquet").exists()
