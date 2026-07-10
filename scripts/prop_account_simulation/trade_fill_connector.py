#!/usr/bin/env python3
"""Convert validated trade/fill ledger rows into prop-account simulator events."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo


SOURCE_EVENT_TYPES = {
    "fill",
    "mark",
    "session_eod",
    "payout_request",
    "payout_approved",
    "payout_denied",
}
BASE_REQUIRED_FIELDS = (
    "timestamp",
    "event_id",
    "event_type",
    "realized_pnl",
    "unrealized_pnl",
    "open_contracts",
)
COST_FIELDS = ("commission", "exchange_fees", "slippage")
APEX_EOD_TIMEZONE = ZoneInfo("America/New_York")
APEX_EOD_SNAPSHOT_TIME = time(16, 59, 59)
APEX_TRADING_DAY_RESET_TIME = time(18, 0, 0)


class TradeFillConnectorError(ValueError):
    """Raised when a trade/fill source ledger cannot be safely converted."""


@dataclass(frozen=True)
class ConnectorResult:
    events: list[dict[str, Any]]
    metadata: dict[str, Any]


def _rows_from_source(source_rows: Any) -> list[Mapping[str, Any]]:
    if hasattr(source_rows, "to_dict"):
        records = source_rows.to_dict("records")
    else:
        records = list(source_rows)
    if not all(isinstance(row, Mapping) for row in records):
        raise TradeFillConnectorError("source ledger rows must be mappings")
    return records


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        timestamp = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            timestamp = datetime.fromisoformat(text)
        except ValueError as exc:
            raise TradeFillConnectorError(f"invalid timestamp: {value!r}") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise TradeFillConnectorError("timestamp must be timezone-aware")
    return timestamp


def _apex_local_timestamp(timestamp: datetime) -> datetime:
    return timestamp.astimezone(APEX_EOD_TIMEZONE)


def _apex_session_date(timestamp: datetime) -> str:
    local_timestamp = _apex_local_timestamp(timestamp)
    session_date = local_timestamp.date()
    if local_timestamp.timetz().replace(tzinfo=None) >= APEX_TRADING_DAY_RESET_TIME:
        session_date += timedelta(days=1)
    return session_date.isoformat()


def _validated_eod_timestamp(timestamp: datetime) -> datetime:
    local_timestamp = _apex_local_timestamp(timestamp)
    local_time = local_timestamp.timetz().replace(tzinfo=None)
    if local_time != APEX_EOD_SNAPSHOT_TIME:
        raise TradeFillConnectorError(
            "session_eod timestamp must align to Apex EOD snapshot time "
            "16:59:59 America/New_York"
        )
    return local_timestamp


def _as_float(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    if value is None:
        raise TradeFillConnectorError(f"missing required field: {key}")
    return float(value)


def _as_int(value: Any) -> int:
    if value is None:
        raise TradeFillConnectorError("sequence_number is required for same-timestamp rows")
    return int(value)


def _stable_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _has_nonzero_cost(row: Mapping[str, Any]) -> bool:
    return any(float(row.get(field) or 0.0) != 0.0 for field in COST_FIELDS)


def _ensure_required_fields(row: Mapping[str, Any]) -> None:
    for field in BASE_REQUIRED_FIELDS:
        if field not in row or row[field] is None:
            raise TradeFillConnectorError(f"missing required field: {field}")


def _sort_key(
    row: Mapping[str, Any],
    timestamp: datetime,
    *,
    prior_timestamp: datetime | None,
    event_id_ordered: bool,
) -> tuple[datetime, str, int | str]:
    same_timestamp = prior_timestamp is not None and timestamp == prior_timestamp
    has_sequence = row.get("sequence_number") is not None
    if has_sequence:
        return (timestamp, "sequence_number", _as_int(row.get("sequence_number")))
    if event_id_ordered:
        return (timestamp, "event_id", str(row["event_id"]))
    if same_timestamp:
        raise TradeFillConnectorError(
            "duplicate timestamp requires deterministic sequence_number or documented ordered event_id"
        )
    return (timestamp, "none", "")


def convert_trade_fill_ledger(
    source_rows: Any,
    *,
    source_id: str = "in_memory",
    event_id_ordered: bool = False,
    allow_separate_cost_columns: bool = False,
    require_eod_for_activity: bool = True,
) -> ConnectorResult:
    """Convert source ledger rows into synthetic simulator events.

    The connector validates and maps rows only. It does not run the prop-account
    simulator and does not write report artifacts.
    """

    rows = _rows_from_source(source_rows)
    events: list[dict[str, Any]] = []
    event_ids: set[str] = set()
    prior_key: tuple[datetime, str, int | str] | None = None
    prior_timestamp: datetime | None = None
    activity_dates: set[str] = set()
    eod_dates: set[str] = set()
    pending_payout_amount: float | None = None
    closure_seen = False

    for row in rows:
        _ensure_required_fields(row)
        event_id = str(row["event_id"])
        if event_id in event_ids:
            raise TradeFillConnectorError(f"duplicate event_id: {event_id}")
        event_ids.add(event_id)

        source_event_type = str(row["event_type"])
        if source_event_type not in SOURCE_EVENT_TYPES:
            raise TradeFillConnectorError(f"unknown source event_type: {source_event_type}")
        if closure_seen:
            raise TradeFillConnectorError("source event after account closure/completion marker")

        timestamp = _parse_timestamp(row["timestamp"])
        key = _sort_key(
            row,
            timestamp,
            prior_timestamp=prior_timestamp,
            event_id_ordered=event_id_ordered,
        )
        if prior_key is not None:
            same_timestamp = prior_timestamp is not None and timestamp == prior_timestamp
            if same_timestamp and key[1] != prior_key[1]:
                raise TradeFillConnectorError(
                    "same-timestamp rows must use one deterministic ordering scheme"
                )
            if key <= prior_key:
                raise TradeFillConnectorError("source rows are not in deterministic chronological order")
        prior_key = key
        prior_timestamp = timestamp

        pnl_mode = str(row.get("realized_pnl_mode") or row.get("pnl_basis") or "delta").lower()
        if pnl_mode == "cumulative":
            raise TradeFillConnectorError("realized_pnl must be an event delta, not cumulative")
        if _has_nonzero_cost(row) and not allow_separate_cost_columns:
            raise TradeFillConnectorError("costs cannot be reconciled as exactly once")

        realized_pnl = _as_float(row, "realized_pnl")
        unrealized_pnl = _as_float(row, "unrealized_pnl")
        open_contracts = _as_float(row, "open_contracts")
        if open_contracts < 0:
            raise TradeFillConnectorError("open_contracts must be nonnegative standard-contract exposure")

        if source_event_type in {"fill", "mark"}:
            activity_dates.add(_apex_session_date(timestamp))
        if source_event_type == "session_eod":
            timestamp = _validated_eod_timestamp(timestamp)
            eod_dates.add(_apex_session_date(timestamp))

        if source_event_type == "mark" and realized_pnl != 0.0:
            raise TradeFillConnectorError("mark events must not carry realized_pnl")
        if source_event_type.startswith("payout_") and realized_pnl != 0.0:
            raise TradeFillConnectorError("payout events must not carry realized_pnl")

        if source_event_type == "fill":
            event = {
                "timestamp": timestamp.isoformat(),
                "event_type": "trade",
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "open_contracts": open_contracts,
            }
        elif source_event_type == "mark":
            event = {
                "timestamp": timestamp.isoformat(),
                "event_type": "trade",
                "realized_pnl": 0.0,
                "unrealized_pnl": unrealized_pnl,
                "open_contracts": open_contracts,
            }
        elif source_event_type == "session_eod":
            event = {
                "timestamp": timestamp.isoformat(),
                "event_type": "eod",
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "open_contracts": open_contracts,
            }
        elif source_event_type == "payout_request":
            requested = float(row.get("payout_amount") or 0.0)
            if requested <= 0:
                raise TradeFillConnectorError("payout_request requires positive payout_amount")
            if pending_payout_amount is not None:
                raise TradeFillConnectorError("payout request already pending")
            pending_payout_amount = requested
            event = {
                "timestamp": timestamp.isoformat(),
                "event_type": "payout_request",
                "requested_payout_amount": requested,
                "unrealized_pnl": unrealized_pnl,
                "open_contracts": open_contracts,
            }
        elif source_event_type == "payout_approved":
            approved = float(row.get("payout_amount") or 0.0)
            if pending_payout_amount is None:
                raise TradeFillConnectorError("payout approval requires prior request")
            if approved != pending_payout_amount:
                raise TradeFillConnectorError("payout approval amount differs from request amount")
            pending_payout_amount = None
            event = {
                "timestamp": timestamp.isoformat(),
                "event_type": "payout_approved",
                "approved_payout_amount": approved,
                "unrealized_pnl": unrealized_pnl,
                "open_contracts": open_contracts,
            }
        elif source_event_type == "payout_denied":
            denied_amount = row.get("payout_amount")
            if pending_payout_amount is None:
                raise TradeFillConnectorError("payout denial requires prior request")
            if denied_amount is not None and float(denied_amount) != pending_payout_amount:
                raise TradeFillConnectorError("payout denial amount differs from request amount")
            pending_payout_amount = None
            event = {
                "timestamp": timestamp.isoformat(),
                "event_type": "payout_denied",
                "unrealized_pnl": unrealized_pnl,
                "open_contracts": open_contracts,
            }
        else:  # pragma: no cover - SOURCE_EVENT_TYPES validation covers this.
            raise TradeFillConnectorError(f"unhandled source event_type: {source_event_type}")

        events.append(event)
        account_status = str(row.get("account_status") or "").lower()
        if account_status in {"closed", "completed"}:
            closure_seen = True

    if require_eod_for_activity:
        missing_eod_dates = sorted(activity_dates - eod_dates)
        if missing_eod_dates:
            raise TradeFillConnectorError(f"missing EOD snapshot for active trading dates: {missing_eod_dates}")

    metadata = {
        "source_id": source_id,
        "source_hash": _stable_hash(rows),
        "row_count_in": len(rows),
        "event_count_out": len(events),
        "rejected_row_count": 0,
        "normalization_assumptions": [
            "realized_pnl_is_event_delta",
            "unrealized_pnl_is_total_account_open_pnl",
            "open_contracts_is_standard_contract_equivalent",
            "costs_are_not_folded_by_connector",
        ],
        "same_timestamp_ordering": "sequence_number" if any(row.get("sequence_number") is not None for row in rows) else "event_id_ordered" if event_id_ordered else "not_required",
        "validation_status": "PASS",
        "failures": [],
    }
    if allow_separate_cost_columns:
        metadata["normalization_assumptions"].append("separate_cost_columns_are_informational_only")
    return ConnectorResult(events=events, metadata=metadata)
