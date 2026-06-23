from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import queue
from types import ModuleType, SimpleNamespace

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
    assert text.startswith("Stale |")


def test_emit_status_line_is_display_only_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = StringIO()
    status = chart.ChartStatus(
        records_updated=3,
        latest_time=datetime(2026, 6, 22, 14, 30, tzinfo=timezone.utc),
        last_close=7552.25,
    )
    monkeypatch.setattr(chart.shutil, "get_terminal_size", lambda fallback: SimpleNamespace(columns=220))

    chart.emit_status_line(status, stdout, symbols="ESU6", timeframe="1m")
    line = stdout.getvalue()

    assert line.startswith("\r")
    assert "\n" not in line
    assert len(line.removeprefix("\r")) <= 220
    assert "ES/ESU6 1m" in line
    assert "model=OFF" in line
    assert "sig=NO_SIGNAL" in line
    assert "mode=DISABLED" in line
    assert "kill=OFF" in line
    assert "risk=UNKNOWN" in line
    assert "recon=UNKNOWN" in line


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


def test_market_callback_accepts_direct_selected_value(monkeypatch: pytest.MonkeyPatch) -> None:
    market_queue: queue.Queue[str] = queue.Queue()
    monkeypatch.setattr(chart.time, "monotonic", lambda: 10.0)
    callback = chart.build_market_callback(
        market_queue,
        current_market=lambda: "ES",
        enabled_after=lambda: 0.0,
    )

    callback("nq")

    assert market_queue.get_nowait() == "NQ"


def test_selection_state_round_trips_market_and_timeframe(tmp_path: Path) -> None:
    state_path = tmp_path / "live_chart_feed_state.json"

    chart.write_selection_state(
        state_path,
        market="NQ",
        timeframe="4h",
        stderr=StringIO(),
    )

    assert chart.load_selection_state(state_path) == {"market": "NQ", "timeframe": "4h"}


class FakeTopbarWidget:
    def __init__(self, value: str, options: tuple[str, ...] = ()) -> None:
        self.value = value
        self.options = options

    def set(self, value: str) -> None:
        self.value = value


class FakeTopbar:
    def __init__(self, chart_obj: "FakeChart") -> None:
        self._chart = chart_obj
        self.widgets: dict[str, FakeTopbarWidget] = {}

    def switcher(
        self,
        name: str,
        options: tuple[str, ...],
        default: str | None = None,
        func: object = None,
    ) -> None:
        widget = FakeTopbarWidget(default or "", options)
        self.widgets[name] = widget

        if callable(func):
            def handler(value: str) -> None:
                widget.value = value
                func(self._chart)

            self._chart.win.handlers[name] = handler

    def textbox(self, name: str, value: str, align: str = "left") -> None:
        _ = align
        self.widgets[name] = FakeTopbarWidget(value)

    def get(self, name: str) -> FakeTopbarWidget | None:
        return self.widgets.get(name)

    def __getitem__(self, name: str) -> FakeTopbarWidget:
        return self.widgets[name]


class FakeWebView:
    def __init__(self) -> None:
        self.emit_queue: queue.Queue[str] = queue.Queue()

    def exit(self) -> None:
        return None


class FakeChart:
    WV = FakeWebView()

    def __init__(self) -> None:
        type(self).WV = FakeWebView()
        self.win = SimpleNamespace(handlers={})
        self.topbar = FakeTopbar(self)
        self.frames: list[object] = []
        self.is_alive = True

    def set(self, frame: object) -> None:
        self.frames.append(frame)

    def update(self, series: object) -> None:
        self.frames.append(series)

    def show(self, block: bool = False) -> None:
        _ = block

    def watermark(self, **kwargs: object) -> None:
        _ = kwargs

    def exit(self) -> None:
        self.is_alive = False


