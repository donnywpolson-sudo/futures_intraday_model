from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_statistical_validity_acceptance_boundary_decision as builder,
)


TEST_INPUTS = {
    "regime_adversarial_disposition": Path("in/regime_adversarial_disposition.json"),
    "post_recompute_reconciliation": Path("in/post_recompute.json"),
    "recompute_summary": Path("in/recompute/statistical_validity_summary.json"),
    "recompute_bootstrap": Path("in/recompute/bootstrap_confidence_intervals.csv"),
    "recompute_stability": Path("in/recompute/stability_matrix.csv"),
    "recompute_adversarial": Path("in/recompute/adversarial_tests.csv"),
    "recompute_markdown": Path("in/recompute/statistical_validity.md"),
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


def _regime_disposition() -> dict:
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
            "probabilistic_sharpe_status": "FAIL",
            "regime_breakdowns_status": "FAIL",
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
            "missing_trial_log_blockers_replaced": True,
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


def _recompute_summary() -> dict:
    return {
        "status": "FAIL",
        "statistical_validity_ready": False,
        "prediction_count": 9_172_416,
        "policy_trade_count": 1_347,
        "failure_count": 5,
        "model_promotion_allowed": False,
        "required_checks": {
            "pbo": {"status": "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"},
            "deflated_sharpe": {
                "status": "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
            },
            "multiple_testing_adjustment": {"status": "FAIL_BONFERRONI_ADJUSTED_PSR"},
            "probabilistic_sharpe": {
                "status": "FAIL",
                "probabilistic_sharpe": 0.0,
                "observation_count": 1_347,
                "sharpe_like": -4.56884658431966,
                "z_score": -18.2206357418968,
            },
            "bootstrap_confidence_intervals": {"status": "PASS", "sample_count": 500},
            "parameter_stability": {"status": "PASS"},
            "regime_breakdowns": {"status": "FAIL"},
        },
    }


def _alpha_matrix() -> dict:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "alpha_evidence_ready": False,
        "model_trust_ready": False,
        "promotion_allowed": False,
    }


def _alpha_closeout() -> dict:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
        "future_modeling_allowed": False,
        "promotion_allowed": False,
        "terminal_fail_count": 5,
        "missing_required_evidence_count": 11,
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
    _write_json(tmp_path, TEST_INPUTS["regime_adversarial_disposition"], _regime_disposition())
    _write_json(tmp_path, TEST_INPUTS["post_recompute_reconciliation"], _post_recompute())
    _write_json(tmp_path, TEST_INPUTS["recompute_summary"], _recompute_summary())
    _write_text(
        tmp_path,
        TEST_INPUTS["recompute_bootstrap"],
        "metric,sample_count,mean,lower_ci,upper_ci\nnet_return_dollars,500,-1,-2,0\n",
    )
    _write_text(
        tmp_path,
        TEST_INPUTS["recompute_stability"],
        "scope,market,year,fold_id,row_count,trade_count,net_return_dollars\n"
        "fold,ES,2024,fold_001,10,1,-1\n",
    )
    _write_text(
        tmp_path,
        TEST_INPUTS["recompute_adversarial"],
        "test_id,status,net_return_dollars,reason\n"
        "top_1pct_trade_removal,PASS,-68218.73500000016,\n"
        "two_x_cost_stress,FAIL,-92118.55500000017,\n"
        "random_entry_distribution,MISSING_WITH_REASON,,requires bounded null harness\n"
        "label_shuffle,MISSING_WITH_REASON,,requires bounded shuffle harness\n",
    )
    _write_text(tmp_path, TEST_INPUTS["recompute_markdown"], "# Statistical validity\n")
    _write_json(tmp_path, TEST_INPUTS["alpha_matrix"], _alpha_matrix())
    _write_json(tmp_path, TEST_INPUTS["alpha_closeout"], _alpha_closeout())
    _write_json(tmp_path, TEST_INPUTS["run_status"], _run_status())
    _write_text(tmp_path, TEST_INPUTS["adversarial_audit"], "Current line remains blocked.\n")
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


def test_acceptance_boundary_passes_current_terminal_blocked_state(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == builder.PASS_STATUS
    summary = report["summary"]
    assert summary["acceptance_boundary_decision"] == builder.BOUNDARY_DECISION
    assert summary["remaining_statistical_validity_blockers_actionable_for_current_line"] is False
    assert (
        summary["new_generated_null_regime_or_variant_evidence_required_for_any_future_reconsideration"]
        is True
    )
    assert summary["probabilistic_sharpe_status"] == "FAIL"
    assert summary["probabilistic_sharpe"] == 0.0
    assert summary["pbo_status"] == "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"
    assert summary["deflated_sharpe_status"] == "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
    assert summary["multiple_testing_status"] == "FAIL_BONFERRONI_ADJUSTED_PSR"
    assert summary["regime_breakdowns_status"] == "FAIL"
    assert summary["statistical_validity_ready"] is False
    assert summary["master_audit_statistical_validity_accepted"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False


def test_missing_upstream_regime_disposition_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    (repo_root / TEST_INPUTS["regime_adversarial_disposition"]).unlink()

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["statistical_validity_ready"] is False


def test_psr_upgrade_or_changed_values_fail_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _recompute_summary()
    payload["required_checks"]["probabilistic_sharpe"]["status"] = "PASS"
    payload["required_checks"]["probabilistic_sharpe"]["probabilistic_sharpe"] = 1.0
    _write_json(repo_root, TEST_INPUTS["recompute_summary"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["master_audit_statistical_validity_accepted"] is False


def test_required_fail_status_upgrade_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _recompute_summary()
    payload["required_checks"]["multiple_testing_adjustment"]["status"] = "PASS"
    _write_json(repo_root, TEST_INPUTS["recompute_summary"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_adversarial_csv_upgrade_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    _write_text(
        repo_root,
        TEST_INPUTS["recompute_adversarial"],
        "test_id,status,net_return_dollars,reason\n"
        "two_x_cost_stress,PASS,1,\n"
        "random_entry_distribution,PASS,1,\n"
        "label_shuffle,MISSING_WITH_REASON,,requires bounded shuffle harness\n",
    )

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_alpha_closeout_promotion_or_count_drift_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _alpha_closeout()
    payload["promotion_allowed"] = True
    payload["terminal_fail_count"] = 4
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
        non_approval_overrides={"promotion_executed": True},
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["promotion_allowed"] is False


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
