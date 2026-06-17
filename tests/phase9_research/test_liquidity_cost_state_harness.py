from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase7_wfa.run_wfa import _fold_masks
from scripts.phase9_research.liquidity_cost_state_harness import (
    CANDIDATE_FEATURES,
    DEFAULT_RUN,
    HYPOTHESIS_ID,
    REQUIRED_BASE_FEATURES,
    _build_report,
    _limit_events_for_selected_folds,
    add_liquidity_cost_features,
    evaluate_gates,
    run_harness,
    score_liquidity_state,
    validate_hypothesis_registered,
)
from scripts.phase9_research.tier1_cost_clearability_event_harness import (
    COST_COLUMN,
    GROSS_COLUMN,
    OPPORTUNITY_COLUMN,
    apply_opportunity_labels,
    non_overlapping_events,
)


def _candidate_registry(path: Path, *, status: str = "CANDIDATE", wfa_allowed: bool = False) -> Path:
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
                "allowed_transitions": {
                    "CANDIDATE": ["DISCOVERY_PASS", "REJECTED", "QUARANTINED"],
                    "DISCOVERY_PASS": ["CONFIRMATION_PASS", "REJECTED", "QUARANTINED"],
                    "CONFIRMATION_PASS": ["FROZEN", "REJECTED", "QUARANTINED"],
                    "FROZEN": ["RETIRED", "QUARANTINED"],
                    "REJECTED": [],
                    "RETIRED": [],
                    "QUARANTINED": [],
                },
                "hypotheses": [
                    {
                        "hypothesis_id": HYPOTHESIS_ID,
                        "status": status,
                        "wfa_allowed": wfa_allowed,
                        "feature_family": "liquidity_cost_state",
                        "scope": {
                            "profile": "tier_1",
                            "resolved_profile": "tier_1_research",
                            "markets": ["ES"],
                            "years": [2024],
                        },
                        "description": "fixture",
                        "status_reason": "fixture",
                        "source_reports": [],
                        "next_allowed_actions": ["RUN_DISCOVERY_HARNESS"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _base_events() -> pd.DataFrame:
    ts = pd.date_range("2024-01-01T00:00:00Z", periods=8, freq="20min")
    frame = pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": 2024,
            "session_id": "session",
            "session_segment_id": "segment",
            "target_entry_ts": ts,
            "target_exit_ts": ts + pd.Timedelta(minutes=15),
            GROSS_COLUMN: [50.0, 45.0, 40.0, 35.0, 8.0, 7.0, 6.0, 5.0],
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
            "feature_realized_vol_15": [10.0, 9.0, 8.0, 7.0, 1.0, 1.0, 1.0, 1.0],
            "feature_realized_vol_60": [20.0, 18.0, 16.0, 14.0, 2.0, 2.0, 2.0, 2.0],
            "feature_realized_range_30": [50.0, 45.0, 40.0, 35.0, 5.0, 5.0, 5.0, 5.0],
            "feature_realized_range_60": [80.0, 70.0, 60.0, 50.0, 8.0, 8.0, 8.0, 8.0],
            "feature_volume_z_60": [3.0, 2.5, 2.0, 1.5, -2.0, -2.0, -2.0, -2.0],
            "feature_range_per_volume": [5.0, 5.0, 4.0, 4.0, 0.5, 0.5, 0.5, 0.5],
            "feature_ret_1": range(8),
            "feature_ret_5": range(8),
            "feature_range_norm": range(8),
            "feature_true_range": range(8),
            "feature_ewma_vol_20": range(8),
            "feature_volume_z_20": range(8),
        }
    )
    labeled = apply_opportunity_labels(frame, {"ES": 10.0})
    events, _ = non_overlapping_events(labeled)
    return add_liquidity_cost_features(events)


def _fold(fold_id: str = "ES_research_0001") -> dict[str, object]:
    return {
        "market": "ES",
        "fold_id": fold_id,
        "split_group": "research",
        "train_start": "2024-01-01T00:00:00+00:00",
        "purged_train_end": "2024-01-01T00:59:00+00:00",
        "test_start": "2024-01-01T01:00:00+00:00",
        "test_end": "2024-01-01T03:00:00+00:00",
        "is_final_holdout": False,
        "final_holdout": False,
        "selection_allowed": True,
    }


def _gate_report(*, control_fail: bool = False, underpowered: bool = False) -> dict[str, object]:
    model_top = 5.0
    control_top = 6.0 if control_fail else 1.0
    scored = 100 if underpowered else 1000
    return {
        "scope": {"markets": ["ES", "CL", "ZN", "6E"]},
        "failures": [],
        "market_stage_summaries": {
            market: {
                stage: {
                    "scored_event_count": scored,
                    "low_friction_selected_event_count": 400,
                    "low_friction_oracle_net_per_event": 4.0,
                    "all_events_oracle_net_per_event": 1.0,
                }
                for stage in ("discovery", "confirmation")
            }
            for market in ("ES", "CL", "ZN", "6E")
        },
        "stage_summaries": {
            stage: {
                "scorers": {
                    "liquidity_state": {
                        "low_friction_oracle_net_per_event": 4.0,
                        "top_decile_oracle_net_per_event": model_top,
                        "all_events_oracle_net_per_event": 1.0,
                    },
                    "random_score": {"top_decile_oracle_net_per_event": control_top},
                    "inverse_score": {"top_decile_oracle_net_per_event": control_top},
                    "market_year_session_baseline": {
                        "top_decile_oracle_net_per_event": control_top
                    },
                    "baseline_ohlcv_proxy": {"top_decile_oracle_net_per_event": control_top},
                }
            }
            for stage in ("discovery", "confirmation")
        },
        "concentration": {
            "market": {"max_share": 0.25},
            "fold": {"max_share": 0.20},
            "hour": {"max_share": 0.20},
        },
    }


def test_candidate_registry_requires_candidate_not_wfa_allowed(tmp_path: Path) -> None:
    registry = _candidate_registry(tmp_path / "registry.json")
    advanced_registry = _candidate_registry(
        tmp_path / "advanced_registry.json",
        status="DISCOVERY_PASS",
        wfa_allowed=False,
    )

    assert validate_hypothesis_registered(registry) == []
    assert any("expected CANDIDATE" in error for error in validate_hypothesis_registered(advanced_registry))


def test_liquidity_cost_feature_math_uses_pre_entry_cost_state_columns() -> None:
    events = _base_events()

    assert set(CANDIDATE_FEATURES).issubset(events.columns)
    assert events.loc[0, "feature_cost_to_realized_vol_15"] == 1.0
    assert events.loc[0, "feature_cost_to_realized_range_30"] == 0.2
    assert events.loc[0, "feature_cost_to_volume_z_60"] == 2.5
    assert OPPORTUNITY_COLUMN in events.columns


def test_liquidity_score_ranks_lower_friction_above_higher_friction() -> None:
    events = _base_events()
    train = events.iloc[:4].copy()
    params = {
        feature: {
            "median": float(train[feature].median()),
            "mad": float((train[feature] - train[feature].median()).abs().median()) or 1.0,
        }
        for feature in CANDIDATE_FEATURES[:-1]
    }

    scores = score_liquidity_state(events, params)

    assert scores.iloc[0] > scores.iloc[-1]


def test_event_cap_preserves_train_and_test_for_each_requested_fold() -> None:
    ts = pd.date_range("2023-12-01T00:00:00Z", periods=360, freq="6h")
    frame = pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": [2023 if item.year == 2023 else 2024 for item in ts],
            "session_id": "session",
            "session_segment_id": "segment",
            "target_entry_ts": ts,
            "target_exit_ts": ts + pd.Timedelta(minutes=15),
            GROSS_COLUMN: [50.0 if idx % 2 else 5.0 for idx in range(len(ts))],
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
            "feature_realized_vol_15": [10.0 + idx % 5 for idx in range(len(ts))],
            "feature_realized_vol_60": [20.0 + idx % 5 for idx in range(len(ts))],
            "feature_realized_range_30": [50.0 + idx % 5 for idx in range(len(ts))],
            "feature_realized_range_60": [80.0 + idx % 5 for idx in range(len(ts))],
            "feature_volume_z_60": [1.0 + idx % 5 for idx in range(len(ts))],
            "feature_range_per_volume": [5.0 + idx % 5 for idx in range(len(ts))],
        }
    )
    events, _ = non_overlapping_events(apply_opportunity_labels(frame, {"ES": 10.0}))
    events = add_liquidity_cost_features(events)
    folds = [
        {
            **_fold("ES_research_0001"),
            "train_start": "2023-12-01T00:00:00+00:00",
            "purged_train_end": "2023-12-31T23:59:00+00:00",
            "test_start": "2024-01-01T00:00:00+00:00",
            "test_end": "2024-01-15T23:59:00+00:00",
        },
        {
            **_fold("ES_research_0007"),
            "train_start": "2024-01-01T00:00:00+00:00",
            "purged_train_end": "2024-01-31T23:59:00+00:00",
            "test_start": "2024-02-01T00:00:00+00:00",
            "test_end": "2024-02-15T23:59:00+00:00",
        },
    ]

    limited = _limit_events_for_selected_folds(events, folds, 80)

    for fold in folds:
        train_mask, test_mask = _fold_masks(limited, fold, limited["cost_clearable_15m"].astype(int))
        assert train_mask.any(), fold["fold_id"]
        assert test_mask.any(), fold["fold_id"]


