from __future__ import annotations

import ast
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pytest

import live_chart_feed as chart
import scripts.kill_switch_off as kill_switch_off_script
import scripts.kill_switch_on as kill_switch_on_script
import scripts.paper_cancel_all as paper_cancel_all_script
import scripts.paper_flatten_all as paper_flatten_all_script
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
    state = OperatorStatusState(
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
        paper_position="ES:1",
        last_error_code="DATA_STALE",
    )
    line = render_operator_status(state, width=80)
    wide_line = render_operator_status(state, width=220)

    assert len(line) == 79
    assert "\n" not in line
    for expected in (
        "LIVE",
        "ES/ESU6 1m",
        "rows=20939",
        "latest=2026-06-22 14:30Z",
        "age=4s",
        "close=7552.25",
        "model=OFF",
        "sig=NO_SIGNAL",
        "mode=DISABLED",
        "kill=OFF",
        "risk=OK",
        "recon=OK",
        "pos=ES:1",
        "err=DATA_STALE",
    ):
        assert expected in wide_line


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


def test_bar_builder_blocks_mixed_contract_window() -> None:
    builder = LiveBarBuilder(timeframe="1m", timeframe_seconds=60)

    assert builder.update(LiveRecord("ES", "ESU6", BASE + timedelta(seconds=1), 100.0, 1)) == []
    with pytest.raises(ValueError, match="cannot mix symbols or contracts"):
        builder.update(LiveRecord("ES", "ESZ6", BASE + timedelta(seconds=2), 101.0, 1))


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
    assert DataQualityGate(config).validate(
        bar(timestamp_utc=BASE - timedelta(minutes=10)),
        now=BASE,
    ).reason_code == "DATA_STALE"
    assert gate.validate(bar(), now=BASE + timedelta(seconds=1)).passed
    duplicate = gate.validate(bar(), now=BASE + timedelta(seconds=2))

    assert duplicate.reason_code == "DUPLICATE_TIMESTAMP"
    assert duplicate.duplicate_timestamp_policy == "block"


def test_data_quality_gate_blocks_contract_mismatch_and_reconnect_gap() -> None:
    config = paper_smoke_config()
    gate = DataQualityGate(config)
    assert gate.validate(bar(), now=BASE + timedelta(seconds=1)).passed

    gap = gate.validate(bar(timestamp_utc=BASE + timedelta(minutes=10)), now=BASE + timedelta(minutes=10))
    mismatch_config = replace(config, allowed_contracts=("ESU6", "ESZ6"))
    mismatch = DataQualityGate(mismatch_config).validate(bar(contract="ESZ6"), now=BASE, active_contract="ESU6")

    assert gap.reason_code == "TIMESTAMP_GAP"
    assert mismatch.reason_code == "CONTRACT_MISMATCH"


