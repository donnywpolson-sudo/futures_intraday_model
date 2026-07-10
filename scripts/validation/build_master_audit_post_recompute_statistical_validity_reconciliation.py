#!/usr/bin/env python3
"""Build a report-only post-recompute statistical-validity reconciliation."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_post_recompute_statistical_validity_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_POST_RECOMPUTE_STATISTICAL_VALIDITY_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_POST_RECOMPUTE_STATISTICAL_VALIDITY_RECONCILIATION_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_post_recompute_statistical_validity_reconciliation_20260710"
)
REPORT_JSON = "master_audit_post_recompute_statistical_validity_reconciliation.json"
REPORT_MD = "master_audit_post_recompute_statistical_validity_reconciliation.md"

RECOMPUTE_ROOT = Path(
    "reports/statistical_validity/tier1_core_phase6_full_predictions_20260706_trial_search_recompute_20260710"
)
RECOMPUTE_SUMMARY = RECOMPUTE_ROOT / "statistical_validity_summary.json"
RECOMPUTE_BOOTSTRAP = RECOMPUTE_ROOT / "bootstrap_confidence_intervals.csv"
RECOMPUTE_STABILITY = RECOMPUTE_ROOT / "stability_matrix.csv"
RECOMPUTE_ADVERSARIAL = RECOMPUTE_ROOT / "adversarial_tests.csv"
RECOMPUTE_MD = RECOMPUTE_ROOT / "statistical_validity.md"
RECOMPUTE_DECISION = Path(
    "reports/master_audit/master_audit_statistical_validity_recompute_decision_20260710/"
    "master_audit_statistical_validity_recompute_decision.json"
)
POST_MUTATION_COMPLETENESS = Path(
    "reports/master_audit/master_audit_post_mutation_trial_search_completeness_reconciliation_20260710/"
    "master_audit_post_mutation_trial_search_completeness_reconciliation.json"
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
    "recompute_summary": RECOMPUTE_SUMMARY,
    "recompute_bootstrap": RECOMPUTE_BOOTSTRAP,
    "recompute_stability": RECOMPUTE_STABILITY,
    "recompute_adversarial": RECOMPUTE_ADVERSARIAL,
    "recompute_markdown": RECOMPUTE_MD,
    "recompute_decision": RECOMPUTE_DECISION,
    "post_mutation_completeness": POST_MUTATION_COMPLETENESS,
    "alpha_matrix": ALPHA_MATRIX,
    "alpha_closeout": ALPHA_CLOSEOUT,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

NON_APPROVAL = {
    "ledger_mutation_executed": False,
    "registry_mutation_executed": False,
    "trial_status_mutation_executed": False,
    "data_model_artifact_mutation_executed": False,
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


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], str | None]:
    if not path.is_file():
        return [], f"missing CSV input: {path.as_posix()}"
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)], None
    except Exception as exc:
        return [], f"unreadable CSV {path.as_posix()}: {exc}"


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
            continue
        payload, error = read_json_object(resolved)
        if error or payload is None:
            failures.append(error or f"missing JSON input: {rel(resolved, repo_root)}")
            payloads[name] = {}
        else:
            payloads[name] = payload
    for name, path in paths.items():
        resolved = resolve_path(repo_root, path)
        if not resolved.is_file():
            failures.append(f"missing input: {rel(resolved, repo_root)}")
    return payloads, failures


def evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    fields = {
        "recompute_summary": {
            "status": "status",
            "statistical_validity_ready": "statistical_validity_ready",
            "prediction_count": "prediction_count",
            "policy_trade_count": "policy_trade_count",
            "failure_count": "failure_count",
        },
        "recompute_decision": {
            "status": "status",
            "pbo_recompute_decision": "summary.pbo_recompute_decision",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "post_mutation_completeness": {
            "status": "status",
            "trial_ledger_search_path_complete": "summary.trial_ledger_search_path_complete",
            "family_metadata_row_count": "summary.family_metadata_row_count",
        },
        "alpha_matrix": {
            "status": "status",
            "verdict": "verdict",
            "alpha_evidence_ready": "alpha_evidence_ready",
        },
        "alpha_closeout": {
            "status": "status",
            "verdict": "verdict",
            "future_modeling_allowed": "future_modeling_allowed",
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


def _required_checks(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    checks = summary.get("required_checks")
    return checks if isinstance(checks, Mapping) else {}


def _row_by_key(rows: Sequence[Mapping[str, str]], key: str, value: str) -> Mapping[str, str]:
    for row in rows:
        if row.get(key) == value:
            return row
    return {}


def build_checks(
    *,
    repo_root: Path,
    reports_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    paths: Mapping[str, Path],
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

    recompute = payloads.get("recompute_summary", {})
    required = _required_checks(recompute)
    pbo = required.get("pbo") if isinstance(required.get("pbo"), Mapping) else {}
    dsr = required.get("deflated_sharpe") if isinstance(required.get("deflated_sharpe"), Mapping) else {}
    multiple = (
        required.get("multiple_testing_adjustment")
        if isinstance(required.get("multiple_testing_adjustment"), Mapping)
        else {}
    )
    psr = (
        required.get("probabilistic_sharpe")
        if isinstance(required.get("probabilistic_sharpe"), Mapping)
        else {}
    )
    bootstrap = (
        required.get("bootstrap_confidence_intervals")
        if isinstance(required.get("bootstrap_confidence_intervals"), Mapping)
        else {}
    )
    stability = (
        required.get("parameter_stability")
        if isinstance(required.get("parameter_stability"), Mapping)
        else {}
    )
    regime = (
        required.get("regime_breakdowns")
        if isinstance(required.get("regime_breakdowns"), Mapping)
        else {}
    )
    trial_search = (
        recompute.get("trial_search_evidence")
        if isinstance(recompute.get("trial_search_evidence"), Mapping)
        else {}
    )
    recompute_ready = (
        recompute.get("status") == "FAIL"
        and recompute.get("statistical_validity_ready") is False
        and recompute.get("prediction_count") == 9_172_416
        and recompute.get("policy_trade_count") == 1_347
        and recompute.get("failure_count") == 5
        and pbo.get("status") == "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"
        and pbo.get("trial_count") == 22
        and pbo.get("search_family_count") == 10
        and pbo.get("multiple_testing_family_count") == 2
        and dsr.get("status") == "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
        and dsr.get("trial_count") == 22
        and dsr.get("observed_sharpe_like") == -4.56884658431966
        and multiple.get("status") == "FAIL_BONFERRONI_ADJUSTED_PSR"
        and multiple.get("trial_count") == 22
        and multiple.get("raw_p_value") == 1.0
        and multiple.get("bonferroni_adjusted_p_value") == 1.0
        and psr.get("status") == "FAIL"
        and regime.get("status") == "FAIL"
        and bootstrap.get("status") == "PASS"
        and bootstrap.get("sample_count") == 500
        and stability.get("status") == "PASS"
        and trial_search.get("trial_count") == 22
        and trial_search.get("search_family_count") == 10
        and trial_search.get("multiple_testing_family_count") == 2
    )
    check(
        checks,
        failures,
        name="recompute_summary_preserves_expected_fail_closed_statuses",
        passed=recompute_ready,
        failure="recompute summary did not preserve expected post-recompute fail-closed statuses/counts",
        evidence=[rel(resolve_path(repo_root, paths["recompute_summary"]), repo_root)],
        details={
            "status": recompute.get("status"),
            "prediction_count": recompute.get("prediction_count"),
            "policy_trade_count": recompute.get("policy_trade_count"),
            "failure_count": recompute.get("failure_count"),
            "pbo": dict(pbo),
            "deflated_sharpe": dict(dsr),
            "multiple_testing_adjustment": dict(multiple),
            "probabilistic_sharpe": dict(psr),
            "regime_breakdowns": dict(regime),
        },
    )

    bootstrap_rows, bootstrap_error = read_csv_rows(resolve_path(repo_root, paths["recompute_bootstrap"]))
    net_row = _row_by_key(bootstrap_rows, "metric", "net_return_dollars")
    bootstrap_csv_ready = bootstrap_error is None and net_row.get("sample_count") == "500"
    check(
        checks,
        failures,
        name="bootstrap_csv_preserved",
        passed=bootstrap_csv_ready,
        failure=bootstrap_error or "bootstrap CSV missing net_return_dollars sample_count=500",
        evidence=[rel(resolve_path(repo_root, paths["recompute_bootstrap"]), repo_root)],
        details={"row_count": len(bootstrap_rows), "net_return_dollars": dict(net_row)},
    )

    stability_rows, stability_error = read_csv_rows(resolve_path(repo_root, paths["recompute_stability"]))
    stability_scopes = sorted({row.get("scope", "") for row in stability_rows if row.get("scope")})
    stability_csv_ready = stability_error is None and bool(stability_rows) and "fold" in stability_scopes
    check(
        checks,
        failures,
        name="stability_csv_preserved",
        passed=stability_csv_ready,
        failure=stability_error or "stability CSV missing fold evidence",
        evidence=[rel(resolve_path(repo_root, paths["recompute_stability"]), repo_root)],
        details={"row_count": len(stability_rows), "scopes": stability_scopes},
    )

    adversarial_rows, adversarial_error = read_csv_rows(resolve_path(repo_root, paths["recompute_adversarial"]))
    by_test = {row.get("test_id"): row for row in adversarial_rows}
    adversarial_ready = (
        adversarial_error is None
        and by_test.get("two_x_cost_stress", {}).get("status") == "FAIL"
        and by_test.get("random_entry_distribution", {}).get("status") == "MISSING_WITH_REASON"
        and by_test.get("label_shuffle", {}).get("status") == "MISSING_WITH_REASON"
    )
    check(
        checks,
        failures,
        name="adversarial_csv_preserves_blockers",
        passed=adversarial_ready,
        failure=adversarial_error
        or "adversarial CSV did not preserve cost stress/random-entry/label-shuffle blockers",
        evidence=[rel(resolve_path(repo_root, paths["recompute_adversarial"]), repo_root)],
        details={"rows": by_test},
    )

    decision = payloads.get("recompute_decision", {})
    decision_summary = (
        decision.get("summary") if isinstance(decision.get("summary"), Mapping) else {}
    )
    decision_ready = (
        decision.get("status")
        == "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_RECOMPUTE_DECISION_REPORT_ONLY"
        and decision_summary.get("pbo_recompute_decision")
        == "READY_FOR_SEPARATE_BOUNDED_STATISTICAL_RECOMPUTE"
        and decision_summary.get("deflated_sharpe_recompute_decision")
        == "READY_FOR_SEPARATE_BOUNDED_STATISTICAL_RECOMPUTE"
        and decision_summary.get("multiple_testing_recompute_decision")
        == "READY_FOR_SEPARATE_BOUNDED_STATISTICAL_RECOMPUTE"
        and decision_summary.get("statistical_validity_ready") is False
        and decision_summary.get("model_trust_ready") is False
        and decision_summary.get("promotion_allowed") is False
    )
    check(
        checks,
        failures,
        name="upstream_recompute_decision_pass_preserved",
        passed=decision_ready,
        failure="upstream recompute decision is not PASS/blocked as expected",
        evidence=[rel(resolve_path(repo_root, paths["recompute_decision"]), repo_root)],
        details={"status": decision.get("status"), "summary": dict(decision_summary)},
    )

    post = payloads.get("post_mutation_completeness", {})
    post_summary = post.get("summary") if isinstance(post.get("summary"), Mapping) else {}
    post_ready = (
        post.get("status")
        == "PASS_MASTER_AUDIT_POST_MUTATION_TRIAL_SEARCH_COMPLETENESS_RECONCILIATION_REPORT_ONLY"
        and post_summary.get("trial_ledger_search_path_complete") is True
        and post_summary.get("family_metadata_row_count") == 22
        and post_summary.get("search_family_count") == 10
        and post_summary.get("multiple_testing_family_count") == 2
        and post_summary.get("statistical_validity_ready") is False
        and post_summary.get("model_trust_ready") is False
        and post_summary.get("promotion_allowed") is False
    )
    check(
        checks,
        failures,
        name="post_mutation_trial_search_completeness_pass_preserved",
        passed=post_ready,
        failure="post-mutation trial/search completeness input is not PASS/blocked as expected",
        evidence=[rel(resolve_path(repo_root, paths["post_mutation_completeness"]), repo_root)],
        details={"status": post.get("status"), "summary": dict(post_summary)},
    )

    closeout = payloads.get("alpha_closeout", {})
    matrix = payloads.get("alpha_matrix", {})
    alpha_ready = (
        matrix.get("alpha_evidence_ready") is False
        and closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and closeout.get("future_modeling_allowed") is False
        and closeout.get("promotion_allowed") is False
    )
    check(
        checks,
        failures,
        name="alpha_closeout_remains_blocked",
        passed=alpha_ready,
        failure="alpha matrix/closeout no longer preserves no-alpha/no-promotion posture",
        evidence=[
            rel(resolve_path(repo_root, paths["alpha_matrix"]), repo_root),
            rel(resolve_path(repo_root, paths["alpha_closeout"]), repo_root),
        ],
        details={
            "alpha_evidence_ready": matrix.get("alpha_evidence_ready"),
            "closeout_verdict": closeout.get("verdict"),
            "future_modeling_allowed": closeout.get("future_modeling_allowed"),
            "promotion_allowed": closeout.get("promotion_allowed"),
        },
    )

    run_status = payloads.get("run_status", {})
    run_summary = (
        run_status.get("summary") if isinstance(run_status.get("summary"), Mapping) else {}
    )
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
        passed=run_flags_clear and all(value is False for value in NON_APPROVAL.values()),
        failure="run-status or report-local non-approval flags show forbidden execution",
        evidence=[rel(resolve_path(repo_root, paths["run_status"]), repo_root)],
        details={"run_summary": dict(run_summary), "non_approval": dict(NON_APPROVAL)},
    )

    derived = {
        "pbo_status": pbo.get("status"),
        "deflated_sharpe_status": dsr.get("status"),
        "multiple_testing_status": multiple.get("status"),
        "probabilistic_sharpe_status": psr.get("status"),
        "bootstrap_status": bootstrap.get("status"),
        "parameter_stability_status": stability.get("status"),
        "regime_breakdowns_status": regime.get("status"),
        "trial_count": pbo.get("trial_count"),
        "search_family_count": pbo.get("search_family_count"),
        "multiple_testing_family_count": pbo.get("multiple_testing_family_count"),
        "prediction_count": recompute.get("prediction_count"),
        "policy_trade_count": recompute.get("policy_trade_count"),
        "failure_count": recompute.get("failure_count"),
        "stability_scopes": stability_scopes,
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity", "UNKNOWN"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "severity": "INFO",
            "finding_id": "missing_trial_log_blockers_replaced",
            "finding": (
                "PBO, Deflated Sharpe, and multiple-testing moved from missing-trial-log "
                "blockers to bounded recompute failure statuses."
            ),
            "evidence_paths": [RECOMPUTE_SUMMARY.as_posix()],
        },
        {
            "severity": "BLOCKER",
            "finding_id": "statistical_validity_still_fail",
            "finding": (
                "Statistical validity remains FAIL; PSR, regime, PBO, Deflated Sharpe, "
                "multiple-testing, and cost-stress evidence still block acceptance."
            ),
            "evidence_paths": [RECOMPUTE_SUMMARY.as_posix(), RECOMPUTE_ADVERSARIAL.as_posix()],
        },
        {
            "severity": "BLOCKER",
            "finding_id": "model_trust_and_promotion_remain_blocked",
            "finding": "Model trust, promotion, paper/live, and production are not approved.",
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
    input_evidence = evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    checks, check_failures, derived = build_checks(
        repo_root=repo_root,
        reports_root=reports_root,
        payloads=payloads,
        paths=paths,
    )
    failures = input_failures + check_failures
    status = PASS_STATUS if not failures else FAIL_STATUS
    findings = build_findings(derived)
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_post_recompute_statistical_validity_reconciliation_report_only",
            "target_gap_area": "statistical_validity",
            "target_checks": ["pbo", "deflated_sharpe", "multiple_testing_adjustment"],
            "reports_root": rel(reports_root, repo_root),
            "evidence_mode": "existing_local_json_csv_md_repo_evidence_only",
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
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "missing_trial_log_blockers_replaced": status == PASS_STATUS,
            "pbo_status": derived.get("pbo_status"),
            "deflated_sharpe_status": derived.get("deflated_sharpe_status"),
            "multiple_testing_status": derived.get("multiple_testing_status"),
            "probabilistic_sharpe_status": derived.get("probabilistic_sharpe_status"),
            "bootstrap_status": derived.get("bootstrap_status"),
            "parameter_stability_status": derived.get("parameter_stability_status"),
            "regime_breakdowns_status": derived.get("regime_breakdowns_status"),
            "trial_count": derived.get("trial_count"),
            "search_family_count": derived.get("search_family_count"),
            "multiple_testing_family_count": derived.get("multiple_testing_family_count"),
            "prediction_count": derived.get("prediction_count"),
            "policy_trade_count": derived.get("policy_trade_count"),
            "recompute_failure_count": derived.get("failure_count"),
            "statistical_validity_ready": False,
            "master_audit_statistical_validity_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
            "finding_counts": finding_counts(findings),
            **dict(NON_APPROVAL),
        },
        "input_evidence": input_evidence,
        "checks": checks,
        "findings": findings,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "recompute summary is FAIL with exact prediction/trade/failure counts",
                "PBO, Deflated Sharpe, and multiple-testing use bounded recompute failure statuses",
                "PSR and regime remain FAIL; bootstrap and parameter stability remain diagnostic PASS",
                "adversarial blockers remain preserved",
                "upstream recompute-decision and post-mutation completeness reports are PASS",
                "alpha closeout and all non-approval flags remain blocked/false",
            ],
            "fail": [
                "missing/unreadable required input",
                "any target statistical check is silently upgraded to PASS",
                "statistical validity, model trust, promotion, paper/live, or production readiness is upgraded",
                "any forbidden execution flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan the next smallest statistical-validity remediation, likely regime/adversarial "
            "null evidence disposition, using existing evidence only."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Post-Recompute Statistical-Validity Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Missing-trial-log blockers replaced: `{summary['missing_trial_log_blockers_replaced']}`",
        f"- PBO status: `{summary['pbo_status']}`",
        f"- Deflated Sharpe status: `{summary['deflated_sharpe_status']}`",
        f"- Multiple-testing status: `{summary['multiple_testing_status']}`",
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
    lines.extend(["", "## Findings", ""])
    for item in report["findings"]:
        lines.append(
            "- `{severity}` `{finding_id}`: {finding}".format(
                severity=item["severity"],
                finding_id=item["finding_id"],
                finding=item["finding"],
            )
        )
    lines.extend(["", "## Evidence Inputs", ""])
    for item in report.get("input_evidence", []):
        lines.append(
            "- `{path}` exists=`{exists}` state=`{state}` git=`{git}` sha256=`{sha}`".format(
                path=item.get("path"),
                exists=item.get("exists"),
                state=item.get("state"),
                git=item.get("git_status"),
                sha=item.get("sha256"),
            )
        )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in report.get("failures", [])] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This reconciliation did not mutate ledgers, registry, trial statuses, reports outside its own output pair, data/model artifacts, WFA/modeling, predictions, Phase 8 outputs, provider state, promotion state, staging, commits, or pushes.",
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
        f"pbo_status={report['summary']['pbo_status']} "
        f"statistical_validity_ready={report['summary']['statistical_validity_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
