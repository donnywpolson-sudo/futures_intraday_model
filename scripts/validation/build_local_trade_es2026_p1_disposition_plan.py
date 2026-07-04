#!/usr/bin/env python3
"""Build a console-only ES 2026 P1 fail-closed disposition plan."""

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

from scripts.validation import build_local_trade_es2026_p1_blocker_proposal as blocker_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_review as readiness_review  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_workflow_status as workflow_status  # noqa: E402
from scripts.validation import build_local_trade_optional_archive_inventory as optional_inventory_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_disposition_plan"
STATUS_READY = "REVIEW_READY_ES2026_P1_DISPOSITION_PLAN"
STATUS_NO_GO = "NO_GO_ES2026_P1_DISPOSITION_PLAN"
DECISION_PLAN_ONLY = "es2026_p1_disposition_plan_only_no_execution"
DECISION_BLOCKED = "es2026_p1_disposition_plan_blocked"

TARGET_MARKET = blocker_gate.TARGET_MARKET
TARGET_YEAR = blocker_gate.TARGET_YEAR
TARGET_PROFILE = blocker_gate.TARGET_PROFILE
DEFAULT_REPAIR_REPORTS_ROOT = blocker_gate.DEFAULT_REPAIR_REPORTS_ROOT
DEFAULT_RAW_QUALITY_REPORT = blocker_gate.DEFAULT_RAW_QUALITY_REPORT
DEFAULT_OPTIONAL_DBN_ROOT = blocker_gate.DEFAULT_OPTIONAL_DBN_ROOT
FALSE_APPROVAL_FLAGS = repair_plan_gate.FALSE_APPROVAL_FLAGS
PREFERRED_OPTION = "repair_path"
DISPOSITION_OPTIONS = (
    "repair_path",
    "accepted_warning_policy",
    "es2026_exclusion",
)

PLAN_ARTIFACTS = (
    "scripts/validation/build_local_trade_es2026_p1_disposition_plan.py",
    "tests/validation/test_build_local_trade_es2026_p1_disposition_plan.py",
    "PROJECT_OUTLINE.md",
    "CODEX_HANDOFF.md",
)

