from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase9_reconciliation as phase9


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
                "audit_area": "Phase 9",
                "run_status": "RUN",
                "detail_status": "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT",
                "evidence_state": "limited-scope",
                "scope": "tier1_core_phase6_full_predictions_20260706 statistical/failure/gap evidence",
                "accepted_evidence": [],
                "notes": ["Existing alpha evidence closeout says the current line is closed."],
            }
        ],
    }


def _overview_payload() -> dict[str, object]:
    return {"status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY", "summary": {"failure_count": 0}}


def _phase_payload(name: str, status: str) -> dict[str, object]:
    return {
        "status": status,
        "summary": {
            "failure_count": 0,
            f"{name}_master_audit_status": f"RUN_LIMITED_SCOPE_{name.upper()}_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
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
        "phase8_reconciliation": _phase_payload(
            "phase8", "PASS_MASTER_AUDIT_PHASE8_RECONCILIATION_REPORT_ONLY"
        ),
    }


def _bucket_status(bucket_id: str) -> str:
    fail = {
        "baseline_no_trade",
        "baseline_random_entry_null",
        "statistical_probabilistic_sharpe",
        "stability_regime_breakdowns",
        "stability_fold_market_year_session",
        "execution_cost_stress",
    }
    missing = {
        "baseline_simple_carry_term_structure",
        "null_label_shuffle",
        "null_timing_shift",
        "statistical_pbo",
        "statistical_deflated_sharpe",
        "statistical_multiple_testing",
        "execution_delay_stress",
        "execution_capacity",
        "execution_liquidity_window",
        "execution_spread_slippage",
        "execution_partial_fills_rejects",
    }
    if bucket_id in fail:
        return "FAIL"
    if bucket_id in missing:
        return "MISSING_EVIDENCE"
    return "PASS"


def _alpha_gap_payload() -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
        "run_id": phase9.RUN_ID,
        "alpha_evidence_ready": False,
        "required_bucket_count": 23,
        "bucket_status_counts": dict(phase9.EXPECTED_BUCKET_STATUS_COUNTS),
        "blockers": [f"blocker-{idx}" for idx in range(17)],
        "buckets": [
            {"bucket_id": bucket_id, "status": _bucket_status(bucket_id)}
            for bucket_id in sorted(phase9.EXPECTED_BUCKET_IDS)
        ],
        "diagnostic_only": True,
        "non_approval": {
            "artifact_freeze": False,
            "cleanup": False,
            "final_holdout": False,
            "live": False,
            "paper": False,
            "phase8_promotion": False,
            "provider_downloads": False,
            "staging_commit_push": False,
            "target_discovery": False,
            "wfa_modeling": False,
        },
    }


def _alpha_closeout_payload(source_sha: str = "placeholder") -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
        "run_id": phase9.RUN_ID,
        "bucket_count": 23,
        "bucket_status_counts": dict(phase9.EXPECTED_BUCKET_STATUS_COUNTS),
        "closeout_classification_counts": dict(phase9.EXPECTED_CLOSEOUT_CLASSIFICATION_COUNTS),
        "terminal_fail_count": 5,
        "missing_required_evidence_count": 11,
        "modeling_pause_required": True,
        "future_modeling_allowed": False,
        "future_evidence_work_allowed": True,
        "promotion_allowed": False,
        "blockers": [f"blocker-{idx}" for idx in range(17)],
        "diagnostic_only": True,
        "source_matrix": {
            "path": phase9.ALPHA_GAP_MATRIX.as_posix(),
            "sha256": source_sha,
            "verdict": "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
            "alpha_evidence_ready": False,
            "bucket_status_counts": dict(phase9.EXPECTED_BUCKET_STATUS_COUNTS),
        },
        "non_approval": {
            "artifact_freeze": False,
            "cleanup": False,
            "final_holdout": False,
            "live": False,
            "paper": False,
            "phase8_refresh": False,
            "promotion": False,
            "provider_downloads": False,
            "rescue_tuning": False,
            "source_tests": False,
            "staging_commit_push": False,
            "target_discovery": False,
            "wfa_modeling": False,
        },
    }


