import json

import polars as pl

from pipeline.common.config import DataSectionConfig, RootConfig
from pipeline.data_gate.preflight import DatasetPreflightError, validate_research_data_preflight


def _cfg(root, manifest_required=True):
    return RootConfig(
        symbols=["ES"],
        start_year=2024,
        end_year=2024,
        data=DataSectionConfig(
            root=str(root),
            validated_root=str(root),
            raw_root=str(root.parent / "raw"),
            manifest_required=manifest_required,
            require_validated_files=True,
            forbid_raw_fallback_after_validation=True,
        ),
    )


def test_validated_root_with_only_manifest_fails(tmp_path):
    root = tmp_path / "validated"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    try:
        validate_research_data_preflight(_cfg(root), tmp_path / "report.json")
    except DatasetPreflightError as exc:
        assert "only manifests" in str(exc) or "missing validated parquet" in str(exc)
    else:
        raise AssertionError("expected preflight failure")


def test_validated_root_with_parquet_passes(tmp_path):
    root = tmp_path / "validated"
    path = root / "ES" / "2024.parquet"
    path.parent.mkdir(parents=True)
    pl.DataFrame({"ts_event": [1], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1]}).write_parquet(path)
    (root / "manifest.json").write_text(json.dumps({"files": [str(path.as_posix())]}), encoding="utf-8")
    report = validate_research_data_preflight(_cfg(root), tmp_path / "report.json")
    assert report["status"] == "PASS"


def test_missing_manifest_fails(tmp_path):
    root = tmp_path / "validated"
    path = root / "ES" / "2024.parquet"
    path.parent.mkdir(parents=True)
    pl.DataFrame({"ts_event": [1], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1]}).write_parquet(path)
    try:
        validate_research_data_preflight(_cfg(root), tmp_path / "report.json")
    except DatasetPreflightError as exc:
        assert "missing manifest" in str(exc)
    else:
        raise AssertionError("expected missing manifest failure")


def test_raw_fallback_is_rejected(tmp_path):
    raw = tmp_path / "raw"
    cfg = RootConfig(data=DataSectionConfig(root=str(raw), raw_root=str(raw), validated_root=str(tmp_path / "validated")))
    try:
        validate_research_data_preflight(cfg, tmp_path / "report.json")
    except DatasetPreflightError as exc:
        assert "raw fallback rejected" in str(exc)
    else:
        raise AssertionError("expected raw fallback rejection")
