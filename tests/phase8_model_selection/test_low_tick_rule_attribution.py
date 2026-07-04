from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.phase8_model_selection.analyze_low_tick_rule_attribution import (
    TARGET_ACCEPTANCE_DISTANCE,
    TARGET_ADVERSE,
    TARGET_DIRECTION,
    TARGET_FAVORABLE,
    TARGET_THRESHOLD,
    TARGET_VALID,
    build_policy_frame,
    confidence_decile_summary,
    join_executed_context,
    summarize_policy_stages,
    target_match_summary,
)
from scripts.phase8_model_selection.analyze_trade_tick_excursions import CostConfig


def _costs() -> CostConfig:
    return CostConfig(
        market="ES",
        tick_size=0.25,
        tick_value=12.5,
        round_turn_cost_dollars=10.0,
    )


def _write_costs(path: Path) -> Path:
    path.write_text(
        """
markets:
  ES:
    tick_size: 0.25
    tick_value: 12.5
    point_value: 50.0
    slippage_ticks_per_side: 0.0
    round_turn_cost_dollars: 10.0
""".strip(),
        encoding="utf-8",
    )
    return path


def _predictions() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=5, freq="min")
    rows = [
        # Executed long, target-direction match, +4 fixed-exit ticks.
        (timestamps[0], 0.70, 0.20, 0.10, 1, 100.0, 101.0),
        # Candidate long, overlap-blocked, +8 fixed-exit ticks.
        (timestamps[1], 0.80, 0.10, 0.10, 1, 100.0, 102.0),
        # Executed short, target-direction mismatch, -4 fixed-exit ticks.
        (timestamps[4], 0.10, 0.75, 0.15, 1, 100.0, 101.0),
        # Flat selected by p_flat.
        (timestamps[3], 0.20, 0.25, 0.55, 0, 100.0, 100.0),
    ]
    out: list[dict[str, object]] = []
    for idx, (timestamp, p_long, p_short, p_flat, y_true, entry, exit_) in enumerate(rows):
        out.append(
            {
                "market": "ES",
                "year": 2024,
                "fold_id": "fold_1",
                "timestamp": timestamp,
                "p_long": p_long,
                "p_short": p_short,
                "p_flat": p_flat,
                "y_true": y_true,
                "execution_open": entry,
                "execution_close": exit_,
                "target_entry_ts": timestamp + pd.Timedelta(minutes=1),
                "target_exit_ts": timestamp + pd.Timedelta(minutes=3),
            }
        )
    return pd.DataFrame(out)


def _excursion_frame(policy_frame: pd.DataFrame) -> pd.DataFrame:
    executed = policy_frame.loc[policy_frame["position"].ne(0)].copy()
    executed["realized_gross_ticks"] = executed["executed_fixed_exit_ticks"]
    executed["current_cost_net_ticks"] = executed["executed_net_ticks"]
    executed["favorable_excursion_ticks"] = [8.0, 6.0]
    executed["adverse_excursion_ticks"] = [2.0, 5.0]
    return executed[
        [
            "market",
            "year",
            "fold_id",
            "timestamp",
            "target_entry_ts",
            "target_exit_ts",
            "position",
            "realized_gross_ticks",
            "current_cost_net_ticks",
            "favorable_excursion_ticks",
            "adverse_excursion_ticks",
        ]
    ]


def _target_context() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=5, freq="min")
    return pd.DataFrame(
        {
            "market": ["ES"] * 5,
            "year": [2024] * 5,
            "timestamp": timestamps,
            TARGET_VALID: [True] * 5,
            TARGET_DIRECTION: [1, 1, 0, 0, 1],
            TARGET_THRESHOLD: [4.36] * 5,
            TARGET_ACCEPTANCE_DISTANCE: [2.0, 3.0, 0.0, 0.0, 8.0],
            TARGET_FAVORABLE: [8.0, 8.0, 0.0, 0.0, 6.0],
            TARGET_ADVERSE: [2.0, 1.0, 0.0, 0.0, 5.0],
        }
    )


def test_path_label_match_vs_fixed_exit_attribution(tmp_path: Path) -> None:
    policy = build_policy_frame(_predictions(), _write_costs(tmp_path / "costs.yaml"), _costs())
    joined = join_executed_context(policy, _excursion_frame(policy), _target_context())
    summary = target_match_summary(joined)

    match = summary.loc[summary["target_direction_match"].eq(True)].iloc[0]
    mismatch = summary.loc[summary["target_direction_match"].eq(False)].iloc[0]
    assert match["mean_realized_ticks"] == pytest.approx(4.0)
    assert mismatch["mean_realized_ticks"] == pytest.approx(-4.0)
    assert joined["giveback_ticks"].tolist() == pytest.approx([4.0, 10.0])


def test_candidate_executed_blocked_stage_summary(tmp_path: Path) -> None:
    policy = build_policy_frame(_predictions(), _write_costs(tmp_path / "costs.yaml"), _costs())
    summary = summarize_policy_stages(policy).set_index("stage")

    assert summary.loc["candidate_pre_nonoverlap", "row_count"] == 3
    assert summary.loc["executed_after_nonoverlap", "row_count"] == 2
    assert summary.loc["blocked_by_nonoverlap", "row_count"] == 1
    assert summary.loc["executed_after_nonoverlap", "median_ticks"] == pytest.approx(0.0)


def test_confidence_decile_summary_keeps_candidate_edge_shape(tmp_path: Path) -> None:
    policy = build_policy_frame(_predictions(), _write_costs(tmp_path / "costs.yaml"), _costs())
    summary = confidence_decile_summary(policy, bins=3)

    assert int(summary["row_count"].sum()) == 3
    assert int(summary["executed_count"].sum()) == 2
    assert set(summary.columns).issuperset({"confidence_decile", "mean_ticks", "median_ticks"})


def test_missing_target_context_join_fails_closed(tmp_path: Path) -> None:
    policy = build_policy_frame(_predictions(), _write_costs(tmp_path / "costs.yaml"), _costs())
    context = _target_context()
    context = context[context["timestamp"].ne(pd.Timestamp("2024-01-02T14:30:00Z"))]

    with pytest.raises(ValueError, match="missing target context join"):
        join_executed_context(policy, _excursion_frame(policy), context)


def test_missing_probability_columns_fail_closed(tmp_path: Path) -> None:
    predictions = _predictions().drop(columns=["p_short"])

    with pytest.raises(ValueError, match="missing required columns"):
        build_policy_frame(predictions, _write_costs(tmp_path / "costs.yaml"), _costs())
