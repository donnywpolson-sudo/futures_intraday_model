from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.es_hypothesis_harness import run_harness


def _write_split_plan(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    folds = []
    specs = [
        ("ES_research_0001", "2024-01-01T00:00:00+00:00", "2024-01-01T23:00:00+00:00"),
        ("ES_research_0005", "2024-01-02T00:00:00+00:00", "2024-01-02T23:00:00+00:00"),
    ]
    for fold_id, test_start, test_end in specs:
        folds.append(
            {
                "market": "ES",
                "fold_id": fold_id,
                "split_group": "research",
                "train_start": "2023-01-01T00:00:00+00:00",
                "purged_train_end": "2023-01-02T23:00:00+00:00",
                "test_start": test_start,
                "test_end": test_end,
                "is_final_holdout": False,
                "final_holdout": False,
                "selection_allowed": True,
            }
        )
    path.write_text(
        json.dumps({"profile": "fixture", "markets": ["ES"], "years": [2023, 2024], "folds": folds}),
        encoding="utf-8",
    )
    return path


def _write_feature_matrices(root: Path, *, flip_confirmation: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "feature_cols.json").write_text(json.dumps(["feature_signal"]), encoding="utf-8")
    es_root = root / "ES"
    es_root.mkdir(parents=True, exist_ok=True)

    train_ts = pd.date_range("2023-01-01T00:00:00Z", periods=48, freq="h")
    train_side = [1 if idx % 2 == 0 else -1 for idx in range(len(train_ts))]
    pd.DataFrame(
        {
            "ts": train_ts,
            "market": "ES",
            "year": 2023,
            "session_id": "session",
            "session_segment_id": "segment",
            "causal_valid": True,
            "target_valid": True,
            "feature_input_valid": True,
            "training_row_valid": True,
            "target_net_dollars_after_est_cost": [100.0 * side for side in train_side],
            "target_gross_dollars_15m": [125.0 * side for side in train_side],
            "round_turn_cost_dollars": 25.0,
            "feature_signal": [float(side) for side in train_side],
        }
    ).to_parquet(es_root / "2023.parquet", index=False)

    test_ts = pd.date_range("2024-01-01T00:00:00Z", periods=48, freq="h")
    test_side = [1 if idx % 2 == 0 else -1 for idx in range(len(test_ts))]
    feature_side = [
        -side if flip_confirmation and ts >= pd.Timestamp("2024-01-02T00:00:00Z") else side
        for side, ts in zip(test_side, test_ts)
    ]
    pd.DataFrame(
        {
            "ts": test_ts,
            "market": "ES",
            "year": 2024,
            "session_id": "session",
            "session_segment_id": "segment",
            "causal_valid": True,
            "target_valid": True,
            "feature_input_valid": True,
            "training_row_valid": True,
            "target_net_dollars_after_est_cost": [100.0 * side for side in test_side],
            "target_gross_dollars_15m": [125.0 * side for side in test_side],
            "round_turn_cost_dollars": 25.0,
            "feature_signal": [float(side) for side in feature_side],
        }
    ).to_parquet(es_root / "2024.parquet", index=False)


def test_harness_graduates_only_when_discovery_and_confirmation_are_positive(tmp_path: Path) -> None:
    input_root = tmp_path / "data" / "feature_matrices" / "baseline"
    reports_root = tmp_path / "reports" / "pipeline_audit"
    split_plan = _write_split_plan(tmp_path / "reports" / "wfa" / "split_plan.json")
    _write_feature_matrices(input_root)

    report = run_harness(
        run="fixture_positive",
        input_root=input_root,
        split_plan=split_plan,
        reports_root=reports_root,
        feature_family=None,
        features=["feature_signal"],
        discovery_fold_ids=["ES_research_0001"],
        confirmation_fold_ids=["ES_research_0005"],
        top_fraction=0.25,
    )

    assert report["graduation_allowed"] is True
    assert report["decision"] == "GRADUATE_TO_LOCKED_OOS_RECHECK"
    assert report["stage_summaries"]["discovery"]["top_total_net_dollars"] > 0
    assert report["stage_summaries"]["confirmation"]["top_total_net_dollars"] > 0
    assert (reports_root / "fixture_positive_hypothesis_harness.json").exists()
    assert (reports_root / "fixture_positive_hypothesis_harness.md").exists()


def test_harness_stops_when_confirmation_fails(tmp_path: Path) -> None:
    input_root = tmp_path / "data" / "feature_matrices" / "baseline"
    reports_root = tmp_path / "reports" / "pipeline_audit"
    split_plan = _write_split_plan(tmp_path / "reports" / "wfa" / "split_plan.json")
    _write_feature_matrices(input_root, flip_confirmation=True)

    report = run_harness(
        run="fixture_negative",
        input_root=input_root,
        split_plan=split_plan,
        reports_root=reports_root,
        feature_family=None,
        features=["feature_signal"],
        discovery_fold_ids=["ES_research_0001"],
        confirmation_fold_ids=["ES_research_0005"],
        top_fraction=0.25,
    )

    assert report["graduation_allowed"] is False
    assert report["decision"] == "STOP_REWORK_HYPOTHESIS"
    assert report["stage_summaries"]["discovery"]["top_total_net_dollars"] > 0
    assert report["stage_summaries"]["confirmation"]["top_total_net_dollars"] < 0


def test_harness_rejects_features_missing_from_registry(tmp_path: Path) -> None:
    input_root = tmp_path / "data" / "feature_matrices" / "baseline"
    split_plan = _write_split_plan(tmp_path / "reports" / "wfa" / "split_plan.json")
    _write_feature_matrices(input_root)

    with pytest.raises(SystemExit, match="selected features missing from registry"):
        run_harness(
            run="fixture_missing",
            input_root=input_root,
            split_plan=split_plan,
            reports_root=tmp_path / "reports" / "pipeline_audit",
            feature_family=None,
            features=["feature_does_not_exist"],
            discovery_fold_ids=["ES_research_0001"],
            confirmation_fold_ids=["ES_research_0005"],
        )
