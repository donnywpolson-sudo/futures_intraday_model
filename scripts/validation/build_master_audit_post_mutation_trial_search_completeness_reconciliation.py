#!/usr/bin/env python3
"""Build a report-only post-mutation trial/search ledger completeness reconciliation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import build_master_audit_trial_ledger_search_path_reconciliation as trial


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_post_mutation_trial_search_completeness_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_POST_MUTATION_TRIAL_SEARCH_COMPLETENESS_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_POST_MUTATION_TRIAL_SEARCH_COMPLETENESS_RECONCILIATION_REPORT_ONLY"
READY_STATUS = "READY_FOR_SEPARATE_STATISTICAL_RECOMPUTE_TRIAL_LEDGER_INPUTS_COMPLETE"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_post_mutation_trial_search_completeness_reconciliation_20260710"
)
REPORT_JSON = "master_audit_post_mutation_trial_search_completeness_reconciliation.json"
REPORT_MD = "master_audit_post_mutation_trial_search_completeness_reconciliation.md"

MUTATION_RECEIPT = Path(
    "reports/master_audit/master_audit_canonical_trial_search_append_only_mutation_execution_20260710/"
    "master_audit_canonical_trial_search_append_only_mutation_execution.json"
)
TARGET_REGISTRY = Path("manifests/target_hypotheses/registry.json")
TARGET_TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
EXPERIMENT_LEDGER = Path("reports/experiments/ledger.jsonl")
STATISTICAL_SUMMARY = Path(
    "reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/"
    "statistical_validity_summary.json"
)
ALPHA_MATRIX = Path(
    "reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/"
    "alpha_evidence_gap_matrix.json"
)
ALPHA_CLOSEOUT = Path(
    "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
    "alpha_evidence_completion_closeout.json"
)
RUN_STATUS = Path("reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json")
ADVERSARIAL_AUDIT = Path("docs/adversarial_current_project_evidence_gate_audit_20260709.md")

REQUIRED_INPUTS = {
    "mutation_receipt": MUTATION_RECEIPT,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "statistical_summary": STATISTICAL_SUMMARY,
    "alpha_matrix": ALPHA_MATRIX,
    "alpha_closeout": ALPHA_CLOSEOUT,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

EXPECTED_REGISTRY_HYPOTHESES = 17
EXPECTED_REGISTRY_NOTES = 14
EXPECTED_TRIAL_STATUS_ROWS = 44
EXPECTED_FAMILY_METADATA_ROWS = 22
EXPECTED_SEARCH_FAMILIES = 10
EXPECTED_MULTIPLE_TESTING_FAMILIES = 2
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4
EXPECTED_EXCLUSIONS = 5


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


def registry_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = payload.get("hypotheses") if isinstance(payload, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def registry_note_count(rows: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        notes = row.get("master_audit_disposition_notes")
        if isinstance(notes, list):
            count += sum(
                1
                for note in notes
                if isinstance(note, Mapping)
                and note.get("source")
                == "master_audit_canonical_trial_search_append_only_mutation_execution_20260710"
            )
    return count


def family_metadata_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if row.get("stage") == "master_audit_family_metadata_append_only_disposition"
        and row.get("status") == "BLOCKED_REPORT_LOCAL_METADATA_CANONICALIZATION"
    ]


def duplicate_values(values: Sequence[Any]) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return sorted(key for key, count in counts.items() if count > 1)


def input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields: dict[str, dict[str, str]] = {
        "mutation_receipt": {
            "status": "status",
            "registry_notes": "summary.registry_note_append_count",
            "trial_status_appends": "summary.trial_status_append_count",
        },
        "target_registry": {"schema_version": "schema_version"},
        "statistical_summary": {
            "status": "status",
            "statistical_validity_ready": "statistical_validity_ready",
            "failure_count": "failure_count",
        },
        "alpha_matrix": {"verdict": "verdict", "alpha_evidence_ready": "alpha_evidence_ready"},
        "alpha_closeout": {
            "verdict": "verdict",
            "promotion_allowed": "promotion_allowed",
        },
        "run_status": {
            "current_line_classification": "summary.current_line_classification",
            "data_model_commands_executed": "summary.data_model_commands_executed",
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
    payloads, payload_failures = load_payloads(repo_root=repo_root, paths=paths)
    trial_rows, trial_errors = read_jsonl_objects(resolve_path(repo_root, paths["target_trial_statuses"]))
    experiment_rows, experiment_errors = read_jsonl_objects(resolve_path(repo_root, paths["experiment_ledger"]))
    registry = registry_rows(payloads.get("target_registry"))
    family_rows = family_metadata_rows(trial_rows)
    registry_ids = {
        str(row.get("target_hypothesis_id"))
        for row in registry
        if row.get("target_hypothesis_id")
    }
    family_hypothesis_ids = {
        str(row.get("hypothesis_id"))
        for row in family_rows
        if row.get("hypothesis_id")
    }
    unknown_family_hypotheses = sorted(family_hypothesis_ids - registry_ids)
    family_trial_ids = [row.get("trial_id") for row in family_rows]
    duplicate_family_trial_ids = duplicate_values(family_trial_ids)
    rows_missing_search_family = [
        str(row.get("trial_id")) for row in family_rows if not row.get("search_family_id")
    ]
    rows_missing_multiple_family = [
        str(row.get("trial_id")) for row in family_rows if not row.get("multiple_testing_family_id")
    ]
    search_families = sorted({str(row.get("search_family_id")) for row in family_rows if row.get("search_family_id")})
    multiple_testing_families = sorted(
        {
            str(row.get("multiple_testing_family_id"))
            for row in family_rows
            if row.get("multiple_testing_family_id")
        }
    )
    note_count = registry_note_count(registry)
    receipt = payloads.get("mutation_receipt")
    statistical = payloads.get("statistical_summary")
    required_checks = statistical.get("required_checks", {}) if isinstance(statistical, Mapping) else {}
    pbo = required_checks.get("pbo", {}) if isinstance(required_checks, Mapping) else {}
    deflated = required_checks.get("deflated_sharpe", {}) if isinstance(required_checks, Mapping) else {}
    multiple = (
        required_checks.get("multiple_testing_adjustment", {})
        if isinstance(required_checks, Mapping)
        else {}
    )
    probabilistic = (
        required_checks.get("probabilistic_sharpe", {})
        if isinstance(required_checks, Mapping)
        else {}
    )
    regimes = required_checks.get("regime_breakdowns", {}) if isinstance(required_checks, Mapping) else {}

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {str(item.get("path")) for item in evidence_rows if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    output_rel = rel(reports_root, repo_root)
    check(
        checks,
        failures,
        name="required_inputs_present",
        passed=not missing_paths,
        failure=f"missing required post-mutation completeness inputs: {missing_paths}",
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
        name="mutation_receipt_proves_expected_append_only_mutation",
        passed=receipt is not None
        and receipt.get("status")
        == "PASS_MASTER_AUDIT_CANONICAL_TRIAL_SEARCH_APPEND_ONLY_MUTATION_EXECUTION"
        and dotted_get(receipt, "summary.canonical_mutation_executed") is True
        and dotted_get(receipt, "summary.registry_note_append_count") == EXPECTED_REGISTRY_NOTES
        and dotted_get(receipt, "summary.trial_status_append_count") == EXPECTED_FAMILY_METADATA_ROWS
        and dotted_get(receipt, "summary.exclusion_candidate_preserved_report_local_count")
        == EXPECTED_EXCLUSIONS
        and dotted_get(receipt, "summary.experiment_ledger_append_count") == 0
        and dotted_get(receipt, "summary.experiment_ledger_mutation_executed") is False,
        failure="canonical mutation receipt does not prove the expected bounded append-only mutation",
        evidence=[MUTATION_RECEIPT.as_posix()],
    )
    check(
        checks,
        failures,
        name="canonical_trial_search_metadata_coverage_complete",
        passed=not trial_errors
        and len(registry) == EXPECTED_REGISTRY_HYPOTHESES
        and note_count == EXPECTED_REGISTRY_NOTES
        and len(trial_rows) == EXPECTED_TRIAL_STATUS_ROWS
        and len(family_rows) == EXPECTED_FAMILY_METADATA_ROWS
        and not unknown_family_hypotheses
        and not duplicate_family_trial_ids
        and not rows_missing_search_family
        and not rows_missing_multiple_family
        and len(search_families) == EXPECTED_SEARCH_FAMILIES
        and len(multiple_testing_families) == EXPECTED_MULTIPLE_TESTING_FAMILIES,
        failure="canonical registry/trial-status search metadata is incomplete or drifted",
        evidence=[TARGET_REGISTRY.as_posix(), TARGET_TRIAL_STATUSES.as_posix()],
        details={
            "registry_hypotheses": len(registry),
            "registry_master_audit_note_count": note_count,
            "trial_status_rows": len(trial_rows),
            "family_metadata_rows": len(family_rows),
            "search_family_count": len(search_families),
            "multiple_testing_family_count": len(multiple_testing_families),
            "unknown_family_hypotheses": unknown_family_hypotheses,
            "duplicate_family_trial_ids": duplicate_family_trial_ids,
            "rows_missing_search_family": rows_missing_search_family,
            "rows_missing_multiple_testing_family": rows_missing_multiple_family,
        },
    )
    check(
        checks,
        failures,
        name="experiment_ledger_preserved_as_non_append_ready_context",
        passed=not experiment_errors and len(experiment_rows) == EXPECTED_EXPERIMENT_LEDGER_ROWS,
        failure="experiment ledger parse/count drifted or became append-ready evidence",
        evidence=[EXPERIMENT_LEDGER.as_posix()],
        details={
            "experiment_ledger_rows": len(experiment_rows),
            "experiment_errors": experiment_errors,
        },
    )
    check(
        checks,
        failures,
        name="statistical_summary_failures_preserved_no_recompute_claim",
        passed=statistical is not None
        and statistical.get("status") == "FAIL"
        and statistical.get("statistical_validity_ready") is False
        and statistical.get("failure_count") == 5
        and pbo.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and deflated.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and multiple.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and probabilistic.get("status") == "FAIL"
        and regimes.get("status") == "FAIL",
        failure="statistical summary no longer preserves current FAIL and non-recomputed blockers",
        evidence=[STATISTICAL_SUMMARY.as_posix()],
        details={
            "statistical_status": statistical.get("status") if statistical else None,
            "pbo_summary_status": pbo.get("status"),
            "deflated_sharpe_summary_status": deflated.get("status"),
            "multiple_testing_summary_status": multiple.get("status"),
            "probabilistic_sharpe_status": probabilistic.get("status"),
            "regime_breakdowns_status": regimes.get("status"),
        },
    )
    check(
        checks,
        failures,
        name="alpha_closeout_and_run_status_remain_blocked",
        passed=dotted_get(payloads.get("alpha_matrix"), "alpha_evidence_ready") is False
        and dotted_get(payloads.get("alpha_closeout"), "verdict")
        == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and dotted_get(payloads.get("alpha_closeout"), "future_modeling_allowed") is False
        and dotted_get(payloads.get("alpha_closeout"), "promotion_allowed") is False
        and dotted_get(payloads.get("run_status"), "summary.data_model_commands_executed") is False
        and dotted_get(payloads.get("run_status"), "summary.wfa_modeling_executed") is False
        and dotted_get(payloads.get("run_status"), "summary.predictions_executed") is False
        and dotted_get(payloads.get("run_status"), "summary.provider_network_calls_executed") is False
        and dotted_get(payloads.get("run_status"), "summary.promotion_or_freeze_or_holdout_executed")
        is False
        and dotted_get(payloads.get("run_status"), "summary.paper_or_live_executed") is False,
        failure="alpha closeout, run status, or forbidden execution flags no longer remain blocked",
        evidence=[ALPHA_MATRIX.as_posix(), ALPHA_CLOSEOUT.as_posix(), RUN_STATUS.as_posix()],
    )
    for item in evidence_rows:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))
    failures.extend(payload_failures)
    failures.extend(trial_errors)
    failures.extend(experiment_errors)
    failures = list(dict.fromkeys(failures))
    status = PASS_STATUS if not failures else FAIL_STATUS
    pbo_status = READY_STATUS if status == PASS_STATUS else "FAIL_POST_MUTATION_TRIAL_LEDGER_INPUTS_INCOMPLETE"
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_post_mutation_trial_search_completeness_reconciliation_report_only",
            "reports_root": output_rel,
            "evidence_mode": "existing_local_post_mutation_canonical_evidence_only",
            "ledger_mutation_scope": "none",
            "registry_mutation_scope": "none",
            "trial_status_mutation_scope": "none",
            "statistical_recompute_scope": "none",
            "report_refresh_scope": "this_report_pair_only",
            "data_model_scope": "none",
            "provider_scope": "none",
            "allowed_inputs": [rel(resolve_path(repo_root, path), repo_root) for path in paths.values()],
        },
        "summary": {
            "status": status,
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": sum(1 for item in checks if item["status"] == "PASS"),
            "failed_check_count": sum(1 for item in checks if item["status"] == "FAIL"),
            "trial_ledger_search_path_complete": status == PASS_STATUS,
            "pbo_status": pbo_status,
            "deflated_sharpe_status": pbo_status,
            "multiple_testing_status": pbo_status,
            "pbo_applicability_ready": status == PASS_STATUS,
            "deflated_sharpe_applicability_ready": status == PASS_STATUS,
            "multiple_testing_applicability_ready": status == PASS_STATUS,
            "separate_statistical_recompute_required": True,
            "statistical_recompute_executed": False,
            "statistical_validity_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
            "registry_hypothesis_count": len(registry),
            "registry_master_audit_note_count": note_count,
            "trial_status_row_count": len(trial_rows),
            "family_metadata_row_count": len(family_rows),
            "search_family_count": len(search_families),
            "multiple_testing_family_count": len(multiple_testing_families),
            "experiment_ledger_row_count": len(experiment_rows),
            "exclusion_candidate_preserved_report_local_count": EXPECTED_EXCLUSIONS,
            "current_statistical_summary_status": statistical.get("status") if statistical else None,
            "current_statistical_summary_failure_count": statistical.get("failure_count") if statistical else None,
            "current_pbo_summary_status": pbo.get("status"),
            "current_deflated_sharpe_summary_status": deflated.get("status"),
            "current_multiple_testing_summary_status": multiple.get("status"),
            "current_probabilistic_sharpe_status": probabilistic.get("status"),
            "current_regime_breakdowns_status": regimes.get("status"),
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
            "current_git_status_short_count": len(status_lines),
        },
        "trial_search_coverage": {
            "search_families": search_families,
            "multiple_testing_families": multiple_testing_families,
            "family_metadata_trial_ids": [str(row.get("trial_id")) for row in family_rows],
        },
        "input_evidence": evidence_rows,
        "checks": checks,
        "failures": failures,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan a separately approved statistical-validity recompute or recompute-decision "
            "using the canonical trial/search family counts. Do not run modeling, Phase 8, "
            "promotion, paper/live, or production work."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Post-Mutation Trial/Search Completeness Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Trial/search path complete: `{summary['trial_ledger_search_path_complete']}`",
        f"- PBO status: `{summary['pbo_status']}`",
        f"- Deflated Sharpe status: `{summary['deflated_sharpe_status']}`",
        f"- Multiple-testing status: `{summary['multiple_testing_status']}`",
        f"- Statistical recompute executed: `{summary['statistical_recompute_executed']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Coverage",
        "",
        f"- Registry hypotheses: `{summary['registry_hypothesis_count']}`",
        f"- Master Audit registry notes: `{summary['registry_master_audit_note_count']}`",
        f"- Trial-status rows: `{summary['trial_status_row_count']}`",
        f"- Family-metadata rows: `{summary['family_metadata_row_count']}`",
        f"- Search families: `{summary['search_family_count']}`",
        f"- Multiple-testing families: `{summary['multiple_testing_family_count']}`",
        f"- Experiment-ledger rows: `{summary['experiment_ledger_row_count']}`",
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
            "- This reconciliation is report-only. It does not recompute statistical validity, accept PBO/Deflated Sharpe/multiple-testing statistics, approve model trust, approve promotion, approve paper/live, or approve production.",
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
        f"family_rows={report['summary']['family_metadata_row_count']} "
        f"search_families={report['summary']['search_family_count']} "
        f"multiple_testing_families={report['summary']['multiple_testing_family_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
