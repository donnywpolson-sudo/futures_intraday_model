from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class TimeframeSpec:
    label: str
    value: int
    unit: str
    minutes: int
    expected_source_rows: int


@dataclass(frozen=True)
class ProcessResult:
    input_path: str
    output_path: str
    market: str
    year: int
    timeframe: str
    status: str
    input_rows: int
    used_rows: int
    excluded_outside_session_rows: int
    output_rows: int


def parse_timeframe(value: str) -> TimeframeSpec:
    text = re.sub(r"[\s,]+", "", value.strip().lower())
    match = re.fullmatch(r"(\d+)([mhdw])", text)
    if not match:
        raise ValueError(f"invalid timeframe: {value!r}")

    amount = int(match.group(1))
    unit = match.group(2)
    if amount <= 0:
        raise ValueError(f"timeframe must be positive: {value!r}")

    minute_multiplier = {"m": 1, "h": 60, "d": 1440, "w": 10080}[unit]
    minutes = amount * minute_multiplier
    expected = minutes if unit in {"m", "h"} else 2
    return TimeframeSpec(
        label=f"{amount}{unit}",
        value=amount,
        unit=unit,
        minutes=minutes,
        expected_source_rows=expected,
    )


def parse_timeframes(value: str | Iterable[str]) -> list[TimeframeSpec]:
    if isinstance(value, str):
        matches = re.findall(r"(\d+)\s*([mhdwMHDW])", value)
        if not matches:
            raise ValueError("no valid timeframes found")
        return [parse_timeframe(f"{amount}{unit}") for amount, unit in matches]

    return [parse_timeframe(item) for item in value]


