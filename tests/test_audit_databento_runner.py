from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from scripts.audit_databento_phase3 import apply_complete_minute_guard, drop_sample_edge_minutes
from scripts.databento_audit_runner import build_arg_parser, enforce_full_scan_policy, enforce_prerequisites


def test_runner_help_exposes_required_options() -> None:
    help_text = build_arg_parser().format_help()
    for option in (
        "--phase",
        "--safe-auto",
        "--through",
        "--data-root",
        "--output-dir",
        "--schemas",
        "--markets",
        "--years",
        "--start-date",
        "--end-date",
        "--sample",
        "--full",
        "--sample-first",
        "--allow-full-scan",
        "--stop-on-severe",
        "--resume",
        "--max-files",
        "--max-rows",
        "--fail-on-severe",
        "--reconstruct-ohlcv-from-trades",
        "--dry-run",
    ):
        assert option in help_text


def test_full_scan_requires_allow_full_scan() -> None:
    args = Namespace(full=True, allow_full_scan=False, sample_first=False)
    with pytest.raises(SystemExit):
        enforce_full_scan_policy(args, 2)


def test_prerequisite_enforcement_refuses_missing_gate(tmp_path: Path) -> None:
    args = Namespace(output_dir=str(tmp_path / "reports" / "data_audit"))
    with pytest.raises(SystemExit):
        enforce_prerequisites(args, 1)


def test_phase3_sample_edge_guard_drops_first_and_last_trade_minutes() -> None:
    trades = pd.DataFrame(
        {
            "market": ["ES", "ES", "ES", "ES"],
            "instrument_id": [1, 1, 1, 1],
            "minute": pd.to_datetime(
                [
                    "2026-01-02T00:00:00Z",
                    "2026-01-02T00:01:00Z",
                    "2026-01-02T00:01:15Z",
                    "2026-01-02T00:02:00Z",
                ]
            ).floor("min"),
        }
    )

    guarded, excluded, reason = drop_sample_edge_minutes(trades)

    assert excluded == 2
    assert reason == "dropped_first_last_observed_trade_minute_per_market_instrument"
    assert guarded["minute"].dt.strftime("%H:%M").tolist() == ["00:01", "00:01"]


def test_phase3_complete_minute_guard_reports_excluded_edges() -> None:
    trades = pd.DataFrame(
        {
            "market": ["ES", "ES", "ES", "ES"],
            "instrument_id": [1, 1, 1, 1],
            "minute": pd.to_datetime(
                [
                    "2026-01-02T00:00:00Z",
                    "2026-01-02T00:01:00Z",
                    "2026-01-02T00:01:15Z",
                    "2026-01-02T00:02:00Z",
                ]
            ).floor("min"),
        }
    )

    guarded, guard_rows = apply_complete_minute_guard(trades, "trades.dbn.zst", "ohlcv.dbn.zst")

    assert len(guard_rows) == 2
    assert sum(row["trade_rows_excluded"] for row in guard_rows) == 2
    assert sum(row["edge_bars_excluded"] for row in guard_rows) == 2
    assert {row["edge_position"] for row in guard_rows} == {"first_sample_minute", "last_sample_minute"}
    assert all(row["action"] == "excluded_from_comparison" for row in guard_rows)
    assert guarded["minute"].dt.strftime("%H:%M").tolist() == ["00:01", "00:01"]
