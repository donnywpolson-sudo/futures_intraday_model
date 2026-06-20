from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.validation import drilldown_phase2_readiness_blockers as drilldown


def _write_checkpoint(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sample_rows() -> list[dict[str, object]]:
    return [
        {
            "market": "ES",
            "year": 2024,
            "status": "PASS",
            "warnings": [],
            "failures": [],
        },
        {
            "market": "RTY",
            "year": 2024,
            "status": "WARN",
            "synthetic_rows_pct": 4.0,
            "synthetic_rows": 100,
            "max_synthetic_gap_minutes": 23,
            "warnings": ["synthetic threshold breached: rows_pct=4.0"],
            "failures": [],
            "status_enrichment_missing_rows": 2,
            "statistics_enrichment_missing_rows": 1,
        },
        {
            "market": "CL",
            "year": 2023,
            "status": "WARN",
            "degraded_rows_pct": 3.0,
            "degraded_bar_rows": 5,
            "warnings": ["degraded threshold breached: rows_pct=3.0"],
            "failures": [],
        },
    ]


def _write_raw(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "ts_event": pd.to_datetime(
                [
                    "2024-01-02T00:00:00Z",
                    "2024-01-02T00:01:00Z",
                    "2024-01-02T00:05:00Z",
                    "2024-01-03T00:00:00Z",
                ],
                utc=True,
            ),
            "open": [1.0, 1.1, 1.2, 1.3],
            "high": [1.0, 1.1, 1.2, 1.3],
            "low": [1.0, 1.1, 1.2, 1.3],
            "close": [1.0, 1.1, 1.2, 1.3],
            "volume": [1, 1, 1, 1],
            "data_quality_status": ["available", "available", "degraded", "available"],
            "status_is_trading": [True, True, True, False],
            "status_is_quoting": [True, True, True, False],
            "status_missing": [False, True, True, False],
            "status_stale": [False, False, True, False],
            "statistics_missing": [False, False, True, False],
            "statistics_stale": [False, False, True, False],
        }
    )
    frame.to_parquet(path, index=False)


def test_build_drilldown_report_reads_selected_raw_only(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    _write_raw(raw_root / "RTY" / "2024.parquet")

    report = drilldown.build_drilldown_report(
        _sample_rows(),
        raw_root=raw_root,
        top_n=1,
        markets={"RTY"},
        years={2024},
    )

    assert report["status"] == "FAIL"
    assert report["policy"] == "READ_ONLY_DIAGNOSTIC_ONLY"
    assert report["selected_market_year_count"] == 1
    assert report["evidence_scope"]["raw_parquet_written"] is False
    row = report["drilldowns"][0]
    assert row["market"] == "RTY"
    assert row["raw_read_status"] == "PASS"
    assert row["raw_row_count"] == 4
    assert row["bool_true_counts"]["status_is_trading"] == 3
    assert row["bool_true_counts"]["status_missing"] == 2
    assert row["bool_true_counts"]["statistics_missing"] == 1
    assert row["raw_gap_summary"]["max_gap_minutes"] == 1435.0
    assert row["raw_gap_summary"]["top_gaps"][0]["gap_minutes"] == 1435.0
    session_gap = row["phase2_session_gap_summary"]
    assert session_gap["scope"] == "phase2_session_calendar_synthetic_candidate_gaps"
    assert session_gap["candidate_gap_count"] == 1
    assert session_gap["synthetic_missing_rows_estimate"] == 3
    assert session_gap["max_candidate_gap_minutes"] == 4.0
    assert session_gap["top_session_gaps"][0]["previous_status_is_trading"] is True
    assert session_gap["top_session_gaps"][0]["next_status_is_quoting"] is True
    assert row["top_degraded_dates"] == [{"date": "2024-01-02", "row_count": 1}]


def test_selection_dedupes_top_offender_categories(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    _write_raw(raw_root / "RTY" / "2024.parquet")

    report = drilldown.build_drilldown_report(
        _sample_rows(),
        raw_root=raw_root,
        top_n=3,
        markets={"RTY"},
    )

    assert report["selected_market_years"] == [{"market": "RTY", "year": 2024}]


def test_max_selected_market_years_caps_raw_reads(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    _write_raw(raw_root / "RTY" / "2024.parquet")
    _write_raw(raw_root / "CL" / "2023.parquet")

    report = drilldown.build_drilldown_report(
        _sample_rows(),
        raw_root=raw_root,
        top_n=3,
        max_selected_market_years=1,
    )

    assert report["selected_market_year_count"] == 1
    assert report["selected_market_years"] == [{"market": "RTY", "year": 2024}]


def test_missing_raw_file_is_reported_without_writing_raw(tmp_path: Path) -> None:
    report = drilldown.build_drilldown_report(
        _sample_rows(),
        raw_root=tmp_path / "raw",
        top_n=1,
        markets={"RTY"},
    )

    assert report["raw_read_failure_count"] == 1
    assert "raw parquet missing" in report["raw_failures"][0]
    assert not (tmp_path / "raw").exists()


def test_cli_writes_json_only_when_requested(tmp_path: Path, capsys) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    raw_root = tmp_path / "raw"
    json_out = tmp_path / "drilldown.json"
    _write_checkpoint(checkpoint, _sample_rows())
    _write_raw(raw_root / "RTY" / "2024.parquet")

    result = drilldown.main(
        [
            "--checkpoint-jsonl",
            str(checkpoint),
            "--raw-root",
            str(raw_root),
            "--top-n",
            "1",
            "--markets",
            "RTY",
            "--json-out",
            str(json_out),
        ]
    )
    stdout_payload = json.loads(capsys.readouterr().out)
    written_payload = json.loads(json_out.read_text(encoding="utf-8"))

    assert result == 1
    assert stdout_payload["selected_market_year_count"] == 1
    assert "drilldowns" not in stdout_payload
    assert stdout_payload["top_session_gaps"][0]["max_gap_minutes"] == 4.0
    assert written_payload["drilldowns"][0]["market"] == "RTY"


def test_cli_errors_on_missing_checkpoint(capsys) -> None:
    result = drilldown.main(["--checkpoint-jsonl", "missing.jsonl"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["status"] == "FAIL"
    assert "missing" in payload["failures"][0]
