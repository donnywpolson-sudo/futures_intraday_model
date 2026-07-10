#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 9 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run
Phase 9 harnesses, statistical-validity reruns, alpha-gap rebuilds, data/model
commands, WFA/modeling, prediction generation, Phase 8 refresh, provider calls,
promotion, freeze, holdout, paper/live, cleanup, staging, commit, or push.
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
STAGE = "master_audit_phase9_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE9_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE9_RECONCILIATION_REPORT_ONLY"

RUN_ID = "tier1_core_phase6_full_predictions_20260706"
EXPECTED_BUCKET_STATUS_COUNTS = {"PASS": 6, "FAIL": 6, "MISSING_EVIDENCE": 11}
EXPECTED_CLOSEOUT_CLASSIFICATION_COUNTS = {
    "diagnostic_pass_only": 6,
    "missing_required_evidence": 11,
    "not_actionable_for_current_line": 1,
    "terminal_fail": 5,
}
EXPECTED_BUCKET_IDS = {
    "baseline_no_trade",
    "baseline_cost_only",
    "baseline_random_entry_null",
    "baseline_simple_trend",
    "baseline_simple_mean_reversion",
    "baseline_simple_carry_term_structure",
    "null_label_shuffle",
    "null_timing_shift",
    "statistical_pbo",
    "statistical_deflated_sharpe",
    "statistical_probabilistic_sharpe",
    "statistical_bootstrap_ci",
    "statistical_multiple_testing",
    "stability_parameter",
    "stability_regime_breakdowns",
    "stability_fold_market_year_session",
    "execution_cost_stress",
    "execution_delay_stress",
    "execution_turnover",
    "execution_capacity",
    "execution_liquidity_window",
    "execution_spread_slippage",
    "execution_partial_fills_rejects",
}
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
DEFAULT_PHASE8 = Path(
    "reports/master_audit/master_audit_phase8_reconciliation_20260709/"
    "master_audit_phase8_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase9_reconciliation_20260709")
REPORT_JSON = "master_audit_phase9_reconciliation.json"
REPORT_MD = "master_audit_phase9_reconciliation.md"

STATISTICAL_VALIDITY = Path(
    f"reports/statistical_validity/{RUN_ID}/statistical_validity_summary.json"
)
FAILURE_ANALYSIS = Path(f"reports/failure_analysis/{RUN_ID}/failure_analysis_summary.json")
ALPHA_GAP_MATRIX = Path(
    "reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/"
    "alpha_evidence_gap_matrix.json"
)
ALPHA_CLOSEOUT = Path(
    "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
    "alpha_evidence_completion_closeout.json"
)

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
    "phase8_reconciliation": DEFAULT_PHASE8,
    "statistical_validity": STATISTICAL_VALIDITY,
    "failure_analysis": FAILURE_ANALYSIS,
    "alpha_gap_matrix": ALPHA_GAP_MATRIX,
    "alpha_closeout": ALPHA_CLOSEOUT,
}

