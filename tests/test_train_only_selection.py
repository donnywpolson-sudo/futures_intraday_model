import json

import polars as pl

from pipeline.common.config import PipelineConfig, RootConfig
from pipeline.features.discovery import select_features_train_only


def test_train_only_feature_selection_cannot_see_test_only_predictive_feature(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = RootConfig(pipeline=PipelineConfig(modeling_mode="full_research"))
    train = pl.DataFrame({"x_train": [0.0, 1.0, 2.0, 3.0], "test_only_edge": [None, None, None, None], "y": [0.0, 1.0, 2.0, 3.0]})
    test = pl.DataFrame({"x_train": [0.0, 0.0], "test_only_edge": [100.0, -100.0], "y": [100.0, -100.0]})
    selected, artifact = select_features_train_only(
        train,
        test,
        ["x_train", "test_only_edge"],
        "y",
        {"config": cfg, "symbol": "ES", "run_id": "r1", "split_id": "1", "train_start": 0, "train_end": 4, "test_start": 4, "test_end": 6},
    )
    assert "x_train" in selected
    assert "test_only_edge" not in selected
    payload = json.loads((tmp_path / artifact["path"]).read_text(encoding="utf-8"))
    assert payload["modeling_mode"] == "full_research"
    assert payload["train_end"] == 4
