#!/usr/bin/env python3
"""Build a report-only unrecovered-source and family-metadata remediation plan.

This command consumes existing local Master Audit trial/search evidence. It
does not restore source reports, mutate ledgers, mutate registries, mutate
trial-status rows, run generated evidence commands, run data/model work, or
change git state.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import build_master_audit_source_report_recovery_disposition_plan as source_plan
from scripts.validation import build_master_audit_trial_ledger_search_path_reconciliation as trial
from scripts.validation import build_master_audit_trial_search_ledger_backfill_decision as backfill
from scripts.validation import build_master_audit_trial_search_ledger_schema_remediation_plan as schema


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_unrecovered_source_family_metadata_remediation"
PASS_STATUS = "PASS_MASTER_AUDIT_UNRECOVERED_SOURCE_FAMILY_METADATA_REMEDIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_UNRECOVERED_SOURCE_FAMILY_METADATA_REMEDIATION_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_unrecovered_source_family_metadata_remediation_20260710"
)
REPORT_JSON = "master_audit_unrecovered_source_family_metadata_remediation.json"
REPORT_MD = "master_audit_unrecovered_source_family_metadata_remediation.md"

SOURCE_DISPOSITION_REPORT = source_plan.DEFAULT_REPORTS_ROOT / source_plan.REPORT_JSON
BACKFILL_DECISION_REPORT = backfill.DEFAULT_REPORTS_ROOT / backfill.REPORT_JSON
SCHEMA_REMEDIATION = schema.DEFAULT_REPORTS_ROOT / schema.REPORT_JSON
TARGET_REGISTRY = schema.TARGET_REGISTRY
TARGET_TRIAL_STATUSES = schema.TARGET_TRIAL_STATUSES
EXPERIMENT_LEDGER = schema.EXPERIMENT_LEDGER
RUN_STATUS = schema.RUN_STATUS
ADVERSARIAL_AUDIT = schema.ADVERSARIAL_AUDIT

REQUIRED_INPUTS = {
    "source_disposition": SOURCE_DISPOSITION_REPORT,
    "backfill_decision": BACKFILL_DECISION_REPORT,
    "schema_remediation": SCHEMA_REMEDIATION,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

EXPECTED_CANDIDATE_ROWS = 27
EXPECTED_SOURCE_REFS = 21
EXPECTED_PRESENT_SOURCE_REFS = 7
EXPECTED_MISSING_SOURCE_REFS = 14
EXPECTED_UNRECOVERED_SOURCE_REPORTS = 14
EXPECTED_REGISTRY_HYPOTHESES = 17
EXPECTED_TRIAL_STATUS_ROWS = 22
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4

PROPOSED_DISPOSITION = "PROPOSE_IRRECOVERABLE_SOURCE_REPORT_DISPOSITION_PENDING_SEPARATE_LEDGER_APPROVAL"
PROPOSED_FAMILY = "PROPOSED_REPORT_LOCAL_FAMILY_ID"
UNRESOLVED = schema.UNRESOLVED

WRITE_APPROVALS = {
    "append_only_backfill_allowed": False,
    "write_schema_complete_rows_allowed": False,
    "write_unresolved_marker_rows_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_mutation_executed": False,
    "registry_mutation_executed": False,
    "trial_status_mutation_executed": False,
    "source_report_restore_executed": False,
}

NON_APPROVAL = {
    "data_model_commands_executed": False,
    "wfa_modeling_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "freeze_executed": False,
    "holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "gap_map_generation_executed": False,
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


def read_jsonl_objects(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    return trial.read_jsonl_objects(path)


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
        "source_disposition": {
            "status": "status",
            "missing_source_refs": "summary.missing_registry_json_source_report_ref_count",
            "source_report_restore_executed": "summary.source_report_restore_executed",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "backfill_decision": {
            "status": "status",
            "backfill_decision": "summary.backfill_decision",
            "append_only_backfill_allowed": "summary.append_only_backfill_allowed",
        },
        "schema_remediation": {
            "status": "status",
            "candidate_rows": "summary.candidate_trial_search_ledger_row_count",
            "search_unresolved": "summary.unresolved_field_counts.search_family_id",
            "multiple_unresolved": "summary.unresolved_field_counts.multiple_testing_family_id",
        },
        "target_registry": {"schema_version": "schema_version"},
        "run_status": {
            "status": "status",
            "current_line_classification": "summary.current_line_classification",
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


def registry_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    return trial.registry_hypotheses(payload)


def candidate_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = payload.get("candidate_trial_search_ledger_rows") if isinstance(payload, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def source_refs(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    refs = payload.get("source_report_reference_inventory") if isinstance(payload, Mapping) else []
    return [row for row in refs if isinstance(row, Mapping)] if isinstance(refs, list) else []


def disposition_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = payload.get("missing_source_report_dispositions") if isinstance(payload, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def source_resolution_for_row(row: Mapping[str, Any]) -> str:
    value = row.get("source_report_resolution")
    return str(value) if value else ""


def normalize_token(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    chars = [ch if ch.isalnum() else "_" for ch in text]
    token = "_".join("".join(chars).split("_"))
    return token or "unknown"


def scope_tokens(registry_row: Mapping[str, Any]) -> tuple[str, str, str]:
    scope = registry_row.get("scope")
    scope_map = scope if isinstance(scope, Mapping) else {}
    profile = normalize_token(
        scope_map.get("resolved_profile") or scope_map.get("profile") or "unknown_profile"
    )
    markets = scope_map.get("markets")
    market_token = "unknown_markets"
    if isinstance(markets, list) and markets:
        market_token = "_".join(normalize_token(item).upper() for item in markets)
    years = scope_map.get("years")
    year_token = "unknown_years"
    if isinstance(years, list) and years:
        year_token = "_".join(str(item) for item in years)
    return profile, market_token, year_token


def unresolved_family(field: str, reason: str, evidence_paths: Sequence[str]) -> dict[str, Any]:
    return {
        "status": UNRESOLVED,
        "field": field,
        "reason": reason,
        "evidence_paths": list(dict.fromkeys(evidence_paths)),
    }


def proposed_family_ids(
    *,
    row: Mapping[str, Any],
    registry_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    hypothesis_id = row.get("hypothesis_id")
    if not isinstance(hypothesis_id, str) or not hypothesis_id:
        evidence_paths = schema.extract_paths(row) if hasattr(schema, "extract_paths") else []
        return (
            unresolved_family(
                "search_family_id",
                "candidate row is not linked to a concrete target hypothesis",
                evidence_paths,
            ),
            unresolved_family(
                "multiple_testing_family_id",
                "candidate row is not linked to a concrete target hypothesis",
                evidence_paths,
            ),
        )
    registry_row = registry_by_id.get(hypothesis_id)
    if not registry_row:
        return (
            unresolved_family("search_family_id", "hypothesis is absent from registry", []),
            unresolved_family(
                "multiple_testing_family_id",
                "hypothesis is absent from registry",
                [],
            ),
        )
    target_family = registry_row.get("target_family")
    if not isinstance(target_family, str) or not target_family:
        return (
            unresolved_family(
                "search_family_id",
                "registry row has no target_family for deterministic assignment",
                list(row.get("registry_source_reports") or []),
            ),
            unresolved_family(
                "multiple_testing_family_id",
                "registry row has no target_family for deterministic assignment",
                list(row.get("registry_source_reports") or []),
            ),
        )
    profile, markets, years = scope_tokens(registry_row)
    target_token = normalize_token(target_family)
    search_family_id = f"search_family::target_registry::{target_token}::{profile}::{markets}::{years}"
    multiple_testing_family_id = (
        f"multiple_testing_family::target_registry::{profile}::{markets}::{years}::"
        "target_search_candidates"
    )
    evidence_paths = [
        TARGET_REGISTRY.as_posix(),
        TARGET_TRIAL_STATUSES.as_posix(),
        *[str(path) for path in row.get("registry_source_reports") or []],
    ]
    return (
        {
            "status": PROPOSED_FAMILY,
            "field": "search_family_id",
            "value": search_family_id,
            "reason": "deterministic report-local proposal from registry target_family and scope",
            "evidence_paths": list(dict.fromkeys(evidence_paths)),
        },
        {
            "status": PROPOSED_FAMILY,
            "field": "multiple_testing_family_id",
            "value": multiple_testing_family_id,
            "reason": "deterministic report-local proposal grouping target-search alternatives by registry scope",
            "evidence_paths": list(dict.fromkeys(evidence_paths)),
        },
    )


def build_source_disposition_notes(
    *,
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for row in rows:
        if row.get("recommended_disposition") != source_plan.UNRECOVERED:
            continue
        notes.append(
            {
                "hypothesis_id": row.get("hypothesis_id"),
                "missing_source_report_path": row.get("missing_source_report_path"),
                "proposed_disposition": PROPOSED_DISPOSITION,
                "canonical_mutation_allowed": False,
                "proposed_registry_trial_status_note": (
                    "Source JSON remains unrecovered after local filesystem and git-history "
                    "search; preserve the missing path and use registry/trial-status notes as "
                    "secondary disposition context only under separate append-only approval."
                ),
                "primary_source_json_absent_caveat": True,
                "impacted_candidate_rows": list(row.get("impacted_candidate_rows") or []),
            }
        )
    return notes


def build_family_metadata_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    registry_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        search_family, multiple_family = proposed_family_ids(
            row=row,
            registry_by_id=registry_by_id,
        )
        output.append(
            {
                "row_id": row.get("row_id"),
                "row_origin": row.get("row_origin"),
                "trial_id": row.get("trial_id"),
                "hypothesis_id": row.get("hypothesis_id"),
                "stage": row.get("stage"),
                "status": row.get("status"),
                "source_report_resolution": source_resolution_for_row(row),
                "search_family_id": search_family,
                "multiple_testing_family_id": multiple_family,
                "eligible_for_future_append_only_backfill": False,
                "canonical_write_requires_separate_approval": True,
            }
        )
    return output


def family_status_counts(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[field]["status"]) for row in rows).items()))


def validate_write_approvals(approvals: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    expected = {**WRITE_APPROVALS, **NON_APPROVAL}
    mismatches = {
        key: {"expected": expected_value, "actual": approvals.get(key)}
        for key, expected_value in expected.items()
        if approvals.get(key) is not expected_value
    }
    return not mismatches, mismatches


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_input_overrides: Mapping[str, Path] | None = None,
    approval_overrides: Mapping[str, bool] | None = None,
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
    payloads, payload_failures = load_payloads(repo_root=repo_root, paths=paths)
    trial_status_rows, trial_status_errors = read_jsonl_objects(
        resolve_path(repo_root, paths["target_trial_statuses"])
    )
    experiment_rows, experiment_errors = read_jsonl_objects(
        resolve_path(repo_root, paths["experiment_ledger"])
    )
    registry = registry_rows(payloads.get("target_registry"))
    registry_by_id = {
        str(row.get("target_hypothesis_id")): row
        for row in registry
        if row.get("target_hypothesis_id")
    }
    registry_ids = set(registry_by_id)
    unknown_trial_hypotheses = trial.unknown_trial_hypotheses(
        trial_rows=trial_status_rows,
        registry_ids=registry_ids,
    )
    source_report = payloads.get("source_disposition")
    backfill_report = payloads.get("backfill_decision")
    schema_report = payloads.get("schema_remediation")
    schema_rows = candidate_rows(schema_report)
    refs = source_refs(schema_report)
    missing_refs = [ref for ref in refs if ref.get("exists") is False]
    present_refs = [ref for ref in refs if ref.get("exists") is True]
    disposition_notes = build_source_disposition_notes(rows=disposition_rows(source_report))
    family_rows = build_family_metadata_rows(
        rows=schema_rows,
        registry_by_id=registry_by_id,
    )
    search_counts = family_status_counts(family_rows, "search_family_id")
    multiple_counts = family_status_counts(family_rows, "multiple_testing_family_id")
    approvals = {**WRITE_APPROVALS, **NON_APPROVAL}
    if approval_overrides:
        approvals.update(approval_overrides)
    approvals_ok, approval_mismatches = validate_write_approvals(approvals)
    output_rel = rel(reports_root, repo_root)

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {str(item.get("path")) for item in evidence_rows if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required unrecovered-source family-metadata inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel.startswith("reports/master_audit/") and not output_rel.endswith("/"),
        failure=f"invalid report output root: {output_rel}",
        details={"reports_root": output_rel},
    )
    source_summary = source_report.get("summary") if isinstance(source_report, Mapping) else {}
    source_summary = source_summary if isinstance(source_summary, Mapping) else {}
    check(
        checks,
        failures,
        name="source_disposition_passes_and_all_missing_remain_unrecovered",
        passed=source_report is not None
        and source_report.get("status") == source_plan.PASS_STATUS
        and source_summary.get("missing_registry_json_source_report_ref_count")
        == EXPECTED_MISSING_SOURCE_REFS
        and source_summary.get("source_report_restore_executed") is False
        and source_summary.get("ledger_mutation_allowed") is False
        and source_summary.get("disposition_counts", {}).get(source_plan.UNRECOVERED)
        == EXPECTED_UNRECOVERED_SOURCE_REPORTS
        and len(disposition_notes) == EXPECTED_UNRECOVERED_SOURCE_REPORTS,
        failure="upstream source disposition is missing, failed, restored sources, or source counts drifted",
        evidence=[SOURCE_DISPOSITION_REPORT.as_posix()],
        details={
            "status": None if source_report is None else source_report.get("status"),
            "disposition_note_count": len(disposition_notes),
            "disposition_counts": source_summary.get("disposition_counts"),
        },
    )
    check(
        checks,
        failures,
        name="backfill_and_schema_reports_pass_and_remain_blocked",
        passed=backfill_report is not None
        and backfill_report.get("status") == backfill.PASS_STATUS
        and dotted_get(backfill_report, "summary.append_only_backfill_allowed") is False
        and schema_report is not None
        and schema_report.get("status") == schema.PASS_STATUS
        and dotted_get(schema_report, "summary.trial_ledger_search_path_complete") is False
        and dotted_get(schema_report, "summary.statistical_validity_ready") is False
        and dotted_get(schema_report, "summary.model_trust_ready") is False
        and dotted_get(schema_report, "summary.promotion_allowed") is False,
        failure="upstream backfill/schema report is missing, failed, or no longer blocked",
        evidence=[BACKFILL_DECISION_REPORT.as_posix(), SCHEMA_REMEDIATION.as_posix()],
    )
    check(
        checks,
        failures,
        name="current_ledgers_parse_with_expected_counts",
        passed=not trial_status_errors
        and not experiment_errors
        and len(registry) == EXPECTED_REGISTRY_HYPOTHESES
        and len(trial_status_rows) == EXPECTED_TRIAL_STATUS_ROWS
        and len(experiment_rows) == EXPECTED_EXPERIMENT_LEDGER_ROWS
        and not unknown_trial_hypotheses,
        failure="registry, trial-status ledger, or experiment ledger failed parse/count/identity checks",
        evidence=[
            TARGET_REGISTRY.as_posix(),
            TARGET_TRIAL_STATUSES.as_posix(),
            EXPERIMENT_LEDGER.as_posix(),
        ],
        details={
            "registry_hypothesis_count": len(registry),
            "trial_status_row_count": len(trial_status_rows),
            "experiment_ledger_row_count": len(experiment_rows),
            "trial_status_errors": list(trial_status_errors),
            "experiment_errors": list(experiment_errors),
            "unknown_trial_hypotheses": unknown_trial_hypotheses,
        },
    )
    check(
        checks,
        failures,
        name="source_ref_and_candidate_row_counts_preserved",
        passed=len(schema_rows) == EXPECTED_CANDIDATE_ROWS
        and len(refs) == EXPECTED_SOURCE_REFS
        and len(present_refs) == EXPECTED_PRESENT_SOURCE_REFS
        and len(missing_refs) == EXPECTED_MISSING_SOURCE_REFS
        and len(family_rows) == EXPECTED_CANDIDATE_ROWS,
        failure="candidate rows or source-report references drifted",
        details={
            "candidate_row_count": len(schema_rows),
            "family_metadata_row_count": len(family_rows),
            "source_ref_count": len(refs),
            "present_ref_count": len(present_refs),
            "missing_ref_count": len(missing_refs),
        },
    )
    check(
        checks,
        failures,
        name="family_metadata_is_report_local_and_explicit",
        passed=len(search_counts) > 0
        and len(multiple_counts) > 0
        and sum(search_counts.values()) == EXPECTED_CANDIDATE_ROWS
        and sum(multiple_counts.values()) == EXPECTED_CANDIDATE_ROWS
        and all(
            row["search_family_id"]["status"] in {PROPOSED_FAMILY, UNRESOLVED}
            and row["multiple_testing_family_id"]["status"] in {PROPOSED_FAMILY, UNRESOLVED}
            and row["eligible_for_future_append_only_backfill"] is False
            for row in family_rows
        ),
        failure="family metadata was not explicit, report-local, or stayed append-blocked",
        details={
            "search_family_status_counts": search_counts,
            "multiple_testing_family_status_counts": multiple_counts,
        },
    )
    check(
        checks,
        failures,
        name="readiness_write_approvals_and_forbidden_actions_remain_false",
        passed=approvals_ok
        and dotted_get(payloads.get("run_status"), "summary.data_model_commands_executed")
        is False
        and dotted_get(payloads.get("run_status"), "summary.wfa_modeling_executed")
        is False
        and dotted_get(payloads.get("run_status"), "summary.predictions_executed")
        is False
        and dotted_get(payloads.get("run_status"), "summary.provider_network_calls_executed")
        is False
        and dotted_get(
            payloads.get("run_status"),
            "summary.promotion_or_freeze_or_holdout_executed",
        )
        is False
        and dotted_get(payloads.get("run_status"), "summary.paper_or_live_executed")
        is False,
        failure="write approval, readiness flag, or forbidden execution flag was true",
        evidence=[RUN_STATUS.as_posix()],
        details={"approval_mismatches": approval_mismatches, "approvals": approvals},
    )
    for item in evidence_rows:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))
    failures.extend(payload_failures)
    failures.extend(trial_status_errors)
    failures.extend(experiment_errors)
    failures = list(dict.fromkeys(failures))
    status = PASS_STATUS if not failures else FAIL_STATUS
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_unrecovered_source_family_metadata_remediation_report_only",
            "reports_root": output_rel,
            "evidence_mode": "existing_local_source_disposition_schema_registry_ledgers_only",
            "source_report_restore_scope": "none",
            "ledger_mutation_scope": "none",
            "registry_mutation_scope": "none",
            "trial_status_mutation_scope": "none",
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
            "passed_check_count": sum(1 for item in checks if item["status"] == "PASS"),
            "failed_check_count": sum(1 for item in checks if item["status"] == "FAIL"),
            "unrecovered_source_family_metadata_remediation_ready": status == PASS_STATUS,
            "candidate_trial_search_ledger_row_count": len(schema_rows),
            "source_report_disposition_note_count": len(disposition_notes),
            "registry_json_source_report_ref_count": len(refs),
            "present_registry_json_source_report_ref_count": len(present_refs),
            "missing_registry_json_source_report_ref_count": len(missing_refs),
            "unrecovered_source_report_count": len(disposition_notes),
            "search_family_status_counts": search_counts,
            "multiple_testing_family_status_counts": multiple_counts,
            "trial_ledger_search_path_complete": False,
            "pbo_status": "FAIL_MISSING_TRIAL_LOG",
            "deflated_sharpe_status": "FAIL_MISSING_TRIAL_LOG",
            "multiple_testing_status": "FAIL_MISSING_TRIAL_LOG",
            "pbo_applicability_ready": False,
            "deflated_sharpe_applicability_ready": False,
            "multiple_testing_applicability_ready": False,
            "statistical_validity_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
            **{key: approvals[key] for key in WRITE_APPROVALS},
            **{key: approvals[key] for key in NON_APPROVAL},
        },
        "input_evidence": evidence_rows,
        "unrecovered_source_report_disposition_notes": disposition_notes,
        "family_metadata_remediation_rows": family_rows,
        "checks": checks,
        "failures": failures,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "write_approvals": {key: approvals[key] for key in WRITE_APPROVALS},
        "non_approval": {key: approvals[key] for key in NON_APPROVAL},
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Use this report only to plan a separately approved append-only ledger, "
            "registry, and trial-status disposition mutation. Do not treat report-local "
            "family IDs as canonical until that mutation is approved and validated."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Unrecovered-Source Family-Metadata Remediation",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Candidate rows: `{summary['candidate_trial_search_ledger_row_count']}`",
        f"- Unrecovered source reports: `{summary['unrecovered_source_report_count']}`",
        f"- Search-family status counts: `{summary['search_family_status_counts']}`",
        f"- Multiple-testing-family status counts: `{summary['multiple_testing_family_status_counts']}`",
        f"- Append-only backfill allowed: `{summary['append_only_backfill_allowed']}`",
        f"- Ledger mutation executed: `{summary['ledger_mutation_executed']}`",
        f"- Source-report restore executed: `{summary['source_report_restore_executed']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Unrecovered Source Disposition Notes",
        "",
        "| Hypothesis | Missing JSON | Proposed disposition | Canonical mutation allowed |",
        "| --- | --- | --- | --- |",
    ]
    for row in report["unrecovered_source_report_disposition_notes"]:
        lines.append(
            "| `{hypothesis}` | `{path}` | `{disp}` | `{allowed}` |".format(
                hypothesis=row.get("hypothesis_id"),
                path=row.get("missing_source_report_path"),
                disp=row.get("proposed_disposition"),
                allowed=row.get("canonical_mutation_allowed"),
            )
        )
    lines.extend(
        [
            "",
            "## Family Metadata Rows",
            "",
            "| Row | Hypothesis | Search family status | Multiple-testing family status | Eligible |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["family_metadata_remediation_rows"]:
        lines.append(
            "| `{row_id}` | `{hypothesis}` | `{search}` | `{multiple}` | `{eligible}` |".format(
                row_id=row.get("row_id"),
                hypothesis=row.get("hypothesis_id"),
                search=row["search_family_id"].get("status"),
                multiple=row["multiple_testing_family_id"].get("status"),
                eligible=row.get("eligible_for_future_append_only_backfill"),
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Failure |", "| --- | --- | --- |"])
    for item in report["checks"]:
        lines.append(
            "| `{name}` | `{status}` | {failure} |".format(
                name=item["name"],
                status=item["status"],
                failure=item.get("failure") or "",
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
            "- This report did not restore source reports, mutate ledgers, mutate registry, mutate trial statuses, mutate data/model artifacts, run generated evidence commands outside this report, run WFA/modeling, run predictions, refresh Phase 8, call providers/network, promote, freeze artifacts, run final holdout, run paper/live, cleanup, stage, commit, push, or refresh gap maps.",
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
        f"unrecovered_sources={report['summary']['unrecovered_source_report_count']} "
        f"candidate_rows={report['summary']['candidate_trial_search_ledger_row_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
