#!/usr/bin/env python3
"""Run the approved ES 2026 P1 accepted-warning criteria review."""

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

from scripts.phase2_causal_base import build_causal_base_data as phase2_causal_base  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_repair_diagnostic as repair_diagnostic  # noqa: E402


STAGE = "local_trade_es2026_p1_accepted_warning_criteria_review"
STATUS_READY = "REVIEW_READY_ES2026_P1_ACCEPTED_WARNING_CRITERIA_REVIEW"
STATUS_NO_GO = "NO_GO_ES2026_P1_ACCEPTED_WARNING_CRITERIA_REVIEW"
DECISION_REVIEW_ONLY = "human_approved_es2026_p1_accepted_warning_criteria_review_only"
DECISION_BLOCKED = "es2026_p1_accepted_warning_criteria_review_blocked"

TARGET_MARKET = repair_diagnostic.TARGET_MARKET
TARGET_YEAR = repair_diagnostic.TARGET_YEAR
TARGET_PROFILE = repair_diagnostic.TARGET_PROFILE
EXPECTED_STATISTICS_ISSUE_ROWS = 6
EXPECTED_STATUS_ISSUE_ROWS = 0
EXPECTED_DEGRADED_ROWS = 0

DEFAULT_INPUT_DIAGNOSTIC = repair_diagnostic.DEFAULT_OUTPUT_JSON
DEFAULT_OUTPUT_ROOT = repair_diagnostic.DEFAULT_REPAIR_REPORTS_ROOT / "accepted_warning_review"
DEFAULT_OUTPUT_JSON = DEFAULT_OUTPUT_ROOT / "ES_2026_accepted_warning_criteria_review.json"
DEFAULT_OUTPUT_MD = DEFAULT_OUTPUT_ROOT / "ES_2026_accepted_warning_criteria_review.md"

CRITERIA_MET = "MET"
CRITERIA_NOT_MET = "NOT_MET"
CRITERIA_STATUS_PACKET_NOT_READY = "ACCEPTED_WARNING_PACKET_NOT_READY"
RECOMMENDED_PATH = "readiness_warning_evidence_or_statistics_repair_required"
STATISTICS_EXCEPTION_CATEGORY = "statistics_enrichment_sparse"

