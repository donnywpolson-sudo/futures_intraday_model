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
import scripts.smoke_live_trading as smoke_live_trading_script
from live_ops.audit import AuditLogger
from live_ops.bar_builder import LiveBarBuilder, bar_contract_row, check_bar_parity
from live_ops.broker import LiveBroker, PaperBroker
from live_ops.model import ModelReadinessGate, build_signal_state
from live_ops.operator import (
    OperatorControlState,
    OperatorStatusState,
    build_order_intent_decision,
    print_operator_status,
    render_operator_status,
)
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
from live_ops.smoke import _run_decision_cycle, run_smoke, sample_bar as smoke_bar, sample_order as smoke_order

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

    assert len(line) <= 80
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


def test_operator_status_small_width_missing_fields_and_messages() -> None:
    default_line = render_operator_status(OperatorStatusState(), width=32)
    tiny_line = render_operator_status(OperatorStatusState(last_error_code="BAD\nCODE"), width=5)
    stdout = StringIO()

    print_operator_status(
        OperatorStatusState(feed_status="ERROR", last_error_code="DATA\nSTALE"),
        stdout=stdout,
        width=40,
        warning="feed\nstale",
        error="model\nunavailable",
    )
    printed = stdout.getvalue()

    assert len(default_line) <= 32
    assert "\n" not in default_line
    assert len(tiny_line) <= 5
    assert "\n" not in tiny_line
    assert printed.startswith("\r")
    assert "\nWARN: feed stale" in printed
    assert "\nERROR: model unavailable" in printed
    assert all(len(line.removeprefix("\r")) <= 40 for line in printed.splitlines())


def test_operator_control_state_file_source_blocks_fail_closed(tmp_path) -> None:
    from live_ops.operator import evaluate_operator_controls, load_operator_control_state

    missing = load_operator_control_state(tmp_path / "missing.json", now=BASE)
    assert evaluate_operator_controls(missing).allowed is True

    valid_path = tmp_path / "operator_control.json"
    valid_path.write_text(
        json.dumps(
            {
                "trading_enabled": True,
                "kill_switch_active": True,
                "pause_new_entries": False,
                "reason": "manual stop",
                "message": "manual stop requested",
                "updated_at": "2026-06-22T14:30:00Z",
            }
        ),
        encoding="utf-8",
    )
    valid = load_operator_control_state(valid_path, now=BASE)
    valid_decision = evaluate_operator_controls(valid)
    assert valid.kill_switch_active is True
    assert valid.updated_at == BASE
    assert valid_decision.allowed is False
    assert valid_decision.reason_code == "OPERATOR_KILL_SWITCH"

    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text("{not-json", encoding="utf-8")
    malformed = load_operator_control_state(malformed_path, now=BASE)
    malformed_decision = evaluate_operator_controls(malformed)
    assert malformed.trading_enabled is False
    assert malformed_decision.allowed is False
    assert malformed_decision.reason_code == "OPERATOR_CONTROL_MALFORMED"


def test_order_intent_gate_creates_valid_scaffold_intent() -> None:
    test_bar = bar()
    _, _, signal = ready_signal(test_bar)
    decision = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=signal,
        quantity=1,
        now=BASE + timedelta(seconds=5),
    )

    assert decision.approved is True
    assert decision.reason_code == "OK"
    assert decision.validation_status == "APPROVED"
    assert decision.mode == "paper"
    assert decision.symbol == "ES"
    assert decision.side == "BUY"
    assert decision.quantity == 1
    assert decision.source_signal == "LONG"
    assert decision.bar_timestamp == BASE
    assert decision.order_intent is not None
    assert decision.order_intent.symbol == "ES"
    assert decision.order_intent.contract == "ESU6"
    assert decision.order_intent.side == "BUY"
    assert decision.order_intent.quantity == 1
    assert decision.order_intent.limit_price == 100.5
    assert decision.order_intent.reason == "signal:LONG"


