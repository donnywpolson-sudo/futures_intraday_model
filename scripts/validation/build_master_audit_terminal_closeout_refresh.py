#!/usr/bin/env python3
"""Build a report-only final Master Audit terminal closeout refresh."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_terminal_closeout_refresh"
PASS_STATUS = "PASS_MASTER_AUDIT_TERMINAL_CLOSEOUT_REFRESH_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_TERMINAL_CLOSEOUT_REFRESH_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_terminal_closeout_refresh_20260710")
REPORT_JSON = "master_audit_terminal_closeout_refresh.json"
REPORT_MD = "master_audit_terminal_closeout_refresh.md"

STATISTICAL_CLOSEOUT_BOUNDARY = Path(
    "reports/master_audit/master_audit_statistical_validity_closeout_boundary_decision_20260710/"
    "master_audit_statistical_validity_closeout_boundary_decision.json"
)
AFTER_PHASE2_GAP_MAP = Path(
    "reports/master_audit/master_audit_gap_remediation_after_phase2_20260710/"
    "master_audit_gap_remediation_evidence_map.json"
)
MASTER_AUDIT_CLOSEOUT = Path(
    "reports/master_audit/master_audit_closeout_20260709/master_audit_closeout.json"
)
MODEL_TRUST_AUDIT = Path(
    "reports/model_trust_audit/codex_model_trust_audit_20260707T000000Z/model_trust_audit.json"
)
ALPHA_CLOSEOUT = Path(
    "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
    "alpha_evidence_completion_closeout.json"
)
RUN_STATUS = Path("reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json")
ADVERSARIAL_AUDIT = Path("docs/adversarial_current_project_evidence_gate_audit_20260709.md")

REQUIRED_INPUTS = {
    "statistical_closeout_boundary": STATISTICAL_CLOSEOUT_BOUNDARY,
    "after_phase2_gap_map": AFTER_PHASE2_GAP_MAP,
    "master_audit_closeout": MASTER_AUDIT_CLOSEOUT,
    "model_trust_audit": MODEL_TRUST_AUDIT,
    "alpha_closeout": ALPHA_CLOSEOUT,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

TERMINAL_CLOSEOUT_DECISION = "TERMINAL_CLOSEOUT_CURRENT_LINE_CLOSED_BLOCKED_REPORT_ONLY"
STATISTICAL_BOUNDARY_DECISION = (
    "PERMANENTLY_BLOCK_CURRENT_LINE_STATISTICAL_VALIDITY_GAP_FROM_EXISTING_EVIDENCE"
)

NON_APPROVAL = {
    "ledger_mutation_executed": False,
    "registry_mutation_executed": False,
    "trial_status_mutation_executed": False,
    "report_mutation_outside_output_pair_executed": False,
    "data_model_artifact_mutation_executed": False,
    "gap_map_refresh_executed": False,
    "statistical_report_generation_executed": False,
    "wfa_modeling_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "artifact_freeze_executed": False,
    "final_holdout_executed": False,
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


def summary_of(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, Mapping) else {}


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
        "statistical_closeout_boundary": {
            "status": "status",
            "decision": "summary.closeout_boundary_decision",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "after_phase2_gap_map": {
            "status": "status",
            "data_integrity_ready": "summary.data_integrity_ready",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "operational_resilience_ready": "summary.operational_resilience_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "master_audit_closeout": {
            "status": "status",
            "closeout_classification": "summary.closeout_classification",
            "full_master_audit_accepted": "summary.full_master_audit_accepted",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "model_trust_audit": {
            "status": "status",
            "permitted_use_label": "permitted_use_label",
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


def _all_non_approval_false(payload: Mapping[str, Any]) -> bool:
    non_approval = payload.get("non_approval")
    return isinstance(non_approval, Mapping) and all(value is False for value in non_approval.values())


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

    stat_boundary = payloads.get("statistical_closeout_boundary", {})
    stat_summary = summary_of(stat_boundary)
    stat_boundary_ready = (
        stat_boundary.get("status")
        == "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_CLOSEOUT_BOUNDARY_DECISION_REPORT_ONLY"
        and stat_summary.get("closeout_boundary_decision") == STATISTICAL_BOUNDARY_DECISION
        and stat_summary.get("statistical_validity") == "FAIL"
        and stat_summary.get("statistical_validity_ready") is False
        and stat_summary.get("master_audit_statistical_validity_accepted") is False
        and stat_summary.get("model_trust_ready") is False
        and stat_summary.get("promotion_allowed") is False
        and stat_summary.get("gap_map_refresh_allowed") is False
        and stat_summary.get("statistical_validity_gap_upgrade_allowed") is False
    )
    check(
        checks,
        failures,
        name="statistical_closeout_boundary_preserved",
        passed=stat_boundary_ready,
        failure="statistical-validity closeout boundary is missing, not PASS, or no longer blocked",
        evidence=[rel(resolve_path(repo_root, paths["statistical_closeout_boundary"]), repo_root)],
        details={
            "status": stat_boundary.get("status"),
            "decision": stat_summary.get("closeout_boundary_decision"),
            "statistical_validity": stat_summary.get("statistical_validity"),
            "statistical_validity_ready": stat_summary.get("statistical_validity_ready"),
            "promotion_allowed": stat_summary.get("promotion_allowed"),
        },
    )

    gap_map = payloads.get("after_phase2_gap_map", {})
    gap_summary = summary_of(gap_map)
    gap_statuses = gap_summary.get("gap_area_statuses")
    gap_statuses = gap_statuses if isinstance(gap_statuses, Mapping) else {}
    after_phase2_ready = (
        gap_map.get("status") == "PASS_MASTER_AUDIT_GAP_REMEDIATION_EVIDENCE_MAP_REPORT_ONLY"
        and gap_summary.get("data_integrity_ready") is True
        and gap_summary.get("statistical_validity_ready") is False
        and gap_summary.get("operational_resilience_ready") is False
        and gap_summary.get("model_trust_ready") is False
        and gap_summary.get("promotion_allowed") is False
        and gap_summary.get("paper_live_ready") is False
        and gap_summary.get("production_ready") is False
        and gap_statuses.get("data_integrity") == "PASS"
        and gap_statuses.get("statistical_validity") == "FAIL"
        and gap_statuses.get("operational_resilience") == "FAIL"
    )
    check(
        checks,
        failures,
        name="after_phase2_gap_map_preserves_terminal_statuses",
        passed=after_phase2_ready,
        failure="after-Phase-2 gap map no longer preserves PASS data integrity and blocked downstream statuses",
        evidence=[rel(resolve_path(repo_root, paths["after_phase2_gap_map"]), repo_root)],
        details={
            "status": gap_map.get("status"),
            "gap_area_statuses": dict(gap_statuses),
            "data_integrity_ready": gap_summary.get("data_integrity_ready"),
            "statistical_validity_ready": gap_summary.get("statistical_validity_ready"),
            "operational_resilience_ready": gap_summary.get("operational_resilience_ready"),
        },
    )

    closeout = payloads.get("master_audit_closeout", {})
    closeout_summary = summary_of(closeout)
    closeout_ready = (
        closeout.get("status") == "PASS_MASTER_AUDIT_CLOSEOUT_REPORT_ONLY"
        and closeout_summary.get("closeout_classification") == "REPORT_ONLY_CLOSEOUT_BLOCKED_NOT_READY"
        and closeout_summary.get("current_line_classification") == "closed_no_alpha_evidence"
        and closeout_summary.get("full_master_audit_accepted") is False
        and closeout_summary.get("model_trust_ready") is False
        and closeout_summary.get("promotion_allowed") is False
        and closeout_summary.get("artifact_freeze_ready") is False
        and closeout_summary.get("final_holdout_ready") is False
        and closeout_summary.get("paper_live_ready") is False
        and closeout_summary.get("production_ready") is False
    )
    check(
        checks,
        failures,
        name="prior_master_audit_closeout_blocked_preserved",
        passed=closeout_ready,
        failure="prior Master Audit closeout no longer preserves blocked/not-ready state",
        evidence=[rel(resolve_path(repo_root, paths["master_audit_closeout"]), repo_root)],
        details={
            "status": closeout.get("status"),
            "closeout_classification": closeout_summary.get("closeout_classification"),
            "full_master_audit_accepted": closeout_summary.get("full_master_audit_accepted"),
            "promotion_allowed": closeout_summary.get("promotion_allowed"),
        },
    )

    model_trust = payloads.get("model_trust_audit", {})
    model_trust_ready = (
        model_trust.get("status") == "PASS_REPORT_WRITTEN"
        and model_trust.get("permitted_use_label") == "research_only"
        and _all_non_approval_false(model_trust)
    )
    check(
        checks,
        failures,
        name="model_trust_audit_research_only_preserved",
        passed=model_trust_ready,
        failure="model-trust audit no longer preserves research-only non-approval state",
        evidence=[rel(resolve_path(repo_root, paths["model_trust_audit"]), repo_root)],
        details={
            "status": model_trust.get("status"),
            "permitted_use_label": model_trust.get("permitted_use_label"),
            "non_approval": dict(model_trust.get("non_approval", {}))
            if isinstance(model_trust.get("non_approval"), Mapping)
            else {},
        },
    )

    alpha_closeout = payloads.get("alpha_closeout", {})
    alpha_ready = (
        alpha_closeout.get("status") == "PASS_REPORT_WRITTEN"
        and alpha_closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("promotion_allowed") is False
    )
    check(
        checks,
        failures,
        name="alpha_closeout_closed_line_preserved",
        passed=alpha_ready,
        failure="alpha closeout no longer preserves closed/no-alpha verdict",
        evidence=[rel(resolve_path(repo_root, paths["alpha_closeout"]), repo_root)],
        details={
            "status": alpha_closeout.get("status"),
            "verdict": alpha_closeout.get("verdict"),
            "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
            "promotion_allowed": alpha_closeout.get("promotion_allowed"),
        },
    )

    run_status = payloads.get("run_status", {})
    run_summary = summary_of(run_status)
    run_flags_clear = (
        run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and run_summary.get("data_model_commands_executed") is False
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
        "terminal_closeout_decision": TERMINAL_CLOSEOUT_DECISION,
        "current_line_classification": "closed_no_alpha_evidence",
        "data_integrity": "PASS",
        "data_integrity_ready": True,
        "statistical_validity": "FAIL",
        "statistical_validity_ready": False,
        "operational_resilience": "FAIL",
        "operational_resilience_ready": False,
        "full_master_audit_accepted": False,
        "model_trust_ready": False,
        "promotion_allowed": False,
        "artifact_freeze_ready": False,
        "final_holdout_ready": False,
        "paper_live_ready": False,
        "production_ready": False,
        "gap_map_refresh_allowed": False,
        "gap_map_refresh_executed": False,
        "statistical_validity_closeout_boundary_decision": stat_summary.get(
            "closeout_boundary_decision"
        ),
        "prior_master_audit_closeout_classification": closeout_summary.get(
            "closeout_classification"
        ),
        "alpha_closeout_verdict": alpha_closeout.get("verdict"),
        "model_trust_permitted_use_label": model_trust.get("permitted_use_label"),
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
            "finding_id": "current_line_terminally_closed_blocked_report_only",
            "severity": "BLOCKER",
            "finding": (
                "The current line is closed and blocked: data integrity is remediated, but "
                "statistical validity and operational resilience remain failed and model trust is not ready."
            ),
            "evidence_paths": [
                STATISTICAL_CLOSEOUT_BOUNDARY.as_posix(),
                AFTER_PHASE2_GAP_MAP.as_posix(),
                MASTER_AUDIT_CLOSEOUT.as_posix(),
            ],
        },
        {
            "finding_id": "no_downstream_approval",
            "severity": "INFO",
            "finding": (
                "This terminal closeout refresh does not authorize modeling, promotion, artifact freeze, "
                "final holdout, paper/live, production, cleanup, staging, commit, or push."
            ),
            "evidence_paths": [ALPHA_CLOSEOUT.as_posix(), MODEL_TRUST_AUDIT.as_posix()],
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
            "operation": "master_audit_terminal_closeout_refresh_report_only",
            "target": "final_current_line_closed_blocked_status",
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
                "data integrity remains PASS after Phase 2 gap remediation",
                "statistical validity and operational resilience remain FAIL",
                "current line remains closed/no-alpha and full Master Audit is not accepted",
                "model trust, promotion, artifact freeze, final holdout, paper/live, and production remain blocked",
            ],
            "fail": [
                "missing/unreadable required input",
                "any downstream readiness flag is upgraded",
                "any forbidden execution flag is true",
                "output root is outside reports/master_audit",
            ],
        },
        "recommended_next_action": (
            "Treat this as terminal current-line closeout evidence only; do not proceed to modeling, "
            "promotion, paper/live, production, cleanup, or git publication without separate approval."
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
        "# Master Audit Terminal Closeout Refresh",
        "",
        f"- Status: `{report['status']}`",
        f"- Failure count: `{summary['failure_count']}`",
        f"- Decision: `{summary['terminal_closeout_decision']}`",
        f"- Data integrity: `{summary['data_integrity']}`",
        f"- Statistical validity: `{summary['statistical_validity']}`",
        f"- Operational resilience: `{summary['operational_resilience']}`",
        f"- Full Master Audit accepted: `{summary['full_master_audit_accepted']}`",
        f"- Model trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        f"- Paper/live ready: `{summary['paper_live_ready']}`",
        f"- Production ready: `{summary['production_ready']}`",
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
            "- This refresh did not mutate ledgers, registry, trial statuses, reports outside its own output pair, data/model artifacts, gap maps, WFA/modeling, predictions, Phase 8 outputs, provider state, promotion state, staging, commits, or pushes.",
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
        f"decision={report['summary']['terminal_closeout_decision']} "
        f"model_trust_ready={report['summary']['model_trust_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
