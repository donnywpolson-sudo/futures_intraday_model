#!/usr/bin/env python3
"""Deterministic signal-to-position execution backtest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ContractSpec:
    market: str
    tick_size: float
    tick_value: float
    point_value: float
    commission_per_contract: float = 0.0
    slippage_ticks: float = 0.0
    max_position: int = 1


@dataclass(frozen=True)
class ExecutionConfig:
    starting_capital: float = 100_000.0
    session_flat: bool = True


def _contract_map(contracts: Mapping[str, ContractSpec] | list[ContractSpec]) -> dict[str, ContractSpec]:
    if isinstance(contracts, Mapping):
        return dict(contracts)
    return {contract.market: contract for contract in contracts}


def _normalize_inputs(signals: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "market", "signal", "execution_price"}
    missing = required - set(signals.columns)
    if missing:
        raise ValueError(f"signals missing required columns: {sorted(missing)}")
    frame = signals.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["signal"] = pd.to_numeric(frame["signal"], errors="coerce").fillna(0.0)
    frame["execution_price"] = pd.to_numeric(frame["execution_price"], errors="coerce")
    if frame["execution_price"].isna().any():
        raise ValueError("execution_price contains NaN")
    if "session_id" not in frame.columns:
        frame["session_id"] = frame["timestamp"].dt.strftime("%Y-%m-%d")
    return frame.sort_values(["market", "timestamp"]).reset_index(drop=True)


def desired_positions(
    signals: pd.DataFrame,
    contracts: Mapping[str, ContractSpec] | list[ContractSpec],
    config: ExecutionConfig = ExecutionConfig(),
) -> pd.DataFrame:
    frame = _normalize_inputs(signals)
    contract_by_market = _contract_map(contracts)
    desired: list[int] = []
    for _, row in frame.iterrows():
        market = str(row["market"])
        if market not in contract_by_market:
            raise ValueError(f"missing contract metadata for market: {market}")
        contract = contract_by_market[market]
        raw = int(np.sign(float(row["signal"])) * contract.max_position)
        desired.append(max(-contract.max_position, min(contract.max_position, raw)))
    frame["desired_position"] = desired
    if config.session_flat:
        last_in_session = frame.groupby(["market", "session_id"], dropna=False).tail(1).index
        frame.loc[last_in_session, "desired_position"] = 0
    return frame


def run_execution_backtest(
    signals: pd.DataFrame,
    contracts: Mapping[str, ContractSpec] | list[ContractSpec],
    config: ExecutionConfig = ExecutionConfig(),
) -> dict[str, object]:
    frame = desired_positions(signals, contracts, config)
    contract_by_market = _contract_map(contracts)
    fills: list[dict[str, object]] = []
    positions: list[dict[str, object]] = []
    previous_position: dict[str, int] = {}
    previous_mark: dict[str, float] = {}
    cumulative_net = 0.0
    equity_curve: list[float] = []

    for _, row in frame.iterrows():
        market = str(row["market"])
        contract = contract_by_market[market]
        timestamp = row["timestamp"]
        mark = float(row["execution_price"])
        current_position = previous_position.get(market, 0)
        prior_mark = previous_mark.get(market, mark)
        desired = int(row["desired_position"])
        order_qty = desired - current_position
        gross_pnl = current_position * (mark - prior_mark) * contract.point_value
        commission = abs(order_qty) * contract.commission_per_contract
        slippage_cost = abs(order_qty) * contract.slippage_ticks * contract.tick_value
        cost = commission + slippage_cost
        net_pnl = gross_pnl - cost
        cumulative_net += net_pnl
        equity = config.starting_capital + cumulative_net
        equity_curve.append(equity)

        if order_qty != 0:
            fill_price = mark + np.sign(order_qty) * contract.slippage_ticks * contract.tick_size
            fills.append(
                {
                    "timestamp": timestamp,
                    "market": market,
                    "session_id": row["session_id"],
                    "order_qty": int(order_qty),
                    "fill_qty": int(order_qty),
                    "fill_price": float(fill_price),
                    "desired_position": desired,
                    "position_before": current_position,
                    "position_after": desired,
                    "slippage_ticks": contract.slippage_ticks,
                    "slippage_cost_dollars": float(slippage_cost),
                    "commission_cost_dollars": float(commission),
                    "cost_dollars": float(cost),
                }
            )

        positions.append(
            {
                "timestamp": timestamp,
                "market": market,
                "session_id": row["session_id"],
                "signal": float(row["signal"]),
                "desired_position": desired,
                "position_before": current_position,
                "order_qty": int(order_qty),
                "position": desired,
                "execution_price": mark,
                "gross_pnl_dollars": float(gross_pnl),
                "slippage_cost_dollars": float(slippage_cost),
                "commission_cost_dollars": float(commission),
                "cost_dollars": float(cost),
                "net_pnl_dollars": float(net_pnl),
                "cumulative_net_pnl_dollars": float(cumulative_net),
                "equity": float(equity),
            }
        )
        previous_position[market] = desired
        previous_mark[market] = mark

    fills_frame = pd.DataFrame(fills)
    positions_frame = pd.DataFrame(positions)
    if positions_frame.empty:
        drawdown = pd.Series(dtype=float)
    else:
        drawdown = positions_frame["equity"] - positions_frame["equity"].cummax()
        positions_frame["drawdown_dollars"] = drawdown

    metrics = {
        "row_count": int(len(positions_frame)),
        "fill_count": int(len(fills_frame)),
        "gross_pnl_dollars": float(positions_frame["gross_pnl_dollars"].sum())
        if not positions_frame.empty
        else 0.0,
        "net_pnl_dollars": float(positions_frame["net_pnl_dollars"].sum())
        if not positions_frame.empty
        else 0.0,
        "slippage_cost_dollars": float(positions_frame["slippage_cost_dollars"].sum())
        if not positions_frame.empty
        else 0.0,
        "commission_cost_dollars": float(positions_frame["commission_cost_dollars"].sum())
        if not positions_frame.empty
        else 0.0,
        "max_drawdown_dollars": float(drawdown.min()) if not drawdown.empty else 0.0,
        "position_change_abs_sum": float(positions_frame["order_qty"].abs().sum())
        if not positions_frame.empty
        else 0.0,
        "ending_equity": float(positions_frame["equity"].iloc[-1])
        if not positions_frame.empty
        else config.starting_capital,
        "session_flat": config.session_flat,
        "max_abs_position": int(positions_frame["position"].abs().max())
        if not positions_frame.empty
        else 0,
    }
    return {"fills": fills_frame, "positions": positions_frame, "metrics": metrics}