def test_timeframe_switch_down_uses_one_minute_source_candles() -> None:
    fake_chart = FakeChart()
    display = chart.ChartDisplayState(
        raw_candles=[],
        timeframe="4h",
        timeframe_seconds=chart.timeframe_seconds("4h"),
        display_tz=timezone.utc,
        display_tz_name="UTC",
    )
    status = chart.ChartStatus()
    source_candles = [
        one_minute_candle(0, 100.0),
        one_minute_candle(1, 101.0),
        one_minute_candle(2, 102.0),
    ]

    chart.replace_source_candles(display, status, source_candles)
    chart.render_chart_display(
        display,
        chart=fake_chart,
        series_factory=lambda candle: candle,
        status=status,
        symbols="ESU6",
        schema="trades",
        mode="test",
        stdout=StringIO(),
    )
    four_hour_frame = [frame for frame in fake_chart.frames if getattr(frame, "empty", False) is False][-1]
    assert len(four_hour_frame) == 1

    timeframe_queue: queue.Queue[str] = queue.Queue()
    timeframe_queue.put("1m")
    assert chart.drain_timeframe_queue(
        timeframe_queue,
        display=display,
        chart_timeframes=chart.SUPPORTED_CHART_TIMEFRAMES,
    )
    chart.render_chart_display(
        display,
        chart=fake_chart,
        series_factory=lambda candle: candle,
        status=status,
        symbols="ESU6",
        schema="trades",
        mode="test",
        stdout=StringIO(),
    )

    one_minute_frame = [frame for frame in fake_chart.frames if getattr(frame, "empty", False) is False][-1]
    assert len(one_minute_frame) == len(source_candles)
    assert [float(value) for value in one_minute_frame["close"]] == [100.0, 101.0, 102.0]


def test_drain_chart_queue_logs_timeframe_switch_render_and_keeps_options() -> None:
    fake_chart = FakeChart()
    chart.configure_timeframe_switcher(
        fake_chart,
        timeframe_options=chart.SUPPORTED_CHART_TIMEFRAMES,
        selected_timeframe="1m",
        on_timeframe_change=None,
    )
    display = chart.ChartDisplayState(
        raw_candles=[],
        timeframe="1m",
        timeframe_seconds=chart.timeframe_seconds("1m"),
        display_tz=timezone.utc,
        display_tz_name="UTC",
        loading=False,
        topbar_state=chart.CHART_STATE_LIVE,
    )
    status = chart.ChartStatus()
    chart.replace_source_candles(
        display,
        status,
        [one_minute_candle(minute, close=100.0 + minute) for minute in range(5)],
    )
    display.loading = False
    display.topbar_state = chart.CHART_STATE_LIVE
    timeframe_queue: queue.Queue[str] = queue.Queue()
    timeframe_queue.put("5m")
    stderr = StringIO()

    chart.drain_chart_queue(
        queue.Queue(),
        chart=fake_chart,
        series_factory=lambda candle: candle,
        display=display,
        timeframe_queue=timeframe_queue,
        market_queue=queue.Queue(),
        chart_timeframes=chart.SUPPORTED_CHART_TIMEFRAMES,
        markets={"ES": chart.MarketInfo(symbol="ES")},
        max_records=0,
        timeout_seconds=0,
        no_data_warning_seconds=0,
        status=status,
        symbols="ESU6",
        market="ES",
        schema="trades",
        mode="test",
        stdout=StringIO(),
        stderr=stderr,
        timing=chart.LiveChartTiming(stderr=stderr),
        clock=lambda: 0.0,
    )

    assert fake_chart.topbar["timeframe"].options == chart.SUPPORTED_CHART_TIMEFRAMES
    assert "Live chart timing: timeframe switch render 5m" in stderr.getvalue()


class FakeStore:
    def __init__(self, instrument_id: int) -> None:
        self.instrument_id = instrument_id

    def to_df(self, **kwargs: object) -> object:
        _ = kwargs
        pandas = __import__("pandas")
        close = 100.0 if self.instrument_id == 101 else 200.0
        return pandas.DataFrame(
            [
                {
                    "ts_event": datetime(2026, 6, 21, 22, 0, tzinfo=timezone.utc),
                    "open": close - 1,
                    "high": close + 1,
                    "low": close - 2,
                    "close": close,
                    "volume": 10,
                }
            ]
        )


class FakeHistorical:
    def __init__(self, key: str, state: SimpleNamespace) -> None:
        _ = key
        self._state = state
        self.metadata = SimpleNamespace(get_dataset_range=lambda dataset: {"end": "2026-06-22"})
        self.symbology = SimpleNamespace(resolve=self.resolve)
        self.timeseries = SimpleNamespace(get_range=self.get_range)

    def resolve(self, **kwargs: object) -> dict[str, object]:
        stype_out = kwargs["stype_out"]
        symbols = kwargs["symbols"]
        if stype_out == "instrument_id":
            instrument_id = 101 if symbols == "ES.v.0" else 202
            return {"result": {symbols: [{"d0": kwargs["start_date"], "d1": kwargs["end_date"], "s": str(instrument_id)}]}}
        raw_symbol = "ESU6" if int(symbols) == 101 else "NQU6"
        return {"result": {str(symbols): [{"d0": kwargs["start_date"], "d1": kwargs["end_date"], "s": raw_symbol}]}}

    def get_range(self, **kwargs: object) -> FakeStore:
        self._state.historical_requests.append(dict(kwargs))
        return FakeStore(int(kwargs["symbols"]))


