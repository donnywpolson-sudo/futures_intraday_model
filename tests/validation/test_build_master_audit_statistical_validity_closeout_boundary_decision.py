from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_statistical_validity_closeout_boundary_decision as builder,
)


TEST_INPUTS = {
    "acceptance_boundary": Path("in/acceptance_boundary.json"),
    "post_recompute_reconciliation": Path("in/post_recompute.json"),
    "regime_adversarial_disposition": Path("in/regime_adversarial.json"),
    "alpha_matrix": Path("in/alpha_matrix.json"),
    "alpha_closeout": Path("in/alpha_closeout.json"),
    "run_status": Path("in/run_status.json"),
    "adversarial_audit": Path("in/adversarial_audit.md"),
}


def _write_json(root: Path, rel_path: Path, payload: dict) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(root: Path, rel_path: Path, text: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _acceptance_boundary() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_ACCEPTANCE_BOUNDARY_DECISION_REPORT_ONLY",
        "summary": {
            "acceptance_boundary_decision": builder.ACCEPTANCE_BOUNDARY_DECISION,
            "remaining_statistical_validity_blockers_actionable_for_current_line": False,
            "new_generated_null_regime_or_variant_evidence_required_for_any_future_reconsideration": True,
            "statistical_validity_ready": False,
            "master_audit_statistical_validity_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _post_recompute() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_POST_RECOMPUTE_STATISTICAL_VALIDITY_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "pbo_status": "FAIL_NO_VARIANT_PERFORMANCE_MATRIX",
            "deflated_sharpe_status": "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION",
            "multiple_testing_status": "FAIL_BONFERRONI_ADJUSTED_PSR",
            "probabilistic_sharpe_status": "FAIL",
            "regime_breakdowns_status": "FAIL",
            "statistical_validity_ready": False,
            "master_audit_statistical_validity_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _regime_adversarial() -> dict:
    return {
        "status": (
            "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_REGIME_ADVERSARIAL_"
            "DISPOSITION_REPORT_ONLY"
        ),
        "summary": {
            "random_entry_null_disposition": (
                "TERMINAL_FAIL_CANDIDATE_DOES_NOT_BEAT_RANDOM_MEDIAN"
            ),
            "two_x_cost_stress_disposition": "TERMINAL_FAIL_EDGE_DOES_NOT_SURVIVE_2X_COST",
            "label_shuffle_disposition": (
                "MISSING_REQUIRED_EVIDENCE_SEPARATE_BOUNDED_SHUFFLE_HARNESS_REQUIRED"
            ),
            "timing_shift_disposition": (
                "MISSING_REQUIRED_EVIDENCE_SEPARATE_BOUNDED_TIMING_SHIFT_HARNESS_REQUIRED"
            ),
            "regime_breakdowns_disposition": (
                "FAIL_MISSING_EXPLICIT_CAUSAL_REGIME_EVIDENCE_NOT_ACTIONABLE_FOR_CURRENT_LINE"
            ),
            "statistical_validity_ready": False,
            "master_audit_statistical_validity_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _alpha_matrix() -> dict:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "alpha_evidence_ready": False,
        "verdict": "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
    }


def _alpha_closeout() -> dict:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
        "future_modeling_allowed": False,
        "promotion_allowed": False,
    }


def _run_status() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "data_model_commands_executed": False,
            "wfa_modeling_executed": False,
            "predictions_executed": False,
            "provider_network_calls_executed": False,
            "promotion_or_freeze_or_holdout_executed": False,
            "paper_or_live_executed": False,
            "cleanup_or_git_publication_executed": False,
        },
    }


def _base_repo(tmp_path: Path) -> Path:
    _write_json(tmp_path, TEST_INPUTS["acceptance_boundary"], _acceptance_boundary())
    _write_json(tmp_path, TEST_INPUTS["post_recompute_reconciliation"], _post_recompute())
    _write_json(tmp_path, TEST_INPUTS["regime_adversarial_disposition"], _regime_adversarial())
    _write_json(tmp_path, TEST_INPUTS["alpha_matrix"], _alpha_matrix())
    _write_json(tmp_path, TEST_INPUTS["alpha_closeout"], _alpha_closeout())
    _write_json(tmp_path, TEST_INPUTS["run_status"], _run_status())
    _write_text(tmp_path, TEST_INPUTS["adversarial_audit"], "Fail / Blocked.\n")
    return tmp_path


def _build(tmp_path: Path) -> dict:
    repo_root = _base_repo(tmp_path)
    return builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )


def test_closeout_boundary_passes_current_blocked_state(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == builder.PASS_STATUS
    summary = report["summary"]
    assert summary["closeout_boundary_decision"] == builder.CLOSEOUT_BOUNDARY_DECISION
    assert summary["statistical_validity"] == "FAIL"
    assert summary["current_line_statistical_validity_gap_permanently_blocked_from_existing_evidence"]
    assert summary["gap_map_refresh_allowed"] is False
    assert summary["statistical_validity_gap_upgrade_allowed"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["master_audit_statistical_validity_accepted"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False


def test_missing_acceptance_boundary_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    (repo_root / TEST_INPUTS["acceptance_boundary"]).unlink()

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["statistical_validity_ready"] is False


def test_changed_acceptance_boundary_decision_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _acceptance_boundary()
    payload["summary"]["acceptance_boundary_decision"] = "READY"
    _write_json(repo_root, TEST_INPUTS["acceptance_boundary"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["statistical_validity_gap_upgrade_allowed"] is False


def test_upstream_statistical_blocker_upgrade_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _post_recompute()
    payload["summary"]["pbo_status"] = "PASS"
    _write_json(repo_root, TEST_INPUTS["post_recompute_reconciliation"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["statistical_validity_ready"] is False


def test_alpha_closeout_reopened_or_promotion_true_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _alpha_closeout()
    payload["verdict"] = "REOPEN"
    payload["promotion_allowed"] = True
    _write_json(repo_root, TEST_INPUTS["alpha_closeout"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["promotion_allowed"] is False


def test_non_approval_flag_true_fails_closed(tmp_path: Path) -> None:
    report = builder.build_report(
        repo_root=_base_repo(tmp_path),
        reports_root=tmp_path / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
        non_approval_overrides={"gap_map_refresh_executed": True},
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["gap_map_refresh_allowed"] is False


def test_writes_exact_report_pair_under_master_audit(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    reports_root = repo_root / builder.DEFAULT_REPORTS_ROOT
    report = builder.build_report(
        repo_root=repo_root,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    json_path, md_path = builder.write_report(report, reports_root)

    assert json_path.name == builder.REPORT_JSON
    assert md_path.name == builder.REPORT_MD
    assert sorted(path.name for path in reports_root.iterdir()) == [
        builder.REPORT_JSON,
        builder.REPORT_MD,
    ]
    assert "reports/master_audit" in reports_root.as_posix()
