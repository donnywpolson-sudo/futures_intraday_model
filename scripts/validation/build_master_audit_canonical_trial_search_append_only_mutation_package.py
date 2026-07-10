#!/usr/bin/env python3
"""Build a report-only canonical trial/search append-only mutation package.

This command packages existing report-local registry notes, trial-status family
metadata rows, and exclusion dispositions into a separately approvable mutation
plan. It does not mutate ledgers, registries, trial-status files, reports
outside its output pair, data/model artifacts, or git state.
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
from scripts.validation import (
    build_master_audit_trial_search_append_only_disposition_mutation_decision as append_decision,
)
from scripts.validation import (
    build_master_audit_unrecovered_source_family_metadata_remediation as family_remediation,
)
from scripts.validation import (
    build_master_audit_unresolved_row_linkage_exclusion_disposition as exclusion_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_canonical_trial_search_append_only_mutation_package"
PASS_STATUS = "PASS_MASTER_AUDIT_CANONICAL_TRIAL_SEARCH_APPEND_ONLY_MUTATION_PACKAGE_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_CANONICAL_TRIAL_SEARCH_APPEND_ONLY_MUTATION_PACKAGE_REPORT_ONLY"
PACKAGE_DECISION = "READY_FOR_SEPARATE_APPEND_ONLY_MUTATION_APPROVAL_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_canonical_trial_search_append_only_mutation_package_20260710"
)
REPORT_JSON = "master_audit_canonical_trial_search_append_only_mutation_package.json"
REPORT_MD = "master_audit_canonical_trial_search_append_only_mutation_package.md"

UNRESOLVED_DISPOSITION = exclusion_plan.DEFAULT_REPORTS_ROOT / exclusion_plan.REPORT_JSON
APPEND_DECISION = append_decision.DEFAULT_REPORTS_ROOT / append_decision.REPORT_JSON
FAMILY_REMEDIATION = family_remediation.DEFAULT_REPORTS_ROOT / family_remediation.REPORT_JSON
TARGET_REGISTRY = append_decision.TARGET_REGISTRY
TARGET_TRIAL_STATUSES = append_decision.TARGET_TRIAL_STATUSES
EXPERIMENT_LEDGER = append_decision.EXPERIMENT_LEDGER
RUN_STATUS = append_decision.RUN_STATUS
ADVERSARIAL_AUDIT = append_decision.ADVERSARIAL_AUDIT

REQUIRED_INPUTS = {
    "unresolved_disposition": UNRESOLVED_DISPOSITION,
    "append_decision": APPEND_DECISION,
    "family_remediation": FAMILY_REMEDIATION,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

EXPECTED_REGISTRY_NOTE_CANDIDATES = 14
EXPECTED_TRIAL_STATUS_APPEND_CANDIDATES = 22
EXPECTED_EXCLUSION_CANDIDATES = 5
EXPECTED_REGISTRY_HYPOTHESES = 17
EXPECTED_TRIAL_STATUS_ROWS = 22
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4

WRITE_APPROVALS = {
    "append_only_mutation_command_approved": False,
    "canonical_mutation_executed": False,
    "registry_mutation_executed": False,
    "trial_status_mutation_executed": False,
    "experiment_ledger_mutation_executed": False,
    "report_refresh_allowed": False,
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
        "unresolved_disposition": {
            "status": "status",
            "exclusions": "summary.exclusion_candidate_count",
            "linkable_rows": "summary.linkable_row_count",
        },
        "append_decision": {
            "status": "status",
            "registry_notes": "summary.registry_disposition_update_candidate_count",
            "trial_status_candidates": "summary.trial_status_append_candidate_count",
        },
        "family_remediation": {
            "status": "status",
            "family_rows": "summary.candidate_trial_search_ledger_row_count",
            "source_notes": "summary.source_report_disposition_note_count",
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


def append_payload(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    draft = payload.get("draft_only_mutation_payload") if isinstance(payload, Mapping) else {}
    return draft if isinstance(draft, Mapping) else {}


def registry_note_source_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = append_payload(payload).get("registry_disposition_update_candidates")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def trial_status_source_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = append_payload(payload).get("trial_status_append_candidates")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def exclusion_source_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = (
        payload.get("unresolved_row_exclusion_dispositions")
        if isinstance(payload, Mapping)
        else []
    )
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def candidate_trial_id(source_trial_id: Any) -> str:
    return f"{source_trial_id}_master_audit_family_metadata_20260710"


def build_registry_note_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "hypothesis_id": row.get("hypothesis_id"),
            "mutation_type": "APPEND_REGISTRY_DISPOSITION_NOTE",
            "missing_source_report_path": row.get("missing_source_report_path"),
            "note": row.get("append_only_note"),
            "primary_source_json_absent_caveat": row.get("primary_source_json_absent_caveat"),
            "canonical_mutation_executed": False,
            "status_change_allowed": False,
            "wfa_allowed_change_allowed": False,
            "source_report_rewrite_allowed": False,
            "next_allowed_actions_change_allowed": False,
        }
        for row in rows
    ]


def build_trial_status_append_candidates(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        source_trial_id = row.get("trial_id")
        output.append(
            {
                "schema_version": 1,
                "trial_id": candidate_trial_id(source_trial_id),
                "hypothesis_id": row.get("hypothesis_id"),
                "stage": "master_audit_family_metadata_append_only_disposition",
                "status": "BLOCKED_REPORT_LOCAL_METADATA_CANONICALIZATION",
                "source_trial_id": source_trial_id,
                "source_trial_stage": row.get("source_trial_stage"),
                "source_trial_status": row.get("source_trial_status"),
                "search_family_id": row.get("proposed_search_family_id"),
                "multiple_testing_family_id": row.get("proposed_multiple_testing_family_id"),
                "evidence": [
                    UNRESOLVED_DISPOSITION.as_posix(),
                    APPEND_DECISION.as_posix(),
                    FAMILY_REMEDIATION.as_posix(),
                ],
                "notes": (
                    "Append-only Master Audit metadata row; records search-family and "
                    "multiple-testing-family IDs without approving WFA/modeling, "
                    "statistical validity, model trust, promotion, paper/live, or production."
                ),
                "canonical_mutation_executed": False,
            }
        )
    return output


def build_exclusion_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row_id": row.get("row_id"),
            "row_origin": row.get("row_origin"),
            "trial_id": row.get("trial_id"),
            "mutation_type": "RECORD_REPORT_LOCAL_EXCLUSION_ONLY",
            "disposition": row.get("disposition"),
            "disposition_reason": row.get("disposition_reason"),
            "evidence_paths": list(row.get("evidence_paths") or []),
            "append_to_trial_statuses_allowed": False,
            "append_to_experiment_ledger_allowed": False,
            "canonical_mutation_executed": False,
        }
        for row in rows
    ]


def duplicate_values(values: Sequence[Any]) -> list[str]:
    counts = Counter(str(value) for value in values)
    return sorted(value for value, count in counts.items() if count > 1)


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
    registry_source = registry_note_source_rows(payloads.get("append_decision"))
    trial_status_source = trial_status_source_rows(payloads.get("append_decision"))
    exclusion_source = exclusion_source_rows(payloads.get("unresolved_disposition"))
    registry_candidates = build_registry_note_candidates(registry_source)
    trial_status_candidates = build_trial_status_append_candidates(trial_status_source)
    exclusion_candidates = build_exclusion_candidates(exclusion_source)
    proposed_trial_ids = [row["trial_id"] for row in trial_status_candidates]
    duplicate_proposed_trial_ids = duplicate_values(proposed_trial_ids)
    existing_trial_ids = {
        str(row.get("trial_id"))
        for row in trial_status_rows
        if isinstance(row, Mapping) and row.get("trial_id")
    }
    colliding_trial_ids = sorted(set(proposed_trial_ids) & existing_trial_ids)
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
        failure=f"missing required canonical mutation-package inputs: {missing_paths}",
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
        name="source_maps_pass_and_remain_non_mutating",
        passed=payloads.get("unresolved_disposition", {}).get("status")
        == exclusion_plan.PASS_STATUS
        and payloads.get("append_decision", {}).get("status") == append_decision.PASS_STATUS
        and payloads.get("family_remediation", {}).get("status")
        == family_remediation.PASS_STATUS
        and dotted_get(payloads.get("unresolved_disposition"), "summary.canonical_append_only_mutation_allowed")
        is False
        and dotted_get(payloads.get("append_decision"), "summary.canonical_append_only_mutation_allowed")
        is False
        and dotted_get(payloads.get("family_remediation"), "summary.ledger_mutation_executed")
        is False,
        failure="one or more source maps are missing, failed, mutated, or append-ready",
        evidence=[UNRESOLVED_DISPOSITION.as_posix(), APPEND_DECISION.as_posix(), FAMILY_REMEDIATION.as_posix()],
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
        evidence=[TARGET_REGISTRY.as_posix(), TARGET_TRIAL_STATUSES.as_posix(), EXPERIMENT_LEDGER.as_posix()],
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
        name="candidate_counts_match_source_maps",
        passed=len(registry_candidates) == EXPECTED_REGISTRY_NOTE_CANDIDATES
        and len(trial_status_candidates) == EXPECTED_TRIAL_STATUS_APPEND_CANDIDATES
        and len(exclusion_candidates) == EXPECTED_EXCLUSION_CANDIDATES,
        failure="canonical mutation-package candidate counts drifted from source maps",
        details={
            "registry_write_candidate_count": len(registry_candidates),
            "trial_status_append_candidate_count": len(trial_status_candidates),
            "exclusion_candidate_count": len(exclusion_candidates),
        },
    )
    check(
        checks,
        failures,
        name="proposed_trial_status_append_ids_are_unique_and_new",
        passed=not duplicate_proposed_trial_ids and not colliding_trial_ids,
        failure="proposed trial-status append IDs are duplicate or collide with existing ledger",
        details={
            "duplicate_proposed_trial_ids": duplicate_proposed_trial_ids,
            "colliding_trial_ids": colliding_trial_ids,
        },
    )
    check(
        checks,
        failures,
        name="package_preserves_blocked_readiness",
        passed=dotted_get(payloads.get("unresolved_disposition"), "summary.statistical_validity_ready")
        is False
        and dotted_get(payloads.get("append_decision"), "summary.statistical_validity_ready")
        is False
        and dotted_get(payloads.get("family_remediation"), "summary.statistical_validity_ready")
        is False
        and dotted_get(payloads.get("unresolved_disposition"), "summary.model_trust_ready")
        is False
        and dotted_get(payloads.get("append_decision"), "summary.model_trust_ready")
        is False
        and dotted_get(payloads.get("family_remediation"), "summary.model_trust_ready")
        is False
        and dotted_get(payloads.get("unresolved_disposition"), "summary.promotion_allowed")
        is False
        and dotted_get(payloads.get("append_decision"), "summary.promotion_allowed")
        is False
        and dotted_get(payloads.get("family_remediation"), "summary.promotion_allowed")
        is False,
        failure="source map upgraded statistical validity, model trust, or promotion readiness",
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
        and dotted_get(payloads.get("run_status"), "summary.promotion_or_freeze_or_holdout_executed")
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
            "operation": "master_audit_canonical_trial_search_append_only_mutation_package_report_only",
            "reports_root": output_rel,
            "evidence_mode": "existing_local_source_maps_only",
            "ledger_mutation_scope": "none",
            "registry_mutation_scope": "none",
            "trial_status_mutation_scope": "none",
            "report_refresh_scope": "this_report_pair_only",
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
            "package_decision": PACKAGE_DECISION,
            "registry_write_candidate_count": len(registry_candidates),
            "trial_status_append_candidate_count": len(trial_status_candidates),
            "exclusion_candidate_count": len(exclusion_candidates),
            "append_only_mutation_command_approved": False,
            "canonical_mutation_executed": False,
            "registry_mutation_executed": False,
            "trial_status_mutation_executed": False,
            "experiment_ledger_mutation_executed": False,
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
        "canonical_mutation_package": {
            "registry_note_candidates": registry_candidates,
            "trial_status_append_candidates": trial_status_candidates,
            "exclusion_disposition_candidates": exclusion_candidates,
            "experiment_ledger_append_candidates": [],
            "canonical_write_allowed_by_this_report": False,
        },
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
            "Use this package only to plan a separately approved append-only mutation "
            "execution command. Do not mutate canonical ledgers from this report."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    package = report["canonical_mutation_package"]
    lines = [
        "# Master Audit Canonical Trial/Search Append-Only Mutation Package",
        "",
        f"- Status: `{report['status']}`",
        f"- Package decision: `{summary['package_decision']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Registry note candidates: `{summary['registry_write_candidate_count']}`",
        f"- Trial-status append candidates: `{summary['trial_status_append_candidate_count']}`",
        f"- Exclusion candidates: `{summary['exclusion_candidate_count']}`",
        f"- Append-only mutation command approved: `{summary['append_only_mutation_command_approved']}`",
        f"- Canonical mutation executed: `{summary['canonical_mutation_executed']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Candidate Counts",
        "",
        f"- Registry note candidates: `{len(package['registry_note_candidates'])}`",
        f"- Trial-status append candidates: `{len(package['trial_status_append_candidates'])}`",
        f"- Exclusion disposition candidates: `{len(package['exclusion_disposition_candidates'])}`",
        f"- Experiment-ledger append candidates: `{len(package['experiment_ledger_append_candidates'])}`",
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
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This package report did not mutate ledgers, registry, trial statuses, reports outside this output pair, source reports, data/model artifacts, Phase 8 outputs, provider state, promotion state, artifact-freeze state, final-holdout state, paper/live state, cleanup state, staging, commits, pushes, or gap maps.",
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
    reports_root = resolve_path(repo_root, args.reports_root).resolve()
    report = build_report(repo_root=repo_root, reports_root=reports_root)
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"registry_candidates={report['summary']['registry_write_candidate_count']} "
        f"trial_status_candidates={report['summary']['trial_status_append_candidate_count']} "
        f"exclusion_candidates={report['summary']['exclusion_candidate_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
