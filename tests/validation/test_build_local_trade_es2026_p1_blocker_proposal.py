from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_blocker_proposal as proposal
from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_review as readiness_review
from scripts.validation import build_local_trade_es2026_p1_workflow_status as workflow_status
from scripts.validation import build_local_trade_optional_archive_inventory as optional_inventory


def _workflow_report(
    *,
    status: str = workflow_status.STATUS_NO_GO,
    current_gate: str = "candidate_readiness_execution",
    current_gate_status: str = "NO_GO_ES2026_P1_CANDIDATE_READINESS_EXECUTION",
) -> dict[str, object]:
    return {
        "summary": {
            "stage": workflow_status.STAGE,
            "status": status,
            "market": "ES",
            "year": 2026,
            "current_gate": current_gate,
            "current_gate_status": current_gate_status,
            "next_action_kind": "fix_or_repair_gate",
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
        }
    }


def _readiness_review_report(
    *,
    status: str = readiness_review.STATUS_NO_GO,
) -> dict[str, object]:
    return {
        "summary": {
            "stage": readiness_review.STAGE,
            "status": status,
            "market": "ES",
            "year": 2026,
            "expected_readiness_output_count": 8,
            "ignored_expected_readiness_output_count": 8,
            "unignored_expected_readiness_output_count": 0,
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
            "failure_count": 1,
        }
    }


def _optional_inventory_report(
    *,
    status: str = optional_inventory.STATUS_READY,
    ready_markets: int = 33,
    invalid_archives: int = 0,
) -> dict[str, object]:
    return {
        "summary": {
            "stage": optional_inventory.STAGE,
            "status": status,
            "year": 2026,
            "start": "2026-01-01",
            "end": "2026-06-13",
            "schemas": ["statistics", "status"],
            "market_count": 33,
            "expected_market_count": 33,
            "ready_market_count": ready_markets,
            "invalid_market_count": 33 - ready_markets,
            "archive_count": 66,
            "invalid_archive_count": invalid_archives,
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
            "failure_count": 0 if status == optional_inventory.STATUS_READY else 1,
        }
    }


def _raw_quality(
    *,
    status: str = "FAIL",
    market: str = "ES",
    year: int = 2026,
    reason: str = "degraded threshold breached: rows_pct=1.74227 bars=2760 sessions=3",
) -> dict[str, object]:
    return {
        "stage": "phase2_readiness_raw_drilldown",
        "status": status,
        "selected_market_year_count": 1,
        "selected_market_years": [{"market": market, "year": year}],
        "drilldowns": [
            {
                "market": market,
                "year": year,
                "raw_read_status": "PASS",
                "degraded_bar_rows": 2760,
                "degraded_rows_pct": 1.74227,
                "degraded_session_rows": 3,
                "statistics_enrichment_missing_rows": 6,
                "statistics_enrichment_stale_rows": 6,
                "top_blocker_reason": reason,
            }
        ],
    }


def _write_raw_quality(tmp_path: Path, payload: dict[str, object] | None = None) -> Path:
    path = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v2" / "ES_2026_candidate_raw_quality_drilldown.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload or _raw_quality()), encoding="utf-8")
    return path


def _build(
    tmp_path: Path,
    *,
    workflow: dict[str, object] | None = None,
    readiness: dict[str, object] | None = None,
    optional: dict[str, object] | None = None,
    raw_quality_payload: dict[str, object] | None = None,
    staged: list[str] | None = None,
) -> dict[str, object]:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v2"
    raw_quality_report = _write_raw_quality(tmp_path, raw_quality_payload)
    return proposal.build_report(
        repo_root=tmp_path,
        work_order_report=reports_root / "work_order.json",
        drilldown_report=reports_root / "drilldown.json",
        checkpoint_jsonl=reports_root / "checkpoint.jsonl",
        repair_reports_root=reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_p1_repair_candidate",
        output_root=tmp_path / "data" / "causal_es2026_p1_candidate",
        raw_alignment_report=reports_root / "candidate_raw_alignment.json",
        raw_quality_report=raw_quality_report,
        workflow_status_report=workflow or _workflow_report(),
        candidate_readiness_review_report=readiness or _readiness_review_report(),
        optional_archive_inventory_report=optional or _optional_inventory_report(),
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=staged or [],
    )


