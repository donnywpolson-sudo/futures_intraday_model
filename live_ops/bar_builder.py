"""Historical/live bar parity and deterministic live bar building."""

from __future__ import annotations

from datetime import datetime, timezone
from math import floor
from typing import Any, Iterable, Mapping

from .schemas import BarParityResult, LiveBar, LiveRecord, utc_datetime

BAR_CONTRACT_FIELDS = (
    "timestamp_utc",
    "symbol",
    "contract",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "bar_is_final",
    "source_schema",
)
FEATURE_EXCLUSION_FIELDS = ("bar_is_final", "source_schema")


def floor_timestamp(value: datetime, seconds: int) -> datetime:
    timestamp = utc_datetime(value).timestamp()
    return datetime.fromtimestamp(floor(timestamp / seconds) * seconds, tz=timezone.utc)


def bar_contract_row(bar: LiveBar) -> dict[str, Any]:
    return {field: getattr(bar, field) for field in BAR_CONTRACT_FIELDS}


def check_bar_parity(
    historical_rows: Iterable[Mapping[str, Any]],
    live_rows: Iterable[Mapping[str, Any]],
) -> BarParityResult:
    historical = list(historical_rows)
    live = list(live_rows)
    if not historical or not live:
        return BarParityResult(False, "EMPTY_INPUT", {"historical_rows": len(historical), "live_rows": len(live)})

    expected = set(BAR_CONTRACT_FIELDS)
    for label, rows in (("historical", historical), ("live", live)):
        fields = set(rows[0])
        if fields != expected:
            return BarParityResult(
                False,
                "FIELD_MISMATCH",
                {"side": label, "expected": sorted(expected), "actual": sorted(fields)},
            )
        timestamp = rows[0]["timestamp_utc"]
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            return BarParityResult(False, "TIMESTAMP_NOT_TZ_AWARE", {"side": label})

    historical_types = {field: type(historical[0][field]).__name__ for field in BAR_CONTRACT_FIELDS}
    live_types = {field: type(live[0][field]).__name__ for field in BAR_CONTRACT_FIELDS}
    if historical_types != live_types:
        return BarParityResult(False, "DTYPE_MISMATCH", {"historical": historical_types, "live": live_types})

    return BarParityResult(
        True,
        "OK",
        {
            "timestamp_convention": "UTC timezone-aware bar start",
            "bar_close_timing": "final bars only after bucket advances or explicit flush",
            "no_trade_interval_behavior": "no synthetic zero-volume bars are emitted by default",
            "session_boundary_rules": "consumer must supply explicit session policy",
            "feature_exclusion_rules": FEATURE_EXCLUSION_FIELDS,
        },
    )


class LiveBarBuilder:
    def __init__(self, *, timeframe: str = "1m", timeframe_seconds: int = 60, source_schema: str = "synthetic-l1"):
        self.timeframe = timeframe
        self.timeframe_seconds = timeframe_seconds
        self.source_schema = source_schema
        self._bucket: datetime | None = None
        self._symbol: str | None = None
        self._contract: str | None = None
        self._open: float | None = None
        self._high: float | None = None
        self._low: float | None = None
        self._close: float | None = None
        self._volume = 0
        self.last_record_time: datetime | None = None

    def update(self, record: LiveRecord) -> list[LiveBar]:
        ts = utc_datetime(record.timestamp_utc)
        if self.last_record_time is not None and ts < self.last_record_time:
            raise ValueError("live record timestamp moved backward")
        self.last_record_time = ts
        bucket = floor_timestamp(ts, self.timeframe_seconds)
        emitted: list[LiveBar] = []

        if self._bucket is not None and bucket > self._bucket:
            emitted.append(self._build_bar(final=True))
            self._reset(bucket, record)
            return emitted

        if self._bucket is None:
            self._reset(bucket, record)
            return emitted

        if record.symbol != self._symbol or record.contract != self._contract:
            raise ValueError("cannot mix symbols or contracts in one live bar builder")

        price = float(record.price)
        self._high = max(float(self._high), price)
        self._low = min(float(self._low), price)
        self._close = price
        self._volume += int(record.size)
        return emitted

    def current_bar(self) -> LiveBar | None:
        if self._bucket is None:
            return None
        return self._build_bar(final=False)

    def flush(self, *, final: bool = True) -> LiveBar | None:
        if self._bucket is None:
            return None
        bar = self._build_bar(final=final)
        self._bucket = None
        return bar

    def _reset(self, bucket: datetime, record: LiveRecord) -> None:
        price = float(record.price)
        self._bucket = bucket
        self._symbol = record.symbol
        self._contract = record.contract
        self._open = price
        self._high = price
        self._low = price
        self._close = price
        self._volume = int(record.size)

    def _build_bar(self, *, final: bool) -> LiveBar:
        if self._bucket is None or self._symbol is None or self._contract is None:
            raise ValueError("no active bar")
        return LiveBar(
            symbol=self._symbol,
            contract=self._contract,
            timestamp_utc=self._bucket,
            timeframe=self.timeframe,
            open=float(self._open),
            high=float(self._high),
            low=float(self._low),
            close=float(self._close),
            volume=int(self._volume),
            bar_is_final=final,
            source_schema=self.source_schema,
        )
