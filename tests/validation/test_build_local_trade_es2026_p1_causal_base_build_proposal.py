from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_causal_base_build_proposal as proposal
from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_review as readiness_review
from scripts.validation import build_local_trade_es2026_p1_workflow_status as workflow_status


def _workflow_report(status: str = workflow_status.STATUS_REVIEW_READY) -> dict[str, object]:
    return {
        "summary": {
            "status": status,
            "current_gate": "candidate_readiness_review",
            "current_gate_status": readiness_review.STATUS_READY,
            "next_action_kind": "separate_causal_base_repair_proposal_decision",
        }
    }


def _readiness_report(status: str = readiness_review.STATUS_READY) -> dict[str, object]:
    return {
        "summary": {
            "status": status,
            "expected_readiness_output_count": 8,
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
        },
        "review_detail": {
            "raw_alignment_status": "PASS",
            "readiness_status": "PASS",
            "readiness_selected_market_year_count": 1,
        },
    }


def _profile_exception(status: str = "PASS") -> dict[str, object]:
    if status != "PASS":
        return {
            "status": "FAIL",
            "matching_exception_count": 0,
            "warning_prefixes": [],
        }
    return {
        "status": "PASS",
        "exception_count": 1,
        "matching_exception_count": 1,
        "market": "ES",
        "year": 2026,
        "category": proposal.EXPECTED_EXCEPTION_CATEGORY,
        "warning_prefixes": [proposal.EXPECTED_WARNING_PREFIX],
        "evidence_paths": [
            "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/readiness_warning_evidence/ES_2026_readiness_warning_evidence.json",
            "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/readiness_warning_evidence/ES_2026_readiness_warning_evidence.md",
        ],
    }


def _paths(tmp_path: Path) -> dict[str, Path]:
    repair_reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    build_reports_root = (
        tmp_path / "reports" / "pipeline_audit" / "local_trade_es2026_p1_causal_base_build_v1"
    )
    return {
        "work_order_report": repair_reports_root / "work_order.json",
        "drilldown_report": repair_reports_root / "drilldown.json",
        "checkpoint_jsonl": repair_reports_root / "phase2_readiness.progress.jsonl",
        "repair_reports_root": repair_reports_root,
        "candidate_raw_root": tmp_path / "data" / "raw_es2026_candidate",
        "output_root": tmp_path / "data" / "causal_es2026_candidate",
        "raw_alignment_report": repair_reports_root
        / "candidate_raw_alignment"
        / "ES_2026_candidate_raw_dbn_alignment.json",
        "build_reports_root": build_reports_root,
        "profile_config": tmp_path / "configs" / "alpha_tiered.yaml",
        "session_config": tmp_path / "configs" / "market_sessions.yaml",
    }


def _ignored_build_paths(tmp_path: Path, paths: dict[str, Path]) -> list[str]:
    return [
        proposal.rel(tmp_path / artifact, tmp_path)
        for artifact in proposal._expected_build_artifacts(
            output_root=paths["output_root"],
            build_reports_root=paths["build_reports_root"],
            include_local_trade_gap_reports=False,
        )
    ]


def _build(
    tmp_path: Path,
    *,
    workflow: dict[str, object] | None = None,
    readiness: dict[str, object] | None = None,
    profile_exception: dict[str, object] | None = None,
    ignored_paths: list[str] | None = None,
    staged: list[str] | None = None,
) -> dict[str, object]:
    paths = _paths(tmp_path)
    return proposal.build_report(
        repo_root=tmp_path,
        **paths,
        workflow_status_report=workflow if workflow is not None else _workflow_report(),
        candidate_readiness_review_report=readiness if readiness is not None else _readiness_report(),
        profile_exception_evidence=(
            profile_exception if profile_exception is not None else _profile_exception()
        ),
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths if ignored_paths is not None else _ignored_build_paths(tmp_path, paths),
    )


