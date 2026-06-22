"""Paper position and order reconciliation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .broker import PaperBroker
from .schemas import ReconciliationResult, utc_datetime


class Reconciler:
    def __init__(self, *, stale_order_seconds: float = 300.0) -> None:
        self.stale_order_seconds = stale_order_seconds

    def reconcile(
        self,
        *,
        strategy_positions: dict[str, int],
        broker: PaperBroker,
        strategy_open_orders: Iterable[str] | None = None,
        now: datetime | None = None,
    ) -> ReconciliationResult:
        broker_positions = {key: value for key, value in broker.positions.items() if value != 0}
        strategy_clean = {key: value for key, value in strategy_positions.items() if value != 0}
        broker_open_orders = set(broker.open_orders)
        details: dict[str, object] = {
            "strategy_positions": strategy_clean,
            "broker_positions": broker_positions,
            "open_orders": sorted(broker_open_orders),
        }
        if strategy_clean != broker_positions:
            return ReconciliationResult("FAIL", "POSITION_MISMATCH", details)
        if strategy_open_orders is not None:
            strategy_open = {str(order_id) for order_id in strategy_open_orders}
            details["strategy_open_orders"] = sorted(strategy_open)
            if strategy_open != broker_open_orders:
                return ReconciliationResult("FAIL", "OPEN_ORDER_MISMATCH", details)

        fill_ids = [fill.fill_id for fill in broker.fills]
        if len(fill_ids) != len(set(fill_ids)):
            return ReconciliationResult("FAIL", "DUPLICATE_FILL", details)

        timestamp = utc_datetime(now or datetime.now(timezone.utc))
        stale_orders = []
        for order_id, order in broker.open_orders.items():
            age = (timestamp - utc_datetime(order.created_timestamp)).total_seconds()
            if age > self.stale_order_seconds:
                stale_orders.append(order_id)
        if stale_orders:
            details["stale_open_orders"] = stale_orders
            return ReconciliationResult("OK", "STALE_OPEN_ORDER", details)

        return ReconciliationResult("OK", "OK", details)
