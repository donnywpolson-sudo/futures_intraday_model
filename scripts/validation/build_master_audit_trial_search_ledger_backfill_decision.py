#!/usr/bin/env python3
"""Build a report-only trial/search ledger backfill decision.

This command consumes the schema-remediation map and current local ledger
evidence. It does not mutate experiment ledgers, target registries,
trial-status ledgers, reports, data, models, predictions, provider state,
promotion state, staging, commits, or remotes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import build_master_audit_trial_ledger_search_path_reconciliation as trial
from scripts.validation import build_master_audit_trial_search_ledger_schema_remediation_plan as schema


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_trial_search_ledger_backfill_decision"
PASS_STATUS = "PASS_MASTER_AUDIT_TRIAL_SEARCH_LEDGER_BACKFILL_DECISION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_TRIAL_SEARCH_LEDGER_BACKFILL_DECISION_REPORT_ONLY"
BACKFILL_DECISION = "BLOCK_APPEND_ONLY_BACKFILL_PENDING_MISSING_SOURCE_REPORT_RECOVERY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_trial_search_ledger_backfill_decision_20260710"
)
REPORT_JSON = "master_audit_trial_search_ledger_backfill_decision.json"
REPORT_MD = "master_audit_trial_search_ledger_backfill_decision.md"

SCHEMA_REMEDIATION = schema.DEFAULT_REPORTS_ROOT / schema.REPORT_JSON
EXPERIMENT_LEDGER = schema.EXPERIMENT_LEDGER
TARGET_REGISTRY = schema.TARGET_REGISTRY
TARGET_TRIAL_STATUSES = schema.TARGET_TRIAL_STATUSES
RUN_STATUS = schema.RUN_STATUS
ADVERSARIAL_AUDIT = schema.ADVERSARIAL_AUDIT

REQUIRED_INPUTS = {
    "schema_remediation": SCHEMA_REMEDIATION,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

EXPECTED_CANDIDATE_ROWS = 27
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4
EXPECTED_REGISTRY_HYPOTHESES = 17
EXPECTED_TRIAL_STATUS_ROWS = 22
EXPECTED_SOURCE_REFS = 21
EXPECTED_PRESENT_SOURCE_REFS = 7
EXPECTED_MISSING_SOURCE_REFS = 14
EXPECTED_UNRESOLVED_SEARCH_FAMILY = 27
EXPECTED_UNRESOLVED_MULTIPLE_TESTING_FAMILY = 27
REQUIRED_FIELDS = tuple(schema.REQUIRED_FIELDS)

WRITE_APPROVALS = {
    "append_only_backfill_allowed": False,
    "write_schema_complete_rows_allowed": False,
    "write_unresolved_marker_rows_allowed": False,
    "ledger_mutation_executed": False,
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
        "schema_remediation": {
            "status": "status",
            "candidate_rows": "summary.candidate_trial_search_ledger_row_count",
            "missing_source_refs": "summary.missing_registry_json_source_report_ref_count",
            "search_unresolved": "summary.unresolved_field_counts.search_family_id",
            "multiple_unresolved": "summary.unresolved_field_counts.multiple_testing_family_id",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
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


def is_unresolved(value: Any) -> bool:
    return schema.is_unresolved(value)


def extract_evidence_paths(value: Any) -> set[str]:
    paths: set[str] = set()
    if isinstance(value, str):
        if "/" in value or "\\" in value:
            paths.add(value.replace("\\", "/"))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"evidence_paths", "registry_source_reports", "path"}:
                paths.update(extract_evidence_paths(item))
            elif isinstance(item, (Mapping, list, tuple, str)):
                paths.update(extract_evidence_paths(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            paths.update(extract_evidence_paths(item))
    return paths


def missing_required_fields(row: Mapping[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if field not in row]


def unresolved_required_fields(row: Mapping[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if is_unresolved(row.get(field))]


def source_report_refs(schema_report: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    refs = schema_report.get("source_report_reference_inventory") if isinstance(schema_report, Mapping) else []
    return [ref for ref in refs if isinstance(ref, Mapping)] if isinstance(refs, list) else []


def candidate_rows(schema_report: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = schema_report.get("candidate_trial_search_ledger_rows") if isinstance(schema_report, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def row_decisions(
    *,
    rows: Sequence[Mapping[str, Any]],
    refs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    missing_source_paths = {
        str(ref.get("path")).replace("\\", "/")
        for ref in refs
        if ref.get("exists") is False and ref.get("path")
    }
    decisions: list[dict[str, Any]] = []
    for row in rows:
        unresolved_fields = unresolved_required_fields(row)
        absent_fields = missing_required_fields(row)
        row_paths = extract_evidence_paths(row)
        missing_row_sources = sorted(row_paths & missing_source_paths)
        blocked_by_missing_search_family = is_unresolved(row.get("search_family_id"))
        blocked_by_missing_multiple = is_unresolved(row.get("multiple_testing_family_id"))
        blocked_by_missing_source = bool(missing_row_sources)
        eligible = not (
            unresolved_fields
            or absent_fields
            or blocked_by_missing_source
            or blocked_by_missing_search_family
            or blocked_by_missing_multiple
        )
        decisions.append(
            {
                "row_id": row.get("row_id"),
                "row_origin": row.get("row_origin"),
                "trial_id": row.get("trial_id"),
                "hypothesis_id": row.get("hypothesis_id"),
                "stage": row.get("stage"),
                "status": row.get("status"),
                "eligible_for_future_backfill": eligible,
                "blocked_by_missing_source_report": blocked_by_missing_source,
                "blocked_by_missing_search_family_id": blocked_by_missing_search_family,
                "blocked_by_missing_multiple_testing_family_id": blocked_by_missing_multiple,
                "missing_source_report_paths": missing_row_sources,
                "unresolved_required_fields": unresolved_fields,
                "missing_required_fields": absent_fields,
            }
        )
    return decisions


def validate_write_approvals(approvals: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    expected = {**WRITE_APPROVALS, **NON_APPROVAL}
    mismatches = {
        key: {"expected": expected_value, "actual": approvals.get(key)}
        for key, expected_value in expected.items()
        if approvals.get(key) is not expected_value
    }
    return not mismatches, mismatches


def registry_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    return trial.registry_hypotheses(payload)


def required_summary(schema_report: Mapping[str, Any] | None) -> Mapping[str, Any]:
    summary = schema_report.get("summary") if isinstance(schema_report, Mapping) else {}
    return summary if isinstance(summary, Mapping) else {}


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
    experiment_rows, experiment_errors = read_jsonl_objects(
        resolve_path(repo_root, paths["experiment_ledger"])
    )
    trial_status_rows, trial_status_errors = read_jsonl_objects(
        resolve_path(repo_root, paths["target_trial_statuses"])
    )
    registry = registry_rows(payloads.get("target_registry"))
    registry_ids = {
        str(row.get("target_hypothesis_id"))
        for row in registry
        if row.get("target_hypothesis_id")
    }
    unknown_trial_hypotheses = trial.unknown_trial_hypotheses(
        trial_rows=trial_status_rows,
        registry_ids=registry_ids,
    )
    schema_report = payloads.get("schema_remediation")
    summary = required_summary(schema_report)
    refs = source_report_refs(schema_report)
    candidates = candidate_rows(schema_report)
    decisions = row_decisions(rows=candidates, refs=refs)
    approvals = {**WRITE_APPROVALS, **NON_APPROVAL}
    if approval_overrides:
        approvals.update(approval_overrides)
    approvals_ok, approval_mismatches = validate_write_approvals(approvals)
    output_rel = rel(reports_root, repo_root)

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {
        str(item.get("path")) for item in evidence_rows if item.get("exists")
    }
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required backfill-decision inputs: {missing_paths}",
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
    check(
        checks,
        failures,
        name="schema_remediation_passes_and_remains_blocked",
        passed=schema_report is not None
        and schema_report.get("status") == schema.PASS_STATUS
        and summary.get("trial_ledger_search_path_complete") is False
        and summary.get("pbo_status") == "FAIL_MISSING_TRIAL_LOG"
        and summary.get("deflated_sharpe_status") == "FAIL_MISSING_TRIAL_LOG"
        and summary.get("multiple_testing_status") == "FAIL_MISSING_TRIAL_LOG"
        and summary.get("pbo_applicability_ready") is False
        and summary.get("deflated_sharpe_applicability_ready") is False
        and summary.get("multiple_testing_applicability_ready") is False
        and summary.get("statistical_validity_ready") is False
        and summary.get("model_trust_ready") is False
        and summary.get("promotion_allowed") is False,
        failure="schema-remediation report is missing, failed, or no longer blocked",
        evidence=[SCHEMA_REMEDIATION.as_posix()],
        details={"status": None if schema_report is None else schema_report.get("status")},
    )
    row_missing_fields = [
        {"row_id": row.get("row_id"), "missing_required_fields": missing_required_fields(row)}
        for row in candidates
        if missing_required_fields(row)
    ]
    check(
        checks,
        failures,
        name="candidate_rows_present_and_schema_complete",
        passed=len(candidates) == EXPECTED_CANDIDATE_ROWS and not row_missing_fields,
        failure="candidate rows are missing, count drifted, or required fields are absent",
        details={
            "candidate_row_count": len(candidates),
            "expected_candidate_row_count": EXPECTED_CANDIDATE_ROWS,
            "row_missing_fields": row_missing_fields,
        },
    )
    check(
        checks,
        failures,
        name="current_ledgers_parse_with_expected_counts",
        passed=not experiment_errors
        and not trial_status_errors
        and len(experiment_rows) == EXPECTED_EXPERIMENT_LEDGER_ROWS
        and len(registry) == EXPECTED_REGISTRY_HYPOTHESES
        and len(trial_status_rows) == EXPECTED_TRIAL_STATUS_ROWS
        and not unknown_trial_hypotheses,
        failure="experiment ledger, target registry, or target trial statuses failed parse/count/identity checks",
        evidence=[
            EXPERIMENT_LEDGER.as_posix(),
            TARGET_REGISTRY.as_posix(),
            TARGET_TRIAL_STATUSES.as_posix(),
        ],
        details={
            "experiment_row_count": len(experiment_rows),
            "registry_hypothesis_count": len(registry),
            "trial_status_row_count": len(trial_status_rows),
            "experiment_errors": list(experiment_errors),
            "trial_status_errors": list(trial_status_errors),
            "unknown_trial_hypotheses": unknown_trial_hypotheses,
        },
    )
    present_refs = [ref for ref in refs if ref.get("exists") is True]
    missing_refs = [ref for ref in refs if ref.get("exists") is False]
    check(
        checks,
        failures,
        name="source_report_reference_counts_preserved",
        passed=len(refs) == EXPECTED_SOURCE_REFS
        and len(present_refs) == EXPECTED_PRESENT_SOURCE_REFS
        and len(missing_refs) == EXPECTED_MISSING_SOURCE_REFS
        and summary.get("registry_json_source_report_ref_count") == EXPECTED_SOURCE_REFS
        and summary.get("present_registry_json_source_report_ref_count")
        == EXPECTED_PRESENT_SOURCE_REFS
        and summary.get("missing_registry_json_source_report_ref_count")
        == EXPECTED_MISSING_SOURCE_REFS,
        failure="source-report reference counts drifted from schema-remediation evidence",
        details={
            "source_ref_count": len(refs),
            "present_source_ref_count": len(present_refs),
            "missing_source_ref_count": len(missing_refs),
            "missing_source_report_paths": [ref.get("path") for ref in missing_refs],
        },
    )
    unresolved_counts = summary.get("unresolved_field_counts")
    unresolved_counts = unresolved_counts if isinstance(unresolved_counts, Mapping) else {}
    check(
        checks,
        failures,
        name="search_and_multiple_testing_family_ids_remain_unresolved",
        passed=unresolved_counts.get("search_family_id") == EXPECTED_UNRESOLVED_SEARCH_FAMILY
        and unresolved_counts.get("multiple_testing_family_id")
        == EXPECTED_UNRESOLVED_MULTIPLE_TESTING_FAMILY,
        failure="search or multiple-testing family unresolved counts changed",
        details={"unresolved_field_counts": dict(unresolved_counts)},
    )
    check(
        checks,
        failures,
        name="backfill_decision_is_blocked_not_append_ready",
        passed=BACKFILL_DECISION
        == "BLOCK_APPEND_ONLY_BACKFILL_PENDING_MISSING_SOURCE_REPORT_RECOVERY"
        and all(decision.get("eligible_for_future_backfill") is False for decision in decisions)
        and any(decision.get("blocked_by_missing_source_report") for decision in decisions)
        and all(decision.get("blocked_by_missing_search_family_id") for decision in decisions)
        and all(
            decision.get("blocked_by_missing_multiple_testing_family_id")
            for decision in decisions
        ),
        failure="backfill decision allowed append-ready rows while blockers remain",
        details={
            "backfill_decision": BACKFILL_DECISION,
            "eligible_row_count": sum(
                1 for decision in decisions if decision.get("eligible_for_future_backfill")
            ),
            "row_decision_count": len(decisions),
        },
    )
    check(
        checks,
        failures,
        name="write_approvals_and_forbidden_actions_remain_false",
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
        failure="write approval or forbidden execution flag was true",
        evidence=[RUN_STATUS.as_posix()],
        details={"approval_mismatches": approval_mismatches, "approvals": approvals},
    )
    for item in evidence_rows:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))
    failures.extend(payload_failures)
    failures.extend(experiment_errors)
    failures.extend(trial_status_errors)
    failures = list(dict.fromkeys(failures))
    status = PASS_STATUS if not failures else FAIL_STATUS
    row_decision_counts = dict(
        sorted(
            Counter(
                "eligible" if item["eligible_for_future_backfill"] else "blocked"
                for item in decisions
            ).items()
        )
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_trial_search_ledger_backfill_decision_report_only",
            "reports_root": output_rel,
            "evidence_mode": "existing_local_schema_remediation_and_ledgers_only",
            "ledger_mutation_scope": "none",
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
            "backfill_decision": BACKFILL_DECISION,
            "append_only_backfill_allowed": approvals["append_only_backfill_allowed"],
            "write_schema_complete_rows_allowed": approvals[
                "write_schema_complete_rows_allowed"
            ],
            "write_unresolved_marker_rows_allowed": approvals[
                "write_unresolved_marker_rows_allowed"
            ],
            "ledger_mutation_executed": approvals["ledger_mutation_executed"],
            "candidate_trial_search_ledger_row_count": len(candidates),
            "row_decision_counts": row_decision_counts,
            "eligible_for_future_backfill_count": row_decision_counts.get("eligible", 0),
            "blocked_row_count": row_decision_counts.get("blocked", 0),
            "registry_json_source_report_ref_count": len(refs),
            "present_registry_json_source_report_ref_count": len(present_refs),
            "missing_registry_json_source_report_ref_count": len(missing_refs),
            "missing_source_report_paths": [ref.get("path") for ref in missing_refs],
            "unresolved_field_counts": dict(unresolved_counts),
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
            **{key: value for key, value in approvals.items() if key in NON_APPROVAL},
        },
        "input_evidence": evidence_rows,
        "row_level_backfill_decisions": decisions,
        "source_report_reference_inventory": list(refs),
        "future_unblock_checklist": {
            "missing_registry_json_source_report_ref_count": 0,
            "unresolved_search_family_id_count": 0,
            "unresolved_multiple_testing_family_id_count": 0,
            "complete_evidence_paths_required": True,
            "separate_append_only_mutation_approval_required": True,
            "ledger_mutation_allowed_by_this_report": False,
        },
        "checks": checks,
        "failures": failures,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "write_approvals": {
            key: approvals[key]
            for key in WRITE_APPROVALS
        },
        "non_approval": {key: approvals[key] for key in NON_APPROVAL},
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan source-report recovery or explicit disposition before any append-only "
            "ledger backfill. Do not write unresolved-marker rows into canonical ledgers."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Trial/Search Ledger Backfill Decision",
        "",
        f"- Status: `{report['status']}`",
        f"- Backfill decision: `{summary['backfill_decision']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Candidate rows: `{summary['candidate_trial_search_ledger_row_count']}`",
        f"- Eligible rows: `{summary['eligible_for_future_backfill_count']}`",
        f"- Blocked rows: `{summary['blocked_row_count']}`",
        f"- Missing registry JSON source reports: `{summary['missing_registry_json_source_report_ref_count']}`",
        f"- Append-only backfill allowed: `{summary['append_only_backfill_allowed']}`",
        f"- Write unresolved marker rows allowed: `{summary['write_unresolved_marker_rows_allowed']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Missing Source Reports",
        "",
    ]
    missing = summary.get("missing_source_report_paths") or []
    lines.extend([f"- `{path}`" for path in missing] or ["- None"])
    lines.extend(
        [
            "",
            "## Row-Level Decisions",
            "",
            "| Row | Origin | Eligible | Missing source | Missing search family | Missing multiple-testing family |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in report["row_level_backfill_decisions"]:
        lines.append(
            "| `{row}` | `{origin}` | `{eligible}` | `{missing_source}` | `{missing_search}` | `{missing_multiple}` |".format(
                row=item.get("row_id"),
                origin=item.get("row_origin"),
                eligible=item.get("eligible_for_future_backfill"),
                missing_source=item.get("blocked_by_missing_source_report"),
                missing_search=item.get("blocked_by_missing_search_family_id"),
                missing_multiple=item.get("blocked_by_missing_multiple_testing_family_id"),
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
    lines.extend(["", "## Future Unblock Checklist", ""])
    for key, value in report["future_unblock_checklist"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This decision report did not mutate ledgers, registry, trial statuses, reports, data, models, predictions, Phase 8 outputs, provider state, promotion state, artifact freeze state, final holdout state, paper/live state, cleanup state, staging, commits, pushes, or gap maps.",
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
        f"decision={report['summary']['backfill_decision']} "
        f"eligible_rows={report['summary']['eligible_for_future_backfill_count']} "
        f"blocked_rows={report['summary']['blocked_row_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