def test_data_quality_stale_heartbeat_blocks_risk() -> None:
    config = paper_smoke_config()
    dq = DataQualityGate(config).validate(
        bar(),
        now=BASE + timedelta(seconds=40),
        heartbeat_timestamp_utc=BASE,
    )
    model = ModelReadinessGate().evaluate(symbol="ES", features={"close": 100.5})
    signal = build_signal_state(bar=bar(), data_quality=dq, model_status=model, now=BASE, signal="LONG")

    decision = RiskManager(config).evaluate(
        order=order(order_id="HEARTBEAT", signal_id="SIG-HEARTBEAT"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
    )

    assert dq.reason_code == "HEARTBEAT_STALE"
    assert decision.reason_code == "DATA_QUALITY_HEARTBEAT_STALE"


def test_data_quality_gap_and_duplicate_after_reconnect_block_risk() -> None:
    config = paper_smoke_config()
    gate = DataQualityGate(config)
    assert gate.validate(bar(), now=BASE + timedelta(seconds=1)).passed

    gap_bar = bar(timestamp_utc=BASE + timedelta(minutes=10))
    gap = gate.validate(gap_bar, now=BASE + timedelta(minutes=10))
    duplicate_gate = DataQualityGate(config)
    assert duplicate_gate.validate(bar(), now=BASE + timedelta(seconds=1)).passed
    duplicate = duplicate_gate.validate(bar(), now=BASE + timedelta(seconds=2))
    model = ModelReadinessGate().evaluate(symbol="ES", features={"close": 100.5})
    gap_signal = build_signal_state(bar=gap_bar, data_quality=gap, model_status=model, now=BASE, signal="LONG")
    duplicate_signal = build_signal_state(bar=bar(), data_quality=duplicate, model_status=model, now=BASE, signal="LONG")

    gap_decision = RiskManager(config).evaluate(
        order=order(order_id="GAP", signal_id="SIG-GAP", bar_timestamp=gap_bar.timestamp_utc),
        signal=gap_signal,
        data_quality=gap,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
        reconnect_reconciled=True,
    )
    duplicate_decision = RiskManager(config).evaluate(
        order=order(order_id="DUP", signal_id="SIG-DUP"),
        signal=duplicate_signal,
        data_quality=duplicate,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
        reconnect_reconciled=True,
    )

    assert gap.reason_code == "TIMESTAMP_GAP"
    assert gap_decision.reason_code == "DATA_QUALITY_TIMESTAMP_GAP"
    assert duplicate.reason_code == "DUPLICATE_TIMESTAMP"
    assert duplicate.duplicate_timestamp_policy == "block"
    assert duplicate_decision.reason_code == "DATA_QUALITY_DUPLICATE_TIMESTAMP"


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
    assert safe.allow_paper_trading is False
    assert safe.allow_live_broker is False
    assert safe.duplicate_timestamp_policy == "block"
    assert paper.allow_trading is True
    assert paper.allow_live_broker is False


def test_risk_blocks_live_mode_and_live_broker_flag() -> None:
    dq, model, signal = ready_signal()

    for config in (
        replace(paper_smoke_config(), allow_live_broker=True),
        replace(paper_smoke_config(), mode="live"),
    ):
        decision = RiskManager(config).evaluate(
            order=order(),
            signal=signal,
            data_quality=dq,
            model_status=model,
            reconciliation=ReconciliationResult("OK", "OK", {}),
            positions={},
            now=BASE,
            session_ok=True,
        )

        assert decision.reason_code == "LIVE_BROKER_BLOCKED"


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


def test_missing_session_config_rejects_risk_approval() -> None:
    dq, model, signal = ready_signal()
    guard = SessionGuard.from_strings({"NQ": ("00:00", "23:59", "UTC")})

    decision = RiskManager(paper_smoke_config(), session_guard=guard).evaluate(
        order=order(order_id="SESSION-MISSING", signal_id="SIG-SESSION-MISSING"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=None,
    )
    dq_session = DataQualityGate(paper_smoke_config(), session_guard=guard).validate(bar(), now=BASE)

    assert decision.reason_code == "OUTSIDE_SESSION"
    assert dq_session.reason_code == "SESSION_CLOSED"


def test_contract_mismatch_blocks_risk_approval() -> None:
    config = replace(paper_smoke_config(), allowed_contracts=("ESU6", "ESZ6"))
    mismatch_bar = bar(contract="ESZ6")
    dq = DataQualityGate(config).validate(mismatch_bar, now=BASE, active_contract="ESU6")
    model = ModelReadinessGate().evaluate(symbol="ES", features={"close": 100.5})
    signal = build_signal_state(bar=mismatch_bar, data_quality=dq, model_status=model, now=BASE, signal="LONG")

    decision = RiskManager(config).evaluate(
        order=order(order_id="CONTRACT-MISMATCH", signal_id="SIG-CONTRACT-MISMATCH", contract="ESZ6"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
    )

    assert dq.reason_code == "CONTRACT_MISMATCH"
    assert decision.reason_code == "DATA_QUALITY_CONTRACT_MISMATCH"


def test_reconnect_requires_data_quality_and_reconciliation_before_risk_approval() -> None:
    dq, model, signal = ready_signal()
    config = paper_smoke_config()

    pending = RiskManager(config).evaluate(
        order=order(order_id="RECONNECT-PENDING", signal_id="SIG-RECONNECT-PENDING"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
        reconnect_reconciled=False,
    )
    failed = RiskManager(config).evaluate(
        order=order(order_id="RECONNECT-FAIL", signal_id="SIG-RECONNECT-FAIL"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("FAIL", "POSITION_MISMATCH", {}),
        positions={},
        now=BASE,
        session_ok=True,
        reconnect_reconciled=True,
    )
    approved = RiskManager(config).evaluate(
        order=order(order_id="RECONNECT-OK", signal_id="SIG-RECONNECT-OK"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
        reconnect_reconciled=True,
    )

    assert pending.reason_code == "RECONNECT_RECONCILIATION_PENDING"
    assert failed.reason_code == "RECONCILIATION_FAILED"
    assert approved.approved


def test_paper_broker_fill_cancel_flatten_and_duplicate_reject(tmp_path) -> None:
    dq, model, signal = ready_signal()
    config = paper_smoke_config()
    safe_risk = RiskManager(safe_default_config()).evaluate(
        order=order(order_id="SAFE"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
    )
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
    safe_response = PaperBroker().place_order(order(order_id="SAFE"), risk_decision=safe_risk, bar=bar())
    broker = PaperBroker(state_path=tmp_path / "paper.json", tick_sizes={"ES": 0.25})
    response = broker.place_order(order(), risk_decision=risk, bar=bar())
    duplicate = broker.place_order(order(), risk_decision=RiskDecision(True, "OK", "approved", order(), None, {}), bar=bar())

    assert safe_response.reason_code == "RISK_REJECTED"
    assert safe_response.accepted is False
    assert response.status == "FILLED"
    assert broker.positions[position_key("ES", "ESU6")] == 1
    loaded = PaperBroker.load(tmp_path / "paper.json")
    assert loaded.positions[position_key("ES", "ESU6")] == 1
    assert loaded.fills[0].order_id == "ORD-1"
    assert duplicate.reason_code == "DUPLICATE_ORDER_ID"

    open_broker = PaperBroker(fill_policy="leave_open")
    open_response = open_broker.place_order(order(order_id="OPEN"), risk_decision=risk, bar=bar())
    assert open_response.status == "OPEN"
    assert open_broker.cancel_all() == 1

    fills = broker.flatten_all(timestamp_utc=BASE, prices={"ES:ESU6": 100.0})
    assert len(fills) == 1
    assert broker.positions[position_key("ES", "ESU6")] == 0


def test_reconciliation_mismatch_and_stale_open_order_warning() -> None:
    assert Reconciler().reconcile(strategy_positions={}, broker=PaperBroker(), now=BASE).status == "OK"

    broker = PaperBroker()
    broker.positions[position_key("ES", "ESU6")] = 1
    mismatch = Reconciler().reconcile(strategy_positions={}, broker=broker, now=BASE)

    open_mismatch_broker = PaperBroker()
    open_mismatch_broker.open_orders["OPEN"] = order(order_id="OPEN")
    open_mismatch = Reconciler().reconcile(
        strategy_positions={},
        strategy_open_orders=set(),
        broker=open_mismatch_broker,
        now=BASE,
    )
    open_broker = PaperBroker(fill_policy="leave_open")
    open_broker.open_orders["OLD"] = order(order_id="OLD", created_timestamp=BASE - timedelta(minutes=10))
    stale = Reconciler(stale_order_seconds=60).reconcile(
        strategy_positions={},
        strategy_open_orders={"OLD"},
        broker=open_broker,
        now=BASE,
    )
    dq, model, signal = ready_signal()
    blocked = RiskManager(paper_smoke_config()).evaluate(
        order=order(order_id="RECON"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=open_mismatch,
        positions={},
        now=BASE,
        session_ok=True,
    )

    assert mismatch.status == "FAIL"
    assert open_mismatch.status == "FAIL"
    assert open_mismatch.reason_code == "OPEN_ORDER_MISMATCH"
    assert stale.status == "OK"
    assert stale.reason_code == "STALE_OPEN_ORDER"
    assert blocked.reason_code == "RECONCILIATION_FAILED"


def test_audit_logging_one_row_per_decision_and_exception(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    logger.write_decision(
        {
            "run_id": "r1",
            "exception": None,
            "api_key": "db-secret",
            "nested": {"password": "pw-secret"},
        }
    )
    logger.write_decision({"run_id": "r1", "exception": "simulated"})

    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert len(lines) == 2
    assert rows[1]["exception"] == "simulated"
    assert rows[0]["api_key"] == "[REDACTED]"
    assert rows[0]["nested"]["password"] == "[REDACTED]"
    assert "db-secret" not in path.read_text(encoding="utf-8")


def test_paper_control_scripts_use_configured_paper_state_only(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    kill_file = tmp_path / "runtime" / "KILL_SWITCH_ON"
    config = replace(safe_default_config(), kill_switch_file=str(kill_file))
    monkeypatch.setattr(kill_switch_on_script, "safe_default_config", lambda: config)
    monkeypatch.setattr(kill_switch_off_script, "safe_default_config", lambda: config)

    assert kill_switch_on_script.main() == 0
    assert kill_file.exists()
    assert kill_switch_off_script.main() == 0
    assert not kill_file.exists()

    dq, model, signal = ready_signal()
    risk = RiskManager(paper_smoke_config()).evaluate(
        order=order(order_id="OPEN"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
    )
    state_path = tmp_path / "paper_state.json"
    broker = PaperBroker(state_path=state_path, fill_policy="leave_open")
    assert broker.place_order(order(order_id="OPEN"), risk_decision=risk, bar=bar()).status == "OPEN"
    assert PaperBroker.load(state_path).open_orders.keys() == {"OPEN"}

    monkeypatch.setattr(paper_cancel_all_script, "STATE_PATH", state_path)
    assert paper_cancel_all_script.main() == 0
    assert PaperBroker.load(state_path).open_orders == {}

    broker = PaperBroker(state_path=state_path)
    broker.positions[position_key("ES", "ESU6")] = 2
    broker.save()
    monkeypatch.setattr(paper_flatten_all_script, "STATE_PATH", state_path)
    assert paper_flatten_all_script.main() == 0
    flattened = PaperBroker.load(state_path)
    assert flattened.positions[position_key("ES", "ESU6")] == 0
    assert flattened.fills[0].order_id == "FLATTEN-ES:ESU6"


def test_live_broker_placeholder_cannot_place_orders() -> None:
    with pytest.raises(NotImplementedError):
        LiveBroker().place_order(order())


def test_live_scaffold_has_no_real_broker_sdk_imports() -> None:
    blocked_roots = {
        "ibapi",
        "ib_insync",
        "ibkr",
        "tws",
        "cqg",
        "rithmic",
        "tradovate",
        "ninjatrader",
    }
    paths = [
        Path("live_chart_feed.py"),
        *Path("live_ops").glob("*.py"),
        Path("scripts/smoke_live_trading.py"),
        Path("scripts/kill_switch_on.py"),
        Path("scripts/kill_switch_off.py"),
        Path("scripts/paper_cancel_all.py"),
        Path("scripts/paper_flatten_all.py"),
    ]

    found: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                root = module.split(".", 1)[0].lower().replace("-", "_")
                if root in blocked_roots:
                    found.append(f"{path}:{module}")

    assert found == []


def test_live_chart_status_path_has_no_broker_order_calls() -> None:
    path = Path("live_chart_feed.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_names = {"PaperBroker", "LiveBroker", "OrderIntent"}
    found: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "live_ops.broker":
            found.append(f"{path}:{node.lineno}:import {node.module}")
        elif isinstance(node, ast.Attribute) and node.attr == "place_order":
            found.append(f"{path}:{node.lineno}:place_order")
        elif isinstance(node, ast.Name) and node.id in forbidden_names:
            found.append(f"{path}:{node.lineno}:{node.id}")

    assert found == []


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
