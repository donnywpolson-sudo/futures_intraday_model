from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import live_chart_feed as chart


def test_watermark_is_market_and_timeframe_only() -> None:
    assert (
        chart.format_chart_title(
            symbols="ESM6",
            schema="trades",
            mode="live",
            chart_timeframe="1m",
            display_tz=timezone.utc,
            display_tz_name="UTC",
        )
        == "ESM6 \u00b7 1m"
    )


def test_timeframe_parser_accepts_supported_values() -> None:
    assert [chart.normalize_timeframe(value) for value in ("1m", "5m", "15m", "30m", "1h")] == [
        "1m",
        "5m",
        "15m",
        "30m",
        "1h",
    ]


def test_timeframe_parser_rejects_invalid_values() -> None:
    with pytest.raises(Exception, match="timeframe must be one of"):
        chart.normalize_timeframe("2m")


def test_cli_timeframe_alias_parses_initial_timeframe() -> None:
    args = chart.build_arg_parser().parse_args(["--market", "ES", "--timeframe", "5m"])
    assert args.chart_timeframe == "5m"


def one_minute_candle(minute: int, close: float, volume: int = 1) -> dict[str, chart.CandleValue]:
    base = datetime(2026, 6, 21, 17, minute, tzinfo=timezone.utc)
    return {
        "time": base,
        "open": close - 0.5,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": volume,
    }


def test_aggregate_one_minute_candles_to_five_minutes() -> None:
    candles = [one_minute_candle(minute, close=100.0 + minute, volume=minute + 1) for minute in range(5)]

    aggregated = chart.aggregate_candles(candles, seconds=chart.timeframe_seconds("5m"))

    assert aggregated == [
        {
            "time": datetime(2026, 6, 21, 17, 0, tzinfo=timezone.utc),
            "open": 99.5,
            "high": 105.0,
            "low": 99.0,
            "close": 104.0,
            "volume": 15,
        }
    ]


def test_aggregate_one_minute_candles_to_fifteen_minutes() -> None:
    candles = [one_minute_candle(minute, close=200.0 + minute, volume=2) for minute in range(15)]

    aggregated = chart.aggregate_candles(candles, seconds=chart.timeframe_seconds("15m"))

    assert len(aggregated) == 1
    assert aggregated[0]["time"] == datetime(2026, 6, 21, 17, 0, tzinfo=timezone.utc)
    assert aggregated[0]["open"] == 199.5
    assert aggregated[0]["high"] == 215.0
    assert aggregated[0]["low"] == 199.0
    assert aggregated[0]["close"] == 214.0
    assert aggregated[0]["volume"] == 30


def test_trade_aggregator_builds_active_one_minute_candle() -> None:
    aggregator = chart.TradeCandleAggregator(timeframe_seconds=60)

    first = aggregator.apply_trade(
        SimpleNamespace(
            ts_event=datetime(2026, 6, 21, 17, 0, 1, tzinfo=timezone.utc),
            price=100.0,
            size=2,
        )
    )
    assert first == {
        "time": datetime(2026, 6, 21, 17, 0, tzinfo=timezone.utc),
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "volume": 2,
    }

    updated = aggregator.apply_trade(
        SimpleNamespace(
            ts_event=datetime(2026, 6, 21, 17, 0, 30, tzinfo=timezone.utc),
            price=101.25,
            size=3,
        )
    )
    assert updated is not None
    assert updated["time"] == first["time"]
    assert updated["open"] == 100.0
    assert updated["high"] == 101.25
    assert updated["low"] == 100.0
    assert updated["close"] == 101.25
    assert updated["volume"] == 5

    stale = aggregator.apply_trade(
        SimpleNamespace(
            ts_event=datetime(2026, 6, 21, 17, 0, 10, tzinfo=timezone.utc),
            price=99.0,
            size=1,
        )
    )
    assert stale is None
    assert aggregator.ignored_out_of_order == 1

    next_minute = aggregator.apply_trade(
        SimpleNamespace(
            ts_event=datetime(2026, 6, 21, 17, 1, 0, tzinfo=timezone.utc),
            price=100.5,
            size=1,
        )
    )
    assert next_minute is not None
    assert next_minute["time"] == datetime(2026, 6, 21, 17, 1, tzinfo=timezone.utc)
    assert next_minute["open"] == 100.5
    assert next_minute["volume"] == 1


