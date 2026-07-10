#!/usr/bin/env python3
"""Build a report-only regime/adversarial statistical-validity disposition."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_statistical_validity_regime_adversarial_disposition"
PASS_STATUS = (
    "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_REGIME_ADVERSARIAL_DISPOSITION_REPORT_ONLY"
)
FAIL_STATUS = (
    "FAIL_MASTER_AUDIT_STATISTICAL_VALIDITY_REGIME_ADVERSARIAL_DISPOSITION_REPORT_ONLY"
)

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_statistical_validity_regime_adversarial_disposition_20260710"
)
REPORT_JSON = "master_audit_statistical_validity_regime_adversarial_disposition.json"
REPORT_MD = "master_audit_statistical_validity_regime_adversarial_disposition.md"

RECOMPUTE_ROOT = Path(
    "reports/statistical_validity/tier1_core_phase6_full_predictions_20260706_trial_search_recompute_20260710"
)
POST_RECOMPUTE_RECONCILIATION = Path(
    "reports/master_audit/master_audit_post_recompute_statistical_validity_reconciliation_20260710/"
    "master_audit_post_recompute_statistical_validity_reconciliation.json"
)
RECOMPUTE_SUMMARY = RECOMPUTE_ROOT / "statistical_validity_summary.json"
RECOMPUTE_ADVERSARIAL = RECOMPUTE_ROOT / "adversarial_tests.csv"
RECOMPUTE_STABILITY = RECOMPUTE_ROOT / "stability_matrix.csv"
RECOMPUTE_MD = RECOMPUTE_ROOT / "statistical_validity.md"
FAILURE_ANALYSIS = Path(
    "reports/failure_analysis/tier1_core_phase6_full_predictions_20260706/"
    "failure_analysis_summary.json"
)
PHASE8_DECISION = Path(
    "reports/phase8/tier1_core_phase6_full_predictions_20260706/alpha_promotion_decision.json"
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
    "post_recompute_reconciliation": POST_RECOMPUTE_RECONCILIATION,
    "recompute_summary": RECOMPUTE_SUMMARY,
    "recompute_adversarial": RECOMPUTE_ADVERSARIAL,
    "recompute_stability": RECOMPUTE_STABILITY,
    "recompute_markdown": RECOMPUTE_MD,
    "failure_analysis": FAILURE_ANALYSIS,
    "phase8_decision": PHASE8_DECISION,
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

DISPOSITIONS = {
    "random_entry_null_disposition": (
        "TERMINAL_FAIL_CANDIDATE_DOES_NOT_BEAT_RANDOM_MEDIAN"
    ),
    "two_x_cost_stress_disposition": "TERMINAL_FAIL_EDGE_DOES_NOT_SURVIVE_2X_COST",
    "label_shuffle_disposition": (
        "MISSING_REQUIRED_EVIDENCE_SEPARATE_BOUNDED_SHUFFLE_HARNESS_REQUIRED"
    ),
    "timing_shift_disposition": (
        "MISSING_REQUIRED_EVIDENCE_SEPARATE_BOUNDED_TIMING_SHIFT_HARNESS_REQUIRED"
    ),
    "regime_breakdowns_disposition": (
        "FAIL_MISSING_EXPLICIT_CAUSAL_REGIME_EVIDENCE_NOT_ACTIONABLE_FOR_CURRENT_LINE"
    ),
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


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
    for path in paths.values():
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
        "post_recompute_reconciliation": {
            "status": "status",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "missing_trial_log_blockers_replaced": "summary.missing_trial_log_blockers_replaced",
        },
        "recompute_summary": {
            "status": "status",
            "statistical_validity_ready": "statistical_validity_ready",
            "failure_count": "failure_count",
        },
        "failure_analysis": {
            "status": "status",
            "failure_analysis_ready": "failure_analysis_ready",
            "failure_count": "failure_count",
        },
        "phase8_decision": {
            "promoted": "promoted",
            "research_alpha_ready": "research_alpha_ready",
            "model_promotion_allowed": "model_promotion_allowed",
        },
        "alpha_matrix": {
            "status": "status",
            "verdict": "verdict",
            "alpha_evidence_ready": "alpha_evidence_ready",
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


def _required_checks(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    checks = summary.get("required_checks")
    return checks if isinstance(checks, Mapping) else {}


def _csv_by_key(rows: Sequence[Mapping[str, str]], key: str) -> dict[str | None, Mapping[str, str]]:
    return {row.get(key): row for row in rows}


def _find_by_id(rows: Sequence[Mapping[str, Any]], key: str, value: str) -> Mapping[str, Any]:
    for row in rows:
        if row.get(key) == value:
            return row
    return {}


def _closeout_bucket(closeout: Mapping[str, Any], bucket_id: str) -> Mapping[str, Any]:
    rows = closeout.get("bucket_dispositions")
    if not isinstance(rows, list):
        return {}
    return _find_by_id([row for row in rows if isinstance(row, Mapping)], "bucket_id", bucket_id)


def _phase8_cost_stress(phase8: Mapping[str, Any]) -> Mapping[str, Any]:
    gate = dotted_get(phase8, "promotion_metric_gate.cost_execution_stress_gate")
    return gate if isinstance(gate, Mapping) else {}


def _two_x_result(gate: Mapping[str, Any]) -> Mapping[str, Any]:
    rows = gate.get("stress_results")
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("cost_multiplier") == 2.0:
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

    upstream = payloads.get("post_recompute_reconciliation", {})
    upstream_summary = upstream.get("summary") if isinstance(upstream.get("summary"), Mapping) else {}
    upstream_ready = (
        upstream.get("status")
        == "PASS_MASTER_AUDIT_POST_RECOMPUTE_STATISTICAL_VALIDITY_RECONCILIATION_REPORT_ONLY"
        and upstream_summary.get("missing_trial_log_blockers_replaced") is True
        and upstream_summary.get("statistical_validity_ready") is False
        and upstream_summary.get("master_audit_statistical_validity_accepted") is False
        and upstream_summary.get("model_trust_ready") is False
        and upstream_summary.get("promotion_allowed") is False
    )
    check(
        checks,
        failures,
        name="upstream_post_recompute_pass_preserved",
        passed=upstream_ready,
        failure="upstream post-recompute reconciliation is not PASS/blocked as expected",
        evidence=[rel(resolve_path(repo_root, paths["post_recompute_reconciliation"]), repo_root)],
        details={"status": upstream.get("status"), "summary": dict(upstream_summary)},
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
    regime = (
        required.get("regime_breakdowns")
        if isinstance(required.get("regime_breakdowns"), Mapping)
        else {}
    )
    recompute_ready = (
        recompute.get("status") == "FAIL"
        and recompute.get("statistical_validity_ready") is False
        and recompute.get("failure_count") == 5
        and pbo.get("status") == "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"
        and dsr.get("status") == "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
        and multiple.get("status") == "FAIL_BONFERRONI_ADJUSTED_PSR"
        and psr.get("status") == "FAIL"
        and regime.get("status") == "FAIL"
    )
    check(
        checks,
        failures,
        name="recompute_statistical_failures_preserved",
        passed=recompute_ready,
        failure="recompute summary did not preserve expected blocked statistical statuses",
        evidence=[rel(resolve_path(repo_root, paths["recompute_summary"]), repo_root)],
        details={
            "status": recompute.get("status"),
            "failure_count": recompute.get("failure_count"),
            "pbo": dict(pbo),
            "deflated_sharpe": dict(dsr),
            "multiple_testing_adjustment": dict(multiple),
            "probabilistic_sharpe": dict(psr),
            "regime_breakdowns": dict(regime),
        },
    )

    adversarial_rows, adversarial_error = read_csv_rows(resolve_path(repo_root, paths["recompute_adversarial"]))
    adversarial = _csv_by_key(adversarial_rows, "test_id")
    adversarial_ready = (
        adversarial_error is None
        and adversarial.get("top_1pct_trade_removal", {}).get("status") == "PASS"
        and adversarial.get("two_x_cost_stress", {}).get("status") == "FAIL"
        and adversarial.get("two_x_cost_stress", {}).get("net_return_dollars")
        == "-92118.55500000017"
        and adversarial.get("random_entry_distribution", {}).get("status")
        == "MISSING_WITH_REASON"
        and adversarial.get("label_shuffle", {}).get("status") == "MISSING_WITH_REASON"
    )
    check(
        checks,
        failures,
        name="adversarial_csv_dispositions_preserved",
        passed=adversarial_ready,
        failure=adversarial_error
        or "adversarial CSV did not preserve top-trade/cost/random-entry/label-shuffle dispositions",
        evidence=[rel(resolve_path(repo_root, paths["recompute_adversarial"]), repo_root)],
        details={"rows": adversarial},
    )

    failure_analysis = payloads.get("failure_analysis", {})
    baselines = dotted_get(failure_analysis, "baseline_comparison_gate.baselines")
    baseline_rows = [row for row in baselines if isinstance(row, Mapping)] if isinstance(baselines, list) else []
    random_entry = _find_by_id(baseline_rows, "baseline_id", "random_entry")
    random_entry_ready = (
        failure_analysis.get("status") == "PASS"
        and random_entry.get("status") == "PASS"
        and random_entry.get("candidate_beats_random_median") is False
        and random_entry.get("simulation_count") == 25.0
        and random_entry.get("trade_count") == 1347.0
    )
    check(
        checks,
        failures,
        name="random_entry_terminal_fail_preserved",
        passed=random_entry_ready,
        failure="failure-analysis random-entry baseline is not present terminal-fail evidence",
        evidence=[rel(resolve_path(repo_root, paths["failure_analysis"]), repo_root)],
        details={"status": failure_analysis.get("status"), "random_entry": dict(random_entry)},
    )

    phase8 = payloads.get("phase8_decision", {})
    cost_gate = _phase8_cost_stress(phase8)
    two_x = _two_x_result(cost_gate)
    phase8_ready = (
        phase8.get("promoted") is False
        and phase8.get("research_alpha_ready") is False
        and phase8.get("model_promotion_allowed") is False
        and cost_gate.get("status") == "FAIL"
        and cost_gate.get("required_cost_stress_multiplier") == 2.0
        and two_x.get("edge_survives") is False
        and two_x.get("required_for_promotion") is True
        and two_x.get("stressed_net_return_dollars") == -92118.55500000017
    )
    check(
        checks,
        failures,
        name="phase8_cost_stress_terminal_fail_preserved",
        passed=phase8_ready,
        failure="Phase 8 cost stress/promotion evidence is not blocked as expected",
        evidence=[rel(resolve_path(repo_root, paths["phase8_decision"]), repo_root)],
        details={
            "promoted": phase8.get("promoted"),
            "research_alpha_ready": phase8.get("research_alpha_ready"),
            "model_promotion_allowed": phase8.get("model_promotion_allowed"),
            "cost_gate": dict(cost_gate),
            "two_x": dict(two_x),
        },
    )

    closeout = payloads.get("alpha_closeout", {})
    matrix = payloads.get("alpha_matrix", {})
    bucket_random = _closeout_bucket(closeout, "baseline_random_entry_null")
    bucket_shuffle = _closeout_bucket(closeout, "null_label_shuffle")
    bucket_timing = _closeout_bucket(closeout, "null_timing_shift")
    bucket_regime = _closeout_bucket(closeout, "stability_regime_breakdowns")
    bucket_stability = _closeout_bucket(closeout, "stability_fold_market_year_session")
    bucket_cost = _closeout_bucket(closeout, "execution_cost_stress")
    closeout_ready = (
        matrix.get("alpha_evidence_ready") is False
        and closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and closeout.get("promotion_allowed") is False
        and bucket_random.get("closeout_classification") == "terminal_fail"
        and bucket_shuffle.get("closeout_classification") == "missing_required_evidence"
        and bucket_timing.get("closeout_classification") == "missing_required_evidence"
        and bucket_regime.get("closeout_classification") == "not_actionable_for_current_line"
        and bucket_stability.get("closeout_classification") == "terminal_fail"
        and bucket_cost.get("closeout_classification") == "terminal_fail"
    )
    check(
        checks,
        failures,
        name="alpha_dispositions_preserve_blockers",
        passed=closeout_ready,
        failure="alpha matrix/closeout no longer preserves expected regime/adversarial blockers",
        evidence=[
            rel(resolve_path(repo_root, paths["alpha_matrix"]), repo_root),
            rel(resolve_path(repo_root, paths["alpha_closeout"]), repo_root),
        ],
        details={
            "alpha_evidence_ready": matrix.get("alpha_evidence_ready"),
            "closeout_verdict": closeout.get("verdict"),
            "promotion_allowed": closeout.get("promotion_allowed"),
            "baseline_random_entry_null": dict(bucket_random),
            "null_label_shuffle": dict(bucket_shuffle),
            "null_timing_shift": dict(bucket_timing),
            "stability_regime_breakdowns": dict(bucket_regime),
            "stability_fold_market_year_session": dict(bucket_stability),
            "execution_cost_stress": dict(bucket_cost),
        },
    )

    run_status = payloads.get("run_status", {})
    run_summary = run_status.get("summary") if isinstance(run_status.get("summary"), Mapping) else {}
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
        **DISPOSITIONS,
        "pbo_status": pbo.get("status"),
        "deflated_sharpe_status": dsr.get("status"),
        "multiple_testing_status": multiple.get("status"),
        "probabilistic_sharpe_status": psr.get("status"),
        "regime_breakdowns_status": regime.get("status"),
        "random_entry_candidate_beats_random_median": random_entry.get(
            "candidate_beats_random_median"
        ),
        "random_entry_simulation_count": random_entry.get("simulation_count"),
        "random_entry_trade_count": random_entry.get("trade_count"),
        "two_x_cost_stress_status": adversarial.get("two_x_cost_stress", {}).get("status"),
        "two_x_cost_stress_net_return_dollars": two_x.get("stressed_net_return_dollars"),
        "label_shuffle_status": adversarial.get("label_shuffle", {}).get("status"),
        "timing_shift_status": bucket_timing.get("source_status"),
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


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "terminal_adversarial_failures_preserved",
            "severity": "BLOCKER",
            "finding": (
                "Random-entry/null and two-times cost-stress evidence remain terminal failures "
                "for the current line."
            ),
            "evidence_paths": [
                FAILURE_ANALYSIS.as_posix(),
                PHASE8_DECISION.as_posix(),
                RECOMPUTE_ADVERSARIAL.as_posix(),
            ],
        },
        {
            "finding_id": "missing_null_and_regime_evidence_preserved",
            "severity": "BLOCKER",
            "finding": (
                "Label-shuffle, timing-shift, and explicit causal regime evidence remain missing "
                "or not actionable for the current closed line."
            ),
            "evidence_paths": [
                RECOMPUTE_SUMMARY.as_posix(),
                RECOMPUTE_ADVERSARIAL.as_posix(),
                ALPHA_CLOSEOUT.as_posix(),
            ],
        },
        {
            "finding_id": "statistical_validity_acceptance_not_upgraded",
            "severity": "INFO",
            "finding": (
                "This report classifies existing blockers only; it does not approve statistical "
                "validity, model trust, promotion, paper/live, or production."
            ),
            "evidence_paths": [POST_RECOMPUTE_RECONCILIATION.as_posix()],
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
            "operation": "master_audit_statistical_validity_regime_adversarial_disposition_report_only",
            "target_gap_area": "statistical_validity",
            "target_checks": [
                "random_entry_null",
                "two_x_cost_stress",
                "label_shuffle",
                "timing_shift",
                "regime_breakdowns",
            ],
            "reports_root": rel(reports_root, repo_root),
            "evidence_mode": "existing_local_json_csv_md_repo_evidence_only",
            "data_model_scope": "none",
            "provider_scope": "none",
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
            **dict(NON_APPROVAL),
        },
        "input_evidence": input_evidence,
        "checks": checks,
        "findings": findings,
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "upstream post-recompute reconciliation is PASS and still blocked",
                "random-entry and two-times cost stress are explicit terminal failures",
                "label-shuffle, timing-shift, and regime evidence remain missing/not actionable",
                "statistical validity, model trust, promotion, paper/live, and production remain blocked",
            ],
            "fail": [
                "missing/unreadable required input",
                "any blocker is silently upgraded to PASS",
                "any readiness or non-approval flag is upgraded",
                "output root is outside reports/master_audit",
            ],
        },
        "recommended_next_action": (
            "Plan whether any remaining statistical-validity blocker is actionable for this closed line, "
            "or explicitly decide that statistical validity cannot be remediated without new null/regime evidence."
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
        "# Master Audit Statistical-Validity Regime/Adversarial Disposition",
        "",
        f"- Status: `{report['status']}`",
        f"- Failure count: `{summary['failure_count']}`",
        f"- Random-entry disposition: `{summary['random_entry_null_disposition']}`",
        f"- 2x cost-stress disposition: `{summary['two_x_cost_stress_disposition']}`",
        f"- Label-shuffle disposition: `{summary['label_shuffle_disposition']}`",
        f"- Timing-shift disposition: `{summary['timing_shift_disposition']}`",
        f"- Regime disposition: `{summary['regime_breakdowns_disposition']}`",
        f"- Statistical validity ready: `{summary['statistical_validity_ready']}`",
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
        f"random_entry={report['summary']['random_entry_null_disposition']} "
        f"statistical_validity_ready={report['summary']['statistical_validity_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