def test_gate_evaluator_pass_underpowered_and_control_failure() -> None:
    assert evaluate_gates(_gate_report())["decision"] == "CONFIRMATION_PASS"
    assert evaluate_gates(_gate_report(underpowered=True))["decision"] == "STOP_UNDERPOWERED"
    assert evaluate_gates(_gate_report(control_fail=True))["decision"] == "REJECTED"


def test_report_schema_is_feasibility_only_and_not_wfa() -> None:
    events = _base_events()
    report = _build_report(
        run="fixture",
        scope={
            "requested_profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "markets": ["ES"],
            "years": [2024],
        },
        input_paths={"split_plan": "reports/wfa/split_plan.json"},
        input_hashes={"reports/wfa/split_plan.json": "hash"},
        folds=[_fold()],
        events=events,
        skipped_overlap_count=0,
        fold_results=[],
        selected_low_friction=pd.DataFrame(),
        failures=["fixture intentionally has no fold results"],
    )

    for key in [
        "hypothesis_id",
        "not_trading_model",
        "not_wfa",
        "uses_saved_predictions",
        "candidate_features",
        "controls",
        "gates",
        "decision",
        "do_not_do",
    ]:
        assert key in report
    assert report["not_wfa"] is True
    assert report["uses_saved_predictions"] is False


