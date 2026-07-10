#!/usr/bin/env python3
"""Build the report-only trial-ledger/search-path reconciliation.

This command consumes existing local registry/ledger evidence only. It does not
run statistical-validity generation, gap-map generation, data/model commands,
WFA/modeling, predictions, Phase 8 refresh, provider/network calls, promotion,
artifact freeze, final holdout, paper/live, cleanup, staging, commit, or push.
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
STAGE = "master_audit_trial_ledger_search_path_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_TRIAL_LEDGER_SEARCH_PATH_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_TRIAL_LEDGER_SEARCH_PATH_RECONCILIATION_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_trial_ledger_search_path_reconciliation_20260710"
)
REPORT_JSON = "master_audit_trial_ledger_search_path_reconciliation.json"
REPORT_MD = "master_audit_trial_ledger_search_path_reconciliation.md"

PARTIAL_RECONCILIATION = Path(
    "reports/master_audit/master_audit_statistical_validity_partial_reconciliation_20260710/"
    "master_audit_statistical_validity_partial_reconciliation.json"
)
STATISTICAL_SUMMARY = Path(
    "reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/"
    "statistical_validity_summary.json"
)
ALPHA_GAP_MATRIX = Path(
    "reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/"
    "alpha_evidence_gap_matrix.json"
)
ALPHA_COMPLETION_CLOSEOUT = Path(
    "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
    "alpha_evidence_completion_closeout.json"
)
EXPERIMENT_LEDGER = Path("reports/experiments/ledger.jsonl")
TARGET_REGISTRY = Path("manifests/target_hypotheses/registry.json")
TARGET_TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
ADVERSARIAL_AUDIT = Path("docs/adversarial_current_project_evidence_gate_audit_20260709.md")

REQUIRED_INPUTS = {
    "partial_reconciliation": PARTIAL_RECONCILIATION,
    "statistical_summary": STATISTICAL_SUMMARY,
    "alpha_gap_matrix": ALPHA_GAP_MATRIX,
    "alpha_completion_closeout": ALPHA_COMPLETION_CLOSEOUT,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

EXPECTED_EXPERIMENT_LEDGER_ROWS = 4
EXPECTED_TARGET_REGISTRY_HYPOTHESES = 17
EXPECTED_TARGET_TRIAL_STATUS_ROWS = 22
EXPECTED_FROZEN_HYPOTHESES = 1

TERMINAL_OR_PASS_STATUSES = {
    "DISCOVERY_PASS",
    "CONFIRMATION_PASS",
    "FROZEN",
    "REJECTED",
    "RETIRED",
    "QUARANTINED",
}

SEARCH_COMPLETENESS_FIELDS = (
    "trial_id",
    "hypothesis_id",
    "run_id",
    "stage",
    "status",
    "search_family_id",
    "multiple_testing_family_id",
    "data_hashes",
    "prediction_hashes",
    "config_hashes",
    "model_family",
    "feature_family",
    "target_label_family",
    "thresholds",
    "policy_variants",
    "seed_policy",
    "hyperparameter_budget",
    "primary_metric",
    "stop_rule",
    "evidence_paths",
    "predeclaration_timestamp",
)

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


def read_jsonl_objects(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        return [], [f"missing JSONL input: {path.as_posix()}"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as exc:
            errors.append(f"{path.as_posix()}:{line_number} JSON parse error: {exc}")
            continue
        if not isinstance(row, dict):
            errors.append(f"{path.as_posix()}:{line_number} JSONL row is not an object")
            continue
        row["_line_number"] = line_number
        rows.append(row)
    return rows, errors


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


def input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields: dict[str, dict[str, str]] = {
        "partial_reconciliation": {
            "status": "status",
            "trial_ledger_search_path_complete": "summary.trial_ledger_search_path_complete",
            "pbo_status": "summary.pbo_status",
            "deflated_sharpe_status": "summary.deflated_sharpe_status",
            "multiple_testing_status": "summary.multiple_testing_status",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "statistical_summary": {
            "status": "status",
            "statistical_validity_ready": "statistical_validity_ready",
            "failure_count": "failure_count",
        },
        "alpha_gap_matrix": {
            "status": "status",
            "alpha_evidence_ready": "alpha_evidence_ready",
            "verdict": "verdict",
        },
        "alpha_completion_closeout": {
            "status": "status",
            "future_modeling_allowed": "future_modeling_allowed",
            "promotion_allowed": "promotion_allowed",
            "verdict": "verdict",
        },
        "target_registry": {
            "schema_version": "schema_version",
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


def text_contains(path: Path, terms: Sequence[str]) -> dict[str, bool]:
    try:
        text = path.read_text(encoding="utf-8").lower()
    except Exception:
        return {term: False for term in terms}
    return {term: term.lower() in text for term in terms}


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


def registry_hypotheses(registry: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = registry.get("hypotheses") if isinstance(registry, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("status")) for row in rows).items()))


def missing_fields_for_rows(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for field in fields:
            value = row.get(field)
            if value in (None, "", [], {}):
                counts[field] += 1
    return dict(sorted(counts.items()))


def terminal_status_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("status", "")).upper() in TERMINAL_OR_PASS_STATUSES
    ]


def terminal_rows_without_evidence_paths(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for row in terminal_status_rows(rows):
        evidence = row.get("evidence")
        has_path = (
            isinstance(evidence, list)
            and any(isinstance(item, str) and item.strip() for item in evidence)
        )
        if not has_path:
            missing.append(
                {
                    "line_number": row.get("_line_number"),
                    "trial_id": row.get("trial_id"),
                    "hypothesis_id": row.get("hypothesis_id"),
                    "status": row.get("status"),
                }
            )
    return missing


def registry_wfa_violations(registry_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "target_hypothesis_id": row.get("target_hypothesis_id"),
            "status": row.get("status"),
            "wfa_allowed": row.get("wfa_allowed"),
        }
        for row in registry_rows
        if row.get("wfa_allowed") is True and row.get("status") != "FROZEN"
    ]


def unknown_trial_hypotheses(
    *,
    trial_rows: Sequence[Mapping[str, Any]],
    registry_ids: set[str],
) -> list[dict[str, Any]]:
    unknown: list[dict[str, Any]] = []
    for row in trial_rows:
        hypothesis_id = str(row.get("hypothesis_id") or "")
        if not hypothesis_id or hypothesis_id not in registry_ids:
            unknown.append(
                {
                    "line_number": row.get("_line_number"),
                    "trial_id": row.get("trial_id"),
                    "hypothesis_id": row.get("hypothesis_id"),
                }
            )
    return unknown


def required_stat_checks(payload: Mapping[str, Any] | None) -> Mapping[str, Mapping[str, Any]]:
    checks = payload.get("required_checks") if isinstance(payload, Mapping) else {}
    if not isinstance(checks, Mapping):
        return {}
    return {
        str(key): value
        for key, value in checks.items()
        if isinstance(value, Mapping)
    }


def build_checks(
    *,
    repo_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    input_evidence_rows: Sequence[Mapping[str, Any]],
    output_rel: str,
    paths: Mapping[str, Path],
    experiment_rows: Sequence[Mapping[str, Any]],
    experiment_errors: Sequence[str],
    trial_status_rows: Sequence[Mapping[str, Any]],
    trial_status_errors: Sequence[str],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {
        str(item.get("path")) for item in input_evidence_rows if item.get("exists")
    }
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required trial-ledger/search-path inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel.startswith("reports/master_audit/") and not output_rel.endswith("/"),
        failure=f"invalid report output root for trial-ledger/search-path reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    partial = payloads.get("partial_reconciliation")
    check(
        checks,
        failures,
        name="upstream_statistical_partial_reconciliation_preserves_blocked_state",
        passed=partial is not None
        and partial.get("status")
        == "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_PARTIAL_RECONCILIATION_REPORT_ONLY"
        and dotted_get(partial, "summary.data_integrity_ready") is True
        and dotted_get(partial, "summary.pbo_status") == "FAIL_MISSING_TRIAL_LOG"
        and dotted_get(partial, "summary.deflated_sharpe_status")
        == "FAIL_MISSING_TRIAL_LOG"
        and dotted_get(partial, "summary.multiple_testing_status")
        == "FAIL_MISSING_TRIAL_LOG"
        and dotted_get(partial, "summary.statistical_validity_ready") is False
        and dotted_get(partial, "summary.model_trust_ready") is False
        and dotted_get(partial, "summary.promotion_allowed") is False,
        failure="upstream statistical partial reconciliation does not preserve blocked trial-log state",
        evidence=[PARTIAL_RECONCILIATION.as_posix()],
        details={
            "status": None if partial is None else partial.get("status"),
            "summary": None if partial is None else partial.get("summary"),
        },
    )

    statistical = payloads.get("statistical_summary")
    required_checks = required_stat_checks(statistical)
    pbo = required_checks.get("pbo", {})
    deflated = required_checks.get("deflated_sharpe", {})
    multiple = required_checks.get("multiple_testing_adjustment", {})
    check(
        checks,
        failures,
        name="statistical_summary_keeps_trial_log_dependent_failures",
        passed=statistical is not None
        and statistical.get("status") == "FAIL"
        and statistical.get("statistical_validity_ready") is False
        and pbo.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and deflated.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and multiple.get("status") == "FAIL_MISSING_TRIAL_LOG",
        failure="statistical summary does not keep PBO/Deflated Sharpe/multiple-testing missing-trial-log failures",
        evidence=[STATISTICAL_SUMMARY.as_posix()],
        details={
            "summary_status": None if statistical is None else statistical.get("status"),
            "pbo": dict(pbo),
            "deflated_sharpe": dict(deflated),
            "multiple_testing_adjustment": dict(multiple),
        },
    )

    matrix = payloads.get("alpha_gap_matrix")
    matrix_pbo = find_bucket(matrix, "statistical_pbo")
    matrix_deflated = find_bucket(matrix, "statistical_deflated_sharpe")
    matrix_multiple = find_bucket(matrix, "statistical_multiple_testing")
    check(
        checks,
        failures,
        name="alpha_gap_matrix_preserves_search_path_missing_evidence",
        passed=matrix is not None
        and matrix.get("status") == "PASS_REPORT_WRITTEN"
        and matrix.get("alpha_evidence_ready") is False
        and matrix_pbo.get("status") == "MISSING_EVIDENCE"
        and matrix_deflated.get("status") == "MISSING_EVIDENCE"
        and matrix_multiple.get("status") == "MISSING_EVIDENCE",
        failure="alpha evidence gap matrix does not preserve PBO/Deflated Sharpe/multiple-testing as missing evidence",
        evidence=[ALPHA_GAP_MATRIX.as_posix()],
        details={
            "statistical_pbo": dict(matrix_pbo),
            "statistical_deflated_sharpe": dict(matrix_deflated),
            "statistical_multiple_testing": dict(matrix_multiple),
        },
    )

    closeout = payloads.get("alpha_completion_closeout")
    closeout_pbo = find_closeout_bucket(closeout, "statistical_pbo")
    closeout_deflated = find_closeout_bucket(closeout, "statistical_deflated_sharpe")
    closeout_multiple = find_closeout_bucket(closeout, "statistical_multiple_testing")
    check(
        checks,
        failures,
        name="alpha_closeout_preserves_missing_required_search_path_evidence",
        passed=closeout is not None
        and closeout.get("status") == "PASS_REPORT_WRITTEN"
        and closeout.get("future_modeling_allowed") is False
        and closeout.get("promotion_allowed") is False
        and closeout_pbo.get("closeout_classification") == "missing_required_evidence"
        and closeout_deflated.get("closeout_classification")
        == "missing_required_evidence"
        and closeout_multiple.get("closeout_classification")
        == "missing_required_evidence",
        failure="alpha completion closeout does not preserve missing-required search-path classifications",
        evidence=[ALPHA_COMPLETION_CLOSEOUT.as_posix()],
        details={
            "statistical_pbo": dict(closeout_pbo),
            "statistical_deflated_sharpe": dict(closeout_deflated),
            "statistical_multiple_testing": dict(closeout_multiple),
        },
    )

    check(
        checks,
        failures,
        name="experiment_ledger_jsonl_parses",
        passed=not experiment_errors and len(experiment_rows) == EXPECTED_EXPERIMENT_LEDGER_ROWS,
        failure=(
            "experiment ledger JSONL did not parse or row count changed: "
            f"errors={list(experiment_errors)} rows={len(experiment_rows)}"
        ),
        evidence=[EXPERIMENT_LEDGER.as_posix()],
        details={
            "row_count": len(experiment_rows),
            "expected_row_count": EXPECTED_EXPERIMENT_LEDGER_ROWS,
            "errors": list(experiment_errors),
        },
    )

    registry = payloads.get("target_registry")
    registry_rows = registry_hypotheses(registry)
    registry_ids = {
        str(row.get("target_hypothesis_id"))
        for row in registry_rows
        if row.get("target_hypothesis_id")
    }
    frozen_count = sum(1 for row in registry_rows if row.get("status") == "FROZEN")
    registry_missing_identity = [
        {
            "target_hypothesis_id": row.get("target_hypothesis_id"),
            "status": row.get("status"),
        }
        for row in registry_rows
        if not row.get("target_hypothesis_id") or not row.get("status")
    ]
    wfa_violations = registry_wfa_violations(registry_rows)
    check(
        checks,
        failures,
        name="target_registry_current_counts_and_wfa_policy_parse",
        passed=registry is not None
        and len(registry_rows) == EXPECTED_TARGET_REGISTRY_HYPOTHESES
        and frozen_count == EXPECTED_FROZEN_HYPOTHESES
        and not registry_missing_identity
        and not wfa_violations,
        failure=(
            "target registry counts, identity fields, or WFA policy are invalid: "
            f"rows={len(registry_rows)} frozen={frozen_count} wfa_violations={wfa_violations}"
        ),
        evidence=[TARGET_REGISTRY.as_posix()],
        details={
            "hypothesis_count": len(registry_rows),
            "expected_hypothesis_count": EXPECTED_TARGET_REGISTRY_HYPOTHESES,
            "frozen_count": frozen_count,
            "expected_frozen_count": EXPECTED_FROZEN_HYPOTHESES,
            "status_counts": status_counts(registry_rows),
            "missing_identity": registry_missing_identity,
            "non_frozen_wfa_allowed": wfa_violations,
        },
    )

    unknown_trials = unknown_trial_hypotheses(
        trial_rows=trial_status_rows,
        registry_ids=registry_ids,
    )
    terminal_missing_evidence = terminal_rows_without_evidence_paths(trial_status_rows)
    check(
        checks,
        failures,
        name="target_trial_status_jsonl_parses_and_matches_registry",
        passed=not trial_status_errors
        and len(trial_status_rows) == EXPECTED_TARGET_TRIAL_STATUS_ROWS
        and not unknown_trials
        and not terminal_missing_evidence,
        failure=(
            "target trial-status JSONL is malformed, has unknown hypotheses, or "
            "terminal/pass rows without evidence paths"
        ),
        evidence=[TARGET_TRIAL_STATUSES.as_posix()],
        details={
            "row_count": len(trial_status_rows),
            "expected_row_count": EXPECTED_TARGET_TRIAL_STATUS_ROWS,
            "status_counts": status_counts(trial_status_rows),
            "errors": list(trial_status_errors),
            "unknown_trials": unknown_trials,
            "terminal_or_pass_rows_without_evidence_paths": terminal_missing_evidence,
        },
    )

    experiment_missing_fields = missing_fields_for_rows(
        experiment_rows,
        SEARCH_COMPLETENESS_FIELDS,
    )
    trial_missing_fields = missing_fields_for_rows(
        trial_status_rows,
        SEARCH_COMPLETENESS_FIELDS,
    )
    trial_ledger_search_path_complete = (
        not experiment_missing_fields
        and not trial_missing_fields
        and len(experiment_rows) >= len(terminal_status_rows(trial_status_rows))
    )
    check(
        checks,
        failures,
        name="current_incomplete_search_path_evidence_explicitly_preserved",
        passed=trial_ledger_search_path_complete is False
        and bool(experiment_missing_fields)
        and pbo.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and deflated.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and multiple.get("status") == "FAIL_MISSING_TRIAL_LOG",
        failure="current search-path incompleteness is not explicitly preserved",
        evidence=[
            EXPERIMENT_LEDGER.as_posix(),
            TARGET_REGISTRY.as_posix(),
            TARGET_TRIAL_STATUSES.as_posix(),
            STATISTICAL_SUMMARY.as_posix(),
        ],
        details={
            "trial_ledger_search_path_complete": trial_ledger_search_path_complete,
            "required_fields": list(SEARCH_COMPLETENESS_FIELDS),
            "experiment_ledger_missing_field_counts": experiment_missing_fields,
            "target_trial_status_missing_field_counts": trial_missing_fields,
        },
    )

    run_status = payloads.get("run_status")
    check(
        checks,
        failures,
        name="run_status_preserves_closed_line_and_forbidden_actions",
        passed=run_status is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and dotted_get(run_status, "summary.current_line_classification")
        == "closed_no_alpha_evidence"
        and dotted_get(run_status, "summary.current_split_classification")
        == "same_fold_rolling_retraining_research_only"
        and dotted_get(run_status, "summary.data_model_commands_executed") is False
        and dotted_get(run_status, "summary.wfa_modeling_executed") is False
        and dotted_get(run_status, "summary.predictions_executed") is False
        and dotted_get(run_status, "summary.provider_network_calls_executed") is False
        and dotted_get(run_status, "summary.promotion_or_freeze_or_holdout_executed")
        is False
        and dotted_get(run_status, "summary.paper_or_live_executed") is False,
        failure="run status does not preserve closed-line and non-execution evidence",
        evidence=[RUN_STATUS.as_posix()],
        details={"summary": run_status.get("summary") if isinstance(run_status, Mapping) else None},
    )

    adversarial_terms = text_contains(
        resolve_path(repo_root, ADVERSARIAL_AUDIT),
        (
            "no complete current-scope trial log",
            "pbo",
            "deflated sharpe",
            "multiple-testing",
        ),
    )
    check(
        checks,
        failures,
        name="adversarial_audit_preserves_trial_search_blockers",
        passed=all(adversarial_terms.values()),
        failure="adversarial audit does not preserve required trial-ledger/search-path blocker statements",
        evidence=[ADVERSARIAL_AUDIT.as_posix()],
        details={"term_presence": adversarial_terms},
    )

    check(
        checks,
        failures,
        name="no_statistical_or_model_readiness_upgrade",
        passed=dotted_get(partial, "summary.statistical_validity_ready") is False
        and dotted_get(partial, "summary.model_trust_ready") is False
        and dotted_get(partial, "summary.promotion_allowed") is False
        and all(value is False for value in NON_APPROVAL.values()),
        failure="trial-ledger/search-path reconciliation attempted a readiness or non-approval upgrade",
        details={
            "partial_statistical_validity_ready": dotted_get(
                partial, "summary.statistical_validity_ready"
            ),
            "partial_model_trust_ready": dotted_get(partial, "summary.model_trust_ready"),
            "partial_promotion_allowed": dotted_get(partial, "summary.promotion_allowed"),
            "non_approval": dict(NON_APPROVAL),
        },
    )

    for item in input_evidence_rows:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "trial_ledger_search_path_complete": trial_ledger_search_path_complete,
        "experiment_ledger_row_count": len(experiment_rows),
        "target_registry_hypothesis_count": len(registry_rows),
        "target_trial_status_row_count": len(trial_status_rows),
        "frozen_hypothesis_count": frozen_count,
        "terminal_or_pass_trial_status_row_count": len(terminal_status_rows(trial_status_rows)),
        "registry_status_counts": status_counts(registry_rows),
        "trial_status_counts": status_counts(trial_status_rows),
        "experiment_ledger_missing_field_counts": experiment_missing_fields,
        "target_trial_status_missing_field_counts": trial_missing_fields,
        "required_completeness_fields": list(SEARCH_COMPLETENESS_FIELDS),
        "pbo_status": pbo.get("status"),
        "deflated_sharpe_status": deflated.get("status"),
        "multiple_testing_status": multiple.get("status"),
        "statistical_validity_ready": False,
        "model_trust_ready": False,
        "promotion_allowed": False,
        "unknown_trial_hypotheses": unknown_trials,
        "terminal_or_pass_rows_without_evidence_paths": terminal_missing_evidence,
        "non_frozen_wfa_allowed": wfa_violations,
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "trial-ledger-001-current-search-path-incomplete",
            "severity": "High",
            "finding": "Current experiment-ledger/search-path evidence is incomplete for PBO, Deflated Sharpe, and multiple-testing acceptance.",
            "verified_facts": [
                f"experiment_ledger_row_count={derived.get('experiment_ledger_row_count')}",
                f"target_registry_hypothesis_count={derived.get('target_registry_hypothesis_count')}",
                f"target_trial_status_row_count={derived.get('target_trial_status_row_count')}",
                f"trial_ledger_search_path_complete={derived.get('trial_ledger_search_path_complete')}",
            ],
            "limitation": "This report maps missing coverage only; it does not create or backfill a complete search ledger.",
            "evidence_paths": [
                EXPERIMENT_LEDGER.as_posix(),
                TARGET_REGISTRY.as_posix(),
                TARGET_TRIAL_STATUSES.as_posix(),
            ],
        },
        {
            "finding_id": "trial-ledger-002-statistical-blockers-preserved",
            "severity": "High",
            "finding": "PBO, Deflated Sharpe, and multiple-testing remain missing-trial-log blockers.",
            "verified_facts": [
                f"pbo_status={derived.get('pbo_status')}",
                f"deflated_sharpe_status={derived.get('deflated_sharpe_status')}",
                f"multiple_testing_status={derived.get('multiple_testing_status')}",
            ],
            "limitation": "No statistical-validity check is upgraded.",
            "evidence_paths": [
                PARTIAL_RECONCILIATION.as_posix(),
                STATISTICAL_SUMMARY.as_posix(),
            ],
        },
        {
            "finding_id": "trial-ledger-003-registry-status-is-not-overfit-accounting",
            "severity": "Info",
            "finding": "Registry and target trial-status rows record branch status, but they are not complete overfit or multiple-testing accounting.",
            "verified_facts": [
                f"registry_status_counts={derived.get('registry_status_counts')}",
                f"trial_status_counts={derived.get('trial_status_counts')}",
            ],
            "limitation": "Future acceptance still needs search-family IDs, multiple-testing family IDs, trial counts, and full variant metadata.",
            "evidence_paths": [TARGET_REGISTRY.as_posix(), TARGET_TRIAL_STATUSES.as_posix()],
        },
        {
            "finding_id": "trial-ledger-004-no-readiness-upgrade",
            "severity": "Info",
            "finding": "Statistical validity, model trust, promotion, paper/live, and production remain blocked.",
            "verified_facts": ["All non-approval flags in this report are false."],
            "limitation": "This report is evidence reconciliation only.",
            "evidence_paths": [RUN_STATUS.as_posix()],
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
    evidence_rows = input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    experiment_rows, experiment_errors = read_jsonl_objects(
        resolve_path(repo_root, paths["experiment_ledger"])
    )
    trial_status_rows, trial_status_errors = read_jsonl_objects(
        resolve_path(repo_root, paths["target_trial_statuses"])
    )
    output_rel = rel(reports_root, repo_root)
    checks, check_failures, derived = build_checks(
        repo_root=repo_root,
        payloads=payloads,
        input_evidence_rows=evidence_rows,
        output_rel=output_rel,
        paths=paths,
        experiment_rows=experiment_rows,
        experiment_errors=experiment_errors,
        trial_status_rows=trial_status_rows,
        trial_status_errors=trial_status_errors,
    )
    failures = input_failures + experiment_errors + trial_status_errors + check_failures
    failures = list(dict.fromkeys(failures))
    status = PASS_STATUS if not failures else FAIL_STATUS
    findings = build_findings(derived)
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_trial_ledger_search_path_reconciliation_report_only",
            "target_gap_area": "statistical_validity",
            "target_checks": [
                "pbo",
                "deflated_sharpe",
                "multiple_testing_adjustment",
            ],
            "reports_root": output_rel,
            "evidence_mode": "existing_local_registry_ledger_json_jsonl_md_only",
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
            "trial_ledger_search_path_reconciliation_ready": status == PASS_STATUS,
            "trial_ledger_search_path_complete": False,
            "pbo_status": derived.get("pbo_status"),
            "deflated_sharpe_status": derived.get("deflated_sharpe_status"),
            "multiple_testing_status": derived.get("multiple_testing_status"),
            "data_integrity_ready": True,
            "statistical_validity_ready": False,
            "statistical_validity_master_audit_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
            "experiment_ledger_row_count": derived.get("experiment_ledger_row_count"),
            "target_registry_hypothesis_count": derived.get(
                "target_registry_hypothesis_count"
            ),
            "target_trial_status_row_count": derived.get(
                "target_trial_status_row_count"
            ),
            "frozen_hypothesis_count": derived.get("frozen_hypothesis_count"),
            "terminal_or_pass_trial_status_row_count": derived.get(
                "terminal_or_pass_trial_status_row_count"
            ),
            "registry_status_counts": derived.get("registry_status_counts"),
            "trial_status_counts": derived.get("trial_status_counts"),
            "required_completeness_fields": derived.get(
                "required_completeness_fields"
            ),
            "experiment_ledger_missing_field_counts": derived.get(
                "experiment_ledger_missing_field_counts"
            ),
            "target_trial_status_missing_field_counts": derived.get(
                "target_trial_status_missing_field_counts"
            ),
            "unknown_trial_hypotheses": derived.get("unknown_trial_hypotheses"),
            "terminal_or_pass_rows_without_evidence_paths": derived.get(
                "terminal_or_pass_rows_without_evidence_paths"
            ),
            "non_frozen_wfa_allowed": derived.get("non_frozen_wfa_allowed"),
            **dict(NON_APPROVAL),
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
            "finding_counts": finding_counts(findings),
        },
        "input_evidence": evidence_rows,
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
                "required local registry/ledger/statistical inputs are readable",
                "experiment ledger parses with current 4-row blocked evidence",
                "target registry parses with 17 hypotheses and exactly 1 frozen hypothesis",
                "target trial-status JSONL parses with 22 rows and no unknown hypotheses",
                "non-candidate trial-status rows include evidence path values",
                "non-FROZEN hypotheses do not have wfa_allowed=true",
                "PBO, Deflated Sharpe, and multiple-testing remain FAIL_MISSING_TRIAL_LOG",
                "trial-ledger/search-path completeness remains false and missing-field map is present",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "malformed experiment ledger, target registry, or target trial-status JSONL",
                "unknown target trial-status hypothesis",
                "non-FROZEN hypothesis with wfa_allowed=true",
                "terminal/pass target trial-status row with no evidence path value",
                "PBO, Deflated Sharpe, multiple-testing, statistical validity, model trust, or promotion is upgraded",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan the next statistical-validity evidence slice from the missing-field "
            "and missing-coverage map; do not run data/model commands, WFA/modeling, "
            "predictions, Phase 8 refresh, provider calls, promotion, or gap-map generation."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Trial-Ledger/Search-Path Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Trial-ledger/search-path complete: `{summary['trial_ledger_search_path_complete']}`",
        f"- Experiment ledger rows: `{summary['experiment_ledger_row_count']}`",
        f"- Target registry hypotheses: `{summary['target_registry_hypothesis_count']}`",
        f"- Target trial-status rows: `{summary['target_trial_status_row_count']}`",
        f"- Frozen hypotheses: `{summary['frozen_hypothesis_count']}`",
        f"- PBO status: `{summary['pbo_status']}`",
        f"- Deflated Sharpe status: `{summary['deflated_sharpe_status']}`",
        f"- Multiple-testing status: `{summary['multiple_testing_status']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Missing Completeness Fields",
        "",
        f"- Required fields: `{summary['required_completeness_fields']}`",
        f"- Experiment ledger missing field counts: `{summary['experiment_ledger_missing_field_counts']}`",
        f"- Target trial-status missing field counts: `{summary['target_trial_status_missing_field_counts']}`",
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
        f"trial_ledger_search_path_complete="
        f"{report['summary']['trial_ledger_search_path_complete']} "
        f"pbo_status={report['summary']['pbo_status']} "
        f"deflated_sharpe_status={report['summary']['deflated_sharpe_status']} "
        f"multiple_testing_status={report['summary']['multiple_testing_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
