from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_post_mutation_trial_search_completeness_reconciliation as post_plan,
)
from scripts.validation import (
    build_master_audit_statistical_validity_recompute_decision as plan,
)
from tests.validation import (
    test_build_master_audit_post_mutation_trial_search_completeness_reconciliation
    as post_fixture,
)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


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
        {
            "scope": "market",
            "market": "ES",
            "row_count": 10,
            "trade_count": 1,
            "net_return_dollars": -1.0,
            "sharpe_like": -1.0,
            "positive_net": False,
            "year": "",
            "fold_id": "",
        },
        {
            "scope": "year",
            "market": "",
            "row_count": 10,
            "trade_count": 1,
            "net_return_dollars": -2.0,
            "sharpe_like": -2.0,
            "positive_net": False,
            "year": 2024,
            "fold_id": "",
        },
        {
            "scope": "fold",
            "market": "ES",
            "row_count": 10,
            "trade_count": 1,
            "net_return_dollars": -3.0,
            "sharpe_like": -3.0,
            "positive_net": False,
            "year": 2024,
            "fold_id": "ES_research_0001",
        },
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
            "test_id": "random_entry_distribution",
            "status": "MISSING_WITH_REASON",
            "net_return_dollars": "",
            "reason": "random-entry distribution is produced by Phase 8 failure analysis",
        },
        {
            "test_id": "label_shuffle",
            "status": "MISSING_WITH_REASON",
            "net_return_dollars": "",
            "reason": "requires a bounded rerun/shuffle harness",
        },
    ]


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
            "deflated_sharpe": {"status": "FAIL_MISSING_TRIAL_LOG", "trial_count": None},
            "probabilistic_sharpe": {"status": "FAIL"},
            "bootstrap_confidence_intervals": {"status": "PASS", "sample_count": 500},
            "multiple_testing_adjustment": {
                "status": "FAIL_MISSING_TRIAL_LOG",
                "trial_count": None,
            },
            "parameter_stability": {"status": "PASS"},
            "regime_breakdowns": {"status": "FAIL"},
        },
    }


def _build_state(tmp_path: Path) -> dict[str, Path]:
    post_overrides = post_fixture._write_post_mutation_state(tmp_path)
    post_root = tmp_path / "reports/master_audit/pm"
    post_root.mkdir(parents=True, exist_ok=True)
    post_report = post_plan.build_report(
        repo_root=tmp_path,
        reports_root=post_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=post_overrides,
    )
    assert post_report["status"] == post_plan.PASS_STATUS
    _write_json(post_root / post_plan.REPORT_JSON, post_report)

    _write_json(tmp_path / plan.STATISTICAL_SUMMARY, _statistical_summary())
    _write_csv(tmp_path / plan.BOOTSTRAP_CI, _bootstrap_rows())
    _write_csv(tmp_path / plan.STABILITY_MATRIX, _stability_rows())
    _write_csv(tmp_path / plan.ADVERSARIAL_TESTS, _adversarial_rows())
    run_status = _read_json(tmp_path / plan.RUN_STATUS)
    run_summary = run_status.setdefault("summary", {})
    run_summary["cleanup_or_git_publication_executed"] = False  # type: ignore[index]
    _write_json(tmp_path / plan.RUN_STATUS, run_status)
    return {"post_mutation_completeness": (post_root / post_plan.REPORT_JSON).relative_to(tmp_path)}


def _build_with_overrides(
    tmp_path: Path,
    overrides: dict[str, Path],
    **kwargs: object,
) -> dict[str, object]:
    overrides.update(kwargs.pop("required_input_overrides", {}) if "required_input_overrides" in kwargs else {})
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "reports/master_audit/recompute_decision",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
        **kwargs,
    )


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    return _build_with_overrides(tmp_path, _build_state(tmp_path), **kwargs)


