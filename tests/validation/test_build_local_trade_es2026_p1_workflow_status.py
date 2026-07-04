from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_workflow_status as status_gate
from scripts.validation import build_local_trade_optional_archive_inventory as optional_inventory
from scripts.validation import run_local_trade_es2026_p1_dry_run_diagnostics as dry_runner
from scripts.validation import build_local_trade_es2026_p1_downstream_wfa_split_gate as downstream_wfa_split_gate
from scripts.validation import run_local_trade_es2026_p1_downstream_feature_build as downstream_feature_runner
from scripts.validation import run_local_trade_es2026_p1_downstream_label_build as downstream_label_runner
from scripts.validation import run_local_trade_es2026_p1_downstream_metrics_build as downstream_metrics_runner
from scripts.validation import run_local_trade_es2026_p1_downstream_model_build as downstream_model_runner
from scripts.validation import run_local_trade_es2026_p1_downstream_wfa_split_build as downstream_wfa_split_runner
from tests.validation import test_build_local_trade_es2026_p1_candidate_conversion_plan as conversion_plan_fixtures
from tests.validation import test_build_local_trade_es2026_p1_candidate_conversion_review as conversion_review_fixtures
from tests.validation import test_build_local_trade_es2026_p1_candidate_readiness_plan as readiness_plan_fixtures
from tests.validation import test_build_local_trade_es2026_p1_candidate_readiness_review as readiness_review_fixtures
from tests.validation import test_build_local_trade_es2026_p1_optional_archive_availability as availability_fixtures
from tests.validation import test_run_local_trade_es2026_p1_dry_run_diagnostics as runner_fixtures


LABEL_EXPECTED_ARTIFACTS = [
    "data/labeled/local_trade_es2026_p1_candidate/ES/2026.parquet",
    "reports/labels/local_trade_es2026_p1_candidate/label_manifest.json",
    "reports/labels/local_trade_es2026_p1_candidate/label_report.json",
]


def _ready_inventory_report() -> dict[str, object]:
    return {
        "summary": {
            "stage": optional_inventory.STAGE,
            "status": optional_inventory.STATUS_READY,
            "year": 2026,
            "start": "2026-01-01",
            "end": "2026-06-13",
            "schemas": ["statistics", "status"],
            "market_count": 33,
            "expected_market_count": 33,
            "ready_market_count": 33,
            "invalid_market_count": 0,
            "archive_count": 66,
            "invalid_archive_count": 0,
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
            "failure_count": 0,
        }
    }


def _build(tmp_path: Path, *, staged: list[str] | None = None) -> dict[str, object]:
    work_order, drilldown, checkpoint, repair_reports_root = runner_fixtures._setup(tmp_path)
    ignored_paths = runner_fixtures._expected_dry_run_paths(repair_reports_root, tmp_path)
    return status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths,
        optional_archive_inventory_report=_ready_inventory_report(),
    )


