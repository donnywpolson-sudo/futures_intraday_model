#!/usr/bin/env python3
"""Build a report-only unresolved row-linkage/exclusion disposition.

This command consumes existing Master Audit trial/search evidence and decides
whether the remaining unresolved rows can be linked to a canonical target
hypothesis/search family or must stay excluded from the canonical trial/search
ledger. It writes only its JSON/Markdown report pair.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import build_master_audit_trial_ledger_search_path_reconciliation as trial
from scripts.validation import (
    build_master_audit_trial_search_append_only_disposition_mutation_decision as upstream,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_unresolved_row_linkage_exclusion_disposition"
PASS_STATUS = "PASS_MASTER_AUDIT_UNRESOLVED_ROW_LINKAGE_EXCLUSION_DISPOSITION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_UNRESOLVED_ROW_LINKAGE_EXCLUSION_DISPOSITION_REPORT_ONLY"
DISPOSITION = "EXCLUDE_FROM_CANONICAL_TRIAL_SEARCH_LEDGER"
EXCLUDED_FAMILY_STATUS = "EXCLUDED_FROM_CANONICAL_TRIAL_SEARCH_LEDGER"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_unresolved_row_linkage_exclusion_disposition_20260710"
)
REPORT_JSON = "master_audit_unresolved_row_linkage_exclusion_disposition.json"
REPORT_MD = "master_audit_unresolved_row_linkage_exclusion_disposition.md"

APPEND_DECISION = upstream.DEFAULT_REPORTS_ROOT / upstream.REPORT_JSON
UPSTREAM_REMEDIATION = upstream.UPSTREAM_REMEDIATION
TARGET_REGISTRY = upstream.TARGET_REGISTRY
TARGET_TRIAL_STATUSES = upstream.TARGET_TRIAL_STATUSES
EXPERIMENT_LEDGER = upstream.EXPERIMENT_LEDGER
RUN_STATUS = upstream.RUN_STATUS
ADVERSARIAL_AUDIT = upstream.ADVERSARIAL_AUDIT

REQUIRED_INPUTS = {
    "append_decision": APPEND_DECISION,
    "upstream_remediation": UPSTREAM_REMEDIATION,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

EXPECTED_UNRESOLVED_ROWS = 5
EXPECTED_LEGACY_ROWS = 4
EXPECTED_CURRENT_ROWS = 1
EXPECTED_REGISTRY_HYPOTHESES = 17
EXPECTED_TRIAL_STATUS_ROWS = 22
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4

WRITE_APPROVALS = {
    "canonical_append_only_mutation_allowed": False,
    "registry_mutation_allowed": False,
    "trial_status_mutation_allowed": False,
    "experiment_ledger_mutation_allowed": False,
    "ledger_mutation_executed": False,
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
        "append_decision": {
            "status": "status",
            "decision": "summary.mutation_decision",
            "unresolved_rows": "summary.unresolved_family_metadata_row_count",
            "canonical_allowed": "summary.canonical_append_only_mutation_allowed",
        },
        "upstream_remediation": {
            "status": "status",
            "unresolved_rows": "summary.unresolved_family_metadata_row_count",
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


def registry_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    return trial.registry_hypotheses(payload)


def blocked_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    draft = payload.get("draft_only_mutation_payload") if isinstance(payload, Mapping) else {}
    rows = draft.get("blocked_unresolved_rows") if isinstance(draft, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def row_evidence_paths(row: Mapping[str, Any]) -> list[str]:
    hypothesis = row.get("hypothesis_id")
    if isinstance(hypothesis, Mapping):
        paths = hypothesis.get("evidence_paths")
        if isinstance(paths, list):
            return [str(path) for path in paths if path]
    return []


def row_has_primary_linkage(row: Mapping[str, Any], registry_ids: set[str]) -> bool:
    hypothesis = row.get("hypothesis_id")
    if isinstance(hypothesis, str) and hypothesis in registry_ids:
        return True
    if isinstance(hypothesis, Mapping):
        value = hypothesis.get("value") or hypothesis.get("hypothesis_id")
        if isinstance(value, str) and value in registry_ids:
            return True
    return False


def disposition_reason(row: Mapping[str, Any]) -> str:
    origin = row.get("row_origin")
    if origin == "experiment_ledger":
        return (
            "legacy experiment-ledger diagnostic row has no primary hypothesis_id "
            "and cannot be linked without inference"
        )
    if origin == "current_wfa_phase8_statistical_run":
        return (
            "current WFA/Phase8/statistical line is closed_no_alpha_evidence and "
            "has no primary target-hypothesis linkage"
        )
    return "unresolved row has no primary target-hypothesis linkage"


def build_exclusion_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    registry_ids: set[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "row_id": row.get("row_id"),
                "row_origin": row.get("row_origin"),
                "trial_id": row.get("trial_id"),
                "source_stage": row.get("stage"),
                "source_status": row.get("status"),
                "linkable_to_target_hypothesis": row_has_primary_linkage(row, registry_ids),
                "canonical_target_hypothesis_id": None,
                "canonical_search_family_id": None,
                "canonical_multiple_testing_family_id": None,
                "disposition": DISPOSITION,
                "disposition_reason": disposition_reason(row),
                "evidence_paths": row_evidence_paths(row),
                "search_family_id": {
                    "status": EXCLUDED_FAMILY_STATUS,
                    "value": None,
                    "reason": "row excluded from canonical trial/search ledger",
                },
                "multiple_testing_family_id": {
                    "status": EXCLUDED_FAMILY_STATUS,
                    "value": None,
                    "reason": "row excluded from canonical trial/search ledger",
                },
                "canonical_mutation_allowed": False,
            }
        )
    return output


def evidence_paths_exist(
    *,
    repo_root: Path,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for row in rows:
        for path in row_evidence_paths(row):
            if not resolve_path(repo_root, path).exists():
                missing.append(path)
    return not missing, sorted(set(missing))


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
    append_report = payloads.get("append_decision")
    upstream_report = payloads.get("upstream_remediation")
    upstream_summary = upstream_report.get("summary") if isinstance(upstream_report, Mapping) else {}
    upstream_summary = upstream_summary if isinstance(upstream_summary, Mapping) else {}
    unresolved_rows = blocked_rows(append_report)
    exclusion_rows = build_exclusion_rows(rows=unresolved_rows, registry_ids=registry_ids)
    evidence_ok, missing_evidence_paths = evidence_paths_exist(
        repo_root=repo_root,
        rows=unresolved_rows,
    )
    linkable_rows = [row for row in exclusion_rows if row["linkable_to_target_hypothesis"]]
    legacy_rows = [row for row in exclusion_rows if row["row_origin"] == "experiment_ledger"]
    current_rows = [
        row for row in exclusion_rows if row["row_origin"] == "current_wfa_phase8_statistical_run"
    ]
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
        failure=f"missing required unresolved-row disposition inputs: {missing_paths}",
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
        name="append_decision_passes_and_still_blocks_five_rows",
        passed=append_report is not None
        and append_report.get("status") == upstream.PASS_STATUS
        and dotted_get(append_report, "summary.mutation_decision") == upstream.MUTATION_DECISION
        and dotted_get(append_report, "summary.unresolved_family_metadata_row_count")
        == EXPECTED_UNRESOLVED_ROWS
        and dotted_get(append_report, "summary.canonical_append_only_mutation_allowed") is False
        and len(unresolved_rows) == EXPECTED_UNRESOLVED_ROWS,
        failure="append-only disposition decision is missing, failed, append-ready, or unresolved-row count drifted",
        evidence=[APPEND_DECISION.as_posix()],
        details={
            "status": None if append_report is None else append_report.get("status"),
            "unresolved_row_count": len(unresolved_rows),
        },
    )
    check(
        checks,
        failures,
        name="upstream_remediation_passes_and_stays_blocked",
        passed=upstream_report is not None
        and upstream_report.get("status") == upstream.upstream.PASS_STATUS
        and upstream_summary.get("search_family_status_counts", {}).get(upstream.upstream.UNRESOLVED)
        == EXPECTED_UNRESOLVED_ROWS
        and upstream_summary.get("multiple_testing_family_status_counts", {}).get(
            upstream.upstream.UNRESOLVED
        )
        == EXPECTED_UNRESOLVED_ROWS
        and upstream_summary.get("statistical_validity_ready") is False
        and upstream_summary.get("model_trust_ready") is False
        and upstream_summary.get("promotion_allowed") is False,
        failure="upstream family-metadata remediation is missing, failed, or no longer blocked",
        evidence=[UPSTREAM_REMEDIATION.as_posix()],
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
        name="unresolved_source_evidence_paths_exist",
        passed=evidence_ok,
        failure=f"unresolved-row source evidence paths are missing: {missing_evidence_paths}",
        evidence=[path for row in unresolved_rows for path in row_evidence_paths(row)],
        details={"missing_evidence_paths": missing_evidence_paths},
    )
    check(
        checks,
        failures,
        name="rows_are_not_primary_linkable_and_are_explicitly_excluded",
        passed=len(exclusion_rows) == EXPECTED_UNRESOLVED_ROWS
        and len(legacy_rows) == EXPECTED_LEGACY_ROWS
        and len(current_rows) == EXPECTED_CURRENT_ROWS
        and not linkable_rows
        and all(row["disposition"] == DISPOSITION for row in exclusion_rows)
        and all(row["canonical_mutation_allowed"] is False for row in exclusion_rows),
        failure="one or more unresolved rows became linkable or lacked explicit exclusion disposition",
        details={
            "exclusion_row_count": len(exclusion_rows),
            "legacy_row_count": len(legacy_rows),
            "current_row_count": len(current_rows),
            "linkable_row_ids": [row["row_id"] for row in linkable_rows],
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
            "operation": "master_audit_unresolved_row_linkage_exclusion_disposition_report_only",
            "reports_root": output_rel,
            "evidence_mode": "existing_local_unresolved_rows_only",
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
            "unresolved_row_count": len(unresolved_rows),
            "legacy_experiment_ledger_row_count": len(legacy_rows),
            "current_wfa_phase8_statistical_row_count": len(current_rows),
            "linkable_row_count": len(linkable_rows),
            "exclusion_candidate_count": len(exclusion_rows),
            "disposition": DISPOSITION,
            "canonical_append_only_mutation_allowed": False,
            "registry_mutation_allowed": False,
            "trial_status_mutation_allowed": False,
            "experiment_ledger_mutation_allowed": False,
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
        "unresolved_row_exclusion_dispositions": exclusion_rows,
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
            "Use this report to plan a separately approved append-only canonical "
            "mutation only if explicit exclusions are accepted; do not backfill or "
            "mutate ledgers from this report."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Unresolved Row-Linkage Exclusion Disposition",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Unresolved rows: `{summary['unresolved_row_count']}`",
        f"- Linkable rows: `{summary['linkable_row_count']}`",
        f"- Exclusion candidates: `{summary['exclusion_candidate_count']}`",
        f"- Canonical append-only mutation allowed: `{summary['canonical_append_only_mutation_allowed']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Exclusion Dispositions",
        "",
        "| Row | Origin | Trial | Disposition | Linkable |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["unresolved_row_exclusion_dispositions"]:
        lines.append(
            "| `{row}` | `{origin}` | `{trial}` | `{disp}` | `{linkable}` |".format(
                row=row.get("row_id"),
                origin=row.get("row_origin"),
                trial=row.get("trial_id"),
                disp=row.get("disposition"),
                linkable=row.get("linkable_to_target_hypothesis"),
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
            "- This report did not mutate ledgers, registry, trial statuses, reports outside this output pair, data/model artifacts, source reports, Phase 8 outputs, provider state, promotion state, artifact-freeze state, final-holdout state, paper/live state, cleanup state, staging, commits, pushes, or gap maps.",
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
        f"linkable_rows={report['summary']['linkable_row_count']} "
        f"exclusion_candidates={report['summary']['exclusion_candidate_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
