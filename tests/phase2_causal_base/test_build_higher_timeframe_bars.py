from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase2_causal_base.build_higher_timeframe_bars import (
    build_timeframe,
    parse_timeframe,
    parse_timeframes,
    process_file,
    write_reports,
)


def _row(
    ts: str,
    *,
    open_price: float,
    session_id: str = "2024-01-02",
    session_date: str = "2024-01-02",
    session_segment_id: str = "2024-01-02_rth",
    is_synthetic: bool = False,
    degraded: bool = False,
    roll: bool = False,
    instrument_change: bool = False,
    boundary: bool = False,
    inside_session: bool = True,
) -> dict[str, object]:
    return {
        "ts": pd.Timestamp(ts),
        "market": "ES",
        "year": 2024,
        "symbol": "ES.v.0",
        "instrument_id": 123,
        "open": open_price,
        "high": open_price + 0.5,
        "low": open_price - 0.5,
        "close": open_price + 0.25,
        "volume": 10,
        "raw_row_present": not is_synthetic,
        "is_synthetic": is_synthetic,
        "valid_ohlcv": True,
        "causal_valid": not (is_synthetic or degraded or roll or instrument_change or boundary),
        "inside_session": inside_session,
        "boundary_session_flag": boundary,
        "session_data_quality_degraded": degraded,
        "session_id": session_id,
        "session_date": session_date,
        "session_segment_id": session_segment_id,
        "roll_window_flag": roll,
        "symbol_change_flag": False,
        "instrument_id_change_flag": instrument_change,
    }


def test_5m_bars_aggregate_ohlcv_and_source_flags() -> None:
    rows = [
        _row("2024-01-02T15:00:00Z", open_price=100.0),
        _row("2024-01-02T15:01:00Z", open_price=101.0),
        _row("2024-01-02T15:02:00Z", open_price=102.0, is_synthetic=True),
        _row("2024-01-02T15:03:00Z", open_price=103.0, degraded=True),
        _row("2024-01-02T15:04:00Z", open_price=104.0),
        _row("2024-01-02T15:05:00Z", open_price=105.0),
    ]
    out = build_timeframe(pd.DataFrame(rows), parse_timeframe("5m"))

    assert len(out) == 2
    first = out.iloc[0]
    assert first["open"] == 100.0
    assert first["high"] == 104.5
    assert first["low"] == 99.5
    assert first["close"] == 104.25
    assert first["volume"] == 50
    assert first["source_rows"] == 5
    assert first["complete_window"] == True
    assert first["synthetic_rows"] == 1
    assert first["degraded_session_rows"] == 1
    assert first["raw_row_present_rows"] == 4
    assert first["bar_quality_status"] == "quarantine"

    second = out.iloc[1]
    assert second["source_rows"] == 1
    assert second["complete_window"] == False
    assert second["bar_quality_status"] == "flagged"


def test_15m_bars_aggregate_ohlcv_and_detect_partial_window() -> None:
    rows = [
        _row(f"2024-01-02T15:{minute:02d}:00Z", open_price=100.0 + minute)
        for minute in range(16)
    ]
    out = build_timeframe(pd.DataFrame(rows), parse_timeframe("15m"))

    assert len(out) == 2
    first = out.iloc[0]
    assert first["open"] == 100.0
    assert first["high"] == 114.5
    assert first["low"] == 99.5
    assert first["close"] == 114.25
    assert first["volume"] == 150
    assert first["source_rows"] == 15
    assert first["complete_window"] == True

    second = out.iloc[1]
    assert second["source_rows"] == 1
    assert second["expected_source_rows"] == 15
    assert second["complete_window"] == False
    assert second["bar_quality_status"] == "flagged"


def test_parse_timeframes_accepts_powershell_unquoted_commas() -> None:
    specs = parse_timeframes("5m 15 m 1 h 4 h 1 d 1 w")
    assert [spec.label for spec in specs] == ["5m", "15m", "1h", "4h", "1d", "1w"]


