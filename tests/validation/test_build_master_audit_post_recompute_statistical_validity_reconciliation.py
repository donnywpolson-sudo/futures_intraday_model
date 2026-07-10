from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_post_recompute_statistical_validity_reconciliation as builder,
)

TEST_INPUTS = {
    "recompute_summary": Path("in/recompute/statistical_validity_summary.json"),
    "recompute_bootstrap": Path("in/recompute/bootstrap_confidence_intervals.csv"),
    "recompute_stability": Path("in/recompute/stability_matrix.csv"),
    "recompute_adversarial": Path("in/recompute/adversarial_tests.csv"),
    "recompute_markdown": Path("in/recompute/statistical_validity.md"),
    "recompute_decision": Path("in/recompute_decision.json"),
    "post_mutation_completeness": Path("in/post_mutation_completeness.json"),
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


def _write_csv(root: Path, rel_path: Path, text: str) -> None:
    _write_text(root, rel_path, text)


def _summary() -> dict:
    return {
        "status": "FAIL",
        "statistical_validity_ready": False,
        "run": "tier1_core_phase6_full_predictions_20260706",
        "prediction_count": 9_172_416,
        "policy_trade_count": 1_347,
        "failure_count": 5,
        "model_promotion_allowed": False,
        "trial_search_evidence": {
            "trial_count": 22,
            "search_family_count": 10,
            "multiple_testing_family_count": 2,
            "source_status": (
                "PASS_MASTER_AUDIT_POST_MUTATION_TRIAL_SEARCH_COMPLETENESS_"
                "RECONCILIATION_REPORT_ONLY"
            ),
            "trial_search_ledger_path": (
                "reports/master_audit/master_audit_post_mutation_trial_search_"
                "completeness_reconciliation_20260710/master_audit_post_mutation_"
                "trial_search_completeness_reconciliation.json"
            ),
            "trial_ledger_search_path_complete": True,
        },
        "required_checks": {
            "pbo": {
                "status": "FAIL_NO_VARIANT_PERFORMANCE_MATRIX",
                "trial_count": 22,
                "search_family_count": 10,
                "multiple_testing_family_count": 2,
            },
            "deflated_sharpe": {
                "status": "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION",
                "trial_count": 22,
                "observed_sharpe_like": -4.56884658431966,
                "search_family_count": 10,
            },
            "multiple_testing_adjustment": {
                "status": "FAIL_BONFERRONI_ADJUSTED_PSR",
                "trial_count": 22,
                "search_family_count": 10,
                "multiple_testing_family_count": 2,
                "raw_p_value": 1.0,
                "bonferroni_adjusted_p_value": 1.0,
            },
            "probabilistic_sharpe": {
                "status": "FAIL",
                "probabilistic_sharpe": 0.0,
                "observation_count": 1_347,
                "sharpe_like": -4.56884658431966,
                "z_score": -18.2206357418968,
            },
            "bootstrap_confidence_intervals": {
                "status": "PASS",
                "sample_count": 500,
            },
            "parameter_stability": {"status": "PASS"},
            "regime_breakdowns": {"status": "FAIL"},
        },
    }


def _recompute_decision() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_RECOMPUTE_DECISION_REPORT_ONLY",
        "summary": {
            "pbo_recompute_decision": "READY_FOR_SEPARATE_BOUNDED_STATISTICAL_RECOMPUTE",
            "deflated_sharpe_recompute_decision": (
                "READY_FOR_SEPARATE_BOUNDED_STATISTICAL_RECOMPUTE"
            ),
            "multiple_testing_recompute_decision": (
                "READY_FOR_SEPARATE_BOUNDED_STATISTICAL_RECOMPUTE"
            ),
            "trial_count_for_recompute": 22,
            "search_family_count": 10,
            "multiple_testing_family_count": 2,
            "statistical_validity_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _post_mutation() -> dict:
    return {
        "status": (
            "PASS_MASTER_AUDIT_POST_MUTATION_TRIAL_SEARCH_COMPLETENESS_"
            "RECONCILIATION_REPORT_ONLY"
        ),
        "summary": {
            "trial_ledger_search_path_complete": True,
            "trial_count": 22,
            "family_metadata_row_count": 22,
            "search_family_count": 10,
            "multiple_testing_family_count": 2,
            "statistical_validity_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
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
        "modeling_pause_required": True,
        "future_modeling_allowed": False,
        "future_evidence_work_allowed": True,
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
    _write_json(tmp_path, TEST_INPUTS["recompute_summary"], _summary())
    _write_csv(
        tmp_path,
        TEST_INPUTS["recompute_bootstrap"],
        "metric,sample_count,lower_ci,median,upper_ci\n"
        "net_return_dollars,500,-80067.74562500016,-55426.87750000031,-29269.266750000264\n",
    )
    _write_csv(
        tmp_path,
        TEST_INPUTS["recompute_stability"],
        "scope,market,year,fold,metric,value,status\nfold,ES,2023,0,net_return_dollars,-10.0,FAIL\n",
    )
    _write_csv(
        tmp_path,
        TEST_INPUTS["recompute_adversarial"],
        "test_id,status,value\n"
        "top_1pct_trade_removal,PASS,-68218.73500000016\n"
        "two_x_cost_stress,FAIL,-92118.55500000017\n"
        "random_entry_distribution,MISSING_WITH_REASON,\n"
        "label_shuffle,MISSING_WITH_REASON,\n",
    )
    _write_text(tmp_path, TEST_INPUTS["recompute_markdown"], "# Statistical validity\n")
    _write_json(tmp_path, TEST_INPUTS["recompute_decision"], _recompute_decision())
    _write_json(tmp_path, TEST_INPUTS["post_mutation_completeness"], _post_mutation())
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


def test_post_recompute_reconciliation_passes_current_blocked_state(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == builder.PASS_STATUS
    summary = report["summary"]
    assert summary["missing_trial_log_blockers_replaced"] is True
    assert summary["pbo_status"] == "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"
    assert summary["deflated_sharpe_status"] == "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
    assert summary["multiple_testing_status"] == "FAIL_BONFERRONI_ADJUSTED_PSR"
    assert summary["trial_count"] == 22
    assert summary["search_family_count"] == 10
    assert summary["multiple_testing_family_count"] == 2
    assert summary["statistical_validity_ready"] is False
    assert summary["master_audit_statistical_validity_accepted"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False


def test_missing_bootstrap_csv_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    (repo_root / TEST_INPUTS["recompute_bootstrap"]).unlink()

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["missing_trial_log_blockers_replaced"] is False
    assert any(item["name"] == "bootstrap_csv_preserved" and item["status"] == "FAIL" for item in report["checks"])


def test_missing_trial_log_status_is_not_accepted_after_recompute(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _summary()
    payload["required_checks"]["pbo"]["status"] = "FAIL_MISSING_TRIAL_LOG"
    _write_json(repo_root, TEST_INPUTS["recompute_summary"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["pbo_status"] == "FAIL_MISSING_TRIAL_LOG"


def test_full_statistical_upgrade_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _summary()
    payload["status"] = "PASS"
    payload["statistical_validity_ready"] = True
    payload["required_checks"]["pbo"]["status"] = "PASS"
    _write_json(repo_root, TEST_INPUTS["recompute_summary"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["statistical_validity_ready"] is False
    assert report["summary"]["promotion_allowed"] is False


def test_count_drift_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _summary()
    payload["policy_trade_count"] = 1_348
    _write_json(repo_root, TEST_INPUTS["recompute_summary"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_upstream_recompute_decision_must_be_pass_and_blocked(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    decision = _recompute_decision()
    decision["status"] = "FAIL"
    decision["summary"]["promotion_allowed"] = True
    _write_json(repo_root, TEST_INPUTS["recompute_decision"], decision)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["promotion_allowed"] is False


def test_post_mutation_completeness_count_drift_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    post_mutation = _post_mutation()
    post_mutation["summary"]["search_family_count"] = 9
    _write_json(repo_root, TEST_INPUTS["post_mutation_completeness"], post_mutation)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_alpha_closeout_promotion_upgrade_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    closeout = _alpha_closeout()
    closeout["promotion_allowed"] = True
    _write_json(repo_root, TEST_INPUTS["alpha_closeout"], closeout)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["model_trust_ready"] is False


def test_write_report_outputs_exact_pair_under_master_audit(tmp_path: Path) -> None:
    report = _build(tmp_path)
    reports_root = tmp_path / builder.DEFAULT_REPORTS_ROOT
    json_path, md_path = builder.write_report(report, reports_root)

    assert sorted(path.name for path in reports_root.iterdir()) == [
        builder.REPORT_JSON,
        builder.REPORT_MD,
    ]
    assert "reports/master_audit/" in json_path.as_posix()
    assert "reports/master_audit/" in md_path.as_posix()
