import polars as pl

from pipeline.data_gate.preflight import DatasetPreflightError, validate_research_data_preflight
from pipeline.common.config import DataSectionConfig, RootConfig
from scripts.validate_databento_continuous import validate_raw_to_validated


def test_validation_writes_validated_parquet_and_manifests(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    p.parent.mkdir(parents=True)
    pl.DataFrame({"ts_event": [1], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1]}).write_parquet(p)
    report = validate_raw_to_validated("data/raw", "data/validated", write_validated=True)
    assert report["status"] == "PASS"
    assert (tmp_path / "data" / "validated" / "ES" / "2024.parquet").exists()
    assert (tmp_path / "data" / "validated" / "manifest.json").exists()
    assert (tmp_path / "reports" / "validation" / "raw_validation_report.json").exists()


def test_validation_filters_markets_and_years(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for market, year in [("ES", 2023), ("ES", 2025), ("CL", 2024), ("ZN", 2025), ("NQ", 2025)]:
        p = tmp_path / "data" / "raw" / market / f"{year}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame({"ts_event": [1], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1]}).write_parquet(p)
    report = validate_raw_to_validated(
        "data/raw",
        "data/validated",
        write_validated=True,
        markets=["ES", "CL"],
        start_year=2024,
        end_year=2025,
    )
    assert report["status"] == "PASS"
    assert sorted((r["market"], r["year"]) for r in report["files"]) == [("CL", "2024"), ("ES", "2025")]
    assert (tmp_path / "data" / "validated" / "ES" / "2025.parquet").exists()
    assert not (tmp_path / "data" / "validated" / "ES" / "2023.parquet").exists()
    assert not (tmp_path / "data" / "validated" / "NQ" / "2025.parquet").exists()


def test_validation_canonicalizes_metadata_heavy_raw_schema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "data" / "raw" / "6B" / "2025.parquet"
    p.parent.mkdir(parents=True)
    pl.DataFrame(
        {
            "rtype": pl.Series([32], dtype=pl.UInt8),
            "publisher_id": pl.Series([1], dtype=pl.UInt16),
            "instrument_id": pl.Series([100], dtype=pl.UInt32),
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": pl.Series([1], dtype=pl.UInt64),
            "symbol": ["6B"],
            "ts_event": pl.datetime_range(pl.datetime(2025, 1, 1), pl.datetime(2025, 1, 1), "1d", eager=True).dt.replace_time_zone("UTC"),
        }
    ).write_parquet(p)
    report = validate_raw_to_validated("data/raw", "data/validated", write_validated=True)
    out = pl.read_parquet(tmp_path / "data" / "validated" / "6B" / "2025.parquet")
    assert report["status"] == "PASS"
    assert out.columns == ["ts_event", "open", "high", "low", "close", "volume"]
    assert out.schema["ts_event"] == pl.Datetime("ns", "UTC")
    for col in ["open", "high", "low", "close", "volume"]:
        assert out.schema[col] == pl.Float64


def test_validated_only_manifest_fails_preflight(tmp_path):
    root = tmp_path / "data" / "validated"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text('{"files":[]}', encoding="utf-8")
    cfg = RootConfig(symbols=["ES"], start_year=2024, end_year=2024, data=DataSectionConfig(root=str(root), validated_root=str(root)))
    try:
        validate_research_data_preflight(cfg, tmp_path / "report.json")
    except DatasetPreflightError as exc:
        assert "only manifests" in str(exc) or "missing validated parquet" in str(exc)
    else:
        raise AssertionError("expected preflight failure")
