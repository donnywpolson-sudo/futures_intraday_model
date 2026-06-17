from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.tier1_market_balanced_cost_clearability_harness import (
    _build_report,
    _fold_result,
    _limit_events_for_selected_folds,
    _top_5_by_market,
    apply_opportunity_labels,
    evaluate_gates,
    non_overlapping_events,
    resolve_profile,
    select_model_features,
)
from scripts.phase7_wfa.run_wfa import _fold_masks


def _profile_config(path: Path) -> Path:
    path.write_text(
        """
aliases:
  tier_1: tier_1_research
profiles:
  tier_1_research:
    markets: [ES, CL, ZN, 6E]
    years: [2023, 2024]
""".strip(),
        encoding="utf-8",
    )
    return path


def _base_frame(market: str = "ES") -> pd.DataFrame:
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
            "market": [market] * 4,
            "year": [2024] * 4,
            "session_segment_id": ["s1"] * 4,
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


def _fold(market: str = "ES", fold_id: str | None = None) -> dict[str, object]:
    return {
        "market": market,
        "fold_id": fold_id or f"{market}_research_0001",
        "split_group": "research",
        "train_start": "2023-01-01T00:00:00+00:00",
        "purged_train_end": "2023-12-31T23:59:00+00:00",
        "test_start": "2024-01-01T00:00:00+00:00",
        "test_end": "2024-01-01T23:59:00+00:00",
        "is_final_holdout": False,
        "final_holdout": False,
        "selection_allowed": True,
    }


def _dated_fold(
    market: str,
    fold_id: str,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
) -> dict[str, object]:
    return {
        "market": market,
        "fold_id": fold_id,
        "split_group": "research",
        "train_start": train_start,
        "purged_train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        "is_final_holdout": False,
        "final_holdout": False,
        "selection_allowed": True,
    }


def _balanced_report(
    *,
    controls: bool = True,
    underpowered: bool = False,
    weak_confirmation: bool = False,
    concentration_failure: bool = False,
) -> dict[str, object]:
    markets = ["ES", "CL", "ZN", "6E"]
    fold_results = []
    top_5_by_market = {}
    market_stage_summaries = {}
    class_balance = {"by_market": []}
    for market in markets:
        class_balance["by_market"].append(
            {"market": market, "event_count": 25000, "cost_clearable_rate": 0.50}
        )
        top_5_by_market[market] = {
            "selected_event_count": 700,
            "clearable_event_count": 560,
            "oracle_gross_upper_bound": 100000.0,
            "oracle_cost_dollars": 10000.0,
            "oracle_net_upper_bound": 90000.0,
            "clearable_rate": 0.80,
            "cost_drag": 0.10,
        }
        if underpowered and market == "CL":
            top_5_by_market[market]["selected_event_count"] = 599
        if concentration_failure and market == "ES":
            top_5_by_market[market]["oracle_net_upper_bound"] = 240000.0

        market_stage_summaries[market] = {}
        for stage in ("discovery", "confirmation"):
            model_value = 10.0 if not (weak_confirmation and market == "ZN" and stage == "confirmation") else 0.5
            scorers = {
                "model": {"top_5pct_oracle_net_upper_bound_per_event": model_value},
                "random_label": {"top_5pct_oracle_net_upper_bound_per_event": 1.0},
                "shuffled_feature": {"top_5pct_oracle_net_upper_bound_per_event": 1.0},
                "market_year_session_baseline": {"top_5pct_oracle_net_upper_bound_per_event": 1.0},
                "inverse_score": {"top_5pct_oracle_net_upper_bound_per_event": 1.0},
                "pooled_score_transfer": {"top_5pct_oracle_net_upper_bound_per_event": 1.0},
            }
            if not controls and market == "6E" and stage == "confirmation":
                scorers.pop("pooled_score_transfer")
            market_stage_summaries[market][stage] = {"scorers": scorers}

        for idx in range(12):
            fold_results.append(
                {
                    "fold_id": f"{market}_research_{idx + 1:04d}",
                    "stage": "discovery" if idx < 6 else "confirmation",
                    "market": market,
                    "scored_event_count": 1000,
                    "positive_top_5pct": not (
                        weak_confirmation and market == "ZN" and idx >= 6
                    ),
                    "bucket_metrics": {},
                }
            )

    return {
        "scope": {"markets": markets},
        "event_counts": {"by_market": {market: 25000 for market in markets}},
        "class_balance": class_balance,
        "fold_results": fold_results,
        "market_stage_summaries": market_stage_summaries,
        "top_5_by_market": top_5_by_market,
        "concentration": {
            "fold": {"max_share": 0.20},
            "hour": {"max_share": 0.20},
            "market": {"max_share": 0.25},
        },
        "failures": [],
    }


