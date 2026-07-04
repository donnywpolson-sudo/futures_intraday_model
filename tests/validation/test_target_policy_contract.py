from __future__ import annotations

import pytest

from scripts.validation import run_opening_range_acceptance_wfa_materialization as materialization
from scripts.validation.target_policy_contract import (
    PAYOFF_PATH_FAVORABLE_EXCURSION,
    POLICY_FIRST_TOUCH_PATH_CAPTURE,
    POLICY_FIXED_HORIZON_EXIT,
    evaluate_target_policy_compatibility,
    first_touch_path_capture_policy_contract,
    fixed_horizon_exit_policy_contract,
    opening_range_acceptance_contract,
    simulate_first_touch_outcome,
)


def test_opening_range_contract_metadata_is_explicit() -> None:
    contract = opening_range_acceptance_contract()

    assert contract["payoff_basis"] == PAYOFF_PATH_FAVORABLE_EXCURSION
    assert contract["entry_rule"] == "next_bar_open"
    assert contract["horizon_bars"] == 30
    assert contract["required_compatible_policy"] == POLICY_FIRST_TOUCH_PATH_CAPTURE
    assert POLICY_FIXED_HORIZON_EXIT in contract["incompatible_policy_evaluation_basis"]


def test_materialization_path_exposes_target_policy_contract() -> None:
    contract = materialization.target_policy_contract_payload()

    assert contract == opening_range_acceptance_contract()


def test_fixed_exit_policy_is_incompatible_with_path_opportunity_target() -> None:
    result = evaluate_target_policy_compatibility(
        opening_range_acceptance_contract(),
        fixed_horizon_exit_policy_contract(),
    )

    assert result["compatible"] is False
    assert result["decisive_economic_evidence_allowed"] is False
    assert result["economic_rejection_allowed"] is False
    assert result["status"] == "INCOMPATIBLE_TARGET_POLICY_CONTRACT"
    assert "fixed_horizon_exit" in result["failures"][0]


def test_first_touch_policy_is_compatible_with_path_opportunity_target() -> None:
    result = evaluate_target_policy_compatibility(
        opening_range_acceptance_contract(),
        first_touch_path_capture_policy_contract(),
    )

    assert result["compatible"] is True
    assert result["decisive_economic_evidence_allowed"] is True
    assert result["economic_approval_allowed"] is True
    assert result["failures"] == []


def test_first_touch_outcomes_cover_tp_sl_neither_and_ambiguous() -> None:
    tp = simulate_first_touch_outcome(
        position=1,
        entry_price=100.0,
        highs=[100.25, 101.0],
        lows=[99.75, 100.5],
        exit_price=100.5,
        tick_size=0.25,
        take_profit_ticks=4,
        stop_loss_ticks=4,
    )
    sl = simulate_first_touch_outcome(
        position=-1,
        entry_price=100.0,
        highs=[100.25, 101.0],
        lows=[99.75, 99.5],
        exit_price=99.5,
        tick_size=0.25,
        take_profit_ticks=4,
        stop_loss_ticks=4,
    )
    neither = simulate_first_touch_outcome(
        position=1,
        entry_price=100.0,
        highs=[100.25, 100.5],
        lows=[99.75, 99.5],
        exit_price=100.5,
        tick_size=0.25,
        take_profit_ticks=4,
        stop_loss_ticks=4,
    )
    ambiguous = simulate_first_touch_outcome(
        position=1,
        entry_price=100.0,
        highs=[101.0],
        lows=[99.0],
        exit_price=100.0,
        tick_size=0.25,
        take_profit_ticks=4,
        stop_loss_ticks=4,
    )

    assert tp["outcome"] == "take_profit"
    assert tp["gross_ticks"] == pytest.approx(4.0)
    assert sl["outcome"] == "stop_loss"
    assert sl["gross_ticks"] == pytest.approx(-4.0)
    assert neither["outcome"] == "horizon_exit"
    assert neither["gross_ticks"] == pytest.approx(2.0)
    assert ambiguous["outcome"] == "both_same_bar_ambiguous"
    assert ambiguous["ambiguous_first_touch"] is True
