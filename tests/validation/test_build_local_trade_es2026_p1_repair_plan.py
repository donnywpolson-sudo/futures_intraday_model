from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_repair_plan as plan_gate


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


def _write_reports(tmp_path: Path, *, market: str = "ES", year: int = 2026) -> tuple[Path, Path, Path]:
    reports_root = tmp_path / "reports" / "es2026"
    reports_root.mkdir(parents=True)
    work_order = reports_root / "ES_2026_repair_work_order.json"
    drilldown = reports_root / "ES_2026_readiness_drilldown.json"
    checkpoint = reports_root / "phase2_readiness.progress.jsonl"
    work_order.write_text(json.dumps(_work_order(market=market, year=year)), encoding="utf-8")
    drilldown.write_text(json.dumps(_drilldown(market=market, year=year)), encoding="utf-8")
    checkpoint.write_text(
        json.dumps({"stage": "phase2_readiness_market_year", "market": market, "year": year}) + "\n",
        encoding="utf-8",
    )
    return work_order, drilldown, checkpoint


def _build(tmp_path: Path, *, staged: list[str] | None = None) -> dict[str, object]:
    work_order, drilldown, checkpoint = _write_reports(tmp_path)
    return plan_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1",
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1" / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
    )


def test_builds_console_only_es2026_p1_repair_plan(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == plan_gate.STATUS_READY
    assert report["summary"]["plan_item_count"] == 3
    assert report["summary"]["command_family_count"] == 7
    assert report["summary"]["approval_required_command_family_count"] == 7
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["candidate_raw_write_approved"] is False
    assert report["summary"]["provider_download_approved"] is False
    assert report["summary"]["readiness_rerun_approved"] is False
    assert report["summary"]["causal_base_repair_approved"] is False
    assert [item["action"] for item in report["plan_items"]] == [
        "statistics_enrichment_repair_or_refresh_plan",
        "degraded_raw_quality_review_plan",
        "keep_exclusion_diagnostic_only_plan",
    ]

    commands = [
        family["command"]
        for item in report["plan_items"]
        for family in item["command_families"]
    ]
    generated = [
        artifact
        for item in report["plan_items"]
        for family in item["command_families"]
        for artifact in family["expected_generated_artifacts"]
    ]
    assert any("--schema statistics" in command and "--dry-run" in command for command in commands)
    assert any("--schema status" in command and "--dry-run" in command for command in commands)
    assert any(path.endswith("phase1a_statistics/databento_download_plan_dry_run.json") for path in generated)
    assert any(path.endswith("phase1a_status/databento_download_plan_dry_run.json") for path in generated)
    assert any("--mode convert-parquet" in command and "--optional-schema-policy require" in command for command in commands)
    assert any("--dbn-root data/dbn/ohlcv_1m" in command for command in commands)
    assert any("--optional-dbn-root data/dbn" in command for command in commands)
    assert any("drilldown_phase2_readiness_blockers" in command and "--markets ES --years 2026" in command for command in commands)
    assert any("--readiness-only" in command and "--readiness-max-market-years 1" in command for command in commands)


def test_wrong_scope_is_no_go(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint = _write_reports(tmp_path, market="NQ", year=2026)

    report = plan_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1",
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1" / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
    )

    assert report["summary"]["status"] == plan_gate.STATUS_NO_GO
    assert report["summary"]["plan_item_count"] == 0
    assert any(
        check["name"] == "proposal_gate_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_path_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/generated.json"])

    assert report["summary"]["status"] == plan_gate.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_output_roots_must_stay_under_generated_roots(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint = _write_reports(tmp_path)

    report = plan_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=tmp_path / "outside_reports",
        candidate_raw_root=tmp_path / "outside_data",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=tmp_path / "outside_reports" / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
    )

    assert report["summary"]["status"] == plan_gate.STATUS_NO_GO
    assert any(
        check["name"] == "repair_reports_root_under_reports"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )
    assert any(
        check["name"] == "candidate_raw_root_under_data"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_is_console_only_and_writes_no_reports(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint = _write_reports(tmp_path)
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = plan_gate.main(
        [
            "--repo-root",
            str(tmp_path),
            "--work-order-report",
            str(work_order),
            "--drilldown-report",
            str(drilldown),
            "--checkpoint-jsonl",
            str(checkpoint),
            "--repair-reports-root",
            str(reports_root),
            "--candidate-raw-root",
            str(tmp_path / "data" / "raw_es2026_candidate"),
            "--output-root",
            str(tmp_path / "data" / "causal_es2026_candidate"),
            "--raw-alignment-report",
            str(reports_root / "alignment.json"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{plan_gate.STAGE} status={plan_gate.STATUS_READY}" in output
    assert "plan_items=3" in output
    assert "command_families=7" in output
    assert "generated_outputs=0" in output
    assert not reports_root.exists()


def test_cli_prints_exact_repair_plan_packet(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint = _write_reports(tmp_path)
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = plan_gate.main(
        [
            "--repo-root",
            str(tmp_path),
            "--work-order-report",
            str(work_order),
            "--drilldown-report",
            str(drilldown),
            "--checkpoint-jsonl",
            str(checkpoint),
            "--repair-reports-root",
            str(reports_root),
            "--candidate-raw-root",
            str(tmp_path / "data" / "raw_es2026_candidate"),
            "--output-root",
            str(tmp_path / "data" / "causal_es2026_candidate"),
            "--raw-alignment-report",
            str(reports_root / "alignment.json"),
            "--print-plan-json",
        ]
    )

    output_lines = capsys.readouterr().out.splitlines()
    packet = json.loads(output_lines[-1])
    commands = [
        family["command"]
        for item in packet["plan_items"]
        for family in item["command_families"]
    ]
    artifacts = [
        artifact
        for item in packet["plan_items"]
        for family in item["command_families"]
        for artifact in family["expected_generated_artifacts"]
    ]

    assert exit_code == 0
    assert output_lines[0].startswith(f"{plan_gate.STAGE} status={plan_gate.STATUS_READY}")
    assert packet["plan_item_count"] == 3
    assert packet["command_family_count"] == 7
    assert packet["approval_required_command_family_count"] == 7
    assert packet["generated_artifact_hygiene"] == {
        "generated_output_count": 0,
        "staged_generated_path_count": 0,
    }
    assert any("--schema statistics" in command and "--dry-run" in command for command in commands)
    assert any("--readiness-only" in command for command in commands)
    assert any(path.endswith("ES_2026_candidate_raw_quality_drilldown.json") for path in artifacts)
    assert not reports_root.exists()
