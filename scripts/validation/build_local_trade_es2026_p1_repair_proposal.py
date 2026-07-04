#!/usr/bin/env python3
"""Build a console-only ES 2026 P1 repair proposal."""

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


STAGE = "local_trade_es2026_p1_repair_proposal"
STATUS_READY = "REVIEW_READY_ES2026_P1_REPAIR_PROPOSAL"
STATUS_NO_GO = "NO_GO_ES2026_P1_REPAIR_PROPOSAL"
DECISION_PROPOSAL_ONLY = "es2026_p1_repair_proposal_only_no_execution"
DECISION_BLOCKED = "es2026_p1_repair_proposal_blocked"

TARGET_MARKET = "ES"
TARGET_YEAR = 2026
PROPOSAL_STATUS_APPROVAL_REQUIRED = "APPROVAL_REQUIRED_NOT_EXECUTED"

DEFAULT_REPORTS_ROOT = Path(
    "reports/pipeline_audit/local_trade_repaired_root_readiness_diagnostic_v2/"
    "tier_3_forward_2026"
)
DEFAULT_WORK_ORDER_REPORT = DEFAULT_REPORTS_ROOT / "ES_2026_repair_work_order.json"
DEFAULT_DRILLDOWN_REPORT = DEFAULT_REPORTS_ROOT / "ES_2026_readiness_drilldown.json"

EXPECTED_WORK_ORDER_ACTIONS = (
    "repair_status_statistics_enrichment",
    "review_degraded_raw_quality",
    "exclude_only_if_explicitly_approved",
)

FALSE_APPROVAL_FLAGS = (
    "statistics_enrichment_repair_approved",
    "degraded_raw_quality_acceptance_approved",
    "exclusion_approved",
    "accepted_warning_packet_approved",
    "causal_base_repair_approved",
    "label_build_approved",
    "feature_matrix_build_approved",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "proof_scan_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "live_or_paper_execution_approved",
)

