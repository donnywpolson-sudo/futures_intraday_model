"""Operator console status rendering."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, TextIO

from .schemas import utc_datetime


MALFORMED_OPERATOR_CONTROL = "OPERATOR_CONTROL_MALFORMED"


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


def _blocked_control(reason_code: str, state: OperatorControlState) -> OperatorControlDecision:
    reason = state.message or state.reason or reason_code
    return OperatorControlDecision(False, reason_code, reason, state)


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
