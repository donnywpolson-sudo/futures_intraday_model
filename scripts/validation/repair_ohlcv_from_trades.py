#!/usr/bin/env python3
"""Repair proven trade-active OHLCV gaps from local trades DBN archives."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


TRADE_ACTIVITY_CLASSIFICATION = "trade_activity_inside_ohlcv_gap"
REPAIR_SOURCE_SCHEMA = "trades_reconstructed_ohlcv_1m"
TIMESTAMP_COLUMNS = ("ts_event", "datetime_utc", "ts", "datetime", "timestamp", "time")

TradeFrameReader = Callable[[Path, int], Iterable[pd.DataFrame]]


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"missing gap audit JSON: {_relative_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"unreadable gap audit JSON {_relative_path(path)}: {exc}"]
    if not isinstance(payload, dict):
        return None, [f"gap audit JSON must be an object: {_relative_path(path)}"]
    return payload, []


def _utc_ts(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _utc_iso(value: Any) -> str:
    return _utc_ts(value).isoformat().replace("+00:00", "Z")


def _timestamp_column(frame: pd.DataFrame) -> pd.Series:
    for column in TIMESTAMP_COLUMNS:
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index)
    raise ValueError("raw parquet missing timestamp column/index")


def _trade_timestamp_series(frame: pd.DataFrame, path: Path) -> pd.Series:
    if "ts_event" in frame.columns:
        return pd.to_datetime(frame["ts_event"], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index)
    for column in ("ts", "datetime", "datetime_utc", "timestamp", "time"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce")
    raise ValueError(f"trades frame missing timestamp column/index: {_relative_path(path)}")


def _default_trade_frame_reader(path: Path, chunk_size: int) -> Iterator[pd.DataFrame]:
    import databento as db

    store = db.DBNStore.from_file(path)
    frames = store.to_df(count=chunk_size, pretty_ts=False, map_symbols=False, schema="trades")
    if isinstance(frames, pd.DataFrame):
        yield frames
    else:
        yield from frames


def _load_raw(path: Path) -> tuple[pd.DataFrame | None, pd.Series, list[str]]:
    if not path.exists():
        return None, pd.Series(dtype="datetime64[ns, UTC]"), [f"missing raw parquet: {_relative_path(path)}"]
    try:
        frame = pd.read_parquet(path)
        return frame, _timestamp_column(frame), []
    except Exception as exc:
        return None, pd.Series(dtype="datetime64[ns, UTC]"), [
            f"unreadable raw parquet {_relative_path(path)}: {exc}"
        ]


def _target_minutes(args: argparse.Namespace, audit: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    requested_minutes = {
        _utc_iso(pd.Timestamp(value).floor("min")) for value in getattr(args, "minute", [])
    }
    tasks: list[dict[str, Any]] = []
    failures: list[str] = []
    for entry in audit.get("market_years", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("market")) != str(args.market) or int(entry.get("year") or 0) != int(args.year):
            continue
        for gap in entry.get("gap_windows", []):
            if not isinstance(gap, dict):
                continue
            if str(gap.get("classification")) != TRADE_ACTIVITY_CLASSIFICATION:
                continue
            for minute in gap.get("matched_trade_minutes", []):
                minute_iso = _utc_iso(pd.Timestamp(minute).floor("min"))
                if requested_minutes and minute_iso not in requested_minutes:
                    continue
                tasks.append(
                    {
                        "market": args.market,
                        "year": int(args.year),
                        "minute": minute_iso,
                        "gap_id": gap.get("synthetic_gap_id"),
                        "first_synthetic_ts": gap.get("first_synthetic_ts"),
                        "last_synthetic_ts": gap.get("last_synthetic_ts"),
                        "instrument_id": gap.get("instrument_id"),
                        "raw_symbol": gap.get("raw_symbol"),
                    }
                )
    if requested_minutes:
        found = {task["minute"] for task in tasks}
        missing = sorted(requested_minutes - found)
        if missing:
            failures.append("requested repair minutes were not matched failed trade-active gaps: " + ", ".join(missing))
    if not tasks:
        failures.append(f"no trade-active gap minutes found for {args.market} {args.year}")
    if len(tasks) > int(args.max_repair_minutes):
        failures.append(
            f"repair minute count {len(tasks)} exceeds --max-repair-minutes={args.max_repair_minutes}"
        )
    return tasks, failures


def _trade_archives(trades_root: Path, market: str, year: int) -> tuple[list[Path], list[str]]:
    market_year_root = trades_root / market / str(year)
    if not market_year_root.exists():
        return [], [f"missing trades archive directory: {_relative_path(market_year_root)}"]
    paths = sorted(market_year_root.glob("*.dbn.zst"))
    if not paths:
        return [], [f"no trades DBN archives found under {_relative_path(market_year_root)}"]
    return paths, []


def _resolve_adjacent_context(
    raw: pd.DataFrame,
    raw_ts: pd.Series,
    tasks: list[dict[str, Any]],
) -> tuple[pd.Series | None, list[str]]:
    failures: list[str] = []
    work = raw.copy()
    work["_repair_ts"] = raw_ts
    work = work.dropna(subset=["_repair_ts"]).sort_values("_repair_ts", kind="mergesort")
    target_minutes = [_utc_ts(task["minute"]) for task in tasks]
    if not target_minutes:
        return None, ["no target minutes"]
    first = min(target_minutes)
    last = max(target_minutes)
    existing = work[work["_repair_ts"].isin(target_minutes)]
    if not existing.empty:
        failures.append(
            "target repair minute already exists in raw OHLCV: "
            + ", ".join(_utc_iso(value) for value in existing["_repair_ts"].tolist())
        )
    before = work[work["_repair_ts"] < first].tail(1)
    after = work[work["_repair_ts"] > last].head(1)
    if before.empty or after.empty:
        failures.append("adjacent raw OHLCV context missing")
        return None, failures
    adjacent = pd.concat([before, after], ignore_index=True)
    ids = pd.to_numeric(adjacent.get("instrument_id"), errors="coerce").dropna().astype("int64")
    unique_ids = sorted(set(int(value) for value in ids.tolist()))
    if len(unique_ids) != 1:
        failures.append("adjacent raw OHLCV instrument_id unresolved")
    expected_ids = {
        int(task["instrument_id"])
        for task in tasks
        if task.get("instrument_id") is not None and str(task.get("instrument_id")) != ""
    }
    if expected_ids and unique_ids and set(unique_ids) != expected_ids:
        failures.append(
            f"adjacent raw instrument_id {unique_ids} does not match gap instrument_id {sorted(expected_ids)}"
        )
    symbols = sorted(set(adjacent.get("raw_symbol", pd.Series(dtype="object")).dropna().astype(str).tolist()))
    expected_symbols = {
        str(task["raw_symbol"]) for task in tasks if task.get("raw_symbol") is not None
    }
    if expected_symbols and symbols and set(symbols) != expected_symbols:
        failures.append(f"adjacent raw symbols {symbols} do not match gap raw_symbol {sorted(expected_symbols)}")
    if failures:
        return None, failures
    return before.iloc[0].drop(labels=["_repair_ts"], errors="ignore"), []


def _scan_trades(
    *,
    archive_paths: list[Path],
    tasks: list[dict[str, Any]],
    chunk_size: int,
    trade_frame_reader: TradeFrameReader,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], list[str]]:
    minute_keys = {str(task["minute"]) for task in tasks}
    instrument_ids = {
        int(task["instrument_id"])
        for task in tasks
        if task.get("instrument_id") is not None and str(task.get("instrument_id")) != ""
    }
    by_minute: dict[str, list[pd.DataFrame]] = {task["minute"]: [] for task in tasks}
    failures: list[str] = []
    scanned_rows = 0
    considered_rows = 0
    archives_read: list[str] = []
    archive_hashes: dict[str, str] = {}
    for path in archive_paths:
        try:
            archive_hashes[_relative_path(path)] = _file_sha256(path)
            for frame in trade_frame_reader(path, chunk_size):
                scanned_rows += int(len(frame))
                if frame.empty:
                    continue
                if "price" not in frame.columns or "size" not in frame.columns:
                    failures.append(f"trades frame missing price/size: {_relative_path(path)}")
                    continue
                work = frame.copy()
                work["_trade_ts"] = _trade_timestamp_series(work, path)
                work = work.dropna(subset=["_trade_ts"])
                work["_minute"] = work["_trade_ts"].dt.floor("min").map(_utc_iso)
                work = work[work["_minute"].isin(minute_keys)]
                if "action" in work.columns:
                    work = work[work["action"].astype(str).eq("T")]
                if instrument_ids:
                    if "instrument_id" not in work.columns:
                        failures.append(f"trades frame missing instrument_id: {_relative_path(path)}")
                        continue
                    work["instrument_id"] = pd.to_numeric(work["instrument_id"], errors="coerce")
                    work = work.dropna(subset=["instrument_id"])
                    work["instrument_id"] = work["instrument_id"].astype("int64")
                    work = work[work["instrument_id"].isin(instrument_ids)]
                if work.empty:
                    continue
                work["price"] = pd.to_numeric(work["price"], errors="coerce")
                work["size"] = pd.to_numeric(work["size"], errors="coerce")
                malformed = work[work[["price", "size", "_trade_ts"]].isna().any(axis=1)]
                if not malformed.empty:
                    failures.append(f"malformed trade rows in {_relative_path(path)}: {len(malformed)}")
                    continue
                considered_rows += int(len(work))
                for minute_iso, group in work.groupby("_minute", sort=False):
                    if str(minute_iso) in by_minute:
                        by_minute[str(minute_iso)].append(group.copy())
            archives_read.append(_relative_path(path))
        except Exception as exc:
            failures.append(f"unreadable trades archive {_relative_path(path)}: {exc}")
    frames_by_minute: dict[str, pd.DataFrame] = {}
    for minute, frames in by_minute.items():
        if not frames:
            failures.append(f"no matching trades found for repair minute {minute}")
            continue
        frames_by_minute[minute] = pd.concat(frames, ignore_index=False).sort_values(
            "_trade_ts", kind="mergesort"
        )
    return frames_by_minute, {
        "trade_rows_scanned": scanned_rows,
        "trade_rows_considered": considered_rows,
        "archives_read": archives_read,
        "archive_hashes": archive_hashes,
    }, failures


def _reconstructed_row(
    *,
    base_row: pd.Series,
    minute: str,
    trades: pd.DataFrame,
    market: str,
    year: int,
    source_files: list[str],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    row = base_row.to_dict()
    ts = _utc_ts(minute)
    prices = pd.to_numeric(trades["price"], errors="raise")
    sizes = pd.to_numeric(trades["size"], errors="raise")
    row["ts_event"] = ts
    if "datetime_utc" in row:
        row["datetime_utc"] = ts
    row["open"] = float(prices.iloc[0])
    row["high"] = float(prices.max())
    row["low"] = float(prices.min())
    row["close"] = float(prices.iloc[-1])
    volume = float(sizes.sum())
    row["volume"] = int(volume) if volume.is_integer() else volume
    row["market"] = market
    row["year"] = year
    row["source_schema"] = REPAIR_SOURCE_SCHEMA
    row["source_file"] = ";".join(source_files)
    row["source_sha256"] = ";".join(source_hashes[path] for path in source_files if path in source_hashes)
    if "data_quality_status" in row:
        row["data_quality_status"] = "available"
    if "data_quality_degraded" in row:
        row["data_quality_degraded"] = False
    return row


def build_report(
    args: argparse.Namespace,
    *,
    trade_frame_reader: TradeFrameReader | None = None,
) -> dict[str, Any]:
    audit_path = Path(args.gap_audit_json)
    audit, failures = _read_json(audit_path)
    tasks: list[dict[str, Any]] = []
    if audit is not None:
        tasks, task_failures = _target_minutes(args, audit)
        failures.extend(task_failures)

    raw_path = Path(args.raw_root) / str(args.market) / f"{int(args.year)}.parquet"
    raw, raw_ts, raw_failures = _load_raw(raw_path)
    failures.extend(raw_failures)
    output_path = Path(args.output_root) / str(args.market) / f"{int(args.year)}.parquet"
    if raw_path.resolve() == output_path.resolve():
        failures.append("output path must not overwrite canonical raw parquet")
    if output_path.exists() and not bool(getattr(args, "overwrite", False)):
        failures.append(f"output already exists; use --overwrite to replace: {_relative_path(output_path)}")

    base_row = None
    if raw is not None and not failures:
        base_row, context_failures = _resolve_adjacent_context(raw, raw_ts, tasks)
        failures.extend(context_failures)

    archive_paths: list[Path] = []
    trade_summary: dict[str, Any] = {
        "trade_rows_scanned": 0,
        "trade_rows_considered": 0,
        "archives_read": [],
        "archive_hashes": {},
    }
    trades_by_minute: dict[str, pd.DataFrame] = {}
    if not failures:
        archive_paths, archive_failures = _trade_archives(Path(args.trades_root), str(args.market), int(args.year))
        failures.extend(archive_failures)
    if not failures:
        reader = trade_frame_reader or _default_trade_frame_reader
        trades_by_minute, trade_summary, trade_failures = _scan_trades(
            archive_paths=archive_paths,
            tasks=tasks,
            chunk_size=int(args.chunk_size),
            trade_frame_reader=reader,
        )
        failures.extend(trade_failures)

    repaired_rows: list[dict[str, Any]] = []
    if not failures and raw is not None and base_row is not None:
        source_files = [path for path in trade_summary["archives_read"]]
        source_hashes = dict(trade_summary["archive_hashes"])
        new_rows = [
            _reconstructed_row(
                base_row=base_row,
                minute=task["minute"],
                trades=trades_by_minute[task["minute"]],
                market=str(args.market),
                year=int(args.year),
                source_files=source_files,
                source_hashes=source_hashes,
            )
            for task in tasks
        ]
        repaired = pd.concat([raw, pd.DataFrame(new_rows)], ignore_index=True)
        repaired["_repair_ts"] = _timestamp_column(repaired)
        repaired = repaired.sort_values("_repair_ts", kind="mergesort").drop(columns=["_repair_ts"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        repaired.to_parquet(output_path, index=False)
        for task, row in zip(tasks, new_rows):
            repaired_rows.append(
                {
                    "market": args.market,
                    "year": int(args.year),
                    "minute": task["minute"],
                    "synthetic_gap_id": task.get("gap_id"),
                    "instrument_id": task.get("instrument_id"),
                    "raw_symbol": task.get("raw_symbol"),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    "source_schema": REPAIR_SOURCE_SCHEMA,
                }
            )

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "method": "reconstruct missing 1-minute OHLCV bars only from local trades inside failed OHLCV gaps",
        "gap_audit_json": _relative_path(audit_path),
        "raw_input_path": _relative_path(raw_path),
        "trades_root": _relative_path(Path(args.trades_root)),
        "output_path": _relative_path(output_path),
        "overwrite": bool(getattr(args, "overwrite", False)),
        "failures": failures,
        "repair_tasks": tasks,
        "repaired_rows": repaired_rows,
        "trade_summary": trade_summary,
    }


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# OHLCV Trade Repair",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Status: `{report['status']}`",
        f"Output: `{report['output_path']}`",
        "",
        "## Repaired Rows",
        "",
        "| Market | Year | Minute | Instrument | Symbol | OHLCV |",
        "|---|---:|---|---:|---|---|",
    ]
    for row in report["repaired_rows"]:
        lines.append(
            "| `{market}` | {year} | `{minute}` | {instrument_id} | `{raw_symbol}` | "
            "{open}/{high}/{low}/{close} vol={volume} |".format(**row)
        )
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-audit-json", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--minute", action="append", default=[])
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--trades-root", default="data/dbn/trades")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out")
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    parser.add_argument("--max-repair-minutes", type=int, default=5)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be > 0")
    if args.max_repair_minutes <= 0:
        raise SystemExit("--max-repair-minutes must be > 0")
    report = build_report(args)
    write_json_report(report, Path(args.json_out))
    if args.md_out:
        write_markdown_report(report, Path(args.md_out))
    if report["status"] != "PASS":
        print(f"FAIL OHLCV trade repair: failures={len(report['failures'])}")
        return 1
    print(f"PASS OHLCV trade repair: repaired_rows={len(report['repaired_rows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
