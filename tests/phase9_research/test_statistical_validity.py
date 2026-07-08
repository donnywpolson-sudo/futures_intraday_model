from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.statistical_validity import build_statistical_validity_report  # noqa: E402
from tests.phase8_model_selection.test_evaluate_predictions import (  # noqa: E402
    _policy,
    _write_costs,
    _write_manifest,
    _write_models,
    _write_predictions,
)


def test_statistical_validity_fails_closed_without_trial_log(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")

    result = build_statistical_validity_report(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        output_root=tmp_path / "reports" / "statistical_validity" / "baseline",
        run="baseline",
        policy=_policy(),
        bootstrap_samples=50,
        bootstrap_seed=123,
    )

    assert result["status"] == "FAIL"
    assert result["statistical_validity_ready"] is False
    assert result["required_checks"]["pbo"]["status"] == "FAIL_MISSING_TRIAL_LOG"
    assert result["required_checks"]["multiple_testing_adjustment"]["status"] == "FAIL_MISSING_TRIAL_LOG"
    bootstrap = pd.read_csv(
        tmp_path
        / "reports"
        / "statistical_validity"
        / "baseline"
        / "bootstrap_confidence_intervals.csv"
    )
    assert set(bootstrap["metric"]) >= {
        "net_return_dollars",
        "sharpe_like",
        "average_net_edge_per_trade",
    }