def test_ready_proposal_defines_exact_bounded_build_packet(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == proposal.STATUS_READY
    assert report["summary"]["expected_generated_output_count"] == 6
    assert report["summary"]["ignored_expected_generated_output_count"] == 6
    assert report["summary"]["unignored_expected_generated_output_count"] == 0
    assert report["summary"]["existing_expected_generated_output_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["causal_base_repair_approved"] is False
    assert report["summary"]["local_trade_gap_gate_postcondition_status"] == "SKIPPED"
    assert report["summary"]["source_requires_local_trade_gap_gate"] is False
    packet = report["proposal"]
    assert packet["proposal_status"] == "READY_FOR_REVIEW_NOT_EXECUTED"
    assert packet["timeout_seconds"] == proposal.COMMAND_TIMEOUT_SECONDS
    assert packet["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert packet["maximum_scope"]["profile"] == "tier_3_forward"
    assert packet["pre_run_artifacts"] == [
        {
            "path": "reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1/include_ES_2026.json",
            "content": {"market_years": [{"market": "ES", "year": 2026}]},
        }
    ]
    command = packet["exact_command"]
    assert command.startswith("python -m scripts.phase2_causal_base.build_causal_base_data")
    assert "--profile tier_3_forward" in command
    assert "--build-max-market-years 1" in command
    assert "--build-progress-checkpoint-jsonl" in command
    assert "--readiness-only" not in command
    assert "--accepted-readiness-exceptions" not in command
    assert "labels_or_features" in packet["forbidden_actions_without_separate_approval"]
    assert "proof_scan" in packet["forbidden_actions_without_separate_approval"]
    assert packet["local_trade_gap_gate_postcondition"]["expected_status"] == "SKIPPED"
    assert packet["local_trade_gap_gate_postcondition"]["expected_reason"] == "profile_not_required"
    assert packet["local_trade_gap_gate_postcondition"]["expected_report_count"] == 0
    assert (
        packet["local_trade_gap_gate_postcondition"]["expected_vendor_backed_status"]
        == proposal.EXPECTED_VENDOR_BACKED_STATUS
    )
    validation_names = {item["name"] for item in packet["validation_checks"]}
    assert {"manifest_exact_scope_pass", "validation_exact_scope_pass", "generated_artifacts_unstaged"} <= validation_names
    validation_check = next(
        item for item in packet["validation_checks"] if item["name"] == "validation_exact_scope_pass"
    )
    assert validation_check["expected"]["local_trade_ohlcv_gap_gate.status"] == "SKIPPED"
    assert validation_check["expected"]["local_trade_ohlcv_gap_gate.reason"] == "profile_not_required"
    assert (
        validation_check["expected"]["files[0].vendor_trusted_ohlcv_no_trade_status"]
        == proposal.EXPECTED_VENDOR_BACKED_STATUS
    )
    assert any("Do not execute until" in item for item in packet["stop_conditions"])
    assert any("SKIPPED/profile_not_required" in item for item in packet["stop_conditions"])


def test_unignored_expected_artifacts_fail_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ignored = _ignored_build_paths(tmp_path, paths)[:-1]

    report = _build(tmp_path, ignored_paths=ignored)

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert report["summary"]["unignored_expected_generated_output_count"] == 1
    assert report["proposal"] == {}
    assert any(
        check["name"] == "expected_build_artifacts_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_existing_expected_artifact_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    existing_output = paths["output_root"] / "ES" / "2026.parquet"
    existing_output.parent.mkdir(parents=True)
    existing_output.write_bytes(b"existing")

    report = _build(tmp_path)

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert report["summary"]["existing_expected_generated_output_count"] == 1
    assert "data/causal_es2026_candidate/ES/2026.parquet" in report[
        "existing_expected_generated_artifacts"
    ]
    assert any(
        check["name"] == "expected_build_artifacts_absent_before_execution"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_profile_exception_mismatch_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, profile_exception=_profile_exception(status="FAIL"))

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert any(
        check["name"] == "profile_exception_exact_es2026"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_workflow_not_review_ready_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, workflow=_workflow_report(status=workflow_status.STATUS_NO_GO))

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert any(
        check["name"] == "workflow_status_review_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_forbidden_build_argument_fails_closed(tmp_path: Path, monkeypatch) -> None:
    original = proposal._build_command

    def bad_command(**kwargs):
        return original(**kwargs) + " --readiness-only"

    monkeypatch.setattr(proposal, "_build_command", bad_command)

    report = _build(tmp_path)

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert any(
        check["name"] == "build_command_exact_and_bounded"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_no_go_writes_no_reports_when_preconditions_missing(tmp_path: Path, capsys) -> None:
    build_reports_root = (
        tmp_path / "reports" / "pipeline_audit" / "local_trade_es2026_p1_causal_base_build_v1"
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = proposal.main(
        [
            "--repo-root",
            str(tmp_path),
            "--work-order-report",
            str(tmp_path / "missing_work_order.json"),
            "--drilldown-report",
            str(tmp_path / "missing_drilldown.json"),
            "--checkpoint-jsonl",
            str(tmp_path / "missing.progress.jsonl"),
            "--repair-reports-root",
            str(tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"),
            "--candidate-raw-root",
            str(tmp_path / "data" / "raw_es2026_candidate"),
            "--output-root",
            str(tmp_path / "data" / "causal_es2026_candidate"),
            "--raw-alignment-report",
            str(tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1" / "alignment.json"),
            "--build-reports-root",
            str(build_reports_root),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{proposal.STAGE} status={proposal.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
    assert "commands_executed=0" in output
    assert not build_reports_root.exists()
