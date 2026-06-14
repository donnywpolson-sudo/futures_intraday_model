from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase7_wfa.combine_wfa_predictions import combine_wfa_prediction_shards


def _write_prediction(path: Path, *, fold_id: str, timestamp: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "market": "ES",
                "year": 2024,
                "fold_id": fold_id,
                "timestamp": pd.Timestamp(timestamp),
                "model_id": "m1",
                "target_name": "target_ret_15m",
                "y_pred_raw": 0.1,
            }
        ]
    ).to_parquet(path, index=False)
    return path


def _write_manifest(path: Path, prediction_path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "failure_count": 0,
                "artifact_evidence_ready": True,
                "prediction_count": 1,
                "prediction_path": prediction_path.as_posix(),
            }
        ),
        encoding="utf-8",
    )
    return path


def test_combine_wfa_prediction_shards_requires_all_folds(tmp_path: Path) -> None:
    pred1 = _write_prediction(
        tmp_path / "data" / "predictions" / "s1" / "oos_predictions.parquet",
        fold_id="ES_research_0001",
        timestamp="2024-01-01T00:00:00Z",
    )
    pred2 = _write_prediction(
        tmp_path / "data" / "predictions" / "s2" / "oos_predictions.parquet",
        fold_id="ES_research_0002",
        timestamp="2024-01-02T00:00:00Z",
    )
    _write_manifest(tmp_path / "reports" / "s1" / "s1_predictions_manifest.json", pred1)
    _write_manifest(tmp_path / "reports" / "s2" / "s2_predictions_manifest.json", pred2)
    split_plan = tmp_path / "reports" / "wfa" / "split_plan.json"
    split_plan.parent.mkdir(parents=True, exist_ok=True)
    split_plan.write_text(
        json.dumps(
            {
                "folds": [
                    {
                        "fold_id": "ES_research_0001",
                        "split_group": "research",
                        "selection_allowed": True,
                    },
                    {
                        "fold_id": "ES_research_0002",
                        "split_group": "research",
                        "selection_allowed": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = combine_wfa_prediction_shards(
        manifest_patterns=[(tmp_path / "reports" / "s*" / "*_predictions_manifest.json").as_posix()],
        run="full",
        predictions_root=tmp_path / "data" / "predictions",
        reports_root=tmp_path / "reports" / "full",
        split_plan=split_plan,
        require_all_folds=True,
    )

    assert manifest["failure_count"] == 0
    assert manifest["prediction_count"] == 2
    assert manifest["fold_count"] == 2
    assert (tmp_path / "data" / "predictions" / "full" / "oos_predictions.parquet").exists()


def test_combine_wfa_prediction_shards_fails_missing_expected_fold(tmp_path: Path) -> None:
    pred1 = _write_prediction(
        tmp_path / "data" / "predictions" / "s1" / "oos_predictions.parquet",
        fold_id="ES_research_0001",
        timestamp="2024-01-01T00:00:00Z",
    )
    _write_manifest(tmp_path / "reports" / "s1" / "s1_predictions_manifest.json", pred1)
    split_plan = tmp_path / "reports" / "wfa" / "split_plan.json"
    split_plan.parent.mkdir(parents=True, exist_ok=True)
    split_plan.write_text(
        json.dumps(
            {
                "folds": [
                    {
                        "fold_id": "ES_research_0001",
                        "split_group": "research",
                        "selection_allowed": True,
                    },
                    {
                        "fold_id": "ES_research_0002",
                        "split_group": "research",
                        "selection_allowed": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = combine_wfa_prediction_shards(
        manifest_patterns=[(tmp_path / "reports" / "s*" / "*_predictions_manifest.json").as_posix()],
        run="full",
        predictions_root=tmp_path / "data" / "predictions",
        reports_root=tmp_path / "reports" / "full",
        split_plan=split_plan,
        require_all_folds=True,
    )

    assert manifest["failure_count"] > 0
    assert "combined predictions missing folds: 1" in manifest["failures"]