def test_order_intent_gate_blocks_controls_config_and_preserves_broker_state() -> None:
    test_bar = bar()
    _, _, signal = ready_signal(test_bar)
    broker = PaperBroker()

    kill = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=signal,
        now=BASE,
        kill_switch_on=True,
    )
    disabled = build_order_intent_decision(
        config=safe_default_config(),
        bar=test_bar,
        signal=signal,
        now=BASE,
    )
    paused = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=signal,
        now=BASE,
        operator_control=OperatorControlState(pause_new_entries=True, message="operator pause"),
    )

    assert kill.reason_code == "KILL_SWITCH_ON"
    assert disabled.reason_code == "TRADING_DISABLED"
    assert paused.reason_code == "OPERATOR_PAUSE_NEW_ENTRIES"
    assert all(item.order_intent is None and item.validation_status == "BLOCKED" for item in (kill, disabled, paused))
    assert broker.open_orders == {}
    assert broker.fills == []


def test_order_intent_gate_blocks_bad_prediction_quantity_symbol_and_stale_bar() -> None:
    test_bar = bar()
    _, _, signal = ready_signal(test_bar)

    malformed = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=replace(signal, score=float("nan")),
        now=BASE,
    )
    zero_quantity = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=signal,
        quantity=0,
        now=BASE,
    )
    too_large = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=signal,
        quantity=2,
        now=BASE,
    )
    unsupported = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=bar(symbol="NQ", contract="NQU6"),
        signal=replace(signal, symbol="NQ", contract="NQU6"),
        now=BASE,
    )
    stale = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=signal,
        now=BASE + timedelta(seconds=120),
    )

    assert malformed.reason_code == "PREDICTION_MALFORMED"
    assert zero_quantity.reason_code == "ORDER_QUANTITY_INVALID"
    assert too_large.reason_code == "ORDER_SIZE_LIMIT"
    assert unsupported.reason_code == "SYMBOL_UNSUPPORTED"
    assert stale.reason_code == "BAR_STALE"
    assert all(item.order_intent is None and item.reason for item in (malformed, zero_quantity, too_large, unsupported, stale))


