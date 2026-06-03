import json

import polars as pl

from pipeline.features.registry import build_column_registry, write_column_registry


def test_column_registry_separates_feature_target_metadata(tmp_path):
    df = pl.DataFrame({"ts_event": [1], "x": [1.0], "target_15m_ret": [0.1], "roll_flag": [1], "settlement_available_at": [1]})
    reg = build_column_registry(df, "baseline")
    assert "x" in reg["feature_columns"]
    assert "target_15m_ret" in reg["target_columns"]
    assert "roll_flag" in reg["metadata_columns"]
    assert "target_15m_ret" in reg["forbidden_model_columns"]
    path = tmp_path / "column_registry.json"
    write_column_registry(df, path, "baseline")
    assert json.loads(path.read_text())["source_stage"] == "baseline"

