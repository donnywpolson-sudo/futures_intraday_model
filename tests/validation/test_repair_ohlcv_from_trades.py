from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd

from scripts.validation.repair_ohlcv_from_trades import (
    REPAIR_SOURCE_SCHEMA,
    build_report,
    main,
)


class FakeTradeReader:
    def __init__(self, frames: list[pd.DataFrame]) -> None:
        self.frames = frames
        self.calls: list[tuple[Path, int]] = []

    def __call__(self, path: Path, chunk_size: int):
        self.calls.append((path, chunk_size))
        yield from self.frames


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_archive(root: Path, market: str = "ES", year: int = 2025) -> Path:
    path = root / market / str(year) / "2025-06-18_2026-01-01.dbn.zst"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"trades")
    return path


def _write_raw(path: Path, *, instruments: tuple[int, int] = (100, 100)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "ts_event": pd.to_datetime(
                ["2025-06-18T00:00:00Z", "2025-06-18T00:02:00Z"], utc=True
            ),
            "open": [10.0, 11.0],
            "high": [10.0, 11.0],
            "low": [10.0, 11.0],
            "close": [10.0, 11.0],
            "volume": [5, 6],
            "rtype": [33, 33],
            "publisher_id": [1, 1],
            "instrument_id": list(instruments),
            "symbol": ["ES.v.0", "ES.v.0"],
            "raw_symbol": ["ESU5", "ESU5"],
            "data_quality_status": ["available", "available"],
            "data_quality_degraded": [False, False],
            "datetime_utc": pd.to_datetime(
                ["2025-06-18T00:00:00Z", "2025-06-18T00:02:00Z"], utc=True
            ),
            "market": ["ES", "ES"],
            "year": [2025, 2025],
            "source_schema": ["ohlcv-1m", "ohlcv-1m"],
            "source_dataset": ["GLBX.MDP3", "GLBX.MDP3"],
            "source_file": ["ohlcv.dbn.zst", "ohlcv.dbn.zst"],
            "source_sha256": ["raw-hash", "raw-hash"],
        }
    )
    frame.to_parquet(path, index=False)


def _write_gap_audit(path: Path, *, existing_minute: str = "2025-06-18T00:01:00Z") -> None:
    _write_json(
        path,
        {
            "market_years": [
                {
                    "market": "ES",
                    "year": 2025,
                    "gap_windows": [
                        {
                            "classification": "trade_activity_inside_ohlcv_gap",
                            "synthetic_gap_id": "gap-1",
                            "first_synthetic_ts": "2025-06-18T00:01:00Z",
                            "last_synthetic_ts": "2025-06-18T00:01:00Z",
                            "matched_trade_minutes": [existing_minute],
                            "instrument_id": 100,
                            "raw_symbol": "ESU5",
                        }
                    ],
                }
            ]
        },
    )


def _trade_frame(times: list[str], *, instrument_id: int = 100) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_event": pd.to_datetime(times, utc=True),
            "instrument_id": [instrument_id] * len(times),
            "action": ["T"] * len(times),
            "price": [10.25, 10.75][: len(times)],
            "size": [2, 3][: len(times)],
        }
    )


def _args(tmp_path: Path) -> Namespace:
    return Namespace(
        gap_audit_json=str(tmp_path / "reports" / "gap.json"),
        market="ES",
        year=2025,
        minute=[],
        raw_root=str(tmp_path / "data" / "raw"),
        trades_root=str(tmp_path / "data" / "dbn" / "trades"),
        output_root=str(tmp_path / "data" / "raw_repaired"),
        json_out=str(tmp_path / "reports" / "repair.json"),
        md_out=str(tmp_path / "reports" / "repair.md"),
        chunk_size=2,
        max_repair_minutes=5,
        overwrite=False,
    )


