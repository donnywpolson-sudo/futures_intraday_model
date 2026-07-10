#!/usr/bin/env python3
"""Build a report-only Master Audit statistical-validity closeout boundary decision."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_statistical_validity_closeout_boundary_decision"
PASS_STATUS = "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_CLOSEOUT_BOUNDARY_DECISION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_STATISTICAL_VALIDITY_CLOSEOUT_BOUNDARY_DECISION_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_statistical_validity_closeout_boundary_decision_20260710"
)
REPORT_JSON = "master_audit_statistical_validity_closeout_boundary_decision.json"
REPORT_MD = "master_audit_statistical_validity_closeout_boundary_decision.md"

ACCEPTANCE_BOUNDARY = Path(
    "reports/master_audit/master_audit_statistical_validity_acceptance_boundary_decision_20260710/"
    "master_audit_statistical_validity_acceptance_boundary_decision.json"
)
POST_RECOMPUTE_RECONCILIATION = Path(
    "reports/master_audit/master_audit_post_recompute_statistical_validity_reconciliation_20260710/"
    "master_audit_post_recompute_statistical_validity_reconciliation.json"
)
REGIME_ADVERSARIAL_DISPOSITION = Path(
    "reports/master_audit/master_audit_statistical_validity_regime_adversarial_disposition_20260710/"
    "master_audit_statistical_validity_regime_adversarial_disposition.json"
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
    "acceptance_boundary": ACCEPTANCE_BOUNDARY,
    "post_recompute_reconciliation": POST_RECOMPUTE_RECONCILIATION,
    "regime_adversarial_disposition": REGIME_ADVERSARIAL_DISPOSITION,
    "alpha_matrix": ALPHA_MATRIX,
    "alpha_closeout": ALPHA_CLOSEOUT,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

ACCEPTANCE_BOUNDARY_DECISION = (
    "BLOCK_STATISTICAL_VALIDITY_ACCEPTANCE_CURRENT_LINE_TERMINAL_FAILS_AND_MISSING_NULL_REGIME_EVIDENCE"
)
CLOSEOUT_BOUNDARY_DECISION = (
    "PERMANENTLY_BLOCK_CURRENT_LINE_STATISTICAL_VALIDITY_GAP_FROM_EXISTING_EVIDENCE"
)

NON_APPROVAL = {
    "ledger_mutation_executed": False,
    "registry_mutation_executed": False,
    "trial_status_mutation_executed": False,
    "report_mutation_outside_output_pair_executed": False,
    "data_model_artifact_mutation_executed": False,
    "gap_map_refresh_executed": False,
    "generated_report_execution_executed": False,
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
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


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
            if not resolved.is_file():
                failures.append(f"missing input: {rel(resolved, repo_root)}")
            continue
        payload, error = read_json_object(resolved)
        if error or payload is None:
            failures.append(error or f"missing JSON input: {rel(resolved, repo_root)}")
            payloads[name] = {}
        else:
            payloads[name] = payload
    return payloads, failures


def evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    fields = {
        "acceptance_boundary": {
            "status": "status",
            "decision": "summary.acceptance_boundary_decision",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "post_recompute_reconciliation": {
            "status": "status",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "regime_adversarial_disposition": {
            "status": "status",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "alpha_matrix": {
            "status": "status",
            "alpha_evidence_ready": "alpha_evidence_ready",
            "model_trust_ready": "model_trust_ready",
        },
        "alpha_closeout": {
            "status": "status",
            "verdict": "verdict",
            "promotion_allowed": "promotion_allowed",
        },
        "run_status": {
            "status": "status",
            "data_model_commands_executed": "summary.data_model_commands_executed",
            "wfa_modeling_executed": "summary.wfa_modeling_executed",
            "predictions_executed": "summary.predictions_executed",
        },
    }
    return [
        inventory.evidence_file(
            repo_root=repo_root,
            relative_path=path,
            json_fields=fields.get(name, {}),
            dirty_map=dirty_map,
        )
        for name, path in paths.items()
    ]


def summary_of(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _blocked_flags_false(summary: Mapping[str, Any]) -> bool:
    return (
        summary.get("statistical_validity_ready") is False
        and summary.get("master_audit_statistical_validity_accepted") is False
        and summary.get("model_trust_ready") is False
        and summary.get("promotion_allowed") is False
    )


def build_checks(
    *,
    repo_root: Path,
    reports_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    paths: Mapping[str, Path],
    non_approval: Mapping[str, bool],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    output_rel = rel(reports_root, repo_root)
    missing_paths = [
        rel(resolve_path(repo_root, path), repo_root)
        for path in paths.values()
        if not resolve_path(repo_root, path).is_file()
    ]
    check(
        checks,
        failures,
        name="required_inputs_present",
        passed=not missing_paths,
        failure=f"missing required inputs: {missing_paths}",
        evidence=[rel(resolve_path(repo_root, path), repo_root) for path in paths.values()],
        details={"missing_paths": missing_paths},
    )
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel.startswith("reports/master_audit/"),
        failure=f"invalid report output root: {output_rel}",
        details={"reports_root": output_rel},
    )

    acceptance = payloads.get("acceptance_boundary", {})
    acceptance_summary = summary_of(acceptance)
    acceptance_ready = (
        acceptance.get("status")
        == "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_ACCEPTANCE_BOUNDARY_DECISION_REPORT_ONLY"
        and acceptance_summary.get("acceptance_boundary_decision") == ACCEPTANCE_BOUNDARY_DECISION
        and acceptance_summary.get("remaining_statistical_validity_blockers_actionable_for_current_line")
        is False
        and acceptance_summary.get(
            "new_generated_null_regime_or_variant_evidence_required_for_any_future_reconsideration"
        )
        is True
        and _blocked_flags_false(acceptance_summary)
    )
    check(
        checks,
        failures,
        name="acceptance_boundary_pass_preserved",
        passed=acceptance_ready,
        failure="acceptance-boundary report is not PASS or no longer preserves blocked current-line decision",
        evidence=[rel(resolve_path(repo_root, paths["acceptance_boundary"]), repo_root)],
        details={
            "status": acceptance.get("status"),
            "decision": acceptance_summary.get("acceptance_boundary_decision"),
            "statistical_validity_ready": acceptance_summary.get("statistical_validity_ready"),
            "promotion_allowed": acceptance_summary.get("promotion_allowed"),
        },
    )

    post = payloads.get("post_recompute_reconciliation", {})
    post_summary = summary_of(post)
    post_ready = (
        post.get("status")
        == "PASS_MASTER_AUDIT_POST_RECOMPUTE_STATISTICAL_VALIDITY_RECONCILIATION_REPORT_ONLY"
        and post_summary.get("pbo_status") == "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"
        and post_summary.get("deflated_sharpe_status")
        == "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
        and post_summary.get("multiple_testing_status") == "FAIL_BONFERRONI_ADJUSTED_PSR"
        and post_summary.get("probabilistic_sharpe_status") == "FAIL"
        and post_summary.get("regime_breakdowns_status") == "FAIL"
        and _blocked_flags_false(post_summary)
    )
    check(
        checks,
        failures,
        name="post_recompute_failures_preserved",
        passed=post_ready,
        failure="post-recompute statistical blockers are not preserved",
        evidence=[rel(resolve_path(repo_root, paths["post_recompute_reconciliation"]), repo_root)],
        details={
            "status": post.get("status"),
            "pbo_status": post_summary.get("pbo_status"),
            "deflated_sharpe_status": post_summary.get("deflated_sharpe_status"),
            "multiple_testing_status": post_summary.get("multiple_testing_status"),
            "probabilistic_sharpe_status": post_summary.get("probabilistic_sharpe_status"),
            "regime_breakdowns_status": post_summary.get("regime_breakdowns_status"),
        },
    )

    regime = payloads.get("regime_adversarial_disposition", {})
    regime_summary = summary_of(regime)
    regime_ready = (
        regime.get("status")
        == "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_REGIME_ADVERSARIAL_DISPOSITION_REPORT_ONLY"
        and regime_summary.get("random_entry_null_disposition")
        == "TERMINAL_FAIL_CANDIDATE_DOES_NOT_BEAT_RANDOM_MEDIAN"
        and regime_summary.get("two_x_cost_stress_disposition")
        == "TERMINAL_FAIL_EDGE_DOES_NOT_SURVIVE_2X_COST"
        and regime_summary.get("label_shuffle_disposition")
        == "MISSING_REQUIRED_EVIDENCE_SEPARATE_BOUNDED_SHUFFLE_HARNESS_REQUIRED"
        and regime_summary.get("timing_shift_disposition")
        == "MISSING_REQUIRED_EVIDENCE_SEPARATE_BOUNDED_TIMING_SHIFT_HARNESS_REQUIRED"
        and regime_summary.get("regime_breakdowns_disposition")
        == "FAIL_MISSING_EXPLICIT_CAUSAL_REGIME_EVIDENCE_NOT_ACTIONABLE_FOR_CURRENT_LINE"
        and _blocked_flags_false(regime_summary)
    )
    check(
        checks,
        failures,
        name="regime_adversarial_blockers_preserved",
        passed=regime_ready,
        failure="regime/adversarial blockers are not preserved",
        evidence=[rel(resolve_path(repo_root, paths["regime_adversarial_disposition"]), repo_root)],
        details={
            "status": regime.get("status"),
            "random_entry_null_disposition": regime_summary.get("random_entry_null_disposition"),
            "two_x_cost_stress_disposition": regime_summary.get("two_x_cost_stress_disposition"),
            "label_shuffle_disposition": regime_summary.get("label_shuffle_disposition"),
            "timing_shift_disposition": regime_summary.get("timing_shift_disposition"),
            "regime_breakdowns_disposition": regime_summary.get("regime_breakdowns_disposition"),
        },
    )

    alpha_matrix = payloads.get("alpha_matrix", {})
    alpha_closeout = payloads.get("alpha_closeout", {})
    alpha_ready = (
        alpha_matrix.get("alpha_evidence_ready") is False
        and alpha_matrix.get("model_trust_ready") is not True
        and alpha_matrix.get("promotion_allowed") is not True
        and alpha_closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("promotion_allowed") is False
    )
    check(
        checks,
        failures,
        name="alpha_closeout_preserves_closed_line",
        passed=alpha_ready,
        failure="alpha matrix/closeout no longer preserves closed current line",
        evidence=[
            rel(resolve_path(repo_root, paths["alpha_matrix"]), repo_root),
            rel(resolve_path(repo_root, paths["alpha_closeout"]), repo_root),
        ],
        details={
            "alpha_evidence_ready": alpha_matrix.get("alpha_evidence_ready"),
            "model_trust_ready": alpha_matrix.get("model_trust_ready"),
            "closeout_verdict": alpha_closeout.get("verdict"),
            "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
            "promotion_allowed": alpha_closeout.get("promotion_allowed"),
        },
    )

    gap_upgrade_blocked = (
        CLOSEOUT_BOUNDARY_DECISION
        == "PERMANENTLY_BLOCK_CURRENT_LINE_STATISTICAL_VALIDITY_GAP_FROM_EXISTING_EVIDENCE"
    )
    check(
        checks,
        failures,
        name="gap_map_upgrade_not_allowed",
        passed=gap_upgrade_blocked,
        failure="closeout boundary allows gap-map/statistical-validity upgrade",
        details={
            "closeout_boundary_decision": CLOSEOUT_BOUNDARY_DECISION,
            "gap_map_refresh_allowed": False,
            "statistical_validity_gap_upgrade_allowed": False,
        },
    )

    run_status = payloads.get("run_status", {})
    run_summary = summary_of(run_status)
    run_flags_clear = (
        run_summary.get("data_model_commands_executed") is False
        and run_summary.get("wfa_modeling_executed") is False
        and run_summary.get("predictions_executed") is False
        and run_summary.get("provider_network_calls_executed") is False
        and run_summary.get("promotion_or_freeze_or_holdout_executed") is False
        and run_summary.get("paper_or_live_executed") is False
        and run_summary.get("cleanup_or_git_publication_executed") is False
    )
    check(
        checks,
        failures,
        name="non_approval_flags_remain_false",
        passed=run_flags_clear and all(value is False for value in non_approval.values()),
        failure="run-status or report-local non-approval flags show forbidden execution",
        evidence=[rel(resolve_path(repo_root, paths["run_status"]), repo_root)],
        details={"run_summary": dict(run_summary), "non_approval": dict(non_approval)},
    )

    derived = {
        "closeout_boundary_decision": CLOSEOUT_BOUNDARY_DECISION,
        "acceptance_boundary_decision": acceptance_summary.get("acceptance_boundary_decision"),
        "current_line_statistical_validity_gap_permanently_blocked_from_existing_evidence": True,
        "statistical_validity_gap_upgrade_allowed": False,
        "gap_map_refresh_allowed": False,
        "gap_map_refresh_executed": False,
        "future_generated_null_regime_or_variant_evidence_required_for_reconsideration": True,
        "pbo_status": post_summary.get("pbo_status"),
        "deflated_sharpe_status": post_summary.get("deflated_sharpe_status"),
        "multiple_testing_status": post_summary.get("multiple_testing_status"),
        "probabilistic_sharpe_status": post_summary.get("probabilistic_sharpe_status"),
        "regime_breakdowns_status": post_summary.get("regime_breakdowns_status"),
        "random_entry_null_disposition": regime_summary.get("random_entry_null_disposition"),
        "two_x_cost_stress_disposition": regime_summary.get("two_x_cost_stress_disposition"),
        "label_shuffle_disposition": regime_summary.get("label_shuffle_disposition"),
        "timing_shift_disposition": regime_summary.get("timing_shift_disposition"),
        "regime_breakdowns_disposition": regime_summary.get("regime_breakdowns_disposition"),
        "alpha_closeout_verdict": alpha_closeout.get("verdict"),
        "statistical_validity": "FAIL",
        "statistical_validity_ready": False,
        "master_audit_statistical_validity_accepted": False,
        "model_trust_ready": False,
        "promotion_allowed": False,
        "paper_live_ready": False,
        "production_ready": False,
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in findings:
        severity = str(item.get("severity", "UNKNOWN"))
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def build_findings() -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "current_line_statistical_validity_gap_permanently_blocked",
            "severity": "BLOCKER",
            "finding": (
                "The current line's statistical-validity gap remains FAIL and is permanently "
                "blocked from acceptance using the existing evidence set."
            ),
            "evidence_paths": [
                ACCEPTANCE_BOUNDARY.as_posix(),
                POST_RECOMPUTE_RECONCILIATION.as_posix(),
                REGIME_ADVERSARIAL_DISPOSITION.as_posix(),
            ],
        },
        {
            "finding_id": "gap_map_upgrade_disallowed_report_only",
            "severity": "INFO",
            "finding": (
                "This report does not refresh the gap map or authorize statistical-validity, "
                "model-trust, promotion, paper/live, or production readiness."
            ),
            "evidence_paths": [ALPHA_CLOSEOUT.as_posix()],
        },
    ]


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_input_overrides: Mapping[str, Path] | None = None,
    non_approval_overrides: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = resolve_path(repo_root, reports_root).resolve()
    paths = dict(REQUIRED_INPUTS)
    if required_input_overrides:
        paths.update(required_input_overrides)
    non_approval = dict(NON_APPROVAL)
    if non_approval_overrides:
        non_approval.update(non_approval_overrides)
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
    input_evidence = evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    checks, check_failures, derived = build_checks(
        repo_root=repo_root,
        reports_root=reports_root,
        payloads=payloads,
        paths=paths,
        non_approval=non_approval,
    )
    failures = input_failures + check_failures
    status = PASS_STATUS if not failures else FAIL_STATUS
    findings = build_findings()
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_statistical_validity_closeout_boundary_decision_report_only",
            "target_gap_area": "statistical_validity",
            "reports_root": rel(reports_root, repo_root),
            "evidence_mode": "existing_local_json_md_repo_evidence_only",
            "data_model_scope": "none",
            "provider_scope": "none",
            "gap_map_refresh_scope": "none",
            "allowed_inputs": [rel(resolve_path(repo_root, path), repo_root) for path in paths.values()],
        },
        "summary": {
            "status": status,
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            **derived,
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
            "finding_counts": finding_counts(findings),
            **non_approval,
        },
        "input_evidence": input_evidence,
        "checks": checks,
        "findings": findings,
        "non_approval": non_approval,
        "pass_fail_criteria": {
            "pass": [
                "acceptance-boundary, post-recompute, and regime/adversarial reports are PASS and still blocked",
                "current line statistical-validity closeout is permanently blocked from existing evidence",
                "gap-map refresh and statistical-validity upgrade are not allowed",
                "model trust, promotion, paper/live, and production remain blocked",
            ],
            "fail": [
                "missing/unreadable required input",
                "any upstream blocker is silently upgraded to PASS",
                "any readiness or non-approval flag is upgraded",
                "output root is outside reports/master_audit",
            ],
        },
        "recommended_next_action": (
            "Use this as report-only closeout evidence for the current line; do not refresh the gap map "
            "or reopen statistical validity without separately approved new generated evidence."
        ),
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "failures": failures,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Statistical-Validity Closeout Boundary Decision",
        "",
        f"- Status: `{report['status']}`",
        f"- Failure count: `{summary['failure_count']}`",
        f"- Decision: `{summary['closeout_boundary_decision']}`",
        f"- Statistical validity: `{summary['statistical_validity']}`",
        f"- Statistical validity ready: `{summary['statistical_validity_ready']}`",
        f"- Master Audit statistical accepted: `{summary['master_audit_statistical_validity_accepted']}`",
        f"- Gap-map refresh allowed: `{summary['gap_map_refresh_allowed']}`",
        f"- Statistical-validity gap upgrade allowed: `{summary['statistical_validity_gap_upgrade_allowed']}`",
        f"- Model trust ready: `{summary['model_trust_ready']}`",
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
    lines.extend(["", "## Findings", ""])
    for item in report["findings"]:
        lines.append(
            "- `{severity}` `{finding_id}`: {finding}".format(
                severity=item["severity"],
                finding_id=item["finding_id"],
                finding=item["finding"],
            )
        )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in report.get("failures", [])] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This decision did not mutate ledgers, registry, trial statuses, reports outside its own output pair, data/model artifacts, gap maps, WFA/modeling, predictions, Phase 8 outputs, provider state, promotion state, staging, commits, or pushes.",
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
        f"decision={report['summary']['closeout_boundary_decision']} "
        f"statistical_validity_ready={report['summary']['statistical_validity_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
