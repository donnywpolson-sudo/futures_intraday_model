#!/usr/bin/env python3
"""Run the approved ES 2026 P1 repair-path diagnostic."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_repair_diagnostic"
STATUS_READY = "REVIEW_READY_ES2026_P1_REPAIR_DIAGNOSTIC"
STATUS_NO_GO = "NO_GO_ES2026_P1_REPAIR_DIAGNOSTIC"
DECISION_DIAGNOSTIC_ONLY = "human_approved_es2026_p1_repair_path_diagnostic_only"
DECISION_BLOCKED = "es2026_p1_repair_diagnostic_blocked"

TARGET_MARKET = repair_plan_gate.TARGET_MARKET
TARGET_YEAR = repair_plan_gate.TARGET_YEAR
TARGET_PROFILE = repair_plan_gate.DEFAULT_PROFILE

DEFAULT_REPAIR_REPORTS_ROOT = repair_plan_gate.DEFAULT_REPAIR_REPORTS_ROOT
DEFAULT_CANDIDATE_RAW_ROOT = repair_plan_gate.DEFAULT_CANDIDATE_RAW_ROOT
DEFAULT_CANDIDATE_RAW_PATH = DEFAULT_CANDIDATE_RAW_ROOT / TARGET_MARKET / f"{TARGET_YEAR}.parquet"
DEFAULT_RAW_QUALITY_REPORT = DEFAULT_REPAIR_REPORTS_ROOT / "ES_2026_candidate_raw_quality_drilldown.json"
DEFAULT_OPTIONAL_SCHEMA_AUDIT = (
    DEFAULT_REPAIR_REPORTS_ROOT
    / "candidate_raw_optional_schema_audit"
    / "ES_2026_optional_schema_audit.json"
)
DEFAULT_CONVERSION_REPORT = (
    DEFAULT_REPAIR_REPORTS_ROOT / "candidate_raw_conversion" / "databento_convert_results.json"
)
DEFAULT_OUTPUT_ROOT = DEFAULT_REPAIR_REPORTS_ROOT / "repair_diagnostics"
DEFAULT_OUTPUT_JSON = DEFAULT_OUTPUT_ROOT / "ES_2026_repair_path_diagnostic.json"
DEFAULT_OUTPUT_MD = DEFAULT_OUTPUT_ROOT / "ES_2026_repair_path_diagnostic.md"

DISPOSITION_CANDIDATE_RAW_REPAIR = "candidate_raw_repair_or_rebuild_required"
DISPOSITION_ACCEPTED_WARNING_REVIEW = "accepted_warning_review_required"
DISPOSITION_REMAIN_FAIL_CLOSED = "remain_fail_closed"

FALSE_APPROVAL_FLAGS = repair_plan_gate.FALSE_APPROVAL_FLAGS

FORBIDDEN_ACTIONS = (
    "data_mutation",
    "candidate_raw_rewrite",
    "readiness_rerun",
    "accepted_warning_packet",
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
    return repair_plan_gate.rel(path, repo_root)


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


def _read_json(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, f"missing JSON: {path.as_posix()}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # pragma: no cover - exact parse errors are runtime-specific.
        return None, f"unreadable JSON: {path.as_posix()}: {type(exc).__name__}: {exc}"


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


def _is_target(row: Mapping[str, Any]) -> bool:
    return str(row.get("market")) == TARGET_MARKET and _as_int(row.get("year")) == TARGET_YEAR


def _target_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if _is_target(row)]


def _path_matches(left: Any, right: Path) -> bool:
    if not left:
        return False
    try:
        return Path(str(left)).resolve() == right.resolve()
    except OSError:
        return str(left).replace("\\", "/") == right.as_posix()


def _raw_quality_row(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    rows = _list_of_mappings(payload.get("drilldowns"))
    target = _target_rows(rows)
    return target[0] if len(target) == 1 else {}


def _conversion_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        return _list_of_mappings(payload.get("outputs"))
    return _list_of_mappings(payload)


def _optional_audit_target_file(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    rows = _list_of_mappings(payload.get("files"))
    target = _target_rows(rows)
    return target[0] if len(target) == 1 else {}


def _bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    return (
        series.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
    )


def _timestamp_series(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    for column in ("ts_event", "ts", "datetime", "datetime_utc", "timestamp", "time"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce"), column
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(frame.index, index=frame.index), "datetime_index"
    return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]"), "missing"


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _date_counts(ts: pd.Series, mask: pd.Series, *, limit: int = 10) -> list[dict[str, Any]]:
    selected = ts[mask & ts.notna()]
    if selected.empty:
        return []
    counts = Counter(selected.dt.date.astype(str))
    return [{"date": date, "row_count": count} for date, count in counts.most_common(limit)]


def _sample_timestamps(ts: pd.Series, mask: pd.Series, *, limit: int = 10) -> list[str]:
    selected = ts[mask & ts.notna()].sort_values().head(limit)
    return [str(pd.Timestamp(value).isoformat()) for value in selected]


def _status_counts(frame: pd.DataFrame) -> dict[str, int]:
    if "data_quality_status" not in frame.columns:
        return {}
    counts = frame["data_quality_status"].fillna("null").astype(str).value_counts()
    return {str(key): int(value) for key, value in counts.sort_index().items()}


def _source_file_counts(frame: pd.DataFrame, column: str, *, limit: int = 10) -> list[dict[str, Any]]:
    if column not in frame.columns:
        return []
    counts = frame[column].fillna("null").astype(str).value_counts().head(limit)
    return [{"path": str(path), "row_count": int(count)} for path, count in counts.items()]


def _read_candidate_raw_metrics(path: Path) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    if not path.exists():
        return {}, [f"candidate raw parquet missing: {path.as_posix()}"]
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - engine-specific runtime error.
        return {}, [f"candidate raw parquet unreadable: {type(exc).__name__}: {exc}"]
    ts, timestamp_source = _timestamp_series(frame)
    data_quality_degraded = _bool_series(frame, "data_quality_degraded")
    if "data_quality_status" in frame.columns:
        unavailable = frame["data_quality_status"].fillna("").astype(str).str.lower().ne("available")
        data_quality_degraded = data_quality_degraded | unavailable
    statistics_missing = _bool_series(frame, "statistics_missing")
    statistics_stale = _bool_series(frame, "statistics_stale")
    status_missing = _bool_series(frame, "status_missing")
    status_stale = _bool_series(frame, "status_stale")
    statistics_issue = statistics_missing | statistics_stale
    status_issue = status_missing | status_stale
    metrics = {
        "path": path.as_posix(),
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "timestamp_source": timestamp_source,
        "timestamp_null_count": int(ts.isna().sum()),
        "first_ts": _iso(ts.dropna().min() if ts.notna().any() else None),
        "last_ts": _iso(ts.dropna().max() if ts.notna().any() else None),
        "columns_present": {
            column: column in frame.columns
            for column in (
                "data_quality_status",
                "data_quality_degraded",
                "statistics_missing",
                "statistics_stale",
                "status_missing",
                "status_stale",
                "status_is_trading",
                "status_is_quoting",
            )
        },
        "data_quality_status_counts": _status_counts(frame),
        "data_quality_degraded_or_unavailable_rows": int(data_quality_degraded.sum()),
        "status_missing_rows": int(status_missing.sum()),
        "status_stale_rows": int(status_stale.sum()),
        "statistics_missing_rows": int(statistics_missing.sum()),
        "statistics_stale_rows": int(statistics_stale.sum()),
        "statistics_issue_rows": int(statistics_issue.sum()),
        "status_issue_rows": int(status_issue.sum()),
        "degraded_and_statistics_issue_rows": int((data_quality_degraded & statistics_issue).sum()),
        "degraded_and_status_issue_rows": int((data_quality_degraded & status_issue).sum()),
        "top_degraded_dates": _date_counts(ts, data_quality_degraded),
        "top_statistics_issue_dates": _date_counts(ts, statistics_issue),
        "top_status_issue_dates": _date_counts(ts, status_issue),
        "statistics_issue_sample_timestamps": _sample_timestamps(ts, statistics_issue),
        "status_issue_sample_timestamps": _sample_timestamps(ts, status_issue),
        "status_source_file_counts": _source_file_counts(frame, "status_source_file"),
        "statistics_source_file_counts": _source_file_counts(frame, "stat_settlement_price_source_file"),
    }
    if metrics["timestamp_null_count"]:
        failures.append("candidate raw has null timestamps")
    return metrics, failures


def _candidate_raw_tree_files(repo_root: Path, candidate_raw_root: Path) -> list[str]:
    if not _path_under(repo_root, candidate_raw_root, "data") or not candidate_raw_root.exists():
        return []
    return sorted(
        rel(path, repo_root)
        for path in candidate_raw_root.rglob("*")
        if path.is_file()
    )


def _planned_outputs(repo_root: Path, output_json: Path, output_md: Path) -> list[str]:
    return [rel(output_json, repo_root), rel(output_md, repo_root)]


def _raw_quality_scope(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"selected": [], "drilldowns": []}
    return {
        "selected": [
            {"market": row.get("market"), "year": row.get("year")}
            for row in _list_of_mappings(payload.get("selected_market_years"))
        ],
        "drilldowns": [
            {"market": row.get("market"), "year": row.get("year")}
            for row in _list_of_mappings(payload.get("drilldowns"))
        ],
    }


def _conversion_scope(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{"market": row.get("market"), "year": row.get("year")} for row in rows]


def _accepted_warning_needed(metrics: Mapping[str, Any]) -> bool:
    return (
        _as_int(metrics.get("statistics_issue_rows")) > 0
        or _as_int(metrics.get("status_issue_rows")) > 0
    )


def _disposition(
    *,
    candidate_raw_metrics: Mapping[str, Any],
    candidate_raw_failures: list[str],
    optional_audit_pass: bool,
    conversion_pass: bool,
) -> dict[str, Any]:
    degraded_rows = _as_int(candidate_raw_metrics.get("data_quality_degraded_or_unavailable_rows"))
    statistics_issue_rows = _as_int(candidate_raw_metrics.get("statistics_issue_rows"))
    status_issue_rows = _as_int(candidate_raw_metrics.get("status_issue_rows"))
    if candidate_raw_failures or degraded_rows > 0 or not optional_audit_pass or not conversion_pass:
        path = DISPOSITION_CANDIDATE_RAW_REPAIR
        reason = (
            "Candidate raw evidence is missing, failed audit/conversion checks, or still has degraded "
            "data-quality rows."
        )
    elif statistics_issue_rows or status_issue_rows:
        path = DISPOSITION_ACCEPTED_WARNING_REVIEW
        reason = (
            "Candidate raw no longer shows degraded data-quality rows, but optional enrichment gaps "
            "remain and need a separate accepted-warning review or further statistics repair."
        )
    else:
        path = DISPOSITION_REMAIN_FAIL_CLOSED
        reason = (
            "Candidate raw repair/rebuild is not indicated by this diagnostic, but ES 2026 remains "
            "fail-closed until a separately approved readiness-only rerun or later gate changes status."
        )
    return {
        "recommended_path": path,
        "reason": reason,
        "candidate_raw_repair_or_rebuild_needed": path == DISPOSITION_CANDIDATE_RAW_REPAIR,
        "accepted_warning_review_needed": path == DISPOSITION_ACCEPTED_WARNING_REVIEW,
        "remain_fail_closed": True,
        "readiness_rerun_approved": False,
        "accepted_warning_packet_approved": False,
        "exclusion_approved": False,
        "stop_condition_met": True,
        "forbidden_actions_preserved": list(FORBIDDEN_ACTIONS),
    }


def _recommended_next(status: str, disposition: Mapping[str, Any] | None = None) -> str:
    if status == STATUS_NO_GO:
        return "Fix missing or invalid ES 2026 repair diagnostic preconditions, then rerun this diagnostic."
    recommended_path = str((disposition or {}).get("recommended_path"))
    if recommended_path == DISPOSITION_ACCEPTED_WARNING_REVIEW:
        return (
            "Review the ES 2026 statistics enrichment gap evidence and approve or reject a separate "
            "accepted-warning criteria review; keep ES 2026 fail-closed."
        )
    if recommended_path == DISPOSITION_CANDIDATE_RAW_REPAIR:
        return (
            "Approve or reject a separate bounded ES 2026 candidate raw repair/rebuild step; keep ES "
            "2026 fail-closed."
        )
    return "Keep ES 2026 fail-closed until a separate bounded readiness or disposition decision is approved."


def build_report(
    *,
    repo_root: Path,
    work_order_report: Path,
    raw_quality_report: Path,
    optional_schema_audit: Path,
    conversion_report: Path,
    candidate_raw_root: Path,
    candidate_raw_path: Path,
    output_json: Path,
    output_md: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
    reports_written: bool = False,
) -> dict[str, Any]:
    work_order_payload, work_order_error = _read_json(work_order_report)
    raw_quality_payload, raw_quality_error = _read_json(raw_quality_report)
    optional_payload, optional_error = _read_json(optional_schema_audit)
    conversion_payload, conversion_error = _read_json(conversion_report)

    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    planned_outputs = _planned_outputs(repo_root, output_json, output_md)
    ignored_outputs = (
        _filter_ignored_expected_paths(planned_outputs, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _git_ignored_generated_paths(repo_root, planned_outputs)
    )
    unignored_outputs = sorted(set(planned_outputs) - set(ignored_outputs))

    work_orders = _list_of_mappings(work_order_payload.get("work_orders") if isinstance(work_order_payload, Mapping) else None)
    raw_quality_selected = _list_of_mappings(
        raw_quality_payload.get("selected_market_years") if isinstance(raw_quality_payload, Mapping) else None
    )
    raw_quality_rows = _list_of_mappings(
        raw_quality_payload.get("drilldowns") if isinstance(raw_quality_payload, Mapping) else None
    )
    raw_quality_row = _raw_quality_row(raw_quality_payload)
    optional_file = _optional_audit_target_file(optional_payload)
    conversion_rows = _conversion_rows(conversion_payload)
    conversion_target_rows = _target_rows(conversion_rows)
    target_tree_files = _candidate_raw_tree_files(repo_root, candidate_raw_root)
    candidate_raw_metrics, candidate_raw_failures = _read_candidate_raw_metrics(candidate_raw_path)

    optional_verdicts = optional_payload.get("verdicts") if isinstance(optional_payload, Mapping) else {}
    if not isinstance(optional_verdicts, Mapping):
        optional_verdicts = {}
    optional_audit_pass = (
        isinstance(optional_payload, Mapping)
        and optional_payload.get("status") == "PASS"
        and optional_verdicts.get("optional_status_readiness") == "PASS"
        and optional_verdicts.get("optional_statistics_readiness") == "PASS"
        and _is_target(optional_file)
    )
    conversion_pass = (
        len(conversion_rows) == 1
        and len(conversion_target_rows) == 1
        and str(conversion_target_rows[0].get("status")) == "ok"
        and conversion_target_rows[0].get("optional_schema_policy") == "require"
        and set(conversion_target_rows[0].get("optional_schemas") or []) >= {"status", "statistics"}
        and _path_matches(conversion_target_rows[0].get("output_path"), candidate_raw_path)
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="work_order_report_readable",
        passed=work_order_error is None and isinstance(work_order_payload, Mapping),
        observed=work_order_error,
        expected="readable JSON object",
        detail="The diagnostic must start from the existing ES 2026 repair work order.",
    )
    _check(
        checks,
        name="work_order_exact_es2026_scope",
        passed=len(work_orders) == 1 and _is_target(work_orders[0] if work_orders else {}),
        observed=_conversion_scope(work_orders),
        expected=[{"market": TARGET_MARKET, "year": TARGET_YEAR}],
        detail="This diagnostic is scoped exactly to ES 2026.",
    )
    _check(
        checks,
        name="raw_quality_report_readable",
        passed=raw_quality_error is None and isinstance(raw_quality_payload, Mapping),
        observed=raw_quality_error,
        expected="readable JSON object",
        detail="The diagnostic must read the generated ES 2026 candidate raw-quality drilldown.",
    )
    _check(
        checks,
        name="raw_quality_exact_es2026_scope",
        passed=(
            len(raw_quality_selected) == 1
            and _is_target(raw_quality_selected[0])
            and len(raw_quality_rows) == 1
            and _is_target(raw_quality_row)
        ),
        observed=_raw_quality_scope(raw_quality_payload),
        expected={"market": TARGET_MARKET, "year": TARGET_YEAR},
        detail="Raw-quality evidence must be restricted to ES 2026.",
    )
    _check(
        checks,
        name="raw_quality_fail_closed_blocker_present",
        passed=(
            isinstance(raw_quality_payload, Mapping)
            and raw_quality_payload.get("status") == "FAIL"
            and raw_quality_row.get("raw_read_status") == "PASS"
            and str(raw_quality_row.get("top_blocker_reason", "")).startswith("degraded threshold breached")
        ),
        observed={
            "status": raw_quality_payload.get("status") if isinstance(raw_quality_payload, Mapping) else None,
            "raw_read_status": raw_quality_row.get("raw_read_status"),
            "top_blocker_reason": raw_quality_row.get("top_blocker_reason"),
        },
        expected="FAIL raw-quality drilldown with degraded threshold blocker and raw_read_status PASS",
        detail="The diagnostic is only valid for the current ES 2026 fail-closed blocker.",
    )
    _check(
        checks,
        name="optional_schema_audit_pass_exact_scope",
        passed=optional_error is None and optional_audit_pass,
        observed={
            "error": optional_error,
            "status": optional_payload.get("status") if isinstance(optional_payload, Mapping) else None,
            "verdicts": optional_verdicts,
            "target_file": {"market": optional_file.get("market"), "year": optional_file.get("year")},
        },
        expected="PASS optional status/statistics audit for exactly ES 2026",
        detail="Status/statistics enrichment evidence must be existing PASS audit evidence.",
    )
    _check(
        checks,
        name="candidate_conversion_exact_scope",
        passed=conversion_error is None and conversion_pass,
        observed={
            "error": conversion_error,
            "scope": _conversion_scope(conversion_rows),
            "target_count": len(conversion_target_rows),
        },
        expected="one successful ES 2026 candidate conversion row with required status/statistics",
        detail="The diagnostic must read, not rewrite, the existing ES 2026 candidate raw conversion.",
    )
    _check(
        checks,
        name="candidate_raw_root_exact_target_only",
        passed=target_tree_files == [rel(candidate_raw_path, repo_root)],
        observed=target_tree_files,
        expected=[rel(candidate_raw_path, repo_root)],
        detail="Candidate raw root must contain only the approved ES 2026 parquet.",
    )
    _check(
        checks,
        name="candidate_raw_parquet_readable",
        passed=not candidate_raw_failures and _as_int(candidate_raw_metrics.get("row_count")) > 0,
        observed=candidate_raw_failures,
        expected="readable non-empty ES 2026 candidate raw parquet",
        detail="The diagnostic reads existing candidate raw parquet but does not rewrite it.",
    )
    _check(
        checks,
        name="output_paths_under_reports",
        passed=_path_under(repo_root, output_json, "reports") and _path_under(repo_root, output_md, "reports"),
        observed=planned_outputs,
        expected="reports/**",
        detail="Diagnostic outputs must be ignored review reports only.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_outputs and len(ignored_outputs) == len(planned_outputs),
        observed=unignored_outputs,
        expected=[],
        detail="Diagnostic report outputs must be ignored generated artifacts.",
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
    disposition = (
        {}
        if failures
        else _disposition(
            candidate_raw_metrics=candidate_raw_metrics,
            candidate_raw_failures=candidate_raw_failures,
            optional_audit_pass=optional_audit_pass,
            conversion_pass=conversion_pass,
        )
    )
    generated_outputs = planned_outputs if reports_written and not failures else []
    approval_flags = _approval_flags()
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_DIAGNOSTIC_ONLY,
            "profile": TARGET_PROFILE,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "candidate_raw_root": rel(candidate_raw_root, repo_root),
            "candidate_raw_path": rel(candidate_raw_path, repo_root),
            "raw_quality_report": rel(raw_quality_report, repo_root),
            "optional_schema_audit": rel(optional_schema_audit, repo_root),
            "conversion_report": rel(conversion_report, repo_root),
            "planned_generated_output_count": len(planned_outputs),
            "ignored_planned_generated_output_count": len(ignored_outputs),
            "unignored_planned_generated_output_count": len(unignored_outputs),
            "generated_report_written": bool(generated_outputs),
            "generated_output_count": len(generated_outputs),
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_disposition": disposition.get("recommended_path"),
            "recommended_next_action": _recommended_next(status, disposition),
            **approval_flags,
        },
        "checks": checks,
        "planned_generated_outputs": planned_outputs,
        "generated_outputs": generated_outputs,
        "raw_quality_evidence": {
            "status": raw_quality_payload.get("status") if isinstance(raw_quality_payload, Mapping) else None,
            "top_blocker_reason": raw_quality_row.get("top_blocker_reason"),
            "checkpoint_degraded_bar_rows": _as_int(raw_quality_row.get("degraded_bar_rows")),
            "checkpoint_degraded_rows_pct": _as_float(raw_quality_row.get("degraded_rows_pct")),
            "checkpoint_degraded_session_rows": _as_int(raw_quality_row.get("degraded_session_rows")),
            "checkpoint_statistics_enrichment_missing_rows": _as_int(
                raw_quality_row.get("statistics_enrichment_missing_rows")
            ),
            "checkpoint_statistics_enrichment_stale_rows": _as_int(
                raw_quality_row.get("statistics_enrichment_stale_rows")
            ),
        },
        "candidate_raw_metrics": candidate_raw_metrics,
        "optional_schema_audit_summary": {
            "status": optional_payload.get("status") if isinstance(optional_payload, Mapping) else None,
            "verdicts": dict(optional_verdicts),
            "target_file_status": optional_file.get("status"),
            "status_metrics": optional_file.get("status_metrics"),
            "statistics_metrics": optional_file.get("statistics_metrics"),
        },
        "conversion_summary": {
            "status": conversion_target_rows[0].get("status") if conversion_target_rows else None,
            "optional_schema_policy": (
                conversion_target_rows[0].get("optional_schema_policy") if conversion_target_rows else None
            ),
            "optional_schema_match_summary": (
                conversion_target_rows[0].get("optional_schema_match_summary") if conversion_target_rows else None
            ),
            "data_quality_status_counts": (
                conversion_target_rows[0].get("data_quality_status_counts") if conversion_target_rows else None
            ),
            "degraded_bar_count": conversion_target_rows[0].get("degraded_bar_count") if conversion_target_rows else None,
        },
        "diagnostic_disposition": disposition,
        "non_approval": {
            "scope": "ES 2026 P1 repair_path diagnostic only",
            "data_written": False,
            "candidate_raw_rewritten": False,
            "readiness_rerun": False,
            "accepted_warning_packet": False,
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
    disposition = report.get("diagnostic_disposition", {})
    if not isinstance(disposition, Mapping):
        disposition = {}
    raw_metrics = report.get("candidate_raw_metrics", {})
    if not isinstance(raw_metrics, Mapping):
        raw_metrics = {}
    lines = [
        "# ES 2026 P1 Repair-Path Diagnostic",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Scope: `{summary.get('profile')}` `{summary.get('market')} {summary.get('year')}`",
        f"- Recommended disposition: `{summary.get('recommended_disposition')}`",
        f"- Fail closed: `{disposition.get('remain_fail_closed')}`",
        f"- Candidate raw degraded/unavailable rows: `{raw_metrics.get('data_quality_degraded_or_unavailable_rows')}`",
        f"- Statistics issue rows: `{raw_metrics.get('statistics_issue_rows')}`",
        f"- Status issue rows: `{raw_metrics.get('status_issue_rows')}`",
        f"- Generated outputs: `{summary.get('generated_output_count')}`",
        "",
        "## Reason",
        "",
        str(disposition.get("reason") or "Preconditions failed; see JSON checks."),
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
    parser.add_argument("--work-order-report", default=str(repair_plan_gate.DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--raw-quality-report", default=str(DEFAULT_RAW_QUALITY_REPORT))
    parser.add_argument("--optional-schema-audit", default=str(DEFAULT_OPTIONAL_SCHEMA_AUDIT))
    parser.add_argument("--conversion-report", default=str(DEFAULT_CONVERSION_REPORT))
    parser.add_argument("--candidate-raw-root", default=str(DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--candidate-raw-path", default=str(DEFAULT_CANDIDATE_RAW_PATH))
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
            work_order_report=resolve_path(repo_root, args.work_order_report),
            raw_quality_report=resolve_path(repo_root, args.raw_quality_report),
            optional_schema_audit=resolve_path(repo_root, args.optional_schema_audit),
            conversion_report=resolve_path(repo_root, args.conversion_report),
            candidate_raw_root=resolve_path(repo_root, args.candidate_raw_root),
            candidate_raw_path=resolve_path(repo_root, args.candidate_raw_path),
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
                    "detail": "Generated data/** and reports/** artifacts must remain unstaged after diagnostics.",
                }
            )
        write_report_files(report, output_json=output_json, output_md=output_md)
    else:
        report["summary"]["post_execution_staged_generated_path_count"] = 0

    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"recommended_disposition={summary['recommended_disposition']} "
        f"planned_generated_outputs={summary['planned_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"post_execution_staged_generated_paths={summary['post_execution_staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
