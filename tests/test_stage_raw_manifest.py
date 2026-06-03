import json

import polars as pl

from pipeline.data_gate.manifest import build_data_manifest


def test_raw_manifest_writes_json_and_csv(tmp_path):
    p = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    p.parent.mkdir(parents=True)
    pl.DataFrame({"ts_event": [1], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1]}).write_parquet(p)
    report = build_data_manifest(tmp_path / "data" / "raw", stage="raw")
    assert report["files"]
    assert (tmp_path / "data" / "raw" / "manifest.json").exists()
    assert (tmp_path / "data" / "raw" / "_manifest.csv").exists()
    assert json.loads((tmp_path / "data" / "raw" / "manifest.json").read_text())["stage"] == "raw"

