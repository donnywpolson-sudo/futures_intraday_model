from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from live_ops.broker import PaperBroker
from live_ops.model import ModelReadinessGate, build_signal_state
from live_ops.operator import build_order_intent_decision
from live_ops.quality import DataQualityGate
from live_ops.risk import preflight_order_intent
from live_ops.schemas import LiveBar, OrderIntentDecision, paper_smoke_config, position_key, safe_default_config

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


def intent_decision(*, config=None, test_bar: LiveBar | None = None, quantity: int = 1) -> OrderIntentDecision:
    config = config or paper_smoke_config()
    test_bar = test_bar or bar()
    dq = DataQualityGate(config).validate(test_bar, now=BASE + timedelta(seconds=5))
    model = ModelReadinessGate().evaluate(symbol=test_bar.symbol, features={"close": test_bar.close})
    signal = build_signal_state(bar=test_bar, data_quality=dq, model_status=model, now=BASE, signal="LONG")
    return build_order_intent_decision(
        config=config,
        bar=test_bar,
        signal=signal,
        quantity=quantity,
        now=BASE + timedelta(seconds=5),
    )


def test_preflight_accepts_valid_intent_without_broker_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_place_order(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("preflight must not submit to broker")

    monkeypatch.setattr(PaperBroker, "place_order", fail_place_order)
    decision = intent_decision()
    broker = PaperBroker()
    preflight = preflight_order_intent(
        config=paper_smoke_config(),
        intent_decision=decision,
        positions={},
        now=BASE + timedelta(seconds=6),
    )

    assert preflight.accepted is True
    assert preflight.preflight_status == "ACCEPTED_FOR_ROUTING"
    assert preflight.reason_code == "OK"
    assert preflight.intent is decision.order_intent
    assert preflight.symbol == "ES"
    assert preflight.side == "BUY"
    assert preflight.quantity == 1
    assert preflight.projected_position == 1
    assert broker.open_orders == {}
    assert broker.fills == []


def test_preflight_distinguishes_blocked_before_intent() -> None:
    blocked_intent = build_order_intent_decision(
        config=safe_default_config(),
        bar=bar(),
        signal=build_signal_state(
            bar=bar(),
            data_quality=DataQualityGate(paper_smoke_config()).validate(bar(), now=BASE),
            model_status=ModelReadinessGate().evaluate(symbol="ES", features={"close": 100.5}),
            now=BASE,
            signal="LONG",
        ),
        now=BASE,
    )

    preflight = preflight_order_intent(
        config=paper_smoke_config(),
        intent_decision=blocked_intent,
        positions={},
        now=BASE,
    )

    assert blocked_intent.approved is False
    assert preflight.accepted is False
    assert preflight.preflight_status == "BLOCKED_BEFORE_INTENT"
    assert preflight.reason_code == "INTENT_NOT_APPROVED"
    assert preflight.intent is None


def test_preflight_blocks_unsupported_symbol_invalid_side_and_quantity_limits() -> None:
    permissive_config = replace(paper_smoke_config(), allowed_symbols=(), allowed_contracts=(), max_order_size=2)
    unsupported_symbol_decision = intent_decision(
        config=permissive_config,
        test_bar=bar(symbol="NQ", contract="NQU6"),
    )
    valid_decision = intent_decision(config=permissive_config, quantity=2)
    bad_side_decision = replace(
        valid_decision,
        order_intent=replace(valid_decision.order_intent, side="HOLD"),
    )
    too_large_decision = intent_decision(config=permissive_config, quantity=2)

    unsupported = preflight_order_intent(
        config=paper_smoke_config(),
        intent_decision=unsupported_symbol_decision,
        positions={},
        now=BASE,
    )
    invalid_side = preflight_order_intent(
        config=paper_smoke_config(),
        intent_decision=bad_side_decision,
        positions={},
        now=BASE,
    )
    too_large = preflight_order_intent(
        config=paper_smoke_config(),
        intent_decision=too_large_decision,
        positions={},
        now=BASE,
    )

    assert unsupported.reason_code == "SYMBOL_UNSUPPORTED"
    assert unsupported.limit_name == "allowed_symbols"
    assert invalid_side.reason_code == "ORDER_SIDE_INVALID"
    assert too_large.reason_code == "ORDER_SIZE_LIMIT"
    assert too_large.limit_name == "max_order_size"


def test_preflight_blocks_projected_position_and_total_position_limits() -> None:
    config = paper_smoke_config()
    decision = intent_decision()
    symbol_limit = preflight_order_intent(
        config=config,
        intent_decision=decision,
        positions={position_key("ES", "ESU6"): 1},
        now=BASE,
    )
    total_limit = preflight_order_intent(
        config=replace(config, max_contracts_per_symbol=2, max_total_contracts=1),
        intent_decision=decision,
        positions={position_key("NQ", "NQU6"): 1},
        now=BASE,
    )

    assert symbol_limit.reason_code == "SYMBOL_POSITION_LIMIT"
    assert symbol_limit.limit_name == "max_contracts_per_symbol"
    assert symbol_limit.projected_position == 2
    assert total_limit.reason_code == "TOTAL_POSITION_LIMIT"
    assert total_limit.limit_name == "max_total_contracts"


def test_preflight_blocks_kill_switch_trading_disabled_duplicate_and_cooldown() -> None:
    decision = intent_decision()
    assert decision.order_intent is not None

    kill = preflight_order_intent(
        config=paper_smoke_config(),
        intent_decision=decision,
        positions={},
        now=BASE,
        kill_switch_on=True,
    )
    disabled = preflight_order_intent(
        config=safe_default_config(),
        intent_decision=decision,
        positions={},
        now=BASE,
    )
    duplicate = preflight_order_intent(
        config=paper_smoke_config(),
        intent_decision=decision,
        positions={},
        now=BASE,
        existing_order_ids=(decision.order_intent.order_id,),
    )
    cooldown = preflight_order_intent(
        config=replace(paper_smoke_config(), min_seconds_between_orders_per_symbol=30.0),
        intent_decision=decision,
        positions={},
        now=BASE + timedelta(seconds=10),
        last_order_time_by_symbol={"ES": BASE},
    )

    assert kill.reason_code == "KILL_SWITCH_ON"
    assert disabled.reason_code == "TRADING_DISABLED"
    assert duplicate.reason_code == "DUPLICATE_ORDER_ID"
    assert cooldown.reason_code == "ORDER_COOLDOWN"
    assert cooldown.limit_name == "min_seconds_between_orders_per_symbol"
