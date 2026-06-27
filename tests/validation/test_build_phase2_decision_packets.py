from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import build_phase2_decision_packets as packets


def _warn_row() -> dict[str, object]:
    return {
        "market": "ZS",
        "year": 2021,
        "status": "WARN",
        "warnings": [
            "roll maturity sequence not monotonic: backsteps=1",
            "synthetic threshold breached: rows_pct=10.787787 max_gap_minutes=46",
        ],
        "failures": [],
        "output_rows": 275506,
        "synthetic_rows": 29721,
        "synthetic_rows_pct": 10.787787,
        "max_synthetic_gap_minutes": 46,
        "degraded_bar_rows": 0,
        "degraded_session_rows": 0,
        "roll_maturity_backstep_count": 1,
        "status_enrichment_missing_rows": 0,
        "status_enrichment_stale_rows": 0,
        "statistics_enrichment_missing_rows": 0,
        "statistics_enrichment_stale_rows": 0,
        "top_blocker_reason": "roll maturity sequence not monotonic: backsteps=1",
    }


def _write_checkpoint(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_build_packet_records_fail_closed_policy() -> None:
    packet = packets.build_packet(
        _warn_row(),
        raw={
            "path": "data/raw/ZS/2021.parquet",
            "exists": True,
            "row_count": 245785,
            "sha256": "abc",
            "source_files": [
                "data/dbn/ohlcv_1m/ZS/2021/2021-01-01_2022-01-01.dbn.zst"
            ],
        },
        generated_at_utc="2026-06-26T00:00:00Z",
        checkpoint_jsonl=Path("checkpoint.jsonl"),
    )

    assert packet["status"] == "ACTION_REQUIRED"
    assert packet["phase2_readiness_evidence"]["decision_status"] == (
        packets.DECISION_STATUS
    )
    assert packet["phase2_readiness_evidence"]["synthetic_rows"] == 29721
    assert packet["phase2_readiness_evidence"]["roll_maturity_backstep_count"] == 1
    assert packet["policy_decision"]["decision"] == "keep_fail_closed"
    assert packet["policy_decision"]["accepted_readiness_exception_added"] is False
    assert packet["policy_decision"]["canonical_phase2_rebuild_approved"] is False


def test_build_packet_refuses_pass_rows() -> None:
    row = _warn_row()
    row["status"] = "PASS"

    with pytest.raises(ValueError, match="is PASS"):
        packets.build_packet(
            row,
            raw={"path": "data/raw/ZS/2021.parquet", "exists": True},
            generated_at_utc="2026-06-26T00:00:00Z",
            checkpoint_jsonl=Path("checkpoint.jsonl"),
        )


def test_cli_writes_json_and_markdown_packets(tmp_path: Path, capsys) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    reports_root = tmp_path / "reports"
    _write_checkpoint(checkpoint, [_warn_row()])

    result = packets.main(
        [
            "--checkpoint-jsonl",
            str(checkpoint),
            "--raw-root",
            str(tmp_path / "raw"),
            "--reports-root",
            str(reports_root),
            "--markets",
            "ZS",
            "--years",
            "2021",
            "--date-tag",
            "20260626",
        ]
    )
    stdout = json.loads(capsys.readouterr().out)
    json_path = (
        reports_root
        / "ZS_2021_scope_20260626"
        / "ZS_2021_decision_packet_20260626.json"
    )
    md_path = (
        reports_root
        / "ZS_2021_scope_20260626"
        / "ZS_2021_decision_packet_20260626.md"
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result == 0
    assert stdout["status"] == "PASS"
    assert json_path.exists()
    assert md_path.exists()
    assert payload["policy_decision"]["decision"] == "keep_fail_closed"
    assert "accepted_readiness_exception" in md_path.read_text(encoding="utf-8")


def test_matching_rows_fails_for_missing_requested_scope() -> None:
    with pytest.raises(ValueError, match="missing checkpoint rows: ZS 2022"):
        packets._matching_rows([_warn_row()], markets=["ZS"], years=[2021, 2022])
