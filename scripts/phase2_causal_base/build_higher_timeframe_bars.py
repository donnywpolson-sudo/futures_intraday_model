#!/usr/bin/env python3
"""Build higher-timeframe bars from Phase 2 causal 1-minute bars."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class TimeframeSpec:
    label: str
    value: int
    unit: str
    pandas_freq: str


@dataclass
class ProcessResult:
    input_path: str
    output_path: str
    market: str
    year: int
    timeframe: str
    status: str
    input_rows: int
    used_rows: int
    output_rows: int
    excluded_outside_session_rows: int


def parse_timeframe(value: str) -> TimeframeSpec:
    cleaned = value.strip().lower().replace(" ", "")
    if len(cleaned) < 2 or not cleaned[:-1].isdigit():
        raise ValueError(f"invalid timeframe: {value!r}")
    amount = int(cleaned[:-1])
    unit = cleaned[-1]
    if amount <= 0 or unit not in {"m", "h", "d", "w"}:
        raise ValueError(f"invalid timeframe: {value!r}")
    freq_unit = {"m": "min", "h": "h", "d": "D", "w": "W"}[unit]
    return TimeframeSpec(
        label=f"{amount}{unit}",
        value=amount,
        unit=unit,
        pandas_freq=f"{amount}{freq_unit}",
    )


def parse_timeframes(value: str | Iterable[str]) -> list[TimeframeSpec]:
    if isinstance(value, str):
        tokens = value.replace(",", " ").split()
    else:
        tokens = [str(item) for item in value]
    specs: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index].lower()
        if token.isdigit() and index + 1 < len(tokens) and tokens[index + 1].lower() in {"m", "h", "d", "w"}:
            specs.append(token + tokens[index + 1].lower())
            index += 2
        else:
            specs.append(token)
            index += 1
    return [parse_timeframe(item) for item in specs]


def _bool_sum(frame: pd.DataFrame, column: str) -> int:
    if column not in frame:
        return 0
    return int(frame[column].fillna(False).astype(bool).sum())


def _first_value(frame: pd.DataFrame, column: str) -> object:
    if column not in frame or frame.empty:
        return None
    return frame[column].iloc[0]


def _quality_status(row: dict[str, object]) -> str:
    if int(row["synthetic_rows"]) or int(row["degraded_session_rows"]):
        return "quarantine"
    flagged = (
        not bool(row["complete_window"])
        or bool(row["source_has_roll_window"])
        or bool(row["source_has_symbol_change"])
        or bool(row["source_has_instrument_id_change"])
        or bool(row["source_has_boundary_session"])
        or int(row["causal_invalid_rows"]) > 0
    )
    return "flagged" if flagged else "pass"


def _aggregate_group(key: object, frame: pd.DataFrame, spec: TimeframeSpec) -> dict[str, object]:
    frame = frame.sort_values("ts")
    expected = spec.value if spec.unit == "m" else spec.value * 60 if spec.unit == "h" else max(len(frame), 2)
    row: dict[str, object] = {
        "ts": frame["ts"].iloc[0],
        "bar_start": key[0] if isinstance(key, tuple) else key,
        "market": _first_value(frame, "market"),
        "year": _first_value(frame, "year"),
        "symbol": _first_value(frame, "symbol"),
        "instrument_id": _first_value(frame, "instrument_id"),
        "session_id": _first_value(frame, "session_id"),
        "session_date": _first_value(frame, "session_date"),
        "session_segment_id": _first_value(frame, "session_segment_id"),
        "open": frame["open"].iloc[0],
        "high": frame["high"].max(),
        "low": frame["low"].min(),
        "close": frame["close"].iloc[-1],
        "volume": frame["volume"].sum(),
        "source_rows": int(len(frame)),
        "expected_source_rows": int(expected),
        "complete_window": bool(len(frame) >= expected),
        "synthetic_rows": _bool_sum(frame, "is_synthetic"),
        "degraded_session_rows": _bool_sum(frame, "session_data_quality_degraded"),
        "raw_row_present_rows": _bool_sum(frame, "raw_row_present"),
        "causal_valid_rows": _bool_sum(frame, "causal_valid"),
        "causal_invalid_rows": int(len(frame) - _bool_sum(frame, "causal_valid")),
        "source_has_roll_window": bool(_bool_sum(frame, "roll_window_flag")),
        "source_has_symbol_change": bool(_bool_sum(frame, "symbol_change_flag")),
        "source_has_instrument_id_change": bool(_bool_sum(frame, "instrument_id_change_flag")),
        "source_has_boundary_session": bool(_bool_sum(frame, "boundary_session_flag")),
    }
    row["bar_quality_status"] = _quality_status(row)
    return row


def _group_keys(df: pd.DataFrame, spec: TimeframeSpec) -> pd.Series:
    if spec.unit in {"m", "h"}:
        return df["ts"].dt.floor(spec.pandas_freq).astype(str) + "|" + df["session_segment_id"].astype(str)
    if spec.unit == "d":
        return df["session_id"].astype(str)
    session_date = pd.to_datetime(df["session_date"])
    week_start = session_date.dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    return "week_" + week_start.astype(str)


def build_timeframe(df: pd.DataFrame, spec: TimeframeSpec) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    working = df.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True)
    keys = _group_keys(working, spec)
    rows = []
    for key, frame in working.groupby(keys, sort=True):
        row = _aggregate_group(key, frame, spec)
        if spec.unit == "w":
            row["session_id"] = key
            row["session_date"] = str(key).replace("week_", "")
        rows.append(row)
    return pd.DataFrame(rows)


def process_file(
    input_path: Path,
    output_path: Path,
    *,
    market: str,
    year: int,
    spec: TimeframeSpec,
    include_outside_session: bool = False,
) -> ProcessResult:
    df = pd.read_parquet(input_path)
    input_rows = len(df)
    if include_outside_session or "inside_session" not in df:
        used = df
        excluded = 0
    else:
        mask = df["inside_session"].fillna(False).astype(bool)
        used = df.loc[mask].copy()
        excluded = int((~mask).sum())

    out = build_timeframe(used, spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)
    status = "PASS"
    if excluded or (not out.empty and (out["bar_quality_status"] != "pass").any()):
        status = "WARN"
    return ProcessResult(
        input_path=input_path.as_posix(),
        output_path=output_path.as_posix(),
        market=market,
        year=year,
        timeframe=spec.label,
        status=status,
        input_rows=input_rows,
        used_rows=len(used),
        output_rows=len(out),
        excluded_outside_session_rows=excluded,
    )


def write_reports(
    results: list[ProcessResult],
    reports_root: Path,
    *,
    profile: str,
    input_root: Path,
    output_root: Path,
    timeframes: list[TimeframeSpec],
    include_outside_session: bool,
) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    by_input: dict[str, ProcessResult] = {}
    for result in results:
        by_input.setdefault(result.input_path, result)
    manifest = {
        "profile": profile,
        "input_root": input_root.as_posix(),
        "output_root": output_root.as_posix(),
        "timeframes": [spec.label for spec in timeframes],
        "include_outside_session": include_outside_session,
        "summary": {
            "output_file_count": len(results),
            "source_file_count": len(by_input),
            "source_input_rows": sum(item.input_rows for item in by_input.values()),
            "source_used_rows": sum(item.used_rows for item in by_input.values()),
            "source_excluded_outside_session_rows": sum(
                item.excluded_outside_session_rows for item in by_input.values()
            ),
        },
        "outputs": [asdict(result) for result in results],
    }
    (reports_root / "higher_timeframe_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--market", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--timeframe", default="5m")
    args = parser.parse_args()
    process_file(
        Path(args.input),
        Path(args.output),
        market=args.market,
        year=args.year,
        spec=parse_timeframe(args.timeframe),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
