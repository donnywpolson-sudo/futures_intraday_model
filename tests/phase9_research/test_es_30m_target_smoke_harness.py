from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.es_30m_target_smoke_harness import (
    EVALUATION_COMPONENT_RANK,
    TARGET_SPECS,
    apply_opening_range_acceptance_continuation_30m_target,
    apply_opportunity_risk_component_rank_30m_target,
    apply_opportunity_risk_asymmetry_30m_target,
    apply_prior_extreme_failure_30m_target,
    apply_triple_barrier_30m_target,
    apply_vol_scaled_terminal_30m_target,
    apply_vwap_reversion_30m_target,
    class_balance,
    duplicate_target_overlap,
    evaluate_stage_gates,
    non_overlapping_events,
    stage_summary,
    target_distribution_summary,
    validate_target_hypothesis_registered,
    validate_target_trial_status_registered,
)


def _cost_config() -> dict[str, float]:
    return {
        "tick_size": 0.25,
        "tick_value": 12.5,
        "round_turn_cost_dollars": 25.0,
        "min_profit_ticks": 2.0,
        "cost_ticks": 2.0,
    }


def _frame(*, periods: int = 120) -> pd.DataFrame:
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    open_ = [100.0] * periods
    for idx in range(52, min(periods, 82)):
        open_[idx] = 102.0
    for idx in range(90, periods):
        open_[idx] = 98.0
    high = [value + 0.25 for value in open_]
    low = [value - 0.25 for value in open_]
    if periods > 26:
        high[26] = 101.25
    if periods > 41:
        low[41] = 98.75
    return pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_segment_id": "ES_2024_01_02",
            "open": open_,
            "high": high,
            "low": low,
            "close": open_,
            "volume": 100,
            "causal_valid": True,
            "valid_ohlcv": True,
            "inside_session": True,
            "feature_input_valid": True,
            "feature_row_valid": True,
            "training_row_valid": True,
            "target_valid": True,
            "target_sign_with_deadzone": [1 if idx % 3 == 0 else 0 for idx in range(periods)],
            "is_synthetic": False,
            "roll_window_flag": False,
            "boundary_session_flag": False,
            "feature_signal": range(periods),
        }
    )


def _prior_extreme_frame() -> pd.DataFrame:
    first_session_periods = 80
    second_session_periods = 140
    periods = first_session_periods + second_session_periods
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    session = ["ES_2024_01_02"] * first_session_periods + ["ES_2024_01_03"] * second_session_periods
    open_ = [100.0] * periods
    close = [100.0] * periods
    high = [100.25] * periods
    low = [99.75] * periods
    for idx in range(first_session_periods):
        high[idx] = 105.0
        low[idx] = 95.0

    high_failure_idx = first_session_periods + 30
    high[high_failure_idx] = 105.25
    open_[high_failure_idx + 31] = 98.0
    close[high_failure_idx + 31] = 98.0
    high[high_failure_idx + 31] = 98.25
    low[high_failure_idx + 31] = 97.75

    low_failure_idx = first_session_periods + 80
    low[low_failure_idx] = 94.75
    open_[low_failure_idx + 31] = 108.0
    close[low_failure_idx + 31] = 108.0
    high[low_failure_idx + 31] = 108.25
    low[low_failure_idx + 31] = 107.75

    return pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_segment_id": session,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100,
            "causal_valid": True,
            "valid_ohlcv": True,
            "inside_session": True,
            "feature_input_valid": True,
            "feature_row_valid": True,
            "training_row_valid": True,
            "target_valid": True,
            "target_sign_with_deadzone": [1 if idx % 3 == 0 else 0 for idx in range(periods)],
            "is_synthetic": False,
            "roll_window_flag": False,
            "boundary_session_flag": False,
            "feature_signal": range(periods),
        }
    )


