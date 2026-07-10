from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase8_reconciliation as phase8


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run_status_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
            "failure_count": 0,
        },
        "run_status_table": [
            {
                "audit_area": "Phase 8",
                "run_status": "RUN",
                "detail_status": "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE",
                "evidence_state": "current",
                "scope": "tier1_core_phase6_full_predictions_20260706 report evidence only",
                "accepted_evidence": [],
                "notes": [
                    "Existing Phase 8 decision says promoted=false and model_promotion_allowed=false."
                ],
            }
        ],
    }


def _overview_payload() -> dict[str, object]:
    return {"status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY", "summary": {"failure_count": 0}}


def _phase_payload(name: str, status: str) -> dict[str, object]:
    return {
        "status": status,
        "scope": {
            "markets": list(phase8.EXPECTED_MARKETS),
            "years": list(phase8.EXPECTED_YEARS),
            "fold_count": phase8.EXPECTED_FOLD_COUNT,
        },
        "summary": {
            "failure_count": 0,
            f"{name}_master_audit_status": f"RUN_LIMITED_SCOPE_{name.upper()}_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
            "prediction_count": 123,
        },
    }


def _previous_phase_payloads() -> dict[str, dict[str, object]]:
    return {
        "phase1b_reconciliation": _phase_payload(
            "phase1b", "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"
        ),
        "phase2_reconciliation": _phase_payload(
            "phase2", "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY"
        ),
        "phase3_reconciliation": _phase_payload(
            "phase3", "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY"
        ),
        "phase4_reconciliation": _phase_payload(
            "phase4", "PASS_MASTER_AUDIT_PHASE4_RECONCILIATION_REPORT_ONLY"
        ),
        "phase5_reconciliation": _phase_payload(
            "phase5", "PASS_MASTER_AUDIT_PHASE5_RECONCILIATION_REPORT_ONLY"
        ),
        "phase6_reconciliation": _phase_payload(
            "phase6", "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY"
        ),
        "phase7_reconciliation": _phase_payload(
            "phase7", "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY"
        ),
    }


def _phase8_decision_payload() -> dict[str, object]:
    return {
        "run": phase8.RUN_ID,
        "profile": phase8.EXPECTED_PROFILE,
        "resolved_profile": phase8.EXPECTED_RESOLVED_PROFILE,
        "promoted": False,
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "promotion_gate": {
            "research_alpha_ready": False,
            "model_promotion_allowed": False,
            "promotion_blocker_count": 30,
        },
        "promotion_metric_gate": {"status": "FAIL", "failure_count": 25},
        "statistical_validity_gate": {"status": "FAIL", "failure_count": 7},
        "blockers": [f"blocker {idx}" for idx in range(30)],
        "costed_oos": {
            "scope": "overall",
            "gross_return_dollars": -19871.875,
            "net_return_dollars": -55995.215,
            "cost_dollars": 36123.34,
            "profit_factor": 0.6698645571410249,
            "trade_count": 1347,
        },
        "markets": [{"market": market} for market in phase8.EXPECTED_MARKETS],
        "folds": [{"fold_id": f"fold-{idx}"} for idx in range(phase8.EXPECTED_FOLD_COUNT)],
        "final_holdout_touched": False,
        "used_final_holdout_for_tuning": False,
        "failure_count": 0,
        "warning_count": 0,
    }


def _phase8_metrics_payload() -> dict[str, object]:
    return {
        "run": phase8.RUN_ID,
        "prediction_count": 123,
        "policy_row_count": 12,
        "failure_count": 0,
        "warning_count": 0,
        "research_policy_metrics_ready": True,
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "final_holdout_touched": False,
    }


def _failure_analysis_payload() -> dict[str, object]:
    return {
        "status": "PASS",
        "failure_analysis_ready": True,
        "diagnostic_only": True,
        "research_only": True,
        "run": phase8.RUN_ID,
        "prediction_count": 123,
        "policy_row_count": 12,
        "failure_count": 0,
        "model_promotion_allowed": False,
        "top_findings": [
            "Gross PnL is -19871.875 and net PnL is -55995.215.",
            "Baseline gate status is FAIL with 2 failures.",
        ],
        "failure_classifications": [
            {"classification": "gross_edge_absent"},
            {"classification": "baseline_failure"},
            {"classification": "cost_stress_failure"},
        ],
    }


def _statistical_validity_payload() -> dict[str, object]:
    return {
        "status": "FAIL",
        "statistical_validity_ready": False,
        "diagnostic_only": True,
        "research_only": True,
        "run": phase8.RUN_ID,
        "prediction_count": 123,
        "policy_trade_count": 1347,
        "failure_count": 5,
        "model_promotion_allowed": False,
        "failures": [
            "statistical-validity evidence missing or failing: pbo",
            "statistical-validity evidence missing or failing: deflated_sharpe",
            "statistical-validity evidence missing or failing: probabilistic_sharpe",
            "statistical-validity evidence missing or failing: multiple_testing_adjustment",
            "statistical-validity evidence missing or failing: regime_breakdowns",
        ],
    }


