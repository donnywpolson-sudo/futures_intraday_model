from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps import live_chart_lightweight as live_chart


@dataclass
class FakeOHLCVRecord:
    ts_event: int = 1_718_717_460_000_000_000
    open: int = 5_500_000_000_000
    high: int = 5_501_000_000_000
    low: int = 5_499_750_000_000
    close: int = 5_500_250_000_000
    volume: int = 42


class SystemMsg:
    msg = "heartbeat"


class SymbolMappingMsg:
    stype_in_symbol = "ES.v.0"
    stype_out_symbol = "ESM6"


class ErrorMsg:
    msg = "subscription error"


class FakeLive:
    instances: list["FakeLive"] = []
    records: list[object] = [FakeOHLCVRecord()]

    def __init__(self, key: str) -> None:
        self.key = key
        self.subscribe_calls: list[dict[str, object]] = []
        self.callbacks: list[object] = []
        self.started = False
        self.stopped = False
        self.block_timeout: float | None = None
        FakeLive.instances.append(self)

    def subscribe(self, **kwargs: object) -> int:
        self.subscribe_calls.append(kwargs)
        return 1

    def add_callback(self, callback: object) -> None:
        self.callbacks.append(callback)

    def start(self) -> None:
        self.started = True
        for record in self.records:
            for callback in self.callbacks:
                callback(record)  # type: ignore[misc]

    def stop(self) -> None:
        self.stopped = True

    def block_for_close(self, timeout: float | None = None) -> None:
        self.block_timeout = timeout


class FakeDB(ModuleType):
    Live = FakeLive


class FakeChart:
    instances: list["FakeChart"] = []

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.updates: list[object] = []
        self.shown = False
        self.closed = False
        self.is_alive = True
        FakeChart.instances.append(self)

    def layout(self, **kwargs: object) -> None:
        self.calls.append(("layout", kwargs))

    def candle_style(self, **kwargs: object) -> None:
        self.calls.append(("candle_style", kwargs))

    def volume_config(self, **kwargs: object) -> None:
        self.calls.append(("volume_config", kwargs))

    def legend(self, **kwargs: object) -> None:
        self.calls.append(("legend", kwargs))

    def watermark(self, **kwargs: object) -> None:
        self.calls.append(("watermark", kwargs))

    def show(self, **kwargs: object) -> None:
        self.calls.append(("show", kwargs))
        self.shown = True

    def update(self, series: object) -> None:
        self.updates.append(series)

    def exit(self) -> None:
        self.closed = True


class FakeChartNoAlive(FakeChart):
    def __init__(self) -> None:
        super().__init__()
        del self.is_alive


class FakeFrame:
    @property
    def T(self) -> "FakeFrame":
        return self


class FakeSeries(dict[str, int | float]):
    def to_frame(self) -> FakeFrame:
        return FakeFrame()


class FakeChartWithSet:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def set(self, _data: object) -> None:
        self.calls.append("set")

    def update(self, _series: object) -> None:
        self.calls.append("update")


def _args(*values: str):
    return live_chart.build_arg_parser().parse_args(list(values))


def _series_factory(candle: dict[str, int | float]) -> dict[str, int | float]:
    return dict(candle)


def test_module_import_does_not_import_databento_or_chart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.modules.pop("apps.live_chart_lightweight", None)
    original_import_module = importlib.import_module

    def fail_on_runtime_import(name: str, package: str | None = None):
        if name in {"databento", "lightweight_charts"}:
            raise AssertionError(f"{name} imported during module import")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_on_runtime_import)
    imported = importlib.import_module("apps.live_chart_lightweight")
    assert imported.DEFAULT_DATASET == "GLBX.MDP3"