def _vwap_reversion_frame() -> pd.DataFrame:
    periods = 150
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    open_ = [100.0] * periods
    high = [100.25] * periods
    low = [99.75] * periods
    close = [100.0] * periods
    volume = [100.0] * periods

    above_stretch_idx = 30
    close[above_stretch_idx] = 102.0
    high[above_stretch_idx] = 102.25
    low[above_stretch_idx] = 101.75
    open_[above_stretch_idx + 31] = 98.0
    close[above_stretch_idx + 31] = 98.0
    high[above_stretch_idx + 31] = 98.25
    low[above_stretch_idx + 31] = 97.75

    below_stretch_idx = 90
    close[below_stretch_idx] = 92.0
    high[below_stretch_idx] = 92.25
    low[below_stretch_idx] = 91.75
    open_[below_stretch_idx + 31] = 108.0
    close[below_stretch_idx + 31] = 108.0
    high[below_stretch_idx + 31] = 108.25
    low[below_stretch_idx + 31] = 107.75

    return pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_segment_id": "ES_2024_01_02",
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "causal_valid": True,
            "valid_ohlcv": True,
            "inside_session": True,
            "feature_input_valid": True,
            "feature_row_valid": True,
            "training_row_valid": True,
            "target_valid": True,
            "target_sign_with_deadzone": [1 if idx % 3 == 0 else 0 for idx in range(periods)],
            "is_synthetic": False,
            "roll_window_flag": False,
            "boundary_session_flag": False,
            "feature_signal": range(periods),
        }
    )


def _opportunity_risk_frame() -> pd.DataFrame:
    periods = 140
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    open_ = [100.0] * periods
    high = [100.25] * periods
    low = [99.75] * periods
    close = [100.0] * periods

    long_idx = 10
    high[long_idx + 10] = 103.0

    short_idx = 60
    low[short_idx + 10] = 97.0

    return pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_segment_id": "ES_2024_01_02",
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100,
            "causal_valid": True,
            "valid_ohlcv": True,
            "inside_session": True,
            "feature_input_valid": True,
            "feature_row_valid": True,
            "training_row_valid": True,
            "target_valid": True,
            "target_sign_with_deadzone": [1 if idx % 3 == 0 else 0 for idx in range(periods)],
            "is_synthetic": False,
            "roll_window_flag": False,
            "boundary_session_flag": False,
            "feature_signal": range(periods),
        }
    )


def _opening_range_frame(*, periods: int = 160, overlapping_long_rows: bool = False) -> pd.DataFrame:
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    open_ = [100.0] * periods
    high = [100.25] * periods
    low = [99.75] * periods
    close = [100.0] * periods
    for idx in range(min(30, periods)):
        high[idx] = 101.0
        low[idx] = 99.0

    long_rows = range(30, min(45, periods)) if overlapping_long_rows else [30]
    for idx in long_rows:
        open_[idx] = 102.0
        high[idx] = 102.25
        low[idx] = 101.75
        close[idx] = 102.0
    if periods > 31:
        open_[31] = 102.0
    if periods > 40:
        high[40] = 103.25

    short_idx = 70
    if periods > short_idx:
        open_[short_idx] = 98.0
        high[short_idx] = 98.25
        low[short_idx] = 97.75
        close[short_idx] = 98.0
    if periods > short_idx + 1:
        open_[short_idx + 1] = 98.0
    if periods > short_idx + 10:
        low[short_idx + 10] = 96.75

    flat_idx = 110
    if periods > flat_idx:
        open_[flat_idx] = 102.0
        high[flat_idx] = 102.25
        low[flat_idx] = 101.75
        close[flat_idx] = 102.0
    if periods > flat_idx + 1:
        open_[flat_idx + 1] = 102.0
    if periods > flat_idx + 10:
        high[flat_idx + 10] = 102.25

    return pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_segment_id": "ES_2024_01_02",
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100,
            "causal_valid": True,
            "valid_ohlcv": True,
            "inside_session": True,
            "feature_input_valid": True,
            "feature_row_valid": True,
            "training_row_valid": True,
            "target_valid": True,
            "target_sign_with_deadzone": [1 if idx % 3 == 0 else 0 for idx in range(periods)],
            "is_synthetic": False,
            "roll_window_flag": False,
            "boundary_session_flag": False,
            "feature_signal": range(periods),
        }
    )