def test_current_boundary_is_dry_run_execution_when_plans_are_absent(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "dry_run_diagnostics_execution"
    assert report["summary"]["current_gate_status"] == dry_runner.STATUS_DRY_RUN_READY
    assert report["summary"]["next_action_kind"] == "approve_bounded_generated_dry_run_plans"
    assert report["summary"]["human_approval_required"] is True
    assert report["summary"]["execution_approval_required"] is True
    assert report["current_boundary"]["execution_approval_required"] is True
    assert report["summary"]["optional_archive_inventory_status"] == optional_inventory.STATUS_READY
    assert report["summary"]["optional_archive_inventory_ready_market_count"] == 33
    assert report["summary"]["optional_archive_inventory_invalid_archive_count"] == 0
    assert report["supporting_evidence"]["optional_archive_inventory"]["archive_count"] == 66
    inventory_summary = next(
        gate for gate in report["gate_summaries"] if gate["gate"] == "optional_archive_inventory"
    )
    assert inventory_summary["ready_market_count"] == 33
    assert report["summary"]["expected_generated_output_count"] == 2
    assert report["summary"]["ignored_expected_generated_output_count"] == 2
    assert report["summary"]["unignored_expected_generated_output_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["provider_download_approved"] is False
    assert dry_runner.APPROVAL_TOKEN in report["current_boundary"]["recommended_command"]
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_family"] == "phase1a_download_dry_run_only"
    assert bounded_plan["command_count"] == 2
    assert bounded_plan["maximum_scope"] == {
        "market_years": [{"market": "ES", "year": 2026}],
        "schemas": ["statistics", "status"],
        "start": "2026-01-01",
        "end": "2026-06-13",
        "network": False,
        "data_mutation": False,
    }
    assert bounded_plan["timeout_seconds_per_command"] == 180
    assert bounded_plan["expected_generated_artifacts"] == report["current_boundary"][
        "expected_generated_artifacts"
    ]
    assert "provider_download_without_separate_approval" in bounded_plan["forbidden_patterns"]
    assert "--estimate-cost" in bounded_plan["forbidden_argument_flags"]
    assert "ignored and unstaged" in bounded_plan["stop_condition"]
    assert any(
        check["name"] == "approval_boundary_expected_outputs_ignored"
        for check in report["checks"]
        if check["status"] == "PASS"
    )
    assert any(
        check["name"] == "approval_boundary_bounded_plan_complete"
        for check in report["checks"]
        if check["status"] == "PASS"
    )


def test_unignored_approval_boundary_outputs_fail_closed(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = runner_fixtures._setup(tmp_path)
    expected_paths = runner_fixtures._expected_dry_run_paths(repair_reports_root, tmp_path)

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=expected_paths[:1],
    )

    assert report["summary"]["status"] == status_gate.STATUS_NO_GO
    assert report["summary"]["current_gate"] == "dry_run_diagnostics_execution"
    dry_run_gate = next(
        gate for gate in report["gate_summaries"] if gate["gate"] == "dry_run_diagnostics_execution"
    )
    assert dry_run_gate["expected_output_count"] == 2
    assert dry_run_gate["ignored_expected_output_count"] == 1
    assert dry_run_gate["unignored_expected_output_count"] == 1
    assert status_gate._boundary_artifact_counts(
        expected_artifacts=expected_paths,
        current_gate_record={},
        ignored_generated_paths=expected_paths[:1],
    ) == (2, 1, 1)


def test_incomplete_approval_boundary_plan_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(status_gate, "_dry_run_bounded_plan", lambda report: {"command_family": ""})
    report = _build(tmp_path)

    assert report["summary"]["status"] == status_gate.STATUS_NO_GO
    assert any(
        check["name"] == "approval_boundary_bounded_plan_complete"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_current_boundary_counts_only_its_expected_ignored_paths(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = runner_fixtures._setup(tmp_path)
    ignored_paths = [
        *runner_fixtures._expected_dry_run_paths(repair_reports_root, tmp_path),
        "reports/pipeline_audit/repair_plan_v1/future_step/extra.json",
    ]

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "dry_run_diagnostics_execution"
    assert report["summary"]["expected_generated_output_count"] == 2
    assert report["summary"]["ignored_expected_generated_output_count"] == 2
    assert report["summary"]["unignored_expected_generated_output_count"] == 0
    assert any(
        check["name"] == "approval_boundary_expected_outputs_ignored"
        for check in report["checks"]
        if check["status"] == "PASS"
    )


def test_staged_generated_artifact_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/generated.json"])

    assert report["summary"]["status"] == status_gate.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_repair_plan_evidence_is_no_go(tmp_path: Path) -> None:
    repair_reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=tmp_path / "missing_work_order.json",
        drilldown_report=tmp_path / "missing_drilldown.json",
        checkpoint_jsonl=tmp_path / "missing.progress.jsonl",
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=[],
    )

    assert report["summary"]["status"] == status_gate.STATUS_NO_GO
    assert report["summary"]["current_gate"] == "repair_plan"
    assert report["summary"]["generated_output_count"] == 0


def test_moves_to_archive_decision_when_dry_run_plans_exist(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = runner_fixtures._setup(tmp_path)
    availability_fixtures._write_plans(tmp_path)

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=availability_fixtures._ignored_paths(repair_reports_root, tmp_path),
    )

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "optional_archive_availability"
    assert report["summary"]["next_action_kind"] == "approve_optional_archive_acquisition_or_cost_diagnostic"
    expected_artifacts = availability_fixtures._expected_archive_artifact_paths(tmp_path)
    assert report["summary"]["expected_generated_output_count"] == len(expected_artifacts)
    assert report["current_boundary"]["expected_generated_artifacts"] == expected_artifacts
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_family"] == "optional_archive_acquisition_or_provider_cost_diagnostic"
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["schemas"] == ["statistics", "status"]
    assert bounded_plan["maximum_scope"]["network"] == "separate_approval_required"
    assert bounded_plan["timeout_seconds_per_command"] == 180
    assert bounded_plan["expected_generated_artifacts"] == expected_artifacts
    assert "provider_download_without_separate_approval" in bounded_plan["forbidden_patterns"]
    assert "--estimate-cost" in bounded_plan["forbidden_argument_flags"]
    assert "separate approval" in bounded_plan["stop_condition"]
    assert report["summary"]["generated_output_count"] == 0


def test_moves_to_candidate_conversion_execution_when_archives_are_reusable(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = runner_fixtures._setup(tmp_path)
    availability_fixtures._write_plans(tmp_path)
    for schema in availability_fixtures.availability.TARGET_SCHEMAS:
        availability_fixtures._write_archive_and_manifest(tmp_path, schema)
    ignored_paths = conversion_plan_fixtures._ignored_paths(tmp_path, repair_reports_root)

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    expected_artifacts = conversion_plan_fixtures._candidate_expected_output_paths(tmp_path)
    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "candidate_conversion_execution"
    assert report["summary"]["next_action_kind"] == "approve_bounded_candidate_raw_conversion"
    assert report["summary"]["expected_generated_output_count"] == len(expected_artifacts)
    assert report["current_boundary"]["expected_generated_artifacts"] == expected_artifacts
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_count"] == 2
    assert "phase1a_convert_existing_dbn_to_candidate_raw" in bounded_plan["command_family"]
    assert "optional_enrichment_schema_audit" in bounded_plan["command_family"]
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["schemas"] == ["ohlcv-1m", "status", "statistics"]
    assert bounded_plan["maximum_scope"]["network"] is False
    assert bounded_plan["maximum_scope"]["data_mutation"] is True
    assert bounded_plan["expected_generated_artifacts"] == expected_artifacts
    assert "candidate conversion produces only the planned ES 2026" in bounded_plan["stop_condition"]
    assert any(
        check["name"] == "approval_boundary_bounded_plan_complete"
        for check in report["checks"]
        if check["status"] == "PASS"
    )


def test_moves_to_candidate_readiness_execution_when_conversion_outputs_are_ready(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, _ = (
        conversion_review_fixtures._setup(tmp_path)
    )
    conversion_review_fixtures._write_conversion_outputs(
        candidate_raw_root=candidate_raw_root,
        repair_reports_root=repair_reports_root,
    )
    ignored_paths = readiness_plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_readiness_outputs=True,
    )

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=repair_reports_root
        / "candidate_raw_alignment"
        / "ES_2026_candidate_raw_dbn_alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    expected_artifacts = readiness_plan_fixtures._expected_output_paths(tmp_path)
    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "candidate_readiness_execution"
    assert report["summary"]["next_action_kind"] == "approve_bounded_candidate_readiness_diagnostics"
    assert report["summary"]["recommended_next_action"] == status_gate.CANDIDATE_READINESS_APPROVAL_COMMAND
    assert report["current_boundary"]["recommended_command"] == status_gate.CANDIDATE_READINESS_APPROVAL_COMMAND
    assert "APPROVE_ES2026_P1_CANDIDATE_READINESS_V1" in report["current_boundary"]["recommended_command"]
    assert report["summary"]["expected_generated_output_count"] == len(expected_artifacts)
    assert report["current_boundary"]["expected_generated_artifacts"] == expected_artifacts
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_count"] == 3
    assert "phase2_readiness_raw_drilldown" in bounded_plan["command_family"]
    assert "phase1c_raw_dbn_alignment_expected_only" in bounded_plan["command_family"]
    assert "phase2_readiness_only_exact_scope" in bounded_plan["command_family"]
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["profile"] == "tier_3_forward"
    assert bounded_plan["maximum_scope"]["network"] is False
    assert bounded_plan["maximum_scope"]["data_mutation"] is False
    assert bounded_plan["expected_generated_artifacts"] == expected_artifacts
    assert "candidate readiness diagnostics produce only the planned ES 2026" in bounded_plan[
        "stop_condition"
    ]
    assert any(
        check["name"] == "approval_boundary_bounded_plan_complete"
        for check in report["checks"]
        if check["status"] == "PASS"
    )


def test_moves_to_downstream_label_execution_when_readiness_review_is_ready(
    tmp_path: Path, monkeypatch
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        readiness_review_fixtures.runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    readiness_review_fixtures._write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    label_expected_artifacts = [
        "data/labeled/local_trade_es2026_p1_candidate/ES/2026.parquet",
        "reports/labels/local_trade_es2026_p1_candidate/label_manifest.json",
        "reports/labels/local_trade_es2026_p1_candidate/label_report.json",
    ]
    ignored_paths = readiness_plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_readiness_outputs=True,
    ) + label_expected_artifacts

    def ready_label_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_label_runner.STAGE,
                "status": downstream_label_runner.STATUS_DRY_RUN_READY,
                "expected_generated_output_count": len(label_expected_artifacts),
                "ignored_expected_generated_output_count": len(label_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 0,
                "recommended_next_action": status_gate.DOWNSTREAM_LABEL_APPROVAL_COMMAND,
            },
            "planned_command": {
                "command_family": "phase3_label_build_exact_es2026_candidate",
                "command": "python -m scripts.phase3_labels.build_labels --markets ES --years 2026",
                "timeout_seconds": 900,
                "expected_generated_artifacts": label_expected_artifacts,
            },
            "checks": [],
        }

    monkeypatch.setattr(
        status_gate.downstream_label_runner,
        "build_report",
        ready_label_runner_report,
    )

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "downstream_label_build_execution"
    assert report["summary"]["current_gate_status"] == downstream_label_runner.STATUS_DRY_RUN_READY
    assert report["summary"]["next_action_kind"] == "approve_bounded_downstream_label_build"
    assert report["summary"]["recommended_next_action"] == status_gate.DOWNSTREAM_LABEL_APPROVAL_COMMAND
    assert report["current_boundary"]["recommended_command"] == status_gate.DOWNSTREAM_LABEL_APPROVAL_COMMAND
    assert report["current_boundary"]["approval_token"] == downstream_label_runner.APPROVAL_TOKEN
    assert report["current_boundary"]["expected_generated_artifacts"] == label_expected_artifacts
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_family"] == "phase3_label_build_exact_es2026_candidate"
    assert bounded_plan["command_count"] == 1
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["profile"] == "tier_3_forward"
    assert bounded_plan["maximum_scope"]["network"] is False
    assert bounded_plan["maximum_scope"]["data_mutation"] is True
    assert bounded_plan["expected_generated_artifacts"] == label_expected_artifacts
    assert "Phase 3 label build produces only the planned ES 2026" in bounded_plan[
        "stop_condition"
    ]


def test_stops_at_downstream_label_no_go_when_labels_are_absent(
    tmp_path: Path, monkeypatch
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        readiness_review_fixtures.runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    readiness_review_fixtures._write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    label_expected_artifacts = [
        "data/labeled/local_trade_es2026_p1_candidate/ES/2026.parquet",
        "reports/labels/local_trade_es2026_p1_candidate/label_manifest.json",
        "reports/labels/local_trade_es2026_p1_candidate/label_report.json",
    ]
    ignored_paths = readiness_plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_readiness_outputs=True,
    ) + label_expected_artifacts

    def blocked_label_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_label_runner.STAGE,
                "status": downstream_label_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(label_expected_artifacts),
                "ignored_expected_generated_output_count": len(label_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 1,
                "recommended_next_action": (
                    "Wire approved ES 2026 accepted-warning evidence through the Phase 3 "
                    "label command and validation tests, then rerun this console-only gate."
                ),
            },
            "planned_command": {
                "command_family": "phase3_label_build_exact_es2026_candidate",
                "expected_generated_artifacts": label_expected_artifacts,
            },
            "checks": [
                {
                    "name": "phase3_accepted_warning_handling_wired",
                    "status": "FAIL",
                    "observed": {"causal_base_manifest_accepted_exception_count": 1},
                    "expected": "wired Phase 3 accepted-warning evidence path",
                    "detail": "The label command is not accepted-warning compatible.",
                }
            ],
        }

    def feature_runner_should_not_run(**_kwargs):
        raise AssertionError("feature runner should not run while labels are absent")

    monkeypatch.setattr(
        status_gate.downstream_label_runner,
        "build_report",
        blocked_label_runner_report,
    )
    monkeypatch.setattr(
        status_gate.downstream_feature_runner,
        "build_report",
        feature_runner_should_not_run,
    )

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_NO_GO
    assert report["summary"]["current_gate"] == "downstream_label_build_execution"
    assert report["summary"]["current_gate_status"] == downstream_label_runner.STATUS_NO_GO
    assert report["summary"]["next_action_kind"] == "fix_or_repair_gate"
    assert report["summary"]["approval_token"] is None
    assert report["summary"]["execution_approval_required"] is False
    assert report["current_boundary"]["recommended_command"] is None
    assert report["current_boundary"]["expected_generated_artifacts"] == []
    assert "accepted-warning evidence" in report["summary"]["recommended_next_action"]


def test_moves_to_downstream_feature_execution_after_labels_are_complete(
    tmp_path: Path, monkeypatch
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        readiness_review_fixtures.runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    readiness_review_fixtures._write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    label_expected_artifacts = [
        "data/labeled/local_trade_es2026_p1_candidate/ES/2026.parquet",
        "reports/labels/local_trade_es2026_p1_candidate/label_manifest.json",
        "reports/labels/local_trade_es2026_p1_candidate/label_report.json",
    ]
    feature_expected_artifacts = [
        "data/feature_matrices/local_trade_es2026_p1_candidate/ES/2026.parquet",
        "data/feature_matrices/local_trade_es2026_p1_candidate/excluded_cols.json",
        "data/feature_matrices/local_trade_es2026_p1_candidate/feature_cols.json",
        "data/feature_matrices/local_trade_es2026_p1_candidate/metadata_cols.json",
        "data/feature_matrices/local_trade_es2026_p1_candidate/target_cols.json",
        "reports/features_baseline/local_trade_es2026_p1_candidate/baseline_feature_manifest.json",
        "reports/features_baseline/local_trade_es2026_p1_candidate/baseline_feature_report.json",
        "reports/features_baseline/local_trade_es2026_p1_candidate/feature_audit.json",
        "reports/features_baseline/local_trade_es2026_p1_candidate/feature_correlation_report.csv",
        "reports/features_baseline/local_trade_es2026_p1_candidate/feature_registry.json",
    ]
    ignored_paths = (
        readiness_plan_fixtures._ignored_paths(
            tmp_path,
            repair_reports_root,
            include_readiness_outputs=True,
        )
        + label_expected_artifacts
        + feature_expected_artifacts
    )

    def completed_label_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_label_runner.STAGE,
                "status": downstream_label_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(label_expected_artifacts),
                "ignored_expected_generated_output_count": len(label_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(label_expected_artifacts),
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "post_execution_staged_generated_path_count": 0,
                "failure_count": 2,
            },
            "planned_command": {
                "command_family": "phase3_label_build_exact_es2026_candidate",
                "command": "python -m scripts.phase3_labels.build_labels --markets ES --years 2026",
                "timeout_seconds": 900,
                "expected_generated_artifacts": label_expected_artifacts,
            },
            "checks": [
                {
                    "name": "planned_outputs_absent_before_execution",
                    "status": "FAIL",
                    "observed": label_expected_artifacts,
                    "expected": [],
                    "detail": "The wrapper should not overwrite existing planned label outputs.",
                }
            ],
        }

    def ready_feature_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_feature_runner.STAGE,
                "status": downstream_feature_runner.STATUS_DRY_RUN_READY,
                "expected_generated_output_count": len(feature_expected_artifacts),
                "ignored_expected_generated_output_count": len(feature_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 0,
                "recommended_next_action": status_gate.DOWNSTREAM_FEATURE_APPROVAL_COMMAND,
            },
            "planned_command": {
                "command_family": "phase4_feature_build_exact_es2026_candidate",
                "command": (
                    "python -m scripts.phase4_features.build_baseline_features "
                    "--markets ES --years 2026"
                ),
                "timeout_seconds": 900,
                "expected_generated_artifacts": feature_expected_artifacts,
            },
            "checks": [],
        }

    monkeypatch.setattr(
        status_gate.downstream_label_runner,
        "build_report",
        completed_label_runner_report,
    )
    monkeypatch.setattr(
        status_gate.downstream_feature_runner,
        "build_report",
        ready_feature_runner_report,
    )

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "downstream_feature_build_execution"
    assert report["summary"]["current_gate_status"] == downstream_feature_runner.STATUS_DRY_RUN_READY
    assert report["summary"]["next_action_kind"] == "approve_bounded_downstream_feature_build"
    assert report["summary"]["recommended_next_action"] == status_gate.DOWNSTREAM_FEATURE_APPROVAL_COMMAND
    assert report["current_boundary"]["recommended_command"] == status_gate.DOWNSTREAM_FEATURE_APPROVAL_COMMAND
    assert report["current_boundary"]["approval_token"] == downstream_feature_runner.APPROVAL_TOKEN
    assert report["current_boundary"]["expected_generated_artifacts"] == feature_expected_artifacts
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_family"] == "phase4_feature_build_exact_es2026_candidate"
    assert bounded_plan["command_count"] == 1
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["profile"] == "tier_3_forward"
    assert bounded_plan["maximum_scope"]["network"] is False
    assert bounded_plan["maximum_scope"]["data_mutation"] is True
    assert bounded_plan["expected_generated_artifacts"] == feature_expected_artifacts
    assert "Phase 4 feature build produces only the planned ES 2026" in bounded_plan[
        "stop_condition"
    ]


def test_moves_to_downstream_wfa_split_gate_after_features_are_complete(
    tmp_path: Path, monkeypatch
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        readiness_review_fixtures.runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    readiness_review_fixtures._write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    feature_expected_artifacts = [
        "data/feature_matrices/local_trade_es2026_p1_candidate/ES/2026.parquet",
        "reports/features_baseline/local_trade_es2026_p1_candidate/baseline_feature_manifest.json",
    ]
    ignored_paths = readiness_plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_readiness_outputs=True,
    ) + feature_expected_artifacts

    def completed_label_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_label_runner.STAGE,
                "status": downstream_label_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "ignored_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "failure_count": 2,
            },
            "planned_command": {
                "command_family": "phase3_label_build_exact_es2026_candidate",
                "expected_generated_artifacts": LABEL_EXPECTED_ARTIFACTS,
            },
            "checks": [],
        }

    def completed_feature_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_feature_runner.STAGE,
                "status": downstream_feature_runner.STATUS_NO_GO,
                "failure_count": 2,
            },
            "planned_command": {
                "command_family": "phase4_feature_build_exact_es2026_candidate",
                "expected_generated_artifacts": feature_expected_artifacts,
            },
            "checks": [],
        }

    def no_go_wfa_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_wfa_split_runner.STAGE,
                "status": downstream_wfa_split_runner.STATUS_NO_GO,
                "expected_generated_output_count": 2,
                "ignored_expected_generated_output_count": 2,
                "unignored_expected_generated_output_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 1,
                "recommended_next_action": "Resolve failed ES 2026 downstream WFA split wrapper checks.",
            },
            "approval_gate": {},
            "checks": [],
        }

    monkeypatch.setattr(
        status_gate.downstream_label_runner,
        "build_report",
        completed_label_runner_report,
    )
    monkeypatch.setattr(
        status_gate.downstream_feature_runner,
        "build_report",
        completed_feature_runner_report,
    )
    monkeypatch.setattr(
        status_gate.downstream_wfa_split_runner,
        "build_report",
        no_go_wfa_runner_report,
    )

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_NO_GO
    assert report["summary"]["current_gate"] == "downstream_wfa_split_build_execution"
    assert report["summary"]["current_gate_status"] == downstream_wfa_split_runner.STATUS_NO_GO
    assert report["summary"]["next_action_kind"] == "fix_or_repair_gate"
    assert (
        report["summary"]["recommended_next_action"]
        == "Resolve failed ES 2026 downstream WFA split wrapper checks."
    )
    assert report["current_boundary"]["approval_token"] is None
    assert report["current_boundary"]["recommended_command"] is None


