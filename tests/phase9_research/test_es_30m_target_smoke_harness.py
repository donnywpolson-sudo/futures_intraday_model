from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.es_30m_target_smoke_harness import (
    EVALUATION_COMPONENT_RANK,
    TARGET_SPECS,
    apply_late_session_range_resolve_session_close_target,
    apply_opening_drive_failed_followthrough_15m_target,
    apply_opening_range_acceptance_event_capture_30m_target,
    apply_opening_range_acceptance_continuation_30m_target,
    apply_opportunity_risk_component_rank_30m_target,
    apply_opportunity_risk_asymmetry_30m_target,
    apply_prior_extreme_failure_30m_target,
    apply_session_compression_breakout_30m_target,
    apply_triple_barrier_30m_target,
    apply_volume_pace_breakout_continuation_30m_target,
    apply_vol_scaled_terminal_30m_target,
    apply_vwap_reclaim_continuation_15m_target,
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


def _vwap_reclaim_frame() -> pd.DataFrame:
    periods = 140
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    open_ = [100.0] * periods
    high = [100.25] * periods
    low = [99.75] * periods
    close = [100.0] * periods
    volume = [100.0] * periods

    for idx in range(20, 25):
        open_[idx] = 98.0
        high[idx] = 98.25
        low[idx] = 97.75
        close[idx] = 98.0
    long_idx = 25
    open_[long_idx] = 100.5
    high[long_idx] = 100.75
    low[long_idx] = 100.25
    close[long_idx] = 100.5
    open_[long_idx + 1] = 100.5
    open_[long_idx + 16] = 110.0

    for idx in range(75, 80):
        open_[idx] = 102.5
        high[idx] = 102.75
        low[idx] = 102.25
        close[idx] = 102.5
    short_idx = 80
    open_[short_idx] = 99.5
    high[short_idx] = 99.75
    low[short_idx] = 99.25
    close[short_idx] = 99.5
    open_[short_idx + 1] = 99.5
    open_[short_idx + 16] = 90.0

    for idx in range(108, 113):
        open_[idx] = 98.0
        high[idx] = 98.25
        low[idx] = 97.75
        close[idx] = 98.0
    flat_idx = 113
    open_[flat_idx] = 100.5
    high[flat_idx] = 100.75
    low[flat_idx] = 100.25
    close[flat_idx] = 100.5
    open_[flat_idx + 1] = 100.5
    open_[flat_idx + 16] = 100.75

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


def _opening_drive_failed_followthrough_frame() -> pd.DataFrame:
    session_periods = 60
    periods = session_periods * 3
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    sessions = (
        ["ES_2024_01_02"] * session_periods
        + ["ES_2024_01_03"] * session_periods
        + ["ES_2024_01_04"] * session_periods
    )
    open_ = [100.0] * periods
    high = [100.25] * periods
    low = [99.75] * periods
    close = [100.0] * periods
    volume = [100.0] * periods

    def set_bar(session_idx: int, local_idx: int, price: float) -> int:
        idx = session_idx * session_periods + local_idx
        open_[idx] = price
        high[idx] = price + 0.25
        low[idx] = price - 0.25
        close[idx] = price
        return idx

    def set_open(session_idx: int, local_idx: int, price: float) -> int:
        idx = session_idx * session_periods + local_idx
        open_[idx] = price
        close[idx] = price
        high[idx] = price + 0.25
        low[idx] = price - 0.25
        return idx

    for session_idx in (0, 2):
        for local_idx in range(15):
            set_bar(session_idx, local_idx, 100.0 + (6.0 * local_idx / 14.0))
        for local_idx in range(15, 25):
            set_bar(session_idx, local_idx, 107.0)
        attempt_idx = set_bar(session_idx, 20, 107.0)
        high[attempt_idx] = 110.0
        event_idx = set_bar(session_idx, 25, 105.75)
        set_open(session_idx, 26, 106.0)
        set_open(session_idx, 41, 96.0 if session_idx == 0 else 105.75)
        assert event_idx == session_idx * session_periods + 25

    for local_idx in range(15):
        set_bar(1, local_idx, 100.0 - (6.0 * local_idx / 14.0))
    for local_idx in range(15, 25):
        set_bar(1, local_idx, 93.0)
    attempt_idx = set_bar(1, 20, 93.0)
    low[attempt_idx] = 90.0
    set_bar(1, 25, 94.25)
    set_open(1, 26, 94.0)
    set_open(1, 41, 104.0)

    return pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_segment_id": sessions,
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


def _session_compression_breakout_frame() -> pd.DataFrame:
    periods = 275
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    open_ = [100.0] * periods
    high = [100.25] * periods
    low = [99.75] * periods
    close = [100.0] * periods

    long_idx = 100
    close[long_idx] = 100.50
    high[long_idx] = 100.75
    low[long_idx] = 100.25
    open_[long_idx + 1] = 100.50
    open_[long_idx + 31] = 102.00

    short_idx = 170
    close[short_idx] = 99.50
    high[short_idx] = 99.75
    low[short_idx] = 99.25
    open_[short_idx + 1] = 99.50
    open_[short_idx + 31] = 98.00

    flat_idx = 235
    close[flat_idx] = 100.50
    high[flat_idx] = 100.75
    low[flat_idx] = 100.25
    open_[flat_idx + 1] = 100.50
    open_[flat_idx + 31] = 100.75

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


def _volume_pace_breakout_frame(
    *,
    prior_sessions: int = 20,
    event_volume: float = 10_000.0,
) -> pd.DataFrame:
    session_periods = 130
    event_idx = 70
    exit_idx = event_idx + 31
    sessions: list[pd.DataFrame] = []
    base_ts = pd.Timestamp("2024-01-02T14:30:00Z")

    def build_session(session_idx: int, event_kind: str) -> pd.DataFrame:
        ts = pd.date_range(base_ts + pd.Timedelta(days=session_idx), periods=session_periods, freq="min")
        open_ = [100.0] * session_periods
        high = [100.25] * session_periods
        low = [99.75] * session_periods
        close = [100.0] * session_periods
        volume = [100.0] * session_periods

        if event_kind == "long":
            close[event_idx] = 100.50
            high[event_idx] = 100.75
            low[event_idx] = 100.25
            volume[event_idx] = event_volume
            open_[event_idx + 1] = 100.50
            open_[exit_idx] = 102.00
            close[exit_idx] = 102.00
            high[exit_idx] = 102.25
            low[exit_idx] = 101.75
        elif event_kind == "short":
            close[event_idx] = 99.50
            high[event_idx] = 99.75
            low[event_idx] = 99.25
            volume[event_idx] = event_volume
            open_[event_idx + 1] = 99.50
            open_[exit_idx] = 98.00
            close[exit_idx] = 98.00
            high[exit_idx] = 98.25
            low[exit_idx] = 97.75
        elif event_kind == "flat":
            close[event_idx] = 100.50
            high[event_idx] = 100.75
            low[event_idx] = 100.25
            volume[event_idx] = event_volume
            open_[event_idx + 1] = 100.50
            open_[exit_idx] = 100.75
            close[exit_idx] = 100.75
            high[exit_idx] = 101.00
            low[exit_idx] = 100.50

        return pd.DataFrame(
            {
                "ts": ts,
                "market": "ES",
                "year": 2024,
                "session_segment_id": f"ES_2024_VOLUME_PACE_{session_idx:04d}",
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
                "target_sign_with_deadzone": [1 if idx % 3 == 0 else 0 for idx in range(session_periods)],
                "is_synthetic": False,
                "roll_window_flag": False,
                "boundary_session_flag": False,
                "feature_signal": range(session_periods),
            }
        )

    for session_idx in range(prior_sessions):
        sessions.append(build_session(session_idx, "none"))
    sessions.append(build_session(prior_sessions, "long"))
    sessions.append(build_session(prior_sessions + 1, "short"))
    sessions.append(build_session(prior_sessions + 2, "flat"))
    return pd.concat(sessions, ignore_index=True)


def _late_session_range_resolve_frame() -> pd.DataFrame:
    session_periods = 121
    sessions: list[pd.DataFrame] = []

    def build_session(date_text: str, session_id: str, event_direction: int) -> pd.DataFrame:
        ts = pd.date_range(f"{date_text}T20:00:00Z", periods=session_periods, freq="min")
        open_ = [100.0] * session_periods
        high = [100.25] * session_periods
        low = [99.75] * session_periods
        close = [100.0] * session_periods
        event_idx = 70
        close_idx = 120
        if event_direction == 1:
            close[event_idx] = 100.50
            high[event_idx] = 100.75
            low[event_idx] = 100.25
            open_[event_idx + 1] = 100.50
            open_[close_idx] = 102.00
            close[close_idx] = 102.00
            high[close_idx] = 102.25
            low[close_idx] = 101.75
        elif event_direction == -1:
            close[event_idx] = 99.50
            high[event_idx] = 99.75
            low[event_idx] = 99.25
            open_[event_idx + 1] = 99.50
            open_[close_idx] = 98.00
            close[close_idx] = 98.00
            high[close_idx] = 98.25
            low[close_idx] = 97.75
        else:
            close[event_idx] = 100.50
            high[event_idx] = 100.75
            low[event_idx] = 100.25
            open_[event_idx + 1] = 100.50
            open_[close_idx] = 100.75
            close[close_idx] = 100.75
            high[close_idx] = 101.00
            low[close_idx] = 100.50
        return pd.DataFrame(
            {
                "ts": ts,
                "market": "ES",
                "year": 2024,
                "session_segment_id": session_id,
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
                "target_sign_with_deadzone": [1 if idx % 3 == 0 else 0 for idx in range(session_periods)],
                "is_synthetic": False,
                "roll_window_flag": False,
                "boundary_session_flag": False,
                "feature_signal": range(session_periods),
            }
        )

    sessions.append(build_session("2024-01-02", "ES_2024_01_02", 1))
    sessions.append(build_session("2024-01-03", "ES_2024_01_03", -1))
    sessions.append(build_session("2024-01-04", "ES_2024_01_04", 0))
    return pd.concat(sessions, ignore_index=True)


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


def test_vwap_reclaim_continuation_15m_target_spec_is_distinct() -> None:
    spec = TARGET_SPECS["vwap_reclaim_continuation_15m_v1"]

    assert spec.target_family == "es_vwap_reclaim_continuation_15m"
    assert spec.slug == "vwap_reclaim_continuation_15m"
    assert spec.horizon_bars == 15
    assert "sqrt(15)" in spec.threshold_description
    assert "target_event_direction_vwap_reclaim_continuation_15m" in spec.target_columns
    assert "target_timeout_exit_ticks_vwap_reclaim_continuation_15m" in spec.target_columns


def test_vwap_reclaim_continuation_15m_label_math() -> None:
    spec = TARGET_SPECS["vwap_reclaim_continuation_15m_v1"]
    labeled = apply_vwap_reclaim_continuation_15m_target(_vwap_reclaim_frame(), _cost_config(), spec)
    event_direction = "target_event_direction_vwap_reclaim_continuation_15m"
    prior_side = "target_prior_excursion_side_vwap_reclaim_continuation_15m"
    timeout_ticks = "target_timeout_exit_ticks_vwap_reclaim_continuation_15m"

    long_idx = 25
    short_idx = 80
    flat_idx = 113
    assert labeled.loc[long_idx, spec.valid_column] == True
    assert labeled.loc[long_idx, event_direction] == 1
    assert labeled.loc[long_idx, prior_side] == -1
    assert labeled.loc[long_idx, spec.direction_column] == 1
    assert labeled.loc[long_idx, spec.nonflat_column] == True
    assert labeled.loc[long_idx, timeout_ticks] == 38.0
    assert labeled.loc[long_idx, spec.gross_column] == 475.0
    assert labeled.loc[long_idx, spec.net_column] == 450.0

    assert labeled.loc[short_idx, spec.valid_column] == True
    assert labeled.loc[short_idx, event_direction] == -1
    assert labeled.loc[short_idx, prior_side] == 1
    assert labeled.loc[short_idx, spec.direction_column] == -1
    assert labeled.loc[short_idx, spec.nonflat_column] == True
    assert labeled.loc[short_idx, timeout_ticks] == 38.0
    assert labeled.loc[short_idx, spec.gross_column] == 475.0
    assert labeled.loc[short_idx, spec.net_column] == 450.0

    assert labeled.loc[flat_idx, spec.valid_column] == True
    assert labeled.loc[flat_idx, event_direction] == 1
    assert labeled.loc[flat_idx, spec.direction_column] == 0
    assert labeled.loc[flat_idx, spec.nonflat_column] == False
    assert labeled.loc[flat_idx, timeout_ticks] == 1.0
    assert labeled.loc[flat_idx, spec.gross_column] == 12.5
    assert labeled.loc[flat_idx, spec.net_column] == -12.5


def test_vwap_reclaim_event_side_does_not_use_future_path() -> None:
    spec = TARGET_SPECS["vwap_reclaim_continuation_15m_v1"]
    event_direction = "target_event_direction_vwap_reclaim_continuation_15m"
    base = apply_vwap_reclaim_continuation_15m_target(_vwap_reclaim_frame(), _cost_config(), spec)
    mutated_frame = _vwap_reclaim_frame()
    mutated_frame.loc[30, ["high", "low", "close"]] = [120.0, 119.5, 120.0]
    mutated = apply_vwap_reclaim_continuation_15m_target(mutated_frame, _cost_config(), spec)

    assert base.loc[25, spec.valid_column] == mutated.loc[25, spec.valid_column]
    assert base.loc[25, event_direction] == mutated.loc[25, event_direction]
    assert base.loc[25, spec.gross_column] == mutated.loc[25, spec.gross_column]
    assert base.loc[25, spec.net_column] == mutated.loc[25, spec.net_column]


def test_vwap_reclaim_rejects_cross_session_15m_horizon() -> None:
    spec = TARGET_SPECS["vwap_reclaim_continuation_15m_v1"]
    frame = _vwap_reclaim_frame()
    frame.loc[35:, "session_segment_id"] = "ES_2024_01_03"
    labeled = apply_vwap_reclaim_continuation_15m_target(frame, _cost_config(), spec)

    assert labeled.loc[25, spec.valid_column] == False


def test_vwap_reclaim_distribution_has_long_short_and_flat() -> None:
    spec = TARGET_SPECS["vwap_reclaim_continuation_15m_v1"]
    labeled = apply_vwap_reclaim_continuation_15m_target(_vwap_reclaim_frame(), _cost_config(), spec)
    events, skipped = non_overlapping_events(labeled, spec)
    balance = class_balance(events, spec)
    distribution = target_distribution_summary(events, spec)

    assert skipped == 0
    assert balance["event_count"] == len(events)
    assert balance["counts"]["long"] >= 1
    assert balance["counts"]["short"] >= 1
    assert balance["counts"]["flat"] >= 1
    assert spec.net_column in distribution


def test_opening_drive_failed_followthrough_15m_target_spec_is_distinct() -> None:
    spec = TARGET_SPECS["opening_drive_failed_followthrough_15m_v1"]

    assert spec.target_family == "es_opening_drive_failed_followthrough_15m"
    assert spec.slug == "opening_drive_failed_followthrough_15m"
    assert spec.horizon_bars == 15
    assert "sqrt(15)" in spec.threshold_description
    assert "target_event_direction_opening_drive_failed_followthrough_15m" in spec.target_columns
    assert "target_timeout_exit_ticks_opening_drive_failed_followthrough_15m" in spec.target_columns


def test_opening_drive_failed_followthrough_15m_label_math() -> None:
    spec = TARGET_SPECS["opening_drive_failed_followthrough_15m_v1"]
    labeled = apply_opening_drive_failed_followthrough_15m_target(
        _opening_drive_failed_followthrough_frame(),
        _cost_config(),
        spec,
    )
    drive_direction = "target_opening_drive_direction_opening_drive_failed_followthrough_15m"
    event_direction = "target_event_direction_opening_drive_failed_followthrough_15m"
    failed_ticks = "target_failed_followthrough_ticks_opening_drive_failed_followthrough_15m"
    timeout_ticks = "target_timeout_exit_ticks_opening_drive_failed_followthrough_15m"

    short_reversal_idx = 25
    long_reversal_idx = 85
    flat_idx = 145
    assert labeled.loc[14, spec.valid_column] == False

    assert labeled.loc[short_reversal_idx, spec.valid_column] == True
    assert labeled.loc[short_reversal_idx, drive_direction] == 1
    assert labeled.loc[short_reversal_idx, event_direction] == -1
    assert labeled.loc[short_reversal_idx, failed_ticks] == 16.0
    assert labeled.loc[short_reversal_idx, spec.direction_column] == -1
    assert labeled.loc[short_reversal_idx, spec.nonflat_column] == True
    assert labeled.loc[short_reversal_idx, timeout_ticks] == 40.0
    assert labeled.loc[short_reversal_idx, spec.gross_column] == 500.0
    assert labeled.loc[short_reversal_idx, spec.net_column] == 475.0

    assert labeled.loc[long_reversal_idx, spec.valid_column] == True
    assert labeled.loc[long_reversal_idx, drive_direction] == -1
    assert labeled.loc[long_reversal_idx, event_direction] == 1
    assert labeled.loc[long_reversal_idx, failed_ticks] == 16.0
    assert labeled.loc[long_reversal_idx, spec.direction_column] == 1
    assert labeled.loc[long_reversal_idx, spec.nonflat_column] == True
    assert labeled.loc[long_reversal_idx, timeout_ticks] == 40.0
    assert labeled.loc[long_reversal_idx, spec.gross_column] == 500.0
    assert labeled.loc[long_reversal_idx, spec.net_column] == 475.0

    assert labeled.loc[flat_idx, spec.valid_column] == True
    assert labeled.loc[flat_idx, drive_direction] == 1
    assert labeled.loc[flat_idx, event_direction] == -1
    assert labeled.loc[flat_idx, spec.direction_column] == 0
    assert labeled.loc[flat_idx, spec.nonflat_column] == False
    assert labeled.loc[flat_idx, timeout_ticks] == 1.0
    assert labeled.loc[flat_idx, spec.gross_column] == 12.5
    assert labeled.loc[flat_idx, spec.net_column] == -12.5


def test_opening_drive_failed_followthrough_event_side_does_not_use_future_path() -> None:
    spec = TARGET_SPECS["opening_drive_failed_followthrough_15m_v1"]
    event_direction = "target_event_direction_opening_drive_failed_followthrough_15m"
    base = apply_opening_drive_failed_followthrough_15m_target(
        _opening_drive_failed_followthrough_frame(),
        _cost_config(),
        spec,
    )
    mutated_frame = _opening_drive_failed_followthrough_frame()
    mutated_frame.loc[30, ["high", "low", "close"]] = [120.0, 119.5, 120.0]
    mutated = apply_opening_drive_failed_followthrough_15m_target(mutated_frame, _cost_config(), spec)

    assert base.loc[25, spec.valid_column] == mutated.loc[25, spec.valid_column]
    assert base.loc[25, event_direction] == mutated.loc[25, event_direction]
    assert base.loc[25, spec.gross_column] == mutated.loc[25, spec.gross_column]
    assert base.loc[25, spec.net_column] == mutated.loc[25, spec.net_column]


def test_opening_drive_failed_followthrough_rejects_cross_session_15m_horizon() -> None:
    spec = TARGET_SPECS["opening_drive_failed_followthrough_15m_v1"]
    frame = _opening_drive_failed_followthrough_frame()
    frame.loc[35:, "session_segment_id"] = "ES_2024_01_99"
    labeled = apply_opening_drive_failed_followthrough_15m_target(frame, _cost_config(), spec)

    assert labeled.loc[25, spec.valid_column] == False


def test_opening_drive_failed_followthrough_distribution_has_long_short_and_flat() -> None:
    spec = TARGET_SPECS["opening_drive_failed_followthrough_15m_v1"]
    labeled = apply_opening_drive_failed_followthrough_15m_target(
        _opening_drive_failed_followthrough_frame(),
        _cost_config(),
        spec,
    )
    events, skipped = non_overlapping_events(labeled, spec)
    balance = class_balance(events, spec)
    distribution = target_distribution_summary(events, spec)

    assert skipped > 0
    assert balance["event_count"] == len(events)
    assert balance["counts"]["long"] >= 1
    assert balance["counts"]["short"] >= 1
    assert balance["counts"]["flat"] >= 1
    assert spec.net_column in distribution


def test_session_compression_breakout_30m_target_spec_is_distinct() -> None:
    spec = TARGET_SPECS["session_compression_breakout_30m_v1"]

    assert spec.target_family == "es_session_compression_breakout_30m"
    assert spec.slug == "session_compression_breakout_30m"
    assert spec.horizon_bars == 30
    assert "25th percentile" in spec.threshold_description
    assert "target_box_high_session_compression_breakout_30m" in spec.target_columns
    assert "target_timeout_exit_ticks_session_compression_breakout_30m" in spec.target_columns


def test_session_compression_breakout_30m_label_math() -> None:
    spec = TARGET_SPECS["session_compression_breakout_30m_v1"]
    labeled = apply_session_compression_breakout_30m_target(
        _session_compression_breakout_frame(),
        _cost_config(),
        spec,
    )
    box_high = "target_box_high_session_compression_breakout_30m"
    box_low = "target_box_low_session_compression_breakout_30m"
    box_range = "target_box_range_ticks_session_compression_breakout_30m"
    compression_threshold = "target_compression_threshold_ticks_session_compression_breakout_30m"
    event_direction = "target_event_direction_session_compression_breakout_30m"
    breakout_ticks = "target_breakout_ticks_session_compression_breakout_30m"
    timeout_ticks = "target_timeout_exit_ticks_session_compression_breakout_30m"

    long_idx = 100
    short_idx = 170
    flat_idx = 235
    assert labeled.loc[89, spec.valid_column] == False

    assert labeled.loc[long_idx, spec.valid_column] == True
    assert labeled.loc[long_idx, box_high] == 100.25
    assert labeled.loc[long_idx, box_low] == 99.75
    assert labeled.loc[long_idx, box_range] == 2.0
    assert labeled.loc[long_idx, compression_threshold] == 2.0
    assert labeled.loc[long_idx, event_direction] == 1
    assert labeled.loc[long_idx, breakout_ticks] == 1.0
    assert labeled.loc[long_idx, spec.direction_column] == 1
    assert labeled.loc[long_idx, spec.nonflat_column] == True
    assert labeled.loc[long_idx, timeout_ticks] == 6.0
    assert labeled.loc[long_idx, spec.gross_column] == 75.0
    assert labeled.loc[long_idx, spec.net_column] == 50.0

    assert labeled.loc[short_idx, spec.valid_column] == True
    assert labeled.loc[short_idx, event_direction] == -1
    assert labeled.loc[short_idx, breakout_ticks] == 1.0
    assert labeled.loc[short_idx, spec.direction_column] == -1
    assert labeled.loc[short_idx, spec.nonflat_column] == True
    assert labeled.loc[short_idx, timeout_ticks] == 6.0
    assert labeled.loc[short_idx, spec.gross_column] == 75.0
    assert labeled.loc[short_idx, spec.net_column] == 50.0

    assert labeled.loc[flat_idx, spec.valid_column] == True
    assert labeled.loc[flat_idx, event_direction] == 1
    assert labeled.loc[flat_idx, spec.direction_column] == 0
    assert labeled.loc[flat_idx, spec.nonflat_column] == False
    assert labeled.loc[flat_idx, timeout_ticks] == 1.0
    assert labeled.loc[flat_idx, spec.gross_column] == 12.5
    assert labeled.loc[flat_idx, spec.net_column] == -12.5


def test_session_compression_breakout_event_side_does_not_use_future_path() -> None:
    spec = TARGET_SPECS["session_compression_breakout_30m_v1"]
    event_direction = "target_event_direction_session_compression_breakout_30m"
    base = apply_session_compression_breakout_30m_target(
        _session_compression_breakout_frame(),
        _cost_config(),
        spec,
    )
    mutated_frame = _session_compression_breakout_frame()
    mutated_frame.loc[110, ["high", "low", "close"]] = [120.0, 119.5, 120.0]
    mutated = apply_session_compression_breakout_30m_target(mutated_frame, _cost_config(), spec)

    assert base.loc[100, spec.valid_column] == mutated.loc[100, spec.valid_column]
    assert base.loc[100, event_direction] == mutated.loc[100, event_direction]
    assert base.loc[100, spec.gross_column] == mutated.loc[100, spec.gross_column]
    assert base.loc[100, spec.net_column] == mutated.loc[100, spec.net_column]


def test_session_compression_breakout_rejects_cross_session_30m_horizon() -> None:
    spec = TARGET_SPECS["session_compression_breakout_30m_v1"]
    frame = _session_compression_breakout_frame()
    frame.loc[120:, "session_segment_id"] = "ES_2024_01_99"
    labeled = apply_session_compression_breakout_30m_target(frame, _cost_config(), spec)

    assert labeled.loc[100, spec.valid_column] == False


def test_session_compression_breakout_distribution_has_long_short_and_flat() -> None:
    spec = TARGET_SPECS["session_compression_breakout_30m_v1"]
    labeled = apply_session_compression_breakout_30m_target(
        _session_compression_breakout_frame(),
        _cost_config(),
        spec,
    )
    events, skipped = non_overlapping_events(labeled, spec)
    balance = class_balance(events, spec)
    distribution = target_distribution_summary(events, spec)

    assert skipped >= 0
    assert events[spec.entry_ts_column].iloc[1:].gt(events[spec.exit_ts_column].shift(1).iloc[1:]).all()
    assert balance["event_count"] == len(events)
    assert balance["counts"]["long"] >= 1
    assert balance["counts"]["short"] >= 1
    assert balance["counts"]["flat"] >= 1
    assert spec.net_column in distribution


def test_volume_pace_breakout_continuation_30m_target_spec_is_distinct() -> None:
    spec = TARGET_SPECS["volume_pace_breakout_continuation_30m_v1"]

    assert spec.target_family == "es_volume_pace_breakout_continuation_30m"
    assert spec.slug == "volume_pace_breakout_continuation_30m"
    assert spec.horizon_bars == 30
    assert "volume pace ratio >= 1.5" in spec.threshold_description
    assert "target_range_high_volume_pace_breakout_continuation_30m" in spec.target_columns
    assert "target_volume_pace_ratio_volume_pace_breakout_continuation_30m" in spec.target_columns
    assert "target_timeout_exit_ticks_volume_pace_breakout_continuation_30m" in spec.target_columns


def test_volume_pace_breakout_continuation_30m_label_math() -> None:
    spec = TARGET_SPECS["volume_pace_breakout_continuation_30m_v1"]
    labeled = apply_volume_pace_breakout_continuation_30m_target(
        _volume_pace_breakout_frame(),
        _cost_config(),
        spec,
    )
    range_high = "target_range_high_volume_pace_breakout_continuation_30m"
    range_low = "target_range_low_volume_pace_breakout_continuation_30m"
    range_ticks = "target_range_ticks_volume_pace_breakout_continuation_30m"
    volume_pace = "target_volume_pace_volume_pace_breakout_continuation_30m"
    volume_baseline = "target_volume_pace_baseline_volume_pace_breakout_continuation_30m"
    volume_ratio = "target_volume_pace_ratio_volume_pace_breakout_continuation_30m"
    event_direction = "target_event_direction_volume_pace_breakout_continuation_30m"
    breakout_ticks = "target_breakout_ticks_volume_pace_breakout_continuation_30m"
    timeout_ticks = "target_timeout_exit_ticks_volume_pace_breakout_continuation_30m"

    session_periods = 130
    event_idx = 70
    long_idx = 20 * session_periods + event_idx
    short_idx = 21 * session_periods + event_idx
    flat_idx = 22 * session_periods + event_idx
    assert labeled.loc[19 * session_periods + event_idx, spec.valid_column] == False

    assert labeled.loc[long_idx, spec.valid_column] == True
    assert labeled.loc[long_idx, range_high] == 100.25
    assert labeled.loc[long_idx, range_low] == 99.75
    assert labeled.loc[long_idx, range_ticks] == 2.0
    assert labeled.loc[long_idx, volume_pace] > 150.0
    assert labeled.loc[long_idx, volume_baseline] == 100.0
    assert labeled.loc[long_idx, volume_ratio] >= 1.5
    assert labeled.loc[long_idx, event_direction] == 1
    assert labeled.loc[long_idx, breakout_ticks] == 1.0
    assert labeled.loc[long_idx, spec.direction_column] == 1
    assert labeled.loc[long_idx, spec.nonflat_column] == True
    assert labeled.loc[long_idx, timeout_ticks] == 6.0
    assert labeled.loc[long_idx, spec.gross_column] == 75.0
    assert labeled.loc[long_idx, spec.net_column] == 50.0

    assert labeled.loc[short_idx, spec.valid_column] == True
    assert labeled.loc[short_idx, event_direction] == -1
    assert labeled.loc[short_idx, breakout_ticks] == 1.0
    assert labeled.loc[short_idx, spec.direction_column] == -1
    assert labeled.loc[short_idx, spec.nonflat_column] == True
    assert labeled.loc[short_idx, timeout_ticks] == 6.0
    assert labeled.loc[short_idx, spec.gross_column] == 75.0
    assert labeled.loc[short_idx, spec.net_column] == 50.0

    assert labeled.loc[flat_idx, spec.valid_column] == True
    assert labeled.loc[flat_idx, event_direction] == 1
    assert labeled.loc[flat_idx, spec.direction_column] == 0
    assert labeled.loc[flat_idx, spec.nonflat_column] == False
    assert labeled.loc[flat_idx, timeout_ticks] == 1.0
    assert labeled.loc[flat_idx, spec.gross_column] == 12.5
    assert labeled.loc[flat_idx, spec.net_column] == -12.5


def test_volume_pace_breakout_event_side_does_not_use_future_path() -> None:
    spec = TARGET_SPECS["volume_pace_breakout_continuation_30m_v1"]
    event_direction = "target_event_direction_volume_pace_breakout_continuation_30m"
    session_periods = 130
    event_idx = 20 * session_periods + 70
    base = apply_volume_pace_breakout_continuation_30m_target(
        _volume_pace_breakout_frame(),
        _cost_config(),
        spec,
    )
    mutated_frame = _volume_pace_breakout_frame()
    mutated_frame.loc[event_idx + 10, ["high", "low", "close"]] = [120.0, 119.5, 120.0]
    mutated = apply_volume_pace_breakout_continuation_30m_target(mutated_frame, _cost_config(), spec)

    assert base.loc[event_idx, spec.valid_column] == mutated.loc[event_idx, spec.valid_column]
    assert base.loc[event_idx, event_direction] == mutated.loc[event_idx, event_direction]
    assert base.loc[event_idx, spec.gross_column] == mutated.loc[event_idx, spec.gross_column]
    assert base.loc[event_idx, spec.net_column] == mutated.loc[event_idx, spec.net_column]


def test_volume_pace_breakout_rejects_cross_session_30m_horizon() -> None:
    spec = TARGET_SPECS["volume_pace_breakout_continuation_30m_v1"]
    session_periods = 130
    event_idx = 20 * session_periods + 70
    frame = _volume_pace_breakout_frame()
    frame.loc[event_idx + 20 :, "session_segment_id"] = "ES_2024_VOLUME_PACE_BROKEN_PATH"
    labeled = apply_volume_pace_breakout_continuation_30m_target(frame, _cost_config(), spec)

    assert labeled.loc[event_idx, spec.valid_column] == False


def test_volume_pace_breakout_requires_prior_session_volume_baseline() -> None:
    spec = TARGET_SPECS["volume_pace_breakout_continuation_30m_v1"]
    session_periods = 130
    event_idx = 19 * session_periods + 70
    labeled = apply_volume_pace_breakout_continuation_30m_target(
        _volume_pace_breakout_frame(prior_sessions=19),
        _cost_config(),
        spec,
    )

    assert labeled.loc[event_idx, spec.valid_column] == False
    assert labeled.loc[event_idx, "target_event_direction_volume_pace_breakout_continuation_30m"] == 0


def test_volume_pace_breakout_rejects_low_volume_pace() -> None:
    spec = TARGET_SPECS["volume_pace_breakout_continuation_30m_v1"]
    session_periods = 130
    event_idx = 20 * session_periods + 70
    labeled = apply_volume_pace_breakout_continuation_30m_target(
        _volume_pace_breakout_frame(event_volume=100.0),
        _cost_config(),
        spec,
    )

    assert labeled.loc[event_idx, spec.valid_column] == False
    assert labeled.loc[event_idx, "target_volume_pace_ratio_volume_pace_breakout_continuation_30m"] == 1.0
    assert labeled.loc[event_idx, "target_event_direction_volume_pace_breakout_continuation_30m"] == 0


def test_volume_pace_breakout_distribution_has_long_short_and_flat() -> None:
    spec = TARGET_SPECS["volume_pace_breakout_continuation_30m_v1"]
    labeled = apply_volume_pace_breakout_continuation_30m_target(
        _volume_pace_breakout_frame(),
        _cost_config(),
        spec,
    )
    events, skipped = non_overlapping_events(labeled, spec)
    balance = class_balance(events, spec)
    distribution = target_distribution_summary(events, spec)

    assert skipped >= 0
    assert events[spec.entry_ts_column].iloc[1:].gt(events[spec.exit_ts_column].shift(1).iloc[1:]).all()
    assert balance["event_count"] == len(events)
    assert balance["counts"]["long"] >= 1
    assert balance["counts"]["short"] >= 1
    assert balance["counts"]["flat"] >= 1
    assert spec.net_column in distribution


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


def test_late_session_range_resolve_session_close_target_spec_is_distinct() -> None:
    spec = TARGET_SPECS["late_session_range_resolve_session_close_v1"]

    assert spec.target_family == "es_late_session_range_resolve_session_close"
    assert spec.slug == "late_session_range_resolve_session_close"
    assert spec.horizon_bars == 60
    assert "session-close exit" in spec.threshold_description
    assert "target_range_high_late_session_range_resolve_session_close" in spec.target_columns
    assert "target_close_exit_ticks_late_session_range_resolve_session_close" in spec.target_columns


def test_late_session_range_resolve_session_close_label_math() -> None:
    spec = TARGET_SPECS["late_session_range_resolve_session_close_v1"]
    labeled = apply_late_session_range_resolve_session_close_target(
        _late_session_range_resolve_frame(),
        _cost_config(),
        spec,
    )
    range_high = "target_range_high_late_session_range_resolve_session_close"
    range_low = "target_range_low_late_session_range_resolve_session_close"
    range_ticks = "target_range_ticks_late_session_range_resolve_session_close"
    event_direction = "target_event_direction_late_session_range_resolve_session_close"
    breakout_ticks = "target_breakout_ticks_late_session_range_resolve_session_close"
    minutes_to_close = "target_minutes_to_close_late_session_range_resolve_session_close"
    close_exit_ticks = "target_close_exit_ticks_late_session_range_resolve_session_close"

    long_idx = 70
    short_idx = 191
    flat_idx = 312
    assert labeled.loc[59, spec.valid_column] == False

    assert labeled.loc[long_idx, spec.valid_column] == True
    assert labeled.loc[long_idx, range_high] == 100.25
    assert labeled.loc[long_idx, range_low] == 99.75
    assert labeled.loc[long_idx, range_ticks] == 2.0
    assert labeled.loc[long_idx, event_direction] == 1
    assert labeled.loc[long_idx, breakout_ticks] == 1.0
    assert labeled.loc[long_idx, minutes_to_close] == 49.0
    assert labeled.loc[long_idx, spec.direction_column] == 1
    assert labeled.loc[long_idx, spec.nonflat_column] == True
    assert labeled.loc[long_idx, close_exit_ticks] == 6.0
    assert labeled.loc[long_idx, spec.gross_column] == 75.0
    assert labeled.loc[long_idx, spec.net_column] == 50.0

    assert labeled.loc[short_idx, spec.valid_column] == True
    assert labeled.loc[short_idx, event_direction] == -1
    assert labeled.loc[short_idx, breakout_ticks] == 1.0
    assert labeled.loc[short_idx, spec.direction_column] == -1
    assert labeled.loc[short_idx, spec.nonflat_column] == True
    assert labeled.loc[short_idx, close_exit_ticks] == 6.0
    assert labeled.loc[short_idx, spec.gross_column] == 75.0
    assert labeled.loc[short_idx, spec.net_column] == 50.0

    assert labeled.loc[flat_idx, spec.valid_column] == True
    assert labeled.loc[flat_idx, event_direction] == 1
    assert labeled.loc[flat_idx, spec.direction_column] == 0
    assert labeled.loc[flat_idx, spec.nonflat_column] == False
    assert labeled.loc[flat_idx, close_exit_ticks] == 1.0
    assert labeled.loc[flat_idx, spec.gross_column] == 12.5
    assert labeled.loc[flat_idx, spec.net_column] == -12.5


def test_late_session_event_side_does_not_use_future_exit_path() -> None:
    spec = TARGET_SPECS["late_session_range_resolve_session_close_v1"]
    event_direction = "target_event_direction_late_session_range_resolve_session_close"
    base = apply_late_session_range_resolve_session_close_target(
        _late_session_range_resolve_frame(),
        _cost_config(),
        spec,
    )
    mutated_frame = _late_session_range_resolve_frame()
    mutated_frame.loc[80, ["high", "low", "close"]] = [120.0, 119.5, 120.0]
    mutated = apply_late_session_range_resolve_session_close_target(mutated_frame, _cost_config(), spec)

    assert base.loc[70, spec.valid_column] == mutated.loc[70, spec.valid_column]
    assert base.loc[70, event_direction] == mutated.loc[70, event_direction]
    assert base.loc[70, spec.gross_column] == mutated.loc[70, spec.gross_column]
    assert base.loc[70, spec.net_column] == mutated.loc[70, spec.net_column]


def test_late_session_missing_completed_range_invalidates_event() -> None:
    spec = TARGET_SPECS["late_session_range_resolve_session_close_v1"]
    frame = _late_session_range_resolve_frame()
    frame.loc[10, "target_valid"] = False
    labeled = apply_late_session_range_resolve_session_close_target(frame, _cost_config(), spec)

    assert labeled.loc[70, spec.valid_column] == False


def test_late_session_cross_session_or_missing_close_invalidates_event() -> None:
    spec = TARGET_SPECS["late_session_range_resolve_session_close_v1"]
    cross_session = _late_session_range_resolve_frame()
    cross_session.loc[120, "session_segment_id"] = "ES_2024_01_99"
    cross_labeled = apply_late_session_range_resolve_session_close_target(cross_session, _cost_config(), spec)

    missing_close = _late_session_range_resolve_frame()
    missing_close.loc[120, "target_valid"] = False
    missing_labeled = apply_late_session_range_resolve_session_close_target(missing_close, _cost_config(), spec)

    assert cross_labeled.loc[70, spec.valid_column] == False
    assert missing_labeled.loc[70, spec.valid_column] == False


def test_late_session_distribution_non_overlap_and_duplicate_overlap() -> None:
    spec = TARGET_SPECS["late_session_range_resolve_session_close_v1"]
    labeled = apply_late_session_range_resolve_session_close_target(
        _late_session_range_resolve_frame(),
        _cost_config(),
        spec,
    )
    events, skipped = non_overlapping_events(labeled, spec)
    balance = class_balance(events, spec)
    overlap = duplicate_target_overlap(events, spec)
    distribution = target_distribution_summary(events, spec)

    assert skipped == 0
    assert balance["event_count"] == len(events)
    assert balance["counts"]["long"] >= 1
    assert balance["counts"]["short"] >= 1
    assert balance["counts"]["flat"] >= 1
    assert overlap["available"] is True
    assert overlap["overlap_with_current_15m_deadzone"] is not None
    assert spec.net_column in distribution


def test_opening_range_event_capture_v2_target_spec_is_distinct() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_event_capture_30m_v2"]

    assert spec.target_family == "es_opening_range_acceptance_continuation_event_capture_30m"
    assert spec.slug == "opening_range_acceptance_event_capture_30m"
    assert spec.valid_column == "target_valid_opening_range_acceptance_event_capture_30m"
    assert "target_timeout_exit_ticks_opening_range_acceptance_event_capture_30m" in spec.target_columns


def test_opening_range_event_capture_v2_fixed_timeout_math_and_first_event() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_event_capture_30m_v2"]
    labeled = apply_opening_range_acceptance_event_capture_30m_target(
        _opening_range_frame(overlapping_long_rows=True),
        _cost_config(),
        spec,
    )
    event_direction = "target_event_direction_opening_range_acceptance_event_capture_30m"
    timeout_ticks = "target_timeout_exit_ticks_opening_range_acceptance_event_capture_30m"
    event_number = "target_session_event_number_opening_range_acceptance_event_capture_30m"

    assert labeled.loc[29, spec.valid_column] == False
    assert labeled.loc[30, spec.valid_column] == True
    assert labeled.loc[30, event_direction] == 1
    assert labeled.loc[30, event_number] == 1
    assert labeled.loc[30, spec.direction_column] == 1
    assert labeled.loc[30, spec.nonflat_column] == True
    assert labeled.loc[30, timeout_ticks] == -8.0
    assert labeled.loc[30, spec.gross_column] == -100.0
    assert labeled.loc[30, spec.net_column] == -125.0
    assert labeled.loc[31, event_direction] == 1
    assert labeled.loc[31, event_number] == 2
    assert labeled.loc[31, spec.valid_column] == False
    assert labeled.loc[70, event_direction] == -1
    assert labeled.loc[70, spec.valid_column] == False


def test_opening_range_event_capture_v2_uses_timeout_not_future_touch() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_event_capture_30m_v2"]
    favorable = "target_favorable_excursion_ticks_opening_range_acceptance_event_capture_30m"
    base = apply_opening_range_acceptance_event_capture_30m_target(_opening_range_frame(), _cost_config(), spec)
    mutated_frame = _opening_range_frame()
    mutated_frame.loc[40, "high"] = 105.0
    mutated = apply_opening_range_acceptance_event_capture_30m_target(mutated_frame, _cost_config(), spec)

    assert base.loc[30, spec.valid_column] == mutated.loc[30, spec.valid_column]
    assert base.loc[30, favorable] != mutated.loc[30, favorable]
    assert base.loc[30, spec.gross_column] == mutated.loc[30, spec.gross_column]
    assert base.loc[30, spec.net_column] == mutated.loc[30, spec.net_column]
    assert base.loc[30, spec.direction_column] == mutated.loc[30, spec.direction_column]


def test_opening_range_event_capture_v2_rejects_cross_session_timeout() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_event_capture_30m_v2"]
    frame = _opening_range_frame()
    frame.loc[55:, "session_segment_id"] = "ES_2024_01_03"
    labeled = apply_opening_range_acceptance_event_capture_30m_target(frame, _cost_config(), spec)

    assert labeled.loc[30, spec.valid_column] == False


def test_opening_range_event_capture_v2_can_score_first_short_session_event() -> None:
    spec = TARGET_SPECS["opening_range_acceptance_continuation_event_capture_30m_v2"]
    frame = _opening_range_frame()
    frame.loc[30, ["open", "high", "low", "close"]] = [100.0, 100.25, 99.75, 100.0]
    frame.loc[110, ["open", "high", "low", "close"]] = [100.0, 100.25, 99.75, 100.0]
    labeled = apply_opening_range_acceptance_event_capture_30m_target(frame, _cost_config(), spec)

    assert labeled.loc[70, spec.valid_column] == True
    assert labeled.loc[70, spec.direction_column] == -1
    assert labeled.loc[70, spec.gross_column] == -100.0
    assert labeled.loc[70, spec.net_column] == -125.0


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
