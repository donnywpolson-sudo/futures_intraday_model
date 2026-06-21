from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.validation import audit_sparse_ohlcv_vendor_convention as audit


def _trades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_event": pd.to_datetime(
                [
                    "2025-06-18T00:00:05Z",
                    "2025-06-18T00:00:30Z",
                    "2025-06-18T00:02:00Z",
                ],
                utc=True,
            ),
            "instrument_id": [10, 10, 10],
            "price": [100.0, 101.0, 102.0],
            "size": [2, 3, 4],
            "sequence": [1, 2, 3],
        },
        index=pd.DatetimeIndex(
            pd.to_datetime(
                [
                    "2025-06-18T00:00:05Z",
                    "2025-06-18T00:00:30Z",
                    "2025-06-18T00:02:00Z",
                ],
                utc=True,
            ),
            name="ts_recv",
        ),
    )


def _ohlcv() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "instrument_id": [10, 10],
            "open": [100.0, 102.0],
            "high": [101.0, 102.0],
            "low": [100.0, 102.0],
            "close": [101.0, 102.0],
            "volume": [5, 4],
        },
        index=pd.DatetimeIndex(
            pd.to_datetime(["2025-06-18T00:00:00Z", "2025-06-18T00:02:00Z"], utc=True),
            name="ts_event",
        ),
    )


def test_compare_trade_ohlcv_frames_allows_no_trade_missing_interval() -> None:
    report = audit.compare_trade_ohlcv_frames(_trades(), _ohlcv())

    assert report["status"] == "PASS"
    assert report["trade_bar_count"] == 2
    assert report["ohlcv_bar_count"] == 2
    assert report["missing_ohlcv_bar_count"] == 0
    assert report["extra_ohlcv_bar_count"] == 0


def test_compare_trade_ohlcv_frames_fails_missing_trade_bar() -> None:
    ohlcv = _ohlcv().iloc[[0]]

    report = audit.compare_trade_ohlcv_frames(_trades(), ohlcv)

    assert report["status"] == "FAIL"
    assert report["missing_ohlcv_bar_count"] == 1


def test_build_report_marks_historical_years_assumption_backed(tmp_path: Path) -> None:
    trade_path = tmp_path / "data" / "dbn" / "trades" / "SR3" / "2025" / "x.dbn.zst"
    ohlcv_path = tmp_path / "data" / "dbn" / "ohlcv_1m" / "SR3" / "2025" / "x.dbn.zst"
    trade_path.parent.mkdir(parents=True)
    ohlcv_path.parent.mkdir(parents=True)
    trade_path.write_bytes(b"x")
    ohlcv_path.write_bytes(b"x")

    def reader(path: Path) -> pd.DataFrame:
        return _trades() if "trades" in path.parts else _ohlcv()

    report = audit.build_sparse_ohlcv_convention_report(
        dbn_root=tmp_path / "data" / "dbn",
        markets=["SR3"],
        direct_years=[2025],
        assumed_history_years=[2018, 2019],
        frame_reader=reader,
    )

    assert report["status"] == "PASS"
    assert report["direct_evidence"][0]["status"] == "PASS"
    assert report["assumption_extension"]["status"] == (
        "ASSUMPTION_BACKED_NOT_DIRECTLY_TRADE_VALIDATED"
    )
    assert report["assumption_extension"]["years"] == [2018, 2019]
