from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase7_wfa.run_wfa import _fold_masks
from scripts.phase9_research.directional_path_quality_target_harness import (
    DEFAULT_TARGET_REGISTRY,
    DIRECTION_COLUMN,
    HYPOTHESIS_ID,
    LABEL_COLUMN,
    QUALITY_COST_COLUMN,
    QUALITY_GROSS_COLUMN,
    _build_report,
    _limit_events_for_selected_folds,
    apply_directional_path_quality_labels,
    evaluate_gates,
    is_leakage_feature,
    non_overlapping_events,
    select_model_features,
    validate_target_hypothesis_registered,
)


def _target_registry(path: Path, *, status: str = "CANDIDATE", wfa_allowed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "allowed_statuses": [
                    "CANDIDATE",
                    "DISCOVERY_PASS",
                    "CONFIRMATION_PASS",
                    "FROZEN",
                    "REJECTED",
                    "RETIRED",
                    "QUARANTINED",
                ],
                "wfa_allowed_statuses": ["FROZEN"],
                "allowed_transitions": {},
                "hypotheses": [
                    {
                        "target_hypothesis_id": HYPOTHESIS_ID,
                        "status": status,
                        "wfa_allowed": wfa_allowed,
                        "target_family": "directional_path_quality",
                        "scope": {
                            "profile": "tier_1",
                            "resolved_profile": "tier_1_research",
                            "markets": ["ES"],
                            "years": [2024],
                        },
                        "description": "fixture",
                        "status_reason": "fixture",
                        "source_reports": [],
                        "next_allowed_actions": ["RUN_PHASE9_TARGET_HARNESS"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _market_configs() -> dict[str, dict[str, float]]:
    return {
        "ES": {
            "round_turn_cost_dollars": 10.0,
            "estimated_cost_ticks": 2.0,
            "min_profit_ticks": 2.0,
            "tick_value": 5.0,
        }
    }


def _base_frame() -> pd.DataFrame:
    ts = pd.date_range("2024-01-01T00:00:00Z", periods=6, freq="20min")
    return pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_segment_id": "segment",
            "target_entry_ts": ts,
            "target_exit_ts": ts + pd.Timedelta(minutes=15),
            "target_ret_ticks_15m": [8.0, -8.0, 8.0, -8.0, 2.0, 10.0],
            "target_gross_dollars_15m": [40.0, -40.0, 40.0, -40.0, 10.0, 50.0],
            "target_estimated_cost_ticks": 2.0,
            "target_estimated_cost_dollars": 10.0,
            "target_sign_with_deadzone": [1, -1, 1, -1, 0, 1],
            "mfe_ticks_15m": [9.0, 2.0, 9.0, 5.0, 2.0, 11.0],
            "mae_ticks_15m": [-1.0, -9.0, -5.0, -9.0, -1.0, -1.0],
            "target_fade_success_15m": [True, True, True, False, False, False],
            "target_valid": True,
            "causal_valid": True,
            "valid_ohlcv": True,
            "inside_session": True,
            "feature_input_valid": True,
            "feature_row_valid": True,
            "training_row_valid": True,
            "is_synthetic": False,
            "roll_window_flag": False,
            "boundary_session_flag": False,
            "feature_signal": [1.0, 1.0, -1.0, -1.0, 0.0, 2.0],
        }
    )


def _fold(fold_id: str = "ES_research_0001") -> dict[str, object]:
    return {
        "market": "ES",
        "fold_id": fold_id,
        "split_group": "research",
        "train_start": "2023-01-01T00:00:00+00:00",
        "purged_train_end": "2023-12-31T23:59:00+00:00",
        "test_start": "2024-01-01T00:00:00+00:00",
        "test_end": "2024-01-01T03:00:00+00:00",
        "is_final_holdout": False,
        "final_holdout": False,
        "selection_allowed": True,
    }


def test_repo_target_hypothesis_registry_blocks_rejected_hypothesis() -> None:
    errors = validate_target_hypothesis_registered(DEFAULT_TARGET_REGISTRY)

    assert any("expected CANDIDATE" in error for error in errors)


def test_target_registry_requires_candidate_not_wfa_allowed(tmp_path: Path) -> None:
    candidate = _target_registry(tmp_path / "registry.json")
    advanced = _target_registry(tmp_path / "advanced.json", status="CONFIRMATION_PASS")
    wfa_allowed = _target_registry(tmp_path / "wfa.json", wfa_allowed=True)

    assert validate_target_hypothesis_registered(candidate) == []
    assert any("expected CANDIDATE" in error for error in validate_target_hypothesis_registered(advanced))
    assert any("wfa_allowed" in error for error in validate_target_hypothesis_registered(wfa_allowed))


def test_directional_path_quality_label_math() -> None:
    labeled = apply_directional_path_quality_labels(_base_frame(), _market_configs())

    assert list(labeled[LABEL_COLUMN]) == [True, True, False, False, False, True]
    assert list(labeled[DIRECTION_COLUMN]) == [1, -1, 0, 0, 0, 1]
    assert list(labeled[QUALITY_GROSS_COLUMN]) == [40.0, 40.0, 0.0, 0.0, 0.0, 50.0]
    assert list(labeled[QUALITY_COST_COLUMN]) == [10.0] * 6


def test_non_overlap_event_conversion_by_market_year_session() -> None:
    frame = _base_frame()
    frame.loc[1, "target_entry_ts"] = pd.Timestamp("2024-01-01T00:05:00Z")
    frame.loc[1, "target_exit_ts"] = pd.Timestamp("2024-01-01T00:20:00Z")
    session_end = frame.iloc[-1].copy()
    session_end["ts"] = pd.Timestamp("2024-01-01T03:00:00Z")
    session_end["target_entry_ts"] = session_end["ts"]
    session_end["target_exit_ts"] = session_end["ts"] + pd.Timedelta(minutes=15)
    session_end["target_valid"] = False
    frame = pd.concat([frame, pd.DataFrame([session_end])], ignore_index=True)
    labeled = apply_directional_path_quality_labels(frame, _market_configs())

    events, skipped = non_overlapping_events(labeled)

    assert skipped == 1
    assert len(events) == 5


def test_invalid_synthetic_roll_boundary_rows_excluded() -> None:
    rows = []
    for idx, column in enumerate(
        [
            None,
            "is_synthetic",
            "roll_window_flag",
            "boundary_session_flag",
            "causal_valid",
            "feature_input_valid",
            "feature_row_valid",
            "target_valid",
        ]
    ):
        row = _base_frame().iloc[0].copy()
        row["ts"] = pd.Timestamp("2024-01-01T00:00:00Z") + pd.Timedelta(minutes=idx * 20)
        row["target_entry_ts"] = row["ts"]
        row["target_exit_ts"] = row["ts"] + pd.Timedelta(minutes=15)
        if column in {"is_synthetic", "roll_window_flag", "boundary_session_flag"}:
            row[column] = True
        elif column in {"causal_valid", "feature_input_valid", "feature_row_valid", "target_valid"}:
            row[column] = False
        rows.append(row)
    labeled = apply_directional_path_quality_labels(pd.DataFrame(rows), _market_configs())

    events, _ = non_overlapping_events(labeled)

    assert len(events) == 1


def test_leakage_guard_blocks_target_future_path_and_cost_columns() -> None:
    selected = select_model_features(
        [
            "feature_signal",
            "target_x",
            "label_x",
            "future_x",
            "entry_x",
            "exit_x",
            "feature_forward_ret",
            "feature_gross_ret",
            "feature_net_ret",
            "feature_pnl",
            "feature_profit",
            "feature_cost_drag",
            "feature_mfe_ratio",
            "feature_mae_ratio",
            LABEL_COLUMN,
        ]
    )

    assert selected == ["feature_signal"]
    assert is_leakage_feature("feature_target_like") is False


def test_event_cap_preserves_train_and_test_for_requested_fold() -> None:
    train = _base_frame().copy()
    train["ts"] = pd.date_range("2023-12-31T21:00:00Z", periods=len(train), freq="20min")
    train["target_entry_ts"] = train["ts"]
    train["target_exit_ts"] = train["ts"] + pd.Timedelta(minutes=15)
    test = _base_frame().copy()
    test["ts"] = pd.date_range("2024-01-01T00:00:00Z", periods=len(test), freq="20min")
    test["target_entry_ts"] = test["ts"]
    test["target_exit_ts"] = test["ts"] + pd.Timedelta(minutes=15)
    labeled = apply_directional_path_quality_labels(pd.concat([train, test]), _market_configs())
    events, _ = non_overlapping_events(labeled)

    limited = _limit_events_for_selected_folds(events, [_fold()], 4)
    train_mask, test_mask = _fold_masks(limited, _fold(), limited[LABEL_COLUMN].astype(int))

    assert len(limited) == 4
    assert train_mask.any()
    assert test_mask.any()


def _gate_report(
    *,
    underpowered: bool = False,
    duplicate: bool = False,
    control_fail: bool = False,
    concentration_fail: bool = False,
) -> dict[str, object]:
    markets = ["ES", "CL", "ZN", "6E"]
    fold_results = []
    for market in markets:
        for idx in range(12):
            fold_results.append(
                {
                    "market": market,
                    "stage": "discovery" if idx < 6 else "confirmation",
                    "positive_top_5pct": True,
                }
            )
    scorer_model = {
        "top_5pct_target_precision": 0.8 if not control_fail else 0.4,
        "top_5pct_target_quality_oracle_net_upper_bound_per_event": 10.0 if not control_fail else 1.0,
    }
    scorer_control = {
        "top_5pct_target_precision": 0.5,
        "top_5pct_target_quality_oracle_net_upper_bound_per_event": 5.0,
    }
    return {
        "scope": {"markets": markets},
        "failures": [],
        "class_balance": {
            "by_market": [
                {
                    "market": market,
                    "quality_count": 100 if underpowered else 6000,
                    "long_count": 100 if underpowered else 2000,
                    "short_count": 100 if underpowered else 2000,
                }
                for market in markets
            ]
        },
        "duplicate_target_overlap": {
            "overlap_with_first_hit_proxy": 0.90 if duplicate else 0.50
        },
        "market_stage_summaries": {
            market: {
                stage: {
                    "scorers": {
                        "model": scorer_model,
                        "random_label": scorer_control,
                        "shuffled_feature": scorer_control,
                        "market_year_session_baseline": scorer_control,
                        "current_deadzone_baseline": scorer_control,
                        "inverse_score": scorer_control,
                        "no_trade_baseline": scorer_control,
                    }
                }
                for stage in ("discovery", "confirmation")
            }
            for market in markets
        },
        "fold_results": fold_results,
        "concentration": {
            "market_shares": {
                "ES": 0.40 if concentration_fail else 0.25,
                "CL": 0.20 if concentration_fail else 0.25,
                "ZN": 0.20 if concentration_fail else 0.25,
                "6E": 0.20 if concentration_fail else 0.25,
            },
            "fold": {"max_share": 0.2},
            "hour": {"max_share": 0.2},
            "side": {"max_share": 0.6},
        },
        "top_5_by_market": {
            market: {
                "target_quality_oracle_gross_upper_bound": 10000.0,
                "target_quality_oracle_cost_dollars": 1000.0,
            }
            for market in markets
        },
    }


def test_gate_evaluator_pass_and_fail_fixtures() -> None:
    assert evaluate_gates(_gate_report())["decision"] == "CONFIRMATION_PASS"
    assert evaluate_gates(_gate_report(underpowered=True))["decision"] == "STOP_UNDERPOWERED"
    assert evaluate_gates(_gate_report(duplicate=True))["decision"] == "STOP_DUPLICATE_TARGET"
    assert evaluate_gates(_gate_report(control_fail=True))["decision"] == "REJECTED"
    assert evaluate_gates(_gate_report(concentration_fail=True))["decision"] == "REJECTED"


def test_report_schema_contains_target_sections() -> None:
    labeled = apply_directional_path_quality_labels(_base_frame(), _market_configs())
    events, _ = non_overlapping_events(labeled)
    fold_results = [
        {
            "fold_id": "ES_research_0001",
            "stage": "discovery",
            "market": "ES",
            "scored_event_count": 10,
            "positive_top_5pct": True,
            "bucket_metrics": {
                scorer: {
                    "top_5pct": {
                        "selected_event_count": 1,
                        "target_positive_count": 1,
                        "target_quality_oracle_gross_upper_bound": 100.0,
                        "target_quality_oracle_cost_dollars": 10.0,
                        "target_quality_oracle_net_upper_bound": 90.0,
                    }
                }
                for scorer in (
                    "model",
                    "random_label",
                    "shuffled_feature",
                    "market_year_session_baseline",
                    "current_deadzone_baseline",
                    "inverse_score",
                    "no_trade_baseline",
                )
            },
        }
    ]

    report = _build_report(
        run="fixture",
        scope={"markets": ["ES"], "years": [2024], "resolved_profile": "tier_1_research"},
        input_paths={"x": "y"},
        input_hashes={"x": "hash"},
        folds=[_fold()],
        events=events,
        skipped_overlap_count=0,
        fold_results=fold_results,
        selected_top_5=events.head(2),
        failures=[],
    )

    assert report["harness_type"] == "phase9_target_construction_feasibility_only"
    assert report["not_wfa"] is True
    assert report["uses_saved_predictions"] is False
    assert "label_definition" in report
    assert "duplicate_target_overlap" in report
    assert "controls" in report
    assert "concentration" in report
    assert "gates" in report