FORBIDDEN_NOW = (
    "generated_report_writes",
    "causal_base_repair_or_build",
    "accepted_warning_packets",
    "label_or_feature_generation",
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
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


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


def _read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"report missing: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive detail comes from runtime exception.
        return {}, f"report unreadable: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"report is not a JSON object: {path.as_posix()}"
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
    return [row for row in value if isinstance(row, Mapping)]


def _target_row(rows: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    if len(rows) != 1:
        return {}
    return rows[0]


def _is_target(row: Mapping[str, Any]) -> bool:
    return str(row.get("market")) == TARGET_MARKET and _as_int(row.get("year")) == TARGET_YEAR


def _actions(row: Mapping[str, Any]) -> list[str]:
    return [str(action) for action in row.get("work_order_actions", []) if str(action)]


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


def _proposal_items(work_order: Mapping[str, Any], drilldown: Mapping[str, Any]) -> list[dict[str, Any]]:
    statistics_missing = _as_int(work_order.get("statistics_enrichment_missing_rows"))
    statistics_stale = _as_int(work_order.get("statistics_enrichment_stale_rows"))
    degraded_rows = _as_int(work_order.get("degraded_bar_rows"))
    degraded_pct = _as_float(work_order.get("degraded_rows_pct"))
    degraded_sessions = _as_int(work_order.get("degraded_session_rows"))
    session_gap_summary = drilldown.get("phase2_session_gap_summary")
    if not isinstance(session_gap_summary, Mapping):
        session_gap_summary = {}
    raw_gap_summary = drilldown.get("raw_gap_summary")
    if not isinstance(raw_gap_summary, Mapping):
        raw_gap_summary = {}
    top_statistics_dates = drilldown.get("top_statistics_missing_dates")
    if not isinstance(top_statistics_dates, list):
        top_statistics_dates = []
    top_degraded_dates = drilldown.get("top_degraded_dates")
    if not isinstance(top_degraded_dates, list):
        top_degraded_dates = []

    return [
        {
            "action": "repair_or_refresh_statistics_enrichment_evidence",
            "proposal_status": PROPOSAL_STATUS_APPROVAL_REQUIRED,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "current_evidence": {
                "statistics_enrichment_missing_rows": statistics_missing,
                "statistics_enrichment_stale_rows": statistics_stale,
                "top_statistics_missing_dates": top_statistics_dates,
            },
            "proposed_direction": (
                "If separately approved, repair or refresh the ES 2026 statistics enrichment "
                "evidence before any readiness rerun. Do not accept missing or stale statistics "
                "metadata as training-ready evidence in this proposal gate."
            ),
            "required_independent_checks": [
                "statistics enrichment source rows are causal and instrument-scoped",
                "missing and stale statistics enrichment rows fall to zero or are separately explained",
                "bounded ES 2026 readiness is rerun only after the repair evidence exists",
            ],
            "forbidden_now": list(FORBIDDEN_NOW),
        },
        {
            "action": "review_degraded_raw_quality_evidence",
            "proposal_status": PROPOSAL_STATUS_APPROVAL_REQUIRED,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "current_evidence": {
                "degraded_bar_rows": degraded_rows,
                "degraded_rows_pct": degraded_pct,
                "degraded_session_rows": degraded_sessions,
                "raw_gap_count": _as_int(raw_gap_summary.get("gap_count")),
                "phase2_session_candidate_gap_count": _as_int(
                    session_gap_summary.get("candidate_gap_count")
                ),
                "phase2_session_synthetic_missing_rows_estimate": _as_int(
                    session_gap_summary.get("synthetic_missing_rows_estimate")
                ),
                "top_degraded_dates": top_degraded_dates,
            },
            "proposed_direction": (
                "Review the ES 2026 degraded raw-quality evidence before repair/build decisions. "
                "If a later repair is approved, it must preserve causal data provenance and produce "
                "PASS readiness evidence before ES 2026 can feed labels or model training."
            ),
            "required_independent_checks": [
                "degraded rows and session gaps are attributable to source quality, enrichment, or session scope",
                "any repaired raw-quality evidence is bounded to ES 2026 and reproducible",
                "thresholds are not loosened to convert WARN to PASS",
            ],
            "forbidden_now": list(FORBIDDEN_NOW),
        },
        {
            "action": "keep_exclusion_diagnostic_only",
            "proposal_status": PROPOSAL_STATUS_APPROVAL_REQUIRED,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "current_evidence": {
                "candidate_exclusion_status": work_order.get("candidate_exclusion_status"),
                "work_order_actions": _actions(work_order),
            },
            "proposed_direction": (
                "Keep ES 2026 exclusion diagnostic-only unless the user separately approves a "
                "universe-change decision. Do not silently drop ES 2026 to make the baseline scope pass."
            ),
            "required_independent_checks": [
                "explicit user approval exists before any exclusion is applied",
                "model-eligible scope and baseline-readiness impact are re-evaluated after any exclusion",
                "exclusion is not used as a substitute for repair when repair evidence is feasible",
            ],
            "forbidden_now": list(FORBIDDEN_NOW),
        },
    ]


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 proposal preconditions, then rerun this console-only gate."
    return (
        "Review this proposal and separately approve a bounded ES 2026 P1 repair plan or keep ES 2026 "
        "fail-closed; do not run repairs, warning acceptance, exclusions, labels, or features without approval."
    )


def build_report(
    *,
    repo_root: Path,
    work_order_report: Path,
    drilldown_report: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    work_order_payload, work_order_error = _read_json_object(work_order_report)
    drilldown_payload, drilldown_error = _read_json_object(drilldown_report)
    work_orders = _list_of_mappings(work_order_payload.get("work_orders"))
    drilldowns = _list_of_mappings(drilldown_payload.get("drilldowns"))
    selected_market_years = _list_of_mappings(drilldown_payload.get("selected_market_years"))
    work_order = _target_row(work_orders)
    drilldown = _target_row(drilldowns)
    selected_market_year = _target_row(selected_market_years)
    action_set = set(_actions(work_order))
    p0_batch = work_order_payload.get("p0_repair_start_batch")
    if not isinstance(p0_batch, Mapping):
        p0_batch = {}
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="work_order_report_readable",
        passed=work_order_error is None,
        observed=work_order_error,
        expected="readable JSON object",
        detail="The proposal gate must read the generated ES 2026 work-order report.",
    )
    _check(
        checks,
        name="drilldown_report_readable",
        passed=drilldown_error is None,
        observed=drilldown_error,
        expected="readable JSON object",
        detail="The proposal gate must read the generated ES 2026 drilldown report.",
    )
    _check(
        checks,
        name="work_order_exact_es2026_scope",
        passed=len(work_orders) == 1 and _is_target(work_order),
        observed=[{"market": row.get("market"), "year": row.get("year")} for row in work_orders],
        expected=[{"market": TARGET_MARKET, "year": TARGET_YEAR}],
        detail="This gate is scoped only to the approved ES 2026 work order.",
    )
    _check(
        checks,
        name="drilldown_exact_es2026_scope",
        passed=(
            len(drilldowns) == 1
            and _is_target(drilldown)
            and len(selected_market_years) == 1
            and _is_target(selected_market_year)
        ),
        observed={
            "selected": [
                {"market": row.get("market"), "year": row.get("year")}
                for row in selected_market_years
            ],
            "drilldowns": [
                {"market": row.get("market"), "year": row.get("year")}
                for row in drilldowns
            ],
        },
        expected={"market": TARGET_MARKET, "year": TARGET_YEAR},
        detail="Drilldown evidence must be restricted to the approved ES 2026 scope.",
    )
    _check(
        checks,
        name="p1_work_order_actions_present",
        passed=work_order.get("priority") == "P1" and set(EXPECTED_WORK_ORDER_ACTIONS) <= action_set,
        observed={"priority": work_order.get("priority"), "actions": sorted(action_set)},
        expected={"priority": "P1", "actions": list(EXPECTED_WORK_ORDER_ACTIONS)},
        detail="The proposal should be based on the expected P1 enrichment and degraded-quality actions.",
    )
    _check(
        checks,
        name="p0_starter_batch_empty",
        passed=_as_int(p0_batch.get("all_p0_raw_session_count")) == 0 and _as_int(p0_batch.get("batch_size")) == 0,
        observed={
            "all_p0_raw_session_count": p0_batch.get("all_p0_raw_session_count"),
            "batch_size": p0_batch.get("batch_size"),
            "readiness_rerun_status": p0_batch.get("readiness_rerun_status"),
        },
        expected={"all_p0_raw_session_count": 0, "batch_size": 0},
        detail="The ES 2026 work order should not imply an approved P0 raw/session repair batch.",
    )
    _check(
        checks,
        name="fail_closed_policy_preserved",
        passed=(
            work_order_payload.get("status") == "FAIL"
            and work_order_payload.get("ready_to_rebuild_tier3_phase2") is False
            and work_order.get("candidate_exclusion_status") == "DIAGNOSTIC_ONLY_NOT_APPROVED"
        ),
        observed={
            "work_order_status": work_order_payload.get("status"),
            "ready_to_rebuild_tier3_phase2": work_order_payload.get("ready_to_rebuild_tier3_phase2"),
            "candidate_exclusion_status": work_order.get("candidate_exclusion_status"),
        },
        expected="FAIL, not rebuild-ready, exclusion diagnostic-only",
        detail="This proposal must not treat ES 2026 as training-ready or excluded.",
    )
    _check(
        checks,
        name="drilldown_evidence_supports_p1_review",
        passed=(
            drilldown.get("raw_read_status") == "PASS"
            and _as_int(work_order.get("statistics_enrichment_missing_rows")) > 0
            and _as_int(work_order.get("statistics_enrichment_stale_rows")) > 0
            and _as_int(work_order.get("degraded_bar_rows")) > 0
        ),
        observed={
            "raw_read_status": drilldown.get("raw_read_status"),
            "statistics_enrichment_missing_rows": work_order.get("statistics_enrichment_missing_rows"),
            "statistics_enrichment_stale_rows": work_order.get("statistics_enrichment_stale_rows"),
            "degraded_bar_rows": work_order.get("degraded_bar_rows"),
        },
        expected="readable raw plus nonzero statistics-enrichment and degraded-quality evidence",
        detail="The P1 proposal should be grounded in the generated ES 2026 evidence.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must remain unstaged while proposing repairs.",
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
    proposal_items = [] if failures else _proposal_items(work_order, drilldown)
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_PROPOSAL_ONLY,
            "input_work_order_report": rel(work_order_report, repo_root),
            "input_drilldown_report": rel(drilldown_report, repo_root),
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "proposal_item_count": len(proposal_items),
            "p1_work_order_count": 0 if failures else 1,
            "p0_starter_batch_count": _as_int(p0_batch.get("batch_size")),
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **approval_flags,
        },
        "checks": checks,
        "proposal_items": proposal_items,
        "source_evidence": {
            "work_order": {
                "status": work_order_payload.get("status"),
                "work_order_count": work_order_payload.get("work_order_count"),
                "priority": work_order.get("priority"),
                "actions": _actions(work_order),
            },
            "drilldown": {
                "status": drilldown_payload.get("status"),
                "selected_market_year_count": drilldown_payload.get("selected_market_year_count"),
                "raw_read_status": drilldown.get("raw_read_status"),
                "raw_path": drilldown.get("raw_path"),
            },
        },
        "non_approval": {
            "scope": "ES 2026 P1 repair proposal only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **approval_flags,
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-order-report", default=str(DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--drilldown-report", default=str(DEFAULT_DRILLDOWN_REPORT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            work_order_report=resolve_path(repo_root, args.work_order_report),
            drilldown_report=resolve_path(repo_root, args.drilldown_report),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"proposal_items={summary['proposal_item_count']} "
        f"p1_work_orders={summary['p1_work_order_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
