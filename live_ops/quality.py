"""Fail-closed live data quality gate."""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from .schemas import DataQualityResult, LiveBar, LiveTradingConfig, utc_datetime


class DataQualityGate:
    def __init__(
        self,
        config: LiveTradingConfig,
        *,
        tick_sizes: dict[str, float] | None = None,
        impossible_range_by_symbol: dict[str, float] | None = None,
        session_guard: Any | None = None,
    ) -> None:
        self.config = config
        self.tick_sizes = tick_sizes or {}
        self.impossible_range_by_symbol = impossible_range_by_symbol or {}
        self.session_guard = session_guard
        self._seen_timestamps: set[tuple[str, str, str, datetime]] = set()
        self._last_timestamp: dict[tuple[str, str, str], datetime] = {}
        self._active_contract_by_symbol: dict[str, str] = {}

    def validate(
        self,
        bar: LiveBar,
        *,
        now: datetime | None = None,
        heartbeat_timestamp_utc: datetime | None = None,
        heartbeat_required: bool = False,
        feed_connected: bool = True,
        reconnect_backfill_required: bool = False,
        active_symbol: str | None = None,
        active_contract: str | None = None,
    ) -> DataQualityResult:
        try:
            ts = utc_datetime(bar.timestamp_utc)
        except ValueError:
            return self._block(bar, "TIMESTAMP_NOT_TZ_AWARE", "bar timestamp must be timezone-aware", None, None)

        age_seconds = None
        if now is not None:
            age_seconds = max(0.0, (utc_datetime(now) - ts).total_seconds())

        if not feed_connected:
            return self._block(bar, "FEED_DISCONNECTED", "market data feed is disconnected", ts, age_seconds)
        if heartbeat_required and heartbeat_timestamp_utc is None:
            return self._block(bar, "NO_HEARTBEAT", "feed heartbeat is required but missing", ts, age_seconds)
        if reconnect_backfill_required:
            return self._block(bar, "RECONNECT_BACKFILL_REQUIRED", "reconnect requires replay/backfill before trading", ts, age_seconds)

        key = (bar.symbol, bar.contract, bar.timeframe)
        timestamp_key = (*key, ts)
        if timestamp_key in self._seen_timestamps:
            if self.config.duplicate_timestamp_policy == "dedupe":
                return DataQualityResult(
                    True,
                    "WARN",
                    "DUPLICATE_TIMESTAMP_DEDUPED",
                    "duplicate timestamp accepted by explicit dedupe policy",
                    bar.symbol,
                    ts,
                    age_seconds,
                    self.config.duplicate_timestamp_policy,
                )
            return self._block(bar, "DUPLICATE_TIMESTAMP", "duplicate timestamp blocked", ts, age_seconds)

        last_ts = self._last_timestamp.get(key)
        if last_ts is not None and ts < last_ts:
            return self._block(bar, "TIMESTAMP_MOVED_BACKWARD", "bar timestamp moved backward", ts, age_seconds)
        if (
            last_ts is not None
            and self.config.max_timestamp_gap_seconds is not None
            and (ts - last_ts).total_seconds() > self.config.max_timestamp_gap_seconds
        ):
            return self._block(bar, "TIMESTAMP_GAP", "large timestamp gap blocked", ts, age_seconds)

        if not self._finite_ohlc(bar):
            return self._block(bar, "OHLC_NOT_FINITE", "OHLC values must be finite", ts, age_seconds)
        if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
            return self._block(bar, "BAD_OHLC", "OHLC relationship is impossible", ts, age_seconds)
        if bar.volume < 0:
            return self._block(bar, "NEGATIVE_VOLUME", "volume must be >= 0", ts, age_seconds)

        tick_size = self.tick_sizes.get(bar.symbol)
        if tick_size is not None and tick_size > 0:
            for price in (bar.open, bar.high, bar.low, bar.close):
                ticks = round(price / tick_size)
                if abs(price - ticks * tick_size) > 1e-9:
                    return self._block(bar, "PRICE_OFF_TICK_GRID", "price is off configured tick grid", ts, age_seconds)

        if self.config.allowed_symbols and bar.symbol not in self.config.allowed_symbols:
            return self._block(bar, "UNKNOWN_SYMBOL", "symbol is not explicitly allowed", ts, age_seconds)
        if self.config.allowed_contracts and bar.contract not in self.config.allowed_contracts:
            return self._block(bar, "UNKNOWN_CONTRACT", "contract is not explicitly allowed", ts, age_seconds)
        if active_symbol is not None and bar.symbol != active_symbol:
            return self._block(bar, "ROOT_SYMBOL_MISMATCH", "bar symbol does not match active root symbol", ts, age_seconds)
        if active_contract is not None and bar.contract != active_contract:
            return self._block(bar, "CONTRACT_MISMATCH", "bar contract does not match active contract", ts, age_seconds)

        previous_contract = self._active_contract_by_symbol.get(bar.symbol)
        if previous_contract is not None and previous_contract != bar.contract:
            return self._block(bar, "CONTRACT_MIX", "contract changed inside active symbol window", ts, age_seconds)

        max_range = self.impossible_range_by_symbol.get(bar.symbol)
        if max_range is not None and bar.high - bar.low > max_range:
            return self._block(bar, "IMPOSSIBLE_RANGE", "bar range exceeds configured limit", ts, age_seconds)

        if age_seconds is not None and age_seconds > self.config.stale_bar_seconds:
            return self._block(bar, "DATA_STALE", "latest bar is stale", ts, age_seconds)

        if heartbeat_timestamp_utc is not None and now is not None:
            heartbeat_age = (utc_datetime(now) - utc_datetime(heartbeat_timestamp_utc)).total_seconds()
            if heartbeat_age > self.config.heartbeat_timeout_seconds:
                return self._block(bar, "HEARTBEAT_STALE", "feed heartbeat is stale", ts, age_seconds)

        if self.session_guard is not None:
            session_check = self.session_guard.check(ts, bar.symbol)
            if not session_check.allowed:
                return self._block(bar, session_check.reason_code, "session guard blocks trading", ts, age_seconds)

        self._seen_timestamps.add(timestamp_key)
        self._last_timestamp[key] = ts
        self._active_contract_by_symbol[bar.symbol] = bar.contract
        return DataQualityResult(
            True,
            "OK",
            "OK",
            "data quality checks passed",
            bar.symbol,
            ts,
            age_seconds,
            self.config.duplicate_timestamp_policy,
        )

    def _block(
        self,
        bar: LiveBar,
        reason_code: str,
        message: str,
        timestamp: datetime | None,
        age_seconds: float | None,
    ) -> DataQualityResult:
        return DataQualityResult(
            False,
            "BLOCK",
            reason_code,
            message,
            bar.symbol,
            timestamp,
            age_seconds,
            self.config.duplicate_timestamp_policy,
        )

    @staticmethod
    def _finite_ohlc(bar: LiveBar) -> bool:
        return all(isfinite(float(value)) for value in (bar.open, bar.high, bar.low, bar.close))
