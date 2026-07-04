#!/usr/bin/env python3
"""Capture approved ES 2026 P1 readiness-warning evidence only."""

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


STAGE = "local_trade_es2026_p1_readiness_warning_evidence"
STATUS_READY = "REVIEW_READY_ES2026_P1_READINESS_WARNING_EVIDENCE"
STATUS_NO_GO = "NO_GO_ES2026_P1_READINESS_WARNING_EVIDENCE"
DECISION_EVIDENCE_ONLY = "human_approved_es2026_p1_readiness_warning_evidence_only"
DECISION_BLOCKED = "es2026_p1_readiness_warning_evidence_blocked"

TARGET_MARKET = repair_diagnostic.TARGET_MARKET
TARGET_YEAR = repair_diagnostic.TARGET_YEAR
TARGET_PROFILE = repair_diagnostic.TARGET_PROFILE

EXPECTED_STATISTICS_ISSUE_ROWS = 6
EXPECTED_STATUS_ISSUE_ROWS = 0
EXPECTED_DEGRADED_ROWS = 0
EXPECTED_PHASE2_STATISTICS_WARNING = (
    "statistics enrichment sparse: missing_rows=6 stale_rows=6"
)
EXPECTED_PHASE2_WARNING_LIST = [EXPECTED_PHASE2_STATISTICS_WARNING]

DEFAULT_INPUT_DIAGNOSTIC = repair_diagnostic.DEFAULT_OUTPUT_JSON
DEFAULT_CANDIDATE_RAW_PATH = repair_diagnostic.DEFAULT_CANDIDATE_RAW_PATH
DEFAULT_OUTPUT_ROOT = repair_diagnostic.DEFAULT_REPAIR_REPORTS_ROOT / "readiness_warning_evidence"
DEFAULT_OUTPUT_JSON = DEFAULT_OUTPUT_ROOT / "ES_2026_readiness_warning_evidence.json"
DEFAULT_OUTPUT_MD = DEFAULT_OUTPUT_ROOT / "ES_2026_readiness_warning_evidence.md"

EVIDENCE_PACKET_READY = "ACCEPTED_WARNING_PACKET_PREPARATION_READY"
EVIDENCE_REPAIR_REQUIRED = "ES2026_REMAINS_FAIL_CLOSED_PENDING_STATISTICS_REPAIR"
RECOMMENDED_PACKET_REVIEW = "separate_accepted_warning_packet_approval_review"
RECOMMENDED_REPAIR = "further_statistics_repair_required"

FALSE_APPROVAL_FLAGS = repair_diagnostic.FALSE_APPROVAL_FLAGS
FORBIDDEN_ACTIONS = (
    "accepted_warning_packet_write",
    "data_mutation",
    "candidate_raw_rewrite",
    "statistics_repair_execution",
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
        "status": "MET" if met else "NOT_MET",
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


def _as_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).lower() == "true"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _planned_outputs(repo_root: Path, output_json: Path, output_md: Path) -> list[str]:
    return [rel(output_json, repo_root), rel(output_md, repo_root)]


