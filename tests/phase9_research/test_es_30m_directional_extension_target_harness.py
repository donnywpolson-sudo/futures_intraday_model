from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.es_30m_directional_extension_target_harness import (
    HYPOTHESIS_ID,
    TARGET_DIRECTION_COLUMN,
    TARGET_GROSS_COLUMN,
    TARGET_NET_COLUMN,
    TARGET_NONFLAT_COLUMN,
    TARGET_VALID_COLUMN,
    apply_30m_directional_extension_target,
    class_balance,
    duplicate_target_overlap,
    evaluate_stage_gates,
    is_leakage_feature,
    non_overlapping_events,
    select_model_features,
    validate_target_hypothesis_registered,
)


def _cost_config() -> dict[str, float]:
    return {
        "tick_size": 0.25,
        "tick_value": 12.5,
        "round_turn_cost_dollars": 25.0,
        "min_profit_ticks": 2.0,
        "cost_ticks": 2.0,
    }


def _frame(*, periods: int = 80) -> pd.DataFrame:
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=periods, freq="min")
    open_ = [100.0] * periods
    for idx in range(periods):
        if idx >= 31:
            open_[idx] = 101.25
        if idx >= 50:
            open_[idx] = 98.75
    return pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_segment_id": "ES_2024_01_02",
            "open": open_,
            "high": [value + 0.25 for value in open_],
            "low": [value - 0.25 for value in open_],
            "close": open_,
            "causal_valid": True,
            "valid_ohlcv": True,
            "inside_session": True,
            "feature_input_valid": True,
            "feature_row_valid": True,
            "training_row_valid": True,
            "target_valid": True,
            "target_sign_with_deadzone": [1 if idx % 2 else 0 for idx in range(periods)],
            "is_synthetic": False,
            "roll_window_flag": False,
            "boundary_session_flag": False,
            "feature_signal": range(periods),
        }
    )


def _registry(path: Path, *, status: str = "CANDIDATE", wfa_allowed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "hypotheses": [
                    {
                        "target_hypothesis_id": HYPOTHESIS_ID,
                        "status": status,
                        "wfa_allowed": wfa_allowed,
                        "target_family": "es_directional_extension_30m",
                        "scope": {
                            "profile": "tier_1",
                            "resolved_profile": "tier_1_research",
                            "markets": ["ES"],
                            "years": [2023, 2024],
                        },
                        "description": "fixture",
                        "status_reason": "fixture",
                        "source_reports": [],
                        "next_allowed_actions": ["RUN_ES_30M_DIRECTIONAL_EXTENSION_DISCOVERY_SMOKE"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_registry_requires_candidate_and_es_scope(tmp_path: Path) -> None:
    candidate = _registry(tmp_path / "candidate.json")
    advanced = _registry(tmp_path / "advanced.json", status="DISCOVERY_PASS")
    wfa_allowed = _registry(tmp_path / "wfa.json", wfa_allowed=True)

    assert validate_target_hypothesis_registered(candidate) == []
    assert any("expected CANDIDATE" in error for error in validate_target_hypothesis_registered(advanced))
    assert any("wfa_allowed" in error for error in validate_target_hypothesis_registered(wfa_allowed))


def test_30m_directional_extension_label_math_and_validity() -> None:
    labeled = apply_30m_directional_extension_target(_frame(), _cost_config())

    assert labeled.loc[0, TARGET_VALID_COLUMN] == True
    assert labeled.loc[0, TARGET_DIRECTION_COLUMN] == 1
    assert labeled.loc[0, TARGET_NONFLAT_COLUMN] == True
    assert labeled.loc[0, TARGET_GROSS_COLUMN] == 62.5
    assert labeled.loc[0, TARGET_NET_COLUMN] == 37.5
    assert labeled.loc[25, TARGET_DIRECTION_COLUMN] == -1
    assert labeled.loc[len(labeled) - 1, TARGET_VALID_COLUMN] == False


def test_non_overlap_keeps_only_non_overlapping_30m_events() -> None:
    labeled = apply_30m_directional_extension_target(_frame(periods=100), _cost_config())

    events, skipped = non_overlapping_events(labeled)

    assert len(events) > 0
    assert skipped > 0
    assert events.iloc[1]["target_entry_ts_30m_extension"] > events.iloc[0]["target_exit_ts_30m_extension"]


def test_duplicate_overlap_and_class_balance_are_reported() -> None:
    labeled = apply_30m_directional_extension_target(_frame(periods=120), _cost_config())
    events, _ = non_overlapping_events(labeled)

    overlap = duplicate_target_overlap(events)
    balance = class_balance(events)

    assert overlap["available"] is True
    assert overlap["overlap_with_current_15m_deadzone"] is not None
    assert balance["event_count"] == len(events)
    assert set(balance["counts"]) == {"long", "short", "flat"}


def test_feature_leakage_filter_blocks_targets_costs_and_forward_terms() -> None:
    selected = select_model_features(
        [
            "feature_signal",
            "target_x",
            "label_x",
            "feature_forward_ret",
            "feature_net_edge",
            "feature_cost_drag",
            "feature_mfe_ratio",
            "feature_mae_ratio",
        ]
    )

    assert selected == ["feature_signal"]
    assert is_leakage_feature("feature_signal") is False


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


def test_stage_gates_cover_stop_conditions() -> None:
    assert evaluate_stage_gates(_stage_report())["decision"] == "DISCOVERY_PASS"
    assert evaluate_stage_gates(_stage_report(top_net=-1.0))["decision"] == "STOP_DISCOVERY_NEGATIVE_NET"
    assert evaluate_stage_gates(_stage_report(overlap=0.90))["decision"] == "STOP_DUPLICATE_TARGET"
    assert evaluate_stage_gates(_stage_report(short_count=1))["decision"] == "STOP_CLASS_COLLAPSE"
    assert evaluate_stage_gates(_stage_report(positive_folds=1))["decision"] == "STOP_UNSTABLE_FOLDS"
