from __future__ import annotations

import json
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
)
from scripts.phase8_model_selection.candidate_rescue_feasibility import (
    RescuePaths,
    run_rescue_audit,
)


HYPOTHESIS_ID = "fixture_opening_range_candidate_v1"
RUN_ID = "fixture_opening_range_candidate_v1_model_expansion_s1"
TARGET_NAME = "target_sign_with_deadzone"


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _paths(tmp_path: Path) -> RescuePaths:
    return RescuePaths(
        predictions=tmp_path / "data" / "predictions.parquet",
        predictions_manifest=tmp_path / "reports" / "wfa" / "manifest.json",
        wfa_report=tmp_path / "reports" / "wfa" / "report.json",
        policy_diagnostics=tmp_path / "reports" / "policy" / "diagnostics.json",
        trades=tmp_path / "reports" / "policy" / "trades.csv",
        bars=tmp_path / "data" / "bars.parquet",
        costs_config=tmp_path / "configs" / "costs.yaml",
        first_touch_diagnostics=tmp_path / "reports" / "first_touch" / "diagnostics.json",
        first_touch_grid=tmp_path / "reports" / "first_touch" / "grid.csv",
        json_out=tmp_path / "reports" / "candidate_rescue" / "rescue_feasibility.json",
        md_out=tmp_path / "reports" / "candidate_rescue" / "rescue_feasibility.md",
    )


def _write_costs(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _prediction_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    base = pd.Timestamp("2024-01-02T14:30:00Z")
    for fold_idx in range(4):
        fold_id = f"ES_research_000{fold_idx + 1}"
        good_ts = base + pd.Timedelta(minutes=fold_idx * 80)
        bad_ts = good_ts + pd.Timedelta(minutes=40)
        rows.append(
            {
                "market": "ES",
                "year": 2024,
                "fold_id": fold_id,
                "timestamp": good_ts,
                "model_id": "fixture_model",
                "target_name": TARGET_NAME,
                "split_group": "research",
                "p_long": 0.90,
                "p_short": 0.05,
                "p_flat": 0.05,
                "y_true": 1,
                "execution_open": 100.0,
                "execution_close": 100.5,
                "target_entry_ts": good_ts + pd.Timedelta(minutes=1),
                "target_exit_ts": good_ts + pd.Timedelta(minutes=3),
                "target_direction": 1,
                "target_acceptance_distance": 2.0,
            }
        )
        rows.append(
            {
                "market": "ES",
                "year": 2024,
                "fold_id": fold_id,
                "timestamp": bad_ts,
                "model_id": "fixture_model",
                "target_name": TARGET_NAME,
                "split_group": "research",
                "p_long": 0.20,
                "p_short": 0.70,
                "p_flat": 0.10,
                "y_true": 1,
                "execution_open": 100.0,
                "execution_close": 101.0,
                "target_entry_ts": bad_ts + pd.Timedelta(minutes=1),
                "target_exit_ts": bad_ts + pd.Timedelta(minutes=3),
                "target_direction": 1,
                "target_acceptance_distance": 7.0,
            }
        )
    return rows


def _write_predictions(path: Path) -> pd.DataFrame:
    predictions = pd.DataFrame(_prediction_rows())
    path.parent.mkdir(parents=True, exist_ok=True)
    predictions.drop(columns=["target_direction", "target_acceptance_distance"]).to_parquet(path, index=False)
    return predictions


def _write_bars(path: Path, predictions: pd.DataFrame) -> None:
    rows: list[dict[str, object]] = []
    for row in predictions.itertuples(index=False):
        for offset in range(4):
            ts = row.timestamp + pd.Timedelta(minutes=offset)
            open_price = 100.0
            if offset == 3:
                open_price = float(row.execution_close)
            high = max(open_price, 102.0 if row.p_long > row.p_short else 101.5)
            low = min(open_price, 99.75 if row.p_long > row.p_short else 99.0)
            rows.append(
                {
                    "ts": ts,
                    "market": "ES",
                    "year": 2024,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    TARGET_VALID: True,
                    TARGET_DIRECTION: int(row.target_direction),
                    TARGET_THRESHOLD: 4.0,
                    TARGET_ACCEPTANCE_DISTANCE: float(row.target_acceptance_distance),
                    TARGET_FAVORABLE: 8.0,
                    TARGET_ADVERSE: 2.0,
                }
            )
    bars = pd.DataFrame(rows).drop_duplicates(["market", "year", "ts"], keep="first")
    path.parent.mkdir(parents=True, exist_ok=True)
    bars.to_parquet(path, index=False)


def _write_trades(path: Path, predictions: pd.DataFrame) -> None:
    rows: list[dict[str, object]] = []
    for row in predictions.itertuples(index=False):
        position = 1 if row.p_long > row.p_short else -1
        price_move = float(row.execution_close) - float(row.execution_open)
        gross = position * price_move * 50.0
        rows.append(
            {
                "market": "ES",
                "year": 2024,
                "fold_id": row.fold_id,
                "timestamp": row.timestamp,
                "target_entry_ts": row.target_entry_ts,
                "target_exit_ts": row.target_exit_ts,
                "position": position,
                "execution_open": row.execution_open,
                "execution_close": row.execution_close,
                "gross_dollars": gross,
                "cost_dollars": 10.0,
                "net_dollars": gross - 10.0,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_core_artifacts(paths: RescuePaths) -> None:
    predictions = _write_predictions(paths.predictions)
    _write_bars(paths.bars, predictions)
    _write_trades(paths.trades, predictions)
    _write_costs(paths.costs_config)
    _write_json(
        paths.predictions_manifest,
        {
            "failure_count": 0,
            "prediction_count": int(len(predictions)),
            "fold_count": 4,
            "model_ids": ["fixture_model"],
            "target_names": [TARGET_NAME],
            "artifact_evidence_ready": True,
        },
    )
    _write_json(paths.wfa_report, {"model_risk_gate": {"status": "PASS_METADATA_READY"}})
    _write_json(
        paths.policy_diagnostics,
        {
            "failure_count": 0,
            "fixed_exit_policy_mismatch": True,
            "economic_approval_allowed": False,
            "economic_rejection_allowed": False,
        },
    )
    _write_json(
        paths.first_touch_diagnostics,
        {
            "decision_support": {
                "screen_status": "FIRST_TOUCH_FEASIBILITY_NO_GO",
                "grid_count": 1,
                "stop_first_positive_overall_grid_count": 0,
                "ambiguous_excluded_positive_overall_grid_count": 0,
                "stop_first_at_least_3_positive_fold_grid_count": 0,
            }
        },
    )
    paths.first_touch_grid.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "scope_type": "overall",
                "scope_value": "all",
                "take_profit_ticks": 4,
                "stop_loss_ticks": 4,
                "stop_first_net_dollars": -25.0,
                "ambiguous_excluded_net_dollars": -15.0,
            }
        ]
    ).to_csv(paths.first_touch_grid, index=False)


