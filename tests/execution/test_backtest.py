from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.execution.backtest import ContractSpec, ExecutionConfig, run_execution_backtest


def _contract(**overrides: float | int) -> ContractSpec:
    values = {
        "market": "ES",
        "tick_size": 0.25,
        "tick_value": 12.5,
        "point_value": 50.0,
        "commission_per_contract": 0.0,
        "slippage_ticks": 0.0,
        "max_position": 1,
    }
    values.update(overrides)
    return ContractSpec(**values)


def _signals(prices: list[float], signals: list[int], sessions: list[str] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-02T14:30:00Z", periods=len(prices), freq="15min"),
            "market": "ES",
            "session_id": sessions or ["s1"] * len(prices),
            "signal": signals,
            "execution_price": prices,
        }
    )


def test_long_trade_tick_pnl_and_flatten() -> None:
    result = run_execution_backtest(
        _signals([100.0, 101.0, 101.0], [1, 1, 0]),
        [_contract()],
        ExecutionConfig(session_flat=False),
    )

    assert result["metrics"]["net_pnl_dollars"] == 50.0
    assert result["positions"].iloc[-1]["position"] == 0
    assert result["fills"]["order_qty"].tolist() == [1, -1]


def test_short_trade_pnl() -> None:
    result = run_execution_backtest(
        _signals([100.0, 99.0, 99.0], [-1, -1, 0]),
        [_contract()],
        ExecutionConfig(session_flat=False),
    )

    assert result["metrics"]["net_pnl_dollars"] == 50.0
    assert result["fills"]["order_qty"].tolist() == [-1, 1]


def test_flip_generates_two_contract_order() -> None:
    result = run_execution_backtest(
        _signals([100.0, 100.5], [1, -1]),
        [_contract()],
        ExecutionConfig(session_flat=False),
    )

    assert result["fills"]["order_qty"].tolist() == [1, -2]
    assert result["positions"].iloc[-1]["position"] == -1
    assert result["metrics"]["position_change_abs_sum"] == 3.0


def test_slipped_fill_and_commission_costs() -> None:
    result = run_execution_backtest(
        _signals([100.0, 100.0], [1, 0]),
        [_contract(slippage_ticks=1.0, commission_per_contract=2.0)],
        ExecutionConfig(session_flat=False),
    )

    fills = result["fills"]
    assert fills.iloc[0]["fill_price"] == 100.25
    assert fills.iloc[0]["slippage_cost_dollars"] == 12.5
    assert result["metrics"]["slippage_cost_dollars"] == 25.0
    assert result["metrics"]["commission_cost_dollars"] == 4.0
    assert result["metrics"]["net_pnl_dollars"] == -29.0


def test_session_flat_prevents_overnight_hold() -> None:
    result = run_execution_backtest(
        _signals(
            [100.0, 100.5, 101.0, 101.5],
            [1, 1, 1, 1],
            sessions=["s1", "s1", "s2", "s2"],
        ),
        [_contract()],
        ExecutionConfig(session_flat=True),
    )

    positions = result["positions"]
    assert positions.loc[positions["session_id"].eq("s1")].iloc[-1]["position"] == 0
    assert positions.loc[positions["session_id"].eq("s2")].iloc[-1]["position"] == 0


def test_drawdown_diagnostics() -> None:
    result = run_execution_backtest(
        _signals([100.0, 99.0, 101.0, 101.0], [1, 1, 1, 0]),
        [_contract()],
        ExecutionConfig(session_flat=False),
    )

    assert result["metrics"]["max_drawdown_dollars"] == -50.0
    assert result["metrics"]["ending_equity"] == 100_050.0
