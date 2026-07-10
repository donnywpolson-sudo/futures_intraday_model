#!/usr/bin/env python3
"""Build a report-only missing source-report recovery/disposition plan.

This command inventories the missing registry JSON source reports that block a
future trial/search ledger backfill. It does not restore source reports, mutate
ledgers, mutate target registries, run generated evidence commands, run
data/model work, or change git state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import build_master_audit_trial_ledger_search_path_reconciliation as trial
from scripts.validation import build_master_audit_trial_search_ledger_backfill_decision as backfill
from scripts.validation import build_master_audit_trial_search_ledger_schema_remediation_plan as schema


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_source_report_recovery_disposition_plan"
PASS_STATUS = "PASS_MASTER_AUDIT_SOURCE_REPORT_RECOVERY_DISPOSITION_PLAN_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_SOURCE_REPORT_RECOVERY_DISPOSITION_PLAN_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_source_report_recovery_disposition_plan_20260710"
)
REPORT_JSON = "master_audit_source_report_recovery_disposition_plan.json"
REPORT_MD = "master_audit_source_report_recovery_disposition_plan.md"

BACKFILL_DECISION_REPORT = backfill.DEFAULT_REPORTS_ROOT / backfill.REPORT_JSON
SCHEMA_REMEDIATION = schema.DEFAULT_REPORTS_ROOT / schema.REPORT_JSON
TARGET_REGISTRY = schema.TARGET_REGISTRY
TARGET_TRIAL_STATUSES = schema.TARGET_TRIAL_STATUSES
EXPERIMENT_LEDGER = schema.EXPERIMENT_LEDGER
RUN_STATUS = schema.RUN_STATUS
ADVERSARIAL_AUDIT = schema.ADVERSARIAL_AUDIT

REQUIRED_INPUTS = {
    "backfill_decision": BACKFILL_DECISION_REPORT,
    "schema_remediation": SCHEMA_REMEDIATION,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

EXPECTED_SOURCE_REFS = 21
EXPECTED_PRESENT_SOURCE_REFS = 7
EXPECTED_MISSING_SOURCE_REFS = 14
EXPECTED_CANDIDATE_ROWS = 27
EXPECTED_UNRESOLVED_SEARCH_FAMILY = 27
EXPECTED_UNRESOLVED_MULTIPLE_TESTING_FAMILY = 27
EXPECTED_TRIAL_STATUS_ROWS = 22
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4
EXPECTED_REGISTRY_HYPOTHESES = 17

RECOVERABLE_GIT = "RECOVERABLE_FROM_LOCAL_GIT_OBJECT"
RECOVERABLE_ALTERNATE = "RECOVERABLE_FROM_LOCAL_ALTERNATE_PATH"
UNRECOVERED = "UNRECOVERED_EXPLICIT_DISPOSITION_REQUIRED"

WRITE_APPROVALS = {
    "append_only_backfill_allowed": False,
    "ledger_mutation_allowed": False,
    "source_report_restore_executed": False,
    "ledger_mutation_executed": False,
    "write_recovered_source_reports_allowed": False,
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
        "backfill_decision": {
            "status": "status",
            "backfill_decision": "summary.backfill_decision",
            "missing_source_refs": "summary.missing_registry_json_source_report_ref_count",
            "search_unresolved": "summary.unresolved_field_counts.search_family_id",
            "multiple_unresolved": "summary.unresolved_field_counts.multiple_testing_family_id",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "schema_remediation": {
            "status": "status",
            "source_refs": "summary.registry_json_source_report_ref_count",
            "present_source_refs": "summary.present_registry_json_source_report_ref_count",
            "missing_source_refs": "summary.missing_registry_json_source_report_ref_count",
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


def source_report_refs(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    refs = payload.get("source_report_reference_inventory") if isinstance(payload, Mapping) else []
    return [ref for ref in refs if isinstance(ref, Mapping)] if isinstance(refs, list) else []


def candidate_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = payload.get("row_level_backfill_decisions") if isinstance(payload, Mapping) else []
    if not isinstance(rows, list):
        rows = payload.get("candidate_trial_search_ledger_rows") if isinstance(payload, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def unresolved_counts(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    counts = dotted_get(payload, "summary.unresolved_field_counts")
    return counts if isinstance(counts, Mapping) else {}


def registry_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    return trial.registry_hypotheses(payload)


def path_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.replace("\\", "/")]
    if isinstance(value, list):
        return [str(item).replace("\\", "/") for item in value if isinstance(item, str)]
    return []


def impacted_rows_for_path(
    *,
    rows: Sequence[Mapping[str, Any]],
    missing_path: str,
) -> list[dict[str, Any]]:
    impacted: list[dict[str, Any]] = []
    for row in rows:
        row_paths = set(path_list(row.get("missing_source_report_paths")))
        if missing_path not in row_paths:
            continue
        impacted.append(
            {
                "row_id": row.get("row_id"),
                "row_origin": row.get("row_origin"),
                "trial_id": row.get("trial_id"),
                "hypothesis_id": row.get("hypothesis_id"),
                "stage": row.get("stage"),
                "status": row.get("status"),
            }
        )
    return impacted


def md_counterpart_path(json_path: str) -> str:
    return str(Path(json_path).with_suffix(".md")).replace("\\", "/")


def local_candidate_paths(
    *,
    repo_root: Path,
    missing_path: str,
    candidate_search_roots: Sequence[Path],
) -> list[str]:
    missing = Path(missing_path)
    matches: list[str] = []
    for root in candidate_search_roots:
        absolute_root = resolve_path(repo_root, root)
        if not absolute_root.is_dir():
            continue
        for candidate in absolute_root.rglob(missing.name):
            candidate_rel = rel(candidate, repo_root)
            if candidate_rel != missing_path.replace("\\", "/"):
                matches.append(candidate_rel)
    return sorted(set(matches))


def git_history_for_path(
    *,
    repo_root: Path,
    missing_path: str,
    overrides: Mapping[str, Sequence[str]] | None,
) -> list[str]:
    if overrides is not None:
        return list(overrides.get(missing_path, []))
    try:
        result = subprocess.run(
            ["git", "log", "--all", "--format=%H", "--", missing_path],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def disposition_for_row(
    *,
    exact_exists: bool,
    alternate_paths: Sequence[str],
    git_commits: Sequence[str],
) -> str:
    if exact_exists or git_commits:
        return RECOVERABLE_GIT if git_commits else RECOVERABLE_ALTERNATE
    if alternate_paths:
        return RECOVERABLE_ALTERNATE
    return UNRECOVERED


def build_disposition_rows(
    *,
    repo_root: Path,
    missing_refs: Sequence[Mapping[str, Any]],
    candidate_rows_for_backfill: Sequence[Mapping[str, Any]],
    git_history_overrides: Mapping[str, Sequence[str]] | None = None,
    candidate_search_roots: Sequence[Path] = (
        Path("reports/pipeline_audit"),
        Path("docs"),
        Path("manifests"),
    ),
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ref in missing_refs:
        missing_path = str(ref.get("path") or "").replace("\\", "/")
        exact_exists = resolve_path(repo_root, missing_path).is_file()
        md_path = md_counterpart_path(missing_path)
        md_exists = resolve_path(repo_root, md_path).is_file()
        alternates = local_candidate_paths(
            repo_root=repo_root,
            missing_path=missing_path,
            candidate_search_roots=candidate_search_roots,
        )
        commits = git_history_for_path(
            repo_root=repo_root,
            missing_path=missing_path,
            overrides=git_history_overrides,
        )
        rows.append(
            {
                "hypothesis_id": ref.get("hypothesis_id"),
                "missing_source_report_path": missing_path,
                "registry_resolution": ref.get("resolution"),
                "registry_reason": ref.get("reason"),
                "current_path_exists": exact_exists,
                "md_counterpart_path": md_path,
                "md_counterpart_exists": md_exists,
                "alternate_local_candidate_paths": list(alternates),
                "git_history_commits": commits,
                "impacted_candidate_rows": impacted_rows_for_path(
                    rows=candidate_rows_for_backfill,
                    missing_path=missing_path,
                ),
                "recommended_disposition": disposition_for_row(
                    exact_exists=exact_exists,
                    alternate_paths=alternates,
                    git_commits=commits,
                ),
            }
        )
    return rows


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
    git_history_overrides: Mapping[str, Sequence[str]] | None = None,
    candidate_search_roots: Sequence[Path] = (
        Path("reports/pipeline_audit"),
        Path("docs"),
        Path("manifests"),
    ),
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
    backfill_report = payloads.get("backfill_decision")
    schema_report = payloads.get("schema_remediation")
    refs = source_report_refs(backfill_report)
    if not refs:
        refs = source_report_refs(schema_report)
    present_refs = [ref for ref in refs if ref.get("exists") is True]
    missing_refs = [ref for ref in refs if ref.get("exists") is False]
    backfill_rows = candidate_rows(backfill_report)
    disposition_rows = build_disposition_rows(
        repo_root=repo_root,
        missing_refs=missing_refs,
        candidate_rows_for_backfill=backfill_rows,
        git_history_overrides=git_history_overrides,
        candidate_search_roots=candidate_search_roots,
    )
    disposition_counts = dict(
        sorted(Counter(str(row["recommended_disposition"]) for row in disposition_rows).items())
    )
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
        failure=f"missing required source-report disposition inputs: {missing_paths}",
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
        name="upstream_backfill_decision_passes_and_remains_blocked",
        passed=backfill_report is not None
        and backfill_report.get("status") == backfill.PASS_STATUS
        and dotted_get(backfill_report, "summary.backfill_decision") == backfill.BACKFILL_DECISION
        and dotted_get(backfill_report, "summary.append_only_backfill_allowed") is False
        and dotted_get(backfill_report, "summary.ledger_mutation_executed") is False
        and dotted_get(backfill_report, "summary.statistical_validity_ready") is False
        and dotted_get(backfill_report, "summary.model_trust_ready") is False
        and dotted_get(backfill_report, "summary.promotion_allowed") is False,
        failure="upstream backfill decision is missing, failed, or no longer blocked",
        evidence=[BACKFILL_DECISION_REPORT.as_posix()],
        details={"status": None if backfill_report is None else backfill_report.get("status")},
    )
    check(
        checks,
        failures,
        name="schema_remediation_passes_and_source_ref_counts_preserved",
        passed=schema_report is not None
        and schema_report.get("status") == schema.PASS_STATUS
        and dotted_get(schema_report, "summary.registry_json_source_report_ref_count")
        == EXPECTED_SOURCE_REFS
        and dotted_get(schema_report, "summary.present_registry_json_source_report_ref_count")
        == EXPECTED_PRESENT_SOURCE_REFS
        and dotted_get(schema_report, "summary.missing_registry_json_source_report_ref_count")
        == EXPECTED_MISSING_SOURCE_REFS,
        failure="schema-remediation report is missing, failed, or source-ref counts drifted",
        evidence=[SCHEMA_REMEDIATION.as_posix()],
        details={
            "status": None if schema_report is None else schema_report.get("status"),
            "source_ref_count": len(refs),
            "present_source_ref_count": len(present_refs),
            "missing_source_ref_count": len(missing_refs),
        },
    )
    missing_paths_from_refs = {str(ref.get("path")) for ref in missing_refs if ref.get("path")}
    disposition_paths = {row["missing_source_report_path"] for row in disposition_rows}
    check(
        checks,
        failures,
        name="all_missing_refs_preserved_with_disposition_rows",
        passed=len(refs) == EXPECTED_SOURCE_REFS
        and len(present_refs) == EXPECTED_PRESENT_SOURCE_REFS
        and len(missing_refs) == EXPECTED_MISSING_SOURCE_REFS
        and missing_paths_from_refs == disposition_paths
        and all(row["recommended_disposition"] in {RECOVERABLE_GIT, RECOVERABLE_ALTERNATE, UNRECOVERED} for row in disposition_rows),
        failure="missing source-report refs were dropped or lack valid dispositions",
        details={
            "missing_ref_count": len(missing_refs),
            "disposition_row_count": len(disposition_rows),
            "missing_without_disposition": sorted(missing_paths_from_refs - disposition_paths),
            "disposition_without_missing_ref": sorted(disposition_paths - missing_paths_from_refs),
            "disposition_counts": disposition_counts,
        },
    )
    backfill_counts = unresolved_counts(backfill_report)
    schema_counts = unresolved_counts(schema_report)
    check(
        checks,
        failures,
        name="search_and_multiple_testing_family_ids_remain_unresolved",
        passed=backfill_counts.get("search_family_id") == EXPECTED_UNRESOLVED_SEARCH_FAMILY
        and backfill_counts.get("multiple_testing_family_id")
        == EXPECTED_UNRESOLVED_MULTIPLE_TESTING_FAMILY
        and schema_counts.get("search_family_id") == EXPECTED_UNRESOLVED_SEARCH_FAMILY
        and schema_counts.get("multiple_testing_family_id")
        == EXPECTED_UNRESOLVED_MULTIPLE_TESTING_FAMILY,
        failure="search or multiple-testing unresolved counts changed",
        details={
            "backfill_unresolved_field_counts": dict(backfill_counts),
            "schema_unresolved_field_counts": dict(schema_counts),
        },
    )
    check(
        checks,
        failures,
        name="current_ledgers_parse_with_expected_counts",
        passed=not trial_status_errors
        and not experiment_errors
        and len(trial_status_rows) == EXPECTED_TRIAL_STATUS_ROWS
        and len(experiment_rows) == EXPECTED_EXPERIMENT_LEDGER_ROWS
        and len(registry) == EXPECTED_REGISTRY_HYPOTHESES
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
        name="readiness_and_write_approvals_remain_blocked",
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
            "operation": "master_audit_source_report_recovery_disposition_plan_report_only",
            "reports_root": output_rel,
            "evidence_mode": "existing_local_backfill_schema_registry_ledger_git_history_only",
            "source_report_restore_scope": "none",
            "ledger_mutation_scope": "none",
            "data_model_scope": "none",
            "provider_scope": "none",
            "allowed_inputs": [
                rel(resolve_path(repo_root, path), repo_root) for path in paths.values()
            ],
            "candidate_search_roots": [root.as_posix() for root in candidate_search_roots],
        },
        "summary": {
            "status": status,
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": sum(1 for item in checks if item["status"] == "PASS"),
            "failed_check_count": sum(1 for item in checks if item["status"] == "FAIL"),
            "source_report_recovery_disposition_plan_ready": status == PASS_STATUS,
            "registry_json_source_report_ref_count": len(refs),
            "present_registry_json_source_report_ref_count": len(present_refs),
            "missing_registry_json_source_report_ref_count": len(missing_refs),
            "disposition_counts": disposition_counts,
            "candidate_trial_search_ledger_row_count": dotted_get(
                backfill_report,
                "summary.candidate_trial_search_ledger_row_count",
            ),
            "unresolved_field_counts": dict(backfill_counts),
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
        "missing_source_report_dispositions": disposition_rows,
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
            "Do not backfill ledgers until missing source reports are recovered "
            "or explicitly dispositioned and search-family plus multiple-testing "
            "family metadata is complete under separate approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Source-Report Recovery Disposition Plan",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Missing source reports: `{summary['missing_registry_json_source_report_ref_count']}`",
        f"- Disposition counts: `{summary['disposition_counts']}`",
        f"- Append-only backfill allowed: `{summary['append_only_backfill_allowed']}`",
        f"- Source-report restore executed: `{summary['source_report_restore_executed']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Missing Source-Report Dispositions",
        "",
        "| Hypothesis | Missing JSON | MD exists | Alternate candidates | Git commits | Disposition | Impacted rows |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["missing_source_report_dispositions"]:
        lines.append(
            "| `{hypothesis}` | `{path}` | `{md}` | `{alt}` | `{git}` | `{disp}` | `{rows}` |".format(
                hypothesis=row.get("hypothesis_id"),
                path=row.get("missing_source_report_path"),
                md=row.get("md_counterpart_exists"),
                alt=len(row.get("alternate_local_candidate_paths") or []),
                git=len(row.get("git_history_commits") or []),
                disp=row.get("recommended_disposition"),
                rows=len(row.get("impacted_candidate_rows") or []),
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
            "- This plan did not restore source reports, mutate ledgers, mutate registry, mutate trial statuses, run generated reports, run data/model commands, run WFA/modeling, refresh Phase 8, call providers/network, promote, freeze artifacts, run final holdout, run paper/live, cleanup, stage, commit, push, or refresh gap maps.",
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
        f"missing_source_reports={report['summary']['missing_registry_json_source_report_ref_count']} "
        f"dispositions={report['summary']['disposition_counts']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
