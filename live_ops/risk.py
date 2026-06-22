"""Fail-closed risk controls for paper-only order intents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as day_time, timezone
from typing import Mapping
from zoneinfo import ZoneInfo

from .schemas import (
    DataQualityResult,
    LiveTradingConfig,
    ModelReadinessResult,
    OrderIntent,
    ReconciliationResult,
    OrderIntentDecision,
    OrderPreflightResult,
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


@dataclass(frozen=True)
class SessionCheckResult:
    allowed: bool
    reason_code: str
    symbol: str
    session_state: str


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

    def check(self, timestamp_utc: datetime, symbol: str) -> SessionCheckResult:
        window = self.windows.get(symbol)
        if window is None:
            return SessionCheckResult(False, "SESSION_MISSING", symbol, "MISSING")
        local_time = utc_datetime(timestamp_utc).astimezone(ZoneInfo(window.timezone_name)).time()
        if window.open_time <= window.close_time:
            is_open = window.open_time <= local_time < window.close_time
        else:
            is_open = local_time >= window.open_time or local_time < window.close_time
        if is_open:
            return SessionCheckResult(True, "SESSION_OPEN", symbol, "OPEN")
        return SessionCheckResult(False, "SESSION_CLOSED", symbol, "CLOSED")

    def is_session_open(self, timestamp_utc: datetime, symbol: str) -> bool:
        return self.check(timestamp_utc, symbol).allowed


def _parse_time(value: str) -> day_time:
    hour, minute = value.split(":", 1)
    return day_time(int(hour), int(minute))


def preflight_order_intent(
    *,
    config: LiveTradingConfig,
    intent_decision: OrderIntentDecision,
    positions: Mapping[str, int] | None = None,
    now: datetime | None = None,
    kill_switch_on: bool = False,
    open_order_count: int = 0,
    max_open_orders: int | None = None,
    existing_order_ids: tuple[str, ...] = (),
    last_order_time_by_symbol: Mapping[str, datetime] | None = None,
) -> OrderPreflightResult:
    timestamp = utc_datetime(now or datetime.now(timezone.utc))
    positions = positions or {}
    intent = intent_decision.order_intent
    if not intent_decision.approved or intent is None:
        return _preflight_block(
            "BLOCKED_BEFORE_INTENT",
            "INTENT_NOT_APPROVED",
            intent_decision.reason,
            intent,
            config=config,
            timestamp=timestamp,
            details={"intent_decision": intent_decision},
        )

    if kill_switch_on:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "KILL_SWITCH_ON",
            "kill switch blocks routing preflight",
            intent,
            config=config,
            timestamp=timestamp,
        )
    if not config.allow_trading or config.mode == "disabled":
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "TRADING_DISABLED",
            "trading is disabled by config",
            intent,
            config=config,
            timestamp=timestamp,
        )
    if config.allow_live_broker or config.mode == "live":
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "LIVE_BROKER_BLOCKED",
            "live broker routing is blocked by scaffold preflight",
            intent,
            config=config,
            timestamp=timestamp,
        )
    if config.mode != "paper" or not config.allow_paper_trading:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "PAPER_TRADING_DISABLED",
            "paper routing is not explicitly enabled",
            intent,
            config=config,
            timestamp=timestamp,
        )
    if not intent.symbol:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "SYMBOL_MISSING",
            "order intent symbol is required",
            intent,
            config=config,
            timestamp=timestamp,
        )
    if config.allowed_symbols and intent.symbol not in config.allowed_symbols:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "SYMBOL_UNSUPPORTED",
            "order intent symbol is not allowed",
            intent,
            config=config,
            timestamp=timestamp,
            limit_name="allowed_symbols",
            limit_value=config.allowed_symbols,
        )
    if config.allowed_contracts and intent.contract not in config.allowed_contracts:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "CONTRACT_UNSUPPORTED",
            "order intent contract is not allowed",
            intent,
            config=config,
            timestamp=timestamp,
            limit_name="allowed_contracts",
            limit_value=config.allowed_contracts,
        )
    side = intent.side.upper()
    if side not in {"BUY", "SELL"}:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "ORDER_SIDE_INVALID",
            "order intent side must be BUY or SELL",
            intent,
            config=config,
            timestamp=timestamp,
        )
    if isinstance(intent.quantity, bool) or not isinstance(intent.quantity, int) or intent.quantity <= 0:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "ORDER_QUANTITY_INVALID",
            "order intent quantity must be a positive integer",
            intent,
            config=config,
            timestamp=timestamp,
        )
    if config.max_order_size <= 0 or intent.quantity > config.max_order_size:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "ORDER_SIZE_LIMIT",
            "order intent quantity exceeds max order size",
            intent,
            config=config,
            timestamp=timestamp,
            limit_name="max_order_size",
            limit_value=config.max_order_size,
        )
    if max_open_orders is not None and open_order_count >= max_open_orders:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "OPEN_ORDER_LIMIT",
            "open order count exceeds scaffold limit",
            intent,
            config=config,
            timestamp=timestamp,
            limit_name="max_open_orders",
            limit_value=max_open_orders,
        )
    if intent.order_id in existing_order_ids:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "DUPLICATE_ORDER_ID",
            "duplicate order intent id",
            intent,
            config=config,
            timestamp=timestamp,
        )

    last_order_time_by_symbol = last_order_time_by_symbol or {}
    previous_time = last_order_time_by_symbol.get(intent.symbol)
    if previous_time is not None and config.min_seconds_between_orders_per_symbol > 0:
        elapsed = (timestamp - utc_datetime(previous_time)).total_seconds()
        if elapsed < config.min_seconds_between_orders_per_symbol:
            return _preflight_block(
                "BLOCKED_BY_PREFLIGHT",
                "ORDER_COOLDOWN",
                "symbol order cooldown active",
                intent,
                config=config,
                timestamp=timestamp,
                limit_name="min_seconds_between_orders_per_symbol",
                limit_value=config.min_seconds_between_orders_per_symbol,
                details={"elapsed_seconds": elapsed},
            )

    current_position = int(positions.get(position_key(intent.symbol, intent.contract), 0))
    signed_quantity = intent.quantity if side == "BUY" else -intent.quantity
    projected_position = current_position + signed_quantity
    if abs(projected_position) > config.max_contracts_per_symbol:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "SYMBOL_POSITION_LIMIT",
            "projected symbol position exceeds scaffold max",
            intent,
            config=config,
            timestamp=timestamp,
            limit_name="max_contracts_per_symbol",
            limit_value=config.max_contracts_per_symbol,
            projected_position=projected_position,
        )
    projected_positions = dict(positions)
    projected_positions[position_key(intent.symbol, intent.contract)] = projected_position
    if sum(abs(int(value)) for value in projected_positions.values()) > config.max_total_contracts:
        return _preflight_block(
            "BLOCKED_BY_PREFLIGHT",
            "TOTAL_POSITION_LIMIT",
            "projected total position exceeds scaffold max",
            intent,
            config=config,
            timestamp=timestamp,
            limit_name="max_total_contracts",
            limit_value=config.max_total_contracts,
            projected_position=projected_position,
        )

    return OrderPreflightResult(
        True,
        "ACCEPTED_FOR_ROUTING",
        "OK",
        "order intent accepted by scaffold preflight; no broker submission performed",
        intent,
        config.mode,
        intent.symbol,
        side,
        intent.quantity,
        timestamp,
        projected_position=projected_position,
        details={"positions": dict(positions), "projected_positions": projected_positions},
    )


def _preflight_block(
    status: str,
    reason_code: str,
    reason: str,
    intent: OrderIntent | None,
    *,
    config: LiveTradingConfig,
    timestamp: datetime,
    limit_name: str | None = None,
    limit_value: object | None = None,
    projected_position: int | None = None,
    details: dict[str, object] | None = None,
) -> OrderPreflightResult:
    return OrderPreflightResult(
        False,
        status,
        reason_code,
        reason,
        intent,
        config.mode,
        intent.symbol if intent is not None else None,
        intent.side.upper() if intent is not None else None,
        intent.quantity if intent is not None else None,
        timestamp,
        limit_name=limit_name,
        limit_value=limit_value,
        projected_position=projected_position,
        details=details or {},
    )


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
        active_symbol: str | None = None,
        active_contract: str | None = None,
        monitor_only: bool = False,
    ) -> RiskDecision:
        ts = utc_datetime(now or datetime.now(timezone.utc))
        snapshot = {
            "mode": self.config.mode,
            "allow_trading": self.config.allow_trading,
            "allow_paper_trading": self.config.allow_paper_trading,
            "kill_switch_on": kill_switch_on,
            "active_symbol": active_symbol,
            "active_contract": active_contract,
            "monitor_only": monitor_only,
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
        if active_symbol is not None and order.symbol != active_symbol:
            return self._reject(order, "ROOT_SYMBOL_MISMATCH", "order symbol does not match active root symbol", snapshot)
        if active_contract is not None and order.contract != active_contract:
            return self._reject(order, "CONTRACT_MISMATCH", "order contract does not match active contract", snapshot)
        if monitor_only:
            return self._reject(order, "MONITOR_ONLY", "monitor-only runtime state blocks trading", snapshot)
        if self.config.allowed_symbols and order.symbol not in self.config.allowed_symbols:
            return self._reject(order, "SYMBOL_NOT_ALLOWED", "symbol is not explicitly allowed", snapshot)
        if self.config.allowed_contracts and order.contract not in self.config.allowed_contracts:
            return self._reject(order, "CONTRACT_NOT_ALLOWED", "contract is not explicitly allowed", snapshot)
        if session_ok is False:
            return self._reject(order, "OUTSIDE_SESSION", "session guard blocks trading", snapshot)
        if session_ok is None and self.session_guard is not None:
            session_check = self.session_guard.check(ts, order.symbol)
            snapshot["session_check"] = session_check
            if not session_check.allowed:
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
