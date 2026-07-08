from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase7_prediction_audit.audit_predictions import build_prediction_audit  # noqa: E402
from tests.phase8_model_selection.test_evaluate_predictions import (  # noqa: E402
    _write_manifest,
    _write_predictions,
)


def test_phase7_prediction_audit_writes_report(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )

    result = build_prediction_audit(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        output_root=tmp_path / "reports" / "prediction_audit" / "baseline",
        run="baseline",
    )

    assert result["status"] == "PASS"
    assert result["diagnostic_type"] == "phase7_prediction_audit"
    assert result["phase7_prediction_audit_ready"] is True
    assert result["prediction_diagnostics_ready"] is True
    assert result["model_promotion_allowed"] is False
    assert result["outputs"]["summary"].endswith("prediction_audit_summary.json")
    assert result["outputs"]["legacy_prediction_diagnostics_summary"].endswith(
        "prediction_diagnostics_summary.json"
    )
    summary_path = (
        tmp_path
        / "reports"
        / "prediction_audit"
        / "baseline"
        / "prediction_audit_summary.json"
    )
    saved = json.loads(summary_path.read_text(encoding="utf-8"))
    assert saved["phase7_public_gate"] is True
    assert saved["input_file_hashes"] == result["input_file_hashes"]
