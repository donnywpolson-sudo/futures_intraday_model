#!/usr/bin/env python3
"""Read-only raw drilldown for selected Phase 2 readiness blockers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.phase2_causal_base.build_causal_base_data import (
    DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    DEFAULT_PROFILE,
    DEFAULT_PROFILE_CONFIG,
    DEFAULT_SESSION_CONFIG,
    _session_metadata,
    load_causal_base_config,
    load_session_calendar,
)
from scripts.validation.audit_phase2_readiness import load_checkpoint_rows
from scripts.validation.summarize_phase2_readiness_blockers import classify_blocker

DEFAULT_CHECKPOINT = Path("reports/phase2_readiness/tier3_readiness_20260620.jsonl")
DEFAULT_RAW_ROOT = Path("data/raw")
TIMESTAMP_COLUMNS = ("ts_event", "ts", "datetime", "datetime_utc", "timestamp", "time")
BOOL_COLUMNS = (
    "status_is_trading",
    "status_is_quoting",
    "status_missing",
    "status_stale",
    "statistics_missing",
    "statistics_stale",
    "data_quality_degraded",
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-jsonl", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--session-config", default=str(DEFAULT_SESSION_CONFIG))
    parser.add_argument(
        "--max-synthetic-gap-minutes",
        type=int,
        default=DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    )
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--max-selected-market-years", type=int, default=5)
    parser.add_argument("--markets", nargs="+")
    parser.add_argument("--years", nargs="+", type=int)
    parser.add_argument("--json-out")
    return parser


def _as_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _checkpoint_context(row: dict[str, Any]) -> dict[str, Any]:
    classes, other_reasons = classify_blocker(row)
    return {
        "market": str(row.get("market")),
        "year": _as_int(row.get("year")),
        "checkpoint_status": row.get("status"),
        "blocker_classes": sorted(classes),
        "other_reasons": other_reasons,
        "top_blocker_reason": row.get("top_blocker_reason"),
        "synthetic_rows_pct": _as_float(row.get("synthetic_rows_pct")),
        "synthetic_rows": _as_int(row.get("synthetic_rows")),
        "max_synthetic_gap_minutes": _as_int(row.get("max_synthetic_gap_minutes")),
        "degraded_rows_pct": _as_float(row.get("degraded_rows_pct")),
        "degraded_bar_rows": _as_int(row.get("degraded_bar_rows")),
        "degraded_session_rows": _as_int(row.get("degraded_session_rows")),
        "roll_window_rows_pct": _as_float(row.get("roll_window_rows_pct")),
        "roll_window_rows": _as_int(row.get("roll_window_rows")),
        "status_enrichment_missing_rows": _as_int(
            row.get("status_enrichment_missing_rows")
        ),
        "status_enrichment_stale_rows": _as_int(row.get("status_enrichment_stale_rows")),
        "statistics_enrichment_missing_rows": _as_int(
            row.get("statistics_enrichment_missing_rows")
        ),
        "statistics_enrichment_stale_rows": _as_int(
            row.get("statistics_enrichment_stale_rows")
        ),
    }


def _select_top_blockers(
    rows: list[dict[str, Any]],
    *,
    top_n: int,
    max_selected_market_years: int | None = None,
    markets: set[str] | None = None,
    years: set[int] | None = None,
) -> list[dict[str, Any]]:
    filtered = []
    for row in rows:
        market = str(row.get("market"))
        year = _as_int(row.get("year"))
        if markets is not None and market not in markets:
            continue
        if years is not None and year not in years:
            continue
        if row.get("status") == "PASS":
            continue
        filtered.append(row)

    limit = max(0, int(top_n))

    def top(key: str, secondary: str | None = None) -> list[dict[str, Any]]:
        return sorted(
            filtered,
            key=lambda row: (
                _as_float(row.get(key)),
                _as_float(row.get(secondary)) if secondary else 0.0,
            ),
            reverse=True,
        )[:limit]

    selected: dict[tuple[str, int], dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for group in (
        top("synthetic_rows_pct", "max_synthetic_gap_minutes"),
        top("degraded_rows_pct"),
        top("status_enrichment_missing_rows", "status_enrichment_stale_rows"),
        top("statistics_enrichment_missing_rows", "statistics_enrichment_stale_rows"),
        top("roll_window_rows_pct", "roll_window_rows"),
    ):
        for row in group:
            key = (str(row.get("market")), _as_int(row.get("year")))
            if key not in selected:
                selected[key] = row
                ordered.append(row)
    if max_selected_market_years is not None:
        ordered = ordered[: max(0, int(max_selected_market_years))]
    return ordered


def _raw_path(raw_root: Path, market: str, year: int) -> Path:
    return raw_root / market / f"{year}.parquet"


def _timestamp_series(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    for column in TIMESTAMP_COLUMNS:
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce"), column
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(frame.index, index=frame.index), "datetime_index"
    return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]"), "missing"


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


def _nullable_bool(value: object) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _iso(value: pd.Timestamp | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _top_date_counts(ts: pd.Series, mask: pd.Series, *, limit: int = 5) -> list[dict[str, Any]]:
    valid = ts[mask & ts.notna()]
    if valid.empty:
        return []
    counts = Counter(valid.dt.date.astype(str))
    return [
        {"date": date, "row_count": count}
        for date, count in counts.most_common(limit)
    ]


def _raw_gap_summary(ts: pd.Series, *, limit: int = 5) -> dict[str, Any]:
    valid = ts.dropna().drop_duplicates().sort_values().reset_index(drop=True)
    if len(valid) < 2:
        return {
            "scope": "raw_utc_consecutive_timestamps_not_session_filtered",
            "gap_count": 0,
            "max_gap_minutes": 0.0,
            "top_gaps": [],
            "top_gap_dates": [],
        }
    deltas = valid.diff()
    gap_mask = deltas > pd.Timedelta(minutes=1)
    gap_indices = list(valid.index[gap_mask])
    top_gaps = []
    for idx in sorted(
        gap_indices,
        key=lambda item: deltas.iloc[item],
        reverse=True,
    )[:limit]:
        previous_ts = valid.iloc[idx - 1]
        next_ts = valid.iloc[idx]
        gap_minutes = deltas.iloc[idx] / pd.Timedelta(minutes=1)
        top_gaps.append(
            {
                "previous_ts": _iso(previous_ts),
                "next_ts": _iso(next_ts),
                "gap_minutes": float(gap_minutes),
            }
        )
    gap_dates = Counter(str(valid.iloc[idx - 1].date()) for idx in gap_indices)
    return {
        "scope": "raw_utc_consecutive_timestamps_not_session_filtered",
        "gap_count": len(gap_indices),
        "max_gap_minutes": float(
            max((deltas.iloc[idx] / pd.Timedelta(minutes=1) for idx in gap_indices), default=0.0)
        ),
        "top_gaps": top_gaps,
        "top_gap_dates": [
            {"date": date, "gap_count": count}
            for date, count in gap_dates.most_common(limit)
        ],
    }


def _phase2_session_gap_summary(
    frame: pd.DataFrame,
    ts: pd.Series,
    *,
    market: str,
    session_config_path: Path,
    max_synthetic_gap_minutes: int,
    top_n: int,
) -> dict[str, Any]:
    if ts.isna().all():
        return {
            "scope": "phase2_session_calendar_synthetic_candidate_gaps",
            "status": "FAIL",
            "failures": ["timestamp source missing"],
        }
    calendar = load_session_calendar(
        market,
        session_config_path,
        allow_hardcoded_calendar=False,
    )
    work = frame.reset_index(drop=True).copy()
    work["_ts"] = ts.reset_index(drop=True)
    metadata = _session_metadata(work["_ts"], calendar).reset_index(drop=True)
    work = pd.concat([work, metadata], axis=1)
    inside = (
        work[work["inside_session"].fillna(False).astype(bool)]
        .sort_values("_ts", kind="mergesort")
        .reset_index(drop=True)
    )
    if len(inside) < 2:
        return {
            "scope": "phase2_session_calendar_synthetic_candidate_gaps",
            "status": "PASS",
            "session_calendar_status": calendar.status,
            "inside_session_raw_rows": int(len(inside)),
            "candidate_gap_count": 0,
            "synthetic_missing_rows_estimate": 0,
            "max_candidate_gap_minutes": 0.0,
            "top_session_gaps": [],
            "top_session_gap_dates": [],
        }

    prev_rows = inside.iloc[:-1].reset_index(drop=True)
    next_rows = inside.iloc[1:].reset_index(drop=True)
    gap_minutes = (
        (next_rows["_ts"] - prev_rows["_ts"]).dt.total_seconds() / 60.0
    )
    same_session = prev_rows["session_id"].astype(object).eq(
        next_rows["session_id"].astype(object)
    )
    candidate_mask = (
        same_session
        & gap_minutes.gt(1)
        & gap_minutes.le(max_synthetic_gap_minutes)
        & prev_rows.get("close", pd.Series([pd.NA] * len(prev_rows))).notna()
    )
    if "instrument_id" in prev_rows.columns and "instrument_id" in next_rows.columns:
        previous_instrument = prev_rows["instrument_id"]
        next_instrument = next_rows["instrument_id"]
        both_known = previous_instrument.notna() & next_instrument.notna()
        instrument_changed = both_known & previous_instrument.ne(next_instrument)
        candidate_mask = candidate_mask & ~instrument_changed

    candidate_indices = list(candidate_mask[candidate_mask].index)
    top_indices = sorted(
        candidate_indices,
        key=lambda idx: gap_minutes.iloc[idx],
        reverse=True,
    )[: max(0, int(top_n))]
    top_gaps = []
    for idx in top_indices:
        previous = prev_rows.iloc[idx]
        next_row = next_rows.iloc[idx]
        gap = float(gap_minutes.iloc[idx])
        top_gaps.append(
            {
                "previous_ts": _iso(previous["_ts"]),
                "next_ts": _iso(next_row["_ts"]),
                "session_id": (
                    None
                    if pd.isna(previous.get("session_id"))
                    else str(previous.get("session_id"))
                ),
                "session_date": (
                    None
                    if pd.isna(previous.get("session_date"))
                    else str(previous.get("session_date"))
                ),
                "gap_minutes": gap,
                "synthetic_missing_minutes": int(gap - 1),
                "previous_status_is_trading": _nullable_bool(
                    previous.get("status_is_trading")
                ),
                "next_status_is_trading": _nullable_bool(next_row.get("status_is_trading")),
                "previous_status_is_quoting": _nullable_bool(
                    previous.get("status_is_quoting")
                ),
                "next_status_is_quoting": _nullable_bool(next_row.get("status_is_quoting")),
                "previous_status_missing": _nullable_bool(previous.get("status_missing")),
                "next_status_missing": _nullable_bool(next_row.get("status_missing")),
                "previous_statistics_missing": _nullable_bool(
                    previous.get("statistics_missing")
                ),
                "next_statistics_missing": _nullable_bool(
                    next_row.get("statistics_missing")
                ),
            }
        )

    gap_dates = Counter(
        str(prev_rows.iloc[idx].get("session_date")) for idx in candidate_indices
    )
    return {
        "scope": "phase2_session_calendar_synthetic_candidate_gaps",
        "status": "WARN" if candidate_indices else "PASS",
        "session_calendar_status": calendar.status,
        "inside_session_raw_rows": int(len(inside)),
        "candidate_gap_count": len(candidate_indices),
        "synthetic_missing_rows_estimate": int(
            sum(gap_minutes.iloc[idx] - 1 for idx in candidate_indices)
        ),
        "max_candidate_gap_minutes": float(
            max((gap_minutes.iloc[idx] for idx in candidate_indices), default=0.0)
        ),
        "top_session_gaps": top_gaps,
        "top_session_gap_dates": [
            {"session_date": date, "gap_count": count}
            for date, count in gap_dates.most_common(max(0, int(top_n)))
        ],
    }


def _quality_counts(frame: pd.DataFrame) -> dict[str, int]:
    if "data_quality_status" not in frame.columns:
        return {}
    counts = frame["data_quality_status"].fillna("null").astype(str).value_counts()
    return {str(key): int(value) for key, value in counts.sort_index().items()}


def drilldown_market_year(
    raw_root: Path,
    row: dict[str, Any],
    *,
    top_n: int,
    session_config_path: Path,
    max_synthetic_gap_minutes: int,
) -> dict[str, Any]:
    context = _checkpoint_context(row)
    market = context["market"]
    year = context["year"]
    path = _raw_path(raw_root, market, year)
    result: dict[str, Any] = {
        **context,
        "raw_path": str(path),
        "raw_read_status": "FAIL",
        "raw_failures": [],
    }
    if not path.exists():
        result["raw_failures"].append(f"raw parquet missing: {path}")
        return result

    try:
        frame = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - exact engine errors vary.
        result["raw_failures"].append(f"raw parquet read failed: {exc}")
        return result

    ts, timestamp_source = _timestamp_series(frame)
    bool_counts = {
        column: int(_bool_series(frame, column).sum())
        for column in BOOL_COLUMNS
        if column in frame.columns
    }
    degraded_mask = _bool_series(frame, "data_quality_degraded")
    if "data_quality_status" in frame.columns:
        degraded_mask = degraded_mask | frame["data_quality_status"].fillna("").astype(str).str.lower().ne("available")

    result.update(
        {
            "raw_read_status": "PASS",
            "raw_row_count": int(len(frame)),
            "raw_column_count": int(len(frame.columns)),
            "timestamp_source": timestamp_source,
            "timestamp_null_count": int(ts.isna().sum()),
            "first_ts": _iso(ts.dropna().min() if ts.notna().any() else None),
            "last_ts": _iso(ts.dropna().max() if ts.notna().any() else None),
            "raw_utc_date_count": int(ts.dropna().dt.date.nunique()) if ts.notna().any() else 0,
            "columns_present": {
                column: column in frame.columns
                for column in (
                    "data_quality_status",
                    "data_quality_degraded",
                    "status_is_trading",
                    "status_is_quoting",
                    "status_missing",
                    "status_stale",
                    "statistics_missing",
                    "statistics_stale",
                )
            },
            "bool_true_counts": bool_counts,
            "data_quality_status_counts": _quality_counts(frame),
            "raw_gap_summary": _raw_gap_summary(ts, limit=top_n),
            "phase2_session_gap_summary": _phase2_session_gap_summary(
                frame,
                ts,
                market=market,
                session_config_path=session_config_path,
                max_synthetic_gap_minutes=max_synthetic_gap_minutes,
                top_n=top_n,
            ),
            "top_degraded_dates": _top_date_counts(ts, degraded_mask, limit=top_n),
            "top_status_missing_dates": _top_date_counts(
                ts, _bool_series(frame, "status_missing"), limit=top_n
            ),
            "top_status_stale_dates": _top_date_counts(
                ts, _bool_series(frame, "status_stale"), limit=top_n
            ),
            "top_statistics_missing_dates": _top_date_counts(
                ts, _bool_series(frame, "statistics_missing"), limit=top_n
            ),
            "top_statistics_stale_dates": _top_date_counts(
                ts, _bool_series(frame, "statistics_stale"), limit=top_n
            ),
        }
    )
    return result


def build_drilldown_report(
    rows: list[dict[str, Any]],
    *,
    raw_root: Path,
    top_n: int = 5,
    profile: str = DEFAULT_PROFILE,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    session_config_path: Path = DEFAULT_SESSION_CONFIG,
    max_synthetic_gap_minutes: int = DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    max_selected_market_years: int | None = 5,
    markets: set[str] | None = None,
    years: set[int] | None = None,
) -> dict[str, Any]:
    config = load_causal_base_config(profile_config_path, profile)
    effective_max_synthetic_gap_minutes = (
        config.max_synthetic_gap_minutes
        if max_synthetic_gap_minutes == DEFAULT_MAX_SYNTHETIC_GAP_MINUTES
        else max_synthetic_gap_minutes
    )
    selected = _select_top_blockers(
        rows,
        top_n=top_n,
        max_selected_market_years=max_selected_market_years,
        markets=markets,
        years=years,
    )
    drilldowns = [
        drilldown_market_year(
            raw_root,
            row,
            top_n=max(1, int(top_n)),
            session_config_path=session_config_path,
            max_synthetic_gap_minutes=effective_max_synthetic_gap_minutes,
        )
        for row in selected
    ]
    raw_failures = [
        failure
        for row in drilldowns
        for failure in row.get("raw_failures", [])
    ]
    blocker_count = sum(1 for row in rows if row.get("status") != "PASS")
    return {
        "stage": "phase2_readiness_raw_drilldown",
        "status": "FAIL" if blocker_count or raw_failures else "PASS",
        "policy": "READ_ONLY_DIAGNOSTIC_ONLY",
        "ready_to_rebuild_tier3_phase2": False,
        "checkpoint_market_year_count": len(rows),
        "checkpoint_blocker_count": blocker_count,
        "selected_market_year_count": len(selected),
        "max_selected_market_years": max_selected_market_years,
        "raw_read_failure_count": len(raw_failures),
        "raw_failures": raw_failures,
        "selected_market_years": [
            {"market": str(row.get("market")), "year": _as_int(row.get("year"))}
            for row in selected
        ],
        "evidence_scope": {
            "checkpoint_jsonl_read": True,
            "raw_parquet_read": True,
            "raw_parquet_written": False,
            "canonical_phase2_written": False,
            "labels_features_wfa_predictions_written": False,
            "gap_scope": "raw_utc_consecutive_timestamps_not_session_filtered",
            "session_gap_scope": "phase2_session_calendar_synthetic_candidate_gaps",
            "max_synthetic_gap_minutes": effective_max_synthetic_gap_minutes,
        },
        "limitations": [
            "This is a bounded diagnostic over selected top offenders, not a full Phase 2 rebuild.",
            "Session gap summaries use Phase 2 calendar logic but do not write causal output.",
            "Repair or exclusion decisions require explicit policy and follow-up evidence.",
        ],
        "drilldowns": drilldowns,
    }


def _compact_stdout(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": report["stage"],
        "status": report["status"],
        "policy": report["policy"],
        "ready_to_rebuild_tier3_phase2": report["ready_to_rebuild_tier3_phase2"],
        "checkpoint_blocker_count": report["checkpoint_blocker_count"],
        "selected_market_year_count": report["selected_market_year_count"],
        "raw_read_failure_count": report["raw_read_failure_count"],
        "selected_market_years": report["selected_market_years"],
        "top_raw_gaps": [
            {
                "market": row["market"],
                "year": row["year"],
                "max_gap_minutes": row.get("raw_gap_summary", {}).get("max_gap_minutes"),
                "gap_count": row.get("raw_gap_summary", {}).get("gap_count"),
            }
            for row in report["drilldowns"][:10]
        ],
        "top_session_gaps": [
            {
                "market": row["market"],
                "year": row["year"],
                "max_gap_minutes": row.get("phase2_session_gap_summary", {}).get(
                    "max_candidate_gap_minutes"
                ),
                "candidate_gap_count": row.get("phase2_session_gap_summary", {}).get(
                    "candidate_gap_count"
                ),
                "synthetic_missing_rows_estimate": row.get(
                    "phase2_session_gap_summary", {}
                ).get("synthetic_missing_rows_estimate"),
            }
            for row in report["drilldowns"][:10]
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        rows = load_checkpoint_rows(Path(args.checkpoint_jsonl))
        report = build_drilldown_report(
            rows,
            raw_root=Path(args.raw_root),
            top_n=args.top_n,
            profile=args.profile,
            profile_config_path=Path(args.profile_config),
            session_config_path=Path(args.session_config),
            max_synthetic_gap_minutes=args.max_synthetic_gap_minutes,
            max_selected_market_years=args.max_selected_market_years,
            markets=set(args.markets) if args.markets else None,
            years=set(args.years) if args.years else None,
        )
        if args.json_out:
            output_path = Path(args.json_out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(_compact_stdout(report), indent=2, sort_keys=True))
        return 0 if report["status"] == "PASS" else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "stage": "phase2_readiness_raw_drilldown",
                    "status": "FAIL",
                    "failure_count": 1,
                    "failures": [str(exc)],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
