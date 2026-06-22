"""Fail-closed risk controls for paper-only order intents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as day_time, timezone
from zoneinfo import ZoneInfo

from .schemas import (
    DataQualityResult,
    LiveTradingConfig,
    ModelReadinessResult,
    OrderIntent,
    ReconciliationResult,
    RiskDecision,
    SignalState,
    position_key,
    utc_datetime,
)


@dataclass(frozen=True)
class SessionWindow:
    open_time: day_time
    close_time: day_time
    timezone_name: str = "UTC"


class SessionGuard:
    def __init__(self, windows: dict[str, SessionWindow]) -> None:
        self.windows = windows

    @classmethod
    def from_strings(cls, rows: dict[str, tuple[str, str, str]]) -> "SessionGuard":
        return cls(
            {
                symbol: SessionWindow(
                    open_time=_parse_time(open_text),
                    close_time=_parse_time(close_text),
                    timezone_name=tz_name,
                )
                for symbol, (open_text, close_text, tz_name) in rows.items()
            }
        )

    def is_session_open(self, timestamp_utc: datetime, symbol: str) -> bool:
        window = self.windows.get(symbol)
        if window is None:
            return False
        local_time = utc_datetime(timestamp_utc).astimezone(ZoneInfo(window.timezone_name)).time()
        if window.open_time <= window.close_time:
            return window.open_time <= local_time < window.close_time
        return local_time >= window.open_time or local_time < window.close_time


def _parse_time(value: str) -> day_time:
    hour, minute = value.split(":", 1)
    return day_time(int(hour), int(minute))


class KillSwitch:
    def __init__(self, file_path: str, *, config_active: bool = False) -> None:
        from pathlib import Path

        self.file_path = Path(file_path)
        self.config_active = config_active

    def is_on(self) -> bool:
        return self.config_active or self.file_path.exists()

    def turn_on(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text("ON\n", encoding="utf-8")

    def turn_off(self) -> None:
        if self.file_path.exists():
            self.file_path.unlink()


class RiskManager:
    def __init__(self, config: LiveTradingConfig, *, session_guard: SessionGuard | None = None) -> None:
        self.config = config
        self.session_guard = session_guard
        self._seen_order_ids: set[str] = set()
        self._seen_signal_ids: set[str] = set()
        self._order_times: list[datetime] = []
        self._last_order_time_by_symbol: dict[str, datetime] = {}
        self._last_order_bar_by_symbol: dict[str, datetime] = {}
        self.trades_today = 0

    def evaluate(
        self,
        *,
        order: OrderIntent | None,
        signal: SignalState,
        data_quality: DataQualityResult,
        model_status: ModelReadinessResult,
        reconciliation: ReconciliationResult,
        positions: dict[str, int],
        now: datetime | None = None,
        kill_switch_on: bool = False,
        daily_loss: float = 0.0,
        spread_ticks: float | None = None,
        slippage_ticks: float | None = None,
        session_ok: bool | None = None,
        startup_warmup_complete: bool = True,
        reconnect_reconciled: bool = True,
    ) -> RiskDecision:
        ts = utc_datetime(now or datetime.now(timezone.utc))
        snapshot = {
            "mode": self.config.mode,
            "allow_trading": self.config.allow_trading,
            "allow_paper_trading": self.config.allow_paper_trading,
            "kill_switch_on": kill_switch_on,
            "positions": dict(positions),
            "daily_loss": daily_loss,
            "trades_today": self.trades_today,
        }

        if order is None:
            return self._reject(None, "NO_ORDER", "no order intent generated", snapshot)
        if kill_switch_on:
            return self._reject(order, "KILL_SWITCH_ON", "kill switch blocks new orders", snapshot)
        if not self.config.allow_trading or self.config.mode == "disabled":
            return self._reject(order, "TRADING_DISABLED", "trading is disabled by config", snapshot)
        if self.config.allow_live_broker or self.config.mode == "live":
            return self._reject(order, "LIVE_BROKER_BLOCKED", "live broker path is blocked", snapshot)
        if self.config.mode != "paper" or not self.config.allow_paper_trading:
            return self._reject(order, "PAPER_TRADING_DISABLED", "paper trading is not explicitly enabled", snapshot)
        if self.config.allowed_symbols and order.symbol not in self.config.allowed_symbols:
            return self._reject(order, "SYMBOL_NOT_ALLOWED", "symbol is not explicitly allowed", snapshot)
        if self.config.allowed_contracts and order.contract not in self.config.allowed_contracts:
            return self._reject(order, "CONTRACT_NOT_ALLOWED", "contract is not explicitly allowed", snapshot)
        if session_ok is False or (session_ok is None and self.session_guard is not None and not self.session_guard.is_session_open(ts, order.symbol)):
            return self._reject(order, "OUTSIDE_SESSION", "session guard blocks trading", snapshot)
        if not data_quality.passed or data_quality.severity == "BLOCK":
            return self._reject(order, f"DATA_QUALITY_{data_quality.reason_code}", "data quality failed", snapshot)
        if model_status.status != "READY":
            return self._reject(order, f"MODEL_{model_status.reason_code}", "model is not ready", snapshot)
        if not signal.tradable or signal.signal not in {"LONG", "SHORT"}:
            return self._reject(order, "SIGNAL_NOT_TRADABLE", "signal is not tradable", snapshot)
        if order.quantity <= 0 or order.quantity > self.config.max_order_size:
            return self._reject(order, "ORDER_SIZE_LIMIT", "order size exceeds configured limit", snapshot)
        if self.config.max_daily_loss <= 0:
            return self._reject(order, "DAILY_LOSS_LIMIT_NOT_CONFIGURED", "max_daily_loss must be positive", snapshot)
        if daily_loss >= self.config.max_daily_loss:
            return self._reject(order, "DAILY_LOSS_LIMIT", "daily loss limit reached", snapshot)
        if self.config.max_trades_per_day <= 0 or self.trades_today >= self.config.max_trades_per_day:
            return self._reject(order, "TRADE_COUNT_LIMIT", "daily trade count limit reached", snapshot)
        if self.config.reject_market_orders and order.order_type.upper() == "MARKET":
            return self._reject(order, "MARKET_ORDER_REJECTED", "market orders are rejected by config", snapshot)
        if order.order_id in self._seen_order_ids:
            return self._reject(order, "DUPLICATE_ORDER_ID", "duplicate order id", snapshot)
        if self.config.no_duplicate_signal_order and order.signal_id in self._seen_signal_ids:
            return self._reject(order, "DUPLICATE_SIGNAL_ORDER", "duplicate signal order", snapshot)
        if not startup_warmup_complete:
            return self._reject(order, "STARTUP_WARMUP", "startup warmup is incomplete", snapshot)
        if not reconnect_reconciled:
            return self._reject(order, "RECONNECT_RECONCILIATION_PENDING", "reconnect requires reconciliation", snapshot)
        if reconciliation.status == "FAIL":
            return self._reject(order, "RECONCILIATION_FAILED", "reconciliation failed", snapshot)
        if self.config.max_spread_ticks is not None and spread_ticks is not None and spread_ticks > self.config.max_spread_ticks:
            return self._reject(order, "SPREAD_LIMIT", "spread guard failed", snapshot)
        if self.config.max_slippage_ticks is not None and slippage_ticks is not None and slippage_ticks > self.config.max_slippage_ticks:
            return self._reject(order, "SLIPPAGE_LIMIT", "slippage guard failed", snapshot)

        recent = [item for item in self._order_times if (ts - item).total_seconds() < 60]
        if len(recent) >= self.config.max_orders_per_minute:
            return self._reject(order, "ORDER_RATE_LIMIT", "orders per minute limit reached", snapshot)
        previous_order_time = self._last_order_time_by_symbol.get(order.symbol)
        if (
            previous_order_time is not None
            and (ts - previous_order_time).total_seconds() < self.config.min_seconds_between_orders_per_symbol
        ):
            return self._reject(order, "ORDER_COOLDOWN", "symbol order cooldown active", snapshot)
        if self.config.no_flip_within_same_bar and self._last_order_bar_by_symbol.get(order.symbol) == utc_datetime(order.bar_timestamp):
            return self._reject(order, "SAME_BAR_ORDER", "same-bar duplicate order blocked", snapshot)

        current_position = positions.get(position_key(order.symbol, order.contract), 0)
        signed_quantity = order.quantity if order.side.upper() == "BUY" else -order.quantity
        projected_symbol_position = current_position + signed_quantity
        if (
            self.config.no_flip_within_same_bar
            and current_position != 0
            and projected_symbol_position != 0
            and (current_position > 0) != (projected_symbol_position > 0)
        ):
            return self._reject(order, "IMMEDIATE_FLIP_BLOCKED", "flat-first workflow is required before flipping", snapshot)
        if abs(projected_symbol_position) > self.config.max_contracts_per_symbol:
            return self._reject(order, "SYMBOL_POSITION_LIMIT", "projected symbol position exceeds limit", snapshot)
        projected_positions = dict(positions)
        projected_positions[position_key(order.symbol, order.contract)] = projected_symbol_position
        if sum(abs(value) for value in projected_positions.values()) > self.config.max_total_contracts:
            return self._reject(order, "TOTAL_POSITION_LIMIT", "projected total position exceeds limit", snapshot)

        self._seen_order_ids.add(order.order_id)
        self._seen_signal_ids.add(order.signal_id)
        self._order_times = recent + [ts]
        self._last_order_time_by_symbol[order.symbol] = ts
        self._last_order_bar_by_symbol[order.symbol] = utc_datetime(order.bar_timestamp)
        self.trades_today += 1
        return RiskDecision(True, "OK", "order intent approved for paper broker", order, None, snapshot)

    @staticmethod
    def _reject(
        order: OrderIntent | None,
        reason_code: str,
        reason: str,
        snapshot: dict[str, object],
    ) -> RiskDecision:
        return RiskDecision(False, reason_code, reason, None, order, snapshot)
