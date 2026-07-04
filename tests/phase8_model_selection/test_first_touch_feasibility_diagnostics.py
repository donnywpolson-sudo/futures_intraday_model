from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.phase8_model_selection.analyze_trade_tick_excursions import CostConfig
from scripts.phase8_model_selection.first_touch_feasibility_diagnostics import (
    RUN_ID,
    TradePath,
    build_grid_summary,
    build_trade_paths,
    decision_support,
    evaluate_first_touch_feasibility,
    output_paths,
)


def _costs() -> CostConfig:
    return CostConfig(
        market="ES",
        tick_size=0.25,
        tick_value=12.5,
        round_turn_cost_dollars=10.0,
    )


def _path(
    *,
    position: int,
    highs: tuple[float, ...],
    lows: tuple[float, ...],
    exit_price: float = 100.0,
) -> TradePath:
    return TradePath(
        market="ES",
        year=2024,
        fold_id="ES_research_0001",
        timestamp=pd.Timestamp("2024-01-02T14:30:00Z"),
        month="2024-01",
        position=position,
        entry_price=100.0,
        exit_price=exit_price,
        cost_dollars=10.0,
        highs=highs,
        lows=lows,
    )


def _bars() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=4, freq="min")
    return pd.DataFrame(
        [
            {"ts": timestamps[0], "market": "ES", "year": 2024, "open": 100.0, "high": 100.0, "low": 100.0},
            {"ts": timestamps[1], "market": "ES", "year": 2024, "open": 100.0, "high": 100.5, "low": 99.75},
            {"ts": timestamps[2], "market": "ES", "year": 2024, "open": 100.25, "high": 101.0, "low": 99.5},
            {"ts": timestamps[3], "market": "ES", "year": 2024, "open": 100.5, "high": 100.5, "low": 100.5},
        ]
    )


def _trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "market": "ES",
                "year": 2024,
                "fold_id": "ES_research_0001",
                "timestamp": pd.Timestamp("2024-01-02T14:30:00Z"),
                "target_entry_ts": pd.Timestamp("2024-01-02T14:31:00Z"),
                "target_exit_ts": pd.Timestamp("2024-01-02T14:33:00Z"),
                "position": 1,
                "execution_open": 100.0,
                "execution_close": 100.5,
                "cost_dollars": 10.0,
            }
        ]
    )


def test_first_touch_grid_covers_tp_sl_neither_ambiguous_and_stop_first() -> None:
    paths = [
        _path(position=1, highs=(101.0,), lows=(100.0,)),
        _path(position=-1, highs=(100.0,), lows=(99.0,)),
        _path(position=1, highs=(100.0,), lows=(99.0,)),
        _path(position=1, highs=(100.5,), lows=(99.75,), exit_price=100.5),
        _path(position=1, highs=(101.0,), lows=(99.0,)),
    ]

    summary = build_grid_summary(paths, _costs(), grid=(4,))
    row = summary.loc[summary["scope_type"].eq("overall")].iloc[0]

    assert row["trade_count"] == 5
    assert row["take_profit_count"] == 2
    assert row["stop_loss_count"] == 1
    assert row["horizon_exit_count"] == 1
    assert row["same_bar_ambiguous_count"] == 1
    assert row["stop_first_take_profit_count"] == 2
    assert row["stop_first_stop_loss_count"] == 2
    assert row["stop_first_horizon_exit_count"] == 1
    assert row["stop_first_gross_ticks"] == pytest.approx(2.0)
    assert row["stop_first_net_dollars"] == pytest.approx(-25.0)
    assert row["ambiguous_excluded_trade_count"] == 4
    assert row["ambiguous_excluded_net_dollars"] == pytest.approx(35.0)


def test_decision_support_marks_single_negative_grid_no_go() -> None:
    paths = [
        _path(position=1, highs=(101.0,), lows=(99.0,)),
        _path(position=1, highs=(100.0,), lows=(99.0,)),
    ]
    summary = build_grid_summary(paths, _costs(), grid=(4,))

    result = decision_support(summary, (4,))

    assert result["screen_status"] == "FIRST_TOUCH_FEASIBILITY_NO_GO"
    assert result["stop_first_positive_overall_grid_count"] == 0


def test_build_trade_paths_fails_closed_on_missing_path_rows() -> None:
    bars = _bars()
    bars = bars[bars["ts"].ne(pd.Timestamp("2024-01-02T14:32:00Z"))]

    with pytest.raises(ValueError, match="missing OHLC path rows"):
        build_trade_paths(_trades(), bars, _costs())


def test_build_trade_paths_fails_closed_on_duplicate_bar_keys() -> None:
    bars = pd.concat([_bars(), _bars().iloc[[1]]], ignore_index=True)

    with pytest.raises(ValueError, match="bars contain duplicate join keys"):
        build_trade_paths(_trades(), bars, _costs())


def test_build_trade_paths_fails_closed_on_stale_outputs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    paths = output_paths(reports_root, RUN_ID)
    paths["diagnostics"].parent.mkdir(parents=True)
    paths["diagnostics"].write_text("stale", encoding="utf-8")

    with pytest.raises(ValueError, match="stale output path exists"):
        evaluate_first_touch_feasibility(
            predictions_path=tmp_path / "missing_predictions.parquet",
            trades_path=tmp_path / "missing_trades.csv",
            bars_path=tmp_path / "missing_bars.parquet",
            costs_config=tmp_path / "missing_costs.yaml",
            reports_root=reports_root,
            run=RUN_ID,
            grid=(4,),
        )
