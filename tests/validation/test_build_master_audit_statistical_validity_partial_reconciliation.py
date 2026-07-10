from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_statistical_validity_partial_reconciliation as partial,
)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _gap_map() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_GAP_REMEDIATION_EVIDENCE_MAP_REPORT_ONLY",
        "summary": {
            "gap_area_statuses": {
                "data_integrity": "PASS",
                "statistical_validity": "FAIL",
                "operational_resilience": "FAIL",
            },
            "data_integrity_ready": True,
            "statistical_validity_ready": False,
            "operational_resilience_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
        },
        "gap_maps": {
            "statistical_validity": {
                "status": "FAIL",
                "ready": False,
                "accepted_check_ids": [],
                "failure_count": 3,
                "checks": [
                    {
                        "check_id": "locked_oos_and_baseline_comparability",
                        "status": "FAIL",
                    },
                    {
                        "check_id": "trial_ledger_and_overfit_accounting",
                        "status": "FAIL",
                    },
                    {
                        "check_id": "stability_regime_concept_drift",
                        "status": "FAIL",
                    },
                ],
            }
        },
    }


def _statistical_summary() -> dict[str, object]:
    return {
        "status": "FAIL",
        "statistical_validity_ready": False,
        "prediction_count": 9_172_416,
        "policy_trade_count": 1_347,
        "failure_count": 5,
        "research_only": True,
        "model_promotion_allowed": False,
        "required_checks": {
            "pbo": {"status": "FAIL_MISSING_TRIAL_LOG", "trial_count": None},
            "deflated_sharpe": {
                "status": "FAIL_MISSING_TRIAL_LOG",
                "trial_count": None,
            },
            "probabilistic_sharpe": {
                "status": "FAIL",
                "probabilistic_sharpe": 0.0,
                "sharpe_like": -4.56884658431966,
            },
            "bootstrap_confidence_intervals": {
                "status": "PASS",
                "sample_count": 500,
            },
            "multiple_testing_adjustment": {
                "status": "FAIL_MISSING_TRIAL_LOG",
                "trial_count": None,
            },
            "parameter_stability": {"status": "PASS"},
            "regime_breakdowns": {"status": "FAIL"},
        },
    }


def _bootstrap_rows() -> list[dict[str, object]]:
    return [
        {
            "metric": "net_return_dollars",
            "sample_count": 500,
            "ci_low": -80_067.74562500016,
            "ci_mid": -55_426.87750000031,
            "ci_high": -29_269.266750000264,
        },
        {
            "metric": "sharpe_like",
            "sample_count": 500,
            "ci_low": -6.229268226113485,
            "ci_mid": -4.520871219651594,
            "ci_high": -2.5914526525926918,
        },
    ]


def _stability_rows() -> list[dict[str, object]]:
    return [
        {"scope": "market", "key": "ES", "net_return_dollars": -1.0},
        {"scope": "year", "key": "2024", "net_return_dollars": -2.0},
        {"scope": "fold", "key": "ES_research_0001", "net_return_dollars": -3.0},
    ]


def _adversarial_rows() -> list[dict[str, object]]:
    return [
        {
            "test_id": "top_1pct_trade_removal",
            "status": "PASS",
            "net_return_dollars": -68_218.73500000016,
            "reason": "",
        },
        {
            "test_id": "two_x_cost_stress",
            "status": "FAIL",
            "net_return_dollars": -92_118.55500000017,
            "reason": "",
        },
        {
            "test_id": "label_shuffle",
            "status": "MISSING_WITH_REASON",
            "net_return_dollars": "",
            "reason": "requires a bounded rerun/shuffle harness",
        },
    ]


def _alpha_gap_matrix() -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
        "alpha_evidence_ready": False,
        "buckets": [
            {"bucket_id": "statistical_pbo", "status": "MISSING_EVIDENCE"},
            {
                "bucket_id": "statistical_deflated_sharpe",
                "status": "MISSING_EVIDENCE",
            },
            {"bucket_id": "statistical_probabilistic_sharpe", "status": "FAIL"},
            {"bucket_id": "statistical_bootstrap_ci", "status": "PASS"},
            {"bucket_id": "statistical_multiple_testing", "status": "MISSING_EVIDENCE"},
            {"bucket_id": "stability_parameter", "status": "PASS"},
            {"bucket_id": "stability_regime_breakdowns", "status": "FAIL"},
        ],
    }