def test_resolves_tier1_scope_from_config(tmp_path: Path) -> None:
    scope = resolve_profile(_profile_config(tmp_path / "alpha_tiered.yaml"), "tier_1")

    assert scope["resolved_profile"] == "tier_1_research"
    assert scope["markets"] == ["ES", "CL", "ZN", "6E"]
    assert scope["years"] == [2023, 2024]


def test_event_construction_excludes_invalid_rows_and_non_overlaps() -> None:
    rows = [_base_frame().iloc[0].copy() for _ in range(5)]
    for idx, row in enumerate(rows):
        row["ts"] = pd.Timestamp("2024-01-01T00:00:00Z") + pd.Timedelta(minutes=idx * 20)
        row["target_entry_ts"] = row["ts"]
        row["target_exit_ts"] = row["ts"] + pd.Timedelta(minutes=15)
    rows[1]["is_synthetic"] = True
    rows[2]["roll_window_flag"] = True
    rows[3]["boundary_session_flag"] = True
    rows[4]["causal_valid"] = False
    session_end = _base_frame().iloc[-1].copy()
    session_end["ts"] = pd.Timestamp("2024-01-01T03:00:00Z")
    frame = pd.DataFrame([*rows, session_end])
    labeled = apply_opportunity_labels(frame, {"ES": 10.0})

    events, _ = non_overlapping_events(labeled)

    assert len(events) == 1
    assert events.iloc[0]["ts"] == pd.Timestamp("2024-01-01T00:00:00Z")


def test_leakage_guard_blocks_target_future_cost_net_gross_columns() -> None:
    selected = select_model_features(
        [
            "feature_signal",
            "target_x",
            "label_x",
            "future_x",
            "entry_x",
            "exit_x",
            "feature_forward_x",
            "feature_cost_x",
            "feature_net_x",
            "feature_gross_x",
            "feature_profit_x",
        ]
    )

    assert selected == ["feature_signal"]


def _scoring_frame(market: str, offset: float) -> pd.DataFrame:
    train_ts = pd.date_range("2023-12-30T00:00:00Z", periods=40, freq="h")
    test_ts = pd.date_range("2024-01-01T00:00:00Z", periods=40, freq="h")
    ts = train_ts.append(test_ts)
    signal = [float(idx % 2) + offset for idx in range(len(ts))]
    gross = [50.0 if idx % 2 else 5.0 for idx in range(len(ts))]
    frame = pd.DataFrame(
        {
            "ts": ts,
            "market": market,
            "year": [2023] * len(train_ts) + [2024] * len(test_ts),
            "session_segment_id": [f"{market}_s"] * len(ts),
            "target_entry_ts": ts,
            "target_exit_ts": ts + pd.Timedelta(minutes=15),
            "target_gross_dollars_15m": gross,
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
            "feature_signal": signal,
        }
    )
    return apply_opportunity_labels(frame, {market: 10.0})


