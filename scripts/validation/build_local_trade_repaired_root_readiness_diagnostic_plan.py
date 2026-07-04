#!/usr/bin/env python3
"""Build a console-only repaired-root readiness diagnostic plan."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.phase2_causal_base import build_causal_base_data as phase2_causal_base
from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_proof_status_promotion_proposal as proposal_gate
from scripts.validation import build_local_trade_upstream_manifest_evidence_resolver as resolver_gate


STAGE = "local_trade_repaired_root_readiness_diagnostic_plan"
STATUS_READY = "REVIEW_READY_REPAIRED_ROOT_READINESS_DIAGNOSTIC_PLAN"
STATUS_NO_GO = "NO_GO_REPAIRED_ROOT_READINESS_DIAGNOSTIC_PLAN"
DECISION_PLAN_ONLY = "repaired_root_readiness_diagnostic_plan_only_no_execution"
DECISION_BLOCKED = "repaired_root_readiness_diagnostic_plan_blocked"

DEFAULT_PROPOSAL = proposal_gate.DEFAULT_JSON_OUT
DEFAULT_DIAGNOSTIC_REPORTS_ROOT = Path(
    "reports/pipeline_audit/local_trade_repaired_root_readiness_diagnostic_v1"
)
DEFAULT_RAW_ROOT = "data/raw"
DEFAULT_OUTPUT_ROOT = ledger_gate.TIER1_CAUSAL_ROOT
DEFAULT_RAW_ALIGNMENT_REPORT = "reports/raw_ingest/raw_dbn_alignment.json"
DEFAULT_TIMEOUT_SECONDS_PER_COMMAND = 900

FALSE_APPROVAL_FLAGS = (
    "readiness_diagnostic_approved",
    "include_list_files_written",
    "readiness_reports_written",
    "accepted_warning_packet_approved",
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

REQUIRED_PHASE2_FLAGS = (
    "--readiness-only",
    "--profile",
    "--raw-root",
    "--output-root",
    "--reports-root",
    "--raw-alignment-report",
    "--market-year-include-list",
    "--readiness-json-out",
    "--readiness-md-out",
    "--readiness-checkpoint-jsonl",
    "--readiness-max-market-years",
    "--readiness-stop-after-blockers",
    "--readiness-progress",
)

FORBIDDEN_PATTERNS = (
    "non_readiness_phase2_build_mode",
    "allow_broad_build_after_readiness_pass",
    "broad_build_approval_token",
    "build_max_market_years",
    "build_progress_checkpoint_jsonl",
    "accepted_readiness_exceptions",
    "causal_base_parquet_writes",
    "accepted_warning_packet_writes",
    "labels",
    "feature_matrices",
    "wfa_or_modeling",
    "metrics_or_predictions",
    "proof_scans",
    "provider_downloads",
    "cleanup",
    "live_or_paper_execution",
    "staging_commits_pushes",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return ledger_gate.rel(path, repo_root)


def group_key(profile: str, year: int) -> str:
    return f"{profile}:{int(year)}"


def parse_raw_alignment_report_overrides(values: Iterable[str] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw_value in values or []:
        if "=" not in raw_value:
            raise ValueError(
                "raw alignment report override must use profile:year=path format: "
                f"{raw_value}"
            )
        raw_key, raw_path = raw_value.split("=", 1)
        raw_key = raw_key.strip()
        raw_path = raw_path.strip()
        if ":" not in raw_key or not raw_path:
            raise ValueError(
                "raw alignment report override must use profile:year=path format: "
                f"{raw_value}"
            )
        profile, raw_year = raw_key.split(":", 1)
        try:
            year = int(raw_year)
        except ValueError as exc:
            raise ValueError(
                "raw alignment report override year must be an integer: "
                f"{raw_value}"
            ) from exc
        overrides[group_key(profile.strip(), year)] = raw_path
    return overrides


def _raw_alignment_report_for_group(
    *,
    group: Mapping[str, Any],
    default_raw_alignment_report: str,
    raw_alignment_report_overrides: Mapping[str, str] | None,
) -> str:
    year = int(group["year"])
    profile = str(group.get("planned_profile"))
    resolved_profile = str(group.get("planned_resolved_profile") or profile)
    overrides = raw_alignment_report_overrides or {}
    return (
        overrides.get(group_key(profile, year))
        or overrides.get(group_key(resolved_profile, year))
        or default_raw_alignment_report
    )


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


def _ensure_reports_root(repo_root: Path, reports_root: Path) -> list[str]:
    try:
        reports_root.resolve().relative_to((repo_root / "reports").resolve())
    except ValueError:
        return [f"diagnostic reports root must be under reports/: {rel(reports_root, repo_root)}"]
    return []


def _phase2_declared_flags() -> set[str]:
    parser = phase2_causal_base.build_arg_parser()
    flags: set[str] = set()
    for action in parser._actions:  # noqa: SLF001 - argparse exposes actions for introspection.
        flags.update(option for option in action.option_strings if option.startswith("--"))
    return flags


def _selected_warning_rows(group: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for blocker in group.get("warning_blockers", []):
        if not isinstance(blocker, Mapping):
            continue
        scope = str(blocker.get("scope"))
        if ":" not in scope:
            continue
        market, raw_year = scope.split(":", 1)
        try:
            year = int(raw_year)
        except ValueError:
            continue
        rows.append(
            {
                "market": market,
                "year": year,
                "status": blocker.get("status"),
                "warning_count": blocker.get("warning_count"),
                "warnings": blocker.get("warnings", []),
            }
        )
    return sorted(rows, key=lambda row: (str(row["market"]), int(row["year"])))


def _slug_markets(markets: Iterable[str]) -> str:
    return "_".join(str(market) for market in markets)


def _planned_paths(
    *,
    repo_root: Path,
    diagnostic_reports_root: Path,
    profile: str,
    year: int,
    markets: list[str],
) -> dict[str, str]:
    group_dir = diagnostic_reports_root / f"{profile}_{year}"
    include_name = f"include_{_slug_markets(markets)}_{year}.json"
    return {
        "include_list": rel(diagnostic_reports_root / include_name, repo_root),
        "reports_root": rel(group_dir, repo_root),
        "readiness_json": rel(group_dir / "phase2_readiness_summary.json", repo_root),
        "readiness_markdown": rel(group_dir / "phase2_readiness_summary.md", repo_root),
        "readiness_checkpoint_jsonl": rel(group_dir / "phase2_readiness.progress.jsonl", repo_root),
    }


def _command(
    *,
    group: Mapping[str, Any],
    paths: Mapping[str, str],
    raw_root: str,
    output_root: str,
    raw_alignment_report: str,
) -> str:
    markets = [str(market) for market in group.get("markets", [])]
    max_rows = len(markets)
    return (
        "python -m scripts.phase2_causal_base.build_causal_base_data "
        f"--readiness-only --profile {group.get('planned_profile')} "
        f"--raw-root {raw_root} --output-root {output_root} "
        f"--reports-root {paths['reports_root']} "
        f"--raw-alignment-report {raw_alignment_report} "
        f"--market-year-include-list {paths['include_list']} "
        f"--readiness-json-out {paths['readiness_json']} "
        f"--readiness-md-out {paths['readiness_markdown']} "
        f"--readiness-checkpoint-jsonl {paths['readiness_checkpoint_jsonl']} "
        f"--readiness-max-market-years {max_rows} "
        f"--readiness-stop-after-blockers {max_rows} "
        "--readiness-progress"
    )


def _diagnostic_group(
    *,
    repo_root: Path,
    group: Mapping[str, Any],
    diagnostic_reports_root: Path,
    raw_root: str,
    output_root: str,
    raw_alignment_report: str,
) -> dict[str, Any]:
    markets = [str(market) for market in group.get("markets", [])]
    year = int(group["year"])
    profile = str(group.get("planned_profile"))
    paths = _planned_paths(
        repo_root=repo_root,
        diagnostic_reports_root=diagnostic_reports_root,
        profile=profile,
        year=year,
        markets=markets,
    )
    include_list_payload = {
        "stage": STAGE,
        "scope": "repaired-root readiness diagnostic include list",
        "market_years": [{"market": market, "year": year} for market in markets],
        "non_approval": {
            "causal_base_repair_approved": False,
            "label_build_approved": False,
            "feature_matrix_build_approved": False,
        },
    }
    return {
        "year": year,
        "profile": profile,
        "resolved_profile": group.get("planned_resolved_profile"),
        "causal_root": group.get("causal_root"),
        "markets": markets,
        "market_year_count": len(markets),
        "source_manifest": group.get("manifest_path"),
        "manifest_status": group.get("manifest_status"),
        "raw_alignment_report": raw_alignment_report,
        "selected_warning_rows": _selected_warning_rows(group),
        "metadata_blockers": group.get("metadata_blockers", []),
        "planned_paths": paths,
        "include_list_payload": include_list_payload,
        "command": _command(
            group=group,
            paths=paths,
            raw_root=raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
        ),
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS_PER_COMMAND,
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
    }


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed repaired-root diagnostic-plan checks, then rerun this console-only plan gate."
    return (
        "Approve or reject the bounded repaired-root readiness diagnostic only. If approved, create the "
        "reported include-list files under reports/ and run only the reported Phase 2 --readiness-only "
        "commands; do not run causal-base builds, labels, or features."
    )


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    diagnostic_reports_root: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    expected_eligible_market_count: int = resolver_gate.DEFAULT_EXPECTED_ELIGIBLE_MARKETS,
    expected_proof_status_market_year_count: int = resolver_gate.DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
    raw_root: str = DEFAULT_RAW_ROOT,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    raw_alignment_report: str = DEFAULT_RAW_ALIGNMENT_REPORT,
    raw_alignment_report_overrides: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    resolver_report = resolver_gate.build_report(
        repo_root=repo_root,
        proposal_path=proposal_path,
        staged_generated_paths=staged_generated_paths,
        expected_eligible_market_count=expected_eligible_market_count,
        expected_proof_status_market_year_count=expected_proof_status_market_year_count,
    )
    resolver_summary = resolver_report["summary"]
    groups = [
        group
        for group in resolver_report.get("groups", [])
        if isinstance(group, Mapping) and group.get("classification") == resolver_gate.CLASS_REPAIRED_WARNING
    ]
    phase2_flags = _phase2_declared_flags()
    missing_phase2_flags = sorted(set(REQUIRED_PHASE2_FLAGS) - phase2_flags)
    staged_count = int(resolver_summary.get("staged_generated_path_count") or 0)
    reports_root_failures = _ensure_reports_root(repo_root, diagnostic_reports_root)
    planned_raw_alignment_reports = {
        _raw_alignment_report_for_group(
            group=group,
            default_raw_alignment_report=raw_alignment_report,
            raw_alignment_report_overrides=raw_alignment_report_overrides,
        )
        for group in groups
    }
    raw_alignment_paths = sorted(resolve_path(repo_root, path) for path in planned_raw_alignment_reports)
    missing_raw_alignment_paths = [
        rel(path, repo_root) for path in raw_alignment_paths if not path.exists()
    ]

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="resolver_plan_ready",
        passed=resolver_summary.get("status") == resolver_gate.STATUS_PLAN_READY,
        observed=resolver_summary.get("status"),
        expected=resolver_gate.STATUS_PLAN_READY,
        detail="Readiness diagnostic planning requires a ready upstream evidence resolver report.",
    )
    _check(
        checks,
        name="candidate_projection_blockers_absent",
        passed=int(resolver_summary.get("candidate_projection_feasible_count") or 0) == 0,
        observed=resolver_summary.get("candidate_projection_feasible_count"),
        expected=0,
        detail="Candidate-root projection must be resolved before the repaired-root-only diagnostic plan.",
    )
    _check(
        checks,
        name="repaired_warning_groups_present",
        passed=bool(groups),
        observed=len(groups),
        expected="at least one repaired-root warning group",
        detail="The diagnostic is only useful while repaired-root warning groups remain blocked.",
    )
    _check(
        checks,
        name="missing_manifest_evidence_absent",
        passed=int(resolver_summary.get("missing_manifest_evidence_count") or 0) == 0,
        observed=resolver_summary.get("missing_manifest_evidence_count"),
        expected=0,
        detail="Diagnostic planning requires existing repaired-root manifest evidence to inspect.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=staged_count == 0,
        observed=staged_count,
        expected=0,
        detail="Generated data/** and reports/** artifacts must not be staged while planning diagnostics.",
    )
    _check(
        checks,
        name="phase2_readiness_cli_supports_bounded_diagnostic",
        passed=not missing_phase2_flags,
        observed=missing_phase2_flags,
        expected=[],
        detail="The Phase 2 CLI must expose readiness-only and exact include-list controls.",
    )
    _check(
        checks,
        name="diagnostic_reports_root_under_reports",
        passed=not reports_root_failures,
        observed=reports_root_failures,
        expected=[],
        detail="Planned diagnostic include lists and readiness reports must stay under reports/.",
    )
    _check(
        checks,
        name="raw_alignment_report_present",
        passed=not missing_raw_alignment_paths,
        observed=missing_raw_alignment_paths if missing_raw_alignment_paths else [rel(path, repo_root) for path in raw_alignment_paths],
        expected="all planned raw alignment reports exist",
        detail="Phase 2 readiness-only commands require raw alignment reports for each diagnostic group.",
    )
    _check(
        checks,
        name="diagnostic_plan_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally writes no include-list files or readiness reports.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    diagnostic_groups = (
        [
            _diagnostic_group(
                repo_root=repo_root,
                group=group,
                diagnostic_reports_root=diagnostic_reports_root,
                raw_root=raw_root,
                output_root=output_root,
                raw_alignment_report=_raw_alignment_report_for_group(
                    group=group,
                    default_raw_alignment_report=raw_alignment_report,
                    raw_alignment_report_overrides=raw_alignment_report_overrides,
                ),
            )
            for group in sorted(groups, key=lambda row: int(row["year"]))
        ]
        if not failures
        else []
    )
    status = STATUS_NO_GO if failures else STATUS_READY
    approval_flags = {flag: False for flag in FALSE_APPROVAL_FLAGS}
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_PLAN_ONLY,
            "input_proposal": rel(proposal_path, repo_root),
            "input_resolver_status": resolver_summary.get("status"),
            "diagnostic_group_count": len(diagnostic_groups),
            "diagnostic_market_year_count": sum(group["market_year_count"] for group in diagnostic_groups),
            "raw_alignment_report_count": len(planned_raw_alignment_reports),
            "raw_alignment_report_override_count": len(raw_alignment_report_overrides or {}),
            "raw_alignment_reports": [rel(path, repo_root) for path in raw_alignment_paths],
            "candidate_projection_blocker_count": resolver_summary.get("candidate_projection_feasible_count"),
            "repaired_warning_group_count": len(groups),
            "selected_warning_row_count": sum(
                len(group.get("selected_warning_rows", [])) for group in diagnostic_groups
            ),
            "diagnostic_reports_root": rel(diagnostic_reports_root, repo_root),
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": staged_count,
            "timeout_seconds_per_command": DEFAULT_TIMEOUT_SECONDS_PER_COMMAND,
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **approval_flags,
        },
        "checks": checks,
        "diagnostic_groups": diagnostic_groups,
        "resolver_summary": {
            "status": resolver_summary.get("status"),
            "blocked_group_count": resolver_summary.get("blocked_group_count"),
            "candidate_projection_feasible_count": resolver_summary.get("candidate_projection_feasible_count"),
            "repaired_warning_evidence_required_count": resolver_summary.get("repaired_warning_evidence_required_count"),
            "missing_manifest_evidence_count": resolver_summary.get("missing_manifest_evidence_count"),
            "failure_count": resolver_summary.get("failure_count"),
        },
        "non_approval": {
            "scope": "repaired-root readiness diagnostic plan only",
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
    parser.add_argument(
        "--raw-alignment-report-for",
        action="append",
        default=[],
        help="Per-group override in profile:year=path format; repeat for multiple diagnostic groups.",
    )
    parser.add_argument("--expected-eligible-market-count", type=int, default=resolver_gate.DEFAULT_EXPECTED_ELIGIBLE_MARKETS)
    parser.add_argument(
        "--expected-proof-status-market-year-count",
        type=int,
        default=resolver_gate.DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    proposal_path = resolve_path(repo_root, args.proposal)
    reports_root = resolve_path(repo_root, args.diagnostic_reports_root)
    try:
        raw_alignment_report_overrides = parse_raw_alignment_report_overrides(args.raw_alignment_report_for)
        report = build_report(
            repo_root=repo_root,
            proposal_path=proposal_path,
            diagnostic_reports_root=reports_root,
            expected_eligible_market_count=args.expected_eligible_market_count,
            expected_proof_status_market_year_count=args.expected_proof_status_market_year_count,
            raw_root=str(args.raw_root),
            output_root=str(args.output_root),
            raw_alignment_report=str(args.raw_alignment_report),
            raw_alignment_report_overrides=raw_alignment_report_overrides,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"diagnostic_groups={summary['diagnostic_group_count']} "
        f"diagnostic_market_years={summary['diagnostic_market_year_count']} "
        f"candidate_projection_blockers={summary['candidate_projection_blocker_count']} "
        f"repaired_warning_groups={summary['repaired_warning_group_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
