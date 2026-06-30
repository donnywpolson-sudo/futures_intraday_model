from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.validation import diagnose_6a_2010_source_vs_raw_gaps as diag


def _write_session_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "session_templates:",
                "  cme_globex_17_16_ct:",
                "    timezone: America/Chicago",
                '    regular_open: "17:00"',
                '    regular_close: "16:00"',
                "    holidays: []",
                "    closed_dates: []",
                "    early_closes: {}",
                "markets:",
                "  default:",
                "    session_template: cme_globex_17_16_ct",
                "  6A:",
                "    session_template: cme_globex_17_16_ct",
            ]
        ),
        encoding="utf-8",
    )


def _write_readiness(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "blocker_count": 1,
                "blockers": [
                    {
                        "market": "6A",
                        "year": 2010,
                        "synthetic_rows_pct": 5.352996,
                        "max_synthetic_gap_minutes": 18,
                        "synthetic_rows": 10926,
                        "status_enrichment_missing_rows": 149749,
                        "statistics_enrichment_missing_rows": 101,
                        "top_blocker_reason": "synthetic threshold breached",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_raw(path: Path, timestamps: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "ts_event": pd.to_datetime(timestamps, utc=True),
            "open": [1.0] * len(timestamps),
            "high": [1.0] * len(timestamps),
            "low": [1.0] * len(timestamps),
            "close": [1.0] * len(timestamps),
            "volume": [1] * len(timestamps),
        }
    ).to_parquet(path, index=False)


def _touch_dbn(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake dbn")


def _dbn_frame(timestamps: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_event": pd.to_datetime(timestamps, utc=True),
            "open": [1.0] * len(timestamps),
            "high": [1.0] * len(timestamps),
            "low": [1.0] * len(timestamps),
            "close": [1.0] * len(timestamps),
            "volume": [1] * len(timestamps),
        }
    )


def test_report_calls_source_gaps_when_raw_matches_dbn(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    dbn_root = tmp_path / "data" / "dbn" / "ohlcv_1m"
    readiness = tmp_path / "readiness.json"
    session_config = tmp_path / "sessions.yaml"
    timestamps = [
        "2010-06-07T22:00:00Z",
        "2010-06-07T22:01:00Z",
        "2010-06-07T22:04:00Z",
    ]
    _write_raw(raw_root / "6A" / "2010.parquet", timestamps)
    _touch_dbn(dbn_root / "6A" / "2010" / "2010-06-06_2011-01-01.dbn.zst")
    _write_readiness(readiness)
    _write_session_config(session_config)

    report = diag.build_report(
        market="6A",
        year=2010,
        raw_root=raw_root,
        dbn_root=dbn_root,
        readiness_json=readiness,
        session_config=session_config,
        load_dbn_frame=lambda _: _dbn_frame(timestamps),
    )

    assert report["status"] == "PASS"
    assert report["stage"] == "market_year_source_vs_raw_gap_diagnosis"
    assert report["source_vs_raw_call"] == "raw_timestamp_set_matches_ohlcv_dbn_source_gaps"
    assert report["timestamp_sets_match"] is True
    assert report["dbn_timestamps_missing_from_raw_count"] == 0
    assert report["interpretation"]["source_gap_evidence"] is True
    assert report["forbidden_actions_performed"]["data_mutation"] is False


def test_report_flags_conversion_when_dbn_has_rows_missing_from_raw(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    dbn_root = tmp_path / "data" / "dbn" / "ohlcv_1m"
    readiness = tmp_path / "readiness.json"
    session_config = tmp_path / "sessions.yaml"
    _write_raw(
        raw_root / "6A" / "2010.parquet",
        ["2010-06-07T22:00:00Z", "2010-06-07T22:04:00Z"],
    )
    _touch_dbn(dbn_root / "6A" / "2010" / "2010-06-06_2011-01-01.dbn.zst")
    _write_readiness(readiness)
    _write_session_config(session_config)

    report = diag.build_report(
        market="6A",
        year=2010,
        raw_root=raw_root,
        dbn_root=dbn_root,
        readiness_json=readiness,
        session_config=session_config,
        load_dbn_frame=lambda _: _dbn_frame(
            [
                "2010-06-07T22:00:00Z",
                "2010-06-07T22:01:00Z",
                "2010-06-07T22:04:00Z",
            ]
        ),
    )

    assert report["source_vs_raw_call"] == "conversion_or_raw_write_dropped_dbn_timestamps_possible"
    assert report["timestamp_sets_match"] is False
    assert report["dbn_timestamps_missing_from_raw_count"] == 1
    assert report["interpretation"]["conversion_bug_evidence"] is True
