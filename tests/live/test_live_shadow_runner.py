from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import live_shadow_runner as live_shadow


@dataclass
class FakeOHLCVRecord:
    ts_event: int = 1_718_721_060_000_000_000
    open: int = 5_500_000_000_000
    high: int = 5_501_000_000_000
    low: int = 5_499_750_000_000
    close: int = 5_500_250_000_000
    volume: int = 42
    instrument_id: int = 123
    publisher_id: int = 1
    rtype: int = 33


class FakeSystemRecord:
    msg = "system"


class FakeRegressor:
    def predict(self, x):  # noqa: ANN001
        return np.full(len(x), 0.25)


class FakeClassifier:
    def __init__(self, classes: list[int], probs: list[float]) -> None:
        self.classes_ = np.asarray(classes)
        self.probs = np.asarray(probs, dtype=float)

    def predict_proba(self, x):  # noqa: ANN001
        return np.tile(self.probs, (len(x), 1))


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
            if self.stopped:
                break
            for callback in self.callbacks:
                callback(record)  # type: ignore[misc]

    def block_for_close(self, timeout: float | None = None) -> None:
        self.block_timeout = timeout

    def stop(self) -> None:
        self.stopped = True


class RuntimeErrorLive(FakeLive):
    def start(self) -> None:
        self.started = True
        raise RuntimeError("live failed")


class FakeDB(ModuleType):
    Live = FakeLive


def _fake_db(live_cls: type[FakeLive]) -> ModuleType:
    module = ModuleType("databento")
    module.Live = live_cls  # type: ignore[attr-defined]
    return module


def _bundle() -> live_shadow.ModelBundle:
    return live_shadow.ModelBundle(
        feature_cols=["feature_ret_1"],
        estimators={
            live_shadow.TARGET_RETURN: FakeRegressor(),
            live_shadow.TARGET_DIRECTION: FakeClassifier([-1, 0, 1], [0.10, 0.10, 0.80]),
            live_shadow.TARGET_FADE: FakeClassifier([0, 1], [0.30, 0.70]),
            live_shadow.TARGET_TREND: FakeClassifier([0, 1], [0.80, 0.20]),
        },
    )


def _args(tmp_path: Path, *values: str):
    bundle_path = tmp_path / "bundle.joblib"
    bundle_path.write_text("fake", encoding="utf-8")
    signals = tmp_path / "signals.jsonl"
    bars = tmp_path / "bars.jsonl"
    return live_shadow.build_arg_parser().parse_args(
        [
            "--model-bundle",
            str(bundle_path),
            "--signals-output",
            str(signals),
            "--bars-output",
            str(bars),
            *values,
        ]
    )


def _loader(_: Path) -> live_shadow.ModelBundle:
    return _bundle()


def test_missing_key_exits_before_model_or_databento_import(tmp_path: Path) -> None:
    def fail_loader(path: Path) -> live_shadow.ModelBundle:
        raise AssertionError(f"unexpected model load: {path}")

    stderr = StringIO()
    result = live_shadow.run_live_shadow(
        _args(tmp_path),
        env={"DATABENTO_API_KEY": ""},
        db_module=FakeDB("databento"),
        model_loader=fail_loader,
        stderr=stderr,
    )

    assert result == 2
    assert "Missing DATABENTO_API_KEY" in stderr.getvalue()


def test_missing_model_bundle_exits_before_subscribe(tmp_path: Path) -> None:
    args = live_shadow.build_arg_parser().parse_args(
        ["--model-bundle", str(tmp_path / "missing.joblib")]
    )
    stderr = StringIO()

    result = live_shadow.run_live_shadow(
        args,
        env={"DATABENTO_API_KEY": "db-test"},
        db_module=FakeDB("databento"),
        stderr=stderr,
    )

    assert result == 2
    assert "Missing model bundle" in stderr.getvalue()
    assert FakeLive.instances == []


