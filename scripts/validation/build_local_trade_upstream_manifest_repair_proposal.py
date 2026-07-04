#!/usr/bin/env python3
"""Build a console-only upstream manifest repair proposal."""

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

from scripts.phase3_labels import build_labels as phase3_labels
from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_upstream_manifest_evidence_resolver as resolver_gate


STAGE = "local_trade_upstream_manifest_repair_proposal"
STATUS_READY = "REVIEW_READY_UPSTREAM_MANIFEST_REPAIR_PROPOSAL"
STATUS_NO_GO = "NO_GO_UPSTREAM_MANIFEST_REPAIR_PROPOSAL"
DECISION_PROPOSAL_ONLY = "upstream_manifest_repair_proposal_only_no_execution"
DECISION_BLOCKED = "upstream_manifest_repair_proposal_blocked"

ACTION_CANDIDATE_PROJECTION = "candidate_manifest_profile_projection"
ACTION_REPAIRED_WARNING = "repaired_root_warning_resolution"
PROPOSAL_STATUS_APPROVAL_REQUIRED = "APPROVAL_REQUIRED_NOT_EXECUTED"

DEFAULT_PROPOSAL = resolver_gate.DEFAULT_PROPOSAL
DEFAULT_EXPECTED_ELIGIBLE_MARKETS = resolver_gate.DEFAULT_EXPECTED_ELIGIBLE_MARKETS
DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS = resolver_gate.DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS

