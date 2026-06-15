from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.validation.audit_raw_session_gaps import _bucket_synthetic_timestamps, _top_counts


LOW_LIQUIDITY_BUCKETS = {
    "outside_configured_session",
    "configured_evening_17_18_ct",
    "overnight_19_05_ct",
    "first_60m_after_configured_open",
    "last_60m_before_configured_close",
}


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _utc_iso(ts: pd.Timestamp) -> str:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").isoformat().replace("+00:00", "Z")


def _timestamp_column(frame: pd.DataFrame) -> pd.Series:
    for column in ("ts", "ts_event", "datetime", "datetime_utc", "timestamp", "time"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index)
    raise ValueError("missing timestamp column/index")


def _read_parquet_with_ts(path: Path) -> tuple[pd.DataFrame | None, pd.Series, list[str]]:
    if not path.exists():
        return None, pd.Series(dtype="datetime64[ns, UTC]"), [f"missing input: {_relative_path(path)}"]
    try:
        frame = pd.read_parquet(path)
        return frame, _timestamp_column(frame), []
    except Exception as exc:
        return None, pd.Series(dtype="datetime64[ns, UTC]"), [f"unreadable input {_relative_path(path)}: {exc}"]


def _session_bucket_counts(metadata: pd.DataFrame) -> list[dict[str, Any]]:
    return _top_counts(metadata.get("session_bucket", pd.Series(dtype="string")), "bucket")


def _active_rows(bucket_counts: list[dict[str, Any]]) -> int:
    return sum(int(row["rows"]) for row in bucket_counts if row["bucket"] not in LOW_LIQUIDITY_BUCKETS)


def _resolve_adjacent_contract(
    raw: pd.DataFrame,
    raw_ts: pd.Series,
    first_ts: pd.Timestamp,
    last_ts: pd.Timestamp,
) -> dict[str, Any]:
    work = raw.copy()
    work["_ts"] = raw_ts
    work = work.dropna(subset=["_ts"]).sort_values("_ts", kind="mergesort")
    before = work[work["_ts"] < first_ts].tail(1)
    after = work[work["_ts"] > last_ts].head(1)
    adjacent = pd.concat([before, after], ignore_index=True)
    symbols = sorted(set(adjacent.get("raw_symbol", pd.Series(dtype="object")).dropna().astype(str)))
    instrument_ids = sorted(
        set(
            int(value)
            for value in pd.to_numeric(adjacent.get("instrument_id"), errors="coerce")
            .dropna()
            .astype("int64")
            .tolist()
        )
    )
    status = "resolved" if len(symbols) == 1 and len(instrument_ids) == 1 else "ambiguous_or_missing"
    return {
        "status": status,
        "raw_symbol": symbols[0] if len(symbols) == 1 else None,
        "raw_symbols": symbols,
        "instrument_id": instrument_ids[0] if len(instrument_ids) == 1 else None,
        "instrument_ids": instrument_ids,
        "before_ts": _utc_iso(pd.Timestamp(before["_ts"].iloc[0])) if not before.empty else None,
        "after_ts": _utc_iso(pd.Timestamp(after["_ts"].iloc[0])) if not after.empty else None,
    }


def _csv_name(task: dict[str, Any]) -> str:
    raw_symbol = task.get("raw_symbol") or "UNRESOLVED"
    gap_id = str(task["synthetic_gap_id"]).replace("/", "_")
    return f"{task['market']}_{task['year']}_{raw_symbol}_{gap_id}.csv"