def test_reconstructs_missing_ohlcv_minute_from_trades(tmp_path: Path) -> None:
    _write_raw(tmp_path / "data" / "raw" / "ES" / "2025.parquet")
    _write_archive(tmp_path / "data" / "dbn" / "trades")
    _write_gap_audit(tmp_path / "reports" / "gap.json")
    reader = FakeTradeReader(
        [_trade_frame(["2025-06-18T00:01:10Z", "2025-06-18T00:01:50Z"])]
    )

    report = build_report(_args(tmp_path), trade_frame_reader=reader)

    assert report["status"] == "PASS"
    assert report["repaired_rows"][0]["source_schema"] == REPAIR_SOURCE_SCHEMA
    output = pd.read_parquet(tmp_path / "data" / "raw_repaired" / "ES" / "2025.parquet")
    assert len(output) == 3
    row = output.loc[pd.to_datetime(output["ts_event"], utc=True).eq(pd.Timestamp("2025-06-18T00:01:00Z"))].iloc[0]
    assert row["open"] == 10.25
    assert row["high"] == 10.75
    assert row["low"] == 10.25
    assert row["close"] == 10.75
    assert row["volume"] == 5
    assert row["source_schema"] == REPAIR_SOURCE_SCHEMA
    assert reader.calls[0][1] == 2


def test_existing_raw_minute_fails_closed(tmp_path: Path) -> None:
    _write_raw(tmp_path / "data" / "raw" / "ES" / "2025.parquet")
    frame = pd.read_parquet(tmp_path / "data" / "raw" / "ES" / "2025.parquet")
    frame = pd.concat(
        [
            frame,
            frame.iloc[[0]].assign(ts_event=pd.Timestamp("2025-06-18T00:01:00Z")),
        ],
        ignore_index=True,
    )
    frame.to_parquet(tmp_path / "data" / "raw" / "ES" / "2025.parquet", index=False)
    _write_archive(tmp_path / "data" / "dbn" / "trades")
    _write_gap_audit(tmp_path / "reports" / "gap.json")

    report = build_report(_args(tmp_path), trade_frame_reader=FakeTradeReader([]))

    assert report["status"] == "FAIL"
    assert any("already exists" in failure for failure in report["failures"])


def test_unresolved_adjacent_context_fails_closed(tmp_path: Path) -> None:
    _write_raw(tmp_path / "data" / "raw" / "ES" / "2025.parquet", instruments=(100, 200))
    _write_archive(tmp_path / "data" / "dbn" / "trades")
    _write_gap_audit(tmp_path / "reports" / "gap.json")

    report = build_report(_args(tmp_path), trade_frame_reader=FakeTradeReader([]))

    assert report["status"] == "FAIL"
    assert any("instrument_id unresolved" in failure for failure in report["failures"])


def test_no_matching_trades_fails_closed(tmp_path: Path) -> None:
    _write_raw(tmp_path / "data" / "raw" / "ES" / "2025.parquet")
    _write_archive(tmp_path / "data" / "dbn" / "trades")
    _write_gap_audit(tmp_path / "reports" / "gap.json")
    reader = FakeTradeReader([_trade_frame(["2025-06-18T00:01:10Z"], instrument_id=200)])

    report = build_report(_args(tmp_path), trade_frame_reader=reader)

    assert report["status"] == "FAIL"
    assert any("no matching trades found" in failure for failure in report["failures"])


def test_main_writes_reports(tmp_path: Path) -> None:
    _write_raw(tmp_path / "data" / "raw" / "ES" / "2025.parquet")
    _write_archive(tmp_path / "data" / "dbn" / "trades")
    _write_gap_audit(tmp_path / "reports" / "gap.json")

    code = main(
        [
            "--gap-audit-json",
            str(tmp_path / "reports" / "gap.json"),
            "--market",
            "ES",
            "--year",
            "2025",
            "--raw-root",
            str(tmp_path / "data" / "raw"),
            "--trades-root",
            str(tmp_path / "data" / "dbn" / "trades"),
            "--output-root",
            str(tmp_path / "data" / "raw_repaired"),
            "--json-out",
            str(tmp_path / "reports" / "repair.json"),
            "--md-out",
            str(tmp_path / "reports" / "repair.md"),
        ]
    )

    assert code in {0, 1}
    assert (tmp_path / "reports" / "repair.json").exists()
    assert (tmp_path / "reports" / "repair.md").exists()
