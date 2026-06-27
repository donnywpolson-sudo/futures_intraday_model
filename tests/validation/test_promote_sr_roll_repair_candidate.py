from __future__ import annotations

import hashlib
import json
import os
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


def _write_dbn_source(
    root: Path,
    *,
    schema_dir: str,
    schema: str,
    market: str,
    year: int,
    stype_in: str = "parent",
) -> Path:
    path = root / schema_dir / market / str(year) / f"{year}-01-01_{year + 1}-01-01.dbn.zst"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"{schema}-{market}-{year}-{stype_in}".encode("utf-8"))
    symbols = [f"{market}.v.0"] if stype_in == "continuous" else [f"{market}.FUT"]
    manifest = {
        "schema": schema,
        "market": market,
        "symbols_requested": symbols,
        "start": f"{year}-01-01",
        "end": f"{year + 1}-01-01",
        "stype_in": stype_in,
        "path": path.as_posix(),
        "file_size_bytes": path.stat().st_size,
        "file_sha256": _sha256(path),
    }
    path.with_name(f"{path.name}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _attach_parent_sources(
    output: dict[str, object],
    dbn_root: Path,
    *,
    stype_in: str = "parent",
) -> dict[str, object]:
    market = str(output["market"])
    year = int(output["year"])
    output["ohlcv_input_paths"] = [
        _write_dbn_source(
            dbn_root,
            schema_dir="ohlcv_1m",
            schema="ohlcv-1m",
            market=market,
            year=year,
            stype_in=stype_in,
        ).as_posix()
    ]
    output["status_paths"] = [
        _write_dbn_source(
            dbn_root,
            schema_dir="status",
            schema="status",
            market=market,
            year=year,
            stype_in=stype_in,
        ).as_posix()
    ]
    output["statistics_paths"] = [
        _write_dbn_source(
            dbn_root,
            schema_dir="statistics",
            schema="statistics",
            market=market,
            year=year,
            stype_in=stype_in,
        ).as_posix()
    ]
    return output


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


def test_alignment_only_writes_report_for_existing_matching_raw(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    raw_root = tmp_path / "data" / "raw"
    dbn_root = candidate_root / "dbn"
    outputs = [
        _attach_parent_sources(
            _write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018"),
            dbn_root,
        ),
        _attach_parent_sources(
            _write_candidate_file(candidate_root, "SR3", 2019, b"sr3-2019"),
            dbn_root,
        ),
    ]
    for row in outputs:
        target = raw_root / str(row["market"]) / f"{row['year']}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((candidate_root / str(row["market"]) / f"{row['year']}.parquet").read_bytes())

    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    alignment_path = tmp_path / "reports" / "alignment.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=alignment_path,
        alignment_only_existing_raw=True,
    )

    assert report["status"] == "PASS"
    assert report["promoted_count"] == 0
    assert report["alignment_only_existing_raw"] is True
    alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
    assert alignment["status"] == "PASS"
    assert alignment["raw_root"] == raw_root.as_posix()
    assert alignment["expected_market_year_count"] == 2
    assert alignment["raw_market_year_count"] == 2
    assert alignment["source_hash_mismatch_count"] == 0
    assert alignment["raw_file_metrics"][0]["output_hash"] == outputs[0]["output_hash"]


def test_alignment_only_refuses_missing_canonical_target(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    dbn_root = candidate_root / "dbn"
    raw_root = tmp_path / "data" / "raw"
    outputs = [
        _attach_parent_sources(
            _write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018"),
            dbn_root,
        )
    ]
    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    alignment_path = tmp_path / "reports" / "alignment.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=alignment_path,
        alignment_only_existing_raw=True,
    )

    assert report["status"] == "FAIL"
    assert any("canonical target missing" in failure for failure in report["failures"])
    assert not alignment_path.exists()


def test_alignment_only_refuses_mismatched_canonical_target_hash(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    dbn_root = candidate_root / "dbn"
    raw_root = tmp_path / "data" / "raw"
    outputs = [
        _attach_parent_sources(
            _write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018"),
            dbn_root,
        )
    ]
    target = raw_root / "SR1" / "2018.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"different")
    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    alignment_path = tmp_path / "reports" / "alignment.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=alignment_path,
        alignment_only_existing_raw=True,
    )

    assert report["status"] == "FAIL"
    assert any("canonical target hash mismatch" in failure for failure in report["failures"])
    assert target.read_bytes() == b"different"
    assert not alignment_path.exists()


def test_alignment_only_does_not_copy_matching_raw_file(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    dbn_root = candidate_root / "dbn"
    raw_root = tmp_path / "data" / "raw"
    outputs = [
        _attach_parent_sources(
            _write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018"),
            dbn_root,
        )
    ]
    target = raw_root / "SR1" / "2018.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"sr1-2018")
    os.utime(target, (1_700_000_000, 1_700_000_000))
    before = target.stat().st_mtime_ns
    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    alignment_path = tmp_path / "reports" / "alignment.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=alignment_path,
        alignment_only_existing_raw=True,
    )

    assert report["status"] == "PASS"
    assert target.read_bytes() == b"sr1-2018"
    assert target.stat().st_mtime_ns == before


def test_alignment_only_refuses_continuous_source_evidence(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    dbn_root = candidate_root / "dbn"
    raw_root = tmp_path / "data" / "raw"
    outputs = [
        _attach_parent_sources(
            _write_candidate_file(candidate_root, "SR1", 2018, b"sr1-2018"),
            dbn_root,
            stype_in="continuous",
        )
    ]
    target = raw_root / "SR1" / "2018.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"sr1-2018")
    manifest_path = tmp_path / "reports" / "manifest.json"
    readiness_path = tmp_path / "reports" / "readiness.json"
    alignment_path = tmp_path / "reports" / "alignment.json"
    _write_json(manifest_path, _manifest(candidate_root, outputs))
    _write_json(readiness_path, _readiness(len(outputs)))

    report = promoter.promote_candidate(
        candidate_manifest=manifest_path,
        readiness_summary=readiness_path,
        raw_root=raw_root,
        expected_exclusions={("SR3", 2018)},
        promoted_raw_alignment_out=alignment_path,
        alignment_only_existing_raw=True,
    )

    assert report["status"] == "FAIL"
    assert any("stype_in is continuous" in failure for failure in report["failures"])
    assert not alignment_path.exists()
