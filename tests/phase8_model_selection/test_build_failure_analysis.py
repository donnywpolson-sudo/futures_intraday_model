from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.build_failure_analysis import build_failure_analysis  # noqa: E402
from tests.phase8_model_selection.test_evaluate_predictions import (  # noqa: E402
    _policy,
    _write_costs,
    _write_manifest,
    _write_models,
    _write_predictions,
)


def test_failure_analysis_builds_baselines_stress_and_classifications(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")

    result = build_failure_analysis(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        output_root=tmp_path / "reports" / "failure_analysis" / "baseline",
        run="baseline",
        policy=_policy(),
    )

    assert result["status"] == "PASS"
    assert result["failure_analysis_ready"] is True
    assert result["baseline_comparison_gate"]["status"] == "FAIL"
    baselines = result["baseline_comparison_gate"]["baselines"]
    assert any(item["baseline_id"] == "random_entry" and item["status"] == "PASS" for item in baselines)
    assert any(
        item["baseline_id"] == "simple_carry" and item["status"] == "MISSING_WITH_REASON"
        for item in baselines
    )
    stress = pd.read_csv(
        tmp_path / "reports" / "failure_analysis" / "baseline" / "stress_tests.csv"
    )
    assert set(stress["stress_type"]) >= {"cost_multiplier", "remove_top_trades"}
    assert 2.0 in set(stress["stress_value"])
    attribution = pd.read_csv(
        tmp_path / "reports" / "failure_analysis" / "baseline" / "pnl_attribution.csv"
    )
    assert {"market", "fold", "side", "regime"} & set(attribution["scope"])


def test_failure_analysis_flags_absent_gross_edge(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    predictions = pd.read_parquet(prediction_path)
    predictions["execution_close"] = predictions["execution_open"]
    predictions.to_parquet(prediction_path, index=False)
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")

    result = build_failure_analysis(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        output_root=tmp_path / "reports" / "failure_analysis" / "baseline",
        run="baseline",
        policy=_policy(),
    )

    assert any(
        item["classification"] == "gross_edge_absent"
        for item in result["failure_classifications"]
    )