def test_intraday_bars_do_not_cross_session_segment_ids() -> None:
    rows = [
        _row("2024-01-02T15:00:00Z", open_price=100.0, session_segment_id="seg_a"),
        _row("2024-01-02T15:01:00Z", open_price=101.0, session_segment_id="seg_b"),
    ]
    out = build_timeframe(pd.DataFrame(rows), parse_timeframe("4h"))

    assert len(out) == 2
    assert sorted(out["session_segment_id"].tolist()) == ["seg_a", "seg_b"]
    assert out["source_rows"].tolist() == [1, 1]


def test_daily_bars_group_by_session_id_across_utc_midnight() -> None:
    rows = [
        _row(
            "2024-01-02T23:58:00Z",
            open_price=100.0,
            session_id="session_a",
            session_date="2024-01-02",
        ),
        _row(
            "2024-01-03T00:01:00Z",
            open_price=101.0,
            session_id="session_a",
            session_date="2024-01-02",
        ),
    ]
    out = build_timeframe(pd.DataFrame(rows), parse_timeframe("1d"))

    assert len(out) == 1
    bar = out.iloc[0]
    assert bar["session_id"] == "session_a"
    assert bar["session_date"] == "2024-01-02"
    assert bar["open"] == 100.0
    assert bar["close"] == 101.25
    assert bar["volume"] == 20
    assert bar["complete_window"] == True


def test_weekly_bars_group_by_session_date_week() -> None:
    rows = [
        _row(
            "2024-01-01T23:00:00Z",
            open_price=100.0,
            session_id="session_2024-01-02",
            session_date="2024-01-01",
        ),
        _row(
            "2024-01-05T21:00:00Z",
            open_price=101.0,
            session_id="session_2024-01-05",
            session_date="2024-01-05",
            roll=True,
        ),
        _row(
            "2024-01-07T23:00:00Z",
            open_price=102.0,
            session_id="session_2024-01-08",
            session_date="2024-01-08",
        ),
    ]
    out = build_timeframe(pd.DataFrame(rows), parse_timeframe("1w"))

    assert len(out) == 2
    first = out.iloc[0]
    assert first["session_id"] == "week_2024-01-01"
    assert first["session_date"] == "2024-01-01"
    assert first["open"] == 100.0
    assert first["high"] == 101.5
    assert first["low"] == 99.5
    assert first["close"] == 101.25
    assert first["volume"] == 20
    assert first["source_rows"] == 2
    assert first["source_has_roll_window"] == True
    assert first["complete_window"] == True
    assert first["bar_quality_status"] == "flagged"

    second = out.iloc[1]
    assert second["session_id"] == "week_2024-01-08"
    assert second["source_rows"] == 1
    assert second["complete_window"] == False


def test_process_file_filters_outside_session_and_writes_manifest(tmp_path: Path) -> None:
    input_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    output_path = tmp_path / "data" / "higher_timeframes" / "5m" / "ES" / "2024.parquet"
    hourly_output_path = tmp_path / "data" / "higher_timeframes" / "1h" / "ES" / "2024.parquet"
    input_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _row("2024-01-02T15:00:00Z", open_price=100.0),
            _row("2024-01-02T15:01:00Z", open_price=101.0, inside_session=False),
        ]
    ).to_parquet(input_path, index=False)

    result = process_file(
        input_path,
        output_path,
        market="ES",
        year=2024,
        spec=parse_timeframe("5m"),
    )
    assert result.status == "WARN"
    assert result.input_rows == 2
    assert result.used_rows == 1
    assert result.excluded_outside_session_rows == 1
    assert output_path.exists()
    hourly_result = process_file(
        input_path,
        hourly_output_path,
        market="ES",
        year=2024,
        spec=parse_timeframe("1h"),
    )

    reports_root = tmp_path / "reports" / "higher_timeframes"
    write_reports(
        [result, hourly_result],
        reports_root,
        profile="tier_0",
        input_root=input_path.parents[1],
        output_root=output_path.parents[2],
        timeframes=[parse_timeframe("5m")],
        include_outside_session=False,
    )
    manifest = json.loads((reports_root / "higher_timeframe_manifest.json").read_text())
    assert manifest["summary"]["output_file_count"] == 2
    assert manifest["summary"]["source_file_count"] == 1
    assert manifest["summary"]["source_input_rows"] == 2
    assert manifest["summary"]["source_excluded_outside_session_rows"] == 1