def test_order_intent_gate_blocks_no_action_flat_and_below_threshold_without_broker_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_place_order(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("order intent gate must not submit to broker")

    monkeypatch.setattr(PaperBroker, "place_order", fail_place_order)
    test_bar = bar()
    dq, model, _ = ready_signal(test_bar)
    no_signal = build_signal_state(bar=test_bar, data_quality=dq, model_status=model, now=BASE, signal=None)
    flat_signal = build_signal_state(bar=test_bar, data_quality=dq, model_status=model, now=BASE, signal="FLAT")
    low_confidence = build_signal_state(
        bar=test_bar,
        data_quality=dq,
        model_status=model,
        now=BASE,
        signal="LONG",
        confidence=0.2,
    )

    no_action = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=no_signal,
        now=BASE,
    )
    flat = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=flat_signal,
        now=BASE,
    )
    below_threshold = build_order_intent_decision(
        config=paper_smoke_config(),
        bar=test_bar,
        signal=low_confidence,
        now=BASE,
        min_confidence=0.5,
    )

    assert no_action.reason_code == "NO_ACTION_SIGNAL"
    assert flat.reason_code == "NO_ACTION_SIGNAL"
    assert below_threshold.reason_code == "SIGNAL_BELOW_THRESHOLD"
    assert all(item.order_intent is None and item.validation_status == "BLOCKED" for item in (no_action, flat, below_threshold))


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
        LiveRecord("ES", "ESU6", BASE + timedelta(minutes=1, seconds=20), 100.0, 4),
        LiveRecord("ES", "ESU6", BASE + timedelta(minutes=2), 102.0, 1),
    ]
    emitted = []
    for record in records:
        emitted.extend(builder.update(record))

    assert emitted == [
        LiveBar("ES", "ESU6", BASE, "1m", 100.0, 101.0, 100.0, 101.0, 5, True, "synthetic-l1"),
        LiveBar("ES", "ESU6", BASE + timedelta(minutes=1), "1m", 99.0, 100.0, 99.0, 100.0, 5, True, "synthetic-l1"),
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
    result = check_bar_parity([row], [row])

    assert result.passed
    assert result.reason_code == "OK"
    assert result.missing_columns == ()
    assert result.extra_columns == ()
    assert result.dtype_mismatches == {}
    assert result.timezone_status == "UTC"
    assert result.partial_bar_status == "FINAL_ONLY"


def test_bar_parity_fails_closed_for_schema_order_dtype_and_contract_window() -> None:
    row = bar_contract_row(bar())
    missing_live = dict(row)
    missing_live.pop("volume")
    extra_live = {**row, "unexpected": 1}
    misordered_live = {
        "symbol": row["symbol"],
        "timestamp_utc": row["timestamp_utc"],
        "contract": row["contract"],
        "timeframe": row["timeframe"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "volume": row["volume"],
        "bar_is_final": row["bar_is_final"],
        "source_schema": row["source_schema"],
    }
    dtype_live = {**row, "volume": float(row["volume"])}
    mixed_contract_live = [
        row,
        bar_contract_row(bar(timestamp_utc=BASE + timedelta(minutes=1), contract="ESZ6")),
    ]

    missing_result = check_bar_parity([row], [missing_live])
    extra_result = check_bar_parity([row], [extra_live])
    order_result = check_bar_parity([row], [misordered_live])
    dtype_result = check_bar_parity([row], [dtype_live])
    contract_result = check_bar_parity([row], mixed_contract_live)

    assert missing_result.reason_code == "FIELD_MISMATCH"
    assert missing_result.missing_columns == ("volume",)
    assert extra_result.reason_code == "FIELD_MISMATCH"
    assert extra_result.extra_columns == ("unexpected",)
    assert order_result.reason_code == "COLUMN_ORDER_MISMATCH"
    assert dtype_result.reason_code == "DTYPE_MISMATCH"
    assert dtype_result.dtype_mismatches == {"volume": ("int", "float")}
    assert contract_result.reason_code == "CONTRACT_WINDOW_MISMATCH"


def test_bar_parity_catches_timestamp_and_partial_bar_status() -> None:
    row = bar_contract_row(bar())
    naive_live = {**row, "timestamp_utc": datetime(2026, 6, 22, 14, 30)}
    non_utc_live = {**row, "timestamp_utc": BASE.astimezone(timezone(timedelta(hours=-5)))}
    partial_live = bar_contract_row(bar(bar_is_final=False))

    naive_result = check_bar_parity([row], [naive_live])
    non_utc_result = check_bar_parity([row], [non_utc_live])
    partial_result = check_bar_parity([row], [partial_live])

    assert naive_result.reason_code == "TIMESTAMP_NOT_TZ_AWARE"
    assert naive_result.timezone_status == "NOT_TZ_AWARE"
    assert non_utc_result.reason_code == "TIMESTAMP_NOT_UTC"
    assert non_utc_result.timezone_status == "NOT_UTC"
    assert partial_result.reason_code == "PARTIAL_BAR_NOT_SCORABLE"
    assert partial_result.partial_bar_status == "HAS_PARTIAL"


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


def test_data_quality_runtime_state_blocks_disconnect_heartbeat_and_backfill() -> None:
    config = paper_smoke_config()

    disconnected = DataQualityGate(config).validate(bar(), now=BASE, feed_connected=False)
    no_heartbeat = DataQualityGate(config).validate(
        bar(),
        now=BASE,
        heartbeat_required=True,
        heartbeat_timestamp_utc=None,
    )
    backfill = DataQualityGate(config).validate(bar(), now=BASE, reconnect_backfill_required=True)
    root_mismatch = DataQualityGate(config).validate(bar(), now=BASE, active_symbol="NQ")

    assert disconnected.reason_code == "FEED_DISCONNECTED"
    assert no_heartbeat.reason_code == "NO_HEARTBEAT"
    assert backfill.reason_code == "RECONNECT_BACKFILL_REQUIRED"
    assert root_mismatch.reason_code == "ROOT_SYMBOL_MISMATCH"


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

    assert unavailable.status == "UNAVAILABLE"
    assert unavailable.reason_code == "MODEL_UNAVAILABLE"
    assert missing.status == "BLOCKED"
    assert missing.reason_code == "FEATURES_MISSING"
    assert missing.missing_features == ("volume",)
    assert missing.ordered_features == ("close",)
    assert build_signal_state(bar=test_bar, data_quality=dq, model_status=unavailable, signal="LONG").signal == "NO_SIGNAL"
    assert build_signal_state(bar=test_bar, data_quality=dq, model_status=missing, signal="LONG").signal == "NO_SIGNAL"


def test_model_readiness_blocks_order_nonfinite_warmup_symbol_and_versions(tmp_path) -> None:
    missing_model = ModelReadinessGate(model_path=tmp_path / "missing.pkl").evaluate(
        symbol="ES",
        features={"close": 100.5},
    )
    gate = ModelReadinessGate(
        expected_features=("close", "volume"),
        supported_symbols=("ES",),
        warmup_bars_required=3,
        model_version="model-v1",
        config_version="config-v1",
        feature_version="feature-v1",
    )

    ready = gate.evaluate(symbol="ES", features={"close": 100.5, "volume": 10}, warmup_bars_available=3)
    order_mismatch = gate.evaluate(symbol="ES", features={"volume": 10, "close": 100.5}, warmup_bars_available=3)
    warmup = gate.evaluate(symbol="ES", features={"close": 100.5, "volume": 10}, warmup_bars_available=2)
    unsupported = gate.evaluate(symbol="NQ", features={"close": 100.5, "volume": 10}, warmup_bars_available=3)

    assert missing_model.status == "UNAVAILABLE"
    assert missing_model.reason_code == "MODEL_FILE_MISSING"
    assert ready.status == "READY"
    assert ready.ordered_features == ("close", "volume")
    assert ready.model_version == "model-v1"
    assert ready.config_version == "config-v1"
    assert ready.feature_version == "feature-v1"
    assert order_mismatch.status == "BLOCKED"
    assert order_mismatch.reason_code == "FEATURE_ORDER_MISMATCH"
    assert order_mismatch.ordered_features == ("volume", "close")
    for value in (float("nan"), float("inf")):
        not_finite = gate.evaluate(symbol="ES", features={"close": value, "volume": 10}, warmup_bars_available=3)
        assert not_finite.status == "BLOCKED"
        assert not_finite.reason_code == "FEATURE_NOT_FINITE"
    assert warmup.status == "UNAVAILABLE"
    assert warmup.reason_code == "WARMUP_INCOMPLETE"
    assert unsupported.status == "BLOCKED"
    assert unsupported.reason_code == "SYMBOL_UNSUPPORTED"


def test_partial_bar_signal_is_non_tradable() -> None:
    test_bar = bar(bar_is_final=False)
    dq = DataQualityGate(paper_smoke_config()).validate(test_bar, now=BASE)
    model = ModelReadinessGate().evaluate(symbol="ES", features={"close": 100.5})

    signal = build_signal_state(bar=test_bar, data_quality=dq, model_status=model, signal="LONG")
    preview = build_signal_state(
        bar=test_bar,
        data_quality=dq,
        model_status=model,
        signal="LONG",
        allow_partial_preview=True,
    )

    assert signal.signal == "NO_SIGNAL"
    assert signal.tradable is False
    assert preview.signal == "LONG"
    assert preview.tradable is False
    assert preview.skip_reason == "NO_TRADABLE_SIGNAL"


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


def test_risk_blocks_runtime_root_contract_and_monitor_only() -> None:
    dq, model, signal = ready_signal()
    config = paper_smoke_config()

    root = RiskManager(config).evaluate(
        order=order(order_id="ROOT"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
        active_symbol="NQ",
    )
    contract = RiskManager(config).evaluate(
        order=order(order_id="CONTRACT"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=True,
        active_contract="ESZ6",
    )
    monitor = RiskManager(config).evaluate(
        order=order(order_id="MONITOR"),
        signal=replace(signal, tradable=False, skip_reason="MONITOR_ONLY"),
        data_quality=dq,
        model_status=model,
        reconciliation=ReconciliationResult("OK", "OK", {}),
        positions={},
        now=BASE,
        session_ok=False,
        monitor_only=True,
    )

    assert root.reason_code == "ROOT_SYMBOL_MISMATCH"
    assert contract.reason_code == "CONTRACT_MISMATCH"
    assert monitor.reason_code == "MONITOR_ONLY"


def test_session_guard_missing_or_closed_session_is_false() -> None:
    guard = SessionGuard.from_strings({"ES": ("15:00", "16:00", "UTC")})

    assert guard.is_session_open(BASE, "ES") is False
    assert guard.is_session_open(BASE, "NQ") is False
    assert guard.check(BASE, "ES").reason_code == "SESSION_CLOSED"
    assert guard.check(BASE, "NQ").reason_code == "SESSION_MISSING"
    assert guard.check(BASE + timedelta(hours=1), "ES").reason_code == "SESSION_OPEN"


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
    assert dq_session.reason_code == "SESSION_MISSING"


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
    position_blocked = RiskManager(paper_smoke_config()).evaluate(
        order=order(order_id="RECON-POSITION"),
        signal=signal,
        data_quality=dq,
        model_status=model,
        reconciliation=mismatch,
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
    assert position_blocked.reason_code == "RECONCILIATION_FAILED"


def test_audit_logging_one_row_per_decision_and_exception(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    logger.write_decision(
        {
            "run_id": "r1",
            "exception": None,
            "api_key": "db-secret",
            "nested": {"password": "pw-secret", "items": [{"account_number": "acct-secret"}]},
        }
    )
    AuditLogger(path).write_decision({"run_id": "r1", "exception": "simulated"})

    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert len(lines) == 2
    assert rows[1]["exception"] == "simulated"
    assert rows[0]["api_key"] == "[REDACTED]"
    assert rows[0]["nested"]["password"] == "[REDACTED]"
    assert rows[0]["nested"]["items"][0]["account_number"] == "[REDACTED]"
    assert "db-secret" not in path.read_text(encoding="utf-8")
    assert "acct-secret" not in path.read_text(encoding="utf-8")


def test_decision_cycle_feature_broker_and_audit_failures_fail_closed(tmp_path) -> None:
    class FailingPreflightAuditLogger(AuditLogger):
        def ensure_writable(self) -> None:
            raise OSError("simulated audit write failure")

    class FailingAppendAuditLogger(AuditLogger):
        def write_decision(self, event: object) -> None:
            raise OSError("simulated audit append failure")

    config = paper_smoke_config()
    feature = _run_decision_cycle(
        name="feature_exception_test",
        logger=AuditLogger(tmp_path / "feature.jsonl"),
        cycle_number=1,
        config=config,
        bar=smoke_bar(),
        order=smoke_order(order_id="ORD-FEATURE-TEST"),
        raise_feature_exception=True,
    )
    broker = _run_decision_cycle(
        name="broker_exception_test",
        logger=AuditLogger(tmp_path / "broker.jsonl"),
        cycle_number=2,
        config=config,
        bar=smoke_bar(),
        order=smoke_order(order_id="ORD-BROKER-TEST"),
        raise_broker_exception=True,
    )
    audit = _run_decision_cycle(
        name="audit_exception_test",
        logger=FailingPreflightAuditLogger(tmp_path / "audit.jsonl"),
        cycle_number=3,
        config=config,
        bar=smoke_bar(),
        order=smoke_order(order_id="ORD-AUDIT-TEST"),
    )
    append_broker = PaperBroker()
    append_audit = _run_decision_cycle(
        name="audit_append_exception_test",
        logger=FailingAppendAuditLogger(tmp_path / "audit-append.jsonl"),
        cycle_number=4,
        config=config,
        bar=smoke_bar(),
        broker=append_broker,
        order=smoke_order(order_id="ORD-AUDIT-APPEND-TEST"),
    )

    assert feature.signal.signal == "NO_SIGNAL"
    assert feature.risk.reason_code == "EXCEPTION"
    assert feature.broker_response is None
    assert "feature" in str(feature.exception)
    assert broker.risk.reason_code == "EXCEPTION"
    assert broker.broker_response is None
    assert "broker" in str(broker.exception)
    assert audit.risk.reason_code == "EXCEPTION"
    assert audit.broker_response is None
    assert "audit log" in str(audit.exception)
    assert append_audit.risk.reason_code == "EXCEPTION"
    assert append_audit.broker_response is None
    assert "audit log append" in str(append_audit.exception)
    assert append_broker.positions == {}
    assert append_broker.open_orders == {}
    assert append_broker.fills == []


def test_paper_control_scripts_use_configured_paper_state_only(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    kill_file = tmp_path / "runtime" / "KILL_SWITCH_ON"
    config = replace(safe_default_config(), kill_switch_file=str(kill_file))
    monkeypatch.setattr(kill_switch_on_script, "safe_default_config", lambda: config)
    monkeypatch.setattr(kill_switch_off_script, "safe_default_config", lambda: config)

    assert kill_switch_on_script.main() == 0
    assert kill_switch_on_script.main() == 0
    assert kill_file.exists()
    assert kill_switch_off_script.main() == 0
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
    assert paper_cancel_all_script.main() == 0
    assert PaperBroker.load(state_path).open_orders == {}

    broker = PaperBroker(state_path=state_path)
    broker.positions[position_key("ES", "ESU6")] = 2
    broker.save()
    monkeypatch.setattr(paper_flatten_all_script, "STATE_PATH", state_path)
    assert paper_flatten_all_script.main() == 0
    assert paper_flatten_all_script.main() == 0
    flattened = PaperBroker.load(state_path)
    assert flattened.positions[position_key("ES", "ESU6")] == 0
    assert flattened.fills[0].order_id == "FLATTEN-ES:ESU6"
    assert len(flattened.fills) == 1


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
    text = stdout.getvalue()
    rows = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    by_scenario = {row["scenario"]: row for row in rows}

    assert "PASS live trading smoke" in text
    assert f"decision_cycles={len(rows)}" in text
    assert f"audit_rows={len(rows)}" in text
    assert all("exception" in row for row in rows)
    assert all("operator_status" in row for row in rows)
    assert all(len(row["operator_status_line"]) == 119 for row in rows)
    assert "operator_status_render" not in by_scenario
    assert by_scenario["missing_model_output"]["signal_state"]["signal"] == "NO_SIGNAL"
    assert by_scenario["missing_model_output"]["operator_status"]["model_status"] == "UNAVAILABLE"
    assert by_scenario["missing_features"]["signal_state"]["signal"] == "NO_SIGNAL"
    assert by_scenario["trading_disabled"]["risk_decision"]["reason_code"] == "TRADING_DISABLED"
    assert by_scenario["trading_disabled"]["operator_status"]["risk_status"] == "BLOCKED"
    assert by_scenario["paper_fill"]["broker_response"]["status"] == "FILLED"
    assert by_scenario["paper_fill"]["operator_status"]["signal"] == "LONG"
    assert by_scenario["paper_fill"]["operator_status"]["trading_mode"] == "PAPER"
    assert by_scenario["paper_fill"]["operator_status"]["risk_status"] == "OK"
    assert by_scenario["paper_fill"]["operator_status"]["paper_position"] == "ES:ESU6=1"
    assert by_scenario["bad_ohlc"]["data_quality_result"]["reason_code"] == "BAD_OHLC"
    assert by_scenario["stale_bar"]["data_quality_result"]["reason_code"] == "DATA_STALE"
    assert by_scenario["stale_heartbeat"]["data_quality_result"]["reason_code"] == "HEARTBEAT_STALE"
    assert by_scenario["feed_disconnected"]["data_quality_result"]["reason_code"] == "FEED_DISCONNECTED"
    assert by_scenario["no_heartbeat"]["data_quality_result"]["reason_code"] == "NO_HEARTBEAT"
    assert by_scenario["duplicate_timestamp"]["data_quality_result"]["reason_code"] == "DUPLICATE_TIMESTAMP"
    assert by_scenario["kill_switch"]["risk_decision"]["reason_code"] == "KILL_SWITCH_ON"
    assert by_scenario["operator_kill_switch"]["risk_decision"]["reason_code"] == "OPERATOR_KILL_SWITCH"
    assert by_scenario["operator_kill_switch"]["operator_control_decision"]["reason_code"] == "OPERATOR_KILL_SWITCH"
    assert by_scenario["operator_kill_switch"]["operator_status"]["kill_switch"] == "ON"
    assert by_scenario["operator_kill_switch"]["broker_response"] is None
    assert by_scenario["operator_trading_disabled"]["risk_decision"]["reason_code"] == "OPERATOR_TRADING_DISABLED"
    assert by_scenario["operator_trading_disabled"]["broker_response"] is None
    assert by_scenario["operator_pause_new_entries"]["risk_decision"]["reason_code"] == "OPERATOR_PAUSE_NEW_ENTRIES"
    assert by_scenario["operator_pause_new_entries"]["broker_response"] is None
    assert by_scenario["oversized_order"]["risk_decision"]["reason_code"] == "ORDER_SIZE_LIMIT"
    assert by_scenario["duplicate_order_id"]["broker_response"]["reason_code"] == "DUPLICATE_ORDER_ID"
    assert by_scenario["reconciliation_mismatch"]["risk_decision"]["reason_code"] == "RECONCILIATION_FAILED"
    assert by_scenario["reconnect_gap"]["data_quality_result"]["reason_code"] == "TIMESTAMP_GAP"
    assert by_scenario["reconnect_backfill_required"]["data_quality_result"]["reason_code"] == "RECONNECT_BACKFILL_REQUIRED"
    assert by_scenario["reconnect_pending"]["risk_decision"]["reason_code"] == "RECONNECT_RECONCILIATION_PENDING"
    assert by_scenario["reconnect_cleared"]["risk_decision"]["approved"] is True
    assert by_scenario["contract_mismatch"]["data_quality_result"]["reason_code"] == "CONTRACT_MISMATCH"
    assert by_scenario["root_symbol_mismatch"]["data_quality_result"]["reason_code"] == "ROOT_SYMBOL_MISMATCH"
    assert by_scenario["outside_session"]["risk_decision"]["reason_code"] == "OUTSIDE_SESSION"
    assert by_scenario["missing_session_config"]["risk_decision"]["reason_code"] == "OUTSIDE_SESSION"
    assert by_scenario["known_closed_period"]["data_quality_result"]["reason_code"] == "SESSION_CLOSED"
    assert by_scenario["monitor_only_outside_session"]["risk_decision"]["reason_code"] == "MONITOR_ONLY"
    assert by_scenario["monitor_only_outside_session"]["signal_state"]["tradable"] is False
    assert by_scenario["unsafe_live_mode"]["risk_decision"]["reason_code"] == "LIVE_BROKER_BLOCKED"
    assert by_scenario["unsafe_live_mode"]["operator_status"]["trading_mode"] == "LIVE_BLOCKED"
    assert by_scenario["forced_exception"]["exception"] is not None
    assert by_scenario["forced_exception"]["risk_decision"]["reason_code"] == "EXCEPTION"
    assert by_scenario["forced_exception"]["broker_response"] is None
    assert by_scenario["feature_exception"]["exception"] is not None
    assert by_scenario["feature_exception"]["broker_response"] is None
    assert by_scenario["broker_exception"]["exception"] is not None
    assert by_scenario["broker_exception"]["broker_response"] is None


def test_smoke_live_trading_cli_returns_zero_and_forced_failure_nonzero(tmp_path) -> None:
    passing_dir = tmp_path / "passing"
    forced_dir = tmp_path / "forced"

    assert smoke_live_trading_script.main(["--audit-dir", str(passing_dir)]) == 0
    assert smoke_live_trading_script.main(["--audit-dir", str(forced_dir), "--force-failure"]) == 1
    assert (passing_dir / "audit.jsonl").exists()
    assert (forced_dir / "audit.jsonl").exists()