EXPECTED_RECONCILIATION_STATUSES = {
    "phase1b_reconciliation": "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY",
    "phase2_reconciliation": "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY",
    "phase3_reconciliation": "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY",
    "phase4_reconciliation": "PASS_MASTER_AUDIT_PHASE4_RECONCILIATION_REPORT_ONLY",
    "phase5_reconciliation": "PASS_MASTER_AUDIT_PHASE5_RECONCILIATION_REPORT_ONLY",
    "phase6_reconciliation": "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY",
    "phase7_reconciliation": "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
    "phase8_reconciliation": "PASS_MASTER_AUDIT_PHASE8_RECONCILIATION_REPORT_ONLY",
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase9_harness_executed": False,
    "statistical_validity_rerun_executed": False,
    "alpha_gap_rebuild_executed": False,
    "alpha_closeout_rebuild_executed": False,
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
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "target_discovery_executed": False,
    "source_tests_executed": False,
    "rescue_tuning_executed": False,
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
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase6_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase7_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase8_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase8_master_audit_status": "summary.phase8_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "statistical_validity": {
            "status": "status",
            "run": "run",
            "failure_count": "failure_count",
            "statistical_validity_ready": "statistical_validity_ready",
            "model_promotion_allowed": "model_promotion_allowed",
        },
        "failure_analysis": {
            "status": "status",
            "run": "run",
            "failure_count": "failure_count",
            "failure_analysis_ready": "failure_analysis_ready",
            "model_promotion_allowed": "model_promotion_allowed",
        },
        "alpha_gap_matrix": {
            "status": "status",
            "verdict": "verdict",
            "run_id": "run_id",
            "alpha_evidence_ready": "alpha_evidence_ready",
            "required_bucket_count": "required_bucket_count",
            "bucket_status_counts": "bucket_status_counts",
        },
        "alpha_closeout": {
            "status": "status",
            "verdict": "verdict",
            "run_id": "run_id",
            "bucket_count": "bucket_count",
            "terminal_fail_count": "terminal_fail_count",
            "missing_required_evidence_count": "missing_required_evidence_count",
            "modeling_pause_required": "modeling_pause_required",
            "future_modeling_allowed": "future_modeling_allowed",
            "future_evidence_work_allowed": "future_evidence_work_allowed",
            "promotion_allowed": "promotion_allowed",
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


def bucket_ids(alpha_gap: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for item in as_list(alpha_gap.get("buckets")):
        if isinstance(item, Mapping) and isinstance(item.get("bucket_id"), str):
            values.add(str(item["bucket_id"]))
    return values


def status_counts(payload: Mapping[str, Any], key: str = "bucket_status_counts") -> dict[str, int]:
    counts = as_mapping(payload.get(key))
    parsed: dict[str, int] = {}
    for name, value in counts.items():
        count = as_int(value)
        if count is not None:
            parsed[str(name)] = count
    return parsed


def non_approval_all_false(payload: Mapping[str, Any]) -> bool:
    non_approval = as_mapping(payload.get("non_approval"))
    return bool(non_approval) and all(value is False for value in non_approval.values())


def statistical_failures(statistical_validity: Mapping[str, Any]) -> list[str]:
    return [str(item) for item in as_list(statistical_validity.get("failures"))]


def has_statistical_failure_labels(failures: Sequence[str]) -> bool:
    text = "\n".join(failures).lower()
    return all(label.lower() in text for label in EXPECTED_STATISTICAL_FAILURES)


def source_matrix_matches_gap(repo_root: Path, alpha_closeout: Mapping[str, Any]) -> dict[str, Any]:
    source = as_mapping(alpha_closeout.get("source_matrix"))
    path_text = source.get("path")
    expected_sha = source.get("sha256")
    actual_sha = None
    if isinstance(path_text, str):
        actual_sha = inventory.sha256_file(resolve_path(repo_root, path_text))
    return {
        "path": path_text,
        "expected_sha256": expected_sha,
        "actual_sha256": actual_sha,
        "matches": isinstance(expected_sha, str)
        and actual_sha is not None
        and expected_sha == actual_sha
        and path_text == ALPHA_GAP_MATRIX.as_posix(),
        "verdict": source.get("verdict"),
        "alpha_evidence_ready": source.get("alpha_evidence_ready"),
        "bucket_status_counts": source.get("bucket_status_counts"),
    }


def build_checks(
    *,
    repo_root: Path,
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
        failure=f"missing required Phase 9 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 9 reconciliation: {output_rel}",
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
        name="master_audit_inputs_are_passed_report_only_blocking_evidence",
        passed=run_status is not None
        and overview is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and previous_status_pass,
        failure="run-status, overview, or Phase 1B-8 reconciliation inputs are not passed report-only blocking evidence",
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
            DEFAULT_PHASE8.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "previous_reconciliation_statuses": previous_statuses,
        },
    )

    phase9_row = row_by_area(run_status, "Phase 9")
    check(
        checks,
        failures,
        name="phase9_ledger_row_is_limited_closeout",
        passed=phase9_row is not None
        and phase9_row.get("run_status") == "RUN"
        and phase9_row.get("detail_status") == "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT"
        and phase9_row.get("evidence_state") == "limited-scope",
        failure="run-status Phase 9 row is not RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT/limited-scope",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"phase9_row": dict(phase9_row or {})},
    )

    statistical_validity = payloads.get("statistical_validity", {})
    failure_analysis = payloads.get("failure_analysis", {})
    alpha_gap = payloads.get("alpha_gap_matrix", {})
    alpha_closeout = payloads.get("alpha_closeout", {})

    stat_failures = statistical_failures(statistical_validity)
    check(
        checks,
        failures,
        name="statistical_validity_failure_preserved",
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

    classifications = {
        str(item.get("classification"))
        for item in as_list(failure_analysis.get("failure_classifications"))
        if isinstance(item, Mapping)
    }
    check(
        checks,
        failures,
        name="failure_analysis_remains_diagnostic_negative_evidence",
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
        },
    )

    gap_status_counts = status_counts(alpha_gap)
    gap_bucket_ids = bucket_ids(alpha_gap)
    check(
        checks,
        failures,
        name="alpha_gap_matrix_preserves_pause_verdict",
        passed=alpha_gap.get("status") == "PASS_REPORT_WRITTEN"
        and alpha_gap.get("verdict")
        == "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE"
        and alpha_gap.get("run_id") == RUN_ID
        and alpha_gap.get("alpha_evidence_ready") is False
        and alpha_gap.get("required_bucket_count") == 23
        and len(as_list(alpha_gap.get("buckets"))) == 23
        and gap_bucket_ids == EXPECTED_BUCKET_IDS
        and gap_status_counts == EXPECTED_BUCKET_STATUS_COUNTS
        and len(as_list(alpha_gap.get("blockers"))) == 17
        and non_approval_all_false(alpha_gap),
        failure="alpha evidence gap matrix no longer preserves the expected pause/blocker evidence",
        evidence=[ALPHA_GAP_MATRIX.as_posix()],
        details={
            "status": alpha_gap.get("status"),
            "verdict": alpha_gap.get("verdict"),
            "run_id": alpha_gap.get("run_id"),
            "alpha_evidence_ready": alpha_gap.get("alpha_evidence_ready"),
            "required_bucket_count": alpha_gap.get("required_bucket_count"),
            "bucket_count": len(as_list(alpha_gap.get("buckets"))),
            "bucket_status_counts": gap_status_counts,
            "missing_bucket_ids": sorted(EXPECTED_BUCKET_IDS - gap_bucket_ids),
            "extra_bucket_ids": sorted(gap_bucket_ids - EXPECTED_BUCKET_IDS),
            "blocker_count": len(as_list(alpha_gap.get("blockers"))),
            "non_approval": alpha_gap.get("non_approval"),
        },
    )

    closeout_status_counts = status_counts(alpha_closeout)
    closeout_classification_counts = status_counts(alpha_closeout, "closeout_classification_counts")
    source_matrix = source_matrix_matches_gap(repo_root, alpha_closeout)
    check(
        checks,
        failures,
        name="alpha_closeout_preserves_terminal_no_alpha_verdict",
        passed=alpha_closeout.get("status") == "PASS_REPORT_WRITTEN"
        and alpha_closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and alpha_closeout.get("run_id") == RUN_ID
        and alpha_closeout.get("bucket_count") == 23
        and closeout_status_counts == EXPECTED_BUCKET_STATUS_COUNTS
        and closeout_classification_counts == EXPECTED_CLOSEOUT_CLASSIFICATION_COUNTS
        and alpha_closeout.get("terminal_fail_count") == 5
        and alpha_closeout.get("missing_required_evidence_count") == 11
        and alpha_closeout.get("modeling_pause_required") is True
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("future_evidence_work_allowed") is True
        and alpha_closeout.get("promotion_allowed") is False
        and len(as_list(alpha_closeout.get("blockers"))) == 17
        and non_approval_all_false(alpha_closeout),
        failure="alpha evidence completion closeout no longer preserves the terminal no-alpha evidence",
        evidence=[ALPHA_CLOSEOUT.as_posix()],
        details={
            "status": alpha_closeout.get("status"),
            "verdict": alpha_closeout.get("verdict"),
            "run_id": alpha_closeout.get("run_id"),
            "bucket_count": alpha_closeout.get("bucket_count"),
            "bucket_status_counts": closeout_status_counts,
            "closeout_classification_counts": closeout_classification_counts,
            "terminal_fail_count": alpha_closeout.get("terminal_fail_count"),
            "missing_required_evidence_count": alpha_closeout.get(
                "missing_required_evidence_count"
            ),
            "modeling_pause_required": alpha_closeout.get("modeling_pause_required"),
            "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
            "future_evidence_work_allowed": alpha_closeout.get(
                "future_evidence_work_allowed"
            ),
            "promotion_allowed": alpha_closeout.get("promotion_allowed"),
            "blocker_count": len(as_list(alpha_closeout.get("blockers"))),
            "non_approval": alpha_closeout.get("non_approval"),
        },
    )

    check(
        checks,
        failures,
        name="alpha_closeout_source_matrix_hash_matches_gap_matrix",
        passed=source_matrix["matches"]
        and source_matrix["verdict"]
        == "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE"
        and source_matrix["alpha_evidence_ready"] is False,
        failure="alpha closeout source_matrix does not hash-match the current alpha gap matrix",
        evidence=[ALPHA_CLOSEOUT.as_posix(), ALPHA_GAP_MATRIX.as_posix()],
        details=source_matrix,
    )

    check(
        checks,
        failures,
        name="model_trust_modeling_promotion_holdout_paper_live_remain_blocked",
        passed=alpha_gap.get("alpha_evidence_ready") is False
        and alpha_closeout.get("modeling_pause_required") is True
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("promotion_allowed") is False
        and all(row["model_trust_ready"] is False for row in previous_statuses.values())
        and all(row["promotion_allowed"] is False for row in previous_statuses.values()),
        failure="model-trust, modeling, promotion, holdout, paper/live, or upstream blocking status was unexpectedly upgraded",
        evidence=[ALPHA_GAP_MATRIX.as_posix(), ALPHA_CLOSEOUT.as_posix()],
        details={
            "alpha_evidence_ready": alpha_gap.get("alpha_evidence_ready"),
            "modeling_pause_required": alpha_closeout.get("modeling_pause_required"),
            "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
            "promotion_allowed": alpha_closeout.get("promotion_allowed"),
            "previous_reconciliation_statuses": previous_statuses,
        },
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "previous_reconciliation_statuses": previous_statuses,
        "phase9_row": dict(phase9_row or {}),
        "statistical_validity_failures": stat_failures,
        "failure_classifications": sorted(classifications),
        "bucket_status_counts": gap_status_counts,
        "closeout_classification_counts": closeout_classification_counts,
        "bucket_ids": sorted(gap_bucket_ids),
        "blocker_count": len(as_list(alpha_gap.get("blockers"))),
        "required_bucket_count": alpha_gap.get("required_bucket_count"),
        "terminal_fail_count": alpha_closeout.get("terminal_fail_count"),
        "missing_required_evidence_count": alpha_closeout.get(
            "missing_required_evidence_count"
        ),
        "source_matrix": source_matrix,
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "phase9-001-limited-alpha-closeout-reconciled",
            "severity": "Info",
            "finding": "Existing Phase 9 evidence is accepted only as limited alpha-evidence closeout.",
            "verified_facts": [
                f"required_bucket_count={derived.get('required_bucket_count')}",
                f"bucket_status_counts={derived.get('bucket_status_counts')}",
                f"blocker_count={derived.get('blocker_count')}",
            ],
            "limitation": "This is not full Phase 9 research-process acceptance.",
            "evidence_paths": [ALPHA_GAP_MATRIX.as_posix(), ALPHA_CLOSEOUT.as_posix()],
        },
        {
            "finding_id": "phase9-002-statistical-validity-blockers-preserved",
            "severity": "Critical",
            "finding": "Statistical-validity evidence remains failing and blocks model-trust/promotion.",
            "verified_facts": [
                f"statistical_validity_failures={derived.get('statistical_validity_failures')}"
            ],
            "limitation": "Missing or failing statistical controls are treated as blockers, not waived tests.",
            "evidence_paths": [STATISTICAL_VALIDITY.as_posix()],
        },
        {
            "finding_id": "phase9-003-current-line-closed",
            "severity": "Critical",
            "finding": "The current line remains closed for alpha evidence.",
            "verified_facts": [
                f"terminal_fail_count={derived.get('terminal_fail_count')}",
                f"missing_required_evidence_count={derived.get('missing_required_evidence_count')}",
            ],
            "limitation": "Future evidence work may be allowed separately, but WFA/modeling, rescue tuning, promotion, holdout, and paper/live remain blocked.",
            "evidence_paths": [ALPHA_CLOSEOUT.as_posix()],
        },
        {
            "finding_id": "phase9-004-full-phase9-acceptance-blocked",
            "severity": "Critical",
            "finding": "Full Phase 9 Master Audit acceptance remains blocked.",
            "verified_facts": [
                "phase9_full_master_audit_accepted=false",
                "future_modeling_allowed=false",
                "promotion_allowed=false",
            ],
            "limitation": "White Reality Check, SPA/FDR-style controls, search-budget accounting, and trial-ledger completeness remain non-upgraded by this report.",
            "evidence_paths": ["MASTER_AUDIT.md"],
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
        repo_root=repo_root,
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
    phase9_classification = (
        "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT"
        if status == PASS_STATUS
        else "FAILED_PHASE9_RECONCILIATION"
    )
    alpha_closeout = payloads.get("alpha_closeout", {})
    alpha_gap = payloads.get("alpha_gap_matrix", {})
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase9_reconciliation_report_only",
            "phase": "Phase 9",
            "phase_name": "Research process, multiple testing, and alpha evidence closeout",
            "run": RUN_ID,
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "parquet_read_scope": "none",
            "phase_command_scope": "none",
            "full_phase9_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase9_master_audit_status": phase9_classification,
            "phase9_limited_alpha_closeout_evidence_ready": status == PASS_STATUS,
            "phase9_full_master_audit_accepted": False,
            "run": RUN_ID,
            "alpha_gap_verdict": alpha_gap.get("verdict"),
            "alpha_closeout_verdict": alpha_closeout.get("verdict"),
            "alpha_evidence_ready": False,
            "model_trust_ready": False,
            "modeling_pause_required": True,
            "future_modeling_allowed": False,
            "future_evidence_work_allowed": bool(
                alpha_closeout.get("future_evidence_work_allowed")
            ),
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
            "required_bucket_count": derived.get("required_bucket_count"),
            "bucket_status_counts": derived.get("bucket_status_counts"),
            "closeout_classification_counts": derived.get(
                "closeout_classification_counts"
            ),
            "blocker_count": derived.get("blocker_count"),
            "terminal_fail_count": derived.get("terminal_fail_count"),
            "missing_required_evidence_count": derived.get(
                "missing_required_evidence_count"
            ),
            "statistical_validity_failure_count": len(
                derived.get("statistical_validity_failures", [])
            ),
            "failure_classifications": derived.get("failure_classifications"),
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
        "bucket_ids": derived.get("bucket_ids", []),
        "statistical_validity_failures": derived.get("statistical_validity_failures", []),
        "source_matrix_reconciliation": derived.get("source_matrix", {}),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required JSON/MD evidence is readable",
                "run-status Phase 9 row is RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT",
                "Phase 1B/2/3/4/5/6/7/8 reconciliations are passed report-only blocking evidence",
                "statistical-validity evidence remains FAIL with the expected five blocking failures",
                "failure-analysis evidence remains diagnostic-only negative evidence",
                "alpha gap matrix preserves the pause verdict, 23 buckets, PASS=6/FAIL=6/MISSING_EVIDENCE=11, and 17 blockers",
                "alpha closeout preserves CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE, terminal_fail_count 5, missing_required_evidence_count 11, and future_modeling_allowed=false",
                "alpha closeout source_matrix hash matches the current alpha gap matrix",
                "model-trust, modeling, promotion, holdout, paper/live, and full Phase 9 acceptance remain blocked",
                "all forbidden action flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "run id, ledger, bucket count, status count, or source-hash mismatch",
                "statistical-validity failures disappear without separate approved evidence",
                "alpha gap or closeout verdict changes away from pause/no-alpha closeout",
                "current line is upgraded to alpha/model-trust/modeling/promotion readiness",
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
            "Plan exactly one next bounded Master Audit area from the updated Phase 1B/2/3/4/5/6/7/8/9 "
            "report-only evidence; do not run data/model/phase commands without separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 9 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 9 status: `{summary.get('phase9_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Run: `{summary.get('run')}`",
        f"- Alpha gap verdict: `{summary.get('alpha_gap_verdict')}`",
        f"- Alpha closeout verdict: `{summary.get('alpha_closeout_verdict')}`",
        f"- Bucket status counts: `{summary.get('bucket_status_counts')}`",
        f"- Closeout classification counts: `{summary.get('closeout_classification_counts')}`",
        f"- Blockers: `{summary.get('blocker_count')}`",
        f"- Terminal failures: `{summary.get('terminal_fail_count')}`",
        f"- Missing required evidence: `{summary.get('missing_required_evidence_count')}`",
        f"- Alpha evidence ready: `{summary.get('alpha_evidence_ready')}`",
        f"- Future modeling allowed: `{summary.get('future_modeling_allowed')}`",
        f"- Promotion allowed: `{summary.get('promotion_allowed')}`",
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
    stat_failures = report.get("statistical_validity_failures", [])
    lines.extend([f"- {failure}" for failure in stat_failures] or ["- None"])
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
            "- This reconciliation did not run Phase 9 harnesses, statistical-validity reruns, alpha-gap rebuilds, alpha-closeout rebuilds, phase audits, data/model commands, WFA/modeling, prediction generation/materialization, Phase 8 refresh, provider/network calls, target discovery, source tests, rescue tuning, promotion, freeze, holdout, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, or model artifacts, and it did not consume or advance the hardened split candidate or hardened Phase 6/7 materialization path.",
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
        f"phase9_status={report['summary']['phase9_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
