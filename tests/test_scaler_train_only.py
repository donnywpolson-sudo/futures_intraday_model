import json

import polars as pl

from pipeline.common.config import PipelineConfig, RootConfig
from pipeline.features.preprocessing import fit_apply_train_scaler


def test_scaler_uses_train_distribution_only_and_persists_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = RootConfig(pipeline=PipelineConfig(modeling_mode="full_research"))
    train = pl.DataFrame({"x": [0.0, 2.0, 4.0], "y": [0.0, 1.0, 2.0]})
    test = pl.DataFrame({"x": [1000.0, 2000.0], "y": [0.0, 1.0]})
    train_s, test_s, artifact = fit_apply_train_scaler(
        train,
        test,
        ["x"],
        {"config": cfg, "symbol": "ES", "run_id": "r1", "split_id": "1", "train_start": 0, "train_end": 3, "test_start": 3, "test_end": 5},
    )
    payload = json.loads((tmp_path / artifact["path"]).read_text(encoding="utf-8"))
    assert payload["features"]["x"]["mean"] == 2.0
    assert payload["train_start"] == 0
    assert payload["modeling_mode"] == "full_research"
    assert train_s["x"].mean() == 0.0
    assert test_s["x"].mean() > 100.0
