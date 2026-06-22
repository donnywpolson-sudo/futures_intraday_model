from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
import queue
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
    assert [chart.normalize_timeframe(value) for value in ("1m", "5m", "15m", "30m", "1h", "4H", "1D")] == [
        "1m",
        "5m",
        "15m",
        "30m",
        "1h",
        "4h",
        "1d",
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


def test_aggregate_one_minute_candles_to_four_hour_exchange_bucket() -> None:
    candles = [
        {
            "time": datetime(2026, 6, 21, 22, 30, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 2,
        },
        {
            "time": datetime(2026, 6, 21, 23, 45, tzinfo=timezone.utc),
            "open": 100.5,
            "high": 103.0,
            "low": 98.5,
            "close": 102.0,
            "volume": 3,
        },
    ]

    aggregated = chart.aggregate_candles(candles, seconds=chart.timeframe_seconds("4h"), timeframe="4h")

    assert aggregated == [
        {
            "time": datetime(2026, 6, 21, 21, 0, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 103.0,
            "low": 98.5,
            "close": 102.0,
            "volume": 5,
        }
    ]


def test_aggregate_one_minute_candles_to_globex_trading_day() -> None:
    candles = [
        {
            "time": datetime(2026, 6, 21, 22, 30, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 2,
        },
        {
            "time": datetime(2026, 6, 22, 20, 0, tzinfo=timezone.utc),
            "open": 100.5,
            "high": 104.0,
            "low": 98.0,
            "close": 103.0,
            "volume": 4,
        },
        {
            "time": datetime(2026, 6, 22, 22, 30, tzinfo=timezone.utc),
            "open": 200.0,
            "high": 201.0,
            "low": 199.0,
            "close": 200.5,
            "volume": 1,
        },
    ]

    aggregated = chart.aggregate_candles(candles, seconds=chart.timeframe_seconds("1d"), timeframe="1d")

    assert aggregated == [
        {
            "time": datetime(2026, 6, 21, 22, 0, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 104.0,
            "low": 98.0,
            "close": 103.0,
            "volume": 6,
        },
        {
            "time": datetime(2026, 6, 22, 22, 0, tzinfo=timezone.utc),
            "open": 200.0,
            "high": 201.0,
            "low": 199.0,
            "close": 200.5,
            "volume": 1,
        },
    ]


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


def test_chart_market_universe_matches_tier3_config_order() -> None:
    config = chart.load_yaml_mapping(chart.ROOT / "configs" / "alpha_tiered.yaml")
    profile = chart.tier3_research_profile(config)
    expected = tuple(str(symbol) for symbol in profile["markets"])

    assert tuple(info.symbol for info in chart.chart_market_universe(chart.ROOT)) == expected


def test_market_search_one_multiple_and_none() -> None:
    markets = chart.discover_available_markets(chart.ROOT)

    assert [market.symbol for market in chart.matching_markets(markets, "nasdaq")] == ["NQ"]
    assert {market.symbol for market in chart.matching_markets(markets, "energy")} == {"CL", "NG", "RB", "HO"}
    assert chart.matching_markets(markets, "crypto") == []


def test_status_text_reports_model_placeholder_and_stale_data() -> None:
    display = chart.ChartDisplayState(
        raw_candles=[],
        timeframe="5m",
        timeframe_seconds=chart.timeframe_seconds("5m"),
        display_tz=timezone.utc,
        display_tz_name="UTC",
        loading=False,
    )
    status = chart.ChartStatus(
        records_updated=10,
        latest_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )

    text = chart.format_topbar_status(symbols="ESU6", display=display, status=status)

    assert "model output unavailable" in text
    assert "stale" in text


def test_model_overlay_status_formats_available_fields() -> None:
    state = chart.ModelOverlayState(
        available=True,
        signal="LONG",
        score=0.7,
        position="flat",
        gate_status="open",
        realized_pnl=1.25,
        unrealized_pnl=-0.5,
    )

    text = chart.model_overlay_status_text(state)

    assert "signal=LONG" in text
    assert "score=0.7" in text
    assert "position=flat" in text
    assert "gate=open" in text
    assert "realized=1.25" in text
    assert "unrealized=-0.5" in text


def test_market_queue_selects_changed_valid_market_only() -> None:
    markets = {
        "ES": chart.MarketInfo(symbol="ES"),
        "NQ": chart.MarketInfo(symbol="NQ"),
    }
    market_queue: queue.Queue[str] = queue.Queue()
    market_queue.put("ES")
    market_queue.put("BAD")
    market_queue.put("NQ")

    assert chart.drain_market_queue(
        market_queue,
        current_market="ES",
        markets=markets,
    ) == "NQ"


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


def test_resolve_single_instrument_selects_candidate_active_at_end() -> None:
    historical = SimpleNamespace(
        symbology=FakeSymbology(
            [
                {"d0": "2026-06-21", "d1": "2026-06-22", "s": "12345"},
                {"d0": "2026-06-22", "d1": "2026-06-23", "s": "67890"},
            ]
        )
    )

    resolved = chart.resolve_single_instrument(
        historical,
        dataset="GLBX.MDP3",
        market="ES",
        query_symbol="ES.v.0",
        start_date="2026-06-21",
        end_date="2026-06-23",
    )

    assert resolved.instrument_id == 67890


def test_resolve_single_instrument_reports_overlapping_active_candidates() -> None:
    historical = SimpleNamespace(
        symbology=FakeSymbology(
            [
                {"d0": "2026-06-21", "d1": "2026-06-23", "s": "12345"},
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


def test_parse_available_end_matches_databento_exclusive_message() -> None:
    parsed = chart.parse_available_end_from_text(
        "GLBX.MDP3 has data available up to, but not including 2026-06-22. "
        "The query end_date was 2026-06-23."
    )

    assert parsed == datetime(2026, 6, 22, tzinfo=timezone.utc)


def test_clamp_exclusive_end_date_uses_available_end() -> None:
    stderr = StringIO()
    final_end = chart.clamp_exclusive_end_date(
        start_date="2026-06-20",
        requested_end_date="2026-06-23",
        available_exclusive_end_date="2026-06-22",
        context="symbology",
        stderr=stderr,
    )

    assert final_end == "2026-06-22"
    assert "requested=2026-06-23" in stderr.getvalue()


def test_clamp_exclusive_end_date_rejects_empty_window() -> None:
    with pytest.raises(ValueError, match="is not after start date"):
        chart.clamp_exclusive_end_date(
            start_date="2026-06-22",
            requested_end_date="2026-06-23",
            available_exclusive_end_date="2026-06-22",
            context="symbology",
            stderr=StringIO(),
        )


def test_clamp_historical_end_uses_available_midnight() -> None:
    final_end = chart.clamp_historical_end(
        start=datetime(2026, 6, 21, 20, tzinfo=timezone.utc),
        requested_end=datetime(2026, 6, 22, 12, tzinfo=timezone.utc),
        available_exclusive_end_date="2026-06-22",
        stderr=StringIO(),
    )

    assert final_end == datetime(2026, 6, 22, tzinfo=timezone.utc)