def test_recompute_decision_passes_current_style_evidence(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    summary = report["summary"]
    assert summary["pbo_recompute_decision"] == plan.READY_DECISION
    assert summary["deflated_sharpe_recompute_decision"] == plan.READY_DECISION
    assert summary["multiple_testing_recompute_decision"] == plan.READY_DECISION
    assert summary["trial_count_for_recompute"] == 22
    assert summary["search_family_count"] == 10
    assert summary["multiple_testing_family_count"] == 2
    assert summary["statistical_recompute_executed"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False


def test_missing_post_mutation_report_fails_closed(tmp_path: Path) -> None:
    overrides = _build_state(tmp_path)
    (tmp_path / overrides["post_mutation_completeness"]).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "reports/master_audit/recompute_decision",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("post-mutation" in failure for failure in report["failures"])


def test_changed_trial_search_family_counts_fail_closed(tmp_path: Path) -> None:
    overrides = _build_state(tmp_path)
    post_path = tmp_path / overrides["post_mutation_completeness"]
    post = _read_json(post_path)
    post["summary"]["search_family_count"] = 9  # type: ignore[index]
    _write_json(post_path, post)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "reports/master_audit/recompute_decision",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("trial/search completeness" in failure for failure in report["failures"])


def test_statistical_summary_upgrade_fails_closed(tmp_path: Path) -> None:
    overrides = _build_state(tmp_path)
    statistical_path = tmp_path / plan.STATISTICAL_SUMMARY
    statistical = _read_json(statistical_path)
    statistical["status"] = "PASS"
    statistical["statistical_validity_ready"] = True
    _write_json(statistical_path, statistical)

    report = _build_with_overrides(tmp_path, overrides)

    assert report["status"] == plan.FAIL_STATUS
    assert any("statistical summary" in failure for failure in report["failures"])


def test_bootstrap_csv_must_preserve_negative_net_return_ci(tmp_path: Path) -> None:
    _build_state(tmp_path)
    rows = copy.deepcopy(_bootstrap_rows())
    rows[0]["ci_high"] = 1.0
    _write_csv(tmp_path / plan.BOOTSTRAP_CI, rows)

    report = _build_with_overrides(tmp_path, {})

    assert report["status"] == plan.FAIL_STATUS
    assert any("bootstrap" in failure.lower() for failure in report["failures"])


def test_adversarial_caveats_must_remain_blocked(tmp_path: Path) -> None:
    _build_state(tmp_path)
    rows = copy.deepcopy(_adversarial_rows())
    rows[1]["status"] = "PASS"
    _write_csv(tmp_path / plan.ADVERSARIAL_TESTS, rows)

    report = _build_with_overrides(tmp_path, {})

    assert report["status"] == plan.FAIL_STATUS
    assert any("adversarial" in failure.lower() for failure in report["failures"])


def test_psr_and_regime_failures_must_remain_failed(tmp_path: Path) -> None:
    _build_state(tmp_path)
    statistical_path = tmp_path / plan.STATISTICAL_SUMMARY
    statistical = _read_json(statistical_path)
    checks = statistical["required_checks"]  # type: ignore[index]
    checks["probabilistic_sharpe"]["status"] = "PASS"  # type: ignore[index]
    checks["regime_breakdowns"]["status"] = "PASS"  # type: ignore[index]
    _write_json(statistical_path, statistical)

    report = _build_with_overrides(tmp_path, {})

    assert report["status"] == plan.FAIL_STATUS
    assert any("statistical summary" in failure for failure in report["failures"])


def test_alpha_closeout_or_promotion_upgrade_fails_closed(tmp_path: Path) -> None:
    _build_state(tmp_path)
    closeout_path = tmp_path / plan.ALPHA_CLOSEOUT
    closeout = _read_json(closeout_path)
    closeout["promotion_allowed"] = True
    _write_json(closeout_path, closeout)

    report = _build_with_overrides(tmp_path, {})

    assert report["status"] == plan.FAIL_STATUS
    assert any("alpha matrix/closeout" in failure for failure in report["failures"])


def test_write_report_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    overrides = _build_state(tmp_path)
    reports_root = tmp_path / "reports/master_audit/rd"

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )
    plan.write_report(report, reports_root)

    assert report["status"] == plan.PASS_STATUS
    assert sorted(path.name for path in reports_root.iterdir()) == [
        plan.REPORT_JSON,
        plan.REPORT_MD,
    ]
    payload = json.loads((reports_root / plan.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["pbo_recompute_decision"] == plan.READY_DECISION
    assert payload["summary"]["statistical_recompute_executed"] is False
    assert payload["summary"]["statistical_validity_ready"] is False
    assert payload["summary"]["model_trust_ready"] is False
