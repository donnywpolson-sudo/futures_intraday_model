from __future__ import annotations

import argparse
from io import StringIO

import pytest

import live_chart_feed as live_chart


def _args(*values: str):
    return live_chart.build_arg_parser().parse_args(list(values))


def test_feed_cli_uses_market_and_timeframe_semantics() -> None:
    args = _args(
        "--market",
        "ES",
        "--timeframe",
        "5m",
        "--historical-backfill",
        "--lookback-hours",
        "2",
        "--timeout-seconds",
        "30",
    )

    assert args.market == "ES"
    assert args.chart_timeframe == "5m"
    assert args.historical_backfill is True
    assert args.lookback_hours == 2
    assert args.timeout_seconds == 30
    assert args.schema == "trades"
    assert args.historical_schema == "ohlcv-1m"
    assert args.stype_in == "instrument_id"


def test_feed_market_defaults_to_continuous_symbol_query() -> None:
    assert live_chart.market_query_symbol("ES", None) == "ES.v.0"
    assert live_chart.market_query_symbol("ES", "ESM6") == "ESM6"


def test_feed_rejects_multi_symbol_override() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="exactly one instrument"):
        live_chart.market_query_symbol("ES", "ESM6,ESU6")


def test_old_symbols_only_command_no_longer_starts_chart() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = live_chart.run_live_chart(
        _args("--symbols", "ES.c.0", "--start", "0", "--max-records", "50"),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert "Select a market explicitly" in stderr.getvalue()
    assert "python live_chart_feed.py --market ES --timeframe 1m" in stderr.getvalue()


def test_feed_requires_live_trade_schema() -> None:
    stderr = StringIO()

    result = live_chart.run_live_chart(
        _args("--market", "ES", "--schema", "ohlcv-1m"),
        env={"DATABENTO_API_KEY": "db-test"},
        stderr=stderr,
    )

    assert result == 2
    assert "schema 'trades'" in stderr.getvalue()


def test_feed_requires_instrument_id_subscription() -> None:
    stderr = StringIO()

    result = live_chart.run_live_chart(
        _args("--market", "ES", "--stype-in", "continuous"),
        env={"DATABENTO_API_KEY": "db-test"},
        stderr=stderr,
    )

    assert result == 2
    assert "stype_in 'instrument_id'" in stderr.getvalue()


def test_feed_requires_one_minute_historical_backfill_schema() -> None:
    stderr = StringIO()

    result = live_chart.run_live_chart(
        _args("--market", "ES", "--historical-schema", "ohlcv-5m"),
        env={"DATABENTO_API_KEY": "db-test"},
        stderr=stderr,
    )

    assert result == 2
    assert "historical backfill must use Databento schema 'ohlcv-1m'" in stderr.getvalue()