def test_missing_key_exits_before_runtime_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_import_databento() -> ModuleType:
        raise AssertionError("databento import should not run without key")

    def fail_import_chart_runtime() -> tuple[type[object], object]:
        raise AssertionError("chart import should not run without key")

    monkeypatch.setattr(live_chart, "import_databento", fail_import_databento)
    monkeypatch.setattr(live_chart, "import_chart_runtime", fail_import_chart_runtime)
    stderr = StringIO()

    result = live_chart.run_live_chart(
        _args("--max-records", "1"),
        env={"DATABENTO_API_KEY": ""},
        stderr=stderr,
    )

    assert result == 2
    assert "Missing DATABENTO_API_KEY" in stderr.getvalue()


def test_fixed_price_to_float_scales_databento_prices() -> None:
    assert live_chart.fixed_price_to_float(5_500_250_000_000) == 5500.25
    assert live_chart.fixed_price_to_float(5500.25) == 5500.25
    assert live_chart.fixed_price_to_float("5500.25") == 5500.25
    with pytest.raises(ValueError, match="undefined"):
        live_chart.fixed_price_to_float(live_chart.UNDEF_PRICE)


def test_normalize_ts_event_returns_utc_epoch_seconds() -> None:
    assert live_chart.normalize_ts_event(1_718_717_460_000_000_000) == 1_718_717_460
    assert live_chart.normalize_ts_event("2024-06-18T13:31:00Z") == 1_718_717_460
    assert (
        live_chart.normalize_ts_event(
            datetime(2024, 6, 18, 13, 31, tzinfo=timezone.utc)
        )
        == 1_718_717_460
    )


def test_ohlcv_record_to_candle_converts_required_fields() -> None:
    candle = live_chart.ohlcv_record_to_candle(FakeOHLCVRecord())

    assert candle == {
        "time": 1_718_717_460,
        "open": 5500.0,
        "high": 5501.0,
        "low": 5499.75,
        "close": 5500.25,
        "volume": 42,
    }


def test_unknown_record_has_readable_skip_message() -> None:
    class UnknownRecord:
        ts_event = 1_718_717_460_000_000_000

    with pytest.raises(ValueError) as exc_info:
        live_chart.ohlcv_record_to_candle(UnknownRecord())

    message = live_chart.describe_record_skip(UnknownRecord(), exc_info.value)
    assert "Skipping UnknownRecord" in message
    assert "missing fields" in message


def test_parse_start_zero_is_integer_replay_start() -> None:
    assert live_chart.parse_start("0") == 0
    assert live_chart.parse_start(None) is None
    assert live_chart.parse_start("2026-06-18T13:30:00Z") == "2026-06-18T13:30:00Z"


def test_callback_pushes_candle_to_queue_without_chart_update() -> None:
    candle_queue = live_chart.queue.Queue()
    stderr = StringIO()
    callback = live_chart.build_record_callback(candle_queue, stderr=stderr)
    callback(FakeOHLCVRecord())

    candle = candle_queue.get_nowait()
    assert candle["close"] == 5500.25
    assert stderr.getvalue() == ""


def test_callback_ignores_databento_control_messages() -> None:
    candle_queue = live_chart.queue.Queue()
    stderr = StringIO()
    callback = live_chart.build_record_callback(candle_queue, stderr=stderr)

    callback(SystemMsg())
    callback(SymbolMappingMsg())

    assert candle_queue.empty()
    assert stderr.getvalue() == ""


def test_callback_ignores_unknown_non_ohlcv_records_without_payload() -> None:
    class UnknownRecord:
        ts_event = 1_718_717_460_000_000_000

    candle_queue = live_chart.queue.Queue()
    stderr = StringIO()
    callback = live_chart.build_record_callback(candle_queue, stderr=stderr)

    callback(UnknownRecord())

    assert candle_queue.empty()
    assert stderr.getvalue() == ""


