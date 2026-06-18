from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import live_smoke_databento as live_smoke


@dataclass
class FakeSystemMsg:
    code: str = "heartbeat"
    msg: str = "system ok"
    pretty_ts_event: str = "2026-06-18T13:30:00Z"
    instrument_id: int = 0


@dataclass
class FakeSymbolMappingMsg:
    instrument_id: int = 123
    stype_in_symbol: str = "ES.c.0"
    stype_out_symbol: str = "ESM6"
    pretty_start_ts: str = "2026-06-18T00:00:00Z"
    pretty_end_ts: str = "2026-06-19T00:00:00Z"


@dataclass
class FakeOHLCVMsg:
    instrument_id: int = 123
    pretty_ts_event: str = "2026-06-18T13:31:00Z"
    pretty_open: str = "5500.00"
    pretty_high: str = "5501.00"
    pretty_low: str = "5499.75"
    pretty_close: str = "5500.25"
    volume: int = 42
    open: int = 550000000000
    high: int = 550100000000
    low: int = 549975000000
    close: int = 550025000000


class FakeLive:
    instances: list["FakeLive"] = []

    def __init__(self, key: str) -> None:
        self.key = key
        self.subscribe_calls: list[dict[str, object]] = []
        self.streams: list[Path] = []
        self.callbacks: list[object] = []
        self.started = False
        self.stopped = False
        self.block_timeout: float | None = None
        FakeLive.instances.append(self)

    def subscribe(self, **kwargs: object) -> int:
        self.subscribe_calls.append(kwargs)
        return 1

    def add_stream(self, stream: Path) -> None:
        self.streams.append(stream)

    def add_callback(self, callback: object) -> None:
        self.callbacks.append(callback)

    def start(self) -> None:
        self.started = True
        records = [FakeSystemMsg(), FakeSymbolMappingMsg(), FakeOHLCVMsg()]
        for record in records:
            if self.stopped:
                break
            for callback in self.callbacks:
                callback(record)  # type: ignore[misc]

    def block_for_close(self, timeout: float | None = None) -> None:
        self.block_timeout = timeout

    def stop(self) -> None:
        self.stopped = True


class FakeDB(ModuleType):
    Live = FakeLive


class RuntimeErrorLive(FakeLive):
    def start(self) -> None:
        self.started = True
        raise RuntimeError("live startup failed")


class KeyboardInterruptLive(FakeLive):
    def start(self) -> None:
        self.started = True
        raise KeyboardInterrupt


def _fake_db(live_cls: type[FakeLive]) -> ModuleType:
    module = ModuleType("databento")
    module.Live = live_cls  # type: ignore[attr-defined]
    return module


def _args(*values: str):
    return live_smoke.build_arg_parser().parse_args(list(values))


def test_module_import_does_not_import_databento(monkeypatch: pytest.MonkeyPatch) -> None:
    sys.modules.pop("scripts.live_smoke_databento", None)
    original_import_module = importlib.import_module

    def fail_on_databento(name: str, package: str | None = None):
        if name == "databento":
            raise AssertionError("databento imported during module import")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_on_databento)
    imported = importlib.import_module("scripts.live_smoke_databento")
    assert imported.DEFAULT_DATASET == "GLBX.MDP3"


def test_missing_key_exits_before_databento_import(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_import(name: str):
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(live_smoke, "import_databento", fail_import)
    stderr = StringIO()

    result = live_smoke.run_live_smoke(
        _args("--max-records", "1"),
        env={"DATABENTO_API_KEY": ""},
        stderr=stderr,
    )

    assert result == 2
    assert "Missing DATABENTO_API_KEY" in stderr.getvalue()


def test_live_smoke_subscribes_with_defaults_and_stops_on_max_records() -> None:
    FakeLive.instances.clear()
    stdout = StringIO()

    result = live_smoke.run_live_smoke(
        _args("--start", "0", "--max-records", "2"),
        db_module=FakeDB("databento"),
        env={"DATABENTO_API_KEY": "db-test"},
        stdout=stdout,
    )

    assert result == 0
    live = FakeLive.instances[-1]
    assert live.key == "db-test"
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
    assert live.block_timeout == 60.0
    assert "SYSTEM" in stdout.getvalue()
    assert "SYMBOL_MAPPING" in stdout.getvalue()
    assert "OHLCV" not in stdout.getvalue()


def test_save_dbn_uses_timestamped_default_path(tmp_path: Path) -> None:
    FakeLive.instances.clear()
    stderr = StringIO()
    out_dir = tmp_path / "live_raw"

    result = live_smoke.run_live_smoke(
        _args(
            "--save-dbn",
            "--dbn-out-dir",
            str(out_dir),
            "--max-records",
            "1",
        ),
        db_module=FakeDB("databento"),
        env={"DATABENTO_API_KEY": "db-test"},
        stderr=stderr,
    )

    assert result == 0
    live = FakeLive.instances[-1]
    assert out_dir.is_dir()
    assert len(live.streams) == 1
    assert live.streams[0].parent == out_dir
    assert live.streams[0].name.startswith("databento_live_GLBX_MDP3_ohlcv_1m_ES_c_0_")
    assert live.streams[0].suffix == ".dbn"
    assert "Writing raw DBN" in stderr.getvalue()


def test_format_record_handles_error_and_unknown_records() -> None:
    class ErrorMsg:
        code = "bad_symbol"
        err = "symbol rejected"
        pretty_ts_event = "2026-06-18T13:30:00Z"

    class Unknown:
        instrument_id = 999
        ts_event = 123

    assert "ERROR" in live_smoke.format_record(ErrorMsg())
    assert "RECORD type=Unknown" in live_smoke.format_record(Unknown())


def test_sdk_error_returns_failure_and_stops_client() -> None:
    FakeLive.instances.clear()
    stderr = StringIO()

    result = live_smoke.run_live_smoke(
        _args("--max-records", "1"),
        db_module=_fake_db(RuntimeErrorLive),
        env={"DATABENTO_API_KEY": "db-test"},
        stderr=stderr,
    )

    live = FakeLive.instances[-1]
    assert result == 1
    assert live.started is True
    assert live.stopped is True
    assert "Databento live smoke failed: live startup failed" in stderr.getvalue()


def test_keyboard_interrupt_returns_130_and_stops_client() -> None:
    FakeLive.instances.clear()
    stderr = StringIO()

    result = live_smoke.run_live_smoke(
        _args("--max-records", "1"),
        db_module=_fake_db(KeyboardInterruptLive),
        env={"DATABENTO_API_KEY": "db-test"},
        stderr=stderr,
    )

    live = FakeLive.instances[-1]
    assert result == 130
    assert live.started is True
    assert live.stopped is True
    assert "Interrupted; stopping live smoke." in stderr.getvalue()
