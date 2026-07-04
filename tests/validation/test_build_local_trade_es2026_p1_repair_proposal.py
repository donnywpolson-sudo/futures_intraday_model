from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_repair_proposal as proposal


def _work_order(*, market: str = "ES", year: int = 2026) -> dict[str, object]:
    return {
        "stage": "phase2_repair_work_order",
        "status": "FAIL",
        "ready_to_rebuild_tier3_phase2": False,
        "work_order_count": 1,
        "p0_repair_start_batch": {
            "status": "REPAIR_REQUIRED_BEFORE_READINESS_RERUN",
            "all_p0_raw_session_count": 0,
            "batch_size": 0,
            "readiness_rerun_status": "NOT_RUN_NO_REPAIRED_MARKET_YEARS_DECLARED",
        },
        "work_orders": [
            {
                "market": market,
                "year": year,
                "priority": "P1",
                "decision_status": "BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED",
                "candidate_exclusion_status": "DIAGNOSTIC_ONLY_NOT_APPROVED",
                "work_order_actions": [
                    "repair_status_statistics_enrichment",
                    "review_degraded_raw_quality",
                    "exclude_only_if_explicitly_approved",
                ],
                "degraded_bar_rows": 2760,
                "degraded_rows_pct": 1.74227,
                "degraded_session_rows": 3,
                "statistics_enrichment_missing_rows": 6,
                "statistics_enrichment_stale_rows": 6,
                "synthetic_rows": 1,
                "synthetic_rows_pct": 0.000631,
                "phase2_session_candidate_gap_count": 113,
                "phase2_session_synthetic_missing_rows_estimate": 1681,
            }
        ],
    }


def _drilldown(*, market: str = "ES", year: int = 2026) -> dict[str, object]:
    return {
        "stage": "phase2_readiness_raw_drilldown",
        "status": "FAIL",
        "selected_market_year_count": 1,
        "selected_market_years": [{"market": market, "year": year}],
        "drilldowns": [
            {
                "market": market,
                "year": year,
                "raw_read_status": "PASS",
                "raw_path": f"data/raw/{market}/{year}.parquet",
                "degraded_bar_rows": 2760,
                "degraded_rows_pct": 1.74227,
                "degraded_session_rows": 3,
                "statistics_enrichment_missing_rows": 6,
                "statistics_enrichment_stale_rows": 6,
                "raw_gap_summary": {
                    "gap_count": 116,
                    "max_gap_minutes": 3406.0,
                },
                "phase2_session_gap_summary": {
                    "candidate_gap_count": 113,
                    "max_candidate_gap_minutes": 16.0,
                    "synthetic_missing_rows_estimate": 1681,
                },
                "top_statistics_missing_dates": [
                    {"date": "2026-03-18", "row_count": 6}
                ],
                "top_degraded_dates": [{"date": "2026-03-16", "row_count": 1380}],
            }
        ],
    }


def _write_reports(tmp_path: Path, *, market: str = "ES", year: int = 2026) -> tuple[Path, Path]:
    reports_root = tmp_path / "reports" / "es2026"
    reports_root.mkdir(parents=True)
    work_order = reports_root / "ES_2026_repair_work_order.json"
    drilldown = reports_root / "ES_2026_readiness_drilldown.json"
    work_order.write_text(json.dumps(_work_order(market=market, year=year)), encoding="utf-8")
    drilldown.write_text(json.dumps(_drilldown(market=market, year=year)), encoding="utf-8")
    return work_order, drilldown


def test_builds_console_only_es2026_p1_repair_proposal(tmp_path: Path) -> None:
    work_order, drilldown = _write_reports(tmp_path)

    report = proposal.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
    )

    assert report["summary"]["status"] == proposal.STATUS_READY
    assert report["summary"]["proposal_item_count"] == 3
    assert report["summary"]["p1_work_order_count"] == 1
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["statistics_enrichment_repair_approved"] is False
    assert report["summary"]["causal_base_repair_approved"] is False
    assert report["summary"]["exclusion_approved"] is False
    assert [item["action"] for item in report["proposal_items"]] == [
        "repair_or_refresh_statistics_enrichment_evidence",
        "review_degraded_raw_quality_evidence",
        "keep_exclusion_diagnostic_only",
    ]
    assert all(item["proposal_status"] == proposal.PROPOSAL_STATUS_APPROVAL_REQUIRED for item in report["proposal_items"])
    assert report["proposal_items"][0]["current_evidence"]["statistics_enrichment_missing_rows"] == 6
    assert report["proposal_items"][1]["current_evidence"]["phase2_session_candidate_gap_count"] == 113


def test_wrong_scope_is_no_go(tmp_path: Path) -> None:
    work_order, drilldown = _write_reports(tmp_path, market="NQ", year=2026)

    report = proposal.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
    )

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert report["summary"]["proposal_item_count"] == 0
    assert any(
        check["name"] == "work_order_exact_es2026_scope"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )
    assert any(
        check["name"] == "drilldown_exact_es2026_scope"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_paths_are_no_go(tmp_path: Path) -> None:
    work_order, drilldown = _write_reports(tmp_path)

    report = proposal.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=["reports/generated.json"],
    )

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_is_console_only_and_writes_no_reports(tmp_path: Path, capsys) -> None:
    work_order, drilldown = _write_reports(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = proposal.main(
        [
            "--repo-root",
            str(tmp_path),
            "--work-order-report",
            str(work_order),
            "--drilldown-report",
            str(drilldown),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{proposal.STAGE} status={proposal.STATUS_READY}" in output
    assert "proposal_items=3" in output
    assert "generated_outputs=0" in output
    assert not list((tmp_path / "reports").glob(f"**/{proposal.STAGE}*"))