def test_builds_source_tests_docs_only_blocker_proposal(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == proposal.STATUS_READY
    assert report["summary"]["proposal_item_count"] == 1
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False
    assert report["summary"]["causal_base_repair_approved"] is False
    assert report["summary"]["accepted_warning_packet_approved"] is False
    assert report["summary"]["exclusion_approved"] is False
    item = report["proposal_items"][0]
    assert item["proposal"] == "source_tests_docs_only_blocker_proposal_gate"
    assert item["current_blocker"]["degraded_bar_rows"] == 2760
    assert item["current_blocker"]["degraded_rows_pct"] == 1.74227
    plan = item["bounded_next_step_plan"]
    assert plan["command_family"] == "source_tests_docs_only_blocker_proposal_gate"
    assert plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert plan["maximum_scope"]["profile"] == "tier_3_forward"
    assert plan["timeout_seconds_per_command"] == 30
    assert "provider_download_without_separate_approval" in plan["forbidden_patterns"]
    assert "raw-quality drilldown is FAIL for exactly ES 2026 with degraded threshold evidence" in plan[
        "required_evidence"
    ]
    assert any(
        check["name"] == "bounded_next_step_plan_complete"
        for check in report["checks"]
        if check["status"] == "PASS"
    )


def test_wrong_workflow_gate_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        workflow=_workflow_report(
            status=workflow_status.STATUS_ACTION_REQUIRED,
            current_gate="candidate_readiness_execution",
            current_gate_status="DRY_RUN_READY_ES2026_P1_CANDIDATE_READINESS_EXECUTION",
        ),
    )

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert report["summary"]["proposal_item_count"] == 0
    assert any(
        check["name"] == "workflow_status_at_candidate_readiness_no_go"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_optional_inventory_not_ready_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        optional=_optional_inventory_report(
            status=optional_inventory.STATUS_NO_GO,
            ready_markets=32,
            invalid_archives=1,
        ),
    )

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert report["summary"]["optional_archive_inventory_status"] == optional_inventory.STATUS_NO_GO
    assert any(
        check["name"] == "optional_archive_inventory_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_raw_quality_without_degraded_threshold_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        raw_quality_payload=_raw_quality(
            status="PASS",
            reason="not a degraded threshold failure",
        ),
    )

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert any(
        check["name"] == "raw_quality_degraded_threshold_failure_present"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_artifacts_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/generated.json"])

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_plan_packet_includes_bounded_plan_and_hygiene(tmp_path: Path) -> None:
    report = _build(tmp_path)

    packet = proposal.plan_packet(report)

    assert packet["status"] == proposal.STATUS_READY
    assert packet["proposal_item_count"] == 1
    assert packet["bounded_next_step_plan"]["command_family"] == "source_tests_docs_only_blocker_proposal_gate"
    assert packet["generated_artifact_hygiene"] == {
        "generated_output_count": 0,
        "staged_generated_path_count": 0,
    }


def test_cli_prints_plan_packet_without_writing_reports(tmp_path: Path, capsys, monkeypatch) -> None:
    report = _build(tmp_path)
    monkeypatch.setattr(proposal, "build_report", lambda **kwargs: report)

    exit_code = proposal.main(["--repo-root", str(tmp_path), "--print-plan-json"])

    output_lines = capsys.readouterr().out.splitlines()
    packet = json.loads(output_lines[-1])
    assert exit_code == 0
    assert output_lines[0].startswith(f"{proposal.STAGE} status={proposal.STATUS_READY}")
    assert packet["bounded_next_step_plan"]["command_family"] == "source_tests_docs_only_blocker_proposal_gate"
    assert not list(tmp_path.glob("**/*blocker_proposal*.json"))
