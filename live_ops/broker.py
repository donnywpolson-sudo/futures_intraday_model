"""Deterministic paper broker. There is intentionally no live order path."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import BrokerResponse, Fill, LiveBar, OrderIntent, RiskDecision, position_key, utc_datetime


class PaperBroker:
    def __init__(
        self,
        *,
        state_path: str | Path | None = None,
        fill_policy: str = "immediate_close",
        fixed_slippage_ticks: float = 0.0,
        tick_sizes: dict[str, float] | None = None,
    ) -> None:
        self.state_path = Path(state_path) if state_path is not None else None
        self.fill_policy = fill_policy
        self.fixed_slippage_ticks = fixed_slippage_ticks
        self.tick_sizes = tick_sizes or {}
        self.positions: dict[str, int] = {}
        self.open_orders: dict[str, OrderIntent] = {}
        self._accepted_order_ids: set[str] = set()
        self.fills: list[Fill] = []

    @classmethod
    def load(cls, state_path: str | Path) -> "PaperBroker":
        broker = cls(state_path=state_path)
        path = Path(state_path)
        if not path.exists():
            return broker
        payload = json.loads(path.read_text(encoding="utf-8"))
        broker.positions = {str(key): int(value) for key, value in payload.get("positions", {}).items()}
        broker._accepted_order_ids = set(payload.get("accepted_order_ids", []))
        broker.open_orders = {
            str(order_id): _order_from_payload(order_payload)
            for order_id, order_payload in payload.get("open_orders", {}).items()
        }
        broker.fills = [_fill_from_payload(fill_payload) for fill_payload in payload.get("fills", [])]
        return broker

    def save(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "positions": self.positions,
            "accepted_order_ids": sorted(self._accepted_order_ids),
            "open_orders": {
                order_id: _order_to_payload(order)
                for order_id, order in sorted(self.open_orders.items())
            },
            "fills": [_fill_to_payload(fill) for fill in self.fills],
        }
        self.state_path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")

    def place_order(
        self,
        order: OrderIntent,
        *,
        risk_decision: RiskDecision,
        bar: LiveBar,
        stale_data: bool = False,
    ) -> BrokerResponse:
        if not risk_decision.approved:
            return BrokerResponse(False, "REJECTED", "RISK_REJECTED", risk_decision.reason)
        if order.order_id in self._accepted_order_ids:
            return BrokerResponse(False, "REJECTED", "DUPLICATE_ORDER_ID", "paper broker rejected duplicate order id")
        if stale_data:
            return BrokerResponse(False, "REJECTED", "STALE_DATA", "paper broker rejected stale data")

        self._accepted_order_ids.add(order.order_id)
        if self.fill_policy == "leave_open":
            self.open_orders[order.order_id] = order
            self.save()
            return BrokerResponse(True, "OPEN", "OPEN_ORDER", "paper order left open")

        fill = self._fill(order, bar)
        self.fills.append(fill)
        key = position_key(order.symbol, order.contract)
        signed_quantity = fill.quantity if fill.side == "BUY" else -fill.quantity
        self.positions[key] = self.positions.get(key, 0) + signed_quantity
        self.save()
        return BrokerResponse(True, "FILLED", "FILLED", "paper order filled", fill)

    def cancel_all(self) -> int:
        count = len(self.open_orders)
        self.open_orders.clear()
        self.save()
        return count

    def flatten_all(
        self,
        *,
        timestamp_utc: datetime | None = None,
        prices: dict[str, float] | None = None,
    ) -> list[Fill]:
        timestamp = utc_datetime(timestamp_utc or datetime.now(timezone.utc))
        prices = prices or {}
        generated: list[Fill] = []
        for key, quantity in list(self.positions.items()):
            if quantity == 0:
                continue
            symbol, contract = key.split(":", 1)
            side = "SELL" if quantity > 0 else "BUY"
            fill = Fill(
                fill_id=f"FLATTEN-{len(self.fills) + len(generated) + 1}",
                order_id=f"FLATTEN-{key}",
                symbol=symbol,
                contract=contract,
                side=side,
                quantity=abs(quantity),
                fill_price=float(prices.get(key, 0.0)),
                timestamp_utc=timestamp,
            )
            self.positions[key] = 0
            generated.append(fill)
        self.fills.extend(generated)
        self.save()
        return generated

    def _fill(self, order: OrderIntent, bar: LiveBar) -> Fill:
        tick_size = self.tick_sizes.get(order.symbol, 0.0)
        direction = 1 if order.side.upper() == "BUY" else -1
        slippage = direction * self.fixed_slippage_ticks * tick_size
        return Fill(
            fill_id=f"FILL-{order.order_id}",
            order_id=order.order_id,
            symbol=order.symbol,
            contract=order.contract,
            side=order.side.upper(),
            quantity=order.quantity,
            fill_price=float(bar.close) + slippage,
            timestamp_utc=utc_datetime(order.created_timestamp),
            slippage=abs(slippage),
        )


class LiveBroker:
    def place_order(self, *_args: object, **_kwargs: object) -> None:
        raise NotImplementedError("live broker execution is intentionally disabled")


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be serialized as an ISO string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _order_to_payload(order: OrderIntent) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "strategy_id": order.strategy_id,
        "symbol": order.symbol,
        "contract": order.contract,
        "side": order.side,
        "quantity": order.quantity,
        "order_type": order.order_type,
        "limit_price": order.limit_price,
        "stop_price": order.stop_price,
        "time_in_force": order.time_in_force,
        "bar_timestamp": utc_datetime(order.bar_timestamp).isoformat(),
        "created_timestamp": utc_datetime(order.created_timestamp).isoformat(),
        "reason": order.reason,
        "signal_id": order.signal_id,
    }


def _order_from_payload(payload: dict[str, Any]) -> OrderIntent:
    return OrderIntent(
        order_id=str(payload["order_id"]),
        strategy_id=str(payload["strategy_id"]),
        symbol=str(payload["symbol"]),
        contract=str(payload["contract"]),
        side=str(payload["side"]),
        quantity=int(payload["quantity"]),
        order_type=str(payload["order_type"]),
        limit_price=None if payload.get("limit_price") is None else float(payload["limit_price"]),
        stop_price=None if payload.get("stop_price") is None else float(payload["stop_price"]),
        time_in_force=str(payload["time_in_force"]),
        bar_timestamp=_parse_datetime(payload["bar_timestamp"]),
        created_timestamp=_parse_datetime(payload["created_timestamp"]),
        reason=str(payload["reason"]),
        signal_id=str(payload["signal_id"]),
    )


def _fill_to_payload(fill: Fill) -> dict[str, Any]:
    return {
        "fill_id": fill.fill_id,
        "order_id": fill.order_id,
        "symbol": fill.symbol,
        "contract": fill.contract,
        "side": fill.side,
        "quantity": fill.quantity,
        "fill_price": fill.fill_price,
        "timestamp_utc": utc_datetime(fill.timestamp_utc).isoformat(),
        "commission": fill.commission,
        "slippage": fill.slippage,
    }


def _fill_from_payload(payload: dict[str, Any]) -> Fill:
    return Fill(
        fill_id=str(payload["fill_id"]),
        order_id=str(payload["order_id"]),
        symbol=str(payload["symbol"]),
        contract=str(payload["contract"]),
        side=str(payload["side"]),
        quantity=int(payload["quantity"]),
        fill_price=float(payload["fill_price"]),
        timestamp_utc=_parse_datetime(payload["timestamp_utc"]),
        commission=float(payload.get("commission", 0.0)),
        slippage=float(payload.get("slippage", 0.0)),
    )