def _prediction_diagnostics_payload() -> dict[str, object]:
    return {
        "status": "PREDICTION_DIAGNOSTICS_READY",
        "run": phase8.RUN_ID,
        "prediction_count": 123,
        "failure_count": 0,
        "failure_labels": ["weak_signal"],
    }


def _prediction_audit_payload() -> dict[str, object]:
    return {
        "status": "PASS",
        "run": phase8.RUN_ID,
        "prediction_count": 123,
        "failure_count": 0,
        "phase7_prediction_audit_ready": True,
    }


def _payloads() -> dict[str, dict[str, object]]:
    payloads = _previous_phase_payloads()
    payloads.update(
        {
            "phase8_decision": _phase8_decision_payload(),
            "phase8_metrics": _phase8_metrics_payload(),
            "failure_analysis": _failure_analysis_payload(),
            "statistical_validity": _statistical_validity_payload(),
            "prediction_diagnostics": _prediction_diagnostics_payload(),
            "prediction_audit": _prediction_audit_payload(),
        }
    )
    return payloads


def _base_repo(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, dict[str, object]] | None = None,
) -> Path:
    _write_text(tmp_path / "MASTER_AUDIT.md", "Phase 8 Audit\n")
    _write_text(tmp_path / "PROJECT_OUTLINE.md", "Phase 8 promotion defaults blocked\n")
    _write_text(tmp_path / "CODEX_HANDOFF.md", "handoff\n")
    _write_json(tmp_path / phase8.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase8.DEFAULT_OVERVIEW, _overview_payload())

    payloads = _payloads()
    if payload_overrides:
        payloads.update(payload_overrides)
    for key, path in phase8.REQUIRED_INPUTS.items():
        if key in {"master_audit", "project_outline", "codex_handoff", "run_status", "overview"}:
            continue
        _write_json(tmp_path / path, payloads[key])
    return tmp_path / phase8.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(tmp_path, payload_overrides=payload_overrides)
    return phase8.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_phase8_reconciliation_passes_as_negative_report_only_evidence(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase8.PASS_STATUS
    assert report["summary"]["phase8_master_audit_status"] == "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE"
    assert report["summary"]["phase8_full_master_audit_accepted"] is False
    assert report["summary"]["research_alpha_ready"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["prediction_parquet_read_executed"] is False
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_promoted_phase8_decision_fails_closed(tmp_path: Path) -> None:
    bad_decision = copy.deepcopy(_phase8_decision_payload())
    bad_decision["promoted"] = True

    report = _build(tmp_path, payload_overrides={"phase8_decision": bad_decision})

    assert report["status"] == phase8.FAIL_STATUS
    assert any("non-approval" in failure for failure in report["failures"])


def test_statistical_validity_must_remain_failing_blocker(tmp_path: Path) -> None:
    bad_stat = copy.deepcopy(_statistical_validity_payload())
    bad_stat["status"] = "PASS"
    bad_stat["failure_count"] = 0
    bad_stat["failures"] = []

    report = _build(tmp_path, payload_overrides={"statistical_validity": bad_stat})

    assert report["status"] == phase8.FAIL_STATUS
    assert any("statistical-validity" in failure for failure in report["failures"])


def test_phase8_metrics_count_mismatch_fails_closed(tmp_path: Path) -> None:
    bad_metrics = copy.deepcopy(_phase8_metrics_payload())
    bad_metrics["prediction_count"] = 999

    report = _build(tmp_path, payload_overrides={"phase8_metrics": bad_metrics})

    assert report["status"] == phase8.FAIL_STATUS
    assert any("metrics JSON" in failure for failure in report["failures"])


def test_upstream_promotion_upgrade_fails_closed(tmp_path: Path) -> None:
    payloads = _previous_phase_payloads()
    bad_phase7 = copy.deepcopy(payloads["phase7_reconciliation"])
    bad_phase7["summary"]["promotion_allowed"] = True

    report = _build(tmp_path, payload_overrides={"phase7_reconciliation": bad_phase7})

    assert report["status"] == phase8.FAIL_STATUS
    assert any("Phase 1B-7" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = phase8.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        phase8.REPORT_JSON,
        phase8.REPORT_MD,
    ]
    payload = json.loads((reports_root / phase8.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["phase8_evaluation_executed"] is False
    assert payload["non_approval"]["prediction_parquet_read_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase8.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase8.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
