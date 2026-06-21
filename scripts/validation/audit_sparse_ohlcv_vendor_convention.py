#!/usr/bin/env python3
"""Audit trade-derived sparse OHLCV convention from local Databento DBN files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

DEFAULT_MARKETS = ("SR1", "SR3")
DEFAULT_DIRECT_YEARS = (2025, 2026)
DEFAULT_ASSUMED_HISTORY_YEARS = tuple(range(2018, 2025))
DEFAULT_DBN_ROOT = Path("data/dbn")
DATABENTO_OHLCV_DOCS_URL = "https://databento.com/docs/schemas-and-data-formats/ohlcv"

FrameReader = Callable[[Path], pd.DataFrame]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbn-root", default=str(DEFAULT_DBN_ROOT))
    parser.add_argument("--markets", nargs="+", default=list(DEFAULT_MARKETS))
    parser.add_argument("--direct-years", nargs="+", type=int, default=list(DEFAULT_DIRECT_YEARS))
    parser.add_argument(
        "--assumed-history-years",
        nargs="+",
        type=int,
        default=list(DEFAULT_ASSUMED_HISTORY_YEARS),
    )
    parser.add_argument("--json-out")
    return parser


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _default_frame_reader(path: Path) -> pd.DataFrame:
    import databento as db

    return db.DBNStore.from_file(path).to_df(pretty_ts=True, map_symbols=False)


def _time_series(frame: pd.DataFrame, *, prefer_index: bool) -> pd.Series:
    if prefer_index and isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(frame.index, index=frame.index)
    if "ts_event" in frame.columns:
        return pd.to_datetime(frame["ts_event"], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(frame.index, index=frame.index)
    return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")


def aggregate_trades_to_ohlcv(trades: pd.DataFrame) -> pd.DataFrame:
    required = {"instrument_id", "price", "size"}
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError("trades frame missing columns: " + ", ".join(missing))
    work = trades.copy()
    # Databento documents OHLCV intervals as based on ts_recv from trade messages.
    work["_minute"] = pd.to_datetime(
        _time_series(work, prefer_index=True), utc=True, errors="coerce"
    ).dt.floor("min")
    work["_row_order"] = range(len(work))
    work = work.dropna(subset=["_minute", "instrument_id", "price", "size"])
    if work.empty:
        return pd.DataFrame(
            columns=["ts_event", "instrument_id", "open", "high", "low", "close", "volume"]
        )
    sort_cols = ["_minute", "instrument_id", "_row_order"]
    if "sequence" in work.columns:
        sort_cols = ["_minute", "instrument_id", "sequence", "_row_order"]
    work = work.sort_values(sort_cols, kind="mergesort")
    grouped = work.groupby(["_minute", "instrument_id"], sort=True)
    return grouped.agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
    ).reset_index(names=["ts_event", "instrument_id"])


def normalize_ohlcv(ohlcv: pd.DataFrame) -> pd.DataFrame:
    required = {"instrument_id", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(ohlcv.columns))
    if missing:
        raise ValueError("ohlcv frame missing columns: " + ", ".join(missing))
    work = ohlcv.copy()
    work["ts_event"] = pd.to_datetime(
        _time_series(work, prefer_index=False), utc=True, errors="coerce"
    ).dt.floor("min")
    work = work.dropna(subset=["ts_event", "instrument_id"])
    return work[
        ["ts_event", "instrument_id", "open", "high", "low", "close", "volume"]
    ].reset_index(drop=True)


def compare_trade_ohlcv_frames(
    trades: pd.DataFrame,
    ohlcv: pd.DataFrame,
    *,
    price_tolerance: float = 1e-9,
) -> dict[str, Any]:
    trade_bars = aggregate_trades_to_ohlcv(trades)
    ohlcv_bars = normalize_ohlcv(ohlcv)
    if trade_bars.empty:
        return {
            "status": "FAIL",
            "trade_bar_count": 0,
            "ohlcv_bar_count": int(len(ohlcv_bars)),
            "failures": ["no trade bars available for direct convention audit"],
        }
    start = trade_bars["ts_event"].min()
    end = trade_bars["ts_event"].max()
    ohlcv_window = ohlcv_bars[
        ohlcv_bars["ts_event"].ge(start) & ohlcv_bars["ts_event"].le(end)
    ].copy()
    key_cols = ["ts_event", "instrument_id"]
    trade_keys = set(map(tuple, trade_bars[key_cols].itertuples(index=False, name=None)))
    ohlcv_keys = set(map(tuple, ohlcv_window[key_cols].itertuples(index=False, name=None)))
    missing_ohlcv = sorted(trade_keys - ohlcv_keys)
    extra_ohlcv = sorted(ohlcv_keys - trade_keys)
    merged = trade_bars.merge(
        ohlcv_window,
        on=key_cols,
        how="inner",
        suffixes=("_trade", "_ohlcv"),
    )
    mismatch_rows = []
    for _, row in merged.iterrows():
        mismatches = []
        for column in ("open", "high", "low", "close"):
            if abs(float(row[f"{column}_trade"]) - float(row[f"{column}_ohlcv"])) > price_tolerance:
                mismatches.append(column)
        if int(row["volume_trade"]) != int(row["volume_ohlcv"]):
            mismatches.append("volume")
        if mismatches:
            mismatch_rows.append(
                {
                    "ts_event": pd.Timestamp(row["ts_event"]).isoformat(),
                    "instrument_id": int(row["instrument_id"]),
                    "mismatched_fields": mismatches,
                }
            )
    failures = []
    if missing_ohlcv:
        failures.append(f"trade minutes missing OHLCV bars: {len(missing_ohlcv)}")
    if extra_ohlcv:
        failures.append(f"OHLCV bars without matching trade minutes: {len(extra_ohlcv)}")
    if mismatch_rows:
        failures.append(f"OHLCV values differ from trade aggregation: {len(mismatch_rows)}")
    return {
        "status": "FAIL" if failures else "PASS",
        "trade_bar_count": int(len(trade_bars)),
        "ohlcv_bar_count": int(len(ohlcv_window)),
        "overlap_start": pd.Timestamp(start).isoformat(),
        "overlap_end": pd.Timestamp(end).isoformat(),
        "missing_ohlcv_bar_count": len(missing_ohlcv),
        "extra_ohlcv_bar_count": len(extra_ohlcv),
        "value_mismatch_count": len(mismatch_rows),
        "mismatch_samples": mismatch_rows[:10],
        "failures": failures,
    }


def _dbn_paths(dbn_root: Path, schema_dir: str, market: str, year: int) -> list[Path]:
    return sorted((dbn_root / schema_dir / market / str(year)).glob("*.dbn.zst"))


def _read_concat(paths: list[Path], frame_reader: FrameReader) -> pd.DataFrame:
    frames = [frame_reader(path) for path in paths]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=False)


def audit_market_year(
    *,
    dbn_root: Path,
    market: str,
    year: int,
    frame_reader: FrameReader = _default_frame_reader,
) -> dict[str, Any]:
    trade_paths = _dbn_paths(dbn_root, "trades", market, year)
    ohlcv_paths = _dbn_paths(dbn_root, "ohlcv_1m", market, year)
    row: dict[str, Any] = {
        "market": market,
        "year": year,
        "trade_paths": [_relative_path(path) for path in trade_paths],
        "ohlcv_paths": [_relative_path(path) for path in ohlcv_paths],
        "trade_file_count": len(trade_paths),
        "ohlcv_file_count": len(ohlcv_paths),
    }
    failures = []
    if not trade_paths:
        failures.append("missing trades DBN archives")
    if not ohlcv_paths:
        failures.append("missing ohlcv_1m DBN archives")
    if failures:
        row.update({"status": "FAIL", "failures": failures})
        return row
    try:
        comparison = compare_trade_ohlcv_frames(
            _read_concat(trade_paths, frame_reader),
            _read_concat(ohlcv_paths, frame_reader),
        )
    except Exception as exc:
        row.update({"status": "FAIL", "failures": [str(exc)]})
        return row
    row.update(comparison)
    return row


def build_sparse_ohlcv_convention_report(
    *,
    dbn_root: Path,
    markets: list[str],
    direct_years: list[int],
    assumed_history_years: list[int],
    frame_reader: FrameReader = _default_frame_reader,
) -> dict[str, Any]:
    direct_rows = [
        audit_market_year(
            dbn_root=dbn_root,
            market=market,
            year=year,
            frame_reader=frame_reader,
        )
        for market in markets
        for year in direct_years
    ]
    failures = [
        failure
        for row in direct_rows
        for failure in row.get("failures", [])
    ]
    return {
        "stage": "sparse_ohlcv_vendor_convention_audit",
        "status": "FAIL" if failures else "PASS",
        "policy": "DIRECT_TRADE_VALIDATED_FOR_CHECKED_YEARS_ASSUMPTION_BACKED_FOR_HISTORY",
        "vendor_reference": {
            "url": DATABENTO_OHLCV_DOCS_URL,
            "summary": (
                "Databento documents OHLCV bars as trade aggregates and states "
                "that no OHLCV record is printed when no trade occurs in an interval."
            ),
        },
        "dbn_root": _relative_path(dbn_root),
        "markets": sorted(markets),
        "direct_trade_validated_years": sorted(direct_years),
        "assumed_history_years": sorted(assumed_history_years),
        "ready_to_rebuild_tier3_phase2": False,
        "direct_evidence": direct_rows,
        "assumption_extension": {
            "status": (
                "ASSUMPTION_BACKED_NOT_DIRECTLY_TRADE_VALIDATED"
                if not failures
                else "BLOCKED_DIRECT_EVIDENCE_FAILED"
            ),
            "markets": sorted(markets),
            "years": sorted(assumed_history_years),
            "caveat": (
                "This supports interpreting missing historical sparse OHLCV intervals "
                "as no-trade gaps under the same vendor schema. It does not reconstruct "
                "missing bars and does not prove every historical minute from trades."
            ),
        },
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_sparse_ohlcv_convention_report(
        dbn_root=Path(args.dbn_root),
        markets=[str(item) for item in args.markets],
        direct_years=[int(item) for item in args.direct_years],
        assumed_history_years=[int(item) for item in args.assumed_history_years],
    )
    if args.json_out:
        json_out = Path(args.json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
