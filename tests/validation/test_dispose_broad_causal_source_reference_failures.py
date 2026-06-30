from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import dispose_broad_causal_source_reference_failures as dispose


def _write_source(path: Path, payload: bytes = b"source") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return dispose.sha256_file(path)


def _failed_row(pair: str, source_file: str, expected_sha256: str) -> dict[str, object]:
    market, year_text = pair.split(":")
    return {
        "market": market,
        "year": int(year_text),
        "pair": pair,
        "planned_input_raw_path": f"data/raw/{market}/{year_text}.parquet",
        "raw_parquet_sha256": f"raw-{pair}",
        "raw_parquet_row_count": 10,
        "timestamp_min": f"{year_text}-01-02T00:00:00+00:00",
        "timestamp_max": f"{year_text}-12-31T23:59:00+00:00",
        "source_references": [
            {
                "source_file": source_file,
                "expected_sha256": expected_sha256,
                "actual_sha256": None,
                "hash_matches": False,
                "source_present": False,
            }
        ],
        "readiness_status": dispose.SOURCE_REFERENCE_STATUS,
    }


def _readiness(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "summary": {
            "stage": dispose.EXPECTED_STAGE,
            "status": "ACTION_REQUIRED",
            "expected_rows": len(rows),
            "checked_action_required_rows": len(rows),
            "readiness_status_counts": {
                dispose.READY_STATUS: 0,
                dispose.SOURCE_REFERENCE_STATUS: len(rows),
                dispose.DEFERRED_STATUS: 0,
            },
            "data_mutation_performed": False,
            "build_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
        },
        "rows": rows,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _historical_files(tmp_path: Path, source_paths: list[str]) -> list[Path]:
    rel_paths = [
        Path("reports/data_reorg/data_inventory_before.json"),
        Path("reports/data_audit/final/quarantine_plan.md"),
        Path("reports/phase2_readiness/restored/manifest.json"),
    ]
    for rel_path in rel_paths:
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(source_paths), encoding="utf-8")
    return rel_paths


def _two_missing_rows() -> tuple[list[dict[str, object]], list[str]]:
    source_paths = [
        "data/dbn_sr_parent_candidate/SR3/2020/2020-01-01_2021-01-01.dbn.zst",
        "data/dbn_sr_parent_candidate/SR1/2020/2020-01-01_2021-01-01.dbn.zst",
    ]
    rows = [
        _failed_row("SR3:2020", source_paths[0], "1" * 64),
        _failed_row("SR1:2020", source_paths[1], "2" * 64),
    ]
    return rows, source_paths


def test_missing_current_sources_are_blocked_and_historical_only(tmp_path: Path) -> None:
    rows, source_paths = _two_missing_rows()
    readiness_path = tmp_path / "readiness.json"
    _write_json(readiness_path, _readiness(rows))

    report = dispose.build_report(
        repo_root=tmp_path,
        readiness_path=readiness_path,
        generated_at_utc="2026-06-29T00:00:00Z",
        historical_paths=_historical_files(tmp_path, source_paths),
        expected_rows=2,
        expected_checked_action_required=2,
        expected_ready=0,
        expected_source_reference_failures=2,
        expected_deferred=0,
    )

    assert report["summary"]["status"] == "ACTION_REQUIRED"
    assert report["summary"]["disposition_status_counts"][dispose.MISSING_SOURCE_STATUS] == 2
    assert report["summary"]["data_mutation_performed"] is False
    assert report["summary"]["repair_approved"] is False
    assert {row["pair"] for row in report["rows"]} == {"SR3:2020", "SR1:2020"}
    assert all(row["historical_evidence_only"] is True for row in report["rows"])
    assert all(row["source_file_present"] is False for row in report["rows"])
    assert all(row["historical_evidence"][0]["contains_source_path"] is True for row in report["rows"])


