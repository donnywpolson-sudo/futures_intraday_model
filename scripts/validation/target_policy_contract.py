#!/usr/bin/env python3
"""Target/policy compatibility contracts for research diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isnan
from typing import Iterable


HYPOTHESIS_OPENING_RANGE_ACCEPTANCE = "opening_range_acceptance_continuation_30m_v1"
TARGET_SIGN_WITH_DEADZONE = "target_sign_with_deadzone"

PAYOFF_PATH_FAVORABLE_EXCURSION = "path_favorable_excursion"
POLICY_FIXED_HORIZON_EXIT = "fixed_horizon_exit"
POLICY_FIRST_TOUCH_PATH_CAPTURE = "first_touch_path_capture"


@dataclass(frozen=True)
class TargetPolicyContract:
    schema_version: int
    hypothesis_id: str
    target_name: str
    target_family: str
    payoff_basis: str
    entry_rule: str
    horizon_bars: int
    label_threshold: str
    cost_threshold_source: str
    required_compatible_policy: str
    compatible_policy_evaluation_basis: tuple[str, ...]
    incompatible_policy_evaluation_basis: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["compatible_policy_evaluation_basis"] = list(self.compatible_policy_evaluation_basis)
        payload["incompatible_policy_evaluation_basis"] = list(self.incompatible_policy_evaluation_basis)
        return payload


@dataclass(frozen=True)
class PolicyEvaluationContract:
    schema_version: int
    policy_name: str
    evaluation_basis: str
    entry_rule: str
    exit_rule: str
    horizon_bars: int
    captures_path_opportunity: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def opening_range_acceptance_contract() -> dict[str, object]:
    return TargetPolicyContract(
        schema_version=1,
        hypothesis_id=HYPOTHESIS_OPENING_RANGE_ACCEPTANCE,
        target_name=TARGET_SIGN_WITH_DEADZONE,
        target_family="es_opening_range_acceptance_continuation_30m",
        payoff_basis=PAYOFF_PATH_FAVORABLE_EXCURSION,
        entry_rule="next_bar_open",
        horizon_bars=30,
        label_threshold="future favorable path excursion > round_turn_cost_ticks + min_profit_ticks",
        cost_threshold_source="configs/costs.yaml ES round_turn_cost_ticks plus min_profit_ticks",
        required_compatible_policy=POLICY_FIRST_TOUCH_PATH_CAPTURE,
        compatible_policy_evaluation_basis=(POLICY_FIRST_TOUCH_PATH_CAPTURE,),
        incompatible_policy_evaluation_basis=(POLICY_FIXED_HORIZON_EXIT,),
    ).to_dict()


def fixed_horizon_exit_policy_contract() -> dict[str, object]:
    return PolicyEvaluationContract(
        schema_version=1,
        policy_name="single_target_unique_max_probability_non_overlapping_one_contract",
        evaluation_basis=POLICY_FIXED_HORIZON_EXIT,
        entry_rule="next_bar_open",
        exit_rule="fixed_30m_exit_open",
        horizon_bars=30,
        captures_path_opportunity=False,
    ).to_dict()


def first_touch_path_capture_policy_contract() -> dict[str, object]:
    return PolicyEvaluationContract(
        schema_version=1,
        policy_name="first_touch_path_capture_feasibility_grid",
        evaluation_basis=POLICY_FIRST_TOUCH_PATH_CAPTURE,
        entry_rule="next_bar_open",
        exit_rule="first_touch_take_profit_or_stop_loss_else_horizon_exit",
        horizon_bars=30,
        captures_path_opportunity=True,
    ).to_dict()


def evaluate_target_policy_compatibility(
    target_contract: dict[str, object],
    policy_contract: dict[str, object],
) -> dict[str, object]:
    policy_basis = str(policy_contract.get("evaluation_basis", ""))
    compatible_basis = {
        str(item) for item in target_contract.get("compatible_policy_evaluation_basis", [])
    }
    compatible = bool(policy_basis in compatible_basis)
    status = "COMPATIBLE_TARGET_POLICY_CONTRACT" if compatible else "INCOMPATIBLE_TARGET_POLICY_CONTRACT"
    failure = (
        ""
        if compatible
        else (
            "policy evaluation basis "
            f"{policy_basis!r} is incompatible with target payoff basis "
            f"{target_contract.get('payoff_basis')!r}; required policy basis is "
            f"{sorted(compatible_basis)}"
        )
    )
    warnings = [] if compatible else [failure]
    return {
        "status": status,
        "compatible": compatible,
        "target_payoff_basis": target_contract.get("payoff_basis"),
        "policy_evaluation_basis": policy_basis,
        "required_compatible_policy": target_contract.get("required_compatible_policy"),
        "decisive_economic_evidence_allowed": compatible,
        "economic_approval_allowed": compatible,
        "economic_rejection_allowed": compatible,
        "non_decisive_reason": "" if compatible else failure,
        "failures": [] if compatible else [failure],
        "warnings": warnings,
    }


def simulate_first_touch_outcome(
    *,
    position: int,
    entry_price: float,
    highs: Iterable[float],
    lows: Iterable[float],
    exit_price: float,
    tick_size: float,
    take_profit_ticks: float,
    stop_loss_ticks: float,
    same_bar_policy: str = "ambiguous",
) -> dict[str, object]:
    if position not in (-1, 1):
        raise ValueError("position must be -1 or 1")
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    if take_profit_ticks <= 0 or stop_loss_ticks <= 0:
        raise ValueError("take_profit_ticks and stop_loss_ticks must be positive")

    high_values = [float(value) for value in highs]
    low_values = [float(value) for value in lows]
    if len(high_values) != len(low_values):
        raise ValueError("highs and lows must have the same length")

    if position == 1:
        take_profit_price = entry_price + take_profit_ticks * tick_size
        stop_loss_price = entry_price - stop_loss_ticks * tick_size
    else:
        take_profit_price = entry_price - take_profit_ticks * tick_size
        stop_loss_price = entry_price + stop_loss_ticks * tick_size

    for index, (high, low) in enumerate(zip(high_values, low_values)):
        if isnan(high) or isnan(low):
            raise ValueError("highs and lows must be finite")
        if position == 1:
            take_profit_hit = high >= take_profit_price
            stop_loss_hit = low <= stop_loss_price
        else:
            take_profit_hit = low <= take_profit_price
            stop_loss_hit = high >= stop_loss_price

        if take_profit_hit and stop_loss_hit:
            if same_bar_policy == "stop_first":
                return {
                    "outcome": "stop_loss",
                    "bar_index": index,
                    "gross_ticks": -float(stop_loss_ticks),
                    "ambiguous_first_touch": True,
                }
            if same_bar_policy != "ambiguous":
                raise ValueError("same_bar_policy must be 'ambiguous' or 'stop_first'")
            return {
                "outcome": "both_same_bar_ambiguous",
                "bar_index": index,
                "gross_ticks": None,
                "ambiguous_first_touch": True,
            }
        if take_profit_hit:
            return {
                "outcome": "take_profit",
                "bar_index": index,
                "gross_ticks": float(take_profit_ticks),
                "ambiguous_first_touch": False,
            }
        if stop_loss_hit:
            return {
                "outcome": "stop_loss",
                "bar_index": index,
                "gross_ticks": -float(stop_loss_ticks),
                "ambiguous_first_touch": False,
            }

    fixed_exit_ticks = position * (float(exit_price) - float(entry_price)) / float(tick_size)
    return {
        "outcome": "horizon_exit",
        "bar_index": None,
        "gross_ticks": float(fixed_exit_ticks),
        "ambiguous_first_touch": False,
    }
