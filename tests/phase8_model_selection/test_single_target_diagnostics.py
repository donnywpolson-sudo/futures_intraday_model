from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Callable

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.evaluate_predictions import (  # noqa: E402
    PolicyConfig,
    PromotionGateConfig,
    evaluate_predictions,
)
from scripts.phase8_model_selection.single_target_diagnostics import (  # noqa: E402
    build_arg_parser,
    evaluate_single_target_predictions,
    main,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_models(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
calibration:
  test_fold_fit_allowed: false
  final_holdout_fit_allowed: false
  no_calibration_marker: no_calibration
  preserve_raw_and_calibrated_scores: true
position_policy:
  p_trend_danger_blocks_fade_trades: false
  side_aware_trend_blocks_fade_trades: true
  p_fade_success_allows_fade_trades: true
  raw_return_prediction_direct_trading_allowed: false
""".strip(),
        encoding="utf-8",
    )
    return path


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


def _base_rows() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=6, freq="15min")
    rows: list[dict[str, object]] = []
    values = [
        (0.70, 0.20, 0.10, 1),
        (0.20, 0.70, 0.10, -1),
        (0.35, 0.20, 0.45, 0),
        (0.65, 0.25, 0.10, 1),
        (0.25, 0.60, 0.15, -1),
        (0.30, 0.25, 0.45, 0),
    ]
    for idx, (p_long, p_short, p_flat, y_true) in enumerate(values):
        timestamp = timestamps[idx]
        rows.append(
            {
                "market": "ES",
                "year": 2024,
                "fold_id": "ES_research_0001",
                "timestamp": timestamp,
                "session_id": "2024-01-02",
                "session_segment_id": "rth",
                "split_group": "research",
                "model_id": "logistic_opening_range_acceptance_continuation_30m_v1",
                "model_family": "logistic_regression",
                "target_name": "target_sign_with_deadzone",
                "prediction_type": "classification_probability",
                "y_true": y_true,
                "y_pred_raw": p_long - p_short,
                "y_pred_calibrated": p_long - p_short,
                "p_long": p_long,
                "p_short": p_short,
                "p_flat": p_flat,
                "p_fade_success": None,
                "p_trend_adverse_long_30m": None,
                "p_trend_favorable_long_30m": None,
                "p_trend_adverse_short_30m": None,
                "p_trend_favorable_short_30m": None,
                "p_trend_danger": None,
                "calibration_id": "no_calibration",
                "model_config_hash": "model-hash",
                "feature_config_hash": "feature-hash",
                "execution_open": 100.0 + idx,
                "execution_close": 101.0 + idx,
                "target_valid": True,
                "target_entry_ts": timestamp + pd.Timedelta(minutes=1),
                "target_exit_ts": timestamp + pd.Timedelta(minutes=31),
                "minutes_until_session_close": 120.0,
            }
        )
    return pd.DataFrame(rows)


def _write_predictions(
    path: Path,
    *,
    mutate: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> Path:
    frame = _base_rows()
    if mutate is not None:
        frame = mutate(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
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
    run: str = "single_target_run",
    overrides: dict[str, object] | None = None,
    remove: set[str] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    split_plan = _write_split_plan(path.parent / "split_plan.json")
    payload: dict[str, object] = {
        "failure_count": 0,
        "run": run,
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": ["ES"],
        "years": [2024],
        "prediction_markets": ["ES"],
        "prediction_years": [2024],
        "prediction_path": prediction_path.as_posix(),
        "prediction_count": int(len(pd.read_parquet(prediction_path))),
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
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_adapter(
    tmp_path: Path,
    *,
    prediction_mutator: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    manifest_run: str = "single_target_run",
    adapter_run: str = "single_target_run",
    manifest_overrides: dict[str, object] | None = None,
    manifest_remove: set[str] | None = None,
) -> dict[str, object]:
    prediction_path = _write_predictions(tmp_path / "predictions" / "oos_predictions.parquet", mutate=prediction_mutator)
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "predictions_manifest.json",
        prediction_path,
        run=manifest_run,
        overrides=manifest_overrides,
        remove=manifest_remove,
    )
    models_path = _write_models(tmp_path / "configs" / "models.yaml")
    return evaluate_single_target_predictions(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        models_config=models_path,
        reports_root=tmp_path / "reports" / "single_target",
        run=adapter_run,
    )


def test_cli_requires_explicit_inputs() -> None:
    parser = build_arg_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_single_target_diagnostics_writes_diagnostic_only_reports(tmp_path: Path) -> None:
    result = _run_adapter(tmp_path)

    assert result["failure_count"] == 0
    assert result["diagnostic_only"] is True
    assert result["canonical_phase8_policy_applicable"] is False
    assert result["research_alpha_ready"] is False
    assert result["model_promotion_allowed"] is False
    assert result["promotion_allowed"] is False
    assert result["live_execution_ready"] is False
    assert result["prediction_manifest_artifact_evidence_ready"] is True
    assert result["coverage"]["row_count"] == 6
    assert result["class_balance"]["class_count"] == 3
    assert result["duplicate_prediction_count"] == 0
    assert result["score_summary"]["prediction_std"] > 0
    assert result["model_comparison_row_count"] == 1

    diagnostics_path = result["diagnostics_path"]
    comparison_path = result["model_comparison_output_path"]
    assert diagnostics_path.exists()
    assert comparison_path.exists()
    saved = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    comparison = pd.read_csv(comparison_path)
    assert saved["failure_count"] == 0
    assert comparison["target_name"].tolist() == ["target_sign_with_deadzone"]
    assert comparison["direction_accuracy"].iloc[0] == pytest.approx(1.0)


def test_manifest_run_mismatch_fails_closed(tmp_path: Path) -> None:
    result = _run_adapter(tmp_path, manifest_run="manifest_run", adapter_run="adapter_run")

    assert result["failure_count"] > 0
    assert result["prediction_manifest_artifact_evidence_ready"] is False
    assert any("prediction manifest run mismatch" in item for item in result["failures"])
    assert result["promotion_allowed"] is False


@pytest.mark.parametrize(
    ("prediction_mutator", "expected_failure"),
    [
        (
            lambda frame: frame.assign(split_group="final_holdout"),
            "final_holdout predictions cannot be used",
        ),
        (
            lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True),
            "duplicate prediction keys",
        ),
        (
            lambda frame: frame.assign(p_long=0.60, p_short=0.20, p_flat=0.20),
            "nonconstant prediction scores",
        ),
        (
            lambda frame: frame.assign(target_name=["other_target", *frame["target_name"].iloc[1:].tolist()]),
            "exactly one target",
        ),
        (
            lambda frame: frame.drop(columns=["p_flat"]),
            "prediction parquet missing required columns",
        ),
        (
            lambda frame: frame.assign(y_true=1),
            "at least two observed classes",
        ),
    ],
)
def test_single_target_diagnostics_fail_closed_cases(
    tmp_path: Path,
    prediction_mutator: Callable[[pd.DataFrame], pd.DataFrame],
    expected_failure: str,
) -> None:
    result = _run_adapter(tmp_path, prediction_mutator=prediction_mutator)

    assert result["failure_count"] > 0
    assert any(expected_failure in item for item in result["failures"])
    assert result["research_alpha_ready"] is False
    assert result["model_promotion_allowed"] is False
    assert result["promotion_allowed"] is False


def test_canonical_phase8_still_rejects_single_target_policy_bundle(tmp_path: Path) -> None:
    prediction_path = _write_predictions(tmp_path / "predictions" / "oos_predictions.parquet")
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "predictions_manifest.json",
        prediction_path,
        run="single_target_run",
    )
    result = evaluate_predictions(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=_write_costs(tmp_path / "configs" / "costs.yaml"),
        models_config=_write_models(tmp_path / "configs" / "models.yaml"),
        metrics_root=tmp_path / "reports" / "metrics",
        model_selection_root=tmp_path / "reports" / "model_selection",
        phase8_root=tmp_path / "reports" / "phase8",
        run="single_target_run",
        policy=PolicyConfig(
            long_short_margin=0.05,
            min_fade_success=0.50,
            max_trend_danger=0.50,
            side_aware_trend_blocks_fade_trades=True,
        ),
        promotion_gate=PromotionGateConfig(
            min_gross_return_dollars=1.0,
            min_net_return_dollars=1.0,
            min_net_sharpe_like=0.0,
            max_cost_drag_to_abs_gross=1.0,
            max_turnover_per_bar=1.0,
            min_trade_count=100,
        ),
    )

    assert result["failure_count"] == 6
    assert "missing policy target predictions: target_ret_15m" in result["failures"]
    assert "missing policy target predictions: target_fade_success_15m" in result["failures"]
    assert result["promotion_gate"]["model_promotion_allowed"] is False


def test_main_returns_nonzero_on_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prediction_path = _write_predictions(
        tmp_path / "predictions" / "oos_predictions.parquet",
        mutate=lambda frame: frame.assign(y_true=1),
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "predictions_manifest.json",
        prediction_path,
    )
    models_path = _write_models(tmp_path / "configs" / "models.yaml")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "single_target_diagnostics.py",
            "--predictions",
            prediction_path.as_posix(),
            "--predictions-manifest",
            manifest_path.as_posix(),
            "--models-config",
            models_path.as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "single_target").as_posix(),
            "--run",
            "single_target_run",
        ],
    )

    assert main() == 1