def test_sleeve_scoring_keeps_independent_market_selection() -> None:
    es = _scoring_frame("ES", 0.0)
    cl = _scoring_frame("CL", 10.0)
    all_events = pd.concat([es, cl], ignore_index=True)

    result, selected = _fold_result(
        fold=_fold("ES"),
        stage="discovery",
        market_events=es,
        all_events=all_events,
        features=["feature_signal"],
        seed=1,
    )

    assert result["market"] == "ES"
    assert set(selected["market"]) == {"ES"}
    assert "pooled_score_transfer" in result["bucket_metrics"]


def test_event_cap_preserves_train_and_test_for_each_requested_fold() -> None:
    ts = pd.date_range("2023-12-01T00:00:00Z", periods=360, freq="6h")
    frame = pd.DataFrame(
        {
            "ts": ts,
            "market": "ES",
            "year": [2023 if item.year == 2023 else 2024 for item in ts],
            "session_segment_id": "session",
            "target_entry_ts": ts,
            "target_exit_ts": ts + pd.Timedelta(minutes=15),
            "target_gross_dollars_15m": [50.0 if idx % 2 else 5.0 for idx in range(len(ts))],
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
            "feature_signal": [float(idx % 2) for idx in range(len(ts))],
        }
    )
    labeled = apply_opportunity_labels(frame, {"ES": 10.0})
    events, _ = non_overlapping_events(labeled)
    folds = [
        _dated_fold(
            "ES",
            "ES_research_0001",
            "2023-12-01T00:00:00+00:00",
            "2023-12-31T23:59:00+00:00",
            "2024-01-01T00:00:00+00:00",
            "2024-01-15T23:59:00+00:00",
        ),
        _dated_fold(
            "ES",
            "ES_research_0007",
            "2024-01-01T00:00:00+00:00",
            "2024-01-31T23:59:00+00:00",
            "2024-02-01T00:00:00+00:00",
            "2024-02-15T23:59:00+00:00",
        ),
    ]

    limited = _limit_events_for_selected_folds(events, folds, 80)

    for fold in folds:
        train_mask, test_mask = _fold_masks(limited, fold, limited["cost_clearable_15m"].astype(int))
        assert train_mask.any(), fold["fold_id"]
        assert test_mask.any(), fold["fold_id"]


def test_gate_evaluator_pass_and_failure_fixtures() -> None:
    assert evaluate_gates(_balanced_report())["decision"] == "PASS"
    assert evaluate_gates(_balanced_report(underpowered=True))["decision"] == "STOP_UNDERPOWERED"
    assert evaluate_gates(_balanced_report(weak_confirmation=True))["decision"] == "STOP_BRANCH_PERMANENTLY"
    assert evaluate_gates(_balanced_report(concentration_failure=True))["decision"] == "STOP_BRANCH_PERMANENTLY"


def test_controls_are_required_per_market_and_stage() -> None:
    result = evaluate_gates(_balanced_report(controls=False))

    assert result["decision"] == "STOP_BRANCH_PERMANENTLY"
    control_gate = [
        gate for gate in result["gates"] if gate["gate"] == "each_market_beats_all_controls_by_stage"
    ][0]
    assert control_gate["pass"] is False
    assert "6E:confirmation:pooled_score_transfer" in control_gate["failures"]


def test_top5_by_market_keeps_market_sleeve_totals() -> None:
    fold_results = []
    for market in ("ES", "CL"):
        fold_results.append(
            {
                "market": market,
                "bucket_metrics": {
                    "model": {
                        "top_5pct": {
                            "selected_event_count": 10,
                            "clearable_event_count": 8,
                            "oracle_gross_upper_bound": 1000.0,
                            "oracle_cost_dollars": 100.0,
                            "oracle_net_upper_bound": 900.0,
                        }
                    }
                },
            }
        )

    totals = _top_5_by_market(fold_results)

    assert totals["ES"]["selected_event_count"] == 10
    assert totals["CL"]["selected_event_count"] == 10
    assert totals["ES"]["clearable_rate"] == 0.8


def test_report_schema_contains_audit_sections() -> None:
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
        "market_stage_summaries",
        "controls",
        "concentration",
        "gates",
        "decision",
        "do_not_do",
    ]:
        assert key in report
