from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_statistical_validity_regime_adversarial_disposition as builder,
)


TEST_INPUTS = {
    "post_recompute_reconciliation": Path("in/post_recompute.json"),
    "recompute_summary": Path("in/recompute/statistical_validity_summary.json"),
    "recompute_adversarial": Path("in/recompute/adversarial_tests.csv"),
    "recompute_stability": Path("in/recompute/stability_matrix.csv"),
    "recompute_markdown": Path("in/recompute/statistical_validity.md"),
    "failure_analysis": Path("in/failure_analysis_summary.json"),
    "phase8_decision": Path("in/alpha_promotion_decision.json"),
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


def _post_recompute() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_POST_RECOMPUTE_STATISTICAL_VALIDITY_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "missing_trial_log_blockers_replaced": True,
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
        "failure_count": 5,
        "required_checks": {
            "pbo": {"status": "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"},
            "deflated_sharpe": {
                "status": "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
            },
            "multiple_testing_adjustment": {"status": "FAIL_BONFERRONI_ADJUSTED_PSR"},
            "probabilistic_sharpe": {"status": "FAIL"},
            "regime_breakdowns": {"status": "FAIL"},
        },
    }


def _failure_analysis() -> dict:
    return {
        "status": "PASS",
        "failure_analysis_ready": True,
        "failure_count": 0,
        "baseline_comparison_gate": {
            "baselines": [
                {
                    "baseline_id": "random_entry",
                    "status": "PASS",
                    "trade_count": 1347.0,
                    "simulation_count": 25.0,
                    "candidate_beats_random_median": False,
                }
            ]
        },
    }


def _phase8_decision() -> dict:
    return {
        "promoted": False,
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "promotion_metric_gate": {
            "cost_execution_stress_gate": {
                "status": "FAIL",
                "required_cost_stress_multiplier": 2.0,
                "stress_results": [
                    {
                        "cost_multiplier": 2.0,
                        "stressed_net_return_dollars": -92118.55500000017,
                        "edge_survives": False,
                        "required_for_promotion": True,
                    }
                ],
            }
        },
    }


def _alpha_closeout() -> dict:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
        "promotion_allowed": False,
        "bucket_dispositions": [
            {
                "bucket_id": "baseline_random_entry_null",
                "source_status": "FAIL",
                "closeout_classification": "terminal_fail",
            },
            {
                "bucket_id": "null_label_shuffle",
                "source_status": "MISSING_EVIDENCE",
                "closeout_classification": "missing_required_evidence",
            },
            {
                "bucket_id": "null_timing_shift",
                "source_status": "MISSING_EVIDENCE",
                "closeout_classification": "missing_required_evidence",
            },
            {
                "bucket_id": "stability_regime_breakdowns",
                "source_status": "FAIL",
                "closeout_classification": "not_actionable_for_current_line",
            },
            {
                "bucket_id": "stability_fold_market_year_session",
                "source_status": "FAIL",
                "closeout_classification": "terminal_fail",
            },
            {
                "bucket_id": "execution_cost_stress",
                "source_status": "FAIL",
                "closeout_classification": "terminal_fail",
            },
        ],
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
    _write_json(tmp_path, TEST_INPUTS["post_recompute_reconciliation"], _post_recompute())
    _write_json(tmp_path, TEST_INPUTS["recompute_summary"], _recompute_summary())
    _write_text(
        tmp_path,
        TEST_INPUTS["recompute_adversarial"],
        "test_id,status,net_return_dollars,reason\n"
        "top_1pct_trade_removal,PASS,-68218.73500000016,\n"
        "two_x_cost_stress,FAIL,-92118.55500000017,\n"
        "random_entry_distribution,MISSING_WITH_REASON,,from Phase 8 failure analysis\n"
        "label_shuffle,MISSING_WITH_REASON,,requires bounded shuffle harness\n",
    )
    _write_text(
        tmp_path,
        TEST_INPUTS["recompute_stability"],
        "scope,market,row_count,trade_count,net_return_dollars,sharpe_like,positive_net,year,fold_id\n"
        "fold,ES,1,1,-1.0,-1.0,False,,ES_research_0001\n",
    )
    _write_text(tmp_path, TEST_INPUTS["recompute_markdown"], "# Statistical validity\n")
    _write_json(tmp_path, TEST_INPUTS["failure_analysis"], _failure_analysis())
    _write_json(tmp_path, TEST_INPUTS["phase8_decision"], _phase8_decision())
    _write_json(
        tmp_path,
        TEST_INPUTS["alpha_matrix"],
        {"status": "PASS_REPORT_WRITTEN", "alpha_evidence_ready": False},
    )
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


