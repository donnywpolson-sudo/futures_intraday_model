from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase6_wfa.prediction_diagnostics import build_prediction_diagnostics  # noqa: E402
from tests.phase8_model_selection.test_evaluate_predictions import (  # noqa: E402
    _write_manifest,
    _write_predictions,
)


def test_prediction_diagnostics_reports_target_quality(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )

    result = build_prediction_diagnostics(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        output_root=tmp_path / "reports" / "prediction_diagnostics" / "baseline",
        run="baseline",
    )

    assert result["status"] == "PREDICTION_DIAGNOSTICS_READY"
    assert result["prediction_diagnostics_ready"] is True
    assert result["failure_count"] == 0
    assert result["prediction_count"] == len(pd.read_parquet(prediction_path))
    target_summary = pd.read_csv(
        tmp_path
        / "reports"
        / "prediction_diagnostics"
        / "baseline"
        / "prediction_target_summary.csv"
    )
    assert {"mean_ic_pearson", "mean_rank_ic_spearman", "ic_dispersion"} <= set(
        target_summary.columns
    )
    assert any(key.endswith("oos_predictions.parquet") for key in result["input_file_hashes"])
