#!/usr/bin/env python3
"""Build a report-only statistical-validity recompute decision."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_statistical_validity_recompute_decision"
PASS_STATUS = "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_RECOMPUTE_DECISION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_STATISTICAL_VALIDITY_RECOMPUTE_DECISION_REPORT_ONLY"
READY_DECISION = "READY_FOR_SEPARATE_BOUNDED_STATISTICAL_RECOMPUTE"
BLOCKED_DECISION = "BLOCKED_RECOMPUTE_DECISION_INPUTS_INCOMPLETE"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_statistical_validity_recompute_decision_20260710"
)
REPORT_JSON = "master_audit_statistical_validity_recompute_decision.json"
REPORT_MD = "master_audit_statistical_validity_recompute_decision.md"

STAT_ROOT = Path("reports/statistical_validity/tier1_core_phase6_full_predictions_20260706")
POST_MUTATION_COMPLETENESS = Path(
    "reports/master_audit/master_audit_post_mutation_trial_search_completeness_reconciliation_20260710/"
    "master_audit_post_mutation_trial_search_completeness_reconciliation.json"
)
STATISTICAL_SUMMARY = STAT_ROOT / "statistical_validity_summary.json"
BOOTSTRAP_CI = STAT_ROOT / "bootstrap_confidence_intervals.csv"
STABILITY_MATRIX = STAT_ROOT / "stability_matrix.csv"
ADVERSARIAL_TESTS = STAT_ROOT / "adversarial_tests.csv"
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
    "post_mutation_completeness": POST_MUTATION_COMPLETENESS,
    "statistical_summary": STATISTICAL_SUMMARY,
    "bootstrap_confidence_intervals": BOOTSTRAP_CI,
    "stability_matrix": STABILITY_MATRIX,
    "adversarial_tests": ADVERSARIAL_TESTS,
    "alpha_matrix": ALPHA_MATRIX,
    "alpha_closeout": ALPHA_CLOSEOUT,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

FUTURE_COMMAND_FAMILY_NOT_APPROVED = (
    "python -m scripts.phase9_research.statistical_validity "
    "--predictions <existing predictions artifact> "
    "--output-root <new bounded output root> "
    "--trial-search-ledger "
    "reports/master_audit/master_audit_post_mutation_trial_search_completeness_reconciliation_20260710/"
    "master_audit_post_mutation_trial_search_completeness_reconciliation.json"
)

NON_APPROVAL = {
    "data_model_commands_executed": False,
    "wfa_modeling_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "statistical_recompute_executed": False,
    "generated_report_execution_executed": False,
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
    for name in ("adversarial_audit",):
        resolved = resolve_path(repo_root, paths[name])
        if not resolved.is_file():
            failures.append(f"missing input: {rel(resolved, repo_root)}")
    return payloads, failures


def input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    fields = {
        "post_mutation_completeness": {
            "status": "status",
            "trial_ledger_search_path_complete": "summary.trial_ledger_search_path_complete",
            "family_metadata_row_count": "summary.family_metadata_row_count",
            "search_family_count": "summary.search_family_count",
            "multiple_testing_family_count": "summary.multiple_testing_family_count",
            "statistical_recompute_executed": "summary.statistical_recompute_executed",
        },
        "statistical_summary": {
            "status": "status",
            "statistical_validity_ready": "statistical_validity_ready",
            "prediction_count": "prediction_count",
            "policy_trade_count": "policy_trade_count",
            "failure_count": "failure_count",
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
            "promotion_or_freeze_or_holdout_executed": "summary.promotion_or_freeze_or_holdout_executed",
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


def _required_checks(statistical_summary: Mapping[str, Any]) -> Mapping[str, Any]:
    checks = statistical_summary.get("required_checks")
    return checks if isinstance(checks, Mapping) else {}


def _find_csv_row(rows: Sequence[Mapping[str, str]], key: str, value: str) -> Mapping[str, str]:
    for row in rows:
        if row.get(key) == value:
            return row
    return {}


def _negative_float(value: Any) -> bool:
    try:
        return float(value) < 0.0
    except (TypeError, ValueError):
        return False


def _bucket(payload: Mapping[str, Any], bucket_id: str) -> Mapping[str, Any]:
    rows = payload.get("buckets")
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("bucket_id") == bucket_id:
            return row
    return {}


def _closeout_bucket(payload: Mapping[str, Any], bucket_id: str) -> Mapping[str, Any]:
    rows = payload.get("bucket_dispositions")
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("bucket_id") == bucket_id:
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

    post = payloads.get("post_mutation_completeness", {})
    post_summary = post.get("summary") if isinstance(post.get("summary"), Mapping) else {}
    post_ready = (
        post.get("status")
        == "PASS_MASTER_AUDIT_POST_MUTATION_TRIAL_SEARCH_COMPLETENESS_RECONCILIATION_REPORT_ONLY"
        and post_summary.get("trial_ledger_search_path_complete") is True
        and post_summary.get("pbo_applicability_ready") is True
        and post_summary.get("deflated_sharpe_applicability_ready") is True
        and post_summary.get("multiple_testing_applicability_ready") is True
        and post_summary.get("family_metadata_row_count") == 22
        and post_summary.get("search_family_count") == 10
        and post_summary.get("multiple_testing_family_count") == 2
        and post_summary.get("statistical_recompute_executed") is False
        and post_summary.get("statistical_validity_ready") is False
        and post_summary.get("model_trust_ready") is False
        and post_summary.get("promotion_allowed") is False
    )
    check(
        checks,
        failures,
        name="post_mutation_trial_search_inputs_complete_no_recompute",
        passed=post_ready,
        failure="post-mutation trial/search completeness is not ready for bounded recompute decision",
        evidence=[rel(resolve_path(repo_root, paths["post_mutation_completeness"]), repo_root)],
        details={
            "status": post.get("status"),
            "trial_ledger_search_path_complete": post_summary.get(
                "trial_ledger_search_path_complete"
            ),
            "family_metadata_row_count": post_summary.get("family_metadata_row_count"),
            "search_family_count": post_summary.get("search_family_count"),
            "multiple_testing_family_count": post_summary.get("multiple_testing_family_count"),
            "statistical_recompute_executed": post_summary.get("statistical_recompute_executed"),
        },
    )

    statistical = payloads.get("statistical_summary", {})
    required = _required_checks(statistical)
    pbo = required.get("pbo") if isinstance(required.get("pbo"), Mapping) else {}
    dsr = (
        required.get("deflated_sharpe")
        if isinstance(required.get("deflated_sharpe"), Mapping)
        else {}
    )
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
    current_stats_blocked = (
        statistical.get("status") == "FAIL"
        and statistical.get("statistical_validity_ready") is False
        and statistical.get("prediction_count") == 9_172_416
        and statistical.get("policy_trade_count") == 1_347
        and statistical.get("failure_count") == 5
        and pbo.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and dsr.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and multiple.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and psr.get("status") == "FAIL"
        and bootstrap.get("status") == "PASS"
        and bootstrap.get("sample_count") == 500
        and stability.get("status") == "PASS"
        and regime.get("status") == "FAIL"
    )
    check(
        checks,
        failures,
        name="current_statistical_summary_blockers_preserved",
        passed=current_stats_blocked,
        failure="current statistical summary was upgraded or expected blocker/count evidence changed",
        evidence=[rel(resolve_path(repo_root, paths["statistical_summary"]), repo_root)],
        details={
            "status": statistical.get("status"),
            "prediction_count": statistical.get("prediction_count"),
            "policy_trade_count": statistical.get("policy_trade_count"),
            "failure_count": statistical.get("failure_count"),
            "pbo_status": pbo.get("status"),
            "deflated_sharpe_status": dsr.get("status"),
            "multiple_testing_status": multiple.get("status"),
            "probabilistic_sharpe_status": psr.get("status"),
            "regime_breakdowns_status": regime.get("status"),
        },
    )

    bootstrap_rows, bootstrap_error = read_csv_rows(resolve_path(repo_root, paths["bootstrap_confidence_intervals"]))
    net_row = _find_csv_row(bootstrap_rows, "metric", "net_return_dollars")
    bootstrap_csv_ready = (
        bootstrap_error is None
        and net_row.get("sample_count") == "500"
        and all(_negative_float(net_row.get(field)) for field in ("ci_low", "ci_mid", "ci_high"))
    )
    check(
        checks,
        failures,
        name="bootstrap_csv_preserves_negative_net_return_ci",
        passed=bootstrap_csv_ready,
        failure=bootstrap_error
        or "bootstrap CI CSV missing net_return_dollars sample_count=500 with negative CI bounds",
        evidence=[rel(resolve_path(repo_root, paths["bootstrap_confidence_intervals"]), repo_root)],
        details={"net_return_dollars": dict(net_row), "row_count": len(bootstrap_rows)},
    )

    stability_rows, stability_error = read_csv_rows(resolve_path(repo_root, paths["stability_matrix"]))
    stability_scopes = sorted({row.get("scope", "") for row in stability_rows if row.get("scope")})
    stability_csv_ready = (
        stability_error is None
        and bool(stability_rows)
        and {"scope", "net_return_dollars"}.issubset(set(stability_rows[0]))
    )
    check(
        checks,
        failures,
        name="stability_csv_supports_parameter_stability_diagnostic_pass",
        passed=stability_csv_ready,
        failure=stability_error or "stability matrix CSV missing required diagnostic rows/columns",
        evidence=[rel(resolve_path(repo_root, paths["stability_matrix"]), repo_root)],
        details={"row_count": len(stability_rows), "scopes": stability_scopes},
    )

    adversarial_rows, adversarial_error = read_csv_rows(resolve_path(repo_root, paths["adversarial_tests"]))
    adversarial_by_id = {row.get("test_id"): row for row in adversarial_rows}
    adversarial_ready = (
        adversarial_error is None
        and adversarial_by_id.get("two_x_cost_stress", {}).get("status") == "FAIL"
        and adversarial_by_id.get("random_entry_distribution", {}).get("status")
        == "MISSING_WITH_REASON"
        and adversarial_by_id.get("label_shuffle", {}).get("status") == "MISSING_WITH_REASON"
    )
    check(
        checks,
        failures,
        name="adversarial_csv_blockers_preserved",
        passed=adversarial_ready,
        failure=adversarial_error
        or "adversarial CSV did not preserve cost stress failure and missing shuffle/random-entry caveats",
        evidence=[rel(resolve_path(repo_root, paths["adversarial_tests"]), repo_root)],
        details={"rows": adversarial_by_id},
    )

    matrix = payloads.get("alpha_matrix", {})
    closeout = payloads.get("alpha_closeout", {})
    alpha_ready = (
        matrix.get("alpha_evidence_ready") is False
        and closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and closeout.get("future_modeling_allowed") is False
        and closeout.get("promotion_allowed") is False
        and _bucket(matrix, "statistical_pbo").get("status") in {"MISSING_EVIDENCE", "FAIL"}
        and _bucket(matrix, "statistical_deflated_sharpe").get("status")
        in {"MISSING_EVIDENCE", "FAIL"}
        and _bucket(matrix, "statistical_multiple_testing").get("status")
        in {"MISSING_EVIDENCE", "FAIL"}
        and _closeout_bucket(closeout, "statistical_pbo").get("closeout_classification")
        == "missing_required_evidence"
        and _closeout_bucket(closeout, "statistical_deflated_sharpe").get(
            "closeout_classification"
        )
        == "missing_required_evidence"
        and _closeout_bucket(closeout, "statistical_multiple_testing").get(
            "closeout_classification"
        )
        == "missing_required_evidence"
    )
    check(
        checks,
        failures,
        name="alpha_closeout_remains_closed_no_alpha_no_promotion",
        passed=alpha_ready,
        failure="alpha matrix/closeout did not preserve no-alpha, no-modeling, no-promotion posture",
        evidence=[
            rel(resolve_path(repo_root, paths["alpha_matrix"]), repo_root),
            rel(resolve_path(repo_root, paths["alpha_closeout"]), repo_root),
        ],
        details={
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
        name="run_status_forbidden_actions_remain_false",
        passed=run_flags_clear and all(value is False for value in NON_APPROVAL.values()),
        failure="run-status or report-local non-approval flags show forbidden execution",
        evidence=[rel(resolve_path(repo_root, paths["run_status"]), repo_root)],
        details={"run_summary": dict(run_summary), "non_approval": dict(NON_APPROVAL)},
    )

    decision = READY_DECISION if not failures else BLOCKED_DECISION
    derived = {
        "decision": decision,
        "pbo_status": pbo.get("status"),
        "deflated_sharpe_status": dsr.get("status"),
        "multiple_testing_status": multiple.get("status"),
        "probabilistic_sharpe_status": psr.get("status"),
        "regime_breakdowns_status": regime.get("status"),
        "bootstrap_ci_sample_count": bootstrap.get("sample_count"),
        "bootstrap_net_return_dollars_ci": dict(net_row),
        "stability_matrix_row_count": len(stability_rows),
        "stability_matrix_scopes": stability_scopes,
        "adversarial_statuses": {
            key: adversarial_by_id.get(key, {}).get("status")
            for key in ("two_x_cost_stress", "random_entry_distribution", "label_shuffle")
        },
        "trial_count_for_recompute": post_summary.get("family_metadata_row_count"),
        "search_family_count": post_summary.get("search_family_count"),
        "multiple_testing_family_count": post_summary.get("multiple_testing_family_count"),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity", "UNKNOWN"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings = [
        {
            "severity": "INFO",
            "finding_id": "trial_search_inputs_complete_for_recompute_decision",
            "finding": (
                "Canonical trial/search family counts are complete enough to plan a "
                "separately approved statistical recompute."
            ),
            "evidence_paths": [POST_MUTATION_COMPLETENESS.as_posix()],
        },
        {
            "severity": "BLOCKER",
            "finding_id": "statistical_recompute_not_executed",
            "finding": (
                "This report does not recompute PBO, Deflated Sharpe, or multiple-testing "
                "statistics; current statistical validity remains blocked."
            ),
            "evidence_paths": [STATISTICAL_SUMMARY.as_posix()],
        },
        {
            "severity": "BLOCKER",
            "finding_id": "current_line_remains_no_alpha",
            "finding": (
                "PSR, regime breakdowns, and adversarial stress blockers remain; model "
                "trust and promotion stay false."
            ),
            "evidence_paths": [ALPHA_CLOSEOUT.as_posix(), ADVERSARIAL_TESTS.as_posix()],
        },
    ]
    if derived.get("decision") == BLOCKED_DECISION:
        findings.append(
            {
                "severity": "BLOCKER",
                "finding_id": "recompute_decision_inputs_incomplete",
                "finding": "One or more required recompute-decision inputs failed validation.",
                "evidence_paths": [POST_MUTATION_COMPLETENESS.as_posix()],
            }
        )
    return findings


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
    evidence = input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    checks, check_failures, derived = build_checks(
        repo_root=repo_root,
        reports_root=reports_root,
        payloads=payloads,
        paths=paths,
    )
    failures = input_failures + check_failures
    status = PASS_STATUS if not failures else FAIL_STATUS
    decision = READY_DECISION if status == PASS_STATUS else BLOCKED_DECISION
    findings = build_findings({**derived, "decision": decision})
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_statistical_validity_recompute_decision_report_only",
            "target_gap_area": "statistical_validity",
            "target_checks": [
                "pbo",
                "deflated_sharpe",
                "multiple_testing_adjustment",
            ],
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
            "pbo_recompute_decision": decision,
            "deflated_sharpe_recompute_decision": decision,
            "multiple_testing_recompute_decision": decision,
            "trial_count_for_recompute": derived.get("trial_count_for_recompute"),
            "search_family_count": derived.get("search_family_count"),
            "multiple_testing_family_count": derived.get("multiple_testing_family_count"),
            "bootstrap_ci_sample_count": derived.get("bootstrap_ci_sample_count"),
            "bootstrap_net_return_dollars_ci": derived.get("bootstrap_net_return_dollars_ci"),
            "stability_matrix_row_count": derived.get("stability_matrix_row_count"),
            "stability_matrix_scopes": derived.get("stability_matrix_scopes"),
            "adversarial_statuses": derived.get("adversarial_statuses"),
            "pbo_current_status": derived.get("pbo_status"),
            "deflated_sharpe_current_status": derived.get("deflated_sharpe_status"),
            "multiple_testing_current_status": derived.get("multiple_testing_status"),
            "probabilistic_sharpe_status": derived.get("probabilistic_sharpe_status"),
            "regime_breakdowns_status": derived.get("regime_breakdowns_status"),
            "statistical_recompute_executed": False,
            "statistical_validity_ready": False,
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
        "input_evidence": evidence,
        "checks": checks,
        "findings": findings,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "future_command_family_not_approved": FUTURE_COMMAND_FAMILY_NOT_APPROVED,
        "pass_fail_criteria": {
            "pass": [
                "post-mutation trial/search completeness is PASS with 22 family rows, 10 search families, and 2 multiple-testing families",
                "current statistical summary remains FAIL with exact prediction/trade/failure counts",
                "bootstrap CI remains PASS with 500 samples and negative net_return_dollars CI",
                "parameter stability remains PASS with stability CSV support",
                "adversarial cost stress, shuffle, and random-entry caveats remain blocked/preserved",
                "PSR and regime breakdowns remain FAIL",
                "alpha closeout remains closed/no-alpha with no modeling or promotion approval",
                "no statistical recompute or forbidden execution is performed",
            ],
            "fail": [
                "missing/unreadable required input",
                "trial/search input completeness regresses",
                "current statistical blockers are silently upgraded",
                "any model trust, promotion, paper/live, production, or forbidden execution flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan a separately approved bounded statistical-validity recompute execution "
            "for PBO, Deflated Sharpe, and multiple-testing only."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Statistical-Validity Recompute Decision",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- PBO recompute decision: `{summary['pbo_recompute_decision']}`",
        f"- Deflated Sharpe recompute decision: `{summary['deflated_sharpe_recompute_decision']}`",
        f"- Multiple-testing recompute decision: `{summary['multiple_testing_recompute_decision']}`",
        f"- Trial count for recompute: `{summary['trial_count_for_recompute']}`",
        f"- Search families: `{summary['search_family_count']}`",
        f"- Multiple-testing families: `{summary['multiple_testing_family_count']}`",
        f"- Statistical recompute executed: `{summary['statistical_recompute_executed']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Future Command Family Not Approved",
        "",
        f"`{report['future_command_family_not_approved']}`",
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
    for item in report.get("findings", []):
        lines.append(
            "- `{severity}` `{finding_id}`: {finding}".format(
                severity=item.get("severity"),
                finding_id=item.get("finding_id"),
                finding=item.get("finding"),
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
            "- This decision did not run statistical recompute, generated report execution, data/model commands, WFA/modeling, predictions, Phase 8 refresh, provider/network calls, promotion, artifact freeze, final holdout, paper/live, cleanup, staging, commit, or push.",
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
        f"pbo_recompute_decision={report['summary']['pbo_recompute_decision']} "
        f"statistical_recompute_executed={report['summary']['statistical_recompute_executed']} "
        f"statistical_validity_ready={report['summary']['statistical_validity_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
