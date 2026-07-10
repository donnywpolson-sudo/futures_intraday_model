#!/usr/bin/env python3
"""Build a report-only append-only disposition mutation decision.

This command decides whether report-local unrecovered-source dispositions and
family metadata proposals can be canonicalized. It does not mutate ledgers,
registries, trial-status files, source reports, data/model artifacts, or git
state.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import build_master_audit_trial_ledger_search_path_reconciliation as trial
from scripts.validation import build_master_audit_unrecovered_source_family_metadata_remediation as upstream


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_trial_search_append_only_disposition_mutation_decision"
PASS_STATUS = "PASS_MASTER_AUDIT_TRIAL_SEARCH_APPEND_ONLY_DISPOSITION_MUTATION_DECISION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_TRIAL_SEARCH_APPEND_ONLY_DISPOSITION_MUTATION_DECISION_REPORT_ONLY"
MUTATION_DECISION = "BLOCK_CANONICAL_APPEND_ONLY_MUTATION_PENDING_UNRESOLVED_LEGACY_AND_CURRENT_RUN_LINKAGE"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_trial_search_append_only_disposition_mutation_decision_20260710"
)
REPORT_JSON = "master_audit_trial_search_append_only_disposition_mutation_decision.json"
REPORT_MD = "master_audit_trial_search_append_only_disposition_mutation_decision.md"

UPSTREAM_REMEDIATION = upstream.DEFAULT_REPORTS_ROOT / upstream.REPORT_JSON
SOURCE_DISPOSITION = upstream.SOURCE_DISPOSITION_REPORT
BACKFILL_DECISION = upstream.BACKFILL_DECISION_REPORT
SCHEMA_REMEDIATION = upstream.SCHEMA_REMEDIATION
TARGET_REGISTRY = upstream.TARGET_REGISTRY
TARGET_TRIAL_STATUSES = upstream.TARGET_TRIAL_STATUSES
EXPERIMENT_LEDGER = upstream.EXPERIMENT_LEDGER
RUN_STATUS = upstream.RUN_STATUS
ADVERSARIAL_AUDIT = upstream.ADVERSARIAL_AUDIT

REQUIRED_INPUTS = {
    "upstream_remediation": UPSTREAM_REMEDIATION,
    "source_disposition": SOURCE_DISPOSITION,
    "backfill_decision": BACKFILL_DECISION,
    "schema_remediation": SCHEMA_REMEDIATION,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

EXPECTED_CANDIDATE_ROWS = 27
EXPECTED_SOURCE_NOTES = 14
EXPECTED_PROPOSED_FAMILY_ROWS = 22
EXPECTED_UNRESOLVED_ROWS = 5
EXPECTED_REGISTRY_HYPOTHESES = 17
EXPECTED_TRIAL_STATUS_ROWS = 22
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4

WRITE_APPROVALS = {
    "canonical_append_only_mutation_allowed": False,
    "registry_mutation_allowed": False,
    "trial_status_mutation_allowed": False,
    "experiment_ledger_mutation_allowed": False,
    "source_report_restore_allowed": False,
    "report_refresh_allowed": False,
    "ledger_mutation_executed": False,
    "registry_mutation_executed": False,
    "trial_status_mutation_executed": False,
    "experiment_ledger_mutation_executed": False,
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
        "upstream_remediation": {
            "status": "status",
            "candidate_rows": "summary.candidate_trial_search_ledger_row_count",
            "source_notes": "summary.source_report_disposition_note_count",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "source_disposition": {"status": "status"},
        "backfill_decision": {"status": "status", "decision": "summary.backfill_decision"},
        "schema_remediation": {"status": "status"},
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


def source_notes(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = (
        payload.get("unrecovered_source_report_disposition_notes")
        if isinstance(payload, Mapping)
        else []
    )
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def family_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = payload.get("family_metadata_remediation_rows") if isinstance(payload, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def family_status(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    if isinstance(value, Mapping):
        return str(value.get("status") or "")
    return ""


def family_value(row: Mapping[str, Any], field: str) -> Any:
    value = row.get(field)
    return value.get("value") if isinstance(value, Mapping) else None


def linked_family_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if family_status(row, "search_family_id") == upstream.PROPOSED_FAMILY
        and family_status(row, "multiple_testing_family_id") == upstream.PROPOSED_FAMILY
    ]


def unresolved_family_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if family_status(row, "search_family_id") == upstream.UNRESOLVED
        or family_status(row, "multiple_testing_family_id") == upstream.UNRESOLVED
    ]


def build_draft_payload(
    *,
    notes: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    linked_rows = linked_family_rows(rows)
    unresolved_rows = unresolved_family_rows(rows)
    return {
        "canonical_write_allowed_by_this_report": False,
        "registry_disposition_update_candidates": [
            {
                "hypothesis_id": note.get("hypothesis_id"),
                "missing_source_report_path": note.get("missing_source_report_path"),
                "append_only_note": note.get("proposed_registry_trial_status_note"),
                "primary_source_json_absent_caveat": note.get("primary_source_json_absent_caveat"),
                "canonical_mutation_allowed": False,
            }
            for note in notes
        ],
        "trial_status_append_candidates": [
            {
                "trial_id": row.get("trial_id"),
                "hypothesis_id": row.get("hypothesis_id"),
                "stage": "master_audit_append_only_disposition_metadata",
                "status": "BLOCKED_REPORT_LOCAL_PROPOSAL",
                "source_trial_stage": row.get("stage"),
                "source_trial_status": row.get("status"),
                "proposed_search_family_id": family_value(row, "search_family_id"),
                "proposed_multiple_testing_family_id": family_value(
                    row,
                    "multiple_testing_family_id",
                ),
                "canonical_mutation_allowed": False,
            }
            for row in linked_rows
            if row.get("row_origin") == "target_trial_statuses"
        ],
        "experiment_ledger_append_candidates": [],
        "current_wfa_phase8_statistical_append_candidates": [],
        "blocked_unresolved_rows": [
            {
                "row_id": row.get("row_id"),
                "row_origin": row.get("row_origin"),
                "trial_id": row.get("trial_id"),
                "hypothesis_id": row.get("hypothesis_id"),
                "stage": row.get("stage"),
                "status": row.get("status"),
                "search_family_status": family_status(row, "search_family_id"),
                "multiple_testing_family_status": family_status(
                    row,
                    "multiple_testing_family_id",
                ),
            }
            for row in unresolved_rows
        ],
    }


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
    registry_ids = {
        str(row.get("target_hypothesis_id"))
        for row in registry
        if row.get("target_hypothesis_id")
    }
    unknown_trial_hypotheses = trial.unknown_trial_hypotheses(
        trial_rows=trial_status_rows,
        registry_ids=registry_ids,
    )
    upstream_report = payloads.get("upstream_remediation")
    upstream_summary = upstream_report.get("summary") if isinstance(upstream_report, Mapping) else {}
    upstream_summary = upstream_summary if isinstance(upstream_summary, Mapping) else {}
    rows = family_rows(upstream_report)
    notes = source_notes(upstream_report)
    linked_rows = linked_family_rows(rows)
    unresolved_rows = unresolved_family_rows(rows)
    draft_payload = build_draft_payload(notes=notes, rows=rows)
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
        failure=f"missing required append-only mutation-decision inputs: {missing_paths}",
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
        name="upstream_remediation_passes_and_counts_preserved",
        passed=upstream_report is not None
        and upstream_report.get("status") == upstream.PASS_STATUS
        and upstream_summary.get("candidate_trial_search_ledger_row_count")
        == EXPECTED_CANDIDATE_ROWS
        and upstream_summary.get("source_report_disposition_note_count")
        == EXPECTED_SOURCE_NOTES
        and upstream_summary.get("search_family_status_counts", {}).get(upstream.PROPOSED_FAMILY)
        == EXPECTED_PROPOSED_FAMILY_ROWS
        and upstream_summary.get("search_family_status_counts", {}).get(upstream.UNRESOLVED)
        == EXPECTED_UNRESOLVED_ROWS
        and upstream_summary.get("multiple_testing_family_status_counts", {}).get(
            upstream.PROPOSED_FAMILY
        )
        == EXPECTED_PROPOSED_FAMILY_ROWS
        and upstream_summary.get("multiple_testing_family_status_counts", {}).get(
            upstream.UNRESOLVED
        )
        == EXPECTED_UNRESOLVED_ROWS
        and upstream_summary.get("source_report_restore_executed") is False,
        failure="upstream unrecovered-source family-metadata report is missing, failed, restored sources, or counts drifted",
        evidence=[UPSTREAM_REMEDIATION.as_posix()],
        details={
            "status": None if upstream_report is None else upstream_report.get("status"),
            "candidate_row_count": len(rows),
            "source_note_count": len(notes),
        },
    )
    check(
        checks,
        failures,
        name="supporting_reports_pass_and_remain_blocked",
        passed=payloads.get("source_disposition", {}).get("status") == upstream.source_plan.PASS_STATUS
        and payloads.get("backfill_decision", {}).get("status") == upstream.backfill.PASS_STATUS
        and payloads.get("schema_remediation", {}).get("status") == upstream.schema.PASS_STATUS
        and dotted_get(payloads.get("backfill_decision"), "summary.append_only_backfill_allowed")
        is False
        and dotted_get(payloads.get("schema_remediation"), "summary.statistical_validity_ready")
        is False
        and dotted_get(payloads.get("schema_remediation"), "summary.model_trust_ready")
        is False
        and dotted_get(payloads.get("schema_remediation"), "summary.promotion_allowed")
        is False,
        failure="supporting source/backfill/schema reports are missing, failed, or no longer blocked",
        evidence=[
            SOURCE_DISPOSITION.as_posix(),
            BACKFILL_DECISION.as_posix(),
            SCHEMA_REMEDIATION.as_posix(),
        ],
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
        name="canonical_mutation_decision_remains_blocked",
        passed=MUTATION_DECISION.startswith("BLOCK_")
        and len(rows) == EXPECTED_CANDIDATE_ROWS
        and len(notes) == EXPECTED_SOURCE_NOTES
        and len(linked_rows) == EXPECTED_PROPOSED_FAMILY_ROWS
        and len(unresolved_rows) == EXPECTED_UNRESOLVED_ROWS
        and len(draft_payload["experiment_ledger_append_candidates"]) == 0
        and len(draft_payload["current_wfa_phase8_statistical_append_candidates"]) == 0
        and len(draft_payload["blocked_unresolved_rows"]) == EXPECTED_UNRESOLVED_ROWS,
        failure="canonical mutation became append-ready while unresolved rows remain",
        details={
            "decision": MUTATION_DECISION,
            "linked_row_count": len(linked_rows),
            "unresolved_row_count": len(unresolved_rows),
        },
    )
    check(
        checks,
        failures,
        name="readiness_write_approvals_and_forbidden_actions_remain_false",
        passed=approvals_ok
        and upstream_summary.get("statistical_validity_ready") is False
        and upstream_summary.get("model_trust_ready") is False
        and upstream_summary.get("promotion_allowed") is False
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
            "operation": "master_audit_trial_search_append_only_disposition_mutation_decision_report_only",
            "reports_root": output_rel,
            "evidence_mode": "existing_local_unrecovered_source_family_metadata_only",
            "ledger_mutation_scope": "none",
            "registry_mutation_scope": "none",
            "trial_status_mutation_scope": "none",
            "source_report_restore_scope": "none",
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
            "mutation_decision": MUTATION_DECISION,
            "candidate_trial_search_ledger_row_count": len(rows),
            "source_report_disposition_note_count": len(notes),
            "proposed_family_metadata_row_count": len(linked_rows),
            "unresolved_family_metadata_row_count": len(unresolved_rows),
            "registry_disposition_update_candidate_count": len(
                draft_payload["registry_disposition_update_candidates"]
            ),
            "trial_status_append_candidate_count": len(
                draft_payload["trial_status_append_candidates"]
            ),
            "experiment_ledger_append_candidate_count": 0,
            "current_wfa_phase8_statistical_append_candidate_count": 0,
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
        "draft_only_mutation_payload": draft_payload,
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
            "Resolve or explicitly exclude the four legacy experiment-ledger rows and "
            "the current WFA/Phase8/statistical row before proposing any canonical "
            "append-only ledger, registry, or trial-status mutation."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    payload = report["draft_only_mutation_payload"]
    lines = [
        "# Master Audit Trial/Search Append-Only Disposition Mutation Decision",
        "",
        f"- Status: `{report['status']}`",
        f"- Mutation decision: `{summary['mutation_decision']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Candidate rows: `{summary['candidate_trial_search_ledger_row_count']}`",
        f"- Proposed family metadata rows: `{summary['proposed_family_metadata_row_count']}`",
        f"- Unresolved family metadata rows: `{summary['unresolved_family_metadata_row_count']}`",
        f"- Registry disposition candidates: `{summary['registry_disposition_update_candidate_count']}`",
        f"- Trial-status append candidates: `{summary['trial_status_append_candidate_count']}`",
        f"- Canonical append-only mutation allowed: `{summary['canonical_append_only_mutation_allowed']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Blocked Unresolved Rows",
        "",
        "| Row | Origin | Trial | Stage | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["blocked_unresolved_rows"]:
        lines.append(
            "| `{row}` | `{origin}` | `{trial}` | `{stage}` | `{status}` |".format(
                row=row.get("row_id"),
                origin=row.get("row_origin"),
                trial=row.get("trial_id"),
                stage=row.get("stage"),
                status=row.get("status"),
            )
        )
    lines.extend(
        [
            "",
            "## Draft-Only Candidate Counts",
            "",
            f"- Registry disposition update candidates: `{len(payload['registry_disposition_update_candidates'])}`",
            f"- Trial-status append candidates: `{len(payload['trial_status_append_candidates'])}`",
            f"- Experiment-ledger append candidates: `{len(payload['experiment_ledger_append_candidates'])}`",
            f"- Current WFA/Phase8/statistical append candidates: `{len(payload['current_wfa_phase8_statistical_append_candidates'])}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Failure |",
            "| --- | --- | --- |",
        ]
    )
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
            "- This decision report did not mutate ledgers, registry, trial statuses, reports outside this output pair, source reports, data/model artifacts, Phase 8 outputs, provider state, promotion state, artifact freeze state, final holdout state, paper/live state, cleanup state, staging, commits, pushes, or gap maps.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / REPORT_JSON
    md_path = reports_root / REPORT_MD
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.parent.mkdir(parents=True, exist_ok=True)
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
    reports_root = resolve_path(repo_root, args.reports_root).resolve()
    report = build_report(repo_root=repo_root, reports_root=reports_root)
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"decision={report['summary']['mutation_decision']} "
        f"unresolved_rows={report['summary']['unresolved_family_metadata_row_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
