from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.phase8_model_selection.analyze_trade_tick_excursions import (
    CostConfig,
    build_tp_sl_grid,
    build_trade_excursion_frame,
    load_cost_config,
)


def _costs() -> CostConfig:
    return CostConfig(
        market="ES",
        tick_size=0.25,
        tick_value=12.5,
        round_turn_cost_dollars=10.0,
    )


def _bars() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=12, freq="min")
    rows = []
    for idx, ts in enumerate(timestamps):
        open_price = 100.0
        rows.append(
            {
                "ts": ts,
                "market": "ES",
                "year": 2024,
                "open": open_price,
                "high": open_price,
                "low": open_price,
            }
        )

    # Long trade path: entry at 14:31, exit at 14:34.
    rows[1].update({"open": 100.0, "high": 101.0, "low": 99.5})
    rows[2].update({"open": 100.5, "high": 102.0, "low": 99.0})
    rows[3].update({"open": 101.0, "high": 101.5, "low": 99.75})
    rows[4].update({"open": 101.0, "high": 150.0, "low": 50.0})

    # Short trade path: entry at 14:36, exit at 14:39.
    rows[6].update({"open": 100.0, "high": 100.75, "low": 99.25})
    rows[7].update({"open": 99.75, "high": 101.0, "low": 98.5})
    rows[8].update({"open": 99.5, "high": 100.25, "low": 99.0})
    rows[9].update({"open": 99.5, "high": 150.0, "low": 50.0})
    return pd.DataFrame(rows)


def _trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "market": "ES",
                "year": 2024,
                "fold_id": "ES_research_0001",
                "timestamp": pd.Timestamp("2024-01-02T14:30:00Z"),
                "target_entry_ts": pd.Timestamp("2024-01-02T14:31:00Z"),
                "target_exit_ts": pd.Timestamp("2024-01-02T14:34:00Z"),
                "position": 1,
                "execution_open": 100.0,
                "execution_close": 101.0,
                "gross_dollars": 50.0,
                "cost_dollars": 10.0,
                "net_dollars": 40.0,
            },
            {
                "market": "ES",
                "year": 2024,
                "fold_id": "ES_research_0001",
                "timestamp": pd.Timestamp("2024-01-02T14:35:00Z"),
                "target_entry_ts": pd.Timestamp("2024-01-02T14:36:00Z"),
                "target_exit_ts": pd.Timestamp("2024-01-02T14:39:00Z"),
                "position": -1,
                "execution_open": 100.0,
                "execution_close": 99.5,
                "gross_dollars": 25.0,
                "cost_dollars": 10.0,
                "net_dollars": 15.0,
            },
        ]
    )


def test_trade_excursion_tick_math_is_position_adjusted() -> None:
    result = build_trade_excursion_frame(_trades(), _bars(), _costs())

    assert result["realized_gross_ticks"].tolist() == pytest.approx([4.0, 2.0])
    assert result["current_cost_ticks"].tolist() == pytest.approx([0.8, 0.8])
    assert result["current_cost_net_ticks"].tolist() == pytest.approx([3.2, 1.2])
    assert result["favorable_excursion_ticks"].tolist() == pytest.approx([8.0, 6.0])
    assert result["adverse_excursion_ticks"].tolist() == pytest.approx([4.0, 4.0])
    assert result["path_bar_count"].tolist() == [3, 3]


def test_tp_sl_grid_marks_both_touched_as_ambiguous() -> None:
    result = build_trade_excursion_frame(_trades(), _bars(), _costs())
    grid = build_tp_sl_grid(result, thresholds=(4,))

    row = grid.iloc[0]
    assert row["tp_ticks"] == 4
    assert row["sl_ticks"] == 4
    assert row["tp_only"] == 0
    assert row["sl_only"] == 0
    assert row["both_touched_ambiguous"] == 2
    assert row["neither"] == 0


def test_missing_entry_join_fails_closed() -> None:
    bars = _bars()
    bars = bars[bars["ts"].ne(pd.Timestamp("2024-01-02T14:31:00Z"))]

    with pytest.raises(ValueError, match="missing entry bar"):
        build_trade_excursion_frame(_trades(), bars, _costs())


def test_load_cost_config_reads_es_ticks(tmp_path: Path) -> None:
    costs_path = tmp_path / "costs.yaml"
    costs_path.write_text(
        """
markets:
  ES:
    tick_size: 0.25
    tick_value: 12.5
    round_turn_cost_dollars: 29.5
""".strip(),
        encoding="utf-8",
    )

    costs = load_cost_config(costs_path)

    assert costs.tick_size == 0.25
    assert costs.tick_value == 12.5
    assert costs.round_turn_cost_ticks == pytest.approx(2.36)
