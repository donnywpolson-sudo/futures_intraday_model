"""Shared live-operations schemas.

This module is intentionally broker-agnostic. It contains no live broker SDK
imports and defaults to disabled, paper-only behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return utc_datetime(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def plain_data(value: Any) -> Any:
    if isinstance(value, datetime):
        return iso_utc(value)
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: plain_data(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [plain_data(item) for item in value]
    return value


@dataclass(frozen=True)
class LiveTradingConfig:
    mode: str = "disabled"
    allow_trading: bool = False
    allow_paper_trading: bool = False
    allow_live_broker: bool = False
    max_contracts_per_symbol: int = 1
    max_total_contracts: int = 1
    max_order_size: int = 1
    max_daily_loss: float = 0.0
    max_trades_per_day: int = 0
    max_orders_per_minute: int = 2
    allowed_symbols: tuple[str, ...] = ()
    allowed_contracts: tuple[str, ...] = ()
    allowed_sessions: tuple[str, ...] = ()
    flatten_before_session_close_minutes: int = 0
    reject_market_orders: bool = True
    max_slippage_ticks: float | None = None
    max_spread_ticks: float | None = None
    min_seconds_between_orders_per_symbol: float = 30.0
    no_flip_within_same_bar: bool = True
    no_duplicate_signal_order: bool = True
    no_trade_on_partial_bar: bool = True
    duplicate_timestamp_policy: str = "block"
    stale_bar_seconds: float = 90.0
    heartbeat_timeout_seconds: float = 30.0
    max_timestamp_gap_seconds: float | None = 180.0
    audit_dir: str = "reports/live_trading_smoke"
    kill_switch_file: str = ".runtime/KILL_SWITCH_ON"
    startup_warmup_bars: int = 0


def safe_default_config() -> LiveTradingConfig:
    return LiveTradingConfig()


def paper_smoke_config(*, audit_dir: str = "reports/live_trading_smoke") -> LiveTradingConfig:
    return LiveTradingConfig(
        mode="paper",
        allow_trading=True,
        allow_paper_trading=True,
        allow_live_broker=False,
        max_contracts_per_symbol=1,
        max_total_contracts=1,
        max_order_size=1,
        max_daily_loss=1000.0,
        max_trades_per_day=10,
        max_orders_per_minute=10,
        allowed_symbols=("ES",),
        allowed_contracts=("ESU6",),
        reject_market_orders=True,
        min_seconds_between_orders_per_symbol=0.0,
        audit_dir=audit_dir,
    )


@dataclass(frozen=True)
class LiveRecord:
    symbol: str
    contract: str
    timestamp_utc: datetime
    price: float
    size: int
    source_schema: str = "synthetic-l1"


@dataclass(frozen=True)
class LiveBar:
    symbol: str
    contract: str
    timestamp_utc: datetime
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    bar_is_final: bool
    source_schema: str


@dataclass(frozen=True)
class BarParityResult:
    passed: bool
    reason_code: str
    details: dict[str, Any]
    missing_columns: tuple[str, ...] = ()
    extra_columns: tuple[str, ...] = ()
    dtype_mismatches: dict[str, tuple[str, str]] = field(default_factory=dict)
    timezone_status: str = "UNKNOWN"
    partial_bar_status: str = "UNKNOWN"


@dataclass(frozen=True)
class DataQualityResult:
    passed: bool
    severity: str
    reason_code: str
    human_message: str
    affected_symbol: str
    latest_bar_time: datetime | None
    latest_bar_age_seconds: float | None
    duplicate_timestamp_policy: str


@dataclass(frozen=True)
class ModelReadinessResult:
    status: str
    reason_code: str
    expected_features: tuple[str, ...] = ()
    missing_features: tuple[str, ...] = ()
    extra_features: tuple[str, ...] = ()
    ordered_features: tuple[str, ...] = ()
    model_version: str | None = None
    config_version: str | None = None
    feature_version: str | None = None


@dataclass(frozen=True)
class SignalState:
    symbol: str
    contract: str
    timestamp_utc: datetime
    bar_timestamp_utc: datetime
    timeframe: str
    features_ready: bool
    model_available: bool
    model_version: str | None
    config_version: str | None
    feature_version: str | None
    prediction: float | None
    score: float | None
    signal: str
    confidence: float | None
    tradable: bool
    skip_reason: str | None
    data_quality_status: str
    source_schema: str
    bar_is_final: bool


@dataclass(frozen=True)
class OrderIntent:
    order_id: str
    strategy_id: str
    symbol: str
    contract: str
    side: str
    quantity: int
    order_type: str
    limit_price: float | None
    stop_price: float | None
    time_in_force: str
    bar_timestamp: datetime
    created_timestamp: datetime
    reason: str
    signal_id: str


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason_code: str
    reason: str
    adjusted_order: OrderIntent | None
    rejected_order: OrderIntent | None
    risk_snapshot: dict[str, Any]


@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    contract: str
    side: str
    quantity: int
    fill_price: float
    timestamp_utc: datetime
    commission: float = 0.0
    slippage: float = 0.0


@dataclass(frozen=True)
class BrokerResponse:
    accepted: bool
    status: str
    reason_code: str
    message: str
    fill: Fill | None = None


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    reason_code: str
    details: dict[str, Any]


def position_key(symbol: str, contract: str) -> str:
    return f"{symbol}:{contract}"
