from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest

import live_chart_feed as chart
from live_ops.audit import AuditLogger
from live_ops.bar_builder import LiveBarBuilder, bar_contract_row, check_bar_parity
from live_ops.broker import LiveBroker, PaperBroker
from live_ops.model import ModelReadinessGate, build_signal_state
from live_ops.operator import OperatorStatusState, render_operator_status
from live_ops.quality import DataQualityGate
from live_ops.reconciliation import Reconciler
from live_ops.risk import KillSwitch, RiskManager, SessionGuard
from live_ops.schemas import (
    LiveBar,
    LiveRecord,
    OrderIntent,
    ReconciliationResult,
    RiskDecision,
    paper_smoke_config,
    position_key,
    safe_default_config,
)
from live_ops.smoke import run_smoke

BASE = datetime(2026, 6, 22, 14, 30, tzinfo=timezone.utc)


def bar(**kwargs: object) -> LiveBar:
    values = {
        "symbol": "ES",
        "contract": "ESU6",
        "timestamp_utc": BASE,
        "timeframe": "1m",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 10,
        "bar_is_final": True,
        "source_schema": "synthetic-l1",
    }
    values.update(kwargs)
    return LiveBar(**values)


def order(**kwargs: object) -> OrderIntent:
    values = {
        "order_id": "ORD-1",
        "strategy_id": "test-strategy",
        "symbol": "ES",
        "contract": "ESU6",
        "side": "BUY",
        "quantity": 1,
        "order_type": "LIMIT",
        "limit_price": 100.5,
        "stop_price": None,
        "time_in_force": "DAY",
        "bar_timestamp": BASE,
        "created_timestamp": BASE + timedelta(seconds=1),
        "reason": "test",
        "signal_id": "SIG-1",
    }
    values.update(kwargs)
    return OrderIntent(**values)


def ready_signal(test_bar: LiveBar | None = None):
    test_bar = test_bar or bar()
    dq = DataQualityGate(paper_smoke_config()).validate(test_bar, now=BASE + timedelta(seconds=5))
    model = ModelReadinessGate().evaluate(symbol="ES", features={"close": 100.5})
    signal = build_signal_state(bar=test_bar, data_quality=dq, model_status=model, now=BASE, signal="LONG")
    return dq, model, signal


def test_operator_status_rendering_width() -> None:
    line = render_operator_status(
        OperatorStatusState(
            feed_status="LIVE",
            active_symbol="ES",
            active_contract="ESU6",
            timeframe="1m",
            records_count=20939,
            latest_bar_time=BASE,
            latest_bar_age_seconds=4,
            last_close=7552.25,
            model_status="OFF",
            signal="NO_SIGNAL",
            trading_mode="DISABLED",
            kill_switch="OFF",
            risk_status="OK",
            reconciliation_status="OK",
        ),
        width=80,
    )

    assert len(line) == 79
    assert "\n" not in line


def test_timeout_args_support_disabled_and_enabled() -> None:
    disabled = chart.build_arg_parser().parse_args(["--market", "ES", "--no-timeout"])
    enabled = chart.build_arg_parser().parse_args(["--market", "ES", "--timeout-seconds", "10"])

    assert chart.effective_timeout_seconds(disabled) is None
    assert chart.effective_timeout_seconds(enabled) == 10.0


def test_l1_like_records_derive_final_ohlcv_bar() -> None:
    builder = LiveBarBuilder(timeframe="1m", timeframe_seconds=60)
    records = [
        LiveRecord("ES", "ESU6", BASE + timedelta(seconds=1), 100.0, 2),
        LiveRecord("ES", "ESU6", BASE + timedelta(seconds=20), 101.0, 3),
        LiveRecord("ES", "ESU6", BASE + timedelta(minutes=1), 99.0, 1),
    ]
    emitted = []
    for record in records:
        emitted.extend(builder.update(record))

    assert emitted == [
        LiveBar("ES", "ESU6", BASE, "1m", 100.0, 101.0, 100.0, 101.0, 5, True, "synthetic-l1")
    ]


def test_bar_final_and_partial_handling() -> None:
    builder = LiveBarBuilder(timeframe="1m", timeframe_seconds=60)
    assert builder.update(LiveRecord("ES", "ESU6", BASE + timedelta(seconds=1), 100.0, 1)) == []
    partial = builder.current_bar()

    assert partial is not None
    assert partial.bar_is_final is False


def test_bar_parity_contract_checks_fields_and_timezone() -> None:
    test_bar = bar()
    row = bar_contract_row(test_bar)

    assert check_bar_parity([row], [row]).passed


def test_data_quality_gate_blocks_bad_ohlc_and_duplicate_timestamp() -> None:
    config = paper_smoke_config()
    gate = DataQualityGate(config)

    assert gate.validate(bar(high=98.0), now=BASE).reason_code == "BAD_OHLC"
    assert gate.validate(bar(), now=BASE + timedelta(seconds=1)).passed
    duplicate = gate.validate(bar(), now=BASE + timedelta(seconds=2))

    assert duplicate.reason_code == "DUPLICATE_TIMESTAMP"
    assert duplicate.duplicate_timestamp_policy == "block"


def test_data_quality_gate_blocks_contract_mismatch_and_reconnect_gap() -> None:
    config = paper_smoke_config()
    gate = DataQualityGate(config)
    assert gate.validate(bar(), now=BASE + timedelta(seconds=1)).passed

    gap = gate.validate(bar(timestamp_utc=BASE + timedelta(minutes=10)), now=BASE + timedelta(minutes=10))
    mismatch = DataQualityGate(config).validate(bar(contract="ESZ6"), now=BASE, active_contract="ESU6")

    assert gap.reason_code == "TIMESTAMP_GAP"
    assert mismatch.reason_code in {"UNKNOWN_CONTRACT", "CONTRACT_MISMATCH"}


