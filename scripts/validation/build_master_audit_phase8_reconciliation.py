#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 8 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run
Phase 8 evaluation, WFA/modeling, prediction generation, rebuild data, read
parquet/model artifacts, call providers/network, promote, freeze, touch holdout,
paper/live, clean up files, stage, commit, or push.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_phase8_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE8_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE8_RECONCILIATION_REPORT_ONLY"

RUN_ID = "tier1_core_phase6_full_predictions_20260706"
EXPECTED_PROFILE = "tier_1_core"
EXPECTED_RESOLVED_PROFILE = "tier_1_research"
EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_FOLD_COUNT = 48
EXPECTED_STATISTICAL_FAILURES = (
    "pbo",
    "deflated_sharpe",
    "probabilistic_sharpe",
    "multiple_testing_adjustment",
    "regime_breakdowns",
)

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_PHASE1B = Path(
    "reports/master_audit/master_audit_phase1b_reconciliation_20260709/"
    "master_audit_phase1b_reconciliation.json"
)
DEFAULT_PHASE2 = Path(
    "reports/master_audit/master_audit_phase2_reconciliation_20260709/"
    "master_audit_phase2_reconciliation.json"
)
DEFAULT_PHASE3 = Path(
    "reports/master_audit/master_audit_phase3_reconciliation_20260709/"
    "master_audit_phase3_reconciliation.json"
)
DEFAULT_PHASE4 = Path(
    "reports/master_audit/master_audit_phase4_reconciliation_20260709/"
    "master_audit_phase4_reconciliation.json"
)
DEFAULT_PHASE5 = Path(
    "reports/master_audit/master_audit_phase5_reconciliation_20260709/"
    "master_audit_phase5_reconciliation.json"
)
DEFAULT_PHASE6 = Path(
    "reports/master_audit/master_audit_phase6_reconciliation_20260709/"
    "master_audit_phase6_reconciliation.json"
)
DEFAULT_PHASE7 = Path(
    "reports/master_audit/master_audit_phase7_reconciliation_20260709/"
    "master_audit_phase7_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase8_reconciliation_20260709")
REPORT_JSON = "master_audit_phase8_reconciliation.json"
REPORT_MD = "master_audit_phase8_reconciliation.md"

PHASE8_DECISION = Path(f"reports/phase8/{RUN_ID}/alpha_promotion_decision.json")
PHASE8_METRICS = Path(f"reports/phase8/{RUN_ID}/metrics.json")
FAILURE_ANALYSIS = Path(f"reports/failure_analysis/{RUN_ID}/failure_analysis_summary.json")
STATISTICAL_VALIDITY = Path(
    f"reports/statistical_validity/{RUN_ID}/statistical_validity_summary.json"
)
PREDICTION_DIAGNOSTICS = Path(
    f"reports/prediction_diagnostics/{RUN_ID}/prediction_diagnostics_summary.json"
)
PREDICTION_AUDIT = Path(f"reports/prediction_audit/{RUN_ID}/prediction_audit_summary.json")

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "phase1b_reconciliation": DEFAULT_PHASE1B,
    "phase2_reconciliation": DEFAULT_PHASE2,
    "phase3_reconciliation": DEFAULT_PHASE3,
    "phase4_reconciliation": DEFAULT_PHASE4,
    "phase5_reconciliation": DEFAULT_PHASE5,
    "phase6_reconciliation": DEFAULT_PHASE6,
    "phase7_reconciliation": DEFAULT_PHASE7,
    "phase8_decision": PHASE8_DECISION,
    "phase8_metrics": PHASE8_METRICS,
    "failure_analysis": FAILURE_ANALYSIS,
    "statistical_validity": STATISTICAL_VALIDITY,
    "prediction_diagnostics": PREDICTION_DIAGNOSTICS,
    "prediction_audit": PREDICTION_AUDIT,
}