def test_default_subscription_args_and_outputs_use_fake_databento(tmp_path: Path) -> None:
    FakeLive.instances.clear()
    FakeLive.records = [FakeSystemRecord(), FakeOHLCVRecord()]
    stdout = StringIO()

    result = live_shadow.run_live_shadow(
        _args(tmp_path, "--start", "0", "--max-bars", "1", "--timeout-seconds", "3"),
        env={"DATABENTO_API_KEY": "db-test"},
        db_module=FakeDB("databento"),
        model_loader=_loader,
        stdout=stdout,
    )

    live = FakeLive.instances[-1]
    assert result == 0
    assert live.subscribe_calls == [
        {
            "dataset": "GLBX.MDP3",
            "schema": "ohlcv-1m",
            "symbols": "ES.v.0",
            "stype_in": "continuous",
            "start": 0,
        }
    ]
    assert live.started is True
    assert live.stopped is True
    assert live.block_timeout == 3.0
    assert "insufficient_feature_warmup" in stdout.getvalue()
    assert (tmp_path / "bars.jsonl").exists()
    assert (tmp_path / "signals.jsonl").exists()


def test_invalid_ohlcv_blocks_signal(tmp_path: Path) -> None:
    bar = FakeOHLCVRecord(high=5_499_000_000_000, low=5_501_000_000_000)
    payload = live_shadow.build_signal_payload(
        [live_shadow.ohlcv_record_to_bar(bar, market="ES", symbol="ES.v.0")],
        market="ES",
        model_bundle=_bundle(),
        tick_size=0.25,
        session_config=Path("configs/market_sessions.yaml"),
        policy=live_shadow.PolicyConfig(),
        min_feature_bars=1,
    )

    assert payload["signal"] == "NO_FADE"
    assert payload["do_not_fade"] is True
    assert "invalid_ohlcv" in payload["reason_flags"]


def test_warmup_blocks_before_model_signal(tmp_path: Path) -> None:
    payload = live_shadow.build_signal_payload(
        [live_shadow.ohlcv_record_to_bar(FakeOHLCVRecord(), market="ES", symbol="ES.v.0")],
        market="ES",
        model_bundle=_bundle(),
        tick_size=0.25,
        session_config=Path("configs/market_sessions.yaml"),
        policy=live_shadow.PolicyConfig(),
        min_feature_bars=2,
    )

    assert payload["signal"] == "NO_FADE"
    assert payload["confidence"] == 0.0
    assert payload["reason_flags"] == ["insufficient_feature_warmup"]


def test_valid_fake_signal_prints_and_writes_jsonl(tmp_path: Path) -> None:
    FakeLive.instances.clear()
    FakeLive.records = [FakeOHLCVRecord()]
    stdout = StringIO()

    result = live_shadow.run_live_shadow(
        _args(tmp_path, "--max-bars", "1", "--min-feature-bars", "1"),
        env={"DATABENTO_API_KEY": "db-test"},
        db_module=FakeDB("databento"),
        model_loader=_loader,
        stdout=stdout,
    )

    assert result == 0
    assert "signal=LONG_FADE" in stdout.getvalue()
    signal = json.loads((tmp_path / "signals.jsonl").read_text(encoding="utf-8"))
    bar = json.loads((tmp_path / "bars.jsonl").read_text(encoding="utf-8"))
    assert signal["signal"] == "LONG_FADE"
    assert signal["do_not_fade"] is False
    assert signal["fade_ok"] is True
    assert signal["suggested_direction"] == "LONG"
    assert signal["confidence"] == pytest.approx(0.7)
    assert signal["reason_flags"] == []
    assert bar["close"] == 5500.25


def test_sdk_error_returns_failure_and_stops_client(tmp_path: Path) -> None:
    FakeLive.instances.clear()
    stderr = StringIO()

    result = live_shadow.run_live_shadow(
        _args(tmp_path, "--max-bars", "1"),
        env={"DATABENTO_API_KEY": "db-test"},
        db_module=_fake_db(RuntimeErrorLive),
        model_loader=_loader,
        stderr=stderr,
    )

    live = FakeLive.instances[-1]
    assert result == 1
    assert live.started is True
    assert live.stopped is True
    assert "Databento live shadow failed: live failed" in stderr.getvalue()
