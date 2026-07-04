#!/usr/bin/env python3
"""Build a console-only ES 2026 P1 blocker proposal."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_review as readiness_review  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_workflow_status as workflow_status  # noqa: E402
from scripts.validation import build_local_trade_optional_archive_inventory as optional_inventory_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_blocker_proposal"
STATUS_READY = "REVIEW_READY_ES2026_P1_BLOCKER_PROPOSAL"
STATUS_NO_GO = "NO_GO_ES2026_P1_BLOCKER_PROPOSAL"
DECISION_PROPOSAL_ONLY = "es2026_p1_blocker_proposal_only_no_execution"
DECISION_BLOCKED = "es2026_p1_blocker_proposal_blocked"

TARGET_MARKET = repair_plan_gate.TARGET_MARKET
TARGET_YEAR = repair_plan_gate.TARGET_YEAR
TARGET_PROFILE = repair_plan_gate.DEFAULT_PROFILE
DEFAULT_REPAIR_REPORTS_ROOT = repair_plan_gate.DEFAULT_REPAIR_REPORTS_ROOT
DEFAULT_RAW_QUALITY_REPORT = DEFAULT_REPAIR_REPORTS_ROOT / "ES_2026_candidate_raw_quality_drilldown.json"
DEFAULT_OPTIONAL_DBN_ROOT = optional_inventory_gate.DEFAULT_DBN_ROOT
FALSE_APPROVAL_FLAGS = repair_plan_gate.FALSE_APPROVAL_FLAGS

PLAN_ARTIFACTS = (
    "scripts/validation/build_local_trade_es2026_p1_blocker_proposal.py",
    "tests/validation/test_build_local_trade_es2026_p1_blocker_proposal.py",
    "PROJECT_OUTLINE.md",
    "CODEX_HANDOFF.md",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return repair_plan_gate.rel(path, repo_root)


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


def _git_staged_generated_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "data", "reports"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --cached failed")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


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


def _summary(report: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = report.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing JSON: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - runtime detail is the useful part.
        return {}, f"unreadable JSON: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"JSON is not an object: {path.as_posix()}"
    return payload, None


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _raw_quality_row(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    rows = _list_of_mappings(payload.get("drilldowns"))
    return rows[0] if len(rows) == 1 else {}


def _exact_scope(payload: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    selected = _list_of_mappings(payload.get("selected_market_years"))
    selected_row = selected[0] if len(selected) == 1 else {}
    return (
        len(selected) == 1
        and str(selected_row.get("market")) == TARGET_MARKET
        and _as_int(selected_row.get("year")) == TARGET_YEAR
        and str(row.get("market")) == TARGET_MARKET
        and _as_int(row.get("year")) == TARGET_YEAR
    )


def _compact_source_evidence(
    *,
    workflow_summary: Mapping[str, Any],
    readiness_summary: Mapping[str, Any],
    optional_summary: Mapping[str, Any],
    raw_quality_report: Path,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "workflow_status": {
            "status": workflow_summary.get("status"),
            "current_gate": workflow_summary.get("current_gate"),
            "current_gate_status": workflow_summary.get("current_gate_status"),
            "next_action_kind": workflow_summary.get("next_action_kind"),
            "generated_output_count": workflow_summary.get("generated_output_count"),
            "staged_generated_path_count": workflow_summary.get("staged_generated_path_count"),
        },
        "candidate_readiness_review": {
            "status": readiness_summary.get("status"),
            "expected_readiness_output_count": readiness_summary.get("expected_readiness_output_count"),
            "ignored_expected_readiness_output_count": readiness_summary.get(
                "ignored_expected_readiness_output_count"
            ),
            "unignored_expected_readiness_output_count": readiness_summary.get(
                "unignored_expected_readiness_output_count"
            ),
            "generated_output_count": readiness_summary.get("generated_output_count"),
            "staged_generated_path_count": readiness_summary.get("staged_generated_path_count"),
            "failure_count": readiness_summary.get("failure_count"),
        },
        "optional_archive_inventory": {
            "status": optional_summary.get("status"),
            "ready_market_count": optional_summary.get("ready_market_count"),
            "expected_market_count": optional_summary.get("expected_market_count"),
            "archive_count": optional_summary.get("archive_count"),
            "invalid_archive_count": optional_summary.get("invalid_archive_count"),
            "generated_output_count": optional_summary.get("generated_output_count"),
            "staged_generated_path_count": optional_summary.get("staged_generated_path_count"),
        },
        "raw_quality_report": rel(raw_quality_report, repo_root),
    }


def _bounded_next_step_plan(*, raw_quality_report: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "disposition_path": "source_tests_docs_only_blocker_proposal_gate",
        "command_family": "source_tests_docs_only_blocker_proposal_gate",
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "profile": TARGET_PROFILE,
            "raw_quality_report": rel(raw_quality_report, repo_root),
            "network": False,
            "data_or_report_generation": False,
            "execution": False,
        },
        "timeout_seconds_per_command": 30,
        "expected_artifacts": list(PLAN_ARTIFACTS),
        "forbidden_patterns": [
            *repair_plan_gate.FORBIDDEN_PATTERNS,
            "readiness_rerun_without_separate_approval",
            "provider_cost_diagnostic_without_separate_approval",
            "accepted_warning_policy_without_separate_approval",
        ],
        "required_evidence": [
            "workflow status is NO_GO at candidate_readiness_execution",
            "candidate readiness review is NO_GO with generated outputs unstaged",
            "optional status/statistics inventory is REVIEW_READY",
            "raw-quality drilldown is FAIL for exactly ES 2026 with degraded threshold evidence",
            "git staged generated data/reports paths are empty",
        ],
        "stop_condition": (
            "Stop when this console-only gate reports REVIEW_READY with one bounded blocker proposal; "
            "do not execute readiness reruns, repairs, accepted-warning policy, exclusions, labels, "
            "features, WFA/modeling, proof scans, provider actions, staging, commits, or pushes."
        ),
    }


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 blocker-proposal preconditions, then rerun this console-only gate."
    return (
        "Review the bounded source/tests/docs-only blocker proposal; do not run readiness, repair, "
        "warning acceptance, exclusion, labels/features, WFA/modeling, proof scan, provider, git, "
        "or live/paper actions without separate approval."
    )


def build_report(
    *,
    repo_root: Path,
    work_order_report: Path,
    drilldown_report: Path,
    checkpoint_jsonl: Path,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    output_root: Path,
    raw_alignment_report: Path,
    raw_quality_report: Path,
    optional_dbn_root: Path | None = None,
    workflow_status_report: Mapping[str, Any] | None = None,
    candidate_readiness_review_report: Mapping[str, Any] | None = None,
    optional_archive_inventory_report: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    common_kwargs = {
        "repo_root": repo_root,
        "work_order_report": work_order_report,
        "drilldown_report": drilldown_report,
        "checkpoint_jsonl": checkpoint_jsonl,
        "repair_reports_root": repair_reports_root,
        "candidate_raw_root": candidate_raw_root,
        "output_root": output_root,
        "raw_alignment_report": raw_alignment_report,
        "generated_at_utc": generated_at_utc,
        "staged_generated_paths": staged_paths,
    }
    if ignored_generated_paths is not None:
        common_kwargs["ignored_generated_paths"] = ignored_generated_paths

    workflow_report = workflow_status_report or workflow_status.build_report(
        **common_kwargs,
        optional_dbn_root=optional_dbn_root,
        optional_archive_inventory_report=optional_archive_inventory_report,
    )
    readiness_report = candidate_readiness_review_report or readiness_review.build_report(
        **common_kwargs
    )
    optional_inventory = optional_archive_inventory_report or optional_inventory_gate.build_report(
        repo_root=repo_root,
        dbn_root=optional_dbn_root or resolve_path(repo_root, DEFAULT_OPTIONAL_DBN_ROOT),
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_paths,
    )
    raw_quality_payload, raw_quality_error = _read_json_object(raw_quality_report)
    raw_quality = _raw_quality_row(raw_quality_payload)

    workflow_summary = _summary(workflow_report)
    readiness_summary = _summary(readiness_report)
    optional_summary = _summary(optional_inventory)

    top_blocker_reason = str(raw_quality.get("top_blocker_reason") or "")
    bounded_plan = _bounded_next_step_plan(raw_quality_report=raw_quality_report, repo_root=repo_root)
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="workflow_status_at_candidate_readiness_no_go",
        passed=(
            workflow_summary.get("status") == workflow_status.STATUS_NO_GO
            and workflow_summary.get("current_gate") == "candidate_readiness_execution"
            and workflow_summary.get("current_gate_status") == "NO_GO_ES2026_P1_CANDIDATE_READINESS_EXECUTION"
            and workflow_summary.get("next_action_kind") == "fix_or_repair_gate"
        ),
        observed={
            "status": workflow_summary.get("status"),
            "current_gate": workflow_summary.get("current_gate"),
            "current_gate_status": workflow_summary.get("current_gate_status"),
            "next_action_kind": workflow_summary.get("next_action_kind"),
        },
        expected="workflow no-go at candidate_readiness_execution with fix_or_repair_gate",
        detail="The blocker proposal must start from the current failed ES 2026 candidate readiness gate.",
    )
    _check(
        checks,
        name="candidate_readiness_review_no_go",
        passed=readiness_summary.get("status") == readiness_review.STATUS_NO_GO,
        observed=readiness_summary.get("status"),
        expected=readiness_review.STATUS_NO_GO,
        detail="The proposal must reflect that candidate readiness outputs are not review-ready.",
    )
    _check(
        checks,
        name="optional_archive_inventory_ready",
        passed=(
            optional_summary.get("status") == optional_inventory_gate.STATUS_READY
            and _as_int(optional_summary.get("ready_market_count")) == _as_int(optional_summary.get("expected_market_count"))
            and _as_int(optional_summary.get("invalid_archive_count")) == 0
        ),
        observed={
            "status": optional_summary.get("status"),
            "ready_market_count": optional_summary.get("ready_market_count"),
            "expected_market_count": optional_summary.get("expected_market_count"),
            "invalid_archive_count": optional_summary.get("invalid_archive_count"),
        },
        expected="ready optional inventory with zero invalid archives",
        detail="The active blocker should not be misclassified as missing optional archive inventory.",
    )
    _check(
        checks,
        name="raw_quality_report_readable",
        passed=raw_quality_error is None,
        observed=raw_quality_error,
        expected="readable JSON object",
        detail="The proposal must read the current ES 2026 candidate raw-quality drilldown.",
    )
    _check(
        checks,
        name="raw_quality_exact_es2026_scope",
        passed=_exact_scope(raw_quality_payload, raw_quality),
        observed={
            "selected_market_years": raw_quality_payload.get("selected_market_years"),
            "drilldown_market": raw_quality.get("market"),
            "drilldown_year": raw_quality.get("year"),
        },
        expected=[{"market": TARGET_MARKET, "year": TARGET_YEAR}],
        detail="The raw-quality evidence must be scoped exactly to ES 2026.",
    )
    _check(
        checks,
        name="raw_quality_degraded_threshold_failure_present",
        passed=(
            raw_quality_payload.get("status") == "FAIL"
            and _as_int(raw_quality_payload.get("selected_market_year_count")) == 1
            and "degraded threshold breached" in top_blocker_reason
            and _as_int(raw_quality.get("degraded_bar_rows")) > 0
            and _as_float(raw_quality.get("degraded_rows_pct")) > 0.0
        ),
        observed={
            "status": raw_quality_payload.get("status"),
            "selected_market_year_count": raw_quality_payload.get("selected_market_year_count"),
            "top_blocker_reason": top_blocker_reason,
            "degraded_bar_rows": raw_quality.get("degraded_bar_rows"),
            "degraded_rows_pct": raw_quality.get("degraded_rows_pct"),
            "degraded_session_rows": raw_quality.get("degraded_session_rows"),
        },
        expected="FAIL with degraded threshold breached evidence",
        detail="The blocker proposal should be grounded in the current degraded-row failure.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while proposing a blocker disposition.",
    )
    _check(
        checks,
        name="bounded_next_step_plan_complete",
        passed=all(
            bounded_plan.get(field)
            for field in (
                "command_family",
                "maximum_scope",
                "timeout_seconds_per_command",
                "expected_artifacts",
                "forbidden_patterns",
                "required_evidence",
                "stop_condition",
            )
        ),
        observed=bounded_plan,
        expected="complete bounded source/tests/docs-only plan",
        detail="The proposal must include scope, command family, timeout, artifacts, forbidden actions, evidence, and stop condition.",
    )
    _check(
        checks,
        name="blocker_proposal_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally exposes no generated report output arguments.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    proposal = [] if failures else [
        {
            "proposal": "source_tests_docs_only_blocker_proposal_gate",
            "proposal_status": "READY_FOR_REVIEW_NOT_EXECUTED",
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "profile": TARGET_PROFILE,
            "current_blocker": {
                "top_blocker_reason": top_blocker_reason,
                "degraded_bar_rows": _as_int(raw_quality.get("degraded_bar_rows")),
                "degraded_rows_pct": _as_float(raw_quality.get("degraded_rows_pct")),
                "degraded_session_rows": _as_int(raw_quality.get("degraded_session_rows")),
                "statistics_enrichment_missing_rows": _as_int(
                    raw_quality.get("statistics_enrichment_missing_rows")
                ),
                "statistics_enrichment_stale_rows": _as_int(
                    raw_quality.get("statistics_enrichment_stale_rows")
                ),
            },
            "bounded_next_step_plan": bounded_plan,
            "rejected_without_separate_approval": [
                "readiness_rerun",
                "provider_download_or_cost_diagnostic",
                "causal_base_repair_or_build",
                "accepted_warning_packet",
                "es2026_exclusion",
                "labels_or_features",
                "wfa_or_modeling",
                "proof_scan",
                "staging_commit_push",
                "live_or_paper_execution",
            ],
        }
    ]

    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_PROPOSAL_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "profile": TARGET_PROFILE,
            "workflow_status": workflow_summary.get("status"),
            "current_gate": workflow_summary.get("current_gate"),
            "current_gate_status": workflow_summary.get("current_gate_status"),
            "candidate_readiness_review_status": readiness_summary.get("status"),
            "optional_archive_inventory_status": optional_summary.get("status"),
            "optional_archive_inventory_ready_market_count": optional_summary.get("ready_market_count"),
            "optional_archive_inventory_invalid_archive_count": optional_summary.get("invalid_archive_count"),
            "raw_quality_status": raw_quality_payload.get("status"),
            "raw_quality_top_blocker_reason": top_blocker_reason,
            "proposal_item_count": len(proposal),
            "bounded_plan_command_family": bounded_plan["command_family"],
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "proposal_items": proposal,
        "bounded_next_step_plan": bounded_plan if not failures else {},
        "source_evidence": _compact_source_evidence(
            workflow_summary=workflow_summary,
            readiness_summary=readiness_summary,
            optional_summary=optional_summary,
            raw_quality_report=raw_quality_report,
            repo_root=repo_root,
        ),
        "non_approval": {
            "scope": "ES 2026 P1 blocker proposal only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-order-report", default=str(repair_plan_gate.DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--drilldown-report", default=str(repair_plan_gate.DEFAULT_DRILLDOWN_REPORT))
    parser.add_argument("--checkpoint-jsonl", default=str(repair_plan_gate.DEFAULT_CHECKPOINT_JSONL))
    parser.add_argument("--repair-reports-root", default=str(DEFAULT_REPAIR_REPORTS_ROOT))
    parser.add_argument("--candidate-raw-root", default=str(repair_plan_gate.DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--output-root", default=str(repair_plan_gate.DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(repair_plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT))
    parser.add_argument("--raw-quality-report", default=str(DEFAULT_RAW_QUALITY_REPORT))
    parser.add_argument("--print-plan-json", action="store_true")
    return parser


def plan_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "stage": STAGE,
        "status": summary.get("status"),
        "market": summary.get("market"),
        "year": summary.get("year"),
        "profile": summary.get("profile"),
        "proposal_item_count": summary.get("proposal_item_count"),
        "bounded_next_step_plan": report.get("bounded_next_step_plan", {}),
        "source_evidence": report.get("source_evidence", {}),
        "generated_artifact_hygiene": {
            "generated_output_count": summary.get("generated_output_count"),
            "staged_generated_path_count": summary.get("staged_generated_path_count"),
        },
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            work_order_report=resolve_path(repo_root, args.work_order_report),
            drilldown_report=resolve_path(repo_root, args.drilldown_report),
            checkpoint_jsonl=resolve_path(repo_root, args.checkpoint_jsonl),
            repair_reports_root=resolve_path(repo_root, args.repair_reports_root),
            candidate_raw_root=resolve_path(repo_root, args.candidate_raw_root),
            output_root=resolve_path(repo_root, args.output_root),
            raw_alignment_report=resolve_path(repo_root, args.raw_alignment_report),
            raw_quality_report=resolve_path(repo_root, args.raw_quality_report),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"current_gate={summary['current_gate']} "
        f"current_gate_status={summary['current_gate_status']} "
        f"candidate_readiness_review_status={summary['candidate_readiness_review_status']} "
        f"optional_inventory_status={summary['optional_archive_inventory_status']} "
        f"raw_quality_status={summary['raw_quality_status']} "
        f"proposal_items={summary['proposal_item_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_plan_json:
        print(json.dumps(plan_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