def test_matching_recovered_source_requires_readiness_rerun(tmp_path: Path) -> None:
    source_file = "data/dbn_sr_parent_candidate/SR3/2020/source.dbn.zst"
    source_hash = _write_source(tmp_path / source_file)
    rows = [_failed_row("SR3:2020", source_file, source_hash)]
    readiness_path = tmp_path / "readiness.json"
    _write_json(readiness_path, _readiness(rows))

    report = dispose.build_report(
        repo_root=tmp_path,
        readiness_path=readiness_path,
        historical_paths=[],
        expected_rows=1,
        expected_checked_action_required=1,
        expected_ready=0,
        expected_source_reference_failures=1,
        expected_deferred=0,
        expected_failed_pairs={"SR3:2020"},
    )

    row = report["rows"][0]
    assert report["summary"]["status"] == "RERUN_READINESS_REQUIRED"
    assert row["disposition_status"] == dispose.RECOVERED_RERUN_STATUS
    assert row["current_source_hash_matches"] is True


def test_hash_mismatch_blocks_current_source(tmp_path: Path) -> None:
    source_file = "data/dbn_sr_parent_candidate/SR1/2020/source.dbn.zst"
    _write_source(tmp_path / source_file, b"actual")
    rows = [_failed_row("SR1:2020", source_file, "0" * 64)]
    readiness_path = tmp_path / "readiness.json"
    _write_json(readiness_path, _readiness(rows))

    report = dispose.build_report(
        repo_root=tmp_path,
        readiness_path=readiness_path,
        historical_paths=[],
        expected_rows=1,
        expected_checked_action_required=1,
        expected_ready=0,
        expected_source_reference_failures=1,
        expected_deferred=0,
        expected_failed_pairs={"SR1:2020"},
    )

    assert report["rows"][0]["disposition_status"] == dispose.HASH_MISMATCH_STATUS
    assert report["rows"][0]["current_source_hash_matches"] is False


def test_invalid_readiness_counts_fail_closed(tmp_path: Path) -> None:
    rows, _ = _two_missing_rows()
    payload = _readiness(rows)
    payload["summary"]["readiness_status_counts"][dispose.SOURCE_REFERENCE_STATUS] = 3  # type: ignore[index]
    readiness_path = tmp_path / "readiness.json"
    _write_json(readiness_path, payload)

    with pytest.raises(ValueError, match="readiness report invariant failure"):
        dispose.build_report(
            repo_root=tmp_path,
            readiness_path=readiness_path,
            expected_rows=2,
            expected_checked_action_required=2,
            expected_ready=0,
            expected_source_reference_failures=2,
            expected_deferred=0,
        )


def test_unexpected_failed_pair_fails_closed(tmp_path: Path) -> None:
    rows = [_failed_row("ES:2020", "data/dbn_sr_parent_candidate/ES/2020/source.dbn.zst", "0" * 64)]
    readiness_path = tmp_path / "readiness.json"
    _write_json(readiness_path, _readiness(rows))

    with pytest.raises(ValueError, match="source_reference_failed_pairs"):
        dispose.build_report(
            repo_root=tmp_path,
            readiness_path=readiness_path,
            expected_rows=1,
            expected_checked_action_required=1,
            expected_ready=0,
            expected_source_reference_failures=1,
            expected_deferred=0,
        )


def test_write_report_outputs_non_approval_text(tmp_path: Path) -> None:
    rows, source_paths = _two_missing_rows()
    readiness_path = tmp_path / "readiness.json"
    _write_json(readiness_path, _readiness(rows))
    report = dispose.build_report(
        repo_root=tmp_path,
        readiness_path=readiness_path,
        historical_paths=_historical_files(tmp_path, source_paths),
        expected_rows=2,
        expected_checked_action_required=2,
        expected_ready=0,
        expected_source_reference_failures=2,
        expected_deferred=0,
    )
    json_out = tmp_path / "out" / "disposition.json"
    md_out = tmp_path / "out" / "disposition.md"

    dispose.write_report(report, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["stage"] == dispose.OUTPUT_STAGE
    assert payload["summary"]["restore_approved"] is False
    assert payload["summary"]["exclusion_approved"] is False
    assert "does not approve broader modeling" in markdown
    assert "config promotion" in markdown
    assert "historical_evidence_only" in markdown