def _statistical_validity_payload() -> dict[str, object]:
    return {
        "status": "FAIL",
        "statistical_validity_ready": False,
        "diagnostic_only": True,
        "research_only": True,
        "run": phase9.RUN_ID,
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


def _failure_analysis_payload() -> dict[str, object]:
    return {
        "status": "PASS",
        "failure_analysis_ready": True,
        "diagnostic_only": True,
        "research_only": True,
        "run": phase9.RUN_ID,
        "prediction_count": 123,
        "policy_row_count": 12,
        "failure_count": 0,
        "model_promotion_allowed": False,
        "failure_classifications": [
            {"classification": "gross_edge_absent"},
            {"classification": "baseline_failure"},
            {"classification": "cost_stress_failure"},
        ],
    }


def _payloads() -> dict[str, dict[str, object]]:
    payloads = _previous_phase_payloads()
    payloads.update(
        {
            "alpha_gap_matrix": _alpha_gap_payload(),
            "alpha_closeout": _alpha_closeout_payload(),
            "statistical_validity": _statistical_validity_payload(),
            "failure_analysis": _failure_analysis_payload(),
        }
    )
    return payloads


def _base_repo(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, dict[str, object]] | None = None,
) -> Path:
    _write_text(tmp_path / "MASTER_AUDIT.md", "Phase 9 Audit\n")
    _write_text(tmp_path / "PROJECT_OUTLINE.md", "Phase 9 closeout blocks promotion\n")
    _write_text(tmp_path / "CODEX_HANDOFF.md", "handoff\n")
    _write_json(tmp_path / phase9.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase9.DEFAULT_OVERVIEW, _overview_payload())

    payloads = _payloads()
    if payload_overrides:
        payloads.update(payload_overrides)
    for key, path in phase9.REQUIRED_INPUTS.items():
        if key in {"master_audit", "project_outline", "codex_handoff", "run_status", "overview"}:
            continue
        if key == "alpha_closeout":
            continue
        _write_json(tmp_path / path, payloads[key])
    gap_sha = phase9.inventory.sha256_file(tmp_path / phase9.ALPHA_GAP_MATRIX)
    closeout = copy.deepcopy(payloads["alpha_closeout"])
    if "source_matrix" in closeout and closeout["source_matrix"].get("sha256") == "placeholder":
        closeout["source_matrix"]["sha256"] = gap_sha
    _write_json(tmp_path / phase9.ALPHA_CLOSEOUT, closeout)
    return tmp_path / phase9.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(tmp_path, payload_overrides=payload_overrides)
    return phase9.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_phase9_reconciliation_passes_as_limited_closeout(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase9.PASS_STATUS
    assert report["summary"]["phase9_master_audit_status"] == "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT"
    assert report["summary"]["phase9_full_master_audit_accepted"] is False
    assert report["summary"]["alpha_evidence_ready"] is False
    assert report["summary"]["future_modeling_allowed"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["prediction_parquet_read_executed"] is False
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_alpha_gap_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_gap = copy.deepcopy(_alpha_gap_payload())
    bad_gap["alpha_evidence_ready"] = True

    report = _build(tmp_path, payload_overrides={"alpha_gap_matrix": bad_gap})

    assert report["status"] == phase9.FAIL_STATUS
    assert any("gap matrix" in failure for failure in report["failures"])


def test_alpha_closeout_modeling_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_closeout = _alpha_closeout_payload()
    bad_closeout["future_modeling_allowed"] = True

    report = _build(tmp_path, payload_overrides={"alpha_closeout": bad_closeout})

    assert report["status"] == phase9.FAIL_STATUS
    assert any("completion closeout" in failure for failure in report["failures"])


def test_statistical_validity_pass_fails_closed(tmp_path: Path) -> None:
    bad_stat = copy.deepcopy(_statistical_validity_payload())
    bad_stat["status"] = "PASS"
    bad_stat["failure_count"] = 0
    bad_stat["failures"] = []

    report = _build(tmp_path, payload_overrides={"statistical_validity": bad_stat})

    assert report["status"] == phase9.FAIL_STATUS
    assert any("statistical-validity" in failure for failure in report["failures"])


def test_source_matrix_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    bad_closeout = _alpha_closeout_payload(source_sha="bad".ljust(64, "0"))

    report = _build(tmp_path, payload_overrides={"alpha_closeout": bad_closeout})

    assert report["status"] == phase9.FAIL_STATUS
    assert any("source_matrix" in failure for failure in report["failures"])


def test_upstream_promotion_upgrade_fails_closed(tmp_path: Path) -> None:
    payloads = _previous_phase_payloads()
    bad_phase8 = copy.deepcopy(payloads["phase8_reconciliation"])
    bad_phase8["summary"]["promotion_allowed"] = True

    report = _build(tmp_path, payload_overrides={"phase8_reconciliation": bad_phase8})

    assert report["status"] == phase9.FAIL_STATUS
    assert any("Phase 1B-8" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = phase9.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        phase9.REPORT_JSON,
        phase9.REPORT_MD,
    ]
    payload = json.loads((reports_root / phase9.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["phase9_harness_executed"] is False
    assert payload["non_approval"]["prediction_parquet_read_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase9.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase9.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