def _complete_fixture(tmp_path: Path) -> RescuePaths:
    paths = _paths(tmp_path)
    _write_core_artifacts(paths)
    return paths


def test_rescue_audit_generates_diagnostic_only_outputs(tmp_path: Path) -> None:
    paths = _complete_fixture(tmp_path)

    result = run_rescue_audit(
        hypothesis_id=HYPOTHESIS_ID,
        run=RUN_ID,
        paths=paths,
        market="ES",
        min_bucket_trades=1,
        min_positive_folds=3,
    )

    codes = {item["code"] for item in result["classifications"]}
    assert result["decision"] == "V2_PACKET_REVIEW_READY"
    assert result["decision_support"]["v1_rescue_allowed"] is False
    assert result["decision_support"]["selected_bucket"] is None
    assert result["decision_support"]["selected_tp_sl"] is None
    assert "FIRST_TOUCH_NO_GO_CONFIRMED" in codes
    assert "UPPER_BOUND_PATH_CAPTURE_POSITIVE_NON_TRADABLE" in codes
    assert result["decision_support"]["stable_positive_bucket_family_count"] >= 2
    assert paths.json_out.exists()
    assert paths.md_out.exists()
    text = paths.md_out.read_text(encoding="utf-8")
    assert "diagnostic-only salvage audit" in text
    assert "No selected TP/SL pair is produced." in text
    assert "promote a model" in text


def test_pretrade_bucket_families_are_predeclared(tmp_path: Path) -> None:
    paths = _complete_fixture(tmp_path)

    result = run_rescue_audit(
        hypothesis_id=HYPOTHESIS_ID,
        run=RUN_ID,
        paths=paths,
        market="ES",
        min_bucket_trades=1,
        min_positive_folds=3,
    )

    families = {row["bucket_family"] for row in result["pretrade_bucket_summaries"]}
    assert {
        "fold",
        "side",
        "time_hour_utc",
        "confidence_decile",
        "probability_margin_decile",
        "opening_range_distance",
    }.issubset(families)


def test_missing_first_touch_evidence_fails_closed(tmp_path: Path) -> None:
    paths = _complete_fixture(tmp_path)
    paths.first_touch_diagnostics.unlink()

    with pytest.raises(ValueError, match="missing required first-touch diagnostics"):
        run_rescue_audit(
            hypothesis_id=HYPOTHESIS_ID,
            run=RUN_ID,
            paths=paths,
            market="ES",
            min_bucket_trades=1,
            min_positive_folds=3,
        )


def test_missing_probability_column_fails_closed(tmp_path: Path) -> None:
    paths = _complete_fixture(tmp_path)
    predictions = pd.read_parquet(paths.predictions).drop(columns=["p_short"])
    predictions.to_parquet(paths.predictions, index=False)

    with pytest.raises(ValueError, match="predictions missing required columns"):
        run_rescue_audit(
            hypothesis_id=HYPOTHESIS_ID,
            run=RUN_ID,
            paths=paths,
            market="ES",
            min_bucket_trades=1,
            min_positive_folds=3,
        )


def test_stale_output_fails_closed_without_overwrite(tmp_path: Path) -> None:
    paths = _complete_fixture(tmp_path)
    paths.json_out.parent.mkdir(parents=True, exist_ok=True)
    paths.json_out.write_text("stale", encoding="utf-8")

    with pytest.raises(ValueError, match="stale output path exists"):
        run_rescue_audit(
            hypothesis_id=HYPOTHESIS_ID,
            run=RUN_ID,
            paths=paths,
            market="ES",
            min_bucket_trades=1,
            min_positive_folds=3,
        )