def test_moves_to_downstream_wfa_split_approval_when_gate_is_ready(
    tmp_path: Path, monkeypatch
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        readiness_review_fixtures.runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    readiness_review_fixtures._write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    split_expected_artifacts = [
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.csv",
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.json",
    ]
    ignored_paths = (
        readiness_plan_fixtures._ignored_paths(
            tmp_path,
            repair_reports_root,
            include_readiness_outputs=True,
        )
        + split_expected_artifacts
    )

    def completed_label_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_label_runner.STAGE,
                "status": downstream_label_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "ignored_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "failure_count": 2,
            },
            "planned_command": {
                "command_family": "phase3_label_build_exact_es2026_candidate",
                "expected_generated_artifacts": LABEL_EXPECTED_ARTIFACTS,
            },
            "checks": [],
        }

    def completed_feature_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_feature_runner.STAGE,
                "status": downstream_feature_runner.STATUS_NO_GO,
                "failure_count": 2,
            },
            "checks": [],
        }

    def ready_wfa_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_wfa_split_runner.STAGE,
                "status": downstream_wfa_split_runner.STATUS_DRY_RUN_READY,
                "expected_generated_output_count": len(split_expected_artifacts),
                "ignored_expected_generated_output_count": len(split_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 0,
                "recommended_next_action": "Review and separately approve the bounded ES 2026 Phase 5 WFA split command.",
            },
            "planned_command": {
                "command_family": "phase5_wfa_split_plan_exact_es2026_candidate",
                "command": (
                    "python -m scripts.phase5_wfa.build_wfa_splits "
                    f"--profile {downstream_wfa_split_gate.TARGET_PROFILE} "
                    "--input-root data/feature_matrices/local_trade_es2026_p1_candidate"
                ),
                "timeout_seconds": 900,
                "expected_generated_artifacts": split_expected_artifacts,
            },
            "checks": [],
        }

    monkeypatch.setattr(
        status_gate.downstream_label_runner,
        "build_report",
        completed_label_runner_report,
    )
    monkeypatch.setattr(
        status_gate.downstream_feature_runner,
        "build_report",
        completed_feature_runner_report,
    )
    monkeypatch.setattr(
        status_gate.downstream_wfa_split_runner,
        "build_report",
        ready_wfa_runner_report,
    )

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "downstream_wfa_split_build_execution"
    assert report["summary"]["current_gate_status"] == downstream_wfa_split_runner.STATUS_DRY_RUN_READY
    assert report["summary"]["next_action_kind"] == "approve_bounded_downstream_wfa_split_build"
    assert report["current_boundary"]["recommended_command"] == status_gate.DOWNSTREAM_WFA_SPLIT_APPROVAL_COMMAND
    assert report["current_boundary"]["approval_token"] == downstream_wfa_split_runner.APPROVAL_TOKEN
    assert report["current_boundary"]["expected_generated_artifacts"] == split_expected_artifacts
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_family"] == "phase5_wfa_split_plan_exact_es2026_candidate"
    assert bounded_plan["command_count"] == 1
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["profile"] == downstream_wfa_split_gate.TARGET_PROFILE
    assert bounded_plan["maximum_scope"]["modeling"] is False
    assert bounded_plan["timeout_seconds_per_command"] == 900
    assert bounded_plan["expected_generated_artifacts"] == split_expected_artifacts
    assert "metrics_or_predictions" in bounded_plan["forbidden_patterns"]
    assert "Phase 5 WFA split build produces only the planned ES 2026" in bounded_plan[
        "stop_condition"
    ]


