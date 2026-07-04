#!/usr/bin/env python3
"""Resolve raw-alignment evidence for the repaired-root readiness diagnostic."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.phase2_causal_base import build_causal_base_data as phase2_causal_base
from scripts.validation import build_local_trade_repaired_root_readiness_diagnostic_plan as diagnostic_plan


STAGE = "local_trade_raw_alignment_evidence_resolver"
STATUS_READY = "REVIEW_READY_RAW_ALIGNMENT_EVIDENCE_REPAIR_PROPOSAL"
STATUS_NO_GO = "NO_GO_RAW_ALIGNMENT_EVIDENCE_RESOLUTION"
DECISION_PROPOSAL_ONLY = "raw_alignment_evidence_repair_proposal_only"
DECISION_BLOCKED = "raw_alignment_evidence_resolution_blocked"

CLASS_MATCHING_READY = "MATCHING_RAW_ALIGNMENT_REPORT_READY"
CLASS_RAW_OBSERVED_SCOPE_UNUSABLE = "RAW_FILES_OBSERVED_BUT_ALIGNMENT_SCOPE_UNUSABLE"
CLASS_MATCHING_MISSING = "MATCHING_RAW_ALIGNMENT_REPORT_MISSING"

DEFAULT_PROPOSAL = diagnostic_plan.DEFAULT_PROPOSAL
DEFAULT_DIAGNOSTIC_REPORTS_ROOT = diagnostic_plan.DEFAULT_DIAGNOSTIC_REPORTS_ROOT
DEFAULT_RAW_ROOT = diagnostic_plan.DEFAULT_RAW_ROOT
DEFAULT_OUTPUT_ROOT = diagnostic_plan.DEFAULT_OUTPUT_ROOT
DEFAULT_RAW_ALIGNMENT_REPORT = diagnostic_plan.DEFAULT_RAW_ALIGNMENT_REPORT
DEFAULT_ALIGNMENT_GLOB = "reports/**/*alignment*.json"
DEFAULT_REPAIR_REPORTS_ROOT = Path("reports/pipeline_audit/local_trade_raw_alignment_repair_v1")
DEFAULT_TIMEOUT_SECONDS_PER_COMMAND = 900

ZERO_COUNT_FIELDS = (
    "missing_raw_count",
    "needs_phase1b_conversion_count",
    "missing_ohlcv_dbn_count",
    "missing_definition_dbn_count",
    "invalid_manifest_count",
    "raw_schema_failure_count",
    "source_hash_mismatch_count",
    "definition_join_mismatch_count",
)

FALSE_APPROVAL_FLAGS = (
    "raw_alignment_generation_approved",
    "diagnostic_runner_update_approved",
    "readiness_diagnostic_approved",
    "causal_base_repair_approved",
    "label_build_approved",
    "feature_matrix_build_approved",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "canonical_promotion_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "live_or_paper_execution_approved",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return diagnostic_plan.rel(path, repo_root)


def _read_json_object(path: Path) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, Mapping) else None


def _int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pair_rows(pairs: Iterable[tuple[str, int]]) -> list[dict[str, Any]]:
    return [
        {"market": market, "year": year}
        for market, year in sorted({(str(market), int(year)) for market, year in pairs})
    ]


def _raw_metric_pairs(report: Mapping[str, Any]) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    metrics = report.get("raw_file_metrics")
    if not isinstance(metrics, list):
        return pairs
    for row in metrics:
        if not isinstance(row, Mapping):
            continue
        market = row.get("market")
        year = _int_value(row.get("year"))
        if market is not None and year is not None:
            pairs.add((str(market), year))
    return pairs


def _target_pairs(group: Mapping[str, Any]) -> set[tuple[str, int]]:
    year = int(group["year"])
    return {(str(market), year) for market in group.get("markets", [])}


def _raw_files_present(repo_root: Path, raw_root: str, target_pairs: set[tuple[str, int]]) -> set[tuple[str, int]]:
    root = resolve_path(repo_root, raw_root)
    present: set[tuple[str, int]] = set()
    for market, year in target_pairs:
        if (root / market / f"{year}.parquet").exists():
            present.add((market, year))
    return present


def _path_matches(repo_root: Path, left: Any, right: Path) -> bool:
    if not isinstance(left, str) or not left:
        return False
    left_path = resolve_path(repo_root, left)
    try:
        return left_path.resolve() == right.resolve()
    except (OSError, ValueError):
        return False


def _raw_alignment_guard_failures(
    *,
    repo_root: Path,
    report: Mapping[str, Any],
    raw_root: Path,
    profile: str,
    resolved_profile: str,
) -> list[str]:
    failures: list[str] = []
    if report.get("stage") != "raw_dbn_alignment_audit":
        failures.append("stage is not raw_dbn_alignment_audit")
    if report.get("status") != "PASS":
        failures.append(f"status is {report.get('status')!r}, not PASS")
    if report.get("audit_completeness") != "full":
        failures.append("audit_completeness is not full")
    if report.get("definition_join_status") != "checked":
        failures.append("definition_join_status is not checked")
    if not _path_matches(repo_root, report.get("raw_root"), raw_root):
        failures.append(
            "raw_root does not match Phase 2 raw_root: "
            f"{report.get('raw_root')} != {rel(raw_root, repo_root)}"
        )
    report_profile = str(report.get("profile", ""))
    report_resolved_profile = str(report.get("resolved_profile", ""))
    if report_profile != profile and report_resolved_profile != resolved_profile:
        failures.append(
            "profile does not match Phase 2 profile: "
            f"{report_profile}/{report_resolved_profile} != {profile}/{resolved_profile}"
        )
    for field_name in ZERO_COUNT_FIELDS:
        value = report.get(field_name)
        if value != 0:
            failures.append(f"{field_name} is {value}, not 0")
    return failures


def _alignment_paths(repo_root: Path, pattern: str) -> list[Path]:
    if not pattern.startswith("reports/") and not pattern.startswith("reports\\"):
        return []
    return sorted(path for path in repo_root.glob(pattern) if path.is_file())


def _candidate_score(candidate: Mapping[str, Any]) -> tuple[int, str]:
    score = 0
    if candidate.get("phase2_usable"):
        score += 100
    score += 8 * int(candidate.get("target_expected_coverage_count") or 0)
    score += 4 * int(candidate.get("target_raw_metric_coverage_count") or 0)
    score += 2 * int(candidate.get("target_raw_file_present_count") or 0)
    score -= len(candidate.get("guard_failures", []))
    return (-score, str(candidate.get("path")))


def _candidate_report(
    *,
    repo_root: Path,
    path: Path,
    report: Mapping[str, Any],
    target_pairs: set[tuple[str, int]],
    raw_root: Path,
    profile: str,
    resolved_profile: str,
) -> dict[str, Any]:
    expected_pairs = phase2_causal_base.raw_alignment_expected_market_years(dict(report))
    raw_metric_pairs = _raw_metric_pairs(report)
    raw_file_pairs = _raw_files_present(repo_root, rel(raw_root, repo_root), target_pairs)
    guard_failures = _raw_alignment_guard_failures(
        repo_root=repo_root,
        report=report,
        raw_root=raw_root,
        profile=profile,
        resolved_profile=resolved_profile,
    )
    expected_hit = target_pairs & expected_pairs
    raw_metric_hit = target_pairs & raw_metric_pairs
    raw_file_hit = target_pairs & raw_file_pairs
    return {
        "path": rel(path, repo_root),
        "status": report.get("status"),
        "profile": report.get("profile"),
        "resolved_profile": report.get("resolved_profile"),
        "raw_root": report.get("raw_root"),
        "expected_market_year_count": len(expected_pairs),
        "raw_metric_market_year_count": len(raw_metric_pairs),
        "target_expected_coverage_count": len(expected_hit),
        "target_raw_metric_coverage_count": len(raw_metric_hit),
        "target_raw_file_present_count": len(raw_file_hit),
        "missing_target_expected_market_years": _pair_rows(target_pairs - expected_pairs),
        "missing_target_raw_metric_market_years": _pair_rows(target_pairs - raw_metric_pairs),
        "missing_target_raw_files": _pair_rows(target_pairs - raw_file_pairs),
        "guard_failures": guard_failures,
        "phase2_usable": not guard_failures and target_pairs <= expected_pairs,
    }


def _scan_group_candidates(
    *,
    repo_root: Path,
    alignment_paths: list[Path],
    group: Mapping[str, Any],
    raw_root: str,
) -> list[dict[str, Any]]:
    target_pairs = _target_pairs(group)
    profile = str(group["profile"])
    resolved_profile = str(group.get("resolved_profile") or profile)
    resolved_raw_root = resolve_path(repo_root, raw_root)
    candidates: list[dict[str, Any]] = []
    for path in alignment_paths:
        report = _read_json_object(path)
        if report is None:
            continue
        if report.get("stage") != "raw_dbn_alignment_audit":
            continue
        candidate = _candidate_report(
            repo_root=repo_root,
            path=path,
            report=report,
            target_pairs=target_pairs,
            raw_root=resolved_raw_root,
            profile=profile,
            resolved_profile=resolved_profile,
        )
        if (
            candidate["phase2_usable"]
            or candidate["target_expected_coverage_count"]
            or candidate["target_raw_metric_coverage_count"]
            or candidate["target_raw_file_present_count"]
            or candidate["profile"] == profile
            or candidate["resolved_profile"] == resolved_profile
        ):
            candidates.append(candidate)
    return sorted(candidates, key=_candidate_score)


def _raw_alignment_generation_command(
    *,
    repo_root: Path,
    group: Mapping[str, Any],
    repair_reports_root: Path,
    raw_root: str,
) -> dict[str, Any]:
    profile = str(group["profile"])
    year = int(group["year"])
    stem = f"{profile}_{year}_raw_dbn_alignment"
    json_out = repair_reports_root / f"{stem}.json"
    md_out = repair_reports_root / f"{stem}.md"
    command = (
        "python -m scripts.validation.audit_raw_dbn_alignment "
        f"--profile {profile} "
        "--dbn-root data/dbn "
        f"--raw-root {raw_root} "
        "--expected-only "
        f"--json-out {rel(json_out, repo_root)} "
        f"--md-out {rel(md_out, repo_root)}"
    )
    return {
        "command": command,
        "json_out": rel(json_out, repo_root),
        "markdown_out": rel(md_out, repo_root),
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS_PER_COMMAND,
        "expected_generated_outputs": [rel(json_out, repo_root), rel(md_out, repo_root)],
        "scope_limit": (
            f"one raw-alignment audit for profile {profile}; profile year {year}; "
            "expected-only profile market-years, no Phase 2 causal-base build"
        ),
    }


def _classify_group(
    *,
    repo_root: Path,
    group: Mapping[str, Any],
    alignment_paths: list[Path],
    raw_root: str,
    repair_reports_root: Path,
) -> dict[str, Any]:
    target_pairs = _target_pairs(group)
    candidates = _scan_group_candidates(
        repo_root=repo_root,
        alignment_paths=alignment_paths,
        group=group,
        raw_root=raw_root,
    )
    matching = [candidate for candidate in candidates if candidate["phase2_usable"]]
    full_raw_metric = [
        candidate for candidate in candidates if candidate["target_raw_metric_coverage_count"] == len(target_pairs)
    ]
    raw_files_present = _raw_files_present(repo_root, raw_root, target_pairs)
    if matching:
        classification = CLASS_MATCHING_READY
        proposed_path = (
            "Use the matching raw-alignment report for this diagnostic group, then rerun the "
            "guarded readiness diagnostic after stale diagnostic-output disposition is approved."
        )
    elif full_raw_metric or raw_files_present == target_pairs:
        classification = CLASS_RAW_OBSERVED_SCOPE_UNUSABLE
        proposed_path = (
            "Generate a matching per-profile raw-alignment report with the bounded audit command; "
            "then update the diagnostic plan/runner to pass the group-specific raw-alignment report."
        )
    else:
        classification = CLASS_MATCHING_MISSING
        proposed_path = (
            "Locate or generate raw-alignment evidence covering the selected market-years before "
            "rerunning the repaired-root readiness diagnostic."
        )
    return {
        "year": int(group["year"]),
        "profile": group["profile"],
        "resolved_profile": group.get("resolved_profile"),
        "markets": list(group.get("markets", [])),
        "target_market_years": _pair_rows(target_pairs),
        "classification": classification,
        "matching_raw_alignment_report": matching[0]["path"] if matching else None,
        "candidate_count": len(candidates),
        "near_candidate_reports": candidates[:8],
        "raw_files_present_count": len(raw_files_present),
        "missing_raw_files": _pair_rows(target_pairs - raw_files_present),
        "approval_required": classification != CLASS_MATCHING_READY,
        "proposed_repair_path": proposed_path,
        "proposed_generation_command": _raw_alignment_generation_command(
            repo_root=repo_root,
            group=group,
            repair_reports_root=repair_reports_root,
            raw_root=raw_root,
        ),
    }


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _recommended_next(status: str, class_counts: Counter[str]) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed raw-alignment evidence resolver preconditions, then rerun this console-only gate."
    if class_counts.get(CLASS_RAW_OBSERVED_SCOPE_UNUSABLE) or class_counts.get(CLASS_MATCHING_MISSING):
        return (
            "Approve or reject a bounded raw-alignment repair direction: source/tests/docs-only "
            "diagnostic plan/runner support for per-group raw-alignment reports, followed by separate "
            "approval before generating the proposed raw-alignment reports."
        )
    return (
        "Approve or reject rerunning the guarded repaired-root readiness diagnostic with matching "
        "raw-alignment evidence; do not run causal-base builds, labels, or features."
    )


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    diagnostic_reports_root: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    expected_eligible_market_count: int = diagnostic_plan.resolver_gate.DEFAULT_EXPECTED_ELIGIBLE_MARKETS,
    expected_proof_status_market_year_count: int = diagnostic_plan.resolver_gate.DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
    raw_root: str = DEFAULT_RAW_ROOT,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    raw_alignment_report: str = DEFAULT_RAW_ALIGNMENT_REPORT,
    alignment_glob: str = DEFAULT_ALIGNMENT_GLOB,
    repair_reports_root: Path | None = None,
) -> dict[str, Any]:
    repair_root = repair_reports_root or resolve_path(repo_root, DEFAULT_REPAIR_REPORTS_ROOT)
    plan = diagnostic_plan.build_report(
        repo_root=repo_root,
        proposal_path=proposal_path,
        diagnostic_reports_root=diagnostic_reports_root,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_generated_paths,
        expected_eligible_market_count=expected_eligible_market_count,
        expected_proof_status_market_year_count=expected_proof_status_market_year_count,
        raw_root=raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
    )
    plan_summary = plan["summary"]
    staged_count = int(plan_summary.get("staged_generated_path_count") or 0)
    diagnostic_groups = [group for group in plan.get("diagnostic_groups", []) if isinstance(group, Mapping)]
    alignment_paths = _alignment_paths(repo_root, alignment_glob)
    groups = [
        _classify_group(
            repo_root=repo_root,
            group=group,
            alignment_paths=alignment_paths,
            raw_root=raw_root,
            repair_reports_root=repair_root,
        )
        for group in diagnostic_groups
    ]
    class_counts: Counter[str] = Counter(str(group["classification"]) for group in groups)
    matching_paths = {
        str(group["matching_raw_alignment_report"])
        for group in groups
        if group.get("matching_raw_alignment_report")
    }

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="diagnostic_plan_ready",
        passed=plan_summary.get("status") == diagnostic_plan.STATUS_READY,
        observed=plan_summary.get("status"),
        expected=diagnostic_plan.STATUS_READY,
        detail="Raw-alignment evidence resolution uses the repaired-root diagnostic plan scope.",
    )
    _check(
        checks,
        name="diagnostic_groups_present",
        passed=bool(diagnostic_groups),
        observed=len(diagnostic_groups),
        expected="at least one diagnostic group",
        detail="There must be repaired-root diagnostic groups to resolve raw-alignment evidence for.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=staged_count == 0,
        observed=staged_count,
        expected=0,
        detail="Generated data/** and reports/** artifacts must not be staged during evidence resolution.",
    )
    _check(
        checks,
        name="alignment_scan_bounded_to_reports",
        passed=alignment_glob.startswith("reports/") or alignment_glob.startswith("reports\\"),
        observed=alignment_glob,
        expected="reports/** bounded glob",
        detail="Resolver may inspect existing reports only; it must not scan arbitrary filesystem roots.",
    )
    _check(
        checks,
        name="raw_alignment_resolver_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate does not expose generated report output arguments.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    approval_flags = {flag: False for flag in FALSE_APPROVAL_FLAGS}
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_PROPOSAL_ONLY,
            "input_proposal": rel(proposal_path, repo_root),
            "input_diagnostic_plan_status": plan_summary.get("status"),
            "diagnostic_group_count": len(diagnostic_groups),
            "alignment_candidate_file_count": len(alignment_paths),
            "matching_group_count": class_counts.get(CLASS_MATCHING_READY, 0),
            "raw_observed_scope_unusable_group_count": class_counts.get(CLASS_RAW_OBSERVED_SCOPE_UNUSABLE, 0),
            "matching_missing_group_count": class_counts.get(CLASS_MATCHING_MISSING, 0),
            "single_matching_report_for_all_groups": (
                bool(groups)
                and class_counts.get(CLASS_MATCHING_READY, 0) == len(groups)
                and len(matching_paths) == 1
            ),
            "per_group_raw_alignment_report_required": bool(groups) and len(matching_paths) != 1,
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": staged_count,
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status, class_counts),
            **approval_flags,
        },
        "checks": checks,
        "groups": groups,
        "classification_counts": dict(sorted(class_counts.items())),
        "diagnostic_plan_summary": {
            "status": plan_summary.get("status"),
            "diagnostic_group_count": plan_summary.get("diagnostic_group_count"),
            "diagnostic_market_year_count": plan_summary.get("diagnostic_market_year_count"),
            "failure_count": plan_summary.get("failure_count"),
        },
        "non_approval": {
            "scope": "raw-alignment evidence resolver only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **approval_flags,
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--proposal", default=str(DEFAULT_PROPOSAL))
    parser.add_argument("--diagnostic-reports-root", default=str(DEFAULT_DIAGNOSTIC_REPORTS_ROOT))
    parser.add_argument("--raw-root", default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--raw-alignment-report", default=DEFAULT_RAW_ALIGNMENT_REPORT)
    parser.add_argument("--alignment-glob", default=DEFAULT_ALIGNMENT_GLOB)
    parser.add_argument("--repair-reports-root", default=str(DEFAULT_REPAIR_REPORTS_ROOT))
    parser.add_argument(
        "--expected-eligible-market-count",
        type=int,
        default=diagnostic_plan.resolver_gate.DEFAULT_EXPECTED_ELIGIBLE_MARKETS,
    )
    parser.add_argument(
        "--expected-proof-status-market-year-count",
        type=int,
        default=diagnostic_plan.resolver_gate.DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    proposal_path = resolve_path(repo_root, args.proposal)
    reports_root = resolve_path(repo_root, args.diagnostic_reports_root)
    repair_reports_root = resolve_path(repo_root, args.repair_reports_root)
    try:
        report = build_report(
            repo_root=repo_root,
            proposal_path=proposal_path,
            diagnostic_reports_root=reports_root,
            expected_eligible_market_count=args.expected_eligible_market_count,
            expected_proof_status_market_year_count=args.expected_proof_status_market_year_count,
            raw_root=str(args.raw_root),
            output_root=str(args.output_root),
            raw_alignment_report=str(args.raw_alignment_report),
            alignment_glob=str(args.alignment_glob),
            repair_reports_root=repair_reports_root,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"diagnostic_groups={summary['diagnostic_group_count']} "
        f"alignment_candidates={summary['alignment_candidate_file_count']} "
        f"matching_groups={summary['matching_group_count']} "
        f"raw_observed_scope_unusable_groups={summary['raw_observed_scope_unusable_group_count']} "
        f"matching_missing_groups={summary['matching_missing_group_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
