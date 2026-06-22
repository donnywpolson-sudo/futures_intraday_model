"""Operator console status rendering."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, TextIO

from .schemas import LiveBar, LiveTradingConfig, OrderIntent, OrderIntentDecision, SignalState, utc_datetime


MALFORMED_OPERATOR_CONTROL = "OPERATOR_CONTROL_MALFORMED"
DEFAULT_ORDER_STRATEGY_ID = "live-ops-scaffold"


@dataclass(frozen=True)
class OperatorControlState:
    trading_enabled: bool = True
    kill_switch_active: bool = False
    pause_new_entries: bool = False
    reason: str = "OK"
    message: str = ""
    updated_at: datetime | None = None
    source: str = "default"


@dataclass(frozen=True)
class OperatorControlDecision:
    allowed: bool
    reason_code: str
    reason: str
    state: OperatorControlState


@dataclass(frozen=True)
class OperatorStatusState:
    feed_status: str = "CLOSED"
    active_symbol: str = "n/a"
    active_contract: str = "n/a"
    timeframe: str = "1m"
    records_count: int = 0
    latest_bar_time: datetime | None = None
    latest_bar_age_seconds: float | None = None
    last_close: float | None = None
    model_status: str = "OFF"
    signal: str = "NO_SIGNAL"
    trading_mode: str = "DISABLED"
    kill_switch: str = "OFF"
    risk_status: str = "UNKNOWN"
    reconciliation_status: str = "UNKNOWN"
    paper_position: str | None = None
    last_error_code: str | None = None


def load_operator_control_state(path: str | Path | None, *, now: datetime | None = None) -> OperatorControlState:
    if path is None:
        return OperatorControlState()
    control_path = Path(path)
    if not control_path.exists():
        return OperatorControlState(source=str(control_path))
    try:
        payload = json.loads(control_path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("operator control payload must be a JSON object")
        return OperatorControlState(
            trading_enabled=_read_bool(payload, "trading_enabled", True),
            kill_switch_active=_read_bool(payload, "kill_switch_active", False),
            pause_new_entries=_read_bool(payload, "pause_new_entries", False),
            reason=str(payload.get("reason") or "OK"),
            message=str(payload.get("message") or ""),
            updated_at=_read_updated_at(payload.get("updated_at")),
            source=str(control_path),
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        updated_at = utc_datetime(now) if now is not None else None
        return OperatorControlState(
            trading_enabled=False,
            reason=MALFORMED_OPERATOR_CONTROL,
            message=f"malformed operator control file: {exc}",
            updated_at=updated_at,
            source=str(control_path),
        )


def evaluate_operator_controls(
    state: OperatorControlState,
    *,
    is_new_entry: bool = True,
) -> OperatorControlDecision:
    if state.reason == MALFORMED_OPERATOR_CONTROL:
        return _blocked_control(MALFORMED_OPERATOR_CONTROL, state)
    if state.kill_switch_active:
        return _blocked_control("OPERATOR_KILL_SWITCH", state)
    if not state.trading_enabled:
        return _blocked_control("OPERATOR_TRADING_DISABLED", state)
    if is_new_entry and state.pause_new_entries:
        return _blocked_control("OPERATOR_PAUSE_NEW_ENTRIES", state)
    return OperatorControlDecision(True, "OK", state.message or state.reason, state)


def build_order_intent_decision(
    *,
    config: LiveTradingConfig,
    bar: LiveBar,
    signal: SignalState,
    quantity: object = 1,
    operator_control: OperatorControlState | None = None,
    now: datetime | None = None,
    strategy_id: str = DEFAULT_ORDER_STRATEGY_ID,
    order_id: str | None = None,
    order_type: str = "LIMIT",
    limit_price: float | None = None,
    time_in_force: str = "DAY",
    kill_switch_on: bool = False,
    min_confidence: float | None = None,
) -> OrderIntentDecision:
    created_timestamp = utc_datetime(now or datetime.now(timezone.utc))
    mode = config.mode
    symbol = signal.symbol or bar.symbol
    source_signal = str(signal.signal).upper() if signal.signal is not None else None

    if kill_switch_on:
        return _blocked_order_intent(
            "KILL_SWITCH_ON",
            "kill switch blocks order intent creation",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )

    control_state = operator_control or OperatorControlState()
    control_decision = evaluate_operator_controls(control_state, is_new_entry=True)
    if not control_decision.allowed:
        return _blocked_order_intent(
            control_decision.reason_code,
            control_decision.reason,
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
            details={"operator_control": control_state},
        )

    if not config.allow_trading or config.mode == "disabled":
        return _blocked_order_intent(
            "TRADING_DISABLED",
            "trading is disabled by config",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    if config.allow_live_broker or config.mode == "live":
        return _blocked_order_intent(
            "LIVE_BROKER_BLOCKED",
            "live broker order intents are blocked in the scaffold",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )

    if not symbol:
        return _blocked_order_intent(
            "SYMBOL_MISSING",
            "symbol is required before order intent creation",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    if config.allowed_symbols and symbol not in config.allowed_symbols:
        return _blocked_order_intent(
            "SYMBOL_UNSUPPORTED",
            "symbol is not supported by config",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    if not signal.contract:
        return _blocked_order_intent(
            "CONTRACT_MISSING",
            "contract is required before order intent creation",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    if config.allowed_contracts and signal.contract not in config.allowed_contracts:
        return _blocked_order_intent(
            "CONTRACT_UNSUPPORTED",
            "contract is not supported by config",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )

    payload_error = _prediction_payload_error(signal)
    if payload_error is not None:
        return _blocked_order_intent(
            "PREDICTION_MALFORMED",
            payload_error,
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    if source_signal in {"FLAT", "NO_SIGNAL"}:
        return _blocked_order_intent(
            "NO_ACTION_SIGNAL",
            "model signal produced no order action",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    if source_signal not in {"LONG", "SHORT"} or not signal.tradable:
        return _blocked_order_intent(
            "SIGNAL_NOT_TRADABLE",
            signal.skip_reason or "signal is not tradable",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    if min_confidence is not None and (signal.confidence is None or signal.confidence < min_confidence):
        return _blocked_order_intent(
            "SIGNAL_BELOW_THRESHOLD",
            "signal confidence is below the scaffold threshold",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )

    bar_timestamp = utc_datetime(signal.bar_timestamp_utc)
    age_seconds = (created_timestamp - bar_timestamp).total_seconds()
    if config.stale_bar_seconds >= 0 and age_seconds > config.stale_bar_seconds:
        return _blocked_order_intent(
            "BAR_STALE",
            "bar timestamp is stale before order intent creation",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
            details={"bar_age_seconds": age_seconds, "stale_bar_seconds": config.stale_bar_seconds},
        )

    quantity_error = _quantity_error(quantity, config.max_order_size)
    if quantity_error is not None:
        reason_code, reason = quantity_error
        return _blocked_order_intent(
            reason_code,
            reason,
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    quantity_int = int(quantity)
    side = "BUY" if source_signal == "LONG" else "SELL"
    resolved_limit_price = bar.close if limit_price is None else limit_price
    if not isinstance(resolved_limit_price, (int, float)) or isinstance(resolved_limit_price, bool) or not isfinite(float(resolved_limit_price)):
        return _blocked_order_intent(
            "ORDER_PRICE_INVALID",
            "limit price must be finite for scaffold order intent creation",
            mode=mode,
            signal=signal,
            source_signal=source_signal,
            created_timestamp=created_timestamp,
        )
    signal_id = f"{symbol}-{bar_timestamp.strftime('%Y%m%dT%H%M%SZ')}-{source_signal}"
    resolved_order_id = order_id or f"{strategy_id}-{signal_id}"
    intent = OrderIntent(
        order_id=resolved_order_id,
        strategy_id=strategy_id,
        symbol=symbol,
        contract=signal.contract,
        side=side,
        quantity=quantity_int,
        order_type=order_type,
        limit_price=float(resolved_limit_price),
        stop_price=None,
        time_in_force=time_in_force,
        bar_timestamp=bar_timestamp,
        created_timestamp=created_timestamp,
        reason=f"signal:{source_signal}",
        signal_id=signal_id,
    )
    return OrderIntentDecision(
        True,
        "OK",
        "order intent created by live-ops scaffold gate",
        intent,
        mode,
        symbol,
        side,
        quantity_int,
        source_signal,
        bar_timestamp,
        created_timestamp,
        "APPROVED",
        {"operator_control": control_state},
    )


def _blocked_control(reason_code: str, state: OperatorControlState) -> OperatorControlDecision:
    reason = state.message or state.reason or reason_code
    return OperatorControlDecision(False, reason_code, reason, state)


def _blocked_order_intent(
    reason_code: str,
    reason: str,
    *,
    mode: str,
    signal: SignalState,
    source_signal: str | None,
    created_timestamp: datetime,
    details: dict[str, Any] | None = None,
) -> OrderIntentDecision:
    return OrderIntentDecision(
        False,
        reason_code,
        reason,
        None,
        mode,
        signal.symbol,
        None,
        None,
        source_signal,
        utc_datetime(signal.bar_timestamp_utc),
        created_timestamp,
        "BLOCKED",
        details or {},
    )


def _prediction_payload_error(signal: SignalState) -> str | None:
    if str(signal.signal).upper() not in {"LONG", "SHORT", "FLAT", "NO_SIGNAL"}:
        return "signal must be LONG, SHORT, FLAT, or NO_SIGNAL"
    for name, value in (
        ("prediction", signal.prediction),
        ("score", signal.score),
        ("confidence", signal.confidence),
    ):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
            return f"{name} must be a finite number"
    return None


def _quantity_error(quantity: object, max_order_size: int) -> tuple[str, str] | None:
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        return "ORDER_QUANTITY_INVALID", "quantity must be an integer"
    if quantity <= 0:
        return "ORDER_QUANTITY_INVALID", "quantity must be positive"
    if max_order_size <= 0 or quantity > max_order_size:
        return "ORDER_SIZE_LIMIT", "quantity exceeds configured scaffold max"
    return None


def _read_bool(payload: Mapping[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    raise ValueError(f"{key} must be a boolean")


def _read_updated_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("updated_at must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return utc_datetime(parsed)


def render_operator_status(state: OperatorStatusState, width: int | None = None) -> str:
    if width is None:
        width = shutil.get_terminal_size((140, 20)).columns
    if width <= 1:
        return ""
    latest = _format_latest(state.latest_bar_time)
    age = _format_age(state.latest_bar_age_seconds)
    close = "n/a" if state.last_close is None else f"{state.last_close:.2f}"
    symbol_contract = _format_symbol_contract(state.active_symbol, state.active_contract)
    parts = [
        state.feed_status,
        f"{symbol_contract} {state.timeframe}",
        f"rows={state.records_count}",
        f"latest={latest}",
        f"age={age}",
        f"close={close}",
        f"model={state.model_status}",
        f"sig={state.signal}",
        f"mode={state.trading_mode}",
        f"kill={state.kill_switch}",
        f"risk={state.risk_status}",
        f"recon={state.reconciliation_status}",
    ]
    if state.paper_position:
        parts.append(f"pos={state.paper_position}")
    if state.last_error_code:
        parts.append(f"err={state.last_error_code}")
    line = " | ".join(parts)
    max_len = width - 1
    return line[:max_len].ljust(max_len)


def print_operator_status(state: OperatorStatusState, *, stdout: TextIO, width: int | None = None) -> None:
    stdout.write("\r" + render_operator_status(state, width=width))
    stdout.flush()


def _format_latest(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return utc_datetime(value).strftime("%Y-%m-%d %H:%MZ")


def _format_symbol_contract(symbol: str, contract: str) -> str:
    if symbol and symbol != "n/a" and contract and contract != "n/a" and symbol != contract:
        return f"{symbol}/{contract}"
    return contract or symbol


def _format_age(value: float | None) -> str:
    if value is None:
        return "n/a"
    seconds = max(0, int(value))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h"