EXPECTED_RECONCILIATION_STATUSES = {
    "phase1b_reconciliation": "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY",
    "phase2_reconciliation": "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY",
    "phase3_reconciliation": "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY",
    "phase4_reconciliation": "PASS_MASTER_AUDIT_PHASE4_RECONCILIATION_REPORT_ONLY",
    "phase5_reconciliation": "PASS_MASTER_AUDIT_PHASE5_RECONCILIATION_REPORT_ONLY",
    "phase6_reconciliation": "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY",
    "phase7_reconciliation": "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase8_evaluation_executed": False,
    "phase8_refresh_executed": False,
    "phase1b_conversion_executed": False,
    "phase2_build_or_readiness_executed": False,
    "phase3_label_build_executed": False,
    "phase4_feature_build_executed": False,
    "phase5_split_build_executed": False,
    "phase6_runner_executed": False,
    "phase7_audit_rerun_executed": False,
    "data_model_commands_executed": False,
    "dbn_read_executed": False,
    "raw_parquet_read_executed": False,
    "causal_parquet_read_executed": False,
    "label_parquet_read_executed": False,
    "feature_parquet_read_executed": False,
    "prediction_parquet_read_executed": False,
    "model_artifact_read_executed": False,
    "wfa_modeling_executed": False,
    "prediction_generation_executed": False,
    "prediction_materialization_executed": False,
    "predictions_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "freeze_executed": False,
    "holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "staging_commit_push_executed": False,
    "hardened_split_candidate_consumed": False,
    "hardened_phase6_materialization_path_consumed": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def list_as_set(value: Any) -> set[Any]:
    return set(as_list(value))


def row_by_area(run_status: Mapping[str, Any] | None, area: str) -> Mapping[str, Any] | None:
    rows = dotted_get(run_status, "run_status_table")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("audit_area") == area:
            return row
    return None


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


def required_input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields: dict[str, dict[str, str]] = {
        "run_status": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
        },
        "overview": {"status": "status", "failure_count": "summary.failure_count"},
        "phase1b_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase2_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase3_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase4_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase5_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase5_master_audit_status": "summary.phase5_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase6_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase6_master_audit_status": "summary.phase6_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase7_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase7_master_audit_status": "summary.phase7_master_audit_status",
            "prediction_count": "summary.prediction_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase8_decision": {
            "run": "run",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "promoted": "promoted",
            "research_alpha_ready": "research_alpha_ready",
            "model_promotion_allowed": "model_promotion_allowed",
            "final_holdout_touched": "final_holdout_touched",
            "used_final_holdout_for_tuning": "used_final_holdout_for_tuning",
            "promotion_blocker_count": "promotion_gate.promotion_blocker_count",
            "promotion_metric_gate_status": "promotion_metric_gate.status",
            "statistical_validity_gate_status": "statistical_validity_gate.status",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "phase8_metrics": {
            "run": "run",
            "prediction_count": "prediction_count",
            "policy_row_count": "policy_row_count",
            "research_policy_metrics_ready": "research_policy_metrics_ready",
            "research_alpha_ready": "research_alpha_ready",
            "model_promotion_allowed": "model_promotion_allowed",
            "final_holdout_touched": "final_holdout_touched",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "failure_analysis": {
            "status": "status",
            "run": "run",
            "prediction_count": "prediction_count",
            "policy_row_count": "policy_row_count",
            "failure_count": "failure_count",
            "model_promotion_allowed": "model_promotion_allowed",
        },
        "statistical_validity": {
            "status": "status",
            "run": "run",
            "prediction_count": "prediction_count",
            "policy_trade_count": "policy_trade_count",
            "failure_count": "failure_count",
            "model_promotion_allowed": "model_promotion_allowed",
        },
        "prediction_diagnostics": {
            "status": "status",
            "run": "run",
            "prediction_count": "prediction_count",
            "failure_count": "failure_count",
            "failure_labels": "failure_labels",
        },
        "prediction_audit": {
            "status": "status",
            "run": "run",
            "prediction_count": "prediction_count",
            "failure_count": "failure_count",
            "phase7_prediction_audit_ready": "phase7_prediction_audit_ready",
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
    for name, path in paths.items():
        resolved = resolve_path(repo_root, path)
        if resolved.suffix.lower() != ".json":
            continue
        payload, error = read_json_object(resolved)
        if error:
            failures.append(f"required JSON input unavailable: {path.as_posix()} ({error})")
        elif payload is not None:
            payloads[name] = payload
    return payloads, failures


def market_set(phase8_decision: Mapping[str, Any]) -> set[str]:
    markets = phase8_decision.get("markets")
    if not isinstance(markets, list):
        return set()
    values: set[str] = set()
    for item in markets:
        if isinstance(item, Mapping) and isinstance(item.get("market"), str):
            values.add(str(item["market"]))
        elif isinstance(item, str):
            values.add(item)
    return values


def classification_set(failure_analysis: Mapping[str, Any]) -> set[str]:
    rows = failure_analysis.get("failure_classifications")
    values: set[str] = set()
    for item in as_list(rows):
        if isinstance(item, Mapping) and isinstance(item.get("classification"), str):
            values.add(str(item["classification"]))
        elif isinstance(item, str):
            values.add(item)
    return values


def previous_reconciliation_statuses(
    payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for name in EXPECTED_RECONCILIATION_STATUSES:
        payload = payloads.get(name, {})
        statuses[name] = {
            "status": payload.get("status"),
            "failure_count": dotted_get(payload, "summary.failure_count"),
            "model_trust_ready": dotted_get(payload, "summary.model_trust_ready"),
            "promotion_allowed": dotted_get(payload, "summary.promotion_allowed"),
            "holdout_allowed": dotted_get(payload, "summary.holdout_allowed"),
            "paper_live_allowed": dotted_get(payload, "summary.paper_live_allowed"),
        }
    return statuses


def statistical_failures(statistical_validity: Mapping[str, Any]) -> list[str]:
    return [str(item) for item in as_list(statistical_validity.get("failures"))]


def has_statistical_failure_labels(failures: Sequence[str]) -> bool:
    text = "\n".join(failures).lower()
    return all(label.lower() in text for label in EXPECTED_STATISTICAL_FAILURES)


def build_checks(
    *,
    payloads: Mapping[str, Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    output_rel: str,
    paths: Mapping[str, Path],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {str(item.get("path")) for item in evidence if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required Phase 8 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 8 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    previous_statuses = previous_reconciliation_statuses(payloads)
    previous_status_pass = all(
        payloads.get(name, {}).get("status") == expected
        and dotted_get(payloads.get(name), "summary.failure_count") == 0
        and dotted_get(payloads.get(name), "summary.model_trust_ready") is False
        and dotted_get(payloads.get(name), "summary.promotion_allowed") is False
        for name, expected in EXPECTED_RECONCILIATION_STATUSES.items()
    )
    check(
        checks,
        failures,
        name="master_audit_inputs_are_passed_report_only_evidence",
        passed=run_status is not None
        and overview is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and previous_status_pass,
        failure="run-status, overview, or Phase 1B-7 reconciliation inputs are not passed report-only blocking evidence",
        evidence=[
            DEFAULT_RUN_STATUS.as_posix(),
            DEFAULT_OVERVIEW.as_posix(),
            DEFAULT_PHASE1B.as_posix(),
            DEFAULT_PHASE2.as_posix(),
            DEFAULT_PHASE3.as_posix(),
            DEFAULT_PHASE4.as_posix(),
            DEFAULT_PHASE5.as_posix(),
            DEFAULT_PHASE6.as_posix(),
            DEFAULT_PHASE7.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "previous_reconciliation_statuses": previous_statuses,
        },
    )

    phase8_row = row_by_area(run_status, "Phase 8")
    check(
        checks,
        failures,
        name="phase8_ledger_row_is_current_failing_evidence",
        passed=phase8_row is not None
        and phase8_row.get("run_status") == "RUN"
        and phase8_row.get("detail_status") == "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE"
        and phase8_row.get("evidence_state") == "current",
        failure="run-status Phase 8 row is not RUN_FAILING_ALPHA_PROMOTION_EVIDENCE/current",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"phase8_row": dict(phase8_row or {})},
    )

    phase8 = payloads.get("phase8_decision", {})
    phase8_metrics = payloads.get("phase8_metrics", {})
    failure_analysis = payloads.get("failure_analysis", {})
    statistical_validity = payloads.get("statistical_validity", {})
    prediction_diagnostics = payloads.get("prediction_diagnostics", {})
    prediction_audit = payloads.get("prediction_audit", {})
    phase7 = payloads.get("phase7_reconciliation", {})

    blocker_count = as_int(dotted_get(phase8, "promotion_gate.promotion_blocker_count"))
    top_level_blocker_count = len(as_list(phase8.get("blockers")))
    folds = as_list(phase8.get("folds"))
    markets = market_set(phase8)
    costed_oos = as_mapping(phase8.get("costed_oos"))
    gross_return = as_number(costed_oos.get("gross_return_dollars"))
    net_return = as_number(costed_oos.get("net_return_dollars"))
    cost_dollars = as_number(costed_oos.get("cost_dollars"))
    profit_factor = as_number(costed_oos.get("profit_factor"))

    check(
        checks,
        failures,
        name="phase8_decision_preserves_negative_non_approval",
        passed=phase8.get("run") == RUN_ID
        and phase8.get("profile") == EXPECTED_PROFILE
        and phase8.get("resolved_profile") == EXPECTED_RESOLVED_PROFILE
        and phase8.get("promoted") is False
        and phase8.get("research_alpha_ready") is False
        and phase8.get("model_promotion_allowed") is False
        and phase8.get("final_holdout_touched") is False
        and phase8.get("used_final_holdout_for_tuning") is False
        and dotted_get(phase8, "promotion_gate.research_alpha_ready") is False
        and dotted_get(phase8, "promotion_gate.model_promotion_allowed") is False
        and blocker_count == 30
        and top_level_blocker_count == 30
        and dotted_get(phase8, "promotion_metric_gate.status") == "FAIL"
        and dotted_get(phase8, "statistical_validity_gate.status") == "FAIL"
        and phase8.get("failure_count") == 0
        and phase8.get("warning_count") == 0,
        failure="Phase 8 alpha decision no longer preserves the expected non-approval/failing-promotion evidence",
        evidence=[PHASE8_DECISION.as_posix()],
        details={
            "run": phase8.get("run"),
            "profile": phase8.get("profile"),
            "resolved_profile": phase8.get("resolved_profile"),
            "promoted": phase8.get("promoted"),
            "research_alpha_ready": phase8.get("research_alpha_ready"),
            "model_promotion_allowed": phase8.get("model_promotion_allowed"),
            "final_holdout_touched": phase8.get("final_holdout_touched"),
            "used_final_holdout_for_tuning": phase8.get("used_final_holdout_for_tuning"),
            "promotion_blocker_count": blocker_count,
            "top_level_blocker_count": top_level_blocker_count,
            "promotion_metric_gate_status": dotted_get(phase8, "promotion_metric_gate.status"),
            "statistical_validity_gate_status": dotted_get(
                phase8, "statistical_validity_gate.status"
            ),
        },
    )

    check(
        checks,
        failures,
        name="phase8_scope_matches_tier1_core_report",
        passed=len(folds) == EXPECTED_FOLD_COUNT
        and markets == set(EXPECTED_MARKETS)
        and list_as_set(dotted_get(phase7, "scope.markets")) == set(EXPECTED_MARKETS)
        and list_as_set(dotted_get(phase7, "scope.years")) == set(EXPECTED_YEARS),
        failure="Phase 8 scope does not reconcile to Tier 1 core 6E/CL/ES/ZN 2023/2024 with 48 folds",
        evidence=[PHASE8_DECISION.as_posix(), DEFAULT_PHASE7.as_posix()],
        details={
            "phase8_fold_count": len(folds),
            "phase8_markets": sorted(markets),
            "phase7_scope_markets": dotted_get(phase7, "scope.markets"),
            "phase7_scope_years": dotted_get(phase7, "scope.years"),
        },
    )

    phase7_prediction_count = dotted_get(phase7, "summary.prediction_count")
    check(
        checks,
        failures,
        name="phase8_metrics_json_reconciles_to_decision_and_phase7",
        passed=phase8_metrics.get("run") == RUN_ID
        and phase8_metrics.get("failure_count") == 0
        and phase8_metrics.get("research_policy_metrics_ready") is True
        and phase8_metrics.get("research_alpha_ready") is False
        and phase8_metrics.get("model_promotion_allowed") is False
        and phase8_metrics.get("final_holdout_touched") is False
        and as_int(phase8_metrics.get("prediction_count")) == as_int(phase7_prediction_count)
        and as_int(phase8_metrics.get("policy_row_count"))
        == as_int(failure_analysis.get("policy_row_count")),
        failure="Phase 8 metrics JSON does not reconcile to the alpha decision/Phase 7 evidence",
        evidence=[PHASE8_METRICS.as_posix(), DEFAULT_PHASE7.as_posix(), FAILURE_ANALYSIS.as_posix()],
        details={
            "run": phase8_metrics.get("run"),
            "prediction_count": phase8_metrics.get("prediction_count"),
            "phase7_prediction_count": phase7_prediction_count,
            "policy_row_count": phase8_metrics.get("policy_row_count"),
            "failure_analysis_policy_row_count": failure_analysis.get("policy_row_count"),
            "research_policy_metrics_ready": phase8_metrics.get("research_policy_metrics_ready"),
            "research_alpha_ready": phase8_metrics.get("research_alpha_ready"),
            "model_promotion_allowed": phase8_metrics.get("model_promotion_allowed"),
            "final_holdout_touched": phase8_metrics.get("final_holdout_touched"),
        },
    )

    check(
        checks,
        failures,
        name="costed_oos_economics_remain_negative",
        passed=gross_return is not None
        and gross_return < 0
        and net_return is not None
        and net_return < 0
        and cost_dollars is not None
        and cost_dollars > 0
        and profit_factor is not None
        and profit_factor < 1.0,
        failure="costed OOS economics no longer preserve the expected negative/non-promotable evidence",
        evidence=[PHASE8_DECISION.as_posix()],
        details={
            "gross_return_dollars": gross_return,
            "net_return_dollars": net_return,
            "cost_dollars": cost_dollars,
            "profit_factor": profit_factor,
            "trade_count": costed_oos.get("trade_count"),
        },
    )

    classifications = classification_set(failure_analysis)
    check(
        checks,
        failures,
        name="failure_analysis_is_diagnostic_only_negative_evidence",
        passed=failure_analysis.get("status") == "PASS"
        and failure_analysis.get("run") == RUN_ID
        and failure_analysis.get("failure_count") == 0
        and failure_analysis.get("failure_analysis_ready") is True
        and failure_analysis.get("diagnostic_only") is True
        and failure_analysis.get("research_only") is True
        and failure_analysis.get("model_promotion_allowed") is False
        and {"gross_edge_absent", "baseline_failure", "cost_stress_failure"}.issubset(
            classifications
        ),
        failure="failure-analysis evidence is not diagnostic-only negative evidence with expected classifications",
        evidence=[FAILURE_ANALYSIS.as_posix()],
        details={
            "status": failure_analysis.get("status"),
            "failure_count": failure_analysis.get("failure_count"),
            "failure_analysis_ready": failure_analysis.get("failure_analysis_ready"),
            "diagnostic_only": failure_analysis.get("diagnostic_only"),
            "research_only": failure_analysis.get("research_only"),
            "model_promotion_allowed": failure_analysis.get("model_promotion_allowed"),
            "failure_classifications": sorted(classifications),
            "top_findings": failure_analysis.get("top_findings"),
        },
    )

    stat_failures = statistical_failures(statistical_validity)
    check(
        checks,
        failures,
        name="statistical_validity_failure_is_preserved_as_blocker",
        passed=statistical_validity.get("status") == "FAIL"
        and statistical_validity.get("run") == RUN_ID
        and statistical_validity.get("statistical_validity_ready") is False
        and statistical_validity.get("failure_count") == 5
        and statistical_validity.get("research_only") is True
        and statistical_validity.get("model_promotion_allowed") is False
        and has_statistical_failure_labels(stat_failures),
        failure="statistical-validity evidence does not preserve the expected five blocking failures",
        evidence=[STATISTICAL_VALIDITY.as_posix()],
        details={
            "status": statistical_validity.get("status"),
            "failure_count": statistical_validity.get("failure_count"),
            "statistical_validity_ready": statistical_validity.get("statistical_validity_ready"),
            "research_only": statistical_validity.get("research_only"),
            "model_promotion_allowed": statistical_validity.get("model_promotion_allowed"),
            "failures": stat_failures,
        },
    )

    check(
        checks,
        failures,
        name="prediction_audit_and_diagnostics_preserve_limited_evidence",
        passed=prediction_audit.get("status") == "PASS"
        and prediction_audit.get("run") == RUN_ID
        and prediction_audit.get("phase7_prediction_audit_ready") is True
        and prediction_audit.get("failure_count") == 0
        and prediction_diagnostics.get("status") == "PREDICTION_DIAGNOSTICS_READY"
        and prediction_diagnostics.get("run") == RUN_ID
        and prediction_diagnostics.get("failure_count") == 0
        and "weak_signal" in as_list(prediction_diagnostics.get("failure_labels")),
        failure="prediction audit/diagnostics are not the expected limited weak-signal evidence",
        evidence=[PREDICTION_AUDIT.as_posix(), PREDICTION_DIAGNOSTICS.as_posix()],
        details={
            "prediction_audit_status": prediction_audit.get("status"),
            "phase7_prediction_audit_ready": prediction_audit.get(
                "phase7_prediction_audit_ready"
            ),
            "prediction_diagnostics_status": prediction_diagnostics.get("status"),
            "failure_labels": prediction_diagnostics.get("failure_labels"),
        },
    )

    blocker_details = {
        "phase8_promoted": phase8.get("promoted"),
        "phase8_research_alpha_ready": phase8.get("research_alpha_ready"),
        "phase8_model_promotion_allowed": phase8.get("model_promotion_allowed"),
        "phase8_final_holdout_touched": phase8.get("final_holdout_touched"),
        "phase8_used_final_holdout_for_tuning": phase8.get("used_final_holdout_for_tuning"),
        "statistical_validity_status": statistical_validity.get("status"),
        "previous_reconciliation_statuses": previous_statuses,
    }
    check(
        checks,
        failures,
        name="model_trust_promotion_holdout_paper_live_remain_blocked",
        passed=phase8.get("promoted") is False
        and phase8.get("research_alpha_ready") is False
        and phase8.get("model_promotion_allowed") is False
        and phase8.get("final_holdout_touched") is False
        and phase8.get("used_final_holdout_for_tuning") is False
        and statistical_validity.get("status") == "FAIL"
        and all(row["model_trust_ready"] is False for row in previous_statuses.values())
        and all(row["promotion_allowed"] is False for row in previous_statuses.values()),
        failure="model-trust, promotion, holdout, paper/live, or upstream blocking status was unexpectedly upgraded",
        evidence=[PHASE8_DECISION.as_posix(), STATISTICAL_VALIDITY.as_posix()],
        details=blocker_details,
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "previous_reconciliation_statuses": previous_statuses,
        "phase8_row": dict(phase8_row or {}),
        "markets": sorted(markets),
        "fold_count": len(folds),
        "prediction_count": phase8_metrics.get("prediction_count"),
        "policy_row_count": phase8_metrics.get("policy_row_count"),
        "policy_trade_count": statistical_validity.get("policy_trade_count"),
        "promotion_blocker_count": blocker_count,
        "top_level_blocker_count": top_level_blocker_count,
        "promotion_metric_failure_count": dotted_get(phase8, "promotion_metric_gate.failure_count"),
        "statistical_validity_gate_failure_count": dotted_get(
            phase8, "statistical_validity_gate.failure_count"
        ),
        "statistical_validity_failure_count": statistical_validity.get("failure_count"),
        "statistical_validity_failures": stat_failures,
        "failure_classifications": sorted(classifications),
        "costed_oos": {
            "gross_return_dollars": gross_return,
            "net_return_dollars": net_return,
            "cost_dollars": cost_dollars,
            "profit_factor": profit_factor,
            "trade_count": costed_oos.get("trade_count"),
        },
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    costed_oos = as_mapping(derived.get("costed_oos"))
    return [
        {
            "finding_id": "phase8-001-failing-promotion-decision-reconciled",
            "severity": "Info",
            "finding": "Existing Phase 8 alpha promotion decision is accepted as completed negative promotion evidence.",
            "verified_facts": [
                f"run={RUN_ID}",
                f"fold_count={derived.get('fold_count')}",
                f"promotion_blocker_count={derived.get('promotion_blocker_count')}",
                f"promotion_metric_failure_count={derived.get('promotion_metric_failure_count')}",
            ],
            "limitation": "This report does not rerun Phase 8 or upgrade the run to model-trust evidence.",
            "evidence_paths": [PHASE8_DECISION.as_posix(), PHASE8_METRICS.as_posix()],
        },
        {
            "finding_id": "phase8-002-costed-oos-economics-block-promotion",
            "severity": "Critical",
            "finding": "Costed OOS economics remain negative and block promotion.",
            "verified_facts": [
                f"gross_return_dollars={costed_oos.get('gross_return_dollars')}",
                f"net_return_dollars={costed_oos.get('net_return_dollars')}",
                f"cost_dollars={costed_oos.get('cost_dollars')}",
                f"profit_factor={costed_oos.get('profit_factor')}",
            ],
            "limitation": "The failure-analysis PASS is diagnostic-only and does not override negative economics.",
            "evidence_paths": [PHASE8_DECISION.as_posix(), FAILURE_ANALYSIS.as_posix()],
        },
        {
            "finding_id": "phase8-003-statistical-validity-fails",
            "severity": "Critical",
            "finding": "Statistical-validity evidence remains failing and blocks model-trust/promotion.",
            "verified_facts": [
                f"statistical_validity_failure_count={derived.get('statistical_validity_failure_count')}",
                f"failures={derived.get('statistical_validity_failures')}",
            ],
            "limitation": "Existing statistical-validity evidence is report-only and must not be treated as a later shortcut around Phase 8 gates.",
            "evidence_paths": [STATISTICAL_VALIDITY.as_posix()],
        },
        {
            "finding_id": "phase8-004-full-acceptance-remains-blocked",
            "severity": "Critical",
            "finding": "Full Phase 8 Master Audit acceptance, model trust, promotion, holdout, and paper/live remain blocked.",
            "verified_facts": [
                "promoted=false",
                "research_alpha_ready=false",
                "model_promotion_allowed=false",
                "final_holdout_touched=false",
            ],
            "limitation": "Any future Phase 8 refresh or promotion path requires separate bounded approval.",
            "evidence_paths": [PHASE8_DECISION.as_posix(), DEFAULT_RUN_STATUS.as_posix()],
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
    output_rel = rel(reports_root, repo_root)
    evidence = required_input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    checks, check_failures, derived = build_checks(
        payloads=payloads,
        evidence=evidence,
        output_rel=output_rel,
        paths=paths,
    )
    failures = input_failures + check_failures
    findings = build_findings(derived)
    status = PASS_STATUS if not failures else FAIL_STATUS
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    phase8_classification = (
        "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE" if status == PASS_STATUS else "FAILED_PHASE8_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase8_reconciliation_report_only",
            "phase": "Phase 8",
            "phase_name": "Prediction evaluation, cost/backtest, and promotion gate",
            "run": RUN_ID,
            "profile": EXPECTED_PROFILE,
            "resolved_profile": EXPECTED_RESOLVED_PROFILE,
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "parquet_read_scope": "none",
            "phase_command_scope": "none",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "fold_count": EXPECTED_FOLD_COUNT,
            "full_phase8_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase8_master_audit_status": phase8_classification,
            "phase8_report_only_negative_promotion_evidence_ready": status == PASS_STATUS,
            "phase8_full_master_audit_accepted": False,
            "research_alpha_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
            "independent_holdout_evidence_ready": False,
            "run": RUN_ID,
            "markets": derived.get("markets"),
            "fold_count": derived.get("fold_count"),
            "prediction_count": derived.get("prediction_count"),
            "policy_row_count": derived.get("policy_row_count"),
            "policy_trade_count": derived.get("policy_trade_count"),
            "promotion_blocker_count": derived.get("promotion_blocker_count"),
            "promotion_metric_failure_count": derived.get("promotion_metric_failure_count"),
            "statistical_validity_gate_failure_count": derived.get(
                "statistical_validity_gate_failure_count"
            ),
            "statistical_validity_failure_count": derived.get(
                "statistical_validity_failure_count"
            ),
            "failure_classifications": derived.get("failure_classifications"),
            "costed_oos": derived.get("costed_oos"),
            "current_line_classification": dotted_get(
                payloads.get("run_status"), "summary.current_line_classification"
            ),
            "current_split_classification": dotted_get(
                payloads.get("run_status"), "summary.current_split_classification"
            ),
            **dict(NON_APPROVAL),
            "finding_counts_by_severity": finding_counts(findings),
        },
        "input_evidence": evidence,
        "previous_reconciliation_statuses": derived.get("previous_reconciliation_statuses", {}),
        "checks": checks,
        "findings": findings,
        "statistical_validity_failures": derived.get("statistical_validity_failures", []),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required JSON/MD evidence is readable",
                "run-status Phase 8 row is RUN_FAILING_ALPHA_PROMOTION_EVIDENCE/current",
                "Phase 1B/2/3/4/5/6/7 reconciliations are passed report-only blocking evidence",
                "Phase 8 alpha decision has promoted=false, research_alpha_ready=false, model_promotion_allowed=false, final_holdout_touched=false, and used_final_holdout_for_tuning=false",
                "Phase 8 scope reconciles to the Tier 1 core run with 48 folds and 6E/CL/ES/ZN markets",
                "Phase 8 metrics JSON reconciles prediction/policy counts to Phase 7 and failure-analysis evidence",
                "costed OOS economics remain negative and non-promotable",
                "failure-analysis evidence remains diagnostic-only negative evidence",
                "statistical-validity evidence remains FAIL with the five expected blocking checks",
                "model-trust, promotion, holdout, paper/live, and full Phase 8 acceptance remain blocked",
                "all forbidden action flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "run id, profile, scope, fold count, or counts mismatch",
                "Phase 8 decision is promoted, alpha-ready, model-promotion-allowed, final-holdout-touched, or used for tuning",
                "promotion/statistical-validity gates no longer fail without a separate decision",
                "costed OOS evidence no longer records negative economics",
                "failure-analysis diagnostic-only classifications are missing",
                "statistical-validity failures are missing or not FAIL",
                "any upstream reconciliation upgrades model trust or promotion",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan exactly one next bounded Master Audit area from the updated Phase 1B/2/3/4/5/6/7/8 "
            "report-only evidence; do not run data/model/phase commands without separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    costed_oos = as_mapping(summary.get("costed_oos"))
    lines = [
        "# Master Audit Phase 8 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 8 status: `{summary.get('phase8_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Run: `{summary.get('run')}`",
        f"- Fold count: `{summary.get('fold_count')}`",
        f"- Promotion blockers: `{summary.get('promotion_blocker_count')}`",
        f"- Statistical-validity failures: `{summary.get('statistical_validity_failure_count')}`",
        f"- Gross return dollars: `{costed_oos.get('gross_return_dollars')}`",
        f"- Net return dollars: `{costed_oos.get('net_return_dollars')}`",
        f"- Profit factor: `{costed_oos.get('profit_factor')}`",
        f"- Research alpha ready: `{summary.get('research_alpha_ready')}`",
        f"- Model-trust ready: `{summary.get('model_trust_ready')}`",
        f"- Promotion allowed: `{summary.get('promotion_allowed')}`",
        f"- Holdout allowed: `{summary.get('holdout_allowed')}`",
        f"- Paper/live allowed: `{summary.get('paper_live_allowed')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Failure |",
        "| --- | --- | --- |",
    ]
    for item in report.get("checks", []):
        lines.append(
            f"| {item.get('name')} | `{item.get('status')}` | {item.get('failure') or ''} |"
        )
    lines.extend(["", "## Findings", ""])
    for item in report.get("findings", []):
        lines.append(
            f"- `{item.get('severity')}` `{item.get('finding_id')}`: {item.get('finding')}"
        )
    lines.extend(["", "## Statistical Validity Failures", ""])
    failures = report.get("statistical_validity_failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
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
    report_failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in report_failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This reconciliation did not run Phase 8 evaluation, WFA/modeling, prediction generation/materialization, rebuild labels/features/splits, run phase audits, call providers/network, approve promotion, freeze artifacts, touch holdout, paper trade, live trade, clean up files, stage, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, or model artifacts, and it did not consume or advance the hardened split candidate or hardened Phase 6/7 materialization path.",
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
        f"phase8_status={report['summary']['phase8_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