def test_model_unavailable_and_feature_missing_emit_no_signal() -> None:
    config = paper_smoke_config()
    test_bar = bar()
    dq = DataQualityGate(config).validate(test_bar, now=BASE)
    unavailable = ModelReadinessGate().evaluate(symbol="ES", features={"close": 100.5}, model_available=False)
    missing = ModelReadinessGate(expected_features=("close", "volume")).evaluate(symbol="ES", features={"close": 100.5})

    assert build_signal_state(bar=test_bar, data_quality=dq, model_status=unavailable, signal="LONG").signal == "NO_SIGNAL"
    assert build_signal_state(bar=test_bar, data_quality=dq, model_status=missing, signal="LONG").signal == "NO_SIGNAL"


def test_partial_bar_signal_is_non_tradable() -> None:
    test_bar = bar(bar_is_final=False)
    dq = DataQualityGate(paper_smoke_config()).validate(test_bar, now=BASE)
    model = ModelReadinessGate().evaluate(symbol="ES", features={"close": 100.5})

    signal = build_signal_state(bar=test_bar, data_quality=dq, model_status=model, signal="LONG")

    assert signal.signal == "NO_SIGNAL"
    assert signal.tradable is False


def test_risk_blocks_by_default_and_paper_override_does_not_weaken_defaults() -> None:
    dq, model, signal = ready_signal()
    safe = safe_default_config()
    paper = paper_smoke_config()

    default_risk = RiskManager(safe).evaluate(
        order=order(),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
    )

    assert default_risk.reason_code == "TRADING_DISABLED"
    assert safe.allow_trading is False
    assert paper.allow_trading is True
    assert paper.allow_live_broker is False


def test_risk_blocks_kill_switch_and_session_guard() -> None:
    dq, model, signal = ready_signal()
    config = paper_smoke_config()
    manager = RiskManager(config)
    kill = manager.evaluate(
        order=order(order_id="KILL"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        kill_switch_on=True,
        session_ok=True,
    )
    session = RiskManager(config).evaluate(
        order=order(order_id="SESSION"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=False,
    )

    assert kill.reason_code == "KILL_SWITCH_ON"
    assert session.reason_code == "OUTSIDE_SESSION"


def test_session_guard_missing_or_closed_session_is_false() -> None:
    guard = SessionGuard.from_strings({"ES": ("15:00", "16:00", "UTC")})

    assert guard.is_session_open(BASE, "ES") is False
    assert guard.is_session_open(BASE, "NQ") is False


def test_paper_broker_fill_cancel_flatten_and_duplicate_reject(tmp_path) -> None:
    dq, model, signal = ready_signal()
    config = paper_smoke_config()
    risk = RiskManager(config).evaluate(
        order=order(),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
    )
    broker = PaperBroker(state_path=tmp_path / "paper.json", tick_sizes={"ES": 0.25})
    response = broker.place_order(order(), risk_decision=risk, bar=bar())
    duplicate = broker.place_order(order(), risk_decision=RiskDecision(True, "OK", "approved", order(), None, {}), bar=bar())

    assert response.status == "FILLED"
    assert broker.positions[position_key("ES", "ESU6")] == 1
    assert duplicate.reason_code == "DUPLICATE_ORDER_ID"

    open_broker = PaperBroker(fill_policy="leave_open")
    open_response = open_broker.place_order(order(order_id="OPEN"), risk_decision=risk, bar=bar())
    assert open_response.status == "OPEN"
    assert open_broker.cancel_all() == 1

    fills = broker.flatten_all(timestamp_utc=BASE, prices={"ES:ESU6": 100.0})
    assert len(fills) == 1
    assert broker.positions[position_key("ES", "ESU6")] == 0


def test_reconciliation_mismatch_and_stale_open_order_warning() -> None:
    broker = PaperBroker()
    broker.positions[position_key("ES", "ESU6")] = 1
    mismatch = Reconciler().reconcile(strategy_positions={}, broker=broker, now=BASE)

    open_broker = PaperBroker(fill_policy="leave_open")
    open_broker.open_orders["OLD"] = order(order_id="OLD", created_timestamp=BASE - timedelta(minutes=10))
    stale = Reconciler(stale_order_seconds=60).reconcile(strategy_positions={}, broker=open_broker, now=BASE)

    assert mismatch.status == "FAIL"
    assert stale.status == "OK"
    assert stale.reason_code == "STALE_OPEN_ORDER"


def test_audit_logging_one_row_per_decision_and_exception(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    logger.write_decision({"run_id": "r1", "exception": None})
    logger.write_decision({"run_id": "r1", "exception": "simulated"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "simulated" in lines[1]


def test_live_broker_placeholder_cannot_place_orders() -> None:
    with pytest.raises(NotImplementedError):
        LiveBroker().place_order(order())


def test_kill_switch_file_blocks_orders(tmp_path) -> None:
    switch = KillSwitch(str(tmp_path / "KILL_SWITCH_ON"))
    assert switch.is_on() is False
    switch.turn_on()
    assert switch.is_on() is True
    switch.turn_off()
    assert switch.is_on() is False


def test_smoke_live_trading_script_scenarios(tmp_path) -> None:
    stdout = StringIO()

    assert run_smoke(audit_dir=tmp_path, stdout=stdout)
    assert "PASS live trading smoke" in stdout.getvalue()
