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
    definition: Path,
    status: Path | None,
    statistics: Path | None,
    market: str = "ES",
    year: int = 2024,
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
        "market": market,
        "year": year,
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
        "definition_source_file": definition.as_posix(),
        "definition_source_sha256": file_sha256(definition),
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
    first = rows[0]
    path = raw_root / str(first["market"]) / f"{int(first['year'])}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _source_paths(dbn_root: Path, market: str = "ES", year: int = 2024) -> tuple[Path, Path, Path, Path]:
    ohlcv = _write_source(
        dbn_root / "ohlcv_1m" / market / str(year) / f"{year}-01-01_{year + 1}-01-01.dbn.zst",
        b"ohlcv",
    )
    definition = _write_source(
        dbn_root / "definition" / market / str(year) / f"{year}-01-01_{year + 1}-01-01.dbn.zst",
        b"definition",
    )
    status = _write_source(
        dbn_root / "status" / market / str(year) / f"{year}-01-01_{year + 1}-01-01.dbn.zst",
        b"status",
    )
    statistics = _write_source(
        dbn_root / "statistics" / market / str(year) / f"{year}-01-01_{year + 1}-01-01.dbn.zst",
        b"statistics",
    )
    return ohlcv, definition, status, statistics


def _write_provider_empty_exception(path: Path, evidence_path: Path) -> Path:
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        '{"status": "FAIL", "provider_empty_estimate_count": 1}\n',
        encoding="utf-8",
    )
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "required_schema_exceptions:",
                "  - schema: status",
                "    market: KE",
                "    year: 2013",
                "    start: 2013-01-01",
                "    end: 2014-01-01",
                "    reason: provider_empty",
                "    evidence_paths:",
                f"      - {evidence_path.as_posix()}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_enriched_raw_optional_schema_audit_passes_complete_sources(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, definition, status, statistics = _source_paths(dbn_root)
    _write_raw(raw_root, [_base_row(ohlcv=ohlcv, definition=definition, status=status, statistics=statistics)])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "PASS"
    assert report["verdicts"]["optional_status_readiness"] == "PASS"
    assert report["verdicts"]["optional_statistics_readiness"] == "PASS"


def test_missing_status_archive_fails_when_flags_are_explicit(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, definition, _, statistics = _source_paths(dbn_root)
    for path in (dbn_root / "status" / "ES" / "2024").glob("*"):
        path.unlink()
    _write_raw(raw_root, [_base_row(ohlcv=ohlcv, definition=definition, status=None, statistics=statistics)])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "FAIL"
    assert report["verdicts"]["optional_status_readiness"] == "FAIL"
    assert report["summary"]["missing_status_archive_market_year_count"] == 1
    assert report["summary"]["status_failure_count"] == 1
    assert report["files"][0]["failures"][0]["failure"] == "required status DBN archive missing for market-year"


def test_missing_status_archive_exception_passes_for_exact_provider_empty_gap(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, definition, _, statistics = _source_paths(dbn_root, "KE", 2013)
    for path in (dbn_root / "status" / "KE" / "2013").glob("*"):
        path.unlink()
    _write_raw(
        raw_root,
        [_base_row(ohlcv=ohlcv, definition=definition, status=None, statistics=statistics, market="KE", year=2013)],
    )
    exceptions = _write_provider_empty_exception(tmp_path / "exceptions.yaml", tmp_path / "evidence.json")

    report = build_report(
        raw_root=raw_root,
        dbn_root=dbn_root,
        expected_column_count=None,
        required_schema_exceptions_config=exceptions,
    )

    assert report["status"] == "PASS"
    assert report["verdicts"]["optional_status_readiness"] == "PASS"
    assert report["summary"]["missing_status_archive_market_year_count"] == 0
    assert report["summary"]["status_required_schema_exception_count"] == 1
    assert report["files"][0]["warnings"] == [
        "provider-unavailable required status DBN exception for market-year"
    ]


def test_missing_statistics_archive_fails_when_flags_are_explicit(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, definition, status, _ = _source_paths(dbn_root)
    for path in (dbn_root / "statistics" / "ES" / "2024").glob("*"):
        path.unlink()
    _write_raw(raw_root, [_base_row(ohlcv=ohlcv, definition=definition, status=status, statistics=None)])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "FAIL"
    assert report["verdicts"]["optional_statistics_readiness"] == "FAIL"
    assert report["summary"]["missing_statistics_archive_market_year_count"] == 1
    assert report["summary"]["statistics_failure_count"] == 1
    assert report["files"][0]["failures"][0]["failure"] == "required statistics DBN archive missing for market-year"


def test_bad_optional_source_hash_fails(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, definition, status, statistics = _source_paths(dbn_root)
    row = _base_row(ohlcv=ohlcv, definition=definition, status=status, statistics=statistics)
    row["stat_open_interest_source_sha256"] = "bad"
    _write_raw(raw_root, [row])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "FAIL"
    assert report["summary"]["source_hash_mismatch_count"] == 1


def test_bad_definition_source_hash_fails(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, definition, status, statistics = _source_paths(dbn_root)
    row = _base_row(ohlcv=ohlcv, definition=definition, status=status, statistics=statistics)
    row["definition_source_sha256"] = "bad"
    _write_raw(raw_root, [row])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "FAIL"
    assert report["summary"]["source_hash_mismatch_count"] == 1


def test_multi_source_file_hash_references_pass(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, definition, status, statistics = _source_paths(dbn_root)
    ohlcv_overlap = _write_source(
        dbn_root / "ohlcv_1m" / "ES" / "2024" / "2024-06-12_2024-06-13.dbn.zst",
        b"ohlcv-overlap",
    )
    definition_overlap = _write_source(
        dbn_root / "definition" / "ES" / "2024" / "2024-06-12_2024-06-13.dbn.zst",
        b"definition-overlap",
    )
    row = _base_row(ohlcv=ohlcv, definition=definition, status=status, statistics=statistics)
    row["source_file"] = ";".join([ohlcv.as_posix(), ohlcv_overlap.as_posix()])
    row["source_sha256"] = ";".join([file_sha256(ohlcv), file_sha256(ohlcv_overlap)])
    row["definition_source_file"] = ";".join([definition.as_posix(), definition_overlap.as_posix()])
    row["definition_source_sha256"] = ";".join([file_sha256(definition), file_sha256(definition_overlap)])
    _write_raw(raw_root, [row])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "PASS"
    assert report["summary"]["missing_source_file_count"] == 0
    assert report["summary"]["source_hash_mismatch_count"] == 0


def test_future_optional_timestamp_fails(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv, definition, status, statistics = _source_paths(dbn_root)
    _write_raw(
        raw_root,
        [
            _base_row(
                ohlcv=ohlcv,
                definition=definition,
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
    ohlcv, definition, status, statistics = _source_paths(dbn_root)
    row = _base_row(ohlcv=ohlcv, definition=definition, status=status, statistics=statistics)
    _write_raw(raw_root, [row, row.copy()])

    report = build_report(raw_root=raw_root, dbn_root=dbn_root, expected_column_count=None)

    assert report["status"] == "FAIL"
    assert report["summary"]["duplicate_key_row_count"] == 1