FORBIDDEN_WITHOUT_APPROVAL = (
    "readiness_rerun",
    "provider_download_or_cost_diagnostic",
    "data_or_report_mutation",
    "causal_base_repair_or_build",
    "accepted_warning_packet",
    "es2026_exclusion",
    "labels_or_features",
    "wfa_or_modeling",
    "proof_scan",
    "staging_commit_push",
    "live_or_paper_execution",
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


def _source_evidence(report: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    evidence = report.get("source_evidence")
    if not isinstance(evidence, Mapping):
        return {}
    value = evidence.get(key)
    return value if isinstance(value, Mapping) else {}


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


def _current_blocker(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "top_blocker_reason": str(row.get("top_blocker_reason") or ""),
        "degraded_bar_rows": _as_int(row.get("degraded_bar_rows")),
        "degraded_rows_pct": _as_float(row.get("degraded_rows_pct")),
        "degraded_session_rows": _as_int(row.get("degraded_session_rows")),
        "statistics_enrichment_missing_rows": _as_int(
            row.get("statistics_enrichment_missing_rows")
        ),
        "statistics_enrichment_stale_rows": _as_int(row.get("statistics_enrichment_stale_rows")),
    }


def _bounded_next_step_plan(*, raw_quality_report: Path, repo_root: Path) -> dict[str, Any]:
    forbidden_patterns = list(
        dict.fromkeys(
            [
                *repair_plan_gate.FORBIDDEN_PATTERNS,
                "readiness_rerun_without_separate_approval",
                "provider_cost_diagnostic_without_separate_approval",
                "accepted_warning_policy_without_separate_approval",
                "es2026_exclusion_without_separate_approval",
            ]
        )
    )
    return {
        "disposition_path": "source_tests_docs_only_disposition_plan_gate",
        "command_family": "source_tests_docs_only_disposition_plan_gate",
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
        "forbidden_patterns": forbidden_patterns,
        "required_evidence": [
            "blocker proposal is REVIEW_READY",
            "workflow status is NO_GO at candidate_readiness_execution",
            "candidate readiness review is NO_GO",
            "optional status/statistics inventory is REVIEW_READY",
            "raw-quality drilldown is FAIL for exactly ES 2026 with degraded threshold evidence",
            "git staged generated data/reports paths are empty",
        ],
        "stop_condition": (
            "Stop when this console-only gate reports REVIEW_READY with exactly three disposition "
            "options and one recommended next action; do not execute repairs, readiness reruns, "
            "accepted-warning policy, exclusions, labels/features, WFA/modeling, proof scans, "
            "provider actions, staging, commits, or pushes."
        ),
    }


def _disposition_options(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    blocker = _current_blocker(row)
    return [
        {
            "option": "repair_path",
            "option_status": "CRITERIA_READY_NOT_APPROVED",
            "recommendation": "PREFERRED_DEFAULT",
            "approval_state": "requires_separate_bounded_approval",
            "current_blocker": blocker,
            "required_evidence_before_execution": [
                "degraded raw-quality review explains or resolves breached threshold evidence",
                "status/statistics enrichment evidence is repaired or refreshed for exact ES 2026 scope",
                "candidate raw-alignment and readiness-only rerun plan remains bounded to ES 2026",
                "generated data/reports artifacts are ignored and unstaged",
            ],
            "minimum_stop_condition": (
                "Do not rerun readiness until degraded raw-quality and status/statistics evidence "
                "are repaired or explicitly dispositioned in a separate approval."
            ),
            "forbidden_without_separate_approval": list(FORBIDDEN_WITHOUT_APPROVAL),
        },
        {
            "option": "accepted_warning_policy",
            "option_status": "CRITERIA_ONLY_NOT_ACCEPTED",
            "recommendation": "NOT_PREFERRED_WITHOUT_PRIMARY_EVIDENCE",
            "approval_state": "requires_separate_bounded_approval",
            "current_blocker": blocker,
            "required_evidence_before_execution": [
                "primary evidence shows degraded rows are acceptable for research validity",
                "no leakage, timestamp-alignment, session-normalization, or validation-window risk is introduced",
                "accepted-warning criteria are documented before any packet is created",
                "downstream baseline/readiness reporting preserves the warning and failure mode",
            ],
            "minimum_stop_condition": (
                "Do not create an accepted-warning packet unless primary evidence justifies the "
                "degraded-row exception and the policy is separately approved."
            ),
            "forbidden_without_separate_approval": list(FORBIDDEN_WITHOUT_APPROVAL),
        },
        {
            "option": "es2026_exclusion",
            "option_status": "DIAGNOSTIC_ONLY_NOT_EXCLUDED",
            "recommendation": "LAST_RESORT_REQUIRES_SCOPE_DECISION",
            "approval_state": "requires_separate_bounded_approval",
            "current_blocker": blocker,
            "required_evidence_before_execution": [
                "documented impact on model-eligible scope and proof-status accounting",
                "reason ES 2026 cannot be repaired or accepted as warning-only",
                "explicit universe/scope decision before any label, feature, WFA, or proof work",
                "handoff and outline record the exclusion as a research-scope decision, not a hidden pass",
            ],
            "minimum_stop_condition": (
                "Do not exclude ES 2026 to make readiness pass unless a separate scope-change "
                "approval documents proof-status and model-eligible impact."
            ),
            "forbidden_without_separate_approval": list(FORBIDDEN_WITHOUT_APPROVAL),
        },
    ]


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 disposition-plan preconditions, then rerun this console-only gate."
    return (
        "Review the ES 2026 disposition plan and explicitly approve exactly one bounded path: "
        "repair_path, accepted_warning_policy, or es2026_exclusion. Default recommendation is repair_path."
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
    blocker_proposal_report: Mapping[str, Any] | None = None,
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
        "raw_quality_report": raw_quality_report,
        "optional_dbn_root": optional_dbn_root,
        "generated_at_utc": generated_at_utc,
        "staged_generated_paths": staged_paths,
    }
    if ignored_generated_paths is not None:
        common_kwargs["ignored_generated_paths"] = ignored_generated_paths

    blocker_report = blocker_proposal_report or blocker_gate.build_report(**common_kwargs)
    blocker_summary = _summary(blocker_report)
    workflow_evidence = _source_evidence(blocker_report, "workflow_status")
    readiness_evidence = _source_evidence(blocker_report, "candidate_readiness_review")
    optional_evidence = _source_evidence(blocker_report, "optional_archive_inventory")
    raw_quality_payload, raw_quality_error = _read_json_object(raw_quality_report)
    raw_quality = _raw_quality_row(raw_quality_payload)
    top_blocker_reason = str(raw_quality.get("top_blocker_reason") or "")

    draft_options = _disposition_options(raw_quality)
    bounded_plan = _bounded_next_step_plan(raw_quality_report=raw_quality_report, repo_root=repo_root)
    option_names = [str(option.get("option")) for option in draft_options]
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="blocker_proposal_ready",
        passed=(
            blocker_summary.get("status") == blocker_gate.STATUS_READY
            and _as_int(blocker_summary.get("proposal_item_count")) == 1
            and _as_int(blocker_summary.get("generated_output_count")) == 0
        ),
        observed={
            "status": blocker_summary.get("status"),
            "proposal_item_count": blocker_summary.get("proposal_item_count"),
            "generated_output_count": blocker_summary.get("generated_output_count"),
        },
        expected="REVIEW_READY blocker proposal with one item and zero generated outputs",
        detail="Disposition planning must start from the current review-ready blocker proposal.",
    )
    _check(
        checks,
        name="blocker_scope_exact_es2026",
        passed=(
            str(blocker_summary.get("market")) == TARGET_MARKET
            and _as_int(blocker_summary.get("year")) == TARGET_YEAR
            and str(blocker_summary.get("profile")) == TARGET_PROFILE
        ),
        observed={
            "market": blocker_summary.get("market"),
            "year": blocker_summary.get("year"),
            "profile": blocker_summary.get("profile"),
        },
        expected={"market": TARGET_MARKET, "year": TARGET_YEAR, "profile": TARGET_PROFILE},
        detail="Disposition planning must not expand beyond exact ES 2026 tier_3_forward scope.",
    )
    _check(
        checks,
        name="workflow_status_no_go_candidate_readiness",
        passed=(
            workflow_evidence.get("status") == workflow_status.STATUS_NO_GO
            and workflow_evidence.get("current_gate") == "candidate_readiness_execution"
            and workflow_evidence.get("current_gate_status")
            == "NO_GO_ES2026_P1_CANDIDATE_READINESS_EXECUTION"
        ),
        observed={
            "status": workflow_evidence.get("status"),
            "current_gate": workflow_evidence.get("current_gate"),
            "current_gate_status": workflow_evidence.get("current_gate_status"),
        },
        expected="workflow no-go at candidate_readiness_execution",
        detail="The plan must preserve the current fail-closed candidate-readiness boundary.",
    )
    _check(
        checks,
        name="candidate_readiness_review_no_go",
        passed=readiness_evidence.get("status") == readiness_review.STATUS_NO_GO,
        observed=readiness_evidence.get("status"),
        expected=readiness_review.STATUS_NO_GO,
        detail="The plan must reflect that candidate readiness evidence is not review-ready.",
    )
    _check(
        checks,
        name="optional_archive_inventory_ready",
        passed=(
            optional_evidence.get("status") == optional_inventory_gate.STATUS_READY
            and _as_int(optional_evidence.get("ready_market_count"))
            == _as_int(optional_evidence.get("expected_market_count"))
            and _as_int(optional_evidence.get("invalid_archive_count")) == 0
        ),
        observed={
            "status": optional_evidence.get("status"),
            "ready_market_count": optional_evidence.get("ready_market_count"),
            "expected_market_count": optional_evidence.get("expected_market_count"),
            "invalid_archive_count": optional_evidence.get("invalid_archive_count"),
        },
        expected="ready optional inventory with zero invalid archives",
        detail="The disposition plan should not misclassify the blocker as optional-archive absence.",
    )
    _check(
        checks,
        name="raw_quality_report_readable",
        passed=raw_quality_error is None,
        observed=raw_quality_error,
        expected="readable JSON object",
        detail="The plan must read the current ES 2026 candidate raw-quality drilldown.",
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
        detail="Raw-quality evidence must be scoped exactly to ES 2026.",
    )
    _check(
        checks,
        name="raw_quality_degraded_threshold_failure_present",
        passed=(
            raw_quality_payload.get("status") == "FAIL"
            and "degraded threshold breached" in top_blocker_reason
            and _as_int(raw_quality.get("degraded_bar_rows")) > 0
            and _as_float(raw_quality.get("degraded_rows_pct")) > 0.0
        ),
        observed={
            "status": raw_quality_payload.get("status"),
            "top_blocker_reason": top_blocker_reason,
            "degraded_bar_rows": raw_quality.get("degraded_bar_rows"),
            "degraded_rows_pct": raw_quality.get("degraded_rows_pct"),
            "degraded_session_rows": raw_quality.get("degraded_session_rows"),
        },
        expected="FAIL with degraded threshold breached evidence",
        detail="The disposition options must be grounded in the degraded-row failure.",
    )
    _check(
        checks,
        name="disposition_options_complete",
        passed=option_names == list(DISPOSITION_OPTIONS),
        observed=option_names,
        expected=list(DISPOSITION_OPTIONS),
        detail="The plan must compare repair, accepted-warning criteria, and exclusion criteria.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while planning disposition.",
    )
    _check(
        checks,
        name="disposition_plan_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally exposes no generated report output arguments.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    options = [] if failures else draft_options
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_PLAN_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "profile": TARGET_PROFILE,
            "blocker_proposal_status": blocker_summary.get("status"),
            "workflow_status": workflow_evidence.get("status"),
            "current_gate": workflow_evidence.get("current_gate"),
            "current_gate_status": workflow_evidence.get("current_gate_status"),
            "candidate_readiness_review_status": readiness_evidence.get("status"),
            "optional_archive_inventory_status": optional_evidence.get("status"),
            "raw_quality_status": raw_quality_payload.get("status"),
            "raw_quality_top_blocker_reason": top_blocker_reason,
            "recommended_option": PREFERRED_OPTION if not failures else None,
            "disposition_option_count": len(options),
            "bounded_plan_command_family": bounded_plan["command_family"],
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "disposition_options": options,
        "bounded_next_step_plan": bounded_plan if not failures else {},
        "source_evidence": {
            "blocker_proposal": {
                "status": blocker_summary.get("status"),
                "proposal_item_count": blocker_summary.get("proposal_item_count"),
                "generated_output_count": blocker_summary.get("generated_output_count"),
                "staged_generated_path_count": blocker_summary.get("staged_generated_path_count"),
            },
            "workflow_status": workflow_evidence,
            "candidate_readiness_review": readiness_evidence,
            "optional_archive_inventory": optional_evidence,
            "raw_quality_report": rel(raw_quality_report, repo_root),
        },
        "non_approval": {
            "scope": "ES 2026 P1 disposition plan only",
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
    parser.add_argument("--print-disposition-json", action="store_true")
    return parser


def disposition_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "stage": STAGE,
        "status": summary.get("status"),
        "market": summary.get("market"),
        "year": summary.get("year"),
        "profile": summary.get("profile"),
        "recommended_option": summary.get("recommended_option"),
        "disposition_option_count": summary.get("disposition_option_count"),
        "disposition_options": report.get("disposition_options", []),
        "bounded_next_step_plan": report.get("bounded_next_step_plan", {}),
        "generated_artifact_hygiene": {
            "generated_output_count": summary.get("generated_output_count"),
            "staged_generated_path_count": summary.get("staged_generated_path_count"),
        },
        "recommended_next_action": summary.get("recommended_next_action"),
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
        f"raw_quality_status={summary['raw_quality_status']} "
        f"recommended_option={summary['recommended_option']} "
        f"disposition_options={summary['disposition_option_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_disposition_json:
        print(json.dumps(disposition_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
