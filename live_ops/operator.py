"""Operator console status rendering."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TextIO

from .schemas import utc_datetime


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


def render_operator_status(state: OperatorStatusState, width: int | None = None) -> str:
    if width is None:
        width = shutil.get_terminal_size((140, 20)).columns
    if width <= 1:
        return ""
    latest = _format_latest(state.latest_bar_time)
    age = _format_age(state.latest_bar_age_seconds)
    close = "n/a" if state.last_close is None else f"{state.last_close:.2f}"
    symbol_contract = state.active_contract or state.active_symbol
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