class FakeLive:
    def __init__(self, key: str, state: SimpleNamespace) -> None:
        _ = key
        self._state = state
        self._callback = None
        self._stopped = False
        self._state.lives.append(self)

    def subscribe(self, **kwargs: object) -> None:
        self._state.live_subscriptions.append(dict(kwargs))

    def add_callback(self, callback: object) -> None:
        self._callback = callback

    def start(self) -> None:
        if len(self._state.live_subscriptions) == 1:
            assert callable(self._callback)
            self._callback(
                SimpleNamespace(
                    ts_event=datetime(2026, 6, 21, 22, 1, tzinfo=timezone.utc),
                    price=999.0,
                    size=1,
                )
            )
            FakeChart.WV.emit_queue.put("market_~_NQ")

    def stop(self) -> None:
        self._stopped = True

    def block_for_close(self, timeout: float = 1.0) -> None:
        _ = timeout


class FailingStartLive(FakeLive):
    def start(self) -> None:
        raise RuntimeError(
            "Connection to glbx-mdp3.lsg.databento.com:13000 failed: "
            "[Errno 11002] getaddrinfo failed"
        )


class SwitchBackLive(FakeLive):
    def start(self) -> None:
        switch_index = len(self._state.live_subscriptions) - 1
        switch_markets = getattr(self._state, "switch_markets", ())
        if switch_index < len(switch_markets):
            FakeChart.WV.emit_queue.put(f"market_~_{switch_markets[switch_index]}")


def fake_databento_module(state: SimpleNamespace, live_cls: type[FakeLive] = FakeLive) -> ModuleType:
    module = ModuleType("fake_databento")
    module.Historical = lambda key: FakeHistorical(key, state)
    module.Live = lambda key: live_cls(key, state)
    return module


def test_run_live_chart_switches_backfill_and_subscription_to_selected_market(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(historical_requests=[], live_subscriptions=[], lives=[])
    fake_chart = FakeChart()
    stderr = StringIO()
    monotonic_values = iter([100.0, 103.0, 103.0, 103.0, 103.1, 103.2, 103.3])
    monkeypatch.setattr(chart.time, "monotonic", lambda: next(monotonic_values, 103.3))

    result = chart.run_live_chart(
        chart.build_arg_parser().parse_args(
            [
                "--market",
                "ES",
                "--timeframe",
                "5m",
                "--historical-backfill",
                "--lookback-hours",
                "4",
                "--timeout-seconds",
                "0.01",
                "--no-persist-selection",
            ]
        ),
        env={"DATABENTO_API_KEY": "db-test"},
        db_module=fake_databento_module(state),
        chart_factory=lambda: fake_chart,
        series_factory=lambda candle: candle,
        stdout=StringIO(),
        stderr=stderr,
        now=datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc),
    )

    assert result == 0
    assert [request["symbols"] for request in state.historical_requests] == [101, 202]
    assert [subscription["symbols"] for subscription in state.live_subscriptions] == [101, 202]
    assert state.lives[0]._stopped is True
    final_non_empty_frame = [frame for frame in fake_chart.frames if getattr(frame, "empty", False) is False][-1]
    assert float(final_non_empty_frame.iloc[-1]["close"]) == 200.0
    assert 999.0 not in [
        float(frame.iloc[-1]["close"])
        for frame in fake_chart.frames
        if hasattr(frame, "empty") and not frame.empty
    ]
    timing_log = stderr.getvalue()
    assert "Live chart timing: chart launch/show" in timing_log
    assert "Live chart timing: dataset range lookup" in timing_log
    assert "Live chart timing: symbology resolve ES" in timing_log
    assert "Live chart timing: historical fetch ES" in timing_log
    assert "Live chart timing: first historical render" in timing_log
    assert "Live chart timing: live subscribe ES" in timing_log
    assert "Live chart timing: live start ES" in timing_log
    assert "Live chart timing: symbology resolve NQ" in timing_log
    assert "Live chart timing: historical fetch NQ" in timing_log
    assert "Live chart timing: market switch render NQ" in timing_log
    assert "Live chart timing: live subscribe NQ" in timing_log


