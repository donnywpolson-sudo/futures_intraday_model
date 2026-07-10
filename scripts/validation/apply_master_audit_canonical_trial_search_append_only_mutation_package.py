#!/usr/bin/env python3
"""Apply the approved Master Audit canonical trial/search append-only mutation package."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import (
    build_master_audit_canonical_trial_search_append_only_mutation_package as package_builder,
)
from scripts.validation import build_master_audit_trial_ledger_search_path_reconciliation as trial


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_canonical_trial_search_append_only_mutation_execution"
PASS_STATUS = "PASS_MASTER_AUDIT_CANONICAL_TRIAL_SEARCH_APPEND_ONLY_MUTATION_EXECUTION"
FAIL_STATUS = "FAIL_MASTER_AUDIT_CANONICAL_TRIAL_SEARCH_APPEND_ONLY_MUTATION_EXECUTION"
DRY_RUN_STATUS = "PASS_MASTER_AUDIT_CANONICAL_TRIAL_SEARCH_APPEND_ONLY_MUTATION_DRY_RUN"
APPROVAL_TOKEN = "APPROVE_CANONICAL_TRIAL_SEARCH_APPEND_ONLY_MUTATION_20260710"

DEFAULT_PACKAGE = package_builder.DEFAULT_REPORTS_ROOT / package_builder.REPORT_JSON
DEFAULT_RECEIPT_ROOT = Path(
    "reports/master_audit/master_audit_canonical_trial_search_append_only_mutation_execution_20260710"
)
RECEIPT_JSON = "master_audit_canonical_trial_search_append_only_mutation_execution.json"
RECEIPT_MD = "master_audit_canonical_trial_search_append_only_mutation_execution.md"
TARGET_REGISTRY = Path("manifests/target_hypotheses/registry.json")
TARGET_TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
EXPERIMENT_LEDGER = Path("reports/experiments/ledger.jsonl")

EXPECTED_REGISTRY_NOTES = 14
EXPECTED_TRIAL_STATUS_APPENDS = 22
EXPECTED_EXCLUSIONS = 5
EXPECTED_EXPERIMENT_APPENDS = 0
EXPECTED_REGISTRY_HYPOTHESES = 17
EXPECTED_TRIAL_STATUS_ROWS_BEFORE = 22
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4

FORBIDDEN_FLAGS = {
    "statistical_validity_ready": False,
    "model_trust_ready": False,
    "promotion_allowed": False,
    "paper_live_ready": False,
    "production_ready": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def utc_now() -> str:
    return inventory.utc_now()


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def read_jsonl_objects(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    return trial.read_jsonl_objects(path)


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    failure: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "failure": None if passed else failure,
            "details": dict(details or {}),
        }
    )
    if not passed:
        failures.append(failure)


def duplicate_values(values: Sequence[Any]) -> list[str]:
    counts = Counter(str(value) for value in values)
    return sorted(value for value, count in counts.items() if count > 1)


def load_registry(path: Path) -> tuple[dict[str, Any] | None, list[Mapping[str, Any]], str | None]:
    payload, error = read_json_object(path)
    if error or payload is None:
        return None, [], error
    rows = payload.get("hypotheses")
    if not isinstance(rows, list):
        return payload, [], "registry hypotheses must be a list"
    return payload, [row for row in rows if isinstance(row, Mapping)], None


def canonical_dirty_paths(status_lines: Sequence[str]) -> list[str]:
    canonical = {
        TARGET_REGISTRY.as_posix(),
        TARGET_TRIAL_STATUSES.as_posix(),
        EXPERIMENT_LEDGER.as_posix(),
    }
    dirty: list[str] = []
    for line in status_lines:
        path = line[3:].strip() if len(line) > 3 else line.strip()
        path = path.replace("\\", "/")
        if path in canonical:
            dirty.append(path)
    return sorted(dirty)


def note_entry(candidate: Mapping[str, Any], *, source_package: str, applied_at_utc: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "master_audit_canonical_trial_search_append_only_mutation_execution_20260710",
        "mutation_type": "APPEND_REGISTRY_DISPOSITION_NOTE",
        "missing_source_report_path": candidate.get("missing_source_report_path"),
        "note": candidate.get("note"),
        "primary_source_json_absent_caveat": candidate.get("primary_source_json_absent_caveat"),
        "source_package": source_package,
        "applied_at_utc": applied_at_utc,
        "status_change_allowed": False,
        "wfa_allowed_change_allowed": False,
        "source_report_rewrite_allowed": False,
        "next_allowed_actions_change_allowed": False,
    }


def append_registry_notes(
    registry: dict[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    source_package: str,
    applied_at_utc: str,
) -> dict[str, Any]:
    by_id = {
        str(row.get("target_hypothesis_id")): row
        for row in registry.get("hypotheses", [])
        if isinstance(row, dict)
    }
    for candidate in candidates:
        hypothesis_id = str(candidate.get("hypothesis_id"))
        row = by_id[hypothesis_id]
        notes = row.setdefault("master_audit_disposition_notes", [])
        if not isinstance(notes, list):
            raise ValueError(f"{hypothesis_id}: master_audit_disposition_notes is not a list")
        notes.append(
            note_entry(candidate, source_package=source_package, applied_at_utc=applied_at_utc)
        )
    return registry


def write_registry(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def append_trial_status_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True, separators=(",", ":")) + "\n")


def build_receipt(
    *,
    repo_root: Path,
    package_path: Path,
    receipt_root: Path,
    execute: bool,
    approval_token: str | None,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    write_mutation: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    package_path = resolve_path(repo_root, package_path).resolve()
    receipt_root = resolve_path(repo_root, receipt_root).resolve()
    generated_at = generated_at_utc or utc_now()
    if git_status_lines is None:
        git_status = inventory.collect_git_status(repo_root)
        status_lines = list(git_status["status_lines"])
        git_error = git_status["error"]
        git_returncode = git_status["returncode"]
    else:
        status_lines = list(git_status_lines)
        git_error = None
        git_returncode = 0

    registry_path = resolve_path(repo_root, TARGET_REGISTRY)
    trial_statuses_path = resolve_path(repo_root, TARGET_TRIAL_STATUSES)
    experiment_ledger_path = resolve_path(repo_root, EXPERIMENT_LEDGER)
    registry_before_hash = sha256_file(registry_path)
    trial_statuses_before_hash = sha256_file(trial_statuses_path)
    experiment_ledger_before_hash = sha256_file(experiment_ledger_path)

    package, package_error = read_json_object(package_path)
    registry_payload, registry_rows, registry_error = load_registry(registry_path)
    trial_rows, trial_errors = read_jsonl_objects(trial_statuses_path)
    experiment_rows, experiment_errors = read_jsonl_objects(experiment_ledger_path)

    summary = package.get("summary", {}) if isinstance(package, Mapping) else {}
    canonical_package = (
        package.get("canonical_mutation_package", {}) if isinstance(package, Mapping) else {}
    )
    registry_candidates = canonical_package.get("registry_note_candidates", [])
    trial_candidates = canonical_package.get("trial_status_append_candidates", [])
    exclusion_candidates = canonical_package.get("exclusion_disposition_candidates", [])
    experiment_candidates = canonical_package.get("experiment_ledger_append_candidates", [])
    if not isinstance(registry_candidates, list):
        registry_candidates = []
    if not isinstance(trial_candidates, list):
        trial_candidates = []
    if not isinstance(exclusion_candidates, list):
        exclusion_candidates = []
    if not isinstance(experiment_candidates, list):
        experiment_candidates = []

    registry_ids = {
        str(row.get("target_hypothesis_id"))
        for row in registry_rows
        if row.get("target_hypothesis_id")
    }
    registry_status_before = {
        str(row.get("target_hypothesis_id")): row.get("status")
        for row in registry_rows
        if row.get("target_hypothesis_id")
    }
    registry_wfa_before = {
        str(row.get("target_hypothesis_id")): row.get("wfa_allowed")
        for row in registry_rows
        if row.get("target_hypothesis_id")
    }
    existing_trial_ids = {
        str(row.get("trial_id"))
        for row in trial_rows
        if isinstance(row, Mapping) and row.get("trial_id")
    }
    proposed_trial_ids = [
        str(row.get("trial_id"))
        for row in trial_candidates
        if isinstance(row, Mapping) and row.get("trial_id")
    ]
    proposed_registry_ids = [
        str(row.get("hypothesis_id"))
        for row in registry_candidates
        if isinstance(row, Mapping) and row.get("hypothesis_id")
    ]
    proposed_trial_hypothesis_ids = [
        str(row.get("hypothesis_id"))
        for row in trial_candidates
        if isinstance(row, Mapping) and row.get("hypothesis_id")
    ]
    package_rel = rel(package_path, repo_root)
    canonical_dirty = canonical_dirty_paths(status_lines)
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    check(
        checks,
        failures,
        name="approval_token_and_execute_gate",
        passed=(not execute) or approval_token == APPROVAL_TOKEN,
        failure="execute mode requires the exact append-only mutation approval token",
        details={"execute": execute, "approval_token_present": bool(approval_token)},
    )
    check(
        checks,
        failures,
        name="canonical_files_clean_before_execution",
        passed=not canonical_dirty,
        failure=f"canonical registry/ledger files are already dirty: {canonical_dirty}",
        details={"canonical_dirty_paths": canonical_dirty},
    )
    check(
        checks,
        failures,
        name="package_passes_and_is_separately_approved_for_execution",
        passed=package_error is None
        and package is not None
        and package.get("status") == package_builder.PASS_STATUS
        and summary.get("package_decision") == package_builder.PACKAGE_DECISION
        and summary.get("canonical_mutation_executed") is False,
        failure="canonical mutation package is missing, failed, already executed, or not ready for separate approval",
        details={"package_error": package_error, "package_status": package.get("status") if package else None},
    )
    check(
        checks,
        failures,
        name="package_counts_match_expected_scope",
        passed=len(registry_candidates) == EXPECTED_REGISTRY_NOTES
        and len(trial_candidates) == EXPECTED_TRIAL_STATUS_APPENDS
        and len(exclusion_candidates) == EXPECTED_EXCLUSIONS
        and len(experiment_candidates) == EXPECTED_EXPERIMENT_APPENDS
        and canonical_package.get("canonical_write_allowed_by_this_report") is False,
        failure="package candidate counts or write-approval flag drifted",
        details={
            "registry_note_candidates": len(registry_candidates),
            "trial_status_append_candidates": len(trial_candidates),
            "exclusion_candidates": len(exclusion_candidates),
            "experiment_ledger_append_candidates": len(experiment_candidates),
            "canonical_write_allowed_by_this_report": canonical_package.get("canonical_write_allowed_by_this_report"),
        },
    )
    check(
        checks,
        failures,
        name="canonical_inputs_parse_with_expected_counts",
        passed=registry_error is None
        and not trial_errors
        and not experiment_errors
        and len(registry_rows) == EXPECTED_REGISTRY_HYPOTHESES
        and len(trial_rows) == EXPECTED_TRIAL_STATUS_ROWS_BEFORE
        and len(experiment_rows) == EXPECTED_EXPERIMENT_LEDGER_ROWS,
        failure="canonical registry, trial-status ledger, or experiment ledger failed parse/count checks",
        details={
            "registry_error": registry_error,
            "trial_errors": trial_errors,
            "experiment_errors": experiment_errors,
            "registry_hypotheses": len(registry_rows),
            "trial_status_rows_before": len(trial_rows),
            "experiment_ledger_rows": len(experiment_rows),
        },
    )
    missing_registry_ids = sorted(set(proposed_registry_ids) - registry_ids)
    missing_trial_hypothesis_ids = sorted(set(proposed_trial_hypothesis_ids) - registry_ids)
    duplicate_trial_ids = duplicate_values(proposed_trial_ids)
    colliding_trial_ids = sorted(set(proposed_trial_ids) & existing_trial_ids)
    check(
        checks,
        failures,
        name="candidate_identity_checks",
        passed=not missing_registry_ids
        and not missing_trial_hypothesis_ids
        and not duplicate_trial_ids
        and not colliding_trial_ids,
        failure="candidate identities are missing, duplicate, or collide with existing trial statuses",
        details={
            "missing_registry_ids": missing_registry_ids,
            "missing_trial_hypothesis_ids": missing_trial_hypothesis_ids,
            "duplicate_trial_ids": duplicate_trial_ids,
            "colliding_trial_ids": colliding_trial_ids,
        },
    )
    forbidden_candidate_writes = [
        row
        for row in registry_candidates
        if isinstance(row, Mapping)
        and (
            row.get("status_change_allowed") is not False
            or row.get("wfa_allowed_change_allowed") is not False
            or row.get("source_report_rewrite_allowed") is not False
            or row.get("next_allowed_actions_change_allowed") is not False
        )
    ]
    forbidden_exclusion_writes = [
        row
        for row in exclusion_candidates
        if isinstance(row, Mapping)
        and (
            row.get("append_to_trial_statuses_allowed") is not False
            or row.get("append_to_experiment_ledger_allowed") is not False
        )
    ]
    check(
        checks,
        failures,
        name="candidate_write_scope_is_append_only_and_blocked",
        passed=not forbidden_candidate_writes
        and not forbidden_exclusion_writes
        and all(summary.get(key) is value for key, value in FORBIDDEN_FLAGS.items()),
        failure="package attempts forbidden status/source/action writes or upgrades readiness flags",
        details={
            "forbidden_registry_candidate_write_count": len(forbidden_candidate_writes),
            "forbidden_exclusion_write_count": len(forbidden_exclusion_writes),
            "forbidden_flags": {key: summary.get(key) for key in FORBIDDEN_FLAGS},
        },
    )

    should_mutate = execute and not failures
    mutation_error: str | None = None
    if should_mutate and write_mutation:
        try:
            if registry_payload is None:
                raise ValueError("registry payload unavailable")
            append_registry_notes(
                registry_payload,
                [row for row in registry_candidates if isinstance(row, Mapping)],
                source_package=package_rel,
                applied_at_utc=generated_at,
            )
            write_registry(registry_path, registry_payload)
            append_trial_status_rows(
                trial_statuses_path,
                [row for row in trial_candidates if isinstance(row, Mapping)],
            )
        except Exception as exc:  # pragma: no cover - defensive receipt path.
            mutation_error = f"{type(exc).__name__}: {exc}"
            failures.append(f"append-only mutation failed: {mutation_error}")

    registry_after_hash = sha256_file(registry_path)
    trial_statuses_after_hash = sha256_file(trial_statuses_path)
    experiment_ledger_after_hash = sha256_file(experiment_ledger_path)
    registry_after_payload, registry_after_rows, registry_after_error = load_registry(registry_path)
    trial_rows_after, trial_after_errors = read_jsonl_objects(trial_statuses_path)
    status_after = {
        str(row.get("target_hypothesis_id")): row.get("status")
        for row in registry_after_rows
        if row.get("target_hypothesis_id")
    }
    wfa_after = {
        str(row.get("target_hypothesis_id")): row.get("wfa_allowed")
        for row in registry_after_rows
        if row.get("target_hypothesis_id")
    }
    notes_after = 0
    for row in registry_after_rows:
        notes = row.get("master_audit_disposition_notes")
        if isinstance(notes, list):
            notes_after += sum(
                1
                for note in notes
                if isinstance(note, Mapping)
                and note.get("source")
                == "master_audit_canonical_trial_search_append_only_mutation_execution_20260710"
            )
    appended_ids_after = {
        str(row.get("trial_id"))
        for row in trial_rows_after
        if isinstance(row, Mapping) and row.get("trial_id") in proposed_trial_ids
    }
    if should_mutate:
        check(
            checks,
            failures,
            name="post_mutation_append_counts_and_hashes",
            passed=mutation_error is None
            and registry_after_error is None
            and not trial_after_errors
            and registry_after_hash != registry_before_hash
            and trial_statuses_after_hash != trial_statuses_before_hash
            and experiment_ledger_after_hash == experiment_ledger_before_hash
            and len(registry_after_rows) == EXPECTED_REGISTRY_HYPOTHESES
            and len(trial_rows_after)
            == EXPECTED_TRIAL_STATUS_ROWS_BEFORE + EXPECTED_TRIAL_STATUS_APPENDS
            and notes_after == EXPECTED_REGISTRY_NOTES
            and len(appended_ids_after) == EXPECTED_TRIAL_STATUS_APPENDS,
            failure="post-mutation hashes/counts do not prove the bounded append-only mutation",
            details={
                "registry_after_error": registry_after_error,
                "trial_after_errors": trial_after_errors,
                "notes_after": notes_after,
                "trial_status_rows_after": len(trial_rows_after),
                "appended_trial_status_ids_after": len(appended_ids_after),
            },
        )
        check(
            checks,
            failures,
            name="post_mutation_status_and_wfa_unchanged",
            passed=status_after == registry_status_before and wfa_after == registry_wfa_before,
            failure="registry status or wfa_allowed changed during append-only mutation",
            details={
                "status_changed": status_after != registry_status_before,
                "wfa_changed": wfa_after != registry_wfa_before,
            },
        )

    final_status = FAIL_STATUS if failures else (PASS_STATUS if execute else DRY_RUN_STATUS)
    report = {
        "stage": STAGE,
        "status": final_status,
        "generated_at_utc": generated_at,
        "scope": {
            "operation": "apply_master_audit_canonical_trial_search_append_only_mutation_package",
            "repo_root": str(repo_root),
            "source_package": package_rel,
            "receipt_root": rel(receipt_root, repo_root),
            "dry_run": not execute,
            "execute_append_only_mutation": execute,
            "canonical_write_scope": [
                TARGET_REGISTRY.as_posix(),
                TARGET_TRIAL_STATUSES.as_posix(),
            ]
            if execute
            else [],
            "experiment_ledger_write_scope": [],
            "data_model_scope": "none",
            "provider_scope": "none",
        },
        "summary": {
            "status": final_status,
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": sum(1 for item in checks if item["status"] == "PASS"),
            "failed_check_count": sum(1 for item in checks if item["status"] == "FAIL"),
            "append_only_mutation_command_approved": execute and approval_token == APPROVAL_TOKEN,
            "canonical_mutation_executed": should_mutate and mutation_error is None,
            "registry_mutation_executed": should_mutate and mutation_error is None,
            "trial_status_mutation_executed": should_mutate and mutation_error is None,
            "experiment_ledger_mutation_executed": False,
            "registry_note_append_count": EXPECTED_REGISTRY_NOTES if should_mutate and not mutation_error else 0,
            "trial_status_append_count": EXPECTED_TRIAL_STATUS_APPENDS if should_mutate and not mutation_error else 0,
            "exclusion_candidate_preserved_report_local_count": len(exclusion_candidates),
            "experiment_ledger_append_count": 0,
            "trial_status_rows_before": len(trial_rows),
            "trial_status_rows_after": len(trial_rows_after),
            "registry_hypothesis_count_before": len(registry_rows),
            "registry_hypothesis_count_after": len(registry_after_rows),
            "statistical_validity_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
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
            "staging_commit_push_executed": False,
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
        },
        "file_hashes": {
            TARGET_REGISTRY.as_posix(): {
                "before_sha256": registry_before_hash,
                "after_sha256": registry_after_hash,
            },
            TARGET_TRIAL_STATUSES.as_posix(): {
                "before_sha256": trial_statuses_before_hash,
                "after_sha256": trial_statuses_after_hash,
            },
            EXPERIMENT_LEDGER.as_posix(): {
                "before_sha256": experiment_ledger_before_hash,
                "after_sha256": experiment_ledger_after_hash,
            },
        },
        "mutation_counts": {
            "registry_note_candidates": len(registry_candidates),
            "trial_status_append_candidates": len(trial_candidates),
            "exclusion_candidates_preserved_report_local": len(exclusion_candidates),
            "experiment_ledger_append_candidates": len(experiment_candidates),
        },
        "checks": checks,
        "failures": list(dict.fromkeys(failures)),
        "git_status_before": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "outputs": {
            "json": rel(receipt_root / RECEIPT_JSON, repo_root),
            "markdown": rel(receipt_root / RECEIPT_MD, repo_root),
        },
        "recommended_next_action": (
            "Run a report-only trial/search ledger completeness reconciliation using this "
            "mutation receipt; do not treat this mutation as statistical-validity or "
            "model-trust acceptance."
        ),
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Canonical Trial/Search Append-Only Mutation Execution",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Append-only mutation command approved: `{summary['append_only_mutation_command_approved']}`",
        f"- Canonical mutation executed: `{summary['canonical_mutation_executed']}`",
        f"- Registry notes appended: `{summary['registry_note_append_count']}`",
        f"- Trial-status rows appended: `{summary['trial_status_append_count']}`",
        f"- Exclusion candidates preserved report-local: `{summary['exclusion_candidate_preserved_report_local_count']}`",
        f"- Experiment-ledger rows appended: `{summary['experiment_ledger_append_count']}`",
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
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Approval Statement",
            "",
            "- This receipt does not approve PBO, Deflated Sharpe, multiple-testing, statistical validity, model trust, promotion, paper/live, production, data/model commands, WFA/modeling, predictions, Phase 8 refresh, provider/network calls, artifact freeze, final holdout, cleanup, staging, commit, or push.",
            "",
        ]
    )
    return "\n".join(lines)


def write_receipt(report: Mapping[str, Any], receipt_root: Path) -> tuple[Path, Path]:
    receipt_root.mkdir(parents=True, exist_ok=True)
    json_path = receipt_root / RECEIPT_JSON
    md_path = receipt_root / RECEIPT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--package", default=DEFAULT_PACKAGE.as_posix())
    parser.add_argument("--receipt-root", default=DEFAULT_RECEIPT_ROOT.as_posix())
    parser.add_argument("--execute-append-only-mutation", action="store_true")
    parser.add_argument("--approval-token", default=None)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    receipt_root = resolve_path(repo_root, args.receipt_root).resolve()
    report = build_receipt(
        repo_root=repo_root,
        package_path=Path(args.package),
        receipt_root=receipt_root,
        execute=bool(args.execute_append_only_mutation),
        approval_token=args.approval_token,
    )
    json_path, md_path = write_receipt(report, receipt_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"registry_notes={report['summary']['registry_note_append_count']} "
        f"trial_status_appends={report['summary']['trial_status_append_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] in {PASS_STATUS, DRY_RUN_STATUS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
