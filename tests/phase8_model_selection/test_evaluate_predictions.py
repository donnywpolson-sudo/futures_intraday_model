from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.evaluate_predictions import (  # noqa: E402
    PolicyConfig,
    PromotionGateConfig,
    build_arg_parser,
    evaluate_predictions,
    load_policy_config,
    main,
)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _write_models(path: Path, *, p_trend_danger_blocks_fade_trades: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    trend_block = str(p_trend_danger_blocks_fade_trades).lower()
    path.write_text(
        f"""
calibration:
  test_fold_fit_allowed: false
  final_holdout_fit_allowed: false
  no_calibration_marker: no_calibration
  preserve_raw_and_calibrated_scores: true
position_policy:
  p_trend_danger_blocks_fade_trades: {trend_block}
  p_fade_success_allows_fade_trades: true
  raw_return_prediction_direct_trading_allowed: false
""".strip(),
        encoding="utf-8",
    )
    return path


def _policy() -> PolicyConfig:
    return PolicyConfig(
        long_short_margin=0.05,
        min_fade_success=0.50,
        max_trend_danger=0.50,
        p_trend_danger_blocks_fade_trades=False,
    )


def _promotion_gate(**overrides: object) -> PromotionGateConfig:
    values = {
        "min_gross_return_dollars": 1.0,
        "min_net_return_dollars": 1.0,
        "min_net_sharpe_like": 0.0,
        "max_cost_drag_to_abs_gross": 1.0,
        "max_turnover_per_bar": 1.0,
        "min_trade_count": 100,
        "min_market_count": 2,
        "min_traded_market_count": 2,
        "min_fold_count": 4,
        "min_traded_fold_count": 4,
        "min_oos_span_days": 30.0,
        "max_single_market_trade_share": 0.75,
        "max_single_fold_trade_share": 0.50,
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
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=5, freq="15min")
    policy_inputs = [
        {"p_long": 0.70, "p_short": 0.20, "p_flat": 0.10, "p_fade": 0.80, "p_trend": 0.20, "entry": 100.0, "exit": 101.0},
        {"p_long": 0.20, "p_short": 0.75, "p_flat": 0.05, "p_fade": 0.85, "p_trend": 0.90, "entry": 101.0, "exit": 100.0},
        {"p_long": 0.68, "p_short": 0.20, "p_flat": 0.12, "p_fade": 0.40, "p_trend": 0.20, "entry": 100.0, "exit": 101.0},
        {"p_long": 0.15, "p_short": 0.75, "p_flat": 0.10, "p_fade": 0.90, "p_trend": 0.10, "entry": 101.0, "exit": 100.0},
        {"p_long": 0.35, "p_short": 0.20, "p_flat": 0.45, "p_fade": 0.90, "p_trend": 0.10, "entry": 100.0, "exit": 101.0},
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


def _write_split_plan(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "profile": "tier_1",
                "resolved_profile": "tier_1_research",
                "config_hash": "split-config-hash",
                "markets": ["ES"],
                "years": [2024],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_manifest(
    path: Path,
    prediction_path: Path,
    *,
    overrides: dict[str, object] | None = None,
    remove: set[str] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    split_plan = _write_split_plan(path.parent / "split_plan.json")
    payload: dict[str, object] = {
        "failure_count": 0,
        "run": "baseline",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": ["ES"],
        "years": [2024],
        "prediction_markets": ["ES"],
        "prediction_years": [2024],
        "prediction_path": prediction_path.as_posix(),
        "prediction_count": 20,
        "output_file_hashes": {prediction_path.as_posix(): _sha256(prediction_path)},
        "input_file_hashes": {split_plan.as_posix(): _sha256(split_plan)},
        "split_plan_path": split_plan.as_posix(),
        "split_plan_hash": _sha256(split_plan),
        "split_plan_profile": "tier_1",
        "split_plan_resolved_profile": "tier_1_research",
        "split_plan_config_hash": "split-config-hash",
        "stale_output_path_exists": False,
        "artifact_evidence_ready": True,
    }
    if overrides:
        payload.update(overrides)
    for key in remove or set():
        payload.pop(key, None)
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return path


def test_cli_predictions_has_no_implicit_data_predictions_default() -> None:
    args = build_arg_parser().parse_args([])

    assert args.predictions is None


def test_cli_missing_predictions_fails_clearly(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["evaluate_predictions.py"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    assert "--predictions is required" in capsys.readouterr().err


def test_cli_accepts_explicit_report_scoped_predictions(tmp_path: Path) -> None:
    prediction_path = tmp_path / "reports" / "wfa" / "fixture_predictions.parquet"

    args = build_arg_parser().parse_args(["--predictions", prediction_path.as_posix()])

    assert Path(args.predictions).as_posix() == prediction_path.as_posix()


def test_policy_config_reads_trend_danger_blocker_flag(tmp_path: Path) -> None:
    disabled_models = _write_models(
        tmp_path / "configs" / "models_disabled.yaml",
        p_trend_danger_blocks_fade_trades=False,
    )
    enabled_models = _write_models(
        tmp_path / "configs" / "models_enabled.yaml",
        p_trend_danger_blocks_fade_trades=True,
    )

    disabled_policy = load_policy_config(
        disabled_models,
        long_short_margin=0.05,
        min_fade_success=0.50,
        max_trend_danger=0.50,
    )
    enabled_policy = load_policy_config(
        enabled_models,
        long_short_margin=0.05,
        min_fade_success=0.50,
        max_trend_danger=0.50,
    )

    assert disabled_policy.p_trend_danger_blocks_fade_trades is False
    assert enabled_policy.p_trend_danger_blocks_fade_trades is True


def test_policy_metrics_do_not_hard_block_aggregate_trend_danger(tmp_path: Path) -> None:
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
    assert overall["row_count"] == 5
    assert overall["trade_count"] == 3
    assert overall["blocked_by_trend_danger"] == 0
    assert overall["blocked_by_fade_filter"] == 1
    assert overall["blocked_by_flat_probability"] == 1
    assert overall["gross_return_dollars"] == 150.0
    assert overall["cost_dollars"] == 30.0
    assert overall["net_return_dollars"] == 120.0
    assert overall["max_drawdown_dollars"] <= 0.0
    assert overall["position_change_abs_sum"] >= 3.0

    metrics = json.loads(result["metrics_path"].read_text(encoding="utf-8"))
    phase8_metrics = json.loads(result["phase8_metrics_path"].read_text(encoding="utf-8"))
    decision = json.loads(result["alpha_promotion_decision_path"].read_text(encoding="utf-8"))
    selection = json.loads(result["model_selection_report_path"].read_text(encoding="utf-8"))
    calibration = json.loads(result["calibration_report_path"].read_text(encoding="utf-8"))
    comparison = pd.read_csv(result["model_comparison_path"])
    turnover = pd.read_csv(result["turnover_path"])

    assert metrics["live_execution_ready"] is False
    assert metrics["execution_realism"] == "research_non_overlapping_target_window_execution_policy"
    assert metrics["execution_policy"] == "max_one_contract_non_overlapping_target_window"
    assert metrics["research_alpha_ready"] is False
    assert metrics["model_promotion_allowed"] is False
    assert metrics["policy_config"]["p_trend_danger_blocks_fade_trades"] is False
    assert phase8_metrics["metrics"]["overall"]["net_return_dollars"] == 120.0
    assert decision["promoted"] is False
    assert decision["model_promotion_allowed"] is False
    assert "trade_count 3 below minimum 100" in decision["blockers"]
    assert "market_count 1 below minimum 2" in decision["blockers"]
    assert decision["final_holdout_touched"] is False
    assert decision["trading_semantics_changed"] is False
    assert decision["used_final_holdout_for_tuning"] is False
    assert selection["selection_status"] == "NOT_SELECTED_BASELINE_DIAGNOSTICS_ONLY"
    assert selection["selected_model_id"] is None
    assert selection["research_alpha_ready"] is False
    assert selection["model_promotion_allowed"] is False
    assert calibration["status"] == "NO_CALIBRATION_APPLIED"
    assert set(comparison["model_id"]) == {
        "ridge_return_v1",
        "logistic_direction_v1",
        "logistic_fade_success_v1",
        "logistic_trend_danger_v1",
    }
    assert calibration["calibration_curve_count"] > 0
    assert turnover.loc[0, "trade_count"] == 3


def test_policy_metrics_net_overlapping_target_windows_before_costs(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    predictions = pd.read_parquet(prediction_path)
    keep_timestamps = sorted(predictions["timestamp"].dropna().unique())[:2]
    predictions = predictions[predictions["timestamp"].isin(keep_timestamps)].copy()
    first_timestamp = pd.Timestamp(keep_timestamps[0])
    overlap_timestamp = first_timestamp + pd.Timedelta(minutes=5)
    predictions.loc[predictions["timestamp"].eq(keep_timestamps[1]), "timestamp"] = overlap_timestamp
    predictions.loc[predictions["timestamp"].eq(overlap_timestamp), "target_entry_ts"] = (
        overlap_timestamp + pd.Timedelta(minutes=1)
    )
    predictions.loc[predictions["timestamp"].eq(overlap_timestamp), "target_exit_ts"] = (
        overlap_timestamp + pd.Timedelta(minutes=16)
    )
    keep_timestamps = [first_timestamp, overlap_timestamp]
    for timestamp in keep_timestamps:
        predictions.loc[predictions["timestamp"].eq(timestamp), "p_long"] = 0.70
        predictions.loc[predictions["timestamp"].eq(timestamp), "p_short"] = 0.20
        predictions.loc[predictions["timestamp"].eq(timestamp), "p_flat"] = 0.10
        predictions.loc[predictions["timestamp"].eq(timestamp), "p_fade_success"] = 0.80
        predictions.loc[predictions["timestamp"].eq(timestamp), "p_trend_danger"] = 0.20
        predictions.loc[predictions["timestamp"].eq(timestamp), "execution_open"] = 100.0
        predictions.loc[predictions["timestamp"].eq(timestamp), "execution_close"] = 101.0
    predictions.loc[predictions["target_name"].eq("target_ret_15m"), "p_long"] = None
    predictions.loc[predictions["target_name"].eq("target_ret_15m"), "p_short"] = None
    predictions.loc[predictions["target_name"].eq("target_ret_15m"), "p_flat"] = None
    predictions.loc[predictions["target_name"].eq("target_fade_success_15m"), "p_fade_success"] = 0.80
    predictions.loc[predictions["target_name"].eq("target_trend_danger_30m"), "p_trend_danger"] = 0.20
    predictions.to_parquet(prediction_path, index=False)
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
        overrides={"prediction_count": int(len(predictions))},
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
        promotion_gate=_promotion_gate(
            min_trade_count=1,
            min_market_count=1,
            min_traded_market_count=1,
            min_fold_count=1,
            min_traded_fold_count=1,
            min_oos_span_days=0.0,
            max_single_market_trade_share=1.0,
            max_single_fold_trade_share=1.0,
        ),
    )

    overall = result["policy_metrics"]["overall"]
    assert result["failure_count"] == 0
    assert overall["candidate_trade_count"] == 2
    assert overall["trade_count"] == 1
    assert overall["blocked_by_execution_overlap"] == 1
    assert overall["gross_return_dollars"] == 50.0
    assert overall["cost_dollars"] == 10.0
    assert overall["net_return_dollars"] == 40.0


@pytest.mark.parametrize(
    ("case", "expected_failure"),
    [
        ("hash", "output hash does not match"),
        ("path", "prediction_path does not match CLI predictions path"),
        ("count", "prediction_count does not match"),
        ("missing_hashes", "output_file_hashes missing"),
        ("missing_count", "prediction_count missing"),
        ("stale", "flags stale output"),
        ("not_ready", "artifact_evidence_ready is false"),
        ("scope", "prediction_markets do not match"),
        ("profile", "profile does not match split-plan profile"),
    ],
)
def test_prediction_manifest_artifact_guard_rejects_invalid_metadata(
    tmp_path: Path,
    case: str,
    expected_failure: str,
) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    overrides: dict[str, object] = {}
    remove: set[str] = set()
    if case == "hash":
        overrides["output_file_hashes"] = {prediction_path.as_posix(): "0" * 64}
    elif case == "path":
        overrides["prediction_path"] = (tmp_path / "other.parquet").as_posix()
    elif case == "count":
        overrides["prediction_count"] = 19
    elif case == "missing_hashes":
        remove.add("output_file_hashes")
    elif case == "missing_count":
        remove.add("prediction_count")
    elif case == "stale":
        overrides["stale_output_path_exists"] = True
    elif case == "not_ready":
        overrides["artifact_evidence_ready"] = False
    elif case == "scope":
        overrides["prediction_markets"] = ["CL"]
    elif case == "profile":
        overrides["profile"] = "tier_2"
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
        overrides=overrides,
        remove=remove,
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
    assert expected_failure in " ".join(result["failures"])


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


def test_locked_negative_wfa_fixture_blocks_promotion_even_when_structure_passes(
    tmp_path: Path,
) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    predictions = pd.read_parquet(prediction_path)
    timestamps = sorted(predictions["timestamp"].dropna().unique())
    predictions.loc[predictions["timestamp"].eq(timestamps[0]), "execution_close"] = 99.0
    predictions.loc[predictions["timestamp"].eq(timestamps[3]), "execution_close"] = 102.0
    predictions.to_parquet(prediction_path, index=False)
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
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
        promotion_gate=_promotion_gate(
            min_trade_count=1,
            min_market_count=1,
            min_traded_market_count=1,
            min_fold_count=1,
            min_traded_fold_count=1,
            min_oos_span_days=0.0,
            max_single_market_trade_share=1.0,
            max_single_fold_trade_share=1.0,
        ),
    )

    gate = result["promotion_gate"]
    assert result["policy_metrics"]["overall"]["gross_return_dollars"] < 0.0
    assert gate["model_promotion_allowed"] is False
    assert any("gross_return_dollars" in blocker for blocker in gate["promotion_blockers"])


def test_phase8_blocks_final_holdout_predictions_for_selection(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    predictions = pd.read_parquet(prediction_path)
    predictions["split_group"] = "final_holdout"
    predictions.to_parquet(prediction_path, index=False)
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
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
    decision = json.loads(result["alpha_promotion_decision_path"].read_text(encoding="utf-8"))
    assert decision["promoted"] is False
    assert decision["final_holdout_touched"] is True
    assert "final_holdout predictions cannot be used" in " ".join(decision["failures"])
