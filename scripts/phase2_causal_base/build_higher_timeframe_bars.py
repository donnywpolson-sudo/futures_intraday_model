#!/usr/bin/env python3
"""Build flag-aware higher-timeframe OHLCV bars from normalized 1-minute data."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase3_labels.build_labels import (
    DEFAULT_PROFILE_CONFIG,
    resolve_profile_inputs,
)


DEFAULT_PROFILE = "all_causal"
DEFAULT_TIMEFRAMES = "5m,15m,1h,4h,1d,1w"

REQUIRED_COLUMNS = [
    "ts",
    "market",
    "year",
    "symbol",
    "instrument_id",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "raw_row_present",
    "is_synthetic",
    "valid_ohlcv",
    "causal_valid",
    "inside_session",
    "boundary_session_flag",
    "session_data_quality_degraded",
    "session_id",
    "session_date",
    "session_segment_id",
    "roll_window_flag",
    "symbol_change_flag",
    "instrument_id_change_flag",
]

BOOL_COLUMNS = [
    "raw_row_present",
    "is_synthetic",
    "valid_ohlcv",
    "causal_valid",
    "inside_session",
    "boundary_session_flag",
    "session_data_quality_degraded",
    "roll_window_flag",
    "symbol_change_flag",
    "instrument_id_change_flag",
]

COUNT_COLUMNS = {
    "raw_row_present": "raw_row_present_rows",
    "is_synthetic": "synthetic_rows",
    "valid_ohlcv": "valid_ohlcv_rows",
    "causal_valid": "causal_valid_rows",
    "inside_session": "inside_session_rows",
    "boundary_session_flag": "boundary_session_rows",
    "session_data_quality_degraded": "degraded_session_rows",
    "roll_window_flag": "roll_window_rows",
    "symbol_change_flag": "symbol_change_rows",
    "instrument_id_change_flag": "instrument_change_rows",
}

OUTPUT_COLUMNS = [
    "ts",
    "timeframe",
    "source_timeframe",
    "market",
    "year",
    "session_id",
    "session_date",
    "session_segment_id",
    "session_segment_count",
    "timestamp_start",
    "timestamp_end",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source_rows",
    "expected_source_rows",
    "complete_window",
    "raw_row_present_rows",
    "synthetic_rows",
    "synthetic_pct",
    "valid_ohlcv_rows",
    "causal_valid_rows",
    "causal_valid_pct",
    "inside_session_rows",
    "degraded_session_rows",
    "degraded_session_pct",
    "roll_window_rows",
    "roll_window_pct",
    "symbol_change_rows",
    "instrument_change_rows",
    "boundary_session_rows",
    "source_has_synthetic",
    "source_has_degraded_session",
    "source_has_roll_window",
    "source_has_symbol_change",
    "source_has_instrument_change",
    "source_has_boundary_session",
    "source_all_valid_ohlcv",
    "source_all_causal_valid",
    "bar_quality_status",
    "symbol_first",
    "symbol_last",
    "instrument_id_first",
    "instrument_id_last",
    "instrument_id_nunique",
]


@dataclass(frozen=True)
class TimeframeSpec:
    label: str
    kind: str
    minutes: int | None
    pandas_freq: str | None
    expected_source_rows: int | None


@dataclass
class BuildResult:
    market: str
    year: int
    timeframe: str
    input_path: str
    output_path: str
    status: str = "FAIL"
    input_rows: int = 0
    used_rows: int = 0
    excluded_outside_session_rows: int = 0
    output_rows: int = 0
    clean_rows: int = 0
    flagged_rows: int = 0
    quarantine_rows: int = 0
    partial_rows: int = 0
    synthetic_source_rows: int = 0
    degraded_source_rows: int = 0
    roll_window_source_rows: int = 0
    instrument_change_source_rows: int = 0
    boundary_session_source_rows: int = 0
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else "unknown"


def parse_timeframe(value: str) -> TimeframeSpec:
    raw = value.strip().lower()
    if raw in {"1d", "d", "day", "daily"}:
        return TimeframeSpec(
            label="1d",
            kind="daily",
            minutes=None,
            pandas_freq=None,
            expected_source_rows=None,
        )
    if raw in {"1w", "w", "week", "weekly"}:
        return TimeframeSpec(
            label="1w",
            kind="weekly",
            minutes=None,
            pandas_freq=None,
            expected_source_rows=None,
        )
    if raw.endswith("min"):
        number_text = raw[:-3]
        suffix = "m"
    elif raw.endswith("m"):
        number_text = raw[:-1]
        suffix = "m"
    elif raw.endswith("h"):
        number_text = raw[:-1]
        suffix = "h"
    elif raw.endswith("w"):
        number_text = raw[:-1]
        if number_text == "1":
            return TimeframeSpec(
                label="1w",
                kind="weekly",
                minutes=None,
                pandas_freq=None,
                expected_source_rows=None,
            )
        raise ValueError(f"Unsupported timeframe: {value!r}")
    else:
        raise ValueError(f"Unsupported timeframe: {value!r}")

    if not number_text.isdigit():
        raise ValueError(f"Unsupported timeframe: {value!r}")
    number = int(number_text)
    if number <= 0:
        raise ValueError(f"Unsupported timeframe: {value!r}")

    minutes = number if suffix == "m" else number * 60
    label = f"{number}h" if suffix == "h" else f"{minutes}m"
    return TimeframeSpec(
        label=label,
        kind="intraday",
        minutes=minutes,
        pandas_freq=f"{minutes}min",
        expected_source_rows=minutes,
    )


def parse_timeframes(raw: str) -> list[TimeframeSpec]:
    raw = re.sub(r"(\d+)\s+([mhdw])\b", r"\1\2", raw.strip().lower())
    values = [item.strip() for item in re.split(r"[\s,]+", raw) if item.strip()]
    if not values:
        raise ValueError("At least one timeframe is required")
    seen: set[str] = set()
    specs: list[TimeframeSpec] = []
    for value in values:
        spec = parse_timeframe(value)
        if spec.label in seen:
            continue
        seen.add(spec.label)
        specs.append(spec)
    return specs


def _valid_ohlcv(df: pd.DataFrame) -> pd.Series:
    return (
        df[["open", "high", "low", "close"]].notna().all(axis=1)
        & df["volume"].notna()
        & (df["high"] >= df["low"])
        & df["open"].between(df["low"], df["high"], inclusive="both")
        & df["close"].between(df["low"], df["high"], inclusive="both")
        & (df["volume"] >= 0)
    )


def _pct(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return (numerator / denominator.where(denominator != 0) * 100.0).fillna(0.0)


def _quality_status(out: pd.DataFrame) -> pd.Series:
    quarantine = (
        out["source_has_degraded_session"]
        | out["source_has_instrument_change"]
        | out["source_has_boundary_session"]
        | (out["synthetic_pct"] > 20.0)
    )
    flagged = (
        out["source_has_synthetic"]
        | out["source_has_roll_window"]
        | out["source_has_symbol_change"]
        | ~out["source_all_valid_ohlcv"]
        | ~out["source_all_causal_valid"]
        | ~out["complete_window"]
    )
    status = pd.Series("clean", index=out.index, dtype="object")
    status.loc[flagged] = "flagged"
    status.loc[quarantine] = "quarantine"
    return status


def _load_input(path: Path, include_outside_session: bool) -> tuple[pd.DataFrame | None, list[str], list[str], int]:
    warnings: list[str] = []
    failures: list[str] = []
    if not path.exists():
        return None, warnings, [f"input missing: {path}"], 0

    columns = pq.ParquetFile(path).schema.names
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        return None, warnings, [f"missing input columns: {missing}"], 0

    df = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    null_ts = int(df["ts"].isna().sum())
    if null_ts:
        failures.append(f"null/unparseable ts rows={null_ts}")
    duplicate_ts = int(df["ts"].duplicated().sum())
    if duplicate_ts:
        failures.append(f"duplicate ts rows={duplicate_ts}")
    if not _valid_ohlcv(df).all():
        failures.append("invalid OHLCV rows")

    for column in BOOL_COLUMNS:
        df[column] = df[column].fillna(False).astype(bool)

    df = df.sort_values("ts", kind="mergesort").reset_index(drop=True)
    excluded = 0
    if not include_outside_session:
        outside = ~df["inside_session"]
        excluded = int(outside.sum())
        if excluded:
            warnings.append(f"excluded outside-session rows={excluded}")
        df = df.loc[~outside].reset_index(drop=True)
    if df.empty:
        failures.append("no usable rows after filters")
    return df, warnings, failures, excluded


def build_timeframe(df: pd.DataFrame, spec: TimeframeSpec) -> pd.DataFrame:
    work = df.copy()
    if spec.kind == "intraday":
        if spec.pandas_freq is None:
            raise ValueError("Intraday timeframe requires pandas_freq")
        work["bar_key"] = work["ts"].dt.floor(spec.pandas_freq)
        group_columns = ["market", "year", "session_id", "session_segment_id", "bar_key"]
    elif spec.kind == "daily":
        work["bar_key"] = work["session_id"].astype("string")
        group_columns = ["market", "year", "session_id"]
    elif spec.kind == "weekly":
        session_dates = pd.to_datetime(work["session_date"], errors="coerce")
        if session_dates.isna().any():
            raise ValueError("Weekly timeframe requires parseable session_date")
        week_start = session_dates - pd.to_timedelta(session_dates.dt.weekday, unit="D")
        work["bar_key"] = week_start.dt.strftime("%Y-%m-%d")
        group_columns = ["market", "year", "bar_key"]
    else:
        raise ValueError(f"Unsupported timeframe kind: {spec.kind!r}")

    grouped = work.groupby(group_columns, sort=False, dropna=False)
    out = grouped.agg(
        timestamp_start=("ts", "min"),
        timestamp_end=("ts", "max"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        source_rows=("ts", "size"),
        session_date_first=("session_date", "first"),
        session_date_last=("session_date", "last"),
        session_segment_id_first=("session_segment_id", "first"),
        session_segment_count=("session_segment_id", "nunique"),
        symbol_first=("symbol", "first"),
        symbol_last=("symbol", "last"),
        instrument_id_first=("instrument_id", "first"),
        instrument_id_last=("instrument_id", "last"),
        instrument_id_nunique=("instrument_id", "nunique"),
        **{
            output_column: (input_column, "sum")
            for input_column, output_column in COUNT_COLUMNS.items()
        },
    ).reset_index()

    if spec.kind == "intraday":
        out["ts"] = pd.to_datetime(out["bar_key"], utc=True)
        out["session_date"] = out["session_date_first"]
    elif spec.kind == "daily":
        out["ts"] = out["timestamp_start"]
        out["session_date"] = out["session_date_first"]
        out["session_segment_id"] = out["session_segment_id_first"]
    else:
        out["ts"] = out["timestamp_start"]
        out["session_id"] = "week_" + out["bar_key"].astype("string")
        out["session_date"] = out["bar_key"].astype("string")
        out["session_segment_id"] = out["session_id"]

    out["timeframe"] = spec.label
    out["source_timeframe"] = "1m"
    out["expected_source_rows"] = (
        spec.expected_source_rows if spec.expected_source_rows is not None else pd.NA
    )
    if spec.kind == "weekly":
        week_start = pd.to_datetime(out["session_date"], errors="coerce")
        first_session_date = pd.to_datetime(out["session_date_first"], errors="coerce")
        last_session_date = pd.to_datetime(out["session_date_last"], errors="coerce")
        week_end = week_start + pd.Timedelta(days=4)
        out["complete_window"] = (
            (first_session_date <= week_start)
            & (last_session_date >= week_end)
        )
    elif spec.expected_source_rows is None:
        out["complete_window"] = True
    else:
        out["complete_window"] = out["source_rows"].eq(spec.expected_source_rows)
    out = out.drop(
        columns=["session_date_first", "session_date_last", "session_segment_id_first"]
    )

    out["synthetic_pct"] = _pct(out["synthetic_rows"], out["source_rows"])
    out["causal_valid_pct"] = _pct(out["causal_valid_rows"], out["source_rows"])
    out["degraded_session_pct"] = _pct(out["degraded_session_rows"], out["source_rows"])
    out["roll_window_pct"] = _pct(out["roll_window_rows"], out["source_rows"])

    out["source_has_synthetic"] = out["synthetic_rows"].gt(0)
    out["source_has_degraded_session"] = out["degraded_session_rows"].gt(0)
    out["source_has_roll_window"] = out["roll_window_rows"].gt(0)
    out["source_has_symbol_change"] = out["symbol_change_rows"].gt(0)
    out["source_has_instrument_change"] = out["instrument_change_rows"].gt(0)
    out["source_has_boundary_session"] = out["boundary_session_rows"].gt(0)
    out["source_all_valid_ohlcv"] = out["valid_ohlcv_rows"].eq(out["source_rows"])
    out["source_all_causal_valid"] = out["causal_valid_rows"].eq(out["source_rows"])
    out["bar_quality_status"] = _quality_status(out)

    return out[OUTPUT_COLUMNS].sort_values("ts", kind="mergesort").reset_index(drop=True)


def _process_loaded_frame(
    df: pd.DataFrame | None,
    load_warnings: list[str],
    load_failures: list[str],
    excluded: int,
    input_path: Path,
    output_path: Path,
    *,
    market: str,
    year: int,
    spec: TimeframeSpec,
) -> BuildResult:
    result = BuildResult(
        market=market,
        year=year,
        timeframe=spec.label,
        input_path=str(input_path),
        output_path=str(output_path),
    )
    result.warnings.extend(load_warnings)
    result.failures.extend(load_failures)
    result.excluded_outside_session_rows = excluded
    if df is None:
        return result

    result.input_rows = len(df) + excluded
    result.used_rows = len(df)
    result.synthetic_source_rows = int(df["is_synthetic"].sum())
    result.degraded_source_rows = int(df["session_data_quality_degraded"].sum())
    result.roll_window_source_rows = int(df["roll_window_flag"].sum())
    result.instrument_change_source_rows = int(df["instrument_id_change_flag"].sum())
    result.boundary_session_source_rows = int(df["boundary_session_flag"].sum())
    if result.failures:
        return result

    out = build_timeframe(df, spec)
    result.output_rows = len(out)
    result.clean_rows = int(out["bar_quality_status"].eq("clean").sum())
    result.flagged_rows = int(out["bar_quality_status"].eq("flagged").sum())
    result.quarantine_rows = int(out["bar_quality_status"].eq("quarantine").sum())
    result.partial_rows = int((~out["complete_window"]).sum())
    if result.quarantine_rows:
        result.warnings.append(f"quarantine bars={result.quarantine_rows}")
    if result.flagged_rows:
        result.warnings.append(f"flagged bars={result.flagged_rows}")
    if result.partial_rows:
        result.warnings.append(f"partial bars={result.partial_rows}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    out.to_parquet(tmp_path, index=False)
    tmp_path.replace(output_path)
    result.status = "WARN" if result.warnings else "PASS"
    return result


def process_file(
    input_path: Path,
    output_path: Path,
    *,
    market: str,
    year: int,
    spec: TimeframeSpec,
    include_outside_session: bool = False,
) -> BuildResult:
    df, warnings, failures, excluded = _load_input(input_path, include_outside_session)
    return _process_loaded_frame(
        df,
        warnings,
        failures,
        excluded,
        input_path,
        output_path,
        market=market,
        year=year,
        spec=spec,
    )


def write_reports(
    results: list[BuildResult],
    reports_root: Path,
    *,
    profile: str,
    input_root: Path,
    output_root: Path,
    timeframes: list[TimeframeSpec],
    include_outside_session: bool,
) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    rows = [asdict(result) for result in results]
    source_results: dict[str, BuildResult] = {}
    for result in results:
        source_results.setdefault(result.input_path, result)
    unique_sources = list(source_results.values())
    summary = {
        "output_file_count": len(results),
        "source_file_count": len(unique_sources),
        "file_count": len(results),
        "pass_count": sum(result.status == "PASS" for result in results),
        "warn_count": sum(result.status == "WARN" for result in results),
        "fail_count": sum(bool(result.failures) for result in results),
        "source_input_rows": int(sum(result.input_rows for result in unique_sources)),
        "source_used_rows": int(sum(result.used_rows for result in unique_sources)),
        "source_excluded_outside_session_rows": int(
            sum(result.excluded_outside_session_rows for result in unique_sources)
        ),
        "source_synthetic_rows": int(
            sum(result.synthetic_source_rows for result in unique_sources)
        ),
        "source_degraded_rows": int(
            sum(result.degraded_source_rows for result in unique_sources)
        ),
        "source_roll_window_rows": int(
            sum(result.roll_window_source_rows for result in unique_sources)
        ),
        "source_instrument_change_rows": int(
            sum(result.instrument_change_source_rows for result in unique_sources)
        ),
        "source_boundary_session_rows": int(
            sum(result.boundary_session_source_rows for result in unique_sources)
        ),
        "timeframe_build_input_rows": int(sum(result.input_rows for result in results)),
        "timeframe_build_used_rows": int(sum(result.used_rows for result in results)),
        "excluded_outside_session_rows": int(
            sum(result.excluded_outside_session_rows for result in results)
        ),
        "output_rows": int(sum(result.output_rows for result in results)),
        "clean_rows": int(sum(result.clean_rows for result in results)),
        "flagged_rows": int(sum(result.flagged_rows for result in results)),
        "quarantine_rows": int(sum(result.quarantine_rows for result in results)),
        "partial_rows": int(sum(result.partial_rows for result in results)),
        "synthetic_source_rows": int(sum(result.synthetic_source_rows for result in results)),
        "degraded_source_rows": int(sum(result.degraded_source_rows for result in results)),
        "roll_window_source_rows": int(sum(result.roll_window_source_rows for result in results)),
        "instrument_change_source_rows": int(
            sum(result.instrument_change_source_rows for result in results)
        ),
        "boundary_session_source_rows": int(
            sum(result.boundary_session_source_rows for result in results)
        ),
    }
    manifest = {
        "generated_at_utc": utc_timestamp(),
        "git_commit": git_commit(),
        "profile": profile,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "timeframes": [asdict(spec) for spec in timeframes],
        "include_outside_session": include_outside_session,
        "summary": summary,
        "outputs": rows,
    }
    (reports_root / "higher_timeframe_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(rows).to_csv(reports_root / "higher_timeframe_manifest.csv", index=False)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--input-root", default="data/causally_gated_normalized")
    parser.add_argument("--output-root", default="data/higher_timeframes")
    parser.add_argument("--reports-root", default="reports/higher_timeframes")
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--timeframes", nargs="+", default=[DEFAULT_TIMEFRAMES])
    parser.add_argument("--include-outside-session", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    reports_root = Path(args.reports_root)
    profile_config = Path(args.profile_config)
    timeframes = parse_timeframes(" ".join(args.timeframes))
    inputs = resolve_profile_inputs(args.profile, input_root, profile_config)

    results: list[BuildResult] = []
    for market, year, input_path in inputs:
        df, warnings, failures, excluded = _load_input(input_path, args.include_outside_session)
        for spec in timeframes:
            output_path = output_root / spec.label / market / f"{year}.parquet"
            result = _process_loaded_frame(
                df,
                warnings,
                failures,
                excluded,
                input_path,
                output_path,
                market=market,
                year=year,
                spec=spec,
            )
            results.append(result)
            print(
                f"{result.status} {market} {year} {spec.label}: "
                f"used={result.used_rows} out={result.output_rows} "
                f"clean={result.clean_rows} flagged={result.flagged_rows} "
                f"quarantine={result.quarantine_rows} "
                f"warnings={len(result.warnings)} failures={len(result.failures)}"
            )

    write_reports(
        results,
        reports_root,
        profile=args.profile,
        input_root=input_root,
        output_root=output_root,
        timeframes=timeframes,
        include_outside_session=args.include_outside_session,
    )
    return 1 if any(result.failures for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
