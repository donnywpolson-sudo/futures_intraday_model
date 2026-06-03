import polars as pl

from pipeline.causal.gate import causal_gate_df, causal_gate_root


def test_causal_gating_flags_metadata_and_writes_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "data" / "session_normalized" / "ES" / "2024.parquet"
    p.parent.mkdir(parents=True)
    pl.DataFrame({"ts_event": [1, 2], "settlement_available_at": [1, 3], "roll_flag": [0, 1], "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1]}).write_parquet(p)
    report = causal_gate_root("data/session_normalized", "data/causally_gated_normalized")
    out = pl.read_parquet(tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet")
    assert report["status"] == "PASS"
    assert "non_model_metadata_columns" in out.columns
    assert "settlement_available_at_is_available" in out.columns
    assert (tmp_path / "reports" / "causal_gating" / "causal_gating_report.json").exists()