def _closeout() -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
        "future_modeling_allowed": False,
        "promotion_allowed": False,
        "bucket_dispositions": [
            {
                "bucket_id": "statistical_pbo",
                "closeout_classification": "missing_required_evidence",
            },
            {
                "bucket_id": "statistical_deflated_sharpe",
                "closeout_classification": "missing_required_evidence",
            },
            {
                "bucket_id": "statistical_probabilistic_sharpe",
                "closeout_classification": "terminal_fail",
            },
            {
                "bucket_id": "statistical_bootstrap_ci",
                "closeout_classification": "diagnostic_pass_only",
            },
            {
                "bucket_id": "statistical_multiple_testing",
                "closeout_classification": "missing_required_evidence",
            },
            {
                "bucket_id": "stability_parameter",
                "closeout_classification": "diagnostic_pass_only",
            },
            {
                "bucket_id": "stability_regime_breakdowns",
                "closeout_classification": "not_actionable_for_current_line",
            },
        ],
    }


def _wfa_split() -> dict[str, object]:
    return {
        "status": "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD",
        "summary": {
            "classification": "same_fold_rolling_retraining_research_only",
            "failure_count": 0,
            "warning_count": 2,
            "model_trust_ready": False,
            "valid_for_independent_holdout_claims": False,
            "valid_for_same_fold_rolling_retraining_research_evidence": True,
        },
        "non_approval": {
            "wfa_modeling": False,
            "predictions": False,
            "promotion": False,
        },
    }


def _run_status() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
            "data_model_commands_executed": False,
            "wfa_modeling_executed": False,
            "predictions_executed": False,
            "provider_network_calls_executed": False,
            "promotion_or_freeze_or_holdout_executed": False,
            "paper_or_live_executed": False,
        },
    }


def _base_repo(
    tmp_path: Path,
    *,
    gap_map: dict[str, object] | None = None,
    statistical_summary: dict[str, object] | None = None,
    alpha_gap_matrix: dict[str, object] | None = None,
    closeout: dict[str, object] | None = None,
    wfa_split: dict[str, object] | None = None,
    run_status: dict[str, object] | None = None,
) -> Path:
    _write_json(tmp_path / partial.GAP_MAP_AFTER_PHASE2, gap_map or _gap_map())
    _write_json(
        tmp_path / partial.STATISTICAL_SUMMARY,
        statistical_summary or _statistical_summary(),
    )
    _write_csv(tmp_path / partial.BOOTSTRAP_CI, _bootstrap_rows())
    _write_csv(tmp_path / partial.STABILITY_MATRIX, _stability_rows())
    _write_csv(tmp_path / partial.ADVERSARIAL_TESTS, _adversarial_rows())
    _write_json(tmp_path / partial.ALPHA_GAP_MATRIX, alpha_gap_matrix or _alpha_gap_matrix())
    _write_json(
        tmp_path / partial.ALPHA_COMPLETION_CLOSEOUT,
        closeout or _closeout(),
    )
    _write_json(tmp_path / partial.WFA_SPLIT_CONTAMINATION, wfa_split or _wfa_split())
    _write_json(tmp_path / partial.RUN_STATUS, run_status or _run_status())
    _write_text(
        tmp_path / partial.ADVERSARIAL_AUDIT,
        "No complete current-scope trial log exists. Probabilistic Sharpe fails. "
        "Regime breakdowns fail. Blocked for trading and alpha acceptance.\n",
    )
    return tmp_path / partial.DEFAULT_REPORTS_ROOT


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root = _base_repo(tmp_path, **kwargs)
    return partial.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )


def test_statistical_partial_reconciliation_passes_current_style_evidence(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == partial.PASS_STATUS
    assert report["summary"]["bootstrap_ci_diagnostic_pass"] is True
    assert report["summary"]["parameter_stability_diagnostic_pass"] is True
    assert report["summary"]["statistical_validity_ready"] is False
    assert report["summary"]["full_master_audit_statistical_check_ready"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["pbo_status"] == "FAIL_MISSING_TRIAL_LOG"
    assert report["summary"]["regime_breakdowns_status"] == "FAIL"


def test_missing_bootstrap_csv_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    (tmp_path / partial.BOOTSTRAP_CI).unlink()

    report = partial.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == partial.FAIL_STATUS
    assert any("bootstrap" in failure.lower() for failure in report["failures"])


def test_missing_stability_csv_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    (tmp_path / partial.STABILITY_MATRIX).unlink()

    report = partial.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == partial.FAIL_STATUS
    assert any("stability" in failure.lower() for failure in report["failures"])


def test_changed_bootstrap_status_fails_closed(tmp_path: Path) -> None:
    statistical = _statistical_summary()
    checks = statistical["required_checks"]  # type: ignore[index]
    checks["bootstrap_confidence_intervals"]["status"] = "FAIL"  # type: ignore[index]

    report = _build(tmp_path, statistical_summary=statistical)

    assert report["status"] == partial.FAIL_STATUS
    assert any("partial-pass" in failure for failure in report["failures"])


def test_changed_parameter_stability_status_fails_closed(tmp_path: Path) -> None:
    statistical = _statistical_summary()
    checks = statistical["required_checks"]  # type: ignore[index]
    checks["parameter_stability"]["status"] = "FAIL"  # type: ignore[index]

    report = _build(tmp_path, statistical_summary=statistical)

    assert report["status"] == partial.FAIL_STATUS
    assert any("partial-pass" in failure for failure in report["failures"])


def test_trial_log_blockers_must_remain_missing_evidence(tmp_path: Path) -> None:
    statistical = _statistical_summary()
    checks = statistical["required_checks"]  # type: ignore[index]
    checks["pbo"]["status"] = "PASS"  # type: ignore[index]

    report = _build(tmp_path, statistical_summary=statistical)

    assert report["status"] == partial.FAIL_STATUS
    assert any("partial-pass" in failure for failure in report["failures"])


def test_psr_and_regime_failures_must_be_preserved(tmp_path: Path) -> None:
    statistical = _statistical_summary()
    checks = statistical["required_checks"]  # type: ignore[index]
    checks["probabilistic_sharpe"]["status"] = "PASS"  # type: ignore[index]
    checks["regime_breakdowns"]["status"] = "PASS"  # type: ignore[index]

    report = _build(tmp_path, statistical_summary=statistical)

    assert report["status"] == partial.FAIL_STATUS
    assert any("partial-pass" in failure for failure in report["failures"])


def test_upstream_data_integrity_must_be_pass(tmp_path: Path) -> None:
    gap_map = _gap_map()
    gap_map["summary"]["gap_area_statuses"]["data_integrity"] = "FAIL"  # type: ignore[index]

    report = _build(tmp_path, gap_map=gap_map)

    assert report["status"] == partial.FAIL_STATUS
    assert any("after-Phase-2 gap map" in failure for failure in report["failures"])


def test_model_or_promotion_flag_true_fails_closed(tmp_path: Path) -> None:
    closeout = _closeout()
    closeout["promotion_allowed"] = True

    report = _build(tmp_path, closeout=closeout)

    assert report["status"] == partial.FAIL_STATUS
    assert any("diagnostic-only" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = partial.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        partial.REPORT_JSON,
        partial.REPORT_MD,
    ]
    payload = json.loads((reports_root / partial.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["statistical_validity_ready"] is False
    assert payload["summary"]["model_trust_ready"] is False


def test_no_gap_map_statistical_check_is_upgraded(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["gap_statistical_check_statuses"] == {
        "locked_oos_and_baseline_comparability": "FAIL",
        "trial_ledger_and_overfit_accounting": "FAIL",
        "stability_regime_concept_drift": "FAIL",
    }
    assert report["summary"]["statistical_validity_ready"] is False
    assert report["summary"]["full_master_audit_statistical_check_ready"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = partial.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == partial.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
