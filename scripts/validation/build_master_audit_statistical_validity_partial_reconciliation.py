#!/usr/bin/env python3
"""Build a report-only statistical-validity partial reconciliation.

This command consumes existing local evidence only. It accepts diagnostic PASS
sub-evidence for bootstrap confidence intervals and parameter stability while
preserving statistical-validity FAIL, missing trial-log blockers, PSR/regime
failures, model-trust blocks, and promotion blocks.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_statistical_validity_partial_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_PARTIAL_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_STATISTICAL_VALIDITY_PARTIAL_RECONCILIATION_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_statistical_validity_partial_reconciliation_20260710"
)
REPORT_JSON = "master_audit_statistical_validity_partial_reconciliation.json"
REPORT_MD = "master_audit_statistical_validity_partial_reconciliation.md"

STAT_ROOT = Path("reports/statistical_validity/tier1_core_phase6_full_predictions_20260706")
GAP_MAP_AFTER_PHASE2 = Path(
    "reports/master_audit/master_audit_gap_remediation_after_phase2_20260710/"
    "master_audit_gap_remediation_evidence_map.json"
)
STATISTICAL_SUMMARY = STAT_ROOT / "statistical_validity_summary.json"
BOOTSTRAP_CI = STAT_ROOT / "bootstrap_confidence_intervals.csv"
STABILITY_MATRIX = STAT_ROOT / "stability_matrix.csv"
ADVERSARIAL_TESTS = STAT_ROOT / "adversarial_tests.csv"
ALPHA_GAP_MATRIX = Path(
    "reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/"
    "alpha_evidence_gap_matrix.json"
)
ALPHA_COMPLETION_CLOSEOUT = Path(
    "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
    "alpha_evidence_completion_closeout.json"
)
WFA_SPLIT_CONTAMINATION = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_contamination_audit/"
    "wfa_split_contamination_audit.json"
)
RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
ADVERSARIAL_AUDIT = Path("docs/adversarial_current_project_evidence_gate_audit_20260709.md")

REQUIRED_INPUTS = {
    "gap_map_after_phase2": GAP_MAP_AFTER_PHASE2,
    "statistical_summary": STATISTICAL_SUMMARY,
    "bootstrap_confidence_intervals": BOOTSTRAP_CI,
    "stability_matrix": STABILITY_MATRIX,
    "adversarial_tests": ADVERSARIAL_TESTS,
    "alpha_gap_matrix": ALPHA_GAP_MATRIX,
    "alpha_completion_closeout": ALPHA_COMPLETION_CLOSEOUT,
    "wfa_split_contamination": WFA_SPLIT_CONTAMINATION,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

NON_APPROVAL = {
    "data_model_commands_executed": False,
    "wfa_modeling_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "statistical_validity_generation_executed": False,
    "alpha_matrix_generation_executed": False,
    "gap_map_generation_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "freeze_executed": False,
    "holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "staging_commit_push_executed": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    failure: str,
    evidence: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "failure": None if passed else failure,
            "evidence": list(evidence),
            "details": dict(details or {}),
        }
    )
    if not passed:
        failures.append(failure)


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], str | None]:
    if not path.is_file():
        return [], f"missing CSV input: {path.as_posix()}"
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)], None
    except Exception as exc:
        return [], f"unreadable CSV {path.as_posix()}: {exc}"


def find_bucket(payload: Mapping[str, Any] | None, bucket_id: str) -> Mapping[str, Any]:
    rows = payload.get("buckets") if isinstance(payload, Mapping) else []
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("bucket_id") == bucket_id:
            return row
    return {}


def find_closeout_bucket(
    payload: Mapping[str, Any] | None,
    bucket_id: str,
) -> Mapping[str, Any]:
    rows = payload.get("bucket_dispositions") if isinstance(payload, Mapping) else []
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("bucket_id") == bucket_id:
            return row
    return {}


def evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields: dict[str, dict[str, str]] = {
        "gap_map_after_phase2": {
            "status": "status",
            "data_integrity": "summary.gap_area_statuses.data_integrity",
            "statistical_validity": "summary.gap_area_statuses.statistical_validity",
            "operational_resilience": "summary.gap_area_statuses.operational_resilience",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "statistical_summary": {
            "status": "status",
            "statistical_validity_ready": "statistical_validity_ready",
            "prediction_count": "prediction_count",
            "policy_trade_count": "policy_trade_count",
            "failure_count": "failure_count",
        },
        "alpha_gap_matrix": {
            "status": "status",
            "verdict": "verdict",
            "alpha_evidence_ready": "alpha_evidence_ready",
        },
        "alpha_completion_closeout": {
            "status": "status",
            "verdict": "verdict",
            "future_modeling_allowed": "future_modeling_allowed",
            "promotion_allowed": "promotion_allowed",
        },
        "wfa_split_contamination": {
            "status": "status",
            "classification": "summary.classification",
            "model_trust_ready": "summary.model_trust_ready",
        },
        "run_status": {
            "status": "status",
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
        },
    }
    return [
        inventory.evidence_file(
            repo_root=repo_root,
            relative_path=relative_path,
            json_fields=json_fields.get(name),
            dirty_map=dirty_map,
        )
        for name, relative_path in paths.items()
    ]


def load_payloads(
    *,
    repo_root: Path,
    paths: Mapping[str, Path],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    payloads: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, relative_path in paths.items():
        if Path(relative_path).suffix.lower() != ".json":
            continue
        payload, error = read_json_object(resolve_path(repo_root, relative_path))
        if error:
            failures.append(f"required JSON input unavailable: {relative_path.as_posix()} ({error})")
        elif payload is not None:
            payloads[name] = payload
    return payloads, failures


def text_contains(path: Path, terms: Sequence[str]) -> dict[str, bool]:
    try:
        text = path.read_text(encoding="utf-8").lower()
    except Exception:
        return {term: False for term in terms}
    return {term: term.lower() in text for term in terms}


def build_checks(
    *,
    repo_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    input_evidence: Sequence[Mapping[str, Any]],
    output_rel: str,
    paths: Mapping[str, Path],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {str(item.get("path")) for item in input_evidence if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required statistical partial reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel.startswith("reports/master_audit/") and not output_rel.endswith("/"),
        failure=f"invalid report output root for statistical partial reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    gap = payloads.get("gap_map_after_phase2")
    gap_statuses = dotted_get(gap, "summary.gap_area_statuses")
    gap_statuses = gap_statuses if isinstance(gap_statuses, Mapping) else {}
    gap_stat = dotted_get(gap, "gap_maps.statistical_validity")
    gap_stat = gap_stat if isinstance(gap_stat, Mapping) else {}
    gap_stat_checks = {
        str(row.get("check_id")): row
        for row in gap_stat.get("checks", [])
        if isinstance(row, Mapping)
    }
    check(
        checks,
        failures,
        name="after_phase2_gap_map_preserves_statistical_validity_fail",
        passed=gap is not None
        and gap.get("status") == "PASS_MASTER_AUDIT_GAP_REMEDIATION_EVIDENCE_MAP_REPORT_ONLY"
        and gap_statuses.get("data_integrity") == "PASS"
        and gap_statuses.get("statistical_validity") == "FAIL"
        and gap_statuses.get("operational_resilience") == "FAIL"
        and dotted_get(gap, "summary.model_trust_ready") is False
        and dotted_get(gap, "summary.promotion_allowed") is False
        and dotted_get(gap, "summary.paper_live_ready") is False
        and dotted_get(gap, "summary.production_ready") is False
        and gap_stat.get("status") == "FAIL"
        and gap_stat.get("accepted_check_ids") == []
        and gap_stat.get("failure_count") == 3
        and all(str(row.get("status")) == "FAIL" for row in gap_stat_checks.values()),
        failure="after-Phase-2 gap map does not preserve statistical-validity fail state",
        evidence=[GAP_MAP_AFTER_PHASE2.as_posix()],
        details={
            "gap_area_statuses": dict(gap_statuses),
            "statistical_validity": {
                "status": gap_stat.get("status"),
                "accepted_check_ids": gap_stat.get("accepted_check_ids"),
                "failure_count": gap_stat.get("failure_count"),
                "check_statuses": {
                    key: row.get("status") for key, row in gap_stat_checks.items()
                },
            },
        },
    )

    statistical = payloads.get("statistical_summary")
    required_checks = statistical.get("required_checks") if isinstance(statistical, Mapping) else {}
    required_checks = required_checks if isinstance(required_checks, Mapping) else {}
    pbo = required_checks.get("pbo") if isinstance(required_checks.get("pbo"), Mapping) else {}
    deflated = (
        required_checks.get("deflated_sharpe")
        if isinstance(required_checks.get("deflated_sharpe"), Mapping)
        else {}
    )
    psr = (
        required_checks.get("probabilistic_sharpe")
        if isinstance(required_checks.get("probabilistic_sharpe"), Mapping)
        else {}
    )
    bootstrap = (
        required_checks.get("bootstrap_confidence_intervals")
        if isinstance(required_checks.get("bootstrap_confidence_intervals"), Mapping)
        else {}
    )
    multiple = (
        required_checks.get("multiple_testing_adjustment")
        if isinstance(required_checks.get("multiple_testing_adjustment"), Mapping)
        else {}
    )
    stability = (
        required_checks.get("parameter_stability")
        if isinstance(required_checks.get("parameter_stability"), Mapping)
        else {}
    )
    regime = (
        required_checks.get("regime_breakdowns")
        if isinstance(required_checks.get("regime_breakdowns"), Mapping)
        else {}
    )
    check(
        checks,
        failures,
        name="statistical_summary_partial_pass_and_failures_preserved",
        passed=statistical is not None
        and statistical.get("status") == "FAIL"
        and statistical.get("statistical_validity_ready") is False
        and statistical.get("prediction_count") == 9_172_416
        and statistical.get("policy_trade_count") == 1_347
        and statistical.get("failure_count") == 5
        and statistical.get("research_only") is True
        and statistical.get("model_promotion_allowed") is False
        and pbo.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and deflated.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and multiple.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and psr.get("status") == "FAIL"
        and bootstrap.get("status") == "PASS"
        and bootstrap.get("sample_count") == 500
        and stability.get("status") == "PASS"
        and regime.get("status") == "FAIL",
        failure="statistical summary does not preserve exact partial-pass/fail-closed state",
        evidence=[STATISTICAL_SUMMARY.as_posix()],
        details={
            "summary_status": None if statistical is None else statistical.get("status"),
            "required_checks": {
                key: dict(value) if isinstance(value, Mapping) else value
                for key, value in required_checks.items()
            },
        },
    )

    bootstrap_rows, bootstrap_error = read_csv_rows(resolve_path(repo_root, BOOTSTRAP_CI))
    net_rows = [
        row
        for row in bootstrap_rows
        if row.get("metric") == "net_return_dollars" and row.get("sample_count") == "500"
    ]
    check(
        checks,
        failures,
        name="bootstrap_confidence_interval_csv_supports_diagnostic_pass",
        passed=bootstrap_error is None and bool(net_rows),
        failure=bootstrap_error
        or "bootstrap confidence interval CSV missing net_return_dollars sample_count=500",
        evidence=[BOOTSTRAP_CI.as_posix()],
        details={"row_count": len(bootstrap_rows), "net_return_dollars_rows": net_rows},
    )

    stability_rows, stability_error = read_csv_rows(resolve_path(repo_root, STABILITY_MATRIX))
    stability_scopes = {row.get("scope") for row in stability_rows}
    check(
        checks,
        failures,
        name="stability_matrix_csv_supports_parameter_stability_pass",
        passed=stability_error is None
        and {"market", "year", "fold"}.issubset(stability_scopes)
        and len(stability_rows) > 0,
        failure=stability_error
        or "stability matrix CSV missing market/year/fold evidence rows",
        evidence=[STABILITY_MATRIX.as_posix()],
        details={"row_count": len(stability_rows), "scopes": sorted(str(item) for item in stability_scopes)},
    )

    adversarial_rows, adversarial_error = read_csv_rows(resolve_path(repo_root, ADVERSARIAL_TESTS))
    adversarial_ids = {row.get("test_id") for row in adversarial_rows}
    check(
        checks,
        failures,
        name="adversarial_tests_csv_preserves_missing_null_caveats",
        passed=adversarial_error is None
        and "label_shuffle" in adversarial_ids
        and "two_x_cost_stress" in adversarial_ids,
        failure=adversarial_error
        or "adversarial tests CSV does not preserve label-shuffle/cost-stress context",
        evidence=[ADVERSARIAL_TESTS.as_posix()],
        details={"test_ids": sorted(str(item) for item in adversarial_ids)},
    )

    matrix = payloads.get("alpha_gap_matrix")
    matrix_buckets = {
        bucket_id: find_bucket(matrix, bucket_id)
        for bucket_id in (
            "statistical_pbo",
            "statistical_deflated_sharpe",
            "statistical_probabilistic_sharpe",
            "statistical_bootstrap_ci",
            "statistical_multiple_testing",
            "stability_parameter",
            "stability_regime_breakdowns",
        )
    }
    check(
        checks,
        failures,
        name="alpha_gap_matrix_classifies_only_diagnostic_subpasses",
        passed=matrix is not None
        and matrix.get("status") == "PASS_REPORT_WRITTEN"
        and matrix.get("verdict") == "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE"
        and matrix.get("alpha_evidence_ready") is False
        and matrix_buckets["statistical_bootstrap_ci"].get("status") == "PASS"
        and matrix_buckets["stability_parameter"].get("status") == "PASS"
        and matrix_buckets["statistical_pbo"].get("status") == "MISSING_EVIDENCE"
        and matrix_buckets["statistical_deflated_sharpe"].get("status") == "MISSING_EVIDENCE"
        and matrix_buckets["statistical_multiple_testing"].get("status") == "MISSING_EVIDENCE"
        and matrix_buckets["statistical_probabilistic_sharpe"].get("status") == "FAIL"
        and matrix_buckets["stability_regime_breakdowns"].get("status") == "FAIL",
        failure="alpha evidence gap matrix does not classify diagnostic PASS and failed/missing buckets as expected",
        evidence=[ALPHA_GAP_MATRIX.as_posix()],
        details={"buckets": {key: dict(value) for key, value in matrix_buckets.items()}},
    )

    closeout = payloads.get("alpha_completion_closeout")
    closeout_buckets = {
        bucket_id: find_closeout_bucket(closeout, bucket_id)
        for bucket_id in (
            "statistical_pbo",
            "statistical_deflated_sharpe",
            "statistical_probabilistic_sharpe",
            "statistical_bootstrap_ci",
            "statistical_multiple_testing",
            "stability_parameter",
            "stability_regime_breakdowns",
        )
    }
    check(
        checks,
        failures,
        name="alpha_closeout_keeps_diagnostic_pass_only_not_model_trust",
        passed=closeout is not None
        and closeout.get("status") == "PASS_REPORT_WRITTEN"
        and closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and closeout.get("future_modeling_allowed") is False
        and closeout.get("promotion_allowed") is False
        and closeout_buckets["statistical_bootstrap_ci"].get("closeout_classification")
        == "diagnostic_pass_only"
        and closeout_buckets["stability_parameter"].get("closeout_classification")
        == "diagnostic_pass_only"
        and closeout_buckets["statistical_pbo"].get("closeout_classification")
        == "missing_required_evidence"
        and closeout_buckets["statistical_deflated_sharpe"].get("closeout_classification")
        == "missing_required_evidence"
        and closeout_buckets["statistical_multiple_testing"].get("closeout_classification")
        == "missing_required_evidence"
        and closeout_buckets["statistical_probabilistic_sharpe"].get(
            "closeout_classification"
        )
        == "terminal_fail"
        and closeout_buckets["stability_regime_breakdowns"].get("closeout_classification")
        == "not_actionable_for_current_line",
        failure="alpha completion closeout does not preserve diagnostic-only and fail-closed classifications",
        evidence=[ALPHA_COMPLETION_CLOSEOUT.as_posix()],
        details={"bucket_dispositions": {key: dict(value) for key, value in closeout_buckets.items()}},
    )

    wfa = payloads.get("wfa_split_contamination")
    wfa_non_approval = wfa.get("non_approval") if isinstance(wfa, Mapping) else {}
    wfa_non_approval = wfa_non_approval if isinstance(wfa_non_approval, Mapping) else {}
    check(
        checks,
        failures,
        name="wfa_split_contamination_remains_research_only",
        passed=wfa is not None
        and wfa.get("status") == "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD"
        and dotted_get(wfa, "summary.classification") == "same_fold_rolling_retraining_research_only"
        and dotted_get(wfa, "summary.failure_count") == 0
        and dotted_get(wfa, "summary.warning_count") == 2
        and dotted_get(wfa, "summary.model_trust_ready") is False
        and dotted_get(wfa, "summary.valid_for_independent_holdout_claims") is False
        and dotted_get(wfa, "summary.valid_for_same_fold_rolling_retraining_research_evidence")
        is True
        and all(value is False for value in wfa_non_approval.values()),
        failure="WFA split-contamination evidence is not preserved as research-only",
        evidence=[WFA_SPLIT_CONTAMINATION.as_posix()],
        details={
            "summary": wfa.get("summary") if isinstance(wfa, Mapping) else None,
            "non_approval": dict(wfa_non_approval),
        },
    )

    run_status = payloads.get("run_status")
    check(
        checks,
        failures,
        name="run_status_preserves_closed_line_and_forbidden_actions",
        passed=run_status is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and dotted_get(run_status, "summary.current_line_classification") == "closed_no_alpha_evidence"
        and dotted_get(run_status, "summary.current_split_classification")
        == "same_fold_rolling_retraining_research_only"
        and dotted_get(run_status, "summary.data_model_commands_executed") is False
        and dotted_get(run_status, "summary.wfa_modeling_executed") is False
        and dotted_get(run_status, "summary.predictions_executed") is False
        and dotted_get(run_status, "summary.provider_network_calls_executed") is False
        and dotted_get(run_status, "summary.promotion_or_freeze_or_holdout_executed") is False
        and dotted_get(run_status, "summary.paper_or_live_executed") is False,
        failure="run status does not preserve closed-line and non-execution evidence",
        evidence=[RUN_STATUS.as_posix()],
        details={"summary": run_status.get("summary") if isinstance(run_status, Mapping) else None},
    )

    adversarial_terms = text_contains(
        resolve_path(repo_root, ADVERSARIAL_AUDIT),
        (
            "no complete current-scope trial log",
            "probabilistic sharpe",
            "regime breakdowns fail",
            "blocked for trading and alpha acceptance",
        ),
    )
    check(
        checks,
        failures,
        name="adversarial_audit_preserves_statistical_blockers",
        passed=all(adversarial_terms.values()),
        failure="adversarial audit does not preserve required statistical blocker statements",
        evidence=[ADVERSARIAL_AUDIT.as_posix()],
        details={"term_presence": adversarial_terms},
    )

    check(
        checks,
        failures,
        name="non_approval_flags_all_false",
        passed=all(value is False for value in NON_APPROVAL.values()),
        failure="one or more statistical partial reconciliation non-approval flags is true",
        details={"non_approval": dict(NON_APPROVAL)},
    )

    for item in input_evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "bootstrap_ci_diagnostic_pass": bootstrap.get("status") == "PASS",
        "parameter_stability_diagnostic_pass": stability.get("status") == "PASS",
        "bootstrap_ci_sample_count": bootstrap.get("sample_count"),
        "bootstrap_ci_csv_row_count": len(bootstrap_rows),
        "stability_matrix_row_count": len(stability_rows),
        "stability_matrix_scopes": sorted(str(item) for item in stability_scopes),
        "pbo_status": pbo.get("status"),
        "deflated_sharpe_status": deflated.get("status"),
        "multiple_testing_status": multiple.get("status"),
        "probabilistic_sharpe_status": psr.get("status"),
        "regime_breakdowns_status": regime.get("status"),
        "gap_statistical_check_statuses": {
            key: row.get("status") for key, row in gap_stat_checks.items()
        },
        "wfa_split_classification": dotted_get(wfa, "summary.classification"),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "stat-partial-001-diagnostic-subpasses-accepted",
            "severity": "Info",
            "finding": "Bootstrap confidence intervals and parameter stability are accepted only as diagnostic sub-evidence.",
            "verified_facts": [
                f"bootstrap_ci_diagnostic_pass={derived.get('bootstrap_ci_diagnostic_pass')}",
                f"bootstrap_ci_sample_count={derived.get('bootstrap_ci_sample_count')}",
                f"parameter_stability_diagnostic_pass={derived.get('parameter_stability_diagnostic_pass')}",
                f"stability_matrix_scopes={derived.get('stability_matrix_scopes')}",
            ],
            "limitation": "This does not clear any full Master Audit statistical-validity check.",
            "evidence_paths": [STATISTICAL_SUMMARY.as_posix(), BOOTSTRAP_CI.as_posix(), STABILITY_MATRIX.as_posix()],
        },
        {
            "finding_id": "stat-partial-002-overfit-and-regime-blockers-preserved",
            "severity": "High",
            "finding": "Trial-log-dependent, PSR, and regime blockers remain unresolved.",
            "verified_facts": [
                f"pbo_status={derived.get('pbo_status')}",
                f"deflated_sharpe_status={derived.get('deflated_sharpe_status')}",
                f"multiple_testing_status={derived.get('multiple_testing_status')}",
                f"probabilistic_sharpe_status={derived.get('probabilistic_sharpe_status')}",
                f"regime_breakdowns_status={derived.get('regime_breakdowns_status')}",
            ],
            "limitation": "PBO, Deflated Sharpe, and multiple testing need complete search-path evidence.",
            "evidence_paths": [STATISTICAL_SUMMARY.as_posix(), ALPHA_COMPLETION_CLOSEOUT.as_posix()],
        },
        {
            "finding_id": "stat-partial-003-research-only-split-preserved",
            "severity": "High",
            "finding": "WFA split evidence remains same-fold rolling-retraining research-only.",
            "verified_facts": [
                f"wfa_split_classification={derived.get('wfa_split_classification')}",
            ],
            "limitation": "This is not independent holdout evidence or model-trust evidence.",
            "evidence_paths": [WFA_SPLIT_CONTAMINATION.as_posix()],
        },
        {
            "finding_id": "stat-partial-004-no-readiness-upgrade",
            "severity": "Info",
            "finding": "Statistical validity, model trust, promotion, paper/live, and production remain blocked.",
            "verified_facts": ["All non-approval flags in this report are false."],
            "limitation": "This report is evidence reconciliation only.",
            "evidence_paths": [GAP_MAP_AFTER_PHASE2.as_posix()],
        },
    ]


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_input_overrides: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = resolve_path(repo_root, reports_root).resolve()
    paths = dict(REQUIRED_INPUTS)
    if required_input_overrides:
        paths.update(required_input_overrides)
    if git_status_lines is None:
        git_status = inventory.collect_git_status(repo_root)
        status_lines = list(git_status["status_lines"])
        git_error = git_status["error"]
        git_returncode = git_status["returncode"]
    else:
        status_lines = list(git_status_lines)
        git_error = None
        git_returncode = 0
    dirty_map = inventory.build_dirty_path_map(status_lines)
    input_evidence = evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    output_rel = rel(reports_root, repo_root)
    checks, check_failures, derived = build_checks(
        repo_root=repo_root,
        payloads=payloads,
        input_evidence=input_evidence,
        output_rel=output_rel,
        paths=paths,
    )
    failures = input_failures + check_failures
    status = PASS_STATUS if not failures else FAIL_STATUS
    findings = build_findings(derived)
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_statistical_validity_partial_reconciliation_report_only",
            "target_gap_area": "statistical_validity",
            "accepted_sub_evidence": [
                "statistical_bootstrap_ci",
                "stability_parameter",
            ],
            "reports_root": output_rel,
            "evidence_mode": "existing_local_json_csv_md_repo_evidence_only",
            "data_model_scope": "none",
            "provider_scope": "none",
            "allowed_inputs": [
                rel(resolve_path(repo_root, path), repo_root) for path in paths.values()
            ],
        },
        "summary": {
            "status": status,
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "statistical_validity_partial_reconciliation_ready": status == PASS_STATUS,
            "bootstrap_ci_diagnostic_pass": derived.get("bootstrap_ci_diagnostic_pass"),
            "parameter_stability_diagnostic_pass": derived.get(
                "parameter_stability_diagnostic_pass"
            ),
            "bootstrap_ci_sample_count": derived.get("bootstrap_ci_sample_count"),
            "bootstrap_ci_csv_row_count": derived.get("bootstrap_ci_csv_row_count"),
            "stability_matrix_row_count": derived.get("stability_matrix_row_count"),
            "stability_matrix_scopes": derived.get("stability_matrix_scopes"),
            "pbo_status": derived.get("pbo_status"),
            "deflated_sharpe_status": derived.get("deflated_sharpe_status"),
            "multiple_testing_status": derived.get("multiple_testing_status"),
            "probabilistic_sharpe_status": derived.get("probabilistic_sharpe_status"),
            "regime_breakdowns_status": derived.get("regime_breakdowns_status"),
            "gap_statistical_check_statuses": derived.get("gap_statistical_check_statuses"),
            "data_integrity_ready": True,
            "statistical_validity_ready": False,
            "statistical_validity_master_audit_accepted": False,
            "full_master_audit_statistical_check_ready": False,
            "operational_resilience_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
            **dict(NON_APPROVAL),
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
            "finding_counts": finding_counts(findings),
        },
        "input_evidence": input_evidence,
        "checks": checks,
        "findings": findings,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "after-Phase-2 gap map has data_integrity PASS while statistical_validity and operational_resilience remain FAIL",
                "statistical summary remains FAIL with exact current prediction/trade/failure counts",
                "bootstrap confidence intervals are PASS with 500 samples and net_return_dollars CSV evidence",
                "parameter stability is PASS with market/year/fold stability CSV evidence",
                "PBO, Deflated Sharpe, and multiple testing remain missing trial-log evidence",
                "Probabilistic Sharpe and regime breakdowns remain FAIL",
                "alpha matrix and closeout classify bootstrap and parameter stability as diagnostic-only PASS",
                "WFA split evidence remains same-fold rolling-retraining research-only",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "any statistical sub-failure is silently upgraded",
                "bootstrap or stability diagnostic PASS evidence is absent",
                "full statistical-validity, model-trust, promotion, paper/live, or production readiness is upgraded",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan a trial-ledger/search-path completeness reconciliation for PBO, "
            "Deflated Sharpe, and multiple-testing applicability using existing "
            "registry/ledger evidence only."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Statistical-Validity Partial Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Bootstrap CI diagnostic PASS: `{summary['bootstrap_ci_diagnostic_pass']}`",
        f"- Parameter stability diagnostic PASS: `{summary['parameter_stability_diagnostic_pass']}`",
        f"- PBO status: `{summary['pbo_status']}`",
        f"- Deflated Sharpe status: `{summary['deflated_sharpe_status']}`",
        f"- Multiple-testing status: `{summary['multiple_testing_status']}`",
        f"- Probabilistic Sharpe status: `{summary['probabilistic_sharpe_status']}`",
        f"- Regime breakdowns status: `{summary['regime_breakdowns_status']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Failure |",
        "| --- | --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(
            "| `{name}` | `{status}` | {failure} |".format(
                name=item["name"],
                status=item["status"],
                failure=item.get("failure") or "",
            )
        )
    lines.extend(["", "## Findings", ""])
    for item in report["findings"]:
        lines.append(
            "- `{severity}` `{finding_id}`: {finding}".format(
                severity=item["severity"],
                finding_id=item["finding_id"],
                finding=item["finding"],
            )
        )
    lines.extend(["", "## Evidence Inputs", ""])
    for item in report.get("input_evidence", []):
        lines.append(
            "- `{path}` exists=`{exists}` state=`{state}` git=`{git}` sha256=`{sha}`".format(
                path=item.get("path"),
                exists=item.get("exists"),
                state=item.get("state"),
                git=item.get("git_status"),
                sha=item.get("sha256"),
            )
        )
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This reconciliation did not run data/model commands, WFA/modeling, predictions, Phase 8 refresh, statistical-validity generation, alpha matrix generation, gap-map generation, provider/network calls, promotion, artifact freeze, final holdout, paper/live, cleanup, staging, commit, or push.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / REPORT_JSON
    md_path = reports_root / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(repo_root=repo_root, reports_root=reports_root)
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"bootstrap_ci_diagnostic_pass={report['summary']['bootstrap_ci_diagnostic_pass']} "
        f"parameter_stability_diagnostic_pass={report['summary']['parameter_stability_diagnostic_pass']} "
        f"statistical_validity_ready={report['summary']['statistical_validity_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