def test_regime_adversarial_disposition_passes_current_blocked_state(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == builder.PASS_STATUS
    summary = report["summary"]
    assert (
        summary["random_entry_null_disposition"]
        == "TERMINAL_FAIL_CANDIDATE_DOES_NOT_BEAT_RANDOM_MEDIAN"
    )
    assert summary["two_x_cost_stress_disposition"] == "TERMINAL_FAIL_EDGE_DOES_NOT_SURVIVE_2X_COST"
    assert (
        summary["label_shuffle_disposition"]
        == "MISSING_REQUIRED_EVIDENCE_SEPARATE_BOUNDED_SHUFFLE_HARNESS_REQUIRED"
    )
    assert (
        summary["timing_shift_disposition"]
        == "MISSING_REQUIRED_EVIDENCE_SEPARATE_BOUNDED_TIMING_SHIFT_HARNESS_REQUIRED"
    )
    assert summary["regime_breakdowns_status"] == "FAIL"
    assert summary["statistical_validity_ready"] is False
    assert summary["master_audit_statistical_validity_accepted"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False


def test_missing_upstream_reconciliation_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    (repo_root / TEST_INPUTS["post_recompute_reconciliation"]).unlink()

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_recompute_upgrade_to_pass_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _recompute_summary()
    payload["status"] = "PASS"
    payload["statistical_validity_ready"] = True
    payload["required_checks"]["probabilistic_sharpe"]["status"] = "PASS"
    _write_json(repo_root, TEST_INPUTS["recompute_summary"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["statistical_validity_ready"] is False


def test_adversarial_csv_missing_label_shuffle_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    _write_text(
        repo_root,
        TEST_INPUTS["recompute_adversarial"],
        "test_id,status,net_return_dollars,reason\n"
        "top_1pct_trade_removal,PASS,-68218.73500000016,\n"
        "two_x_cost_stress,FAIL,-92118.55500000017,\n"
        "random_entry_distribution,MISSING_WITH_REASON,,from Phase 8 failure analysis\n",
    )

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_random_entry_no_longer_terminal_fail_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _failure_analysis()
    payload["baseline_comparison_gate"]["baselines"][0]["candidate_beats_random_median"] = True
    _write_json(repo_root, TEST_INPUTS["failure_analysis"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_two_x_cost_stress_no_longer_fail_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _phase8_decision()
    payload["promotion_metric_gate"]["cost_execution_stress_gate"]["status"] = "PASS"
    payload["promotion_metric_gate"]["cost_execution_stress_gate"]["stress_results"][0][
        "edge_survives"
    ] = True
    _write_json(repo_root, TEST_INPUTS["phase8_decision"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_alpha_closeout_silent_label_shuffle_inference_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _alpha_closeout()
    for bucket in payload["bucket_dispositions"]:
        if bucket["bucket_id"] == "null_label_shuffle":
            bucket["source_status"] = "PASS"
            bucket["closeout_classification"] = "diagnostic_pass_only"
    _write_json(repo_root, TEST_INPUTS["alpha_closeout"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_non_approval_flag_true_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _run_status()
    payload["summary"]["predictions_executed"] = True
    _write_json(repo_root, TEST_INPUTS["run_status"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["promotion_allowed"] is False


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