FALSE_APPROVAL_FLAGS = repair_diagnostic.FALSE_APPROVAL_FLAGS
FORBIDDEN_ACTIONS = (
    "accepted_warning_packet_write",
    "readiness_rerun",
    "data_mutation",
    "candidate_raw_rewrite",
    "es2026_exclusion",
    "causal_base_build",
    "labels_or_features",
    "wfa_or_modeling",
    "proof_scan",
    "staging_commit_push",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return repair_diagnostic.rel(path, repo_root)


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


def _normalize_artifact_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _filter_ignored_expected_paths(expected_paths: Iterable[str], ignored_paths: Iterable[str]) -> list[str]:
    ignored = {_normalize_artifact_path(path) for path in ignored_paths}
    return sorted(path for path in expected_paths if _normalize_artifact_path(path) in ignored)


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


def _git_ignored_generated_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    candidates = sorted({str(path) for path in paths if str(path)})
    if not candidates:
        return []
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=repo_root,
        input=("\n".join(candidates) + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "git check-ignore failed")
    stdout = result.stdout.decode("utf-8", errors="replace")
    return sorted(line.strip() for line in stdout.splitlines() if line.strip())


def _path_under(repo_root: Path, path: Path, prefix: str) -> bool:
    try:
        path.resolve().relative_to((repo_root / prefix).resolve())
    except ValueError:
        return False
    return True


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


def _criterion(
    *,
    name: str,
    met: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": CRITERIA_MET if met else CRITERIA_NOT_MET,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }


def _read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing JSON: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - parse detail varies.
        return {}, f"unreadable JSON: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"JSON is not an object: {path.as_posix()}"
    return payload, None


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _planned_outputs(repo_root: Path, output_json: Path, output_md: Path) -> list[str]:
    return [rel(output_json, repo_root), rel(output_md, repo_root)]


def _accepted_categories() -> list[str]:
    return sorted(str(category) for category in phase2_causal_base.ACCEPTED_READINESS_EXCEPTION_CATEGORIES)


def _diagnostic_summary(diagnostic: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = diagnostic.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _candidate_metrics(diagnostic: Mapping[str, Any]) -> Mapping[str, Any]:
    metrics = diagnostic.get("candidate_raw_metrics")
    return metrics if isinstance(metrics, Mapping) else {}


def _optional_summary(diagnostic: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = diagnostic.get("optional_schema_audit_summary")
    return summary if isinstance(summary, Mapping) else {}


def _conversion_summary(diagnostic: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = diagnostic.get("conversion_summary")
    return summary if isinstance(summary, Mapping) else {}


def _criteria(diagnostic: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = _diagnostic_summary(diagnostic)
    metrics = _candidate_metrics(diagnostic)
    optional = _optional_summary(diagnostic)
    conversion = _conversion_summary(diagnostic)
    categories = _accepted_categories()
    sample_timestamps = _as_list(metrics.get("statistics_issue_sample_timestamps"))
    optional_stats = optional.get("statistics_metrics")
    if not isinstance(optional_stats, Mapping):
        optional_stats = {}
    optional_status = optional.get("status_metrics")
    if not isinstance(optional_status, Mapping):
        optional_status = {}
    return [
        _criterion(
            name="exact_statistics_issue_rows_identified",
            met=_as_int(metrics.get("statistics_issue_rows")) == EXPECTED_STATISTICS_ISSUE_ROWS
            and len(sample_timestamps) == EXPECTED_STATISTICS_ISSUE_ROWS,
            observed={
                "statistics_issue_rows": metrics.get("statistics_issue_rows"),
                "sample_timestamps": sample_timestamps,
            },
            expected={
                "statistics_issue_rows": EXPECTED_STATISTICS_ISSUE_ROWS,
                "sample_timestamp_count": EXPECTED_STATISTICS_ISSUE_ROWS,
            },
            detail="The review is limited to the six statistics enrichment rows identified by the repair diagnostic.",
        ),
        _criterion(
            name="no_candidate_raw_degraded_or_status_issue_rows",
            met=_as_int(metrics.get("data_quality_degraded_or_unavailable_rows")) == EXPECTED_DEGRADED_ROWS
            and _as_int(metrics.get("status_issue_rows")) == EXPECTED_STATUS_ISSUE_ROWS,
            observed={
                "degraded_or_unavailable_rows": metrics.get("data_quality_degraded_or_unavailable_rows"),
                "status_issue_rows": metrics.get("status_issue_rows"),
            },
            expected={
                "degraded_or_unavailable_rows": EXPECTED_DEGRADED_ROWS,
                "status_issue_rows": EXPECTED_STATUS_ISSUE_ROWS,
            },
            detail="Accepted-warning criteria cannot mask degraded raw quality or status enrichment gaps.",
        ),
        _criterion(
            name="optional_audit_confirms_statistics_gap_only",
            met=optional.get("status") == "PASS"
            and _as_int(optional_stats.get("statistics_missing_rows")) == EXPECTED_STATISTICS_ISSUE_ROWS
            and _as_int(optional_stats.get("statistics_stale_rows")) == EXPECTED_STATISTICS_ISSUE_ROWS
            and _as_int(optional_status.get("status_missing_rows")) == 0
            and _as_int(optional_status.get("status_stale_rows")) == 0,
            observed={
                "optional_audit_status": optional.get("status"),
                "statistics_metrics": optional_stats,
                "status_metrics": optional_status,
            },
            expected="PASS optional audit with exactly six missing/stale statistics rows and zero status gaps",
            detail="Primary optional-schema audit evidence must agree with the candidate raw scan.",
        ),
        _criterion(
            name="candidate_conversion_preserved_required_optional_schemas",
            met=conversion.get("status") == "ok"
            and conversion.get("optional_schema_policy") == "require",
            observed={
                "conversion_status": conversion.get("status"),
                "optional_schema_policy": conversion.get("optional_schema_policy"),
            },
            expected={"conversion_status": "ok", "optional_schema_policy": "require"},
            detail="The warning review must start from the existing required-status/statistics candidate conversion.",
        ),
        _criterion(
            name="current_phase2_exception_schema_supports_statistics_warning",
            met=STATISTICS_EXCEPTION_CATEGORY in categories,
            observed=categories,
            expected=f"{STATISTICS_EXCEPTION_CATEGORY} present",
            detail=(
                "Current Phase 2 accepted-readiness exceptions do not support a statistics-enrichment-only "
                "category, so an accepted-warning packet should not be approved yet."
            ),
        ),
        _criterion(
            name="exact_phase2_statistics_warning_available",
            met=False,
            observed={
                "repair_diagnostic_status": summary.get("status"),
                "repair_diagnostic_disposition": summary.get("recommended_disposition"),
                "readiness_rerun_approved": False,
            },
            expected="separately approved readiness evidence with exact current warning strings",
            detail=(
                "This criteria review is forbidden from rerunning readiness, and the existing no-go stopped "
                "before raw-alignment/readiness outputs. Exact current Phase 2 warning strings are therefore "
                "not available for a packet."
            ),
        ),
    ]


def _criteria_summary(criteria: list[Mapping[str, Any]]) -> dict[str, Any]:
    unmet = [item for item in criteria if item.get("status") != CRITERIA_MET]
    unmet_names = {str(item.get("name")) for item in unmet}
    if "current_phase2_exception_schema_supports_statistics_warning" in unmet_names:
        reason = (
            "The six statistics rows are isolated in candidate raw evidence, but current Phase 2 exception "
            "schema lacks statistics-only support and exact current readiness warning strings are unavailable."
        )
    elif "exact_phase2_statistics_warning_available" in unmet_names:
        reason = (
            "Phase 2 now supports statistics-only warning criteria, but exact current readiness warning "
            "strings are unavailable because this review is forbidden from rerunning readiness."
        )
    elif unmet:
        reason = "One or more accepted-warning criteria are not met; see criteria details."
    else:
        reason = "All criteria are met for a separate accepted-warning packet approval decision."
    return {
        "criteria_status": CRITERIA_STATUS_PACKET_NOT_READY if unmet else "ACCEPTED_WARNING_PACKET_REVIEW_READY",
        "criteria_met_count": len(criteria) - len(unmet),
        "criteria_not_met_count": len(unmet),
        "accepted_warning_packet_should_be_separately_approved": not unmet,
        "further_statistics_repair_needed": bool(unmet),
        "es2026_remains_fail_closed": True,
        "recommended_path": RECOMMENDED_PATH if unmet else "separate_accepted_warning_packet_approval_review",
        "reason": reason,
    }


def _recommended_next(status: str, criteria_summary: Mapping[str, Any] | None = None) -> str:
    if status == STATUS_NO_GO:
        return "Fix missing or invalid ES 2026 accepted-warning review preconditions, then rerun this review."
    if (criteria_summary or {}).get("accepted_warning_packet_should_be_separately_approved") is True:
        return "Approve or reject a separate bounded accepted-warning packet write; keep ES 2026 fail-closed until then."
    return (
        "Approve either a bounded readiness-warning evidence refresh or further ES 2026 statistics repair; "
        "keep ES 2026 fail-closed."
    )


def build_report(
    *,
    repo_root: Path,
    input_diagnostic: Path,
    output_json: Path,
    output_md: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
    reports_written: bool = False,
) -> dict[str, Any]:
    diagnostic, diagnostic_error = _read_json(input_diagnostic)
    summary = _diagnostic_summary(diagnostic)
    metrics = _candidate_metrics(diagnostic)
    planned_outputs = _planned_outputs(repo_root, output_json, output_md)
    ignored_outputs = (
        _filter_ignored_expected_paths(planned_outputs, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _git_ignored_generated_paths(repo_root, planned_outputs)
    )
    unignored_outputs = sorted(set(planned_outputs) - set(ignored_outputs))
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="repair_diagnostic_readable",
        passed=diagnostic_error is None,
        observed=diagnostic_error,
        expected="readable JSON object",
        detail="Accepted-warning criteria review must start from the repair-path diagnostic.",
    )
    _check(
        checks,
        name="repair_diagnostic_ready_for_accepted_warning_review",
        passed=summary.get("status") == repair_diagnostic.STATUS_READY
        and summary.get("recommended_disposition") == repair_diagnostic.DISPOSITION_ACCEPTED_WARNING_REVIEW,
        observed={
            "status": summary.get("status"),
            "recommended_disposition": summary.get("recommended_disposition"),
        },
        expected={
            "status": repair_diagnostic.STATUS_READY,
            "recommended_disposition": repair_diagnostic.DISPOSITION_ACCEPTED_WARNING_REVIEW,
        },
        detail="This review is only valid after the repair diagnostic recommends accepted-warning review.",
    )
    _check(
        checks,
        name="exact_es2026_scope",
        passed=summary.get("profile") == TARGET_PROFILE
        and summary.get("market") == TARGET_MARKET
        and _as_int(summary.get("year")) == TARGET_YEAR,
        observed={
            "profile": summary.get("profile"),
            "market": summary.get("market"),
            "year": summary.get("year"),
        },
        expected={"profile": TARGET_PROFILE, "market": TARGET_MARKET, "year": TARGET_YEAR},
        detail="The approved review is scoped exactly to ES 2026 / tier_3_forward.",
    )
    _check(
        checks,
        name="limited_to_six_statistics_rows",
        passed=_as_int(metrics.get("statistics_issue_rows")) == EXPECTED_STATISTICS_ISSUE_ROWS
        and _as_int(metrics.get("status_issue_rows")) == 0
        and _as_int(metrics.get("data_quality_degraded_or_unavailable_rows")) == 0,
        observed={
            "statistics_issue_rows": metrics.get("statistics_issue_rows"),
            "status_issue_rows": metrics.get("status_issue_rows"),
            "data_quality_degraded_or_unavailable_rows": metrics.get("data_quality_degraded_or_unavailable_rows"),
        },
        expected={
            "statistics_issue_rows": EXPECTED_STATISTICS_ISSUE_ROWS,
            "status_issue_rows": 0,
            "data_quality_degraded_or_unavailable_rows": 0,
        },
        detail="The run-specific approval is limited to the six statistics enrichment rows.",
    )
    _check(
        checks,
        name="output_paths_under_reports",
        passed=_path_under(repo_root, output_json, "reports") and _path_under(repo_root, output_md, "reports"),
        observed=planned_outputs,
        expected="reports/**",
        detail="Accepted-warning criteria outputs must be ignored review reports only.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_outputs and len(ignored_outputs) == len(planned_outputs),
        observed=unignored_outputs,
        expected=[],
        detail="Accepted-warning criteria review outputs must be ignored generated artifacts.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    criteria = [] if failures else _criteria(diagnostic)
    criteria_summary = {} if failures else _criteria_summary(criteria)
    generated_outputs = planned_outputs if reports_written and not failures else []
    approval_flags = _approval_flags()
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_REVIEW_ONLY,
            "profile": TARGET_PROFILE,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "input_diagnostic": rel(input_diagnostic, repo_root),
            "planned_generated_output_count": len(planned_outputs),
            "ignored_planned_generated_output_count": len(ignored_outputs),
            "unignored_planned_generated_output_count": len(unignored_outputs),
            "generated_report_written": bool(generated_outputs),
            "generated_output_count": len(generated_outputs),
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "criteria_status": criteria_summary.get("criteria_status"),
            "recommended_path": criteria_summary.get("recommended_path"),
            "accepted_warning_packet_should_be_separately_approved": bool(
                criteria_summary.get("accepted_warning_packet_should_be_separately_approved")
            ),
            "further_statistics_repair_needed": bool(
                criteria_summary.get("further_statistics_repair_needed")
            ),
            "es2026_remains_fail_closed": True,
            "recommended_next_action": _recommended_next(status, criteria_summary),
            **approval_flags,
        },
        "checks": checks,
        "criteria": criteria,
        "criteria_summary": criteria_summary,
        "planned_generated_outputs": planned_outputs,
        "generated_outputs": generated_outputs,
        "input_evidence": {
            "repair_diagnostic_summary": dict(summary),
            "candidate_raw_metrics": dict(metrics),
            "accepted_readiness_exception_categories": _accepted_categories(),
        },
        "non_approval": {
            "scope": "ES 2026 accepted-warning criteria review only",
            "accepted_warning_packet_written": False,
            "readiness_rerun": False,
            "data_written": False,
            "candidate_raw_rewritten": False,
            "exclusion": False,
            "causal_base_build": False,
            "labels_features_wfa_modeling": False,
            "proof_scan": False,
            **approval_flags,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    if not isinstance(summary, Mapping):
        summary = {}
    criteria_summary = report.get("criteria_summary", {})
    if not isinstance(criteria_summary, Mapping):
        criteria_summary = {}
    lines = [
        "# ES 2026 Accepted-Warning Criteria Review",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Scope: `{summary.get('profile')}` `{summary.get('market')} {summary.get('year')}`",
        f"- Criteria status: `{summary.get('criteria_status')}`",
        f"- Accepted-warning packet approval recommended: `{summary.get('accepted_warning_packet_should_be_separately_approved')}`",
        f"- Further statistics repair needed: `{summary.get('further_statistics_repair_needed')}`",
        f"- ES 2026 remains fail-closed: `{summary.get('es2026_remains_fail_closed')}`",
        "",
        "## Reason",
        "",
        str(criteria_summary.get("reason") or "Preconditions failed; see JSON checks."),
        "",
        "## Next",
        "",
        str(summary.get("recommended_next_action")),
        "",
        "## Forbidden",
        "",
    ]
    for action in FORBIDDEN_ACTIONS:
        lines.append(f"- `{action}`")
    lines.append("")
    return "\n".join(lines)


def write_report_files(report: dict[str, Any], *, output_json: Path, output_md: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--input-diagnostic", default=str(DEFAULT_INPUT_DIAGNOSTIC))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    output_json = resolve_path(repo_root, args.output_json)
    output_md = resolve_path(repo_root, args.output_md)
    try:
        report = build_report(
            repo_root=repo_root,
            input_diagnostic=resolve_path(repo_root, args.input_diagnostic),
            output_json=output_json,
            output_md=output_md,
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1

    summary = report["summary"]
    if summary["status"] == STATUS_READY:
        report["summary"]["generated_report_written"] = True
        report["summary"]["generated_output_count"] = len(report["planned_generated_outputs"])
        report["generated_outputs"] = list(report["planned_generated_outputs"])
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output_md.write_text(render_markdown(report), encoding="utf-8")
        post_staged_paths = _git_staged_generated_paths(repo_root)
        report["summary"]["post_execution_staged_generated_path_count"] = len(post_staged_paths)
        if post_staged_paths:
            report["summary"]["status"] = STATUS_NO_GO
            report["summary"]["failure_count"] = int(report["summary"]["failure_count"]) + 1
            report["checks"].append(
                {
                    "name": "post_execution_staged_generated_artifacts_absent",
                    "status": "FAIL",
                    "observed": post_staged_paths,
                    "expected": [],
                    "detail": "Generated data/** and reports/** artifacts must remain unstaged after review.",
                }
            )
        write_report_files(report, output_json=output_json, output_md=output_md)
    else:
        report["summary"]["post_execution_staged_generated_path_count"] = 0

    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"criteria_status={summary['criteria_status']} "
        f"packet_approval_recommended={summary['accepted_warning_packet_should_be_separately_approved']} "
        f"planned_generated_outputs={summary['planned_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"post_execution_staged_generated_paths={summary['post_execution_staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
