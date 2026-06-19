from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase1A_download.download_databento_raw import STAT_TYPE_FIELDS, file_sha256
from scripts.validation.audit_enriched_raw_optional_schemas import build_report


def _write_source(path: Path, payload: bytes = b"dbn") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _base_row(
    *,
    ohlcv: Path,
    status: Path | None,
    statistics: Path | None,
    ts_event: pd.Timestamp = pd.Timestamp("2024-01-02T15:00:00Z"),
    status_ts_event: pd.Timestamp | None = pd.Timestamp("2024-01-02T14:59:00Z"),
) -> dict[str, object]:
    status_missing = status is None or status_ts_event is None
    row: dict[str, object] = {
        "ts_event": ts_event,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 10,
        "rtype": 33,
        "publisher_id": 1,
        "instrument_id": 100,
        "symbol": "ESH4",
        "data_quality_status": "available",
        "data_quality_degraded": False,
        "datetime_utc": ts_event,
        "market": "ES",
        "year": 2024,
        "raw_symbol": "ESH4",
        "tick_size": 0.25,
        "contract_multiplier_or_point_value": 50,
        "expiration": pd.Timestamp("2024-03-15T00:00:00Z"),
        "maturity_year": 2024,
        "maturity_month": 3,
        "source_schema": "ohlcv-1m",
        "source_dataset": "GLBX.MDP3",
        "source_file": ohlcv.as_posix(),
        "source_sha256": file_sha256(ohlcv),
        "status_ts_event": status_ts_event if status is not None else pd.NaT,
        "status_action": 7 if status is not None else pd.NA,
        "status_action_name": "TRADING" if status is not None else pd.NA,
        "status_reason": 0 if status is not None else pd.NA,
        "status_reason_name": "0" if status is not None else pd.NA,
        "status_trading_event": 0 if status is not None else pd.NA,
        "status_trading_event_name": "NONE" if status is not None else pd.NA,
        "status_is_trading": True if status is not None else pd.NA,
        "status_is_quoting": True if status is not None else pd.NA,
        "status_is_short_sell_restricted": False if status is not None else pd.NA,
        "status_source_file": status.as_posix() if status is not None else pd.NA,
        "status_source_sha256": file_sha256(status) if status is not None else pd.NA,
        "status_missing": status_missing,
        "status_stale": status_missing,
    }
    all_stat_missing = statistics is None
    for stat_name, value_column in STAT_TYPE_FIELDS.values():
        value = 100.0 if value_column == "price" else 1000
        row[f"stat_{stat_name}"] = pd.NA if statistics is None else value
        row[f"stat_{stat_name}_ts_event"] = pd.NaT if statistics is None else pd.Timestamp("2024-01-02T14:58:00Z")
        row[f"stat_{stat_name}_source_file"] = statistics.as_posix() if statistics is not None else pd.NA
        row[f"stat_{stat_name}_source_sha256"] = file_sha256(statistics) if statistics is not None else pd.NA
        row[f"stat_{stat_name}_missing"] = statistics is None
    row["statistics_missing"] = all_stat_missing
    row["statistics_stale"] = all_stat_missing
    return row


def _write_raw(raw_root: Path, rows: list[dict[str, object]]) -> Path:
    path = raw_root / "ES" / "2024.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _source_paths(dbn_root: Path) -> tuple[Path, Path, Path]:
    ohlcv = _write_source(dbn_root / "ohlcv_1m" / "ES" / "2024" / "2024-01-01_2025-01-01.dbn.zst", b"ohlcv")
    status = _write_source(dbn_root / "status" / "ES" / "2024" / "2024-01-01_2025-01-01.dbn.zst", b"status")
    statistics = _write_source(
        dbn_root / "statistics" / "ES" / "2024" / "2024-01-01_2025-01-01.dbn.zst",
        b"statistics",
    )
    return ohlcv, status, statistics


def test_enriched_raw_optional_schema_audit_passes_complete_sources(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, status, statistics = _source_paths(dbn_root)
    _write_raw(raw_root, [_base_row(ohlcv=ohlcv, status=status, statistics=statistics)])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "PASS"
    assert report["verdicts"]["optional_status_readiness"] == "PASS"
    assert report["verdicts"]["optional_statistics_readiness"] == "PASS"


def test_missing_status_archive_is_warning_when_flags_are_explicit(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, _, statistics = _source_paths(dbn_root)
    for path in (dbn_root / "status" / "ES" / "2024").glob("*"):
        path.unlink()
    _write_raw(raw_root, [_base_row(ohlcv=ohlcv, status=None, statistics=statistics)])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "PASS"
    assert report["verdicts"]["optional_status_readiness"] == "WARN"
    assert report["summary"]["missing_status_archive_market_year_count"] == 1


def test_bad_optional_source_hash_fails(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, status, statistics = _source_paths(dbn_root)
    row = _base_row(ohlcv=ohlcv, status=status, statistics=statistics)
    row["stat_open_interest_source_sha256"] = "bad"
    _write_raw(raw_root, [row])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "FAIL"
    assert report["summary"]["source_hash_mismatch_count"] == 1


def test_future_optional_timestamp_fails(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, status, statistics = _source_paths(dbn_root)
    _write_raw(
        raw_root,
        [
            _base_row(
                ohlcv=ohlcv,
                status=status,
                statistics=statistics,
                status_ts_event=pd.Timestamp("2024-01-02T15:01:00Z"),
            )
        ],
    )

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "FAIL"
    assert report["files"][0]["status_metrics"]["status_future_timestamp_rows"] == 1


def test_duplicate_ohlcv_grain_fails(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, status, statistics = _source_paths(dbn_root)
    row = _base_row(ohlcv=ohlcv, status=status, statistics=statistics)
    _write_raw(raw_root, [row, row.copy()])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "FAIL"
    assert report["summary"]["duplicate_key_row_count"] == 1
