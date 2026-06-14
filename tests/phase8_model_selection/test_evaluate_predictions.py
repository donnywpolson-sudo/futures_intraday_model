from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.evaluate_predictions import (  # noqa: E402
    PolicyConfig,
    PromotionGateConfig,
    evaluate_predictions,
)


def _write_costs(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
cost_model:
  name: fixture_costs
  live_fill_model_available: false
markets:
  ES:
    point_value: 50.0
    round_turn_cost_dollars: 10.0
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_models(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
calibration:
  test_fold_fit_allowed: false
  final_holdout_fit_allowed: false
  no_calibration_marker: no_calibration
  preserve_raw_and_calibrated_scores: true
""".strip(),
        encoding="utf-8",
    )
    return path


def _policy() -> PolicyConfig:
    return PolicyConfig(
        long_short_margin=0.05,
        min_fade_success=0.50,
        max_trend_danger=0.50,
    )


def _promotion_gate(**overrides: object) -> PromotionGateConfig:
    values = {
        "min_net_return_dollars": 1.0,
        "min_net_sharpe_like": 0.0,
        "max_cost_drag_to_abs_gross": 1.0,
        "max_turnover_per_bar": 1.0,
        "min_trade_count": 1,
        "require_positive_net_all_markets": True,
        "require_positive_net_all_folds": True,
    }
    values.update(overrides)
    return PromotionGateConfig(**values)


def _prediction_rows(timestamp: pd.Timestamp, *, entry: float, exit_: float) -> dict[str, object]:
    return {
        "market": "ES",
        "year": 2024,
        "fold_id": "ES_research_0001",
        "timestamp": timestamp,
        "session_id": "2024-01-01",
        "session_segment_id": "rth",
        "split_group": "research",
        "model_family": "fixture",
        "prediction_type": "classification_probability",
        "calibration_id": "no_calibration",
        "model_config_hash": "model-hash",
        "feature_config_hash": "feature-hash",
        "execution_open": entry,
        "execution_close": exit_,
        "target_valid": True,
        "target_entry_ts": timestamp + pd.Timedelta(minutes=1),
        "target_exit_ts": timestamp + pd.Timedelta(minutes=16),
        "minutes_until_session_close": 60.0,
    }


def _write_predictions(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=4, freq="15min")
    policy_inputs = [
        {"p_long": 0.70, "p_short": 0.20, "p_flat": 0.10, "p_fade": 0.80, "p_trend": 0.20, "entry": 100.0, "exit": 101.0},
        {"p_long": 0.20, "p_short": 0.75, "p_flat": 0.05, "p_fade": 0.85, "p_trend": 0.90, "entry": 101.0, "exit": 100.0},
        {"p_long": 0.68, "p_short": 0.20, "p_flat": 0.12, "p_fade": 0.40, "p_trend": 0.20, "entry": 100.0, "exit": 101.0},
        {"p_long": 0.15, "p_short": 0.75, "p_flat": 0.10, "p_fade": 0.90, "p_trend": 0.10, "entry": 101.0, "exit": 100.0},
    ]
    rows: list[dict[str, object]] = []
    for idx, item in enumerate(policy_inputs):
        base = _prediction_rows(timestamps[idx], entry=item["entry"], exit_=item["exit"])
        rows.append(
            {
                **base,
                "model_id": "ridge_return_v1",
                "model_family": "ridge_regression",
                "target_name": "target_ret_15m",
                "prediction_type": "regression",
                "y_true": 0.01,
                "y_pred_raw": 0.002,
                "y_pred_calibrated": 0.002,
                "p_long": None,
                "p_short": None,
                "p_flat": None,
                "p_fade_success": None,
                "p_trend_danger": None,
            }
        )
        rows.append(
            {
                **base,
                "model_id": "logistic_direction_v1",
                "target_name": "target_sign_with_deadzone",
                "y_true": 1 if item["p_long"] > item["p_short"] else -1,
                "y_pred_raw": item["p_long"] - item["p_short"],
                "y_pred_calibrated": item["p_long"] - item["p_short"],
                "p_long": item["p_long"],
                "p_short": item["p_short"],
                "p_flat": item["p_flat"],
                "p_fade_success": None,
                "p_trend_danger": None,
            }
        )
        rows.append(
            {
                **base,
                "model_id": "logistic_fade_success_v1",
                "target_name": "target_fade_success_15m",
                "y_true": int(item["p_fade"] >= 0.5),
                "y_pred_raw": item["p_fade"],
                "y_pred_calibrated": item["p_fade"],
                "p_long": None,
                "p_short": None,
                "p_flat": None,
                "p_fade_success": item["p_fade"],
                "p_trend_danger": None,
            }
        )
        rows.append(
            {
                **base,
                "model_id": "logistic_trend_danger_v1",
                "target_name": "target_trend_danger_30m",
                "y_true": int(item["p_trend"] >= 0.5),
                "y_pred_raw": item["p_trend"],
                "y_pred_calibrated": item["p_trend"],
                "p_long": None,
                "p_short": None,
                "p_flat": None,
                "p_fade_success": None,
                "p_trend_danger": item["p_trend"],
            }
        )
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _write_manifest(path: Path, prediction_path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "failure_count": 0,
                "prediction_count": 16,
                "output_file_hashes": {prediction_path.as_posix(): "hash"},
                "stale_output_path_exists": False,
                "artifact_evidence_ready": True,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_policy_metrics_block_trend_danger_and_fade_filter(tmp_path: Path) -> None:
    prediction_path = _write_predictions(tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet")
    manifest_path = _write_manifest(tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json", prediction_path)
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")

    result = evaluate_predictions(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        metrics_root=tmp_path / "reports" / "metrics",
        model_selection_root=tmp_path / "reports" / "model_selection",
        run="baseline",
        policy=_policy(),
        promotion_gate=_promotion_gate(),
    )

    assert result["failure_count"] == 0
    overall = result["policy_metrics"]["overall"]
    assert overall["row_count"] == 4
    assert overall["trade_count"] == 2
    assert overall["blocked_by_trend_danger"] == 1
    assert overall["blocked_by_fade_filter"] == 1
    assert overall["gross_return_dollars"] == 100.0
    assert overall["cost_dollars"] == 20.0
    assert overall["net_return_dollars"] == 80.0

    metrics = json.loads(result["metrics_path"].read_text(encoding="utf-8"))
    selection = json.loads(result["model_selection_report_path"].read_text(encoding="utf-8"))
    calibration = json.loads(result["calibration_report_path"].read_text(encoding="utf-8"))
    comparison = pd.read_csv(result["model_comparison_path"])
    turnover = pd.read_csv(result["turnover_path"])

    assert metrics["live_execution_ready"] is False
    assert metrics["execution_realism"] == "research_round_turn_cost_assumption_only"
    assert metrics["research_alpha_ready"] is True
    assert metrics["model_promotion_allowed"] is True
    assert selection["selection_status"] == "NOT_SELECTED_BASELINE_DIAGNOSTICS_ONLY"
    assert selection["selected_model_id"] is None
    assert selection["research_alpha_ready"] is True
    assert selection["model_promotion_allowed"] is True
    assert calibration["status"] == "NO_CALIBRATION_APPLIED"
    assert set(comparison["model_id"]) == {
        "ridge_return_v1",
        "logistic_direction_v1",
        "logistic_fade_success_v1",
        "logistic_trend_danger_v1",
    }
    assert turnover.loc[0, "trade_count"] == 2


def test_prediction_manifest_must_certify_artifact_evidence(tmp_path: Path) -> None:
    prediction_path = _write_predictions(tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet")
    manifest_path = tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "failure_count": 1,
                "prediction_count": 0,
                "output_file_hashes": {prediction_path.as_posix(): "NOT_WRITTEN"},
                "stale_output_path_exists": True,
                "artifact_evidence_ready": False,
            }
        ),
        encoding="utf-8",
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")

    result = evaluate_predictions(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        metrics_root=tmp_path / "reports" / "metrics",
        model_selection_root=tmp_path / "reports" / "model_selection",
        run="baseline",
        policy=_policy(),
        promotion_gate=_promotion_gate(),
    )

    assert result["failure_count"] > 0
    selection = json.loads(result["model_selection_report_path"].read_text(encoding="utf-8"))
    assert selection["prediction_manifest_artifact_evidence_ready"] is False
    assert selection["model_promotion_allowed"] is False
    assert "prediction manifest failure_count is nonzero" in selection["failures"]


def test_promotion_gate_blocks_bad_alpha_even_when_structure_passes(tmp_path: Path) -> None:
    prediction_path = _write_predictions(tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet")
    manifest_path = _write_manifest(tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json", prediction_path)
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")

    result = evaluate_predictions(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        metrics_root=tmp_path / "reports" / "metrics",
        model_selection_root=tmp_path / "reports" / "model_selection",
        run="baseline",
        policy=_policy(),
        promotion_gate=_promotion_gate(min_net_return_dollars=1000.0),
    )

    assert result["failure_count"] == 0
    gate = result["promotion_gate"]
    assert gate["research_alpha_ready"] is False
    assert gate["model_promotion_allowed"] is False
    assert any("net_return_dollars" in blocker for blocker in gate["promotion_blockers"])
    metrics = json.loads(result["metrics_path"].read_text(encoding="utf-8"))
    assert metrics["research_policy_metrics_ready"] is True
    assert metrics["research_alpha_ready"] is False
