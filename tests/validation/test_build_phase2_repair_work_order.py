from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_phase2_repair_work_order as work_order


def _write_checkpoint(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _rows() -> list[dict[str, object]]:
    return [
        {"market": "ES", "year": 2024, "status": "PASS", "warnings": [], "failures": []},
        {
            "market": "SR3",
            "year": 2020,
            "status": "WARN",
            "synthetic_rows_pct": 20.0,
            "max_synthetic_gap_minutes": 120,
            "warnings": ["synthetic threshold breached: rows_pct=20.0"],
            "failures": [],
            "status_enrichment_missing_rows": 10,
            "statistics_enrichment_missing_rows": 20,
        },
        {
            "market": "CL",
            "year": 2022,
            "status": "WARN",
            "degraded_rows_pct": 2.5,
            "degraded_bar_rows": 50,
            "warnings": ["degraded threshold breached: rows_pct=2.5"],
            "failures": [],
        },
        {
            "market": "ZB",
            "year": 2021,
            "status": "WARN",
            "roll_window_rows_pct": 4.0,
            "roll_window_rows": 400,
            "warnings": ["roll exclusion threshold breached: rows_pct=4.0 rows=400"],
            "failures": [],
        },
    ]


def test_report_builds_actionable_work_orders() -> None:
    report = work_order.build_repair_work_order_report(_rows())

    assert report["status"] == "FAIL"
    assert report["policy"] == "FAIL_CLOSED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED"
    assert report["pass_count"] == 1
    assert report["work_order_count"] == 3
    assert report["action_counts"] == {
        "repair_raw_coverage": 1,
        "repair_status_statistics_enrichment": 1,
        "review_session_scope": 1,
        "review_degraded_raw_quality": 1,
        "review_roll_metadata": 1,
        "exclude_only_if_explicitly_approved": 3,
    }
    sr3 = next(row for row in report["work_orders"] if row["market"] == "SR3")
    assert sr3["priority"] == "P0"
    assert sr3["work_order_actions"] == [
        "repair_raw_coverage",
        "repair_status_statistics_enrichment",
        "review_session_scope",
        "exclude_only_if_explicitly_approved",
    ]
    assert sr3["candidate_exclusion_status"] == "DIAGNOSTIC_ONLY_NOT_APPROVED"


def test_drilldown_evidence_is_merged_without_raw_reads() -> None:
    drilldown = {
        ("SR3", 2020): {
            "phase2_session_gap_summary": {
                "candidate_gap_count": 7,
                "synthetic_missing_rows_estimate": 100,
                "max_candidate_gap_minutes": 120.0,
            }
        }
    }

    report = work_order.build_repair_work_order_report(_rows(), drilldown_rows=drilldown)
    sr3 = next(row for row in report["work_orders"] if row["market"] == "SR3")

    assert report["evidence_scope"]["raw_parquet_read"] is False
    assert report["evidence_scope"]["drilldown_json_read"] is True
    assert sr3["drilldown_available"] is True
    assert sr3["phase2_session_candidate_gap_count"] == 7
    assert sr3["phase2_session_synthetic_missing_rows_estimate"] == 100


def test_p0_start_batch_contains_guarded_rerun_commands() -> None:
    report = work_order.build_repair_work_order_report(_rows(), p0_batch_size=1)
    batch = report["p0_repair_start_batch"]

    assert batch["status"] == "REPAIR_REQUIRED_BEFORE_READINESS_RERUN"
    assert batch["all_p0_raw_session_count"] == 1
    assert batch["batch_size"] == 1
    assert batch["readiness_rerun_status"] == "NOT_RUN_NO_REPAIRED_MARKET_YEARS_DECLARED"
    assert batch["batch_market_years"] == [
        {
            "market": "SR3",
            "year": 2020,
            "product_group": "rates",
            "synthetic_rows_pct": 20.0,
            "max_synthetic_gap_minutes": 120,
            "phase2_session_candidate_gap_count": 0,
            "phase2_session_synthetic_missing_rows_estimate": 0,
            "required_decision": "repair_raw_coverage_or_session_scope_before_bounded_readiness",
        }
    ]
    assert (
        "--markets SR3 --years 2020"
        in batch["bounded_readiness_commands_after_repair"][0]["command"]
    )


def test_cli_writes_json_csv_and_markdown(tmp_path: Path, capsys) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    drilldown = tmp_path / "drilldown.json"
    json_out = tmp_path / "work_order.json"
    csv_out = tmp_path / "work_order.csv"
    md_out = tmp_path / "work_order.md"
    _write_checkpoint(checkpoint, _rows())
    drilldown.write_text(json.dumps({"drilldowns": []}), encoding="utf-8")

    result = work_order.main(
        [
            "--checkpoint-jsonl",
            str(checkpoint),
            "--drilldown-json",
            str(drilldown),
            "--json-out",
            str(json_out),
            "--csv-out",
            str(csv_out),
            "--md-out",
            str(md_out),
        ]
    )
    stdout_payload = json.loads(capsys.readouterr().out)
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))

    assert result == 1
    assert stdout_payload["work_order_count"] == 3
    assert json_payload["work_orders"][0]["decision_status"] == (
        "BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED"
    )
    assert "work_order_actions" in csv_out.read_text(encoding="utf-8")
    assert "Phase 2 Repair Work Order" in md_out.read_text(encoding="utf-8")


def test_cli_errors_on_malformed_drilldown(tmp_path: Path, capsys) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    drilldown = tmp_path / "bad.json"
    _write_checkpoint(checkpoint, _rows())
    drilldown.write_text("[]", encoding="utf-8")

    result = work_order.main(
        ["--checkpoint-jsonl", str(checkpoint), "--drilldown-json", str(drilldown)]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["status"] == "FAIL"
    assert "drilldown JSON must be a mapping" in payload["failures"][0]
