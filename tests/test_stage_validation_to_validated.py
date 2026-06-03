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