def _diagnostic_summary(diagnostic: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = diagnostic.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _candidate_metrics(diagnostic: Mapping[str, Any]) -> Mapping[str, Any]:
    metrics = diagnostic.get("candidate_raw_metrics")
    return metrics if isinstance(metrics, Mapping) else {}


def _resolved_summary_candidate_raw_path(
    repo_root: Path,
    summary: Mapping[str, Any],
    fallback: Path,
) -> Path:
    candidate = summary.get("candidate_raw_path")
    if not isinstance(candidate, str) or not candidate:
        return fallback
    return resolve_path(repo_root, candidate)


def _phase2_warning_evidence_from_result(
    result: phase2_causal_base.ValidationResult,
    *,
    repo_root: Path,
    non_written_output_path: Path,
) -> dict[str, Any]:
    return {
        "collection_error": None,
        "profile": result.profile,
        "market": result.market,
        "year": result.year,
        "input_path": result.input_path,
        "non_written_output_path": rel(non_written_output_path, repo_root),
        "write_output": False,
        "status": result.status,
        "warnings": list(result.warnings),
        "failures": list(result.failures),
        "warning_count": len(result.warnings),
        "failure_count": len(result.failures),
        "raw_rows": result.raw_rows,
        "output_rows": result.output_rows,
        "synthetic_rows": result.synthetic_rows,
        "synthetic_gap_threshold_breached": result.synthetic_gap_threshold_breached,
        "roll_window_threshold_breached": result.roll_window_threshold_breached,
        "degraded_threshold_breached": result.degraded_threshold_breached,
        "roll_maturity_backstep_count": result.roll_maturity_backstep_count,
        "degraded_bar_rows": result.degraded_bar_rows,
        "degraded_session_rows": result.degraded_session_rows,
        "status_enrichment_missing_rows": result.status_enrichment_missing_rows,
        "status_enrichment_stale_rows": result.status_enrichment_stale_rows,
        "statistics_enrichment_missing_rows": result.statistics_enrichment_missing_rows,
        "statistics_enrichment_stale_rows": result.statistics_enrichment_stale_rows,
    }


def _collect_phase2_warning_evidence(
    *,
    repo_root: Path,
    candidate_raw_path: Path,
    non_written_output_path: Path,
    profile_config_path: Path,
    session_config_path: Path,
) -> dict[str, Any]:
    try:
        result = phase2_causal_base.process_file(
            candidate_raw_path,
            non_written_output_path,
            profile=TARGET_PROFILE,
            profile_config_path=profile_config_path,
            session_config_path=session_config_path,
            write_output=False,
        )
    except Exception as exc:  # pragma: no cover - exact parquet/config errors vary.
        return {
            "collection_error": f"{type(exc).__name__}: {exc}",
            "profile": TARGET_PROFILE,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "input_path": rel(candidate_raw_path, repo_root),
            "non_written_output_path": rel(non_written_output_path, repo_root),
            "write_output": False,
            "status": "ERROR",
            "warnings": [],
            "failures": [],
            "warning_count": 0,
            "failure_count": 0,
        }
    return _phase2_warning_evidence_from_result(
        result,
        repo_root=repo_root,
        non_written_output_path=non_written_output_path,
    )


def _evidence_criteria(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    warnings = [str(item) for item in _as_list(evidence.get("warnings"))]
    failures = [str(item) for item in _as_list(evidence.get("failures"))]
    return [
        _criterion(
            name="phase2_warning_evidence_collected",
            met=not evidence.get("collection_error"),
            observed=evidence.get("collection_error"),
            expected=None,
            detail="The guarded evidence command must obtain current Phase 2 warning evidence.",
        ),
        _criterion(
            name="phase2_scope_exact_es2026_tier3_forward",
            met=evidence.get("profile") == TARGET_PROFILE
            and evidence.get("market") == TARGET_MARKET
            and _as_int(evidence.get("year")) == TARGET_YEAR,
            observed={
                "profile": evidence.get("profile"),
                "market": evidence.get("market"),
                "year": evidence.get("year"),
            },
            expected={"profile": TARGET_PROFILE, "market": TARGET_MARKET, "year": TARGET_YEAR},
            detail="The warning evidence must be exactly ES 2026 / tier_3_forward.",
        ),
        _criterion(
            name="phase2_status_warn_without_failures",
            met=evidence.get("status") == "WARN" and not failures,
            observed={"status": evidence.get("status"), "failures": failures},
            expected={"status": "WARN", "failures": []},
            detail="The accepted-warning path requires warnings only, with no Phase 2 failures.",
        ),
        _criterion(
            name="exact_current_statistics_warning_only",
            met=warnings == EXPECTED_PHASE2_WARNING_LIST,
            observed=warnings,
            expected=EXPECTED_PHASE2_WARNING_LIST,
            detail="The packet can only be prepared from the exact current statistics-only warning string.",
        ),
        _criterion(
            name="statistics_rows_are_isolated",
            met=_as_int(evidence.get("statistics_enrichment_missing_rows")) == EXPECTED_STATISTICS_ISSUE_ROWS
            and _as_int(evidence.get("statistics_enrichment_stale_rows")) == EXPECTED_STATISTICS_ISSUE_ROWS
            and _as_int(evidence.get("status_enrichment_missing_rows")) == 0
            and _as_int(evidence.get("status_enrichment_stale_rows")) == 0
            and _as_int(evidence.get("degraded_bar_rows")) == 0,
            observed={
                "statistics_enrichment_missing_rows": evidence.get("statistics_enrichment_missing_rows"),
                "statistics_enrichment_stale_rows": evidence.get("statistics_enrichment_stale_rows"),
                "status_enrichment_missing_rows": evidence.get("status_enrichment_missing_rows"),
                "status_enrichment_stale_rows": evidence.get("status_enrichment_stale_rows"),
                "degraded_bar_rows": evidence.get("degraded_bar_rows"),
            },
            expected={
                "statistics_enrichment_missing_rows": EXPECTED_STATISTICS_ISSUE_ROWS,
                "statistics_enrichment_stale_rows": EXPECTED_STATISTICS_ISSUE_ROWS,
                "status_enrichment_missing_rows": 0,
                "status_enrichment_stale_rows": 0,
                "degraded_bar_rows": 0,
            },
            detail="The refresh is limited to six isolated statistics enrichment rows.",
        ),
        _criterion(
            name="no_other_phase2_warning_contamination",
            met=not _as_bool(evidence.get("synthetic_gap_threshold_breached"))
            and not _as_bool(evidence.get("roll_window_threshold_breached"))
            and not _as_bool(evidence.get("degraded_threshold_breached"))
            and _as_int(evidence.get("roll_maturity_backstep_count")) == 0,
            observed={
                "synthetic_gap_threshold_breached": evidence.get("synthetic_gap_threshold_breached"),
                "roll_window_threshold_breached": evidence.get("roll_window_threshold_breached"),
                "degraded_threshold_breached": evidence.get("degraded_threshold_breached"),
                "roll_maturity_backstep_count": evidence.get("roll_maturity_backstep_count"),
            },
            expected={
                "synthetic_gap_threshold_breached": False,
                "roll_window_threshold_breached": False,
                "degraded_threshold_breached": False,
                "roll_maturity_backstep_count": 0,
            },
            detail="The evidence cannot include unrelated Phase 2 warning causes.",
        ),
    ]


def _evidence_summary(criteria: list[Mapping[str, Any]]) -> dict[str, Any]:
    unmet = [item for item in criteria if item.get("status") != "MET"]
    packet_ready = not unmet
    return {
        "evidence_status": EVIDENCE_PACKET_READY if packet_ready else EVIDENCE_REPAIR_REQUIRED,
        "evidence_criteria_met_count": len(criteria) - len(unmet),
        "evidence_criteria_not_met_count": len(unmet),
        "accepted_warning_packet_can_be_prepared_with_separate_approval": packet_ready,
        "accepted_warning_packet_should_be_written_now": False,
        "further_statistics_repair_needed": not packet_ready,
        "es2026_remains_fail_closed": True,
        "recommended_path": RECOMMENDED_PACKET_REVIEW if packet_ready else RECOMMENDED_REPAIR,
        "reason": (
            "Exact current Phase 2 statistics-only warning evidence is available for a separately "
            "approved accepted-warning packet."
            if packet_ready
            else "Exact current Phase 2 warning evidence does not support a packet; ES 2026 remains fail-closed pending statistics repair."
        ),
    }


def _recommended_next(status: str, evidence_summary: Mapping[str, Any] | None = None) -> str:
    if status == STATUS_NO_GO:
        return "Fix missing or invalid ES 2026 readiness-warning evidence preconditions, then rerun this evidence refresh."
    if (evidence_summary or {}).get("accepted_warning_packet_can_be_prepared_with_separate_approval") is True:
        return "Approve or reject a separate bounded accepted-warning packet write; keep ES 2026 fail-closed until then."
    return "Approve further ES 2026 statistics repair; keep ES 2026 fail-closed."


def build_report(
    *,
    repo_root: Path,
    input_diagnostic: Path,
    candidate_raw_path: Path,
    output_json: Path,
    output_md: Path,
    profile_config_path: Path = phase2_causal_base.DEFAULT_PROFILE_CONFIG,
    session_config_path: Path = phase2_causal_base.DEFAULT_SESSION_CONFIG,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
    phase2_warning_evidence: Mapping[str, Any] | None = None,
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
    summary_candidate_raw_path = _resolved_summary_candidate_raw_path(repo_root, summary, candidate_raw_path)
    sample_timestamps = _as_list(metrics.get("statistics_issue_sample_timestamps"))

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="repair_diagnostic_readable",
        passed=diagnostic_error is None,
        observed=diagnostic_error,
        expected="readable JSON object",
        detail="Readiness-warning evidence must start from the repair-path diagnostic.",
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
        detail="This refresh is only valid after the repair diagnostic recommends accepted-warning review.",
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
        detail="The approved refresh is scoped exactly to ES 2026 / tier_3_forward.",
    )
    _check(
        checks,
        name="candidate_raw_path_matches_diagnostic",
        passed=summary_candidate_raw_path.resolve() == candidate_raw_path.resolve()
        and candidate_raw_path.exists(),
        observed={
            "diagnostic_candidate_raw_path": rel(summary_candidate_raw_path, repo_root),
            "candidate_raw_path": rel(candidate_raw_path, repo_root),
            "candidate_raw_exists": candidate_raw_path.exists(),
        },
        expected={
            "diagnostic_candidate_raw_path": rel(candidate_raw_path, repo_root),
            "candidate_raw_exists": True,
        },
        detail="The warning evidence must inspect the exact candidate raw file from the diagnostic.",
    )
    _check(
        checks,
        name="limited_to_six_statistics_rows",
        passed=_as_int(metrics.get("statistics_issue_rows")) == EXPECTED_STATISTICS_ISSUE_ROWS
        and len(sample_timestamps) == EXPECTED_STATISTICS_ISSUE_ROWS
        and _as_int(metrics.get("status_issue_rows")) == EXPECTED_STATUS_ISSUE_ROWS
        and _as_int(metrics.get("data_quality_degraded_or_unavailable_rows")) == EXPECTED_DEGRADED_ROWS,
        observed={
            "statistics_issue_rows": metrics.get("statistics_issue_rows"),
            "statistics_issue_sample_timestamp_count": len(sample_timestamps),
            "status_issue_rows": metrics.get("status_issue_rows"),
            "data_quality_degraded_or_unavailable_rows": metrics.get("data_quality_degraded_or_unavailable_rows"),
        },
        expected={
            "statistics_issue_rows": EXPECTED_STATISTICS_ISSUE_ROWS,
            "statistics_issue_sample_timestamp_count": EXPECTED_STATISTICS_ISSUE_ROWS,
            "status_issue_rows": EXPECTED_STATUS_ISSUE_ROWS,
            "data_quality_degraded_or_unavailable_rows": EXPECTED_DEGRADED_ROWS,
        },
        detail="The run-specific approval is limited to the six isolated statistics enrichment rows.",
    )
    _check(
        checks,
        name="output_paths_under_reports",
        passed=_path_under(repo_root, output_json, "reports") and _path_under(repo_root, output_md, "reports"),
        observed=planned_outputs,
        expected="reports/**",
        detail="Readiness-warning evidence outputs must be ignored review reports only.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_outputs and len(ignored_outputs) == len(planned_outputs),
        observed=unignored_outputs,
        expected=[],
        detail="Readiness-warning evidence outputs must be ignored generated artifacts.",
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
    non_written_output_path = output_json.parent / "non_written_causal_base" / TARGET_MARKET / f"{TARGET_YEAR}.parquet"
    if failures:
        evidence: Mapping[str, Any] = {
            "collection_error": "preconditions failed; Phase 2 warning evidence not collected",
            "profile": TARGET_PROFILE,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "input_path": rel(candidate_raw_path, repo_root),
            "non_written_output_path": rel(non_written_output_path, repo_root),
            "write_output": False,
            "status": "NOT_RUN",
            "warnings": [],
            "failures": [],
        }
    elif phase2_warning_evidence is not None:
        evidence = dict(phase2_warning_evidence)
    else:
        evidence = _collect_phase2_warning_evidence(
            repo_root=repo_root,
            candidate_raw_path=candidate_raw_path,
            non_written_output_path=non_written_output_path,
            profile_config_path=profile_config_path,
            session_config_path=session_config_path,
        )

    evidence_criteria = _evidence_criteria(evidence)
    evidence_summary = _evidence_summary(evidence_criteria)
    generated_outputs = planned_outputs if reports_written and not failures else []
    approval_flags = _approval_flags()
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_EVIDENCE_ONLY,
            "profile": TARGET_PROFILE,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "input_diagnostic": rel(input_diagnostic, repo_root),
            "candidate_raw_path": rel(candidate_raw_path, repo_root),
            "profile_config_path": rel(profile_config_path, repo_root),
            "session_config_path": rel(session_config_path, repo_root),
            "planned_generated_output_count": len(planned_outputs),
            "ignored_planned_generated_output_count": len(ignored_outputs),
            "unignored_planned_generated_output_count": len(unignored_outputs),
            "generated_report_written": bool(generated_outputs),
            "generated_output_count": len(generated_outputs),
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status, evidence_summary),
            **evidence_summary,
            **approval_flags,
        },
        "checks": checks,
        "evidence_criteria": evidence_criteria,
        "planned_generated_outputs": planned_outputs,
        "generated_outputs": generated_outputs,
        "repair_diagnostic_evidence": {
            "status": summary.get("status"),
            "recommended_disposition": summary.get("recommended_disposition"),
            "statistics_issue_rows": metrics.get("statistics_issue_rows"),
            "statistics_issue_sample_timestamps": sample_timestamps,
            "status_issue_rows": metrics.get("status_issue_rows"),
            "data_quality_degraded_or_unavailable_rows": metrics.get(
                "data_quality_degraded_or_unavailable_rows"
            ),
        },
        "phase2_warning_evidence": evidence,
        "non_approval": {
            "scope": "ES 2026 / tier_3_forward readiness-warning evidence only",
            "data_written": False,
            "candidate_raw_rewritten": False,
            "readiness_rerun": False,
            "accepted_warning_packet_written": False,
            "statistics_repair_executed": False,
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
    phase2_evidence = report.get("phase2_warning_evidence", {})
    if not isinstance(phase2_evidence, Mapping):
        phase2_evidence = {}
    lines = [
        "# ES 2026 P1 Readiness-Warning Evidence",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Scope: `{summary.get('profile')}` `{summary.get('market')} {summary.get('year')}`",
        f"- Evidence status: `{summary.get('evidence_status')}`",
        f"- Packet can be prepared with separate approval: `{summary.get('accepted_warning_packet_can_be_prepared_with_separate_approval')}`",
        f"- ES 2026 remains fail-closed: `{summary.get('es2026_remains_fail_closed')}`",
        f"- Phase 2 status: `{phase2_evidence.get('status')}`",
        f"- Phase 2 warnings: `{phase2_evidence.get('warnings')}`",
        f"- Generated outputs: `{summary.get('generated_output_count')}`",
        "",
        "## Reason",
        "",
        str(summary.get("reason") or "Preconditions failed; see JSON checks."),
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
    parser.add_argument("--candidate-raw-path", default=str(DEFAULT_CANDIDATE_RAW_PATH))
    parser.add_argument("--profile-config", default=str(phase2_causal_base.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--session-config", default=str(phase2_causal_base.DEFAULT_SESSION_CONFIG))
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
            candidate_raw_path=resolve_path(repo_root, args.candidate_raw_path),
            profile_config_path=resolve_path(repo_root, args.profile_config),
            session_config_path=resolve_path(repo_root, args.session_config),
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
                    "detail": "Generated data/** and reports/** artifacts must remain unstaged after evidence refresh.",
                }
            )
        write_report_files(report, output_json=output_json, output_md=output_md)
    else:
        report["summary"]["post_execution_staged_generated_path_count"] = 0

    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"evidence_status={summary['evidence_status']} "
        f"packet_ready={summary['accepted_warning_packet_can_be_prepared_with_separate_approval']} "
        f"planned_generated_outputs={summary['planned_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"post_execution_staged_generated_paths={summary['post_execution_staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