def test_trade_aggregator_builds_active_five_minute_candle() -> None:
    aggregator = chart.TradeCandleAggregator(timeframe_seconds=chart.timeframe_seconds("5m"))

    first = aggregator.apply_trade(
        SimpleNamespace(
            ts_event=datetime(2026, 6, 21, 17, 3, 1, tzinfo=timezone.utc),
            price=100.0,
            size=2,
        )
    )
    updated = aggregator.apply_trade(
        SimpleNamespace(
            ts_event=datetime(2026, 6, 21, 17, 4, 59, tzinfo=timezone.utc),
            price=101.0,
            size=3,
        )
    )
    next_bucket = aggregator.apply_trade(
        SimpleNamespace(
            ts_event=datetime(2026, 6, 21, 17, 5, 0, tzinfo=timezone.utc),
            price=102.0,
            size=1,
        )
    )

    assert first is not None
    assert first["time"] == datetime(2026, 6, 21, 17, 0, tzinfo=timezone.utc)
    assert updated is not None
    assert updated["time"] == first["time"]
    assert updated["high"] == 101.0
    assert updated["close"] == 101.0
    assert updated["volume"] == 5
    assert next_bucket is not None
    assert next_bucket["time"] == datetime(2026, 6, 21, 17, 5, tzinfo=timezone.utc)


def test_append_display_candle_replaces_active_minute() -> None:
    display = chart.ChartDisplayState(
        raw_candles=[],
        timeframe="1m",
        timeframe_seconds=60,
        display_tz=timezone.utc,
        display_tz_name="UTC",
    )
    status = chart.ChartStatus()
    first = {
        "time": datetime(2026, 6, 21, 17, 0, tzinfo=timezone.utc),
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "volume": 1,
    }
    update = {**first, "high": 101.0, "close": 101.0, "volume": 2}

    assert chart.append_display_candle(display, status, first)
    assert chart.append_display_candle(display, status, update)

    assert len(display.raw_candles) == 1
    assert display.raw_candles[0]["close"] == 101.0
    assert display.raw_candles[0]["volume"] == 2


def test_discover_available_markets_from_tier3_config(tmp_path) -> None:
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "alpha_tiered.yaml").write_text(
        "\n".join(
            [
                "profiles:",
                "  tier_3_research:",
                "    description: Tier 3 test profile",
                "    markets: [ES, CL, NQ]",
                "    market_families:",
                "      ES: equity_index",
                "      CL: energy",
                "      NQ: equity_index",
            ]
        ),
        encoding="utf-8",
    )

    markets = chart.discover_available_markets(tmp_path)

    assert sorted(markets) == ["CL", "ES", "NQ"]
    assert markets["CL"].family == "energy"
    assert "crude" in markets["CL"].aliases


def test_real_tier3_market_count_from_alpha_config() -> None:
    markets = chart.discover_available_markets(chart.ROOT)

    assert len(markets) == 33
    assert "ES" in markets


def test_market_search_one_multiple_and_none() -> None:
    markets = chart.discover_available_markets(chart.ROOT)

    assert [market.symbol for market in chart.matching_markets(markets, "nasdaq")] == ["NQ"]
    assert {market.symbol for market in chart.matching_markets(markets, "energy")} == {"CL", "NG", "RB", "HO"}
    assert chart.matching_markets(markets, "crypto") == []


class FakeSymbology:
    def __init__(self, instrument_candidates: list[dict[str, str]]) -> None:
        self.instrument_candidates = instrument_candidates

    def resolve(self, **kwargs: object) -> dict[str, object]:
        if kwargs["stype_out"] == "instrument_id":
            return {"result": {kwargs["symbols"]: self.instrument_candidates}}
        return {
            "result": {
                str(kwargs["symbols"]): [
                    {"d0": kwargs["start_date"], "d1": kwargs["end_date"], "s": "ESM6"}
                ]
            }
        }


def test_resolve_single_instrument_requires_one_candidate() -> None:
    historical = SimpleNamespace(
        symbology=FakeSymbology(
            [{"d0": "2026-06-21", "d1": "2026-06-22", "s": "12345"}]
        )
    )

    resolved = chart.resolve_single_instrument(
        historical,
        dataset="GLBX.MDP3",
        market="ES",
        query_symbol="ES.v.0",
        start_date="2026-06-21",
        end_date="2026-06-22",
    )

    assert resolved.instrument_id == 12345
    assert resolved.raw_symbol == "ESM6"


def test_resolve_single_instrument_reports_ambiguous_candidates() -> None:
    historical = SimpleNamespace(
        symbology=FakeSymbology(
            [
                {"d0": "2026-06-21", "d1": "2026-06-22", "s": "12345"},
                {"d0": "2026-06-22", "d1": "2026-06-23", "s": "67890"},
            ]
        )
    )

    with pytest.raises(ValueError, match="exactly one live instrument"):
        chart.resolve_single_instrument(
            historical,
            dataset="GLBX.MDP3",
            market="ES",
            query_symbol="ES.v.0",
            start_date="2026-06-21",
            end_date="2026-06-23",
        )