FALSE_APPROVAL_FLAGS = (
    "manifest_projection_approved",
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

FORBIDDEN_NOW = (
    "generated_reports",
    "manifest_projections",
    "accepted_warning_files",
    "causal_base_outputs",
    "labels",
    "feature_matrices",
    "wfa_or_modeling",
    "metrics_or_predictions",
    "proof_scans",
    "provider_downloads",
    "live_or_paper_execution",
    "staging_commits_pushes",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return resolver_gate.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return resolver_gate.rel(path, repo_root)


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


def _current_phase3_acceptance_support() -> dict[str, Any]:
    approved_root = phase3_labels.APPROVED_TIER1_CANDIDATE_ROOT.as_posix()
    approved_path = phase3_labels.APPROVED_TIER1_ACCEPTED_EXCEPTIONS_PATH.as_posix()
    return {
        "approved_input_root": approved_root,
        "approved_exceptions_path": approved_path,
        "approved_exception_count": len(phase3_labels.APPROVED_TIER1_ACCEPTED_EXCEPTIONS),
        "reusable_for_local_trade_repaired_root": approved_root == ledger_gate.TIER1_CAUSAL_ROOT,
        "current_local_trade_repaired_root": ledger_gate.TIER1_CAUSAL_ROOT,
        "detail": (
            "Existing Phase 3 accepted-readiness exceptions are restricted to an older Tier 1 "
            "candidate root and cannot approve the current local-trade repaired-root warnings."
        ),
    }


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


def _candidate_projection_item(group: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action": ACTION_CANDIDATE_PROJECTION,
        "proposal_status": PROPOSAL_STATUS_APPROVAL_REQUIRED,
        "causal_root": group.get("causal_root"),
        "year": group.get("year"),
        "markets": group.get("markets", []),
        "source_manifest": group.get("manifest_path"),
        "source_profile": group.get("manifest_profile"),
        "source_resolved_profile": group.get("manifest_resolved_profile"),
        "target_profile": group.get("planned_profile"),
        "target_resolved_profile": group.get("planned_resolved_profile"),
        "proposed_repair": (
            "If separately approved, create a bounded generated manifest-profile projection from the "
            "existing PASS all_raw candidate-root manifest to the exact Phase 3 profile/year scope. "
            "Do not change parquet data."
        ),
        "required_independent_checks": [
            "source manifest remains PASS",
            "selected output rows remain PASS with zero warnings and zero failures",
            "output file hashes still reference the selected market-year parquet files",
            "generated projection, if later approved, is review-only until readiness passes",
        ],
        "forbidden_now": list(FORBIDDEN_NOW),
    }


def _repaired_warning_item(group: Mapping[str, Any], acceptance_support: Mapping[str, Any]) -> dict[str, Any]:
    selected_warnings = _selected_warning_rows(group)
    return {
        "action": ACTION_REPAIRED_WARNING,
        "proposal_status": PROPOSAL_STATUS_APPROVAL_REQUIRED,
        "causal_root": group.get("causal_root"),
        "year": group.get("year"),
        "markets": group.get("markets", []),
        "source_manifest": group.get("manifest_path"),
        "manifest_status": group.get("manifest_status"),
        "manifest_profile": group.get("manifest_profile"),
        "manifest_resolved_profile": group.get("manifest_resolved_profile"),
        "target_profile": group.get("planned_profile"),
        "target_resolved_profile": group.get("planned_resolved_profile"),
        "selected_warning_rows": selected_warnings,
        "metadata_blockers": group.get("metadata_blockers", []),
        "existing_phase3_acceptance_support_reusable": bool(
            acceptance_support.get("reusable_for_local_trade_repaired_root")
        ),
        "proposed_repair_options": [
            {
                "option": "accepted_warning_packet_plus_manifest_metadata_projection",
                "approval_required": True,
                "sufficient_by_itself": False,
                "detail": (
                    "A warning packet alone is not enough while the repaired-root manifest "
                    "resolved_profile metadata does not match the planned Phase 3 profile."
                ),
            },
            {
                "option": "bounded_causal_base_repair",
                "approval_required": True,
                "sufficient_by_itself": "only if it produces matching PASS manifest evidence or approved warnings",
                "detail": (
                    "Rebuild or repair only the selected repaired-root market-years under a separately "
                    "approved bounded command gate."
                ),
            },
        ],
        "required_independent_checks": [
            "selected warning text is preserved exactly",
            "manifest resolved_profile metadata is corrected or explicitly accepted",
            "no unselected WARN rows are silently accepted for Phase 3 labels",
            "baseline readiness returns review-ready before any labels/features run",
        ],
        "forbidden_now": list(FORBIDDEN_NOW),
    }


def _proposal_items(resolver_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    acceptance_support = _current_phase3_acceptance_support()
    items: list[dict[str, Any]] = []
    for group in resolver_report.get("groups", []):
        if not isinstance(group, Mapping):
            continue
        classification = group.get("classification")
        if classification == resolver_gate.CLASS_CANDIDATE_PROJECTION:
            items.append(_candidate_projection_item(group))
        elif classification == resolver_gate.CLASS_REPAIRED_WARNING:
            items.append(_repaired_warning_item(group, acceptance_support))
    return items


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed repair proposal preconditions, then rerun this proposal gate."
    return (
        "Review this proposal and separately approve one actual repair path before creating generated "
        "manifest projections, accepted-warning packets, causal-base outputs, labels, or feature matrices."
    )


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    expected_eligible_market_count: int = DEFAULT_EXPECTED_ELIGIBLE_MARKETS,
    expected_proof_status_market_year_count: int = DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
) -> dict[str, Any]:
    resolver_report = resolver_gate.build_report(
        repo_root=repo_root,
        proposal_path=proposal_path,
        staged_generated_paths=staged_generated_paths,
        expected_eligible_market_count=expected_eligible_market_count,
        expected_proof_status_market_year_count=expected_proof_status_market_year_count,
    )
    resolver_summary = resolver_report["summary"]
    items = _proposal_items(resolver_report)
    candidate_items = [item for item in items if item["action"] == ACTION_CANDIDATE_PROJECTION]
    repaired_items = [item for item in items if item["action"] == ACTION_REPAIRED_WARNING]
    staged_count = int(resolver_summary.get("staged_generated_path_count") or 0)
    acceptance_support = _current_phase3_acceptance_support()

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="resolver_plan_ready",
        passed=resolver_summary.get("status") == resolver_gate.STATUS_PLAN_READY,
        observed=resolver_summary.get("status"),
        expected=resolver_gate.STATUS_PLAN_READY,
        detail="Repair proposals can only be built from a ready upstream evidence resolver report.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=staged_count == 0,
        observed=staged_count,
        expected=0,
        detail="Generated data/** and reports/** artifacts must not be staged while proposing repairs.",
    )
    _check(
        checks,
        name="repair_proposal_items_present",
        passed=bool(items),
        observed=len(items),
        expected="at least one candidate projection or repaired warning proposal",
        detail="The proposal gate should convert resolver blocker classifications into reviewable repair items.",
    )
    _check(
        checks,
        name="phase3_existing_warning_acceptance_not_reused_silently",
        passed=acceptance_support["reusable_for_local_trade_repaired_root"] is False,
        observed=acceptance_support,
        expected="current local-trade repaired-root warnings require a new explicit approval path",
        detail="Existing Phase 3 accepted exceptions must not be treated as approval for this local-trade scope.",
    )
    _check(
        checks,
        name="proposal_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally exposes no generated report output arguments.",
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
            "input_resolver_status": resolver_summary.get("status"),
            "proposal_item_count": len(items),
            "candidate_projection_proposal_count": len(candidate_items),
            "repaired_warning_proposal_count": len(repaired_items),
            "selected_warning_row_count": sum(len(item.get("selected_warning_rows", [])) for item in repaired_items),
            "staged_generated_path_count": staged_count,
            "generated_report_written": False,
            "generated_output_count": 0,
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **approval_flags,
        },
        "checks": checks,
        "proposal_items": items,
        "phase3_existing_warning_acceptance_support": acceptance_support,
        "resolver_summary": {
            "status": resolver_summary.get("status"),
            "blocked_group_count": resolver_summary.get("blocked_group_count"),
            "candidate_projection_feasible_count": resolver_summary.get("candidate_projection_feasible_count"),
            "repaired_warning_evidence_required_count": resolver_summary.get("repaired_warning_evidence_required_count"),
            "missing_manifest_evidence_count": resolver_summary.get("missing_manifest_evidence_count"),
            "failure_count": resolver_summary.get("failure_count"),
        },
        "non_approval": {
            "scope": "upstream manifest repair proposal only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **approval_flags,
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--proposal", default=str(DEFAULT_PROPOSAL))
    parser.add_argument("--expected-eligible-market-count", type=int, default=DEFAULT_EXPECTED_ELIGIBLE_MARKETS)
    parser.add_argument(
        "--expected-proof-status-market-year-count",
        type=int,
        default=DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    proposal_path = resolve_path(repo_root, args.proposal)
    try:
        report = build_report(
            repo_root=repo_root,
            proposal_path=proposal_path,
            expected_eligible_market_count=args.expected_eligible_market_count,
            expected_proof_status_market_year_count=args.expected_proof_status_market_year_count,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"proposal_items={summary['proposal_item_count']} "
        f"candidate_projection_proposals={summary['candidate_projection_proposal_count']} "
        f"repaired_warning_proposals={summary['repaired_warning_proposal_count']} "
        f"selected_warning_rows={summary['selected_warning_row_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