def test_callback_reports_malformed_ohlcv_like_records() -> None:
    class MissingVolumeRecord:
        ts_event = 1_718_717_460_000_000_000
        open = 5_500_000_000_000
        high = 5_501_000_000_000
        low = 5_499_750_000_000
        close = 5_500_250_000_000

    candle_queue = live_chart.queue.Queue()
    stderr = StringIO()
    callback = live_chart.build_record_callback(candle_queue, stderr=stderr)

    callback(MissingVolumeRecord())

    assert candle_queue.empty()
    assert "Skipping MissingVolumeRecord" in stderr.getvalue()
    assert "missing fields" in stderr.getvalue()


def test_callback_reports_error_records() -> None:
    candle_queue = live_chart.queue.Queue()
    stderr = StringIO()
    callback = live_chart.build_record_callback(candle_queue, stderr=stderr)

    callback(ErrorMsg())

    assert candle_queue.empty()
    assert "Skipping ErrorMsg" in stderr.getvalue()


def test_first_chart_candle_uses_set_when_supported() -> None:
    chart = FakeChartWithSet()
    series = FakeSeries(
        {"time": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}
    )

    live_chart.update_chart_candle(chart, series, initialize=True)
    live_chart.update_chart_candle(chart, series, initialize=False)

    assert chart.calls == ["set", "update"]


def test_live_chart_subscribes_and_updates_from_queue() -> None:
    FakeLive.instances.clear()
    FakeLive.records = [FakeOHLCVRecord(), FakeOHLCVRecord(close=5_500_500_000_000)]
    FakeChart.instances.clear()
    stdout = StringIO()

    result = live_chart.run_live_chart(
        _args("--start", "0", "--max-records", "2", "--timeout-seconds", "1"),
        db_module=FakeDB("databento"),
        chart_factory=FakeChart,
        series_factory=_series_factory,
        env={"DATABENTO_API_KEY": "db-test"},
        stdout=stdout,
    )

    live = FakeLive.instances[-1]
    chart = FakeChart.instances[-1]
    assert result == 0
    assert live.subscribe_calls == [
        {
            "dataset": "GLBX.MDP3",
            "schema": "ohlcv-1m",
            "symbols": "ES.c.0",
            "stype_in": "continuous",
            "start": 0,
        }
    ]
    assert live.started is True
    assert live.stopped is True
    assert live.block_timeout == 1.0
    assert chart.shown is True
    assert chart.closed is True
    assert len(chart.updates) == 2
    assert chart.updates[-1]["close"] == 5500.5
    assert "records_updated=2" in stdout.getvalue()


def test_timeout_stops_client_without_records() -> None:
    FakeLive.instances.clear()
    FakeLive.records = []
    FakeChart.instances.clear()
    stdout = StringIO()

    result = live_chart.run_live_chart(
        _args("--max-records", "1", "--timeout-seconds", "0"),
        db_module=FakeDB("databento"),
        chart_factory=FakeChart,
        series_factory=_series_factory,
        env={"DATABENTO_API_KEY": "db-test"},
        stdout=stdout,
    )

    live = FakeLive.instances[-1]
    chart = FakeChart.instances[-1]
    assert result == 0
    assert live.stopped is True
    assert chart.closed is True
    assert chart.updates == []
    assert "timed_out=True" in stdout.getvalue()


def test_chart_without_alive_state_is_bounded_by_max_records() -> None:
    FakeLive.instances.clear()
    FakeLive.records = [FakeOHLCVRecord()]
    FakeChart.instances.clear()
    stdout = StringIO()

    result = live_chart.run_live_chart(
        _args("--max-records", "1", "--timeout-seconds", "1"),
        db_module=FakeDB("databento"),
        chart_factory=FakeChartNoAlive,
        series_factory=_series_factory,
        env={"DATABENTO_API_KEY": "db-test"},
        stdout=stdout,
    )

    live = FakeLive.instances[-1]
    chart = FakeChart.instances[-1]
    assert result == 0
    assert live.stopped is True
    assert chart.closed is True
    assert len(chart.updates) == 1
    assert "records_updated=1" in stdout.getvalue()