def test_moves_to_downstream_model_approval_after_wfa_split_is_complete(
    tmp_path: Path, monkeypatch
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        readiness_review_fixtures.runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    readiness_review_fixtures._write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    split_expected_artifacts = [
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.csv",
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.json",
    ]
    model_expected_artifacts = [
        "data/predictions/local_trade_es2026_p1_candidate/local_trade_es2026_p1_model_smoke/oos_predictions.parquet",
        "reports/wfa/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_predictions_manifest.json",
        "reports/wfa/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_wfa_report.json",
    ]
    ignored_paths = (
        readiness_plan_fixtures._ignored_paths(
            tmp_path,
            repair_reports_root,
            include_readiness_outputs=True,
        )
        + split_expected_artifacts
        + model_expected_artifacts
    )

    def completed_label_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_label_runner.STAGE,
                "status": downstream_label_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "ignored_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "failure_count": 2,
            },
            "planned_command": {
                "command_family": "phase3_label_build_exact_es2026_candidate",
                "expected_generated_artifacts": LABEL_EXPECTED_ARTIFACTS,
            },
            "checks": [],
        }

    def completed_feature_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_feature_runner.STAGE,
                "status": downstream_feature_runner.STATUS_NO_GO,
                "failure_count": 2,
            },
            "checks": [],
        }

    def completed_wfa_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_wfa_split_runner.STAGE,
                "status": downstream_wfa_split_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(split_expected_artifacts),
                "ignored_expected_generated_output_count": len(split_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(split_expected_artifacts),
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 1,
            },
            "planned_command": {
                "command_family": "phase5_wfa_split_plan_exact_es2026_candidate",
                "expected_generated_artifacts": split_expected_artifacts,
            },
            "checks": [],
        }

    def ready_model_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_model_runner.STAGE,
                "status": downstream_model_runner.STATUS_DRY_RUN_READY,
                "expected_generated_output_count": len(model_expected_artifacts),
                "ignored_expected_generated_output_count": len(model_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 0,
                "recommended_next_action": "Review and separately approve the bounded ES 2026 Phase 6 model smoke command.",
            },
            "planned_command": {
                "command_family": "phase6_wfa_model_smoke_exact_es2026_candidate",
                "command": (
                    "python -m scripts.phase6_wfa.run_wfa --markets ES --max-folds 1 "
                    "--write-predictions"
                ),
                "timeout_seconds": 900,
                "expected_generated_artifacts": model_expected_artifacts,
            },
            "checks": [],
        }

    monkeypatch.setattr(status_gate.downstream_label_runner, "build_report", completed_label_runner_report)
    monkeypatch.setattr(status_gate.downstream_feature_runner, "build_report", completed_feature_runner_report)
    monkeypatch.setattr(status_gate.downstream_wfa_split_runner, "build_report", completed_wfa_runner_report)
    monkeypatch.setattr(status_gate.downstream_model_runner, "build_report", ready_model_runner_report)

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "downstream_model_build_execution"
    assert report["summary"]["current_gate_status"] == downstream_model_runner.STATUS_DRY_RUN_READY
    assert report["summary"]["next_action_kind"] == "approve_bounded_downstream_model_build"
    assert report["current_boundary"]["recommended_command"] == status_gate.DOWNSTREAM_MODEL_APPROVAL_COMMAND
    assert report["current_boundary"]["approval_token"] == downstream_model_runner.APPROVAL_TOKEN
    assert report["current_boundary"]["expected_generated_artifacts"] == model_expected_artifacts
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_family"] == "phase6_wfa_model_smoke_exact_es2026_candidate"
    assert bounded_plan["command_count"] == 1
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["profile"] == status_gate.downstream_model_gate.DEFAULT_PROFILE
    assert bounded_plan["maximum_scope"]["model_training"] is True
    assert bounded_plan["maximum_scope"]["prediction_write"] is True
    assert bounded_plan["maximum_scope"]["model_selection"] is False
    assert bounded_plan["expected_generated_artifacts"] == model_expected_artifacts
    assert "Phase 6 model smoke produces only the planned ES 2026" in bounded_plan[
        "stop_condition"
    ]


