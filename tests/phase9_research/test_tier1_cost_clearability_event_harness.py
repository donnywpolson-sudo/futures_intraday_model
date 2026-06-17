from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.tier1_cost_clearability_event_harness import (
    _build_report,
    _limit_events_for_folds,
    apply_opportunity_labels,
    evaluate_gates,
    non_overlapping_events,
    select_model_features,
)
from scripts.phase7_wfa.run_wfa import _fold_masks


def _base_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.to_datetime(
                [
                    "2024-01-01T00:00:00Z",
                    "2024-01-01T00:05:00Z",
                    "2024-01-01T00:16:00Z",
                    "2024-01-01T00:31:00Z",
                ]
            ),
            "market": ["ES", "ES", "ES", "ES"],
            "year": [2024, 2024, 2024, 2024],
            "session_segment_id": ["s1", "s1", "s1", "s1"],
            "target_entry_ts": pd.to_datetime(
                [
                    "2024-01-01T00:00:00Z",
                    "2024-01-01T00:05:00Z",
                    "2024-01-01T00:16:00Z",
                    None,
                ]
            ),
            "target_exit_ts": pd.to_datetime(
                [
                    "2024-01-01T00:15:00Z",
                    "2024-01-01T00:20:00Z",
                    "2024-01-01T00:31:00Z",
                    None,
                ]
            ),
            "target_gross_dollars_15m": [50.0, 60.0, 5.0, None],
            "target_valid": [True, True, True, False],
            "causal_valid": [True, True, True, True],
            "valid_ohlcv": [True, True, True, True],
            "inside_session": [True, True, True, True],
            "feature_input_valid": [True, True, True, True],
            "feature_row_valid": [True, True, True, True],
            "training_row_valid": [True, True, True, True],
            "is_synthetic": [False, False, False, False],
            "roll_window_flag": [False, False, False, False],
            "boundary_session_flag": [False, False, False, False],
            "feature_signal": [1.0, 2.0, 3.0, 4.0],
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
        "test_end": "2024-01-01T00:31:00+00:00",
        "is_final_holdout": False,
        "final_holdout": False,
        "selection_allowed": True,
    }


def test_non_overlap_event_conversion_by_market_year_session() -> None:
    labeled = apply_opportunity_labels(_base_frame(), {"ES": 10.0})

    events, skipped = non_overlapping_events(labeled)

    assert skipped == 1
    assert list(events["target_entry_ts"]) == list(
        pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-01T00:16:00Z"])
    )


def test_no_target_future_cost_net_gross_columns_enter_x() -> None:
    selected = select_model_features(
        [
            "feature_signal",
            "target_alpha",
            "label_alpha",
            "future_alpha",
            "entry_price",
            "exit_price",
            "feature_forward_return",
            "feature_gross_return",
            "feature_net_return",
            "feature_pnl",
            "feature_profit",
            "feature_cost_drag",
            "cost_clearable_15m",
            "opportunity_net_dollars",
        ]
    )

    assert selected == ["feature_signal"]


def test_synthetic_roll_boundary_session_invalid_rows_excluded() -> None:
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
        row["feature_signal"] = float(idx)
        if column in {"is_synthetic", "roll_window_flag", "boundary_session_flag"}:
            row[column] = True
        elif column in {"causal_valid", "feature_input_valid", "feature_row_valid", "target_valid"}:
            row[column] = False
        rows.append(row)
    session_end = _base_frame().iloc[-1].copy()
    session_end["ts"] = pd.Timestamp("2024-01-01T03:00:00Z")
    rows.append(session_end)
    labeled = apply_opportunity_labels(pd.DataFrame(rows), {"ES": 10.0})

    events, _ = non_overlapping_events(labeled)

    assert len(events) == 1
    assert events.iloc[0]["feature_signal"] == 0.0


def test_opportunity_label_math_uses_abs_gross_minus_config_cost() -> None:
    frame = _base_frame().iloc[:3].copy()
    frame["market"] = ["ES", "CL", "CL"]
    frame["target_gross_dollars_15m"] = [-20.0, 10.0, 2.0]

    labeled = apply_opportunity_labels(frame, {"ES": 10.0, "CL": 3.0})

    assert list(labeled["target_estimated_cost_dollars"]) == [10.0, 3.0, 3.0]
    assert list(labeled["opportunity_net_dollars"]) == [10.0, 7.0, -1.0]
    assert list(labeled["cost_clearable_15m"]) == [True, True, False]


def test_max_event_cap_preserves_requested_fold_train_and_test_rows() -> None:
    train = _base_frame().copy()
    train["ts"] = pd.date_range("2023-12-31T21:00:00Z", periods=len(train), freq="20min")
    train["target_entry_ts"] = train["ts"]
    train["target_exit_ts"] = train["ts"] + pd.Timedelta(minutes=15)
    test = _base_frame().copy()
    test["ts"] = pd.date_range("2024-01-01T00:00:00Z", periods=len(test), freq="20min")
    test["target_entry_ts"] = test["ts"]
    test["target_exit_ts"] = test["ts"] + pd.Timedelta(minutes=15)
    frame = pd.concat([train, test], ignore_index=True)
    labeled = apply_opportunity_labels(frame, {"ES": 10.0})
    events, _ = non_overlapping_events(labeled)

    limited = _limit_events_for_folds(events, [_fold()], 4)
    train_mask, test_mask = _fold_masks(limited, _fold(), limited["cost_clearable_15m"].astype(int))

    assert len(limited) == 4
    assert train_mask.any()
    assert test_mask.any()