def test_run_harness_dry_run_does_not_write_reports(tmp_path: Path) -> None:
    input_root = tmp_path / "data" / "feature_matrices" / "baseline"
    reports_root = tmp_path / "reports" / "pipeline_audit"
    registry = _candidate_registry(tmp_path / "manifests" / "feature_hypotheses" / "registry.json")
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    costs_config = tmp_path / "configs" / "costs.yaml"
    split_plan = tmp_path / "reports" / "wfa" / "split_plan.json"
    feature_cols = list(REQUIRED_BASE_FEATURES) + [
        "feature_ret_1",
        "feature_ret_5",
        "feature_range_norm",
        "feature_true_range",
        "feature_ewma_vol_20",
        "feature_volume_z_20",
    ]
    input_root.mkdir(parents=True)
    (input_root / "feature_cols.json").write_text(json.dumps(feature_cols), encoding="utf-8")
    frame = _base_events().drop(columns=[COST_COLUMN, OPPORTUNITY_COLUMN, "event_hour"])
    market_path = input_root / "ES" / "2024.parquet"
    market_path.parent.mkdir(parents=True)
    frame.to_parquet(market_path, index=False)
    profile_config.parent.mkdir(parents=True)
    profile_config.write_text(
        "profiles:\n  tier_1_research:\n    markets: [ES]\n    years: [2024]\naliases:\n  tier_1: tier_1_research\n",
        encoding="utf-8",
    )
    costs_config.write_text(
        "markets:\n  ES:\n    round_turn_cost_dollars: 10.0\n",
        encoding="utf-8",
    )
    split_plan.parent.mkdir(parents=True)
    split_plan.write_text(
        json.dumps(
            {
                "folds": [_fold()],
            }
        ),
        encoding="utf-8",
    )

    report = run_harness(
        run="fixture",
        profile="tier_1",
        profile_config=profile_config,
        costs_config=costs_config,
        input_root=input_root,
        split_plan=split_plan,
        reports_root=reports_root,
        registry_path=registry,
        write_reports=False,
    )

    assert report["run"] == "fixture"
    assert report["hypothesis_id"] == HYPOTHESIS_ID
    assert not reports_root.exists()