def _registry(path: Path, hypothesis_id: str, *, status: str = "CANDIDATE") -> Path:
    spec = TARGET_SPECS[hypothesis_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "hypotheses": [
                    {
                        "target_hypothesis_id": spec.hypothesis_id,
                        "status": status,
                        "wfa_allowed": False,
                        "target_family": spec.target_family,
                        "scope": {
                            "profile": "tier_1",
                            "resolved_profile": "tier_1_research",
                            "markets": ["ES"],
                            "years": [2023, 2024],
                        },
                        "description": "fixture",
                        "status_reason": "fixture",
                        "source_reports": [],
                        "next_allowed_actions": ["RUN_ES_30M_DISCOVERY_SMOKE"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _trial_statuses(
    path: Path,
    hypothesis_id: str,
    *,
    status: str = "CANDIDATE",
    stage: str = "register_candidate",
    evidence: list[str] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "trial_id": f"{hypothesis_id}_candidate",
                "hypothesis_id": hypothesis_id,
                "status": status,
                "stage": stage,
                "evidence": [] if evidence is None else evidence,
                "notes": "fixture",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_registry_requires_candidate_status_and_es_scope(tmp_path: Path) -> None:
    spec = TARGET_SPECS["vol_scaled_terminal_30m_v1"]
    candidate = _registry(tmp_path / "candidate.json", spec.hypothesis_id)
    rejected = _registry(tmp_path / "rejected.json", spec.hypothesis_id, status="REJECTED")

    assert validate_target_hypothesis_registered(spec, candidate) == []
    assert any("expected CANDIDATE" in error for error in validate_target_hypothesis_registered(spec, rejected))


def test_registry_expected_status_tracks_stage(tmp_path: Path) -> None:
    spec = TARGET_SPECS["vwap_reversion_30m_v1"]
    discovery_pass = _registry(tmp_path / "discovery_pass.json", spec.hypothesis_id, status="DISCOVERY_PASS")

    assert validate_target_hypothesis_registered(spec, discovery_pass, stage="confirmation") == []
    assert any(
        "expected CANDIDATE" in error
        for error in validate_target_hypothesis_registered(spec, discovery_pass, stage="discovery")
    )


def test_trial_status_requires_candidate_register_event_without_evidence(tmp_path: Path) -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_30m_v1"]
    candidate = _trial_statuses(tmp_path / "candidate.jsonl", spec.hypothesis_id)
    with_evidence = _trial_statuses(
        tmp_path / "with_evidence.jsonl",
        spec.hypothesis_id,
        evidence=["reports/pipeline_audit/opening_range_acceptance_continuation_30m_v1_discovery_smoke.json"],
    )
    advanced = _trial_statuses(
        tmp_path / "advanced.jsonl",
        spec.hypothesis_id,
        status="DISCOVERY_PASS",
        stage="phase9_discovery_smoke",
        evidence=["reports/pipeline_audit/opening_range_acceptance_continuation_30m_v1_discovery_smoke.json"],
    )

    assert validate_target_trial_status_registered(spec, candidate) == []
    assert any("evidence must be empty" in error for error in validate_target_trial_status_registered(spec, with_evidence))
    assert any(
        "expected latest trial status CANDIDATE" in error
        for error in validate_target_trial_status_registered(spec, advanced)
    )


def test_vol_scaled_terminal_30m_label_math() -> None:
    spec = TARGET_SPECS["vol_scaled_terminal_30m_v1"]
    labeled = apply_vol_scaled_terminal_30m_target(_frame(), _cost_config(), spec)

    assert labeled.loc[21, spec.valid_column] == True
    assert labeled.loc[21, spec.direction_column] == 1
    assert labeled.loc[21, spec.nonflat_column] == True
    assert labeled.loc[21, spec.threshold_ticks_column] >= 4.0
    assert labeled.loc[21, spec.gross_column] == 100.0
    assert labeled.loc[21, spec.net_column] == 75.0
    assert labeled.loc[60, spec.direction_column] == -1
    assert labeled.loc[len(labeled) - 1, spec.valid_column] == False


def test_triple_barrier_30m_first_touch_label_math() -> None:
    spec = TARGET_SPECS["triple_barrier_30m_v1"]
    labeled = apply_triple_barrier_30m_target(_frame(), _cost_config(), spec)

    assert labeled.loc[21, spec.valid_column] == True
    assert labeled.loc[21, spec.direction_column] == 1
    assert labeled.loc[21, spec.gross_column] >= 50.0
    assert labeled.loc[21, spec.net_column] >= 25.0
    assert labeled.loc[36, spec.direction_column] == -1


def test_prior_extreme_failure_30m_label_math() -> None:
    spec = TARGET_SPECS["prior_extreme_failure_30m_v1"]
    labeled = apply_prior_extreme_failure_30m_target(_prior_extreme_frame(), _cost_config(), spec)

    high_failure_idx = 110
    low_failure_idx = 160
    assert labeled.loc[high_failure_idx, spec.valid_column] == True
    assert labeled.loc[high_failure_idx, spec.direction_column] == -1
    assert labeled.loc[high_failure_idx, spec.nonflat_column] == True
    assert labeled.loc[high_failure_idx, spec.gross_column] == -100.0
    assert labeled.loc[high_failure_idx, spec.net_column] == -75.0
    assert labeled.loc[low_failure_idx, spec.valid_column] == True
    assert labeled.loc[low_failure_idx, spec.direction_column] == 1
    assert labeled.loc[low_failure_idx, spec.gross_column] == 400.0
    assert labeled.loc[low_failure_idx, spec.net_column] == 375.0
    assert labeled.loc[0, spec.valid_column] == False


def test_vwap_reversion_30m_label_math() -> None:
    spec = TARGET_SPECS["vwap_reversion_30m_v1"]
    labeled = apply_vwap_reversion_30m_target(_vwap_reversion_frame(), _cost_config(), spec)

    above_stretch_idx = 30
    below_stretch_idx = 90
    assert labeled.loc[above_stretch_idx, spec.valid_column] == True
    assert labeled.loc[above_stretch_idx, spec.direction_column] == -1
    assert labeled.loc[above_stretch_idx, spec.nonflat_column] == True
    assert labeled.loc[above_stretch_idx, spec.gross_column] == -100.0
    assert labeled.loc[above_stretch_idx, spec.net_column] == -75.0
    assert labeled.loc[below_stretch_idx, spec.valid_column] == True
    assert labeled.loc[below_stretch_idx, spec.direction_column] == 1
    assert labeled.loc[below_stretch_idx, spec.gross_column] == 400.0
    assert labeled.loc[below_stretch_idx, spec.net_column] == 375.0
    assert labeled.loc[0, spec.valid_column] == False


def test_opportunity_risk_asymmetry_30m_label_math() -> None:
    spec = TARGET_SPECS["opportunity_risk_asymmetry_30m_v1"]
    labeled = apply_opportunity_risk_asymmetry_30m_target(_opportunity_risk_frame(), _cost_config(), spec)

    long_idx = 10
    short_idx = 60
    flat_idx = 90
    assert labeled.loc[long_idx, spec.valid_column] == True
    assert labeled.loc[long_idx, spec.direction_column] == 1
    assert labeled.loc[long_idx, spec.nonflat_column] == True
    assert labeled.loc[long_idx, spec.threshold_ticks_column] == 4.0
    assert labeled.loc[long_idx, spec.gross_column] == 150.0
    assert labeled.loc[long_idx, spec.net_column] == 125.0
    assert labeled.loc[long_idx, "target_long_opportunity_ticks_opportunity_risk_asymmetry_30m"] == 12.0
    assert labeled.loc[long_idx, "target_long_risk_ticks_opportunity_risk_asymmetry_30m"] == 1.0
    assert labeled.loc[long_idx, "target_long_opportunity_risk_opportunity_risk_asymmetry_30m"] == 3.0

    assert labeled.loc[short_idx, spec.valid_column] == True
    assert labeled.loc[short_idx, spec.direction_column] == -1
    assert labeled.loc[short_idx, spec.nonflat_column] == True
    assert labeled.loc[short_idx, spec.gross_column] == -150.0
    assert labeled.loc[short_idx, spec.net_column] == -125.0
    assert labeled.loc[short_idx, "target_short_opportunity_ticks_opportunity_risk_asymmetry_30m"] == 12.0
    assert labeled.loc[short_idx, "target_short_risk_ticks_opportunity_risk_asymmetry_30m"] == 1.0
    assert labeled.loc[short_idx, "target_short_opportunity_risk_opportunity_risk_asymmetry_30m"] == 3.0

    assert labeled.loc[flat_idx, spec.valid_column] == True
    assert labeled.loc[flat_idx, spec.direction_column] == 0
    assert labeled.loc[flat_idx, spec.nonflat_column] == False
    assert labeled.loc[flat_idx, spec.gross_column] == 0.0
    assert labeled.loc[flat_idx, spec.net_column] == 0.0
    assert labeled.loc[len(labeled) - 1, spec.valid_column] == False


def test_opportunity_risk_component_rank_30m_label_math() -> None:
    spec = TARGET_SPECS["opportunity_risk_component_rank_30m_v1"]
    labeled = apply_opportunity_risk_component_rank_30m_target(_opportunity_risk_frame(), _cost_config(), spec)

    long_idx = 10
    short_idx = 60
    flat_idx = 90
    assert labeled.loc[long_idx, spec.valid_column] == True
    assert labeled.loc[long_idx, spec.direction_column] == 1
    assert labeled.loc[long_idx, spec.nonflat_column] == True
    assert labeled.loc[long_idx, spec.threshold_ticks_column] == 4.0
    assert labeled.loc[long_idx, "target_best_opportunity_risk_opportunity_risk_component_rank_30m"] == 3.0
    assert labeled.loc[long_idx, spec.net_column] == 3.0
    assert labeled.loc[long_idx, "target_long_opportunity_ticks_opportunity_risk_component_rank_30m"] == 12.0
    assert labeled.loc[long_idx, "target_long_risk_ticks_opportunity_risk_component_rank_30m"] == 1.0

    assert labeled.loc[short_idx, spec.valid_column] == True
    assert labeled.loc[short_idx, spec.direction_column] == -1
    assert labeled.loc[short_idx, spec.nonflat_column] == True
    assert labeled.loc[short_idx, "target_best_opportunity_risk_opportunity_risk_component_rank_30m"] == 3.0
    assert labeled.loc[short_idx, spec.net_column] == 3.0
    assert labeled.loc[short_idx, "target_short_opportunity_ticks_opportunity_risk_component_rank_30m"] == 12.0
    assert labeled.loc[short_idx, "target_short_risk_ticks_opportunity_risk_component_rank_30m"] == 1.0

    assert labeled.loc[flat_idx, spec.valid_column] == True
    assert labeled.loc[flat_idx, spec.direction_column] == 0
    assert labeled.loc[flat_idx, spec.nonflat_column] == False
    assert labeled.loc[flat_idx, "target_best_opportunity_risk_opportunity_risk_component_rank_30m"] == 0.25
    assert labeled.loc[len(labeled) - 1, spec.valid_column] == False


def test_opening_range_acceptance_continuation_30m_label_math() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_30m_v1"]
    labeled = apply_opening_range_acceptance_continuation_30m_target(
        _opening_range_frame(),
        _cost_config(),
        spec,
    )
    event_direction = "target_event_direction_opening_range_acceptance_continuation_30m"
    or_high = "target_opening_range_high_opening_range_acceptance_continuation_30m"
    or_low = "target_opening_range_low_opening_range_acceptance_continuation_30m"

    assert labeled.loc[29, spec.valid_column] == False
    assert labeled.loc[30, spec.valid_column] == True
    assert labeled.loc[30, or_high] == 101.0
    assert labeled.loc[30, or_low] == 99.0
    assert labeled.loc[30, event_direction] == 1
    assert labeled.loc[30, spec.direction_column] == 1
    assert labeled.loc[30, spec.nonflat_column] == True
    assert labeled.loc[30, spec.gross_column] == 62.5
    assert labeled.loc[30, spec.net_column] == 37.5
    assert labeled.loc[70, event_direction] == -1
    assert labeled.loc[70, spec.direction_column] == -1
    assert labeled.loc[70, spec.gross_column] == -62.5
    assert labeled.loc[70, spec.net_column] == -37.5
    assert labeled.loc[110, event_direction] == 1
    assert labeled.loc[110, spec.direction_column] == 0
    assert labeled.loc[110, spec.nonflat_column] == False


def test_opening_range_event_side_does_not_use_future_path() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_30m_v1"]
    event_direction = "target_event_direction_opening_range_acceptance_continuation_30m"
    favorable = "target_favorable_excursion_ticks_opening_range_acceptance_continuation_30m"
    base = apply_opening_range_acceptance_continuation_30m_target(_opening_range_frame(), _cost_config(), spec)
    mutated_frame = _opening_range_frame()
    mutated_frame.loc[40, "high"] = 102.0
    mutated = apply_opening_range_acceptance_continuation_30m_target(mutated_frame, _cost_config(), spec)

    assert base.loc[30, spec.valid_column] == mutated.loc[30, spec.valid_column]
    assert base.loc[30, event_direction] == mutated.loc[30, event_direction]
    assert base.loc[30, favorable] != mutated.loc[30, favorable]
    assert base.loc[30, spec.direction_column] != mutated.loc[30, spec.direction_column]


def test_opening_range_rejects_cross_session_30m_horizon() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_30m_v1"]
    frame = _opening_range_frame()
    frame.loc[55:, "session_segment_id"] = "ES_2024_01_03"
    labeled = apply_opening_range_acceptance_continuation_30m_target(frame, _cost_config(), spec)

    assert labeled.loc[30, spec.valid_column] == False


def test_opening_range_distribution_non_overlap_and_duplicate_overlap() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_30m_v1"]
    labeled = apply_opening_range_acceptance_continuation_30m_target(
        _opening_range_frame(overlapping_long_rows=True),
        _cost_config(),
        spec,
    )
    events, skipped = non_overlapping_events(labeled, spec)
    balance = class_balance(events, spec)
    overlap = duplicate_target_overlap(events, spec)
    distribution = target_distribution_summary(events, spec)

    assert len(events) > 0
    assert skipped > 0
    assert balance["event_count"] == len(events)
    assert set(balance["counts"]) == {"long", "short", "flat"}
    assert balance["counts"]["long"] >= 1
    assert balance["counts"]["short"] >= 1
    assert balance["counts"]["flat"] >= 1
    assert overlap["available"] is True
    assert overlap["overlap_with_current_15m_deadzone"] is not None
    assert spec.net_column in distribution


def test_non_overlap_balance_and_duplicate_overlap_are_reported() -> None:
    spec = TARGET_SPECS["triple_barrier_30m_v1"]
    labeled = apply_triple_barrier_30m_target(_frame(), _cost_config(), spec)
    events, skipped = non_overlapping_events(labeled, spec)

    assert len(events) > 0
    assert skipped > 0
    assert class_balance(events, spec)["event_count"] == len(events)
    assert duplicate_target_overlap(events, spec)["available"] is True


def _stage_report(
    *,
    top_net: float = 100.0,
    overlap: float = 0.20,
    short_count: int = 1200,
    positive_folds: int = 3,
) -> dict[str, object]:
    return {
        "stage": "discovery",
        "failures": [],
        "class_balance": {
            "event_count": 10000,
            "counts": {"long": 1500, "short": short_count, "flat": 7300},
            "rates": {"long": 0.15, "short": short_count / 10000, "flat": 0.73},
        },
        "duplicate_target_overlap": {"overlap_with_current_15m_deadzone": overlap},
        "stage_summary": {
            "expected_fold_count": 4,
            "fold_count": 4,
            "top_rows": 100,
            "top_total_net_dollars": top_net,
            "positive_top_net_fold_count": positive_folds,
            "min_prediction_std": 0.1,
        },
    }


def _component_rank_stage_report(
    *,
    event_count: int = 10000,
    positive_folds: int = 3,
    top_uplift: float = 10.0,
) -> dict[str, object]:
    return {
        "stage": "discovery",
        "evaluation_mode": EVALUATION_COMPONENT_RANK,
        "event_count": event_count,
        "failures": [],
        "class_balance": {
            "event_count": event_count,
            "counts": {"long": 4900, "short": 4900, "flat": 200},
            "rates": {"long": 0.49, "short": 0.49, "flat": 0.02},
        },
        "duplicate_target_overlap": {"overlap_with_current_15m_deadzone": None},
        "stage_summary": {
            "evaluation_mode": EVALUATION_COMPONENT_RANK,
            "expected_fold_count": 4,
            "fold_count": 4,
            "test_rows": 1000,
            "scored_rows": 1000,
            "top_rows": 100,
            "top_total_rank_score": 200.0,
            "top_avg_rank_score": 2.0,
            "baseline_avg_rank_score": 1.9,
            "top_total_rank_score_uplift": top_uplift,
            "top_avg_rank_score_uplift": top_uplift / 100.0,
            "positive_rank_uplift_fold_count": positive_folds,
            "min_prediction_std": 0.1,
        },
    }


def test_stage_gates_cover_stop_conditions() -> None:
    assert evaluate_stage_gates(_stage_report())["decision"] == "DISCOVERY_PASS"
    assert evaluate_stage_gates(_stage_report(top_net=-1.0))["decision"] == "STOP_DISCOVERY_NEGATIVE_NET"
    assert evaluate_stage_gates(_stage_report(overlap=0.90))["decision"] == "STOP_DUPLICATE_TARGET"
    assert evaluate_stage_gates(_stage_report(short_count=1))["decision"] == "STOP_CLASS_COLLAPSE"
    assert evaluate_stage_gates(_stage_report(positive_folds=1))["decision"] == "STOP_UNSTABLE_FOLDS"


def test_component_rank_stage_gates_cover_stop_conditions() -> None:
    assert evaluate_stage_gates(_component_rank_stage_report())["decision"] == "DISCOVERY_PASS"
    assert evaluate_stage_gates(_component_rank_stage_report(event_count=10))["decision"] == "STOP_UNDERPOWERED"
    assert (
        evaluate_stage_gates(_component_rank_stage_report(positive_folds=1))["decision"]
        == "STOP_UNSTABLE_RANK_UPLIFT"
    )
    assert (
        evaluate_stage_gates(_component_rank_stage_report(top_uplift=0.0))["decision"]
        == "STOP_DISCOVERY_NONPOSITIVE_RANK_UPLIFT"
    )


def test_component_rank_stage_summary_uses_rank_uplift() -> None:
    summary = stage_summary(
        [
            {
                "evaluation_mode": EVALUATION_COMPONENT_RANK,
                "test_rows": 10,
                "scored_rows": 10,
                "top_rows": 2,
                "top_total_rank_score": 6.0,
                "baseline_avg_rank_score": 2.0,
                "top_total_rank_score_uplift": 2.0,
                "top_rank_score_uplift": 1.0,
                "prediction_std": 0.1,
            },
            {
                "evaluation_mode": EVALUATION_COMPONENT_RANK,
                "test_rows": 10,
                "scored_rows": 10,
                "top_rows": 2,
                "top_total_rank_score": 5.0,
                "baseline_avg_rank_score": 2.5,
                "top_total_rank_score_uplift": 0.0,
                "top_rank_score_uplift": 0.0,
                "prediction_std": 0.2,
            },
        ],
        2,
    )

    assert summary["evaluation_mode"] == EVALUATION_COMPONENT_RANK
    assert summary["top_avg_rank_score"] == 2.75
    assert summary["baseline_avg_rank_score"] == 2.25
    assert summary["top_avg_rank_score_uplift"] == 0.5
    assert summary["positive_rank_uplift_fold_count"] == 1
