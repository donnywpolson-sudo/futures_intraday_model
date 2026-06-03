import polars as pl

from pipeline.session.normalize import normalize_session_df, session_normalize_root


def test_session_normalization_writes_session_id_and_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "data" / "validated" / "ES" / "2024.parquet"
    p.parent.mkdir(parents=True)
    pl.DataFrame({"ts_event": [2, 1, 1], "open": [1.0, 1.0, 1.0], "high": [1.0, 1.0, 1.0], "low": [1.0, 1.0, 1.0], "close": [1.0, 1.0, 1.0], "volume": [1, 1, 1]}).write_parquet(p)
    report = session_normalize_root("data/validated", "data/session_normalized")
    out = pl.read_parquet(tmp_path / "data" / "session_normalized" / "ES" / "2024.parquet")
    assert report["status"] == "PASS"
    assert "session_id" in out.columns
    assert out["ts_event"].n_unique() == out.height
    assert (tmp_path / "data" / "session_normalized" / "manifest.json").exists()

