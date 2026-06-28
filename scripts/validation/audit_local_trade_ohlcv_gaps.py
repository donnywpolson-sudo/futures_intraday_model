#!/usr/bin/env python3
"""Cross-check missing OHLCV minutes against local trades DBN archives."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1A_download.download_databento_raw import (  # noqa: E402
    raw_file_manifest_path,
    validate_raw_file_manifest,
)
from scripts.phase1_raw_contract import REQUIRED_DATASET, SCHEMA_PATHS  # noqa: E402


SCHEMAS_TO_VERIFY = ("ohlcv-1m", "definition", "trades")
LOCAL_TRADES_SCHEMA_ACCESS_START = "2025-06-18"
LOCAL_TRADES_SCHEMA_ACCESS_END = "2026-06-13"
VERIFIED_NO_TRADE = "verified_no_trade_rows_inside_ohlcv_gap"
TRADE_ACTIVITY = "trade_activity_inside_ohlcv_gap"
TIMESTAMP_BASIS_MISMATCH = "timestamp_basis_mismatch_with_ohlcv_source_bar"
UNVERIFIED_MISSING_COVERAGE = "unverified_missing_trade_coverage"
UNVERIFIED_CONTRACT = "unverified_unresolved_contract_context"
NO_MISSING = "no_missing_ohlcv_minutes"
PENDING = "pending_trade_scan"
CAVEAT = (
    "A passing local trades cross-check supports a Databento OHLCV no-trade "
    "convention assumption inside the configured local trades schema access "
    f"window [{LOCAL_TRADES_SCHEMA_ACCESS_START}, {LOCAL_TRADES_SCHEMA_ACCESS_END}); "
    "downstream Tier 1 data-audit policy may apply this as a dataset-wide "
    "same-market OHLCV validation assumption, but it is not direct trades proof "
    "outside the access window."
)

TradeFrameReader = Callable[[Path, int], Iterable[pd.DataFrame]]


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _utc_ts(value: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _utc_iso(ts: pd.Timestamp) -> str:
    return _utc_ts(ts).isoformat().replace("+00:00", "Z")


def _validate_local_trades_access_window(start: pd.Timestamp, end: pd.Timestamp) -> None:
    access_start = _utc_ts(LOCAL_TRADES_SCHEMA_ACCESS_START)
    access_end = _utc_ts(LOCAL_TRADES_SCHEMA_ACCESS_END)
    if start < access_start or end > access_end:
        raise ValueError(
            "requested local trades window "
            f"[{_utc_iso(start)}, {_utc_iso(end)}) is outside configured local trades schema "
            f"access window [{_utc_iso(access_start)}, {_utc_iso(access_end)})"
        )


def _timestamp_column(frame: pd.DataFrame, path: Path) -> pd.Series:
    for column in ("ts", "ts_event", "datetime", "datetime_utc", "timestamp", "time"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index)
    raise ValueError(f"missing timestamp column/index in {_relative_path(path)}")


def _read_parquet_with_ts(path: Path) -> tuple[pd.DataFrame | None, pd.Series, list[str]]:
    if not path.exists():
        return None, pd.Series(dtype="datetime64[ns, UTC]"), [f"missing input: {_relative_path(path)}"]
    try:
        frame = pd.read_parquet(path)
        return frame, _timestamp_column(frame, path), []
    except Exception as exc:
        return None, pd.Series(dtype="datetime64[ns, UTC]"), [
            f"unreadable input {_relative_path(path)}: {exc}"
        ]


def _read_yaml(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"missing profile config: {_relative_path(path)}"]
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {}, [f"unreadable profile config {_relative_path(path)}: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"profile config is not a mapping: {_relative_path(path)}"]
    return payload, []


def _resolve_profile_name(profile: str, aliases: dict[str, Any]) -> str:
    resolved = profile
    seen: set[str] = set()
    while resolved in aliases and resolved not in seen:
        seen.add(resolved)
        resolved = str(aliases[resolved])
    return resolved


def _load_scope(
    profile_config: Path,
    requested_profiles: list[str],
    market_filter: list[str] | None,
) -> tuple[dict[str, Any], list[str]]:
    payload, failures = _read_yaml(profile_config)
    profiles = payload.get("profiles", {})
    aliases = payload.get("aliases", {})
    if failures:
        return {
            "requested_profiles": requested_profiles,
            "resolved_profiles": [],
            "markets": [],
            "years": [],
            "market_filter": market_filter or [],
        }, failures
    if not isinstance(profiles, dict):
        return {}, ["profile config missing profiles mapping"]
    if not isinstance(aliases, dict):
        aliases = {}

    resolved_profiles: list[str] = []
    markets: list[str] = []
    years: list[int] = []
    for requested in requested_profiles:
        resolved = _resolve_profile_name(str(requested), aliases)
        resolved_profiles.append(resolved)
        entry = profiles.get(resolved)
        if not isinstance(entry, dict):
            failures.append(f"profile not found: {requested}")
            continue
        for market in entry.get("markets", []):
            value = str(market)
            if value not in markets:
                markets.append(value)
        for year in entry.get("years", []):
            value = int(year)
            if value not in years:
                years.append(value)

    requested_filter = [str(item) for item in market_filter or []]
    if requested_filter:
        unknown = sorted(set(requested_filter) - set(markets))
        if unknown:
            failures.append(f"market filter not in profile scope: {unknown}")
        markets = [market for market in markets if market in set(requested_filter)]

    if not markets:
        failures.append("resolved scope has no markets")
    if not years:
        failures.append("resolved scope has no years")
    return {
        "requested_profiles": requested_profiles,
        "resolved_profiles": resolved_profiles,
        "markets": markets,
        "years": sorted(years),
        "market_filter": requested_filter,
    }, failures


def _schema_root(dbn_root: Path, schema: str) -> Path:
    return dbn_root / SCHEMA_PATHS[schema]


def _load_manifest(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    manifest_path = raw_file_manifest_path(path)
    if not manifest_path.exists():
        return None, [f"missing manifest: {_relative_path(manifest_path)}"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"unreadable manifest {_relative_path(manifest_path)}: {exc}"]
    if not isinstance(payload, dict):
        return None, [f"manifest is not an object: {_relative_path(manifest_path)}"]
    return payload, []


def _manifest_interval(manifest: dict[str, Any]) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    try:
        start = _utc_ts(str(manifest["start"]))
        end = _utc_ts(str(manifest["end"]))
    except Exception:
        return None
    if end <= start:
        return None
    return start, end


def _filename_interval(path: Path) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    name = path.name.removesuffix(".dbn.zst")
    parts = name.split("_")
    if len(parts) != 2:
        return None
    try:
        start = _utc_ts(parts[0])
        end = _utc_ts(parts[1])
    except Exception:
        return None
    if end <= start:
        return None
    return start, end


def _overlaps_window(
    interval: tuple[pd.Timestamp, pd.Timestamp] | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> bool:
    if interval is None:
        return False
    interval_start, interval_end = interval
    return interval_start < end and interval_end > start


def _path_year_may_overlap(path: Path, start: pd.Timestamp, end: pd.Timestamp) -> bool:
    year = _archive_year(path)
    if year is None:
        return True
    year_start = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
    year_end = pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC")
    return year_start < end and year_end > start


def _archive_year(path: Path) -> int | None:
    try:
        return int(path.parent.name)
    except ValueError:
        return None


def _archive_rows_for_schema_market(
    dbn_root: Path,
    schema: str,
    market: str,
    requested_start: pd.Timestamp,
    requested_end: pd.Timestamp,
) -> dict[str, Any]:
    root = _schema_root(dbn_root, schema) / market
    failures: list[str] = []
    archives: list[dict[str, Any]] = []
    if not root.is_dir():
        return {
            "schema": schema,
            "market": market,
            "root": _relative_path(root),
            "status": "FAIL",
            "failures": [f"{market} {schema}: missing market directory {_relative_path(root)}"],
            "archive_count": 0,
            "invalid_manifest_count": 0,
            "valid_intervals": [],
            "selected_intervals": [],
            "coverage_gaps": [],
        }

    for path in sorted(root.rglob("*.dbn.zst")):
        archive_failures: list[str] = []
        manifest, manifest_failures = _load_manifest(path)
        interval = _manifest_interval(manifest) if manifest is not None else _filename_interval(path)
        if not _overlaps_window(interval, requested_start, requested_end) and not (
            interval is None and _path_year_may_overlap(path, requested_start, requested_end)
        ):
            continue
        if not path.is_file() or path.stat().st_size <= 0:
            archive_failures.append(f"empty archive: {_relative_path(path)}")
        year = _archive_year(path)
        archive_failures.extend(manifest_failures)
        if manifest is not None:
            archive_failures.extend(
                validate_raw_file_manifest(
                    path,
                    expected_schema=schema,
                    expected_market=market,
                    expected_year=year,
                )
            )
            interval = _manifest_interval(manifest)
            if interval is None:
                archive_failures.append(f"manifest time range invalid: {_relative_path(raw_file_manifest_path(path))}")
            elif manifest.get("dataset") != REQUIRED_DATASET:
                archive_failures.append("manifest dataset mismatch")
            elif manifest.get("schema") != schema:
                archive_failures.append("manifest schema mismatch")
            elif manifest.get("market") != market:
                archive_failures.append("manifest market mismatch")
        elif interval is None:
            archive_failures.append(f"archive interval unresolved: {_relative_path(path)}")

        row = {
            "path": _relative_path(path),
            "manifest_path": _relative_path(raw_file_manifest_path(path)),
            "file_size_bytes": path.stat().st_size if path.exists() else 0,
            "failures": archive_failures,
        }
        if interval is not None and not archive_failures:
            start, end = interval
            row["start"] = _utc_iso(start)
            row["end"] = _utc_iso(end)
        archives.append(row)
        failures.extend(f"{market} {schema}: {failure}" for failure in archive_failures)

    valid_intervals = [
        {
            "start": str(row["start"]),
            "end": str(row["end"]),
            "path": str(row["path"]),
        }
        for row in archives
        if not row["failures"] and row.get("start") and row.get("end")
    ]
    return {
        "schema": schema,
        "market": market,
        "root": _relative_path(root),
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "archive_count": len(archives),
        "invalid_manifest_count": sum(1 for row in archives if row["failures"]),
        "valid_intervals": valid_intervals,
        "selected_intervals": [],
        "coverage_gaps": [],
        "archives": archives,
    }


def _interval_bounds(interval: dict[str, Any]) -> tuple[pd.Timestamp, pd.Timestamp]:
    return _utc_ts(str(interval["start"])), _utc_ts(str(interval["end"]))


def _coverage_gaps(
    intervals: list[dict[str, Any]],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[dict[str, str]]:
    current = start
    gaps: list[dict[str, str]] = []
    ordered = sorted(intervals, key=lambda row: (_interval_bounds(row)[0], _interval_bounds(row)[1]))
    while current < end:
        candidates = [row for row in ordered if _interval_bounds(row)[0] <= current < _interval_bounds(row)[1]]
        if candidates:
            best = max(candidates, key=lambda row: _interval_bounds(row)[1])
            current = min(_interval_bounds(best)[1], end)
            continue
        future_starts = [_interval_bounds(row)[0] for row in ordered if _interval_bounds(row)[0] > current]
        gap_end = min(future_starts) if future_starts else end
        gap_end = min(gap_end, end)
        gaps.append({"start": _utc_iso(current), "end": _utc_iso(gap_end)})
        current = gap_end
    return gaps


def _select_covering_intervals(
    intervals: list[dict[str, Any]],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    current = start
    ordered = sorted(intervals, key=lambda row: (_interval_bounds(row)[0], _interval_bounds(row)[1]))
    while current < end:
        candidates = [row for row in ordered if _interval_bounds(row)[0] <= current < _interval_bounds(row)[1]]
        if not candidates:
            break
        best = max(candidates, key=lambda row: _interval_bounds(row)[1])
        selected.append(best)
        current = min(_interval_bounds(best)[1], end)
    return selected


def build_preflight(
    *,
    dbn_root: Path,
    markets: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    by_schema_market: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for schema in SCHEMAS_TO_VERIFY:
        schema_rows: dict[str, Any] = {}
        for market in markets:
            row = _archive_rows_for_schema_market(dbn_root, schema, market, start, end)
            row["coverage_gaps"] = _coverage_gaps(row["valid_intervals"], start, end)
            row["selected_intervals"] = _select_covering_intervals(row["valid_intervals"], start, end)
            if row["coverage_gaps"]:
                row["failures"].append(
                    f"{market} {schema}: uncovered requested window segments={len(row['coverage_gaps'])}"
                )
            row["status"] = "FAIL" if row["failures"] else "PASS"
            failures.extend(row["failures"])
            schema_rows[market] = row
        by_schema_market[schema] = schema_rows
    return {
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "schemas": list(SCHEMAS_TO_VERIFY),
        "markets": markets,
        "requested_window": {"start": _utc_iso(start), "end": _utc_iso(end)},
        "by_schema_market": by_schema_market,
    }


def _years_in_window(years: list[int], start: pd.Timestamp, end: pd.Timestamp) -> list[int]:
    selected: list[int] = []
    for year in years:
        year_start = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
        year_end = pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC")
        if year_start < end and year_end > start:
            selected.append(year)
    return selected


def _year_window(year: int, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    year_start = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
    year_end = pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC")
    return max(start, year_start), min(end, year_end)


def _prepare_raw_context(raw: pd.DataFrame, raw_ts: pd.Series) -> pd.DataFrame:
    work = raw.copy()
    work["_ts"] = raw_ts
    return work.dropna(subset=["_ts"]).sort_values("_ts", kind="mergesort").reset_index(drop=True)


def _series_values(frame: pd.DataFrame, columns: list[str]) -> list[Any]:
    for column in columns:
        if column in frame.columns:
            return frame[column].dropna().tolist()
    return []


def _resolve_adjacent_contract(
    raw_context: pd.DataFrame,
    first_ts: pd.Timestamp,
    last_ts: pd.Timestamp,
) -> dict[str, Any]:
    if raw_context.empty:
        before = pd.DataFrame()
        after = pd.DataFrame()
    else:
        ts = raw_context["_ts"]
        before_pos = int(ts.searchsorted(first_ts, side="left")) - 1
        after_pos = int(ts.searchsorted(last_ts, side="right"))
        before = raw_context.iloc[[before_pos]] if before_pos >= 0 else pd.DataFrame()
        after = raw_context.iloc[[after_pos]] if after_pos < len(raw_context) else pd.DataFrame()
    adjacent = pd.concat([before, after], ignore_index=True)
    symbols = sorted(set(str(value) for value in _series_values(adjacent, ["raw_symbol", "symbol"])))
    instrument_ids = sorted(
        set(
            int(value)
            for value in pd.to_numeric(adjacent.get("instrument_id"), errors="coerce")
            .dropna()
            .astype("int64")
            .tolist()
        )
    )
    source_files = sorted(set(str(value) for value in _series_values(adjacent, ["source_file"])))
    source_hashes = sorted(set(str(value) for value in _series_values(adjacent, ["source_sha256"])))
    return {
        "status": "resolved" if len(symbols) == 1 and len(instrument_ids) == 1 else "ambiguous_or_missing",
        "raw_symbol": symbols[0] if len(symbols) == 1 else None,
        "raw_symbols": symbols,
        "instrument_id": instrument_ids[0] if len(instrument_ids) == 1 else None,
        "instrument_ids": instrument_ids,
        "before_ts": _utc_iso(pd.Timestamp(before["_ts"].iloc[0])) if not before.empty else None,
        "after_ts": _utc_iso(pd.Timestamp(after["_ts"].iloc[0])) if not after.empty else None,
        "raw_ohlcv_source_files": source_files,
        "raw_ohlcv_source_hashes": source_hashes,
    }


def _synthetic_work_frame(causal: pd.DataFrame, causal_ts: pd.Series, raw_ts: pd.Series) -> pd.DataFrame:
    synthetic = causal.loc[causal["is_synthetic"].fillna(False).astype(bool)]
    columns = [column for column in ("synthetic_gap_id", "synthetic_gap_size_minutes") if column in synthetic.columns]
    work = synthetic.loc[:, columns].reset_index(drop=True).copy()
    work["_ts"] = causal_ts.loc[synthetic.index].reset_index(drop=True)
    work = work.dropna(subset=["_ts"]).sort_values("_ts", kind="mergesort").reset_index(drop=True)
    raw_values = set(int(pd.Timestamp(value).value) for value in raw_ts.dropna().dt.floor("min").tolist())
    work_values = work["_ts"].map(lambda value: int(pd.Timestamp(value).floor("min").value))
    return work.loc[~work_values.isin(raw_values)].reset_index(drop=True)


def _group_synthetic_minutes(work: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    if work.empty:
        return []
    grouped = work.copy()
    if "synthetic_gap_id" in grouped.columns and grouped["synthetic_gap_id"].notna().all():
        grouped["_gap_id"] = grouped["synthetic_gap_id"].astype(str)
        return [(str(gap_id), group.copy()) for gap_id, group in grouped.groupby("_gap_id", sort=False)]

    gap_ids: list[str] = []
    current_id = 1
    previous_ts: pd.Timestamp | None = None
    for value in grouped["_ts"]:
        ts = pd.Timestamp(value)
        if previous_ts is not None and ts != previous_ts + pd.Timedelta(minutes=1):
            current_id += 1
        gap_ids.append(f"generated_gap_{current_id:06d}")
        previous_ts = ts
    grouped["_gap_id"] = gap_ids
    return [(str(gap_id), group.copy()) for gap_id, group in grouped.groupby("_gap_id", sort=False)]


def _gap_window(
    *,
    market: str,
    year: int,
    gap_id: str,
    group: pd.DataFrame,
    context: dict[str, Any],
    coverage_failures: list[str],
) -> dict[str, Any]:
    ts = pd.to_datetime(group["_ts"], utc=True, errors="coerce").dropna().sort_values()
    minutes = sorted(set(int(pd.Timestamp(value).value) for value in ts.dt.floor("min").tolist()))
    classification = PENDING
    failures: list[str] = []
    if coverage_failures:
        classification = UNVERIFIED_MISSING_COVERAGE
        failures.extend(coverage_failures)
    elif context["status"] != "resolved":
        classification = UNVERIFIED_CONTRACT
        failures.append("adjacent contract context unresolved")
    return {
        "market": market,
        "year": year,
        "synthetic_gap_id": gap_id,
        "first_synthetic_ts": _utc_iso(pd.Timestamp(ts.min())),
        "last_synthetic_ts": _utc_iso(pd.Timestamp(ts.max())),
        "missing_minute_count": len(minutes),
        "missing_minute_keys": minutes,
        "instrument_id": context.get("instrument_id"),
        "raw_symbol": context.get("raw_symbol"),
        "contract_context": context,
        "classification": classification,
        "trade_rows_inside_ohlcv_gap": 0,
        "ts_event_trade_rows_inside_ohlcv_gap": 0,
        "ts_recv_trade_rows_inside_ohlcv_gap": 0,
        "timestamp_basis_mismatch_rows": 0,
        "matched_trade_minutes": [],
        "matched_ts_event_minutes": [],
        "matched_ts_recv_minutes": [],
        "ts_recv_ohlcv_source_match_minutes": [],
        "timestamp_basis_evaluations": [],
        "timestamp_basis_match": None,
        "missing_ohlcv_trade_gap": None,
        "failures": failures,
    }


def _default_trade_frame_reader(path: Path, chunk_size: int) -> Iterator[pd.DataFrame]:
    import databento as db

    store = db.DBNStore.from_file(path)
    frames = store.to_df(count=chunk_size, pretty_ts=False, map_symbols=False, schema="trades")
    if isinstance(frames, pd.DataFrame):
        yield frames
    else:
        yield from frames


def _trade_timestamp_series(frame: pd.DataFrame, path: Path) -> pd.Series:
    if "ts_event" in frame.columns:
        return pd.to_datetime(frame["ts_event"], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index)
    return _timestamp_column(frame, path)


def _floor_ns_minute(values: pd.Series) -> pd.Series:
    return (pd.to_numeric(values, errors="coerce") // 60_000_000_000 * 60_000_000_000).astype("Int64")


def _datetime_minute_ns(values: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(values, utc=True, errors="coerce").dt.floor("min")
    return timestamps.map(lambda value: pd.NA if pd.isna(value) else int(pd.Timestamp(value).value)).astype("Int64")


def _trade_event_minute_series(frame: pd.DataFrame, path: Path) -> pd.Series:
    if "ts_event" in frame.columns and pd.api.types.is_numeric_dtype(frame["ts_event"]):
        return _floor_ns_minute(frame["ts_event"])
    return _datetime_minute_ns(_trade_timestamp_series(frame, path))


def _trade_recv_minute_series(frame: pd.DataFrame) -> pd.Series:
    if "ts_recv" in frame.columns and pd.api.types.is_numeric_dtype(frame["ts_recv"]):
        return _floor_ns_minute(frame["ts_recv"])
    if "ts_recv" in frame.columns:
        return _datetime_minute_ns(frame["ts_recv"])
    if frame.index.name == "ts_recv" and pd.api.types.is_numeric_dtype(frame.index):
        return _floor_ns_minute(pd.Series(frame.index, index=frame.index))
    if isinstance(frame.index, pd.DatetimeIndex):
        return _datetime_minute_ns(pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index))
    return pd.Series(pd.NA, index=frame.index, dtype="Int64")


def _context_ohlcv_minutes(context: dict[str, Any]) -> set[int]:
    minutes: set[int] = set()
    for key in ("before_ts", "after_ts"):
        value = context.get(key)
        if value:
            minutes.add(int(_utc_ts(str(value)).floor("min").value))
    return minutes


def _minute_iso_from_ns(value: int | None) -> str | None:
    if value is None:
        return None
    return _utc_iso(pd.Timestamp(int(value), unit="ns", tz="UTC"))


def _scan_trade_archives(
    *,
    archive_paths: list[Path],
    gaps: list[dict[str, Any]],
    chunk_size: int,
    trade_frame_reader: TradeFrameReader,
) -> dict[str, Any]:
    pending_indexes = [idx for idx, gap in enumerate(gaps) if gap["classification"] == PENDING]
    minute_to_gap_indexes: dict[int, list[int]] = defaultdict(list)
    required_ids = {
        int(gaps[idx]["instrument_id"])
        for idx in pending_indexes
        if gaps[idx].get("instrument_id") is not None
    }
    missing_minute_key_set = set(minute_to_gap_indexes)
    for idx in pending_indexes:
        for minute in gaps[idx]["missing_minute_keys"]:
            minute_to_gap_indexes[int(minute)].append(idx)
            missing_minute_key_set.add(int(minute))

    scanned_rows = 0
    considered_rows = 0
    archives_read: list[str] = []
    failures: list[str] = []
    matched_minutes_by_gap: dict[int, set[str]] = defaultdict(set)
    matched_event_minutes_by_gap: dict[int, set[str]] = defaultdict(set)
    matched_recv_minutes_by_gap: dict[int, set[str]] = defaultdict(set)
    source_match_recv_minutes_by_gap: dict[int, set[str]] = defaultdict(set)
    for path in archive_paths:
        try:
            for frame in trade_frame_reader(path, chunk_size):
                scanned_rows += int(len(frame))
                if frame.empty:
                    continue
                if required_ids and "instrument_id" not in frame.columns:
                    failures.append(f"trade frame missing instrument_id: {_relative_path(path)}")
                    continue
                work = pd.DataFrame(
                    {
                        "ts_event_minute": _trade_event_minute_series(frame, path),
                        "ts_recv_minute": _trade_recv_minute_series(frame),
                    }
                )
                if "instrument_id" in frame.columns:
                    work["instrument_id"] = pd.to_numeric(frame["instrument_id"], errors="coerce")
                else:
                    work["instrument_id"] = pd.NA
                if required_ids:
                    work = work.dropna(subset=["instrument_id"])
                    work["instrument_id"] = work["instrument_id"].astype("int64")
                    work = work[work["instrument_id"].isin(required_ids)]
                work = work.dropna(subset=["ts_event_minute"], how="all")
                if work.empty:
                    continue
                work["ts_event_minute"] = work["ts_event_minute"].astype("Int64")
                work["ts_recv_minute"] = work["ts_recv_minute"].astype("Int64")
                event_matches = work["ts_event_minute"].isin(missing_minute_key_set)
                recv_matches = work["ts_recv_minute"].isin(missing_minute_key_set)
                work = work.loc[event_matches | recv_matches].copy()
                considered_rows += int(len(work))
                if work.empty:
                    continue
                for row in work.itertuples(index=False):
                    instrument_id = getattr(row, "instrument_id")
                    event_minute = (
                        int(getattr(row, "ts_event_minute"))
                        if pd.notna(getattr(row, "ts_event_minute"))
                        else None
                    )
                    recv_minute = (
                        int(getattr(row, "ts_recv_minute")) if pd.notna(getattr(row, "ts_recv_minute")) else None
                    )
                    candidate_gap_indexes = set()
                    if event_minute is not None:
                        candidate_gap_indexes.update(minute_to_gap_indexes.get(event_minute, []))
                    if recv_minute is not None:
                        candidate_gap_indexes.update(minute_to_gap_indexes.get(recv_minute, []))
                    for gap_idx in candidate_gap_indexes:
                        gap_id = gaps[gap_idx].get("instrument_id")
                        if pd.notna(instrument_id) and gap_id is not None and int(instrument_id) != int(gap_id):
                            continue
                        missing_minutes = set(int(minute) for minute in gaps[gap_idx]["missing_minute_keys"])
                        event_in_gap = event_minute in missing_minutes if event_minute is not None else False
                        recv_in_gap = recv_minute in missing_minutes if recv_minute is not None else False
                        source_match = (
                            recv_minute in _context_ohlcv_minutes(gaps[gap_idx]["contract_context"])
                            if recv_minute is not None
                            else False
                        )
                        if event_in_gap and event_minute is not None:
                            gaps[gap_idx]["ts_event_trade_rows_inside_ohlcv_gap"] += 1
                            matched_event_minutes_by_gap[gap_idx].add(_minute_iso_from_ns(event_minute) or "")
                        if recv_in_gap and recv_minute is not None:
                            gaps[gap_idx]["ts_recv_trade_rows_inside_ohlcv_gap"] += 1
                            gaps[gap_idx]["trade_rows_inside_ohlcv_gap"] += 1
                            matched_recv_minutes_by_gap[gap_idx].add(_minute_iso_from_ns(recv_minute) or "")
                            matched_minutes_by_gap[gap_idx].add(_minute_iso_from_ns(recv_minute) or "")
                        elif event_in_gap and recv_minute is None:
                            gaps[gap_idx]["trade_rows_inside_ohlcv_gap"] += 1
                            matched_minutes_by_gap[gap_idx].add(_minute_iso_from_ns(event_minute) or "")
                        elif event_in_gap and source_match:
                            gaps[gap_idx]["timestamp_basis_mismatch_rows"] += 1
                            if recv_minute is not None:
                                source_match_recv_minutes_by_gap[gap_idx].add(_minute_iso_from_ns(recv_minute) or "")
                        elif event_in_gap:
                            gaps[gap_idx]["trade_rows_inside_ohlcv_gap"] += 1
                            matched_minutes_by_gap[gap_idx].add(_minute_iso_from_ns(event_minute) or "")
                        if event_in_gap or recv_in_gap:
                            gaps[gap_idx]["timestamp_basis_evaluations"].append(
                                {
                                    "ts_event_minute": _minute_iso_from_ns(event_minute),
                                    "ts_recv_minute": _minute_iso_from_ns(recv_minute),
                                    "ts_event_in_missing_gap": event_in_gap,
                                    "ts_recv_in_missing_gap": recv_in_gap,
                                    "ts_recv_matches_adjacent_ohlcv_source_bar": source_match,
                                }
                            )
            archives_read.append(_relative_path(path))
        except Exception as exc:
            failures.append(f"unreadable trades archive {_relative_path(path)}: {exc}")

    if failures:
        for idx in pending_indexes:
            gaps[idx]["classification"] = UNVERIFIED_MISSING_COVERAGE
            gaps[idx]["failures"].extend(failures)
    else:
        for idx in pending_indexes:
            gaps[idx]["matched_trade_minutes"] = sorted(matched_minutes_by_gap[idx])
            gaps[idx]["matched_ts_event_minutes"] = sorted(matched_event_minutes_by_gap[idx])
            gaps[idx]["matched_ts_recv_minutes"] = sorted(matched_recv_minutes_by_gap[idx])
            gaps[idx]["ts_recv_ohlcv_source_match_minutes"] = sorted(source_match_recv_minutes_by_gap[idx])
            if int(gaps[idx]["trade_rows_inside_ohlcv_gap"]) > 0:
                gaps[idx]["classification"] = TRADE_ACTIVITY
                gaps[idx]["timestamp_basis_match"] = "missing_gap"
                gaps[idx]["missing_ohlcv_trade_gap"] = True
                gaps[idx]["failures"].append("trade rows found inside missing OHLCV minute")
            elif int(gaps[idx]["timestamp_basis_mismatch_rows"]) > 0:
                gaps[idx]["classification"] = TIMESTAMP_BASIS_MISMATCH
                gaps[idx]["timestamp_basis_match"] = "ts_recv"
                gaps[idx]["missing_ohlcv_trade_gap"] = False
            else:
                gaps[idx]["classification"] = VERIFIED_NO_TRADE
                gaps[idx]["timestamp_basis_match"] = "no_trade"
                gaps[idx]["missing_ohlcv_trade_gap"] = False
    return {
        "trade_rows_scanned": scanned_rows,
        "trade_rows_considered": considered_rows,
        "archives_read": archives_read,
        "failures": failures,
    }


def _market_year_coverage_failures(
    preflight: dict[str, Any],
    market: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[str]:
    failures: list[str] = []
    for schema in SCHEMAS_TO_VERIFY:
        row = preflight["by_schema_market"][schema][market]
        gaps = _coverage_gaps(row["valid_intervals"], start, end)
        if gaps:
            failures.append(f"{market} {schema}: uncovered market-year audit window")
        failures.extend(row.get("failures", []))
    return failures


def _selected_trade_paths(
    preflight: dict[str, Any],
    market: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[Path]:
    row = preflight["by_schema_market"]["trades"][market]
    return [
        Path(str(interval["path"]))
        for interval in _select_covering_intervals(row["valid_intervals"], start, end)
    ]


def _raw_path_for_market_year(
    raw_root: Path,
    raw_overlay_root: Path | None,
    market: str,
    year: int,
) -> Path:
    if raw_overlay_root is not None:
        overlay_path = raw_overlay_root / market / f"{year}.parquet"
        if overlay_path.exists():
            return overlay_path
    return raw_root / market / f"{year}.parquet"


def audit_market_year(
    *,
    market: str,
    year: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
    raw_root: Path,
    raw_overlay_root: Path | None,
    causal_root: Path,
    preflight: dict[str, Any],
    chunk_size: int,
    max_gap_windows: int | None,
    trade_frame_reader: TradeFrameReader,
) -> dict[str, Any]:
    raw_path = _raw_path_for_market_year(raw_root, raw_overlay_root, market, year)
    causal_path = causal_root / market / f"{year}.parquet"
    failures = _market_year_coverage_failures(preflight, market, start, end)
    raw, raw_ts, raw_failures = _read_parquet_with_ts(raw_path)
    causal, causal_ts, causal_failures = _read_parquet_with_ts(causal_path)
    failures.extend(raw_failures)
    failures.extend(causal_failures)
    if raw is None or causal is None:
        return {
            "market": market,
            "year": year,
            "status": "FAIL",
            "failures": failures,
            "paths": {"raw": _relative_path(raw_path), "causal": _relative_path(causal_path)},
            "gap_windows": [],
            "summary": {
                "synthetic_gap_count": 0,
                "missing_minute_count": 0,
                "verified_empty_minutes": 0,
                "failed_minutes": 0,
                "unverified_minutes": 0,
                "trade_rows_scanned": 0,
                "archives_read": 0,
            },
        }
    if "is_synthetic" not in causal.columns:
        failures.append(f"missing is_synthetic column: {_relative_path(causal_path)}")
        return {
            "market": market,
            "year": year,
            "status": "FAIL",
            "failures": failures,
            "paths": {"raw": _relative_path(raw_path), "causal": _relative_path(causal_path)},
            "gap_windows": [],
            "summary": {
                "synthetic_gap_count": 0,
                "missing_minute_count": 0,
                "verified_empty_minutes": 0,
                "failed_minutes": 0,
                "unverified_minutes": 0,
                "trade_rows_scanned": 0,
                "archives_read": 0,
            },
        }

    raw_window_ts = raw_ts.loc[raw_ts.ge(start) & raw_ts.lt(end)]
    causal_window = causal.loc[causal_ts.ge(start) & causal_ts.lt(end)].copy()
    causal_window_ts = causal_ts.loc[causal_window.index]
    work = _synthetic_work_frame(causal_window, causal_window_ts, raw_window_ts)
    raw_context = _prepare_raw_context(raw, raw_ts)
    gap_windows: list[dict[str, Any]] = []
    for gap_id, group in _group_synthetic_minutes(work):
        if max_gap_windows is not None and len(gap_windows) >= max_gap_windows:
            break
        ts = pd.to_datetime(group["_ts"], utc=True, errors="coerce").dropna()
        context = _resolve_adjacent_contract(raw_context, pd.Timestamp(ts.min()), pd.Timestamp(ts.max()))
        coverage_failures = failures if failures else []
        gap_windows.append(
            _gap_window(
                market=market,
                year=year,
                gap_id=gap_id,
                group=group,
                context=context,
                coverage_failures=coverage_failures,
            )
        )

    trade_scan = {
        "trade_rows_scanned": 0,
        "trade_rows_considered": 0,
        "archives_read": [],
        "failures": [],
    }
    if gap_windows and not failures:
        trade_scan = _scan_trade_archives(
            archive_paths=_selected_trade_paths(preflight, market, start, end),
            gaps=gap_windows,
            chunk_size=chunk_size,
            trade_frame_reader=trade_frame_reader,
        )
        failures.extend(trade_scan["failures"])

    classification_counts = Counter(str(gap["classification"]) for gap in gap_windows)
    missing_minutes = sum(int(gap["missing_minute_count"]) for gap in gap_windows)
    failed_minutes = sum(
        int(gap["missing_minute_count"]) for gap in gap_windows if gap["classification"] == TRADE_ACTIVITY
    )
    unverified_minutes = sum(
        int(gap["missing_minute_count"])
        for gap in gap_windows
        if str(gap["classification"]).startswith("unverified_")
    )
    verified_empty_minutes = sum(
        int(gap["missing_minute_count"]) for gap in gap_windows if gap["classification"] == VERIFIED_NO_TRADE
    )
    timestamp_basis_mismatch_minutes = sum(
        int(gap["missing_minute_count"]) for gap in gap_windows if gap["classification"] == TIMESTAMP_BASIS_MISMATCH
    )
    status = "PASS"
    if failures or failed_minutes or unverified_minutes:
        status = "FAIL"
    return {
        "market": market,
        "year": year,
        "status": status,
        "failures": failures,
        "paths": {"raw": _relative_path(raw_path), "causal": _relative_path(causal_path)},
        "window": {"start": _utc_iso(start), "end": _utc_iso(end)},
        "no_missing_ohlcv_minutes": not gap_windows,
        "gap_windows": [
            {key: value for key, value in gap.items() if key != "missing_minute_keys"}
            for gap in gap_windows
        ],
        "classification_counts": dict(sorted(classification_counts.items())),
        "summary": {
            "synthetic_gap_count": len(gap_windows),
            "missing_minute_count": missing_minutes,
            "verified_empty_minutes": verified_empty_minutes,
            "timestamp_basis_mismatch_minutes": timestamp_basis_mismatch_minutes,
            "failed_minutes": failed_minutes,
            "unverified_minutes": unverified_minutes,
            "trade_rows_scanned": trade_scan["trade_rows_scanned"],
            "trade_rows_considered": trade_scan["trade_rows_considered"],
            "archives_read": len(trade_scan["archives_read"]),
        },
    }


def build_report(
    args: argparse.Namespace,
    *,
    trade_frame_reader: TradeFrameReader | None = None,
) -> dict[str, Any]:
    start = _utc_ts(str(args.start))
    end = _utc_ts(str(args.end))
    if end <= start:
        raise ValueError("--end must be after --start")
    _validate_local_trades_access_window(start, end)
    if int(args.chunk_size) <= 0:
        raise ValueError("--chunk-size must be > 0")
    if args.max_gap_windows is not None and int(args.max_gap_windows) <= 0:
        raise ValueError("--max-gap-windows must be > 0")

    scope, scope_failures = _load_scope(
        Path(args.profile_config),
        [str(profile) for profile in args.profiles],
        [str(market) for market in args.markets] if args.markets else None,
    )
    markets = list(scope.get("markets", []))
    years = _years_in_window([int(year) for year in scope.get("years", [])], start, end)
    failures = list(scope_failures)
    if not years:
        failures.append("no profile years overlap requested window")
    preflight = build_preflight(
        dbn_root=Path(args.dbn_root),
        markets=markets,
        start=start,
        end=end,
    ) if markets else {
        "status": "FAIL",
        "failures": ["no markets to preflight"],
        "schemas": list(SCHEMAS_TO_VERIFY),
        "markets": [],
        "requested_window": {"start": _utc_iso(start), "end": _utc_iso(end)},
        "by_schema_market": {schema: {} for schema in SCHEMAS_TO_VERIFY},
    }
    failures.extend(preflight["failures"])

    entries: list[dict[str, Any]] = []
    if not bool(args.inventory_only):
        reader = trade_frame_reader or _default_trade_frame_reader
        for market in markets:
            for year in years:
                year_start, year_end = _year_window(year, start, end)
                if year_start >= year_end:
                    continue
                entries.append(
                    audit_market_year(
                        market=market,
                        year=year,
                        start=year_start,
                        end=year_end,
                        raw_root=Path(args.raw_root),
                        raw_overlay_root=Path(args.raw_overlay_root)
                        if getattr(args, "raw_overlay_root", None)
                        else None,
                        causal_root=Path(args.causal_root),
                        preflight=preflight,
                        chunk_size=int(args.chunk_size),
                        max_gap_windows=args.max_gap_windows,
                        trade_frame_reader=reader,
                    )
                )

    status = "FAIL" if failures or any(entry["status"] != "PASS" for entry in entries) else "PASS"
    summary = {
        "market_count": len(markets),
        "year_count": len(years),
        "market_year_count": len(entries),
        "status_counts": dict(sorted(Counter(entry["status"] for entry in entries).items())),
        "synthetic_gap_count": sum(int(entry["summary"]["synthetic_gap_count"]) for entry in entries),
        "missing_minute_count": sum(int(entry["summary"]["missing_minute_count"]) for entry in entries),
        "verified_empty_minutes": sum(int(entry["summary"]["verified_empty_minutes"]) for entry in entries),
        "timestamp_basis_mismatch_minutes": sum(
            int(entry["summary"].get("timestamp_basis_mismatch_minutes", 0)) for entry in entries
        ),
        "failed_minutes": sum(int(entry["summary"]["failed_minutes"]) for entry in entries),
        "unverified_minutes": sum(int(entry["summary"]["unverified_minutes"]) for entry in entries),
        "trade_rows_scanned": sum(int(entry["summary"]["trade_rows_scanned"]) for entry in entries),
        "archives_read": sum(int(entry["summary"]["archives_read"]) for entry in entries),
    }
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": status,
        "failures": failures,
        "method": "local trades DBN cross-check of OHLCV synthetic missing minutes",
        "caveat": CAVEAT,
        "inventory_only": bool(args.inventory_only),
        "scope": scope,
        "window": {"start": _utc_iso(start), "end": _utc_iso(end)},
        "local_trades_schema_access": {
            "start": _utc_iso(_utc_ts(LOCAL_TRADES_SCHEMA_ACCESS_START)),
            "end": _utc_iso(_utc_ts(LOCAL_TRADES_SCHEMA_ACCESS_END)),
        },
        "dbn_root": _relative_path(Path(args.dbn_root)),
        "raw_root": _relative_path(Path(args.raw_root)),
        "raw_overlay_root": _relative_path(Path(args.raw_overlay_root))
        if getattr(args, "raw_overlay_root", None)
        else None,
        "causal_root": _relative_path(Path(args.causal_root)),
        "chunk_size": int(args.chunk_size),
        "max_gap_windows": args.max_gap_windows,
        "preflight": preflight,
        "summary": summary,
        "market_years": entries,
    }


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Local Trades OHLCV Gap Cross-Check",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Status: `{report['status']}`",
        f"Window: `{report['window']['start']}` to `{report['window']['end']}`",
        f"Inventory only: `{report['inventory_only']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in report["summary"].items():
        lines.append(f"| `{key}` | {value} |")
    if report["market_years"]:
        lines.extend(
            [
                "",
                "## Market-Years",
                "",
                "| Market | Year | Status | Gaps | Missing min | Verified empty | Failed min | Unverified min | Trades scanned | Archives |",
                "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for entry in report["market_years"]:
            summary = entry["summary"]
            lines.append(
                "| `{market}` | {year} | `{status}` | {gaps} | {missing} | {verified} | {failed} | {unverified} | {scanned} | {archives} |".format(
                    market=entry["market"],
                    year=entry["year"],
                    status=entry["status"],
                    gaps=summary["synthetic_gap_count"],
                    missing=summary["missing_minute_count"],
                    verified=summary["verified_empty_minutes"],
                    failed=summary["failed_minutes"],
                    unverified=summary["unverified_minutes"],
                    scanned=summary["trade_rows_scanned"],
                    archives=summary["archives_read"],
                )
            )
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    lines.extend(["", "## Caveat", "", str(report["caveat"])])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-config", default="configs/alpha_tiered.yaml")
    parser.add_argument("--profiles", nargs="+", default=["tier_3_holdout", "tier_3_forward"])
    parser.add_argument("--markets", nargs="*")
    parser.add_argument("--start", default=LOCAL_TRADES_SCHEMA_ACCESS_START)
    parser.add_argument("--end", default=LOCAL_TRADES_SCHEMA_ACCESS_END)
    parser.add_argument("--dbn-root", default="data/dbn")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--raw-overlay-root")
    parser.add_argument("--causal-root", default=None)
    parser.add_argument("--json-out", default="reports/pipeline_audit/local_trade_ohlcv_gap_crosscheck_2025_2026.json")
    parser.add_argument("--md-out", default="reports/pipeline_audit/local_trade_ohlcv_gap_crosscheck_2025_2026.md")
    parser.add_argument("--chunk-size", type=int, default=250_000)
    parser.add_argument("--max-gap-windows", type=int)
    parser.add_argument("--inventory-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.causal_root is None:
        parser.error("--causal-root is required; pass an explicit causal root")
    report = build_report(args)
    write_json_report(report, Path(args.json_out))
    if args.md_out:
        write_markdown_report(report, Path(args.md_out))
    print(
        "status={status} inventory_only={inventory_only} markets={markets} "
        "market_years={market_years} gaps={gaps} missing_minutes={missing} "
        "failed_minutes={failed} unverified_minutes={unverified}".format(
            status=report["status"],
            inventory_only=report["inventory_only"],
            markets=report["summary"]["market_count"],
            market_years=report["summary"]["market_year_count"],
            gaps=report["summary"]["synthetic_gap_count"],
            missing=report["summary"]["missing_minute_count"],
            failed=report["summary"]["failed_minutes"],
            unverified=report["summary"]["unverified_minutes"],
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