def _build_tasks_for_market_year(
    *,
    market: str,
    year: int,
    raw_root: Path,
    causal_root: Path,
    session_config: Path,
    external_root: Path,
    max_windows_per_market_year: int,
    buffer_minutes: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    raw_path = raw_root / market / f"{year}.parquet"
    causal_path = causal_root / market / f"{year}.parquet"
    raw, raw_ts, raw_failures = _read_parquet_with_ts(raw_path)
    causal, causal_ts, causal_failures = _read_parquet_with_ts(causal_path)
    failures = raw_failures + causal_failures
    if not session_config.exists():
        failures.append(f"missing session config: {_relative_path(session_config)}")
    if failures or raw is None or causal is None:
        return [], failures
    if "is_synthetic" not in causal.columns:
        return [], [f"missing is_synthetic column: {_relative_path(causal_path)}"]

    synthetic_mask = causal["is_synthetic"].fillna(False).astype(bool)
    synthetic = causal.loc[synthetic_mask].copy()
    synthetic_ts = causal_ts.loc[synthetic_mask]
    if synthetic.empty:
        return [], []
    if "synthetic_gap_id" not in synthetic.columns:
        synthetic["synthetic_gap_id"] = range(1, len(synthetic) + 1)
    if "synthetic_gap_size_minutes" not in synthetic.columns:
        synthetic["synthetic_gap_size_minutes"] = 1

    metadata = _bucket_synthetic_timestamps(synthetic_ts, market, session_config).reset_index(drop=True)
    work = synthetic.reset_index(drop=True).copy()
    work["_ts"] = synthetic_ts.reset_index(drop=True)
    work["_session_bucket"] = metadata.get("session_bucket", pd.Series(dtype="string"))
    work["_ct_hour"] = metadata.get("ct_hour", pd.Series(dtype="Int64"))
    work["_session_date"] = metadata.get("session_date", pd.Series(dtype="string"))

    tasks: list[dict[str, Any]] = []
    for gap_id, group in work.groupby("synthetic_gap_id", sort=False):
        ts = pd.to_datetime(group["_ts"], utc=True, errors="coerce").dropna()
        if ts.empty:
            continue
        first_ts = pd.Timestamp(ts.min())
        last_ts = pd.Timestamp(ts.max())
        bucket_counts = [
            {"bucket": str(bucket), "rows": int(rows)}
            for bucket, rows in Counter(group["_session_bucket"].dropna().astype(str)).most_common()
        ]
        active_rows = _active_rows(bucket_counts)
        gap_size = int(pd.to_numeric(group["synthetic_gap_size_minutes"], errors="coerce").max() or len(group))
        task = {
            "market": market,
            "year": year,
            "synthetic_gap_id": str(gap_id),
            "gap_size_minutes": gap_size,
            "synthetic_rows": int(len(group)),
            "first_synthetic_ts": _utc_iso(first_ts),
            "last_synthetic_ts": _utc_iso(last_ts),
            "query_start_utc": _utc_iso(first_ts - pd.Timedelta(minutes=buffer_minutes)),
            "query_end_utc": _utc_iso(last_ts + pd.Timedelta(minutes=buffer_minutes + 1)),
            "source_gap_timestamps": [_utc_iso(pd.Timestamp(value)) for value in ts.tolist()],
            "session_bucket_counts": bucket_counts,
            "ct_hour_buckets": [
                {"ct_hour": str(hour), "rows": int(rows)}
                for hour, rows in Counter(group["_ct_hour"].dropna().astype(str)).most_common()
            ],
            "session_dates": sorted(set(group["_session_date"].dropna().astype(str))),
            "active_session_rows": active_rows,
            "active_session_share": float(active_rows / len(group)) if len(group) else 0.0,
            "raw_symbol": None,
            "raw_symbols": [],
            "instrument_id": None,
            "instrument_ids": [],
            "contract_resolution_status": "not_resolved",
            "adjacent_before_ts": None,
            "adjacent_after_ts": None,
            "external_csv_expected": None,
            "external_status": "not_checked",
            "external_bar_count_in_gap": None,
            "decision": "needs_external_ohlcv_export",
            "reason": "cross_check_missing_ohlcv_minutes_against_independent_ohlcv_source",
        }
        task["external_csv_expected"] = _relative_path(external_root / _csv_name(task))
        tasks.append(task)

    tasks.sort(
        key=lambda row: (
            -int(row["active_session_rows"] > 0),
            -float(row["active_session_share"]),
            -int(row["gap_size_minutes"]),
            str(row["first_synthetic_ts"]),
        )
    )
    selected = tasks[:max_windows_per_market_year]
    for task in selected:
        contract = _resolve_adjacent_contract(
            raw,
            raw_ts,
            pd.Timestamp(str(task["first_synthetic_ts"])),
            pd.Timestamp(str(task["last_synthetic_ts"])),
        )
        task["raw_symbol"] = contract["raw_symbol"]
        task["raw_symbols"] = contract["raw_symbols"]
        task["instrument_id"] = contract["instrument_id"]
        task["instrument_ids"] = contract["instrument_ids"]
        task["contract_resolution_status"] = contract["status"]
        task["adjacent_before_ts"] = contract["before_ts"]
        task["adjacent_after_ts"] = contract["after_ts"]
        task["external_csv_expected"] = _relative_path(external_root / _csv_name(task))
    return selected, []


def _audit_external_csv(task: dict[str, Any], external_root: Path) -> None:
    csv_path = external_root / _csv_name(task)
    task["external_csv_expected"] = _relative_path(csv_path)
    if not csv_path.exists():
        task["external_status"] = "missing_external_csv"
        task["decision"] = "needs_external_ohlcv_export"
        return
    try:
        frame = pd.read_csv(csv_path)
        ts = _timestamp_column(frame).dt.floor("min")
    except Exception as exc:
        task["external_status"] = f"unreadable_external_csv: {exc}"
        task["decision"] = "external_ohlcv_inconclusive"
        return
    gap_ts = pd.to_datetime(pd.Series(task["source_gap_timestamps"]), utc=True, errors="coerce").dt.floor("min")
    gap_values = set(gap_ts.dropna().astype("int64").tolist())
    external_values = set(ts.dropna().astype("int64").tolist())
    present = sorted(gap_values.intersection(external_values))
    task["external_bar_count_in_gap"] = len(present)
    if present:
        task["external_status"] = "external_ohlcv_bar_present_in_gap"
        task["decision"] = "external_source_disagrees_keep_quarantined_or_backfill"
    else:
        task["external_status"] = "external_ohlcv_bar_absent_in_gap"
        task["decision"] = "external_ohlcv_absence_supports_empty_minute_assumption_for_sample"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    raw_root = Path(args.raw_root)
    causal_root = Path(args.causal_root)
    session_config = Path(args.session_config)
    external_root = Path(args.external_root)
    tasks: list[dict[str, Any]] = []
    failures: list[str] = []
    for market in args.markets:
        for year in args.years:
            market_tasks, market_failures = _build_tasks_for_market_year(
                market=market,
                year=int(year),
                raw_root=raw_root,
                causal_root=causal_root,
                session_config=session_config,
                external_root=external_root,
                max_windows_per_market_year=int(args.max_windows_per_market_year),
                buffer_minutes=int(args.buffer_minutes),
            )
            tasks.extend(market_tasks)
            failures.extend(f"{market} {year}: {failure}" for failure in market_failures)
    for task in tasks:
        _audit_external_csv(task, external_root)

    if args.require_external and any(task["external_status"] == "missing_external_csv" for task in tasks):
        failures.append("required external CSV exports are missing")
    decisions = Counter(str(task["decision"]) for task in tasks)
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "method": "sample missing OHLCV windows and compare against user-provided independent OHLCV CSV exports",
        "raw_root": _relative_path(raw_root),
        "causal_root": _relative_path(causal_root),
        "session_config": _relative_path(session_config),
        "external_root": _relative_path(external_root),
        "require_external": bool(args.require_external),
        "csv_contract": {
            "one_file_per_task": True,
            "required_timestamp_columns_any_of": ["ts", "ts_event", "datetime", "datetime_utc", "timestamp", "time"],
            "timestamp_timezone": "UTC preferred; timestamps are parsed as UTC",
            "expected_filename_field": "external_csv_expected",
        },
        "summary": {
            "task_count": len(tasks),
            "decision_counts": dict(sorted(decisions.items())),
        },
        "tasks": tasks,
    }


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# External OHLCV Gap Cross-Check",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Status: `{report['status']}`",
        "",
        "| Market | Year | Symbol | Gap | Start | End | Gap min | Active rows | External status | Decision | CSV |",
        "|---|---:|---|---|---|---|---:|---:|---|---|---|",
    ]
    for task in report["tasks"]:
        lines.append(
            "| `{market}` | {year} | `{symbol}` | `{gap}` | {start} | {end} | {gap_min} | "
            "{active} | `{status}` | `{decision}` | `{csv}` |".format(
                market=task["market"],
                year=task["year"],
                symbol=task.get("raw_symbol") or "UNRESOLVED",
                gap=task["synthetic_gap_id"],
                start=task["query_start_utc"],
                end=task["query_end_utc"],
                gap_min=task["gap_size_minutes"],
                active=task["active_session_rows"],
                status=task["external_status"],
                decision=task["decision"],
                csv=task["external_csv_expected"],
            )
        )
    lines.extend(
        [
            "",
            "Caveat: independent OHLCV absence supports, but does not prove, no-trade minutes.",
        ]
    )
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markets", nargs="+", required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--causal-root", default="data/causally_gated_normalized")
    parser.add_argument("--session-config", default="configs/market_sessions.yaml")
    parser.add_argument("--external-root", default="data/external_ohlcv_gap_checks")
    parser.add_argument("--json-out", default="reports/pipeline_audit/external_ohlcv_gap_crosscheck.json")
    parser.add_argument("--md-out", default="reports/pipeline_audit/external_ohlcv_gap_crosscheck.md")
    parser.add_argument("--max-windows-per-market-year", type=int, default=2)
    parser.add_argument("--buffer-minutes", type=int, default=2)
    parser.add_argument("--require-external", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_report(args)
    write_json_report(report, Path(args.json_out))
    write_markdown_report(report, Path(args.md_out))
    if report["status"] != "PASS":
        print(f"FAIL external OHLCV gap cross-check: failures={len(report['failures'])}")
        return 1
    print(
        "PASS external OHLCV gap cross-check: "
        f"tasks={report['summary']['task_count']} decisions={report['summary']['decision_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