def test_moves_to_downstream_metrics_approval_after_model_outputs_are_complete(
    tmp_path: Path, monkeypatch
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        readiness_review_fixtures.runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    readiness_review_fixtures._write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    split_expected_artifacts = [
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.csv",
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.json",
    ]
    model_expected_artifacts = [
        "data/predictions/local_trade_es2026_p1_candidate/local_trade_es2026_p1_model_smoke/oos_predictions.parquet",
        "reports/wfa/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_predictions_manifest.json",
        "reports/wfa/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_wfa_report.json",
    ]
    metrics_expected_artifacts = sorted(
        [
            "reports/metrics/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_metrics.json",
            "reports/metrics/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_metrics.csv",
            "reports/metrics/local_trade_es2026_p1_candidate_model/turnover_diagnostics.csv",
            "reports/model_selection/local_trade_es2026_p1_candidate_model/model_comparison.csv",
            "reports/model_selection/local_trade_es2026_p1_candidate_model/model_selection_report.json",
            "reports/model_selection/local_trade_es2026_p1_candidate_model/calibration_report.json",
            "reports/phase8/local_trade_es2026_p1_candidate_model/metrics.json",
            "reports/phase8/local_trade_es2026_p1_candidate_model/alpha_promotion_decision.json",
        ]
    )
    ignored_paths = (
        readiness_plan_fixtures._ignored_paths(
            tmp_path,
            repair_reports_root,
            include_readiness_outputs=True,
        )
        + split_expected_artifacts
        + model_expected_artifacts
        + metrics_expected_artifacts
    )

    def completed_label_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_label_runner.STAGE,
                "status": downstream_label_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "ignored_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "failure_count": 2,
            },
            "planned_command": {
                "command_family": "phase3_label_build_exact_es2026_candidate",
                "expected_generated_artifacts": LABEL_EXPECTED_ARTIFACTS,
            },
            "checks": [],
        }

    def completed_feature_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_feature_runner.STAGE,
                "status": downstream_feature_runner.STATUS_NO_GO,
                "failure_count": 2,
            },
            "checks": [],
        }

    def completed_wfa_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_wfa_split_runner.STAGE,
                "status": downstream_wfa_split_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(split_expected_artifacts),
                "ignored_expected_generated_output_count": len(split_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(split_expected_artifacts),
                "failure_count": 1,
            },
            "planned_command": {
                "command_family": "phase5_wfa_split_plan_exact_es2026_candidate",
                "expected_generated_artifacts": split_expected_artifacts,
            },
            "checks": [],
        }

    def completed_model_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_model_runner.STAGE,
                "status": downstream_model_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(model_expected_artifacts),
                "ignored_expected_generated_output_count": len(model_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(model_expected_artifacts),
                "failure_count": 1,
            },
            "planned_command": {
                "command_family": "phase6_wfa_model_smoke_exact_es2026_candidate",
                "expected_generated_artifacts": model_expected_artifacts,
            },
            "checks": [],
        }

    def ready_metrics_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_metrics_runner.STAGE,
                "status": downstream_metrics_runner.STATUS_DRY_RUN_READY,
                "expected_generated_output_count": len(metrics_expected_artifacts),
                "ignored_expected_generated_output_count": len(metrics_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 0,
                "recommended_next_action": "Review and separately approve the bounded ES 2026 Phase 8 metrics command.",
            },
            "planned_command": {
                "command_family": "phase8_metrics_model_selection_exact_es2026_candidate",
                "command": "python -m scripts.phase8_model_selection.evaluate_predictions --run local_trade_es2026_p1_model_smoke",
                "timeout_seconds": 900,
                "expected_generated_artifacts": metrics_expected_artifacts,
            },
            "checks": [],
        }

    monkeypatch.setattr(status_gate.downstream_label_runner, "build_report", completed_label_runner_report)
    monkeypatch.setattr(status_gate.downstream_feature_runner, "build_report", completed_feature_runner_report)
    monkeypatch.setattr(status_gate.downstream_wfa_split_runner, "build_report", completed_wfa_runner_report)
    monkeypatch.setattr(status_gate.downstream_model_runner, "build_report", completed_model_runner_report)
    monkeypatch.setattr(status_gate.downstream_metrics_runner, "build_report", ready_metrics_runner_report)

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "downstream_metrics_build_execution"
    assert report["summary"]["current_gate_status"] == downstream_metrics_runner.STATUS_DRY_RUN_READY
    assert report["summary"]["next_action_kind"] == "approve_bounded_downstream_metrics_build"
    assert report["current_boundary"]["recommended_command"] == status_gate.DOWNSTREAM_METRICS_APPROVAL_COMMAND
    assert report["current_boundary"]["approval_token"] == downstream_metrics_runner.APPROVAL_TOKEN
    assert report["current_boundary"]["expected_generated_artifacts"] == metrics_expected_artifacts
    bounded_plan = report["current_boundary"]["bounded_plan"]
    assert bounded_plan["command_family"] == "phase8_metrics_model_selection_exact_es2026_candidate"
    assert bounded_plan["command_count"] == 1
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["profile"] == status_gate.downstream_metrics_gate.DEFAULT_PROFILE
    assert bounded_plan["maximum_scope"]["reports_mutation"] is True
    assert bounded_plan["maximum_scope"]["promotion_or_freeze"] is False
    assert bounded_plan["maximum_scope"]["live_or_paper_execution"] is False
    assert bounded_plan["expected_generated_artifacts"] == metrics_expected_artifacts
    assert "Phase 8 metrics/model-selection produces only the planned ES 2026" in bounded_plan[
        "stop_condition"
    ]