def build_timeframe(frame: pd.DataFrame, spec: TimeframeSpec) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    if "ts" not in frame.columns:
        raise ValueError("input frame must contain a ts column")

    data = frame.copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    data = data.sort_values("ts").reset_index(drop=True)
    data["_bucket_ts"] = _bucket_series(data, spec)
    data["_group_key"] = _group_key_series(data, spec)

    rows: list[dict[str, object]] = []
    for _, group in data.groupby("_group_key", sort=True, dropna=False):
        group = group.sort_values("ts")
        first = group.iloc[0]
        source_rows = int(len(group))
        expected_rows = spec.expected_source_rows
        complete_window = source_rows >= expected_rows
        synthetic_rows = _sum_bool(group, "is_synthetic")
        degraded_rows = _sum_bool(group, "session_data_quality_degraded")
        raw_rows = _sum_bool(group, "raw_row_present", default=True)
        roll = _any_bool(group, "roll_window_flag")
        instrument_change = _any_bool(group, "instrument_id_change_flag")
        boundary = _any_bool(group, "boundary_session_flag")
        invalid_rows = source_rows - _sum_bool(group, "causal_valid", default=True)

        if synthetic_rows or degraded_rows:
            quality = "quarantine"
        elif not complete_window or roll or instrument_change or boundary or invalid_rows:
            quality = "flagged"
        else:
            quality = "pass"

        session_id, session_date, segment_id = _session_fields(first, spec)
        rows.append(
            {
                "ts": first["_bucket_ts"],
                "market": first.get("market"),
                "year": first.get("year"),
                "symbol": first.get("symbol"),
                "instrument_id": first.get("instrument_id"),
                "session_id": session_id,
                "session_date": session_date,
                "session_segment_id": segment_id,
                "timeframe": spec.label,
                "open": group["open"].iloc[0],
                "high": group["high"].max(),
                "low": group["low"].min(),
                "close": group["close"].iloc[-1],
                "volume": group["volume"].sum(),
                "source_rows": source_rows,
                "expected_source_rows": expected_rows,
                "complete_window": bool(complete_window),
                "synthetic_rows": synthetic_rows,
                "degraded_session_rows": degraded_rows,
                "raw_row_present_rows": raw_rows,
                "invalid_causal_rows": int(invalid_rows),
                "source_has_roll_window": bool(roll),
                "source_has_instrument_change": bool(instrument_change),
                "source_has_boundary_session": bool(boundary),
                "bar_quality_status": quality,
            }
        )

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
    frame = pd.read_parquet(input_path)
    input_rows = int(len(frame))
    excluded = 0
    if not include_outside_session and "inside_session" in frame.columns:
        mask = frame["inside_session"].fillna(False).astype(bool)
        excluded = int((~mask).sum())
        frame = frame.loc[mask].copy()

    output = build_timeframe(frame, spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(output_path, index=False)

    statuses = set(output.get("bar_quality_status", pd.Series(dtype=str)).dropna())
    status = "PASS" if excluded == 0 and statuses <= {"pass"} else "WARN"
    return ProcessResult(
        input_path=str(input_path),
        output_path=str(output_path),
        market=market,
        year=year,
        timeframe=spec.label,
        status=status,
        input_rows=input_rows,
        used_rows=int(len(frame)),
        excluded_outside_session_rows=excluded,
        output_rows=int(len(output)),
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
    unique_sources: dict[str, ProcessResult] = {}
    for result in results:
        unique_sources.setdefault(result.input_path, result)

    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_path": "scripts/phase2_causal_base/build_higher_timeframe_bars.py",
        "profile": profile,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "include_outside_session": include_outside_session,
        "timeframes": [asdict(spec) for spec in timeframes],
        "summary": {
            "status_counts": status_counts,
            "source_file_count": len(unique_sources),
            "output_file_count": sum(1 for result in results if result.output_rows > 0),
            "source_input_rows": sum(result.input_rows for result in unique_sources.values()),
            "source_used_rows": sum(result.used_rows for result in unique_sources.values()),
            "source_excluded_outside_session_rows": sum(
                result.excluded_outside_session_rows for result in unique_sources.values()
            ),
        },
        "results": [asdict(result) for result in results],
    }
    (reports_root / "higher_timeframe_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (reports_root / "higher_timeframe_summary.md").write_text(
        _summary_markdown(manifest),
        encoding="utf-8",
    )


def _bucket_series(data: pd.DataFrame, spec: TimeframeSpec) -> pd.Series:
    if spec.unit in {"m", "h"}:
        return data["ts"].dt.floor(f"{spec.minutes}min")
    if spec.unit == "d":
        return pd.to_datetime(data["session_date"], utc=True, errors="coerce")
    session_dates = pd.to_datetime(data["session_date"], errors="coerce")
    return session_dates.dt.to_period("W-SUN").dt.start_time.dt.tz_localize("UTC")


def _group_key_series(data: pd.DataFrame, spec: TimeframeSpec) -> pd.Series:
    if spec.unit in {"m", "h"}:
        segment = data.get("session_segment_id", pd.Series("", index=data.index)).astype(str)
        return segment + "|" + data["_bucket_ts"].astype(str)
    if spec.unit == "d":
        return data.get("session_id", data["_bucket_ts"]).astype(str)
    return data["_bucket_ts"].astype(str)


def _session_fields(row: pd.Series, spec: TimeframeSpec) -> tuple[str | None, str | None, str | None]:
    if spec.unit == "w":
        session_date = pd.Timestamp(row["_bucket_ts"]).date().isoformat()
        return f"week_{session_date}", session_date, None
    return row.get("session_id"), row.get("session_date"), row.get("session_segment_id")


def _sum_bool(frame: pd.DataFrame, column: str, *, default: bool = False) -> int:
    if column not in frame.columns:
        return int(default) * len(frame)
    return int(frame[column].fillna(default).astype(bool).sum())


def _any_bool(frame: pd.DataFrame, column: str) -> bool:
    return bool(_sum_bool(frame, column) > 0)


def _summary_markdown(manifest: dict[str, object]) -> str:
    summary = manifest["summary"]
    assert isinstance(summary, dict)
    return "\n".join(
        [
            "# Higher Timeframe Summary",
            "",
            f"- Profile: `{manifest['profile']}`",
            f"- Source files: {summary['source_file_count']}",
            f"- Output files: {summary['output_file_count']}",
            f"- Source input rows: {summary['source_input_rows']}",
            f"- Excluded outside-session rows: {summary['source_excluded_outside_session_rows']}",
            "",
        ]
    )