def test_run_live_chart_keeps_historical_backfill_when_live_dns_fails() -> None:
    state = SimpleNamespace(historical_requests=[], live_subscriptions=[], lives=[])
    fake_chart = FakeChart()
    stdout = StringIO()
    stderr = StringIO()

    result = chart.run_live_chart(
        chart.build_arg_parser().parse_args(
            [
                "--market",
                "ES",
                "--timeframe",
                "1m",
                "--historical-backfill",
                "--lookback-hours",
                "4",
                "--timeout-seconds",
                "0",
                "--no-persist-selection",
            ]
        ),
        env={"DATABENTO_API_KEY": "db-test"},
        db_module=fake_databento_module(state, FailingStartLive),
        chart_factory=lambda: fake_chart,
        series_factory=lambda candle: candle,
        stdout=stdout,
        stderr=stderr,
        now=datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc),
    )

    assert result == 0
    assert [request["symbols"] for request in state.historical_requests] == [101]
    assert [subscription["symbols"] for subscription in state.live_subscriptions] == [101]
    assert state.lives[0]._stopped is True
    assert "Databento live stream unavailable after historical backfill" in stderr.getvalue()
    assert "Databento live chart failed" not in stderr.getvalue()
    assert "timed_out=True" in stdout.getvalue()
    assert fake_chart.topbar["status"].value.startswith("Historical-only |")


def test_run_live_chart_reuses_cached_backfill_when_switching_back_to_market(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(
        historical_requests=[],
        live_subscriptions=[],
        lives=[],
        switch_markets=("NQ", "ES"),
    )
    fake_chart = FakeChart()
    monotonic_value = 100.0

    def advance_monotonic() -> float:
        nonlocal monotonic_value
        monotonic_value += 2.0
        return monotonic_value

    monkeypatch.setattr(chart.time, "monotonic", advance_monotonic)

    result = chart.run_live_chart(
        chart.build_arg_parser().parse_args(
            [
                "--market",
                "ES",
                "--timeframe",
                "1m",
                "--historical-backfill",
                "--lookback-hours",
                "4",
                "--timeout-seconds",
                "0.01",
                "--no-persist-selection",
            ]
        ),
        env={"DATABENTO_API_KEY": "db-test"},
        db_module=fake_databento_module(state, SwitchBackLive),
        chart_factory=lambda: fake_chart,
        series_factory=lambda candle: candle,
        stdout=StringIO(),
        stderr=StringIO(),
        now=datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc),
    )

    assert result == 0
    assert [request["symbols"] for request in state.historical_requests] == [101, 202]
    assert [subscription["symbols"] for subscription in state.live_subscriptions] == [101, 202, 101]


def test_run_live_chart_uses_persisted_market_and_timeframe(tmp_path: Path) -> None:
    state = SimpleNamespace(historical_requests=[], live_subscriptions=[], lives=[])
    state_path = tmp_path / "live_chart_feed_state.json"
    fake_chart = FakeChart()
    monotonic_values = iter([103.0, 103.0, 103.02])
    chart.write_selection_state(
        state_path,
        market="NQ",
        timeframe="4h",
        stderr=StringIO(),
    )

    result = chart.run_live_chart(
        chart.build_arg_parser().parse_args(
            [
                "--historical-backfill",
                "--lookback-hours",
                "4",
                "--timeout-seconds",
                "0.01",
                "--selection-state-path",
                str(state_path),
            ]
        ),
        env={"DATABENTO_API_KEY": "db-test"},
        db_module=fake_databento_module(state),
        chart_factory=lambda: fake_chart,
        series_factory=lambda candle: candle,
        stdout=StringIO(),
        stderr=StringIO(),
        now=datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc),
        clock=lambda: next(monotonic_values, 103.02),
    )

    assert result == 0
    assert [request["symbols"] for request in state.historical_requests] == [202]
    assert [subscription["symbols"] for subscription in state.live_subscriptions] == [202]
    assert chart.load_selection_state(state_path) == {"market": "NQ", "timeframe": "4h"}
    assert fake_chart.topbar["timeframe"].value == "4h"
    assert fake_chart.topbar["timeframe"].options == chart.SUPPORTED_CHART_TIMEFRAMES


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