def _gate_report(*, controls: bool = True, underpowered: bool = False) -> dict[str, object]:
    markets = ["ES", "CL", "ZN", "6E"]
    fold_results = []
    for market in markets:
        for idx in range(12):
            fold_results.append(
                {
                    "fold_id": f"{market}_research_{idx + 1:04d}",
                    "stage": "discovery" if idx < 6 else "confirmation",
                    "market": market,
                    "scored_event_count": 1000,
                    "positive_top_5pct": True,
                    "bucket_metrics": {
                        "model": {
                            "top_5pct": {
                                "selected_event_count": 100,
                                "oracle_gross_upper_bound": 10000.0,
                                "oracle_cost_dollars": 1000.0,
                                "oracle_net_upper_bound": 9000.0,
                            }
                        }
                    },
                }
            )
    scorers = {
        "model": {
            "top_5pct_selected_event_count": 2400,
            "top_5pct_oracle_net_upper_bound": 24000.0,
            "top_5pct_oracle_net_upper_bound_per_event": 10.0,
        },
        "random_label": {
            "top_5pct_selected_event_count": 2400,
            "top_5pct_oracle_net_upper_bound": 2400.0,
            "top_5pct_oracle_net_upper_bound_per_event": 1.0,
        },
        "shuffled_feature": {
            "top_5pct_selected_event_count": 2400,
            "top_5pct_oracle_net_upper_bound": 2400.0,
            "top_5pct_oracle_net_upper_bound_per_event": 1.0,
        },
        "market_year_session_baseline": {
            "top_5pct_selected_event_count": 2400,
            "top_5pct_oracle_net_upper_bound": 2400.0,
            "top_5pct_oracle_net_upper_bound_per_event": 1.0,
        },
        "inverse_score": {
            "top_5pct_selected_event_count": 2400,
            "top_5pct_oracle_net_upper_bound": 2400.0,
            "top_5pct_oracle_net_upper_bound_per_event": 1.0,
        },
    }
    if not controls:
        scorers.pop("random_label")
    top_5_by_market = {
        market: {
            "selected_event_count": 1200,
            "oracle_gross_upper_bound": 100000.0,
            "oracle_cost_dollars": 10000.0,
            "oracle_net_upper_bound": 90000.0,
        }
        for market in markets
    }
    if underpowered:
        top_5_by_market["CL"]["selected_event_count"] = 99
    return {
        "scope": {"markets": markets},
        "event_counts": {"by_market": {market: 1000 for market in markets}},
        "fold_results": fold_results,
        "stage_summaries": {
            "discovery": {"scorers": dict(scorers)},
            "confirmation": {"scorers": dict(scorers)},
        },
        "top_5_by_market": top_5_by_market,
        "concentration": {
            "fold": {"max_share": 0.2},
            "market": {"max_share": 0.2},
            "hour": {"max_share": 0.2},
        },
        "failures": [],
    }


def test_gate_evaluator_pass_and_underpowered_fixtures() -> None:
    assert evaluate_gates(_gate_report())["decision"] == "PASS"
    assert evaluate_gates(_gate_report(underpowered=True))["decision"] == "STOP_UNDERPOWERED"


def test_report_schema_includes_required_audit_sections() -> None:
    labeled = apply_opportunity_labels(_base_frame(), {"ES": 10.0})
    events, skipped = non_overlapping_events(labeled)

    report = _build_report(
        run="fixture",
        scope={"requested_profile": "tier_1", "resolved_profile": "tier_1_research", "markets": ["ES"], "years": [2024]},
        input_paths={"split_plan": "reports/wfa/split_plan.json"},
        input_hashes={"reports/wfa/split_plan.json": "hash"},
        folds=[_fold()],
        events=events,
        skipped_overlap_count=skipped,
        fold_results=[],
        top_rows=pd.DataFrame(),
        failures=["fixture intentionally has no fold results"],
    )

    for key in [
        "scope",
        "input_paths",
        "input_hashes",
        "controls",
        "concentration",
        "gates",
        "decision",
        "event_counts",
        "class_balance",
    ]:
        assert key in report


def test_controls_are_required_for_pass() -> None:
    result = evaluate_gates(_gate_report(controls=False))

    assert result["decision"] == "STOP_BRANCH_PERMANENTLY"
    control_gate = [
        gate
        for gate in result["gates"]
        if gate["gate"] == "model_beats_all_controls_discovery_and_confirmation"
    ][0]
    assert control_gate["pass"] is False