def test_moves_to_downstream_metrics_review_after_metrics_outputs_are_complete(
    tmp_path: Path, monkeypatch
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        readiness_review_fixtures.runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    readiness_review_fixtures._write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    split_expected_artifacts = [
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.csv",
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.json",
    ]
    model_expected_artifacts = [
        "data/predictions/local_trade_es2026_p1_candidate/local_trade_es2026_p1_model_smoke/oos_predictions.parquet",
        "reports/wfa/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_predictions_manifest.json",
        "reports/wfa/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_wfa_report.json",
    ]
    metrics_expected_artifacts = sorted(
        [
            "reports/metrics/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_metrics.json",
            "reports/metrics/local_trade_es2026_p1_candidate_model/local_trade_es2026_p1_model_smoke_metrics.csv",
            "reports/metrics/local_trade_es2026_p1_candidate_model/turnover_diagnostics.csv",
            "reports/model_selection/local_trade_es2026_p1_candidate_model/model_comparison.csv",
            "reports/model_selection/local_trade_es2026_p1_candidate_model/model_selection_report.json",
            "reports/model_selection/local_trade_es2026_p1_candidate_model/calibration_report.json",
            "reports/phase8/local_trade_es2026_p1_candidate_model/metrics.json",
            "reports/phase8/local_trade_es2026_p1_candidate_model/alpha_promotion_decision.json",
        ]
    )
    ignored_paths = (
        readiness_plan_fixtures._ignored_paths(
            tmp_path,
            repair_reports_root,
            include_readiness_outputs=True,
        )
        + split_expected_artifacts
        + model_expected_artifacts
        + metrics_expected_artifacts
    )

    def completed_label_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_label_runner.STAGE,
                "status": downstream_label_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "ignored_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
                "failure_count": 2,
            },
            "planned_command": {
                "command_family": "phase3_label_build_exact_es2026_candidate",
                "expected_generated_artifacts": LABEL_EXPECTED_ARTIFACTS,
            },
            "checks": [],
        }

    def completed_feature_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_feature_runner.STAGE,
                "status": downstream_feature_runner.STATUS_NO_GO,
                "failure_count": 2,
            },
            "checks": [],
        }

    def completed_wfa_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_wfa_split_runner.STAGE,
                "status": downstream_wfa_split_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(split_expected_artifacts),
                "ignored_expected_generated_output_count": len(split_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(split_expected_artifacts),
                "failure_count": 1,
            },
            "planned_command": {
                "command_family": "phase5_wfa_split_plan_exact_es2026_candidate",
                "expected_generated_artifacts": split_expected_artifacts,
            },
            "checks": [],
        }

    def completed_model_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_model_runner.STAGE,
                "status": downstream_model_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(model_expected_artifacts),
                "ignored_expected_generated_output_count": len(model_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(model_expected_artifacts),
                "failure_count": 1,
            },
            "planned_command": {
                "command_family": "phase6_wfa_model_smoke_exact_es2026_candidate",
                "expected_generated_artifacts": model_expected_artifacts,
            },
            "checks": [],
        }

    def completed_metrics_runner_report(**_kwargs):
        return {
            "summary": {
                "stage": downstream_metrics_runner.STAGE,
                "status": downstream_metrics_runner.STATUS_NO_GO,
                "expected_generated_output_count": len(metrics_expected_artifacts),
                "ignored_expected_generated_output_count": len(metrics_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(metrics_expected_artifacts),
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 1,
                "recommended_next_action": "Completed metrics outputs already exist.",
            },
            "planned_command": {
                "command_family": "phase8_metrics_model_selection_exact_es2026_candidate",
                "expected_generated_artifacts": metrics_expected_artifacts,
            },
            "checks": [],
        }

    def ready_metrics_review_report(**_kwargs):
        return {
            "summary": {
                "stage": status_gate.downstream_metrics_review_gate.STAGE,
                "status": status_gate.downstream_metrics_review_gate.STATUS_READY,
                "expected_generated_output_count": len(metrics_expected_artifacts),
                "ignored_expected_generated_output_count": len(metrics_expected_artifacts),
                "unignored_expected_generated_output_count": 0,
                "existing_expected_generated_output_count": len(metrics_expected_artifacts),
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 0,
                "recommended_next_action": (
                    "Review the completed ES 2026 Phase 8 diagnostics; do not promote, "
                    "freeze artifacts, proof-scan, stage, commit, push, or run live/paper "
                    "paths without a separate bounded approval gate."
                ),
            },
            "checks": [],
            "non_approval": {
                "promotion_or_freeze_approved": False,
                "proof_scan_approved": False,
                "generated_output_count": 0,
                "commands_executed": 0,
            },
        }

    monkeypatch.setattr(status_gate.downstream_label_runner, "build_report", completed_label_runner_report)
    monkeypatch.setattr(status_gate.downstream_feature_runner, "build_report", completed_feature_runner_report)
    monkeypatch.setattr(status_gate.downstream_wfa_split_runner, "build_report", completed_wfa_runner_report)
    monkeypatch.setattr(status_gate.downstream_model_runner, "build_report", completed_model_runner_report)
    monkeypatch.setattr(status_gate.downstream_metrics_runner, "build_report", completed_metrics_runner_report)
    monkeypatch.setattr(
        status_gate.downstream_metrics_review_gate,
        "build_report",
        ready_metrics_review_report,
    )

    report = status_gate.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == status_gate.STATUS_ACTION_REQUIRED
    assert report["summary"]["current_gate"] == "downstream_metrics_review"
    assert (
        report["summary"]["current_gate_status"]
        == "REVIEW_READY_ES2026_P1_DOWNSTREAM_METRICS_REVIEW"
    )
    assert (
        report["summary"]["next_action_kind"]
        == "review_downstream_metrics_before_separate_promotion_or_proof_decision"
    )
    assert report["summary"]["approval_token"] is None
    assert report["summary"]["execution_approval_required"] is False
    assert report["current_boundary"]["execution_approval_required"] is False
    assert report["current_boundary"]["recommended_command"] is None
    assert report["current_boundary"]["expected_generated_artifacts"] == []
    assert report["current_boundary"]["bounded_plan"] == {}
    assert report["current_boundary"]["non_approval"]["promotion_or_freeze_approved"] is False
    assert report["current_boundary"]["non_approval"]["proof_scan_approved"] is False
    packet = status_gate.boundary_approval_packet(report)
    assert packet["execution_approval_required"] is False
    assert packet["non_approval"]["promotion_or_freeze_approved"] is False
    assert packet["non_approval"]["proof_scan_approved"] is False
    assert "do not promote" in report["summary"]["recommended_next_action"]
    assert "proof-scan" in report["summary"]["recommended_next_action"]


def test_cli_status_writes_no_reports(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = runner_fixtures._setup(tmp_path)
    (tmp_path / ".gitignore").write_text("reports/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = status_gate.main(
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
            str(repair_reports_root),
            "--candidate-raw-root",
            str(tmp_path / "data" / "raw_es2026_candidate"),
            "--output-root",
            str(tmp_path / "data" / "causal_es2026_candidate"),
            "--raw-alignment-report",
            str(repair_reports_root / "alignment.json"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{status_gate.STAGE} status={status_gate.STATUS_ACTION_REQUIRED}" in output
    assert "current_gate=dry_run_diagnostics_execution" in output
    assert "ignored_expected_generated_outputs=2" in output
    assert "unignored_expected_generated_outputs=0" in output
    assert "generated_outputs=0" in output
    assert not repair_reports_root.exists()


def test_cli_boundary_json_prints_approval_packet_without_reports(
    tmp_path: Path, capsys
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = runner_fixtures._setup(tmp_path)
    (tmp_path / ".gitignore").write_text("reports/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = status_gate.main(
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
            str(repair_reports_root),
            "--candidate-raw-root",
            str(tmp_path / "data" / "raw_es2026_candidate"),
            "--output-root",
            str(tmp_path / "data" / "causal_es2026_candidate"),
            "--raw-alignment-report",
            str(repair_reports_root / "alignment.json"),
            "--print-boundary-json",
        ]
    )

    output_lines = capsys.readouterr().out.splitlines()
    packet = json.loads(output_lines[-1])
    bounded_plan = packet["bounded_plan"]

    assert exit_code == 0
    assert output_lines[0].startswith(f"{status_gate.STAGE} status={status_gate.STATUS_ACTION_REQUIRED}")
    assert packet["recommended_command"] == status_gate.DRY_RUN_APPROVAL_COMMAND
    assert packet["approval_token"] == dry_runner.APPROVAL_TOKEN
    assert packet["execution_approval_required"] is True
    assert packet["current_gate"] == "dry_run_diagnostics_execution"
    assert packet["non_approval"]["model_selection_approved"] is False
    assert packet["non_approval"]["model_promotion_approved"] is False
    assert packet["non_approval"]["promotion_or_freeze_approved"] is False
    assert packet["non_approval"]["wfa_model_training_approved"] is False
    assert bounded_plan["command_family"] == "phase1a_download_dry_run_only"
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["timeout_seconds_per_command"] == 180
    assert len(packet["expected_generated_artifacts"]) == 2
    assert packet["generated_artifact_hygiene"]["ignored_expected_generated_output_count"] == 2
    assert "provider_download_without_separate_approval" in bounded_plan["forbidden_patterns"]
    assert "ignored and unstaged" in bounded_plan["stop_condition"]
    assert not repair_reports_root.exists()


def test_cli_boundary_json_prints_optional_archive_packet_after_dry_run_plans(
    tmp_path: Path, capsys
) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = runner_fixtures._setup(tmp_path)
    (tmp_path / ".gitignore").write_text("data/\nreports/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    availability_fixtures._write_plans(tmp_path)

    exit_code = status_gate.main(
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
            str(repair_reports_root),
            "--candidate-raw-root",
            str(tmp_path / "data" / "raw_es2026_candidate"),
            "--output-root",
            str(tmp_path / "data" / "causal_es2026_candidate"),
            "--raw-alignment-report",
            str(repair_reports_root / "alignment.json"),
            "--print-boundary-json",
        ]
    )

    output_lines = capsys.readouterr().out.splitlines()
    packet = json.loads(output_lines[-1])
    bounded_plan = packet["bounded_plan"]

    assert exit_code == 0
    assert output_lines[0].startswith(f"{status_gate.STAGE} status={status_gate.STATUS_ACTION_REQUIRED}")
    assert packet["recommended_command"] is None
    assert packet["approval_token"] is None
    assert packet["current_gate"] == "optional_archive_availability"
    assert packet["next_action_kind"] == "approve_optional_archive_acquisition_or_cost_diagnostic"
    assert bounded_plan["command_family"] == "optional_archive_acquisition_or_provider_cost_diagnostic"
    assert bounded_plan["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert bounded_plan["maximum_scope"]["schemas"] == ["statistics", "status"]
    assert bounded_plan["maximum_scope"]["network"] == "separate_approval_required"
    assert bounded_plan["maximum_scope"]["data_mutation"] == "separate_approval_required"
    assert len(packet["expected_generated_artifacts"]) == 4
    assert packet["generated_artifact_hygiene"]["ignored_expected_generated_output_count"] == 4
    assert packet["generated_artifact_hygiene"]["unignored_expected_generated_output_count"] == 0
    assert packet["generated_artifact_hygiene"]["generated_output_count"] == 0
    assert packet["generated_artifact_hygiene"]["staged_generated_path_count"] == 0
    assert "separate approval" in bounded_plan["stop_condition"]
    assert not (tmp_path / "data" / "dbn").exists()
