import json
import os
from pathlib import Path

import polars as pl

from pipeline.common.cache import build_cache_metadata, cache_is_fresh, read_cache_metadata, write_cache_metadata
from pipeline.common.config import ExecutionConfig, FeaturesConfig, IOConfig, RootConfig, TargetConfig
from pipeline.data.cache_status import cache_status
from pipeline.data_gate.manifest import build_data_manifest
from pipeline.features.baseline import baseline_feature_root
from pipeline.features.expansion import expanded_feature_root
from pipeline.labels.generate import label_root


def _causal_root(tmp_path):
    root = tmp_path / "data/causally_gated_normalized"
    p = root / "ES" / "2025.parquet"
    p.parent.mkdir(parents=True)
    n = 30
    pl.DataFrame({
        "ts_event": list(range(n)),
        "open": [100.0 + i for i in range(n)],
        "high": [101.0 + i for i in range(n)],
        "low": [99.0 + i for i in range(n)],
        "close": [100.5 + i for i in range(n)],
        "volume": [100 + i for i in range(n)],
        "session_id": ["s"] * n,
        "prediction_time": list(range(n)),
        "earliest_execution_time": [i + 1 for i in range(n)],
    }).write_parquet(p)
    build_data_manifest(root, "causally_gated_normalized")
    return root


def test_unchanged_source_config_reuses_labels_and_features(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _causal_root(tmp_path)
    cfg = RootConfig(target=TargetConfig(target_15m_horizon=1))
    assert label_root(root, "data/labeled", cfg)["files"][0]["status"] == "PASS"
    assert label_root(root, "data/labeled", cfg)["files"][0]["status"] == "COMPLETED_CACHED"
    baseline_feature_root("data/labeled", "data/feature_matrices/baseline", cfg)
    assert baseline_feature_root("data/labeled", "data/feature_matrices/baseline", cfg)["files"][0]["status"] == "COMPLETED_CACHED"


def test_changed_source_manifest_invalidates_labels_and_features(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _causal_root(tmp_path)
    cfg = RootConfig(target=TargetConfig(target_15m_horizon=1))
    label_root(root, "data/labeled", cfg)
    baseline_feature_root("data/labeled", "data/feature_matrices/baseline", cfg)
    manifest = root / "manifest.json"
    raw = json.loads(manifest.read_text())
    raw["changed"] = True
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    assert label_root(root, "data/labeled", cfg)["files"][0]["status"] == "PASS"
    labeled_manifest = Path("data/labeled/manifest.json")
    raw2 = json.loads(labeled_manifest.read_text())
    raw2["changed"] = True
    labeled_manifest.write_text(json.dumps(raw2), encoding="utf-8")
    assert baseline_feature_root("data/labeled", "data/feature_matrices/baseline", cfg)["files"][0]["status"] == "PASS"


def test_changed_target_config_invalidates_labels(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _causal_root(tmp_path)
    cfg = RootConfig(target=TargetConfig(target_15m_horizon=1))
    label_root(root, "data/labeled", cfg)
    changed = RootConfig(target=TargetConfig(target_15m_horizon=2))
    assert label_root(root, "data/labeled", changed)["files"][0]["status"] == "PASS"


def test_changed_feature_config_invalidates_feature_matrices(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _causal_root(tmp_path)
    cfg = RootConfig(target=TargetConfig(target_15m_horizon=1), features=FeaturesConfig(roll_windows=[5]))
    label_root(root, "data/labeled", cfg)
    baseline_feature_root("data/labeled", "data/feature_matrices/baseline", cfg)
    changed = RootConfig(target=TargetConfig(target_15m_horizon=1), features=FeaturesConfig(roll_windows=[5, 10]))
    assert baseline_feature_root("data/labeled", "data/feature_matrices/baseline", changed)["files"][0]["status"] == "PASS"
    expanded_feature_root("data/feature_matrices/baseline", "data/feature_matrices/expanded", changed)
    assert expanded_feature_root("data/feature_matrices/baseline", "data/feature_matrices/expanded", changed)["files"][0]["status"] == "COMPLETED_CACHED"


def test_execution_config_invalidates_backtest_metrics_cache(tmp_path):
    cfg = RootConfig(execution=ExecutionConfig(slippage_ticks=1.0))
    p = tmp_path / "output" / "backtest_results.parquet"
    p.parent.mkdir()
    pl.DataFrame({"pnl": [1.0]}).write_parquet(p)
    meta = build_cache_metadata(p, source_stage="x", output_stage="backtest_results", source_paths=[p], config=cfg, config_sections=["execution"], code_paths=[])
    write_cache_metadata(p, meta)
    assert cache_is_fresh(p, meta, cfg)[0]
    changed = RootConfig(execution=ExecutionConfig(slippage_ticks=2.0))
    expected = build_cache_metadata(p, source_stage="x", output_stage="backtest_results", source_paths=[p], config=changed, config_sections=["execution"], code_paths=[])
    fresh, reason = cache_is_fresh(p, expected, changed)
    assert not fresh
    assert reason == "config mismatch"


def test_missing_metadata_and_skip_completed_false_force_regeneration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _causal_root(tmp_path)
    cfg = RootConfig(target=TargetConfig(target_15m_horizon=1))
    label_root(root, "data/labeled", cfg)
    os.remove("data/labeled/ES/2025.parquet.metadata.json")
    assert label_root(root, "data/labeled", cfg)["files"][0]["status"] == "PASS"
    forced = RootConfig(target=TargetConfig(target_15m_horizon=1), io=IOConfig(skip_completed=False))
    assert label_root(root, "data/labeled", forced)["files"][0]["status"] == "PASS"


def test_cache_status_reports_missing_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "data/x.parquet"
    p.parent.mkdir()
    pl.DataFrame({"x": [1]}).write_parquet(p)
    report = cache_status("data", "artifacts", "reports")
    assert report["counts"]["missing metadata"] >= 1


def test_cache_status_backfills_missing_metadata_as_untrusted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "data/labeled/ES/2025.parquet"
    p.parent.mkdir(parents=True)
    pl.DataFrame({"x": [1]}).write_parquet(p)
    cfg = RootConfig()

    report = cache_status("data", "artifacts", "reports", config=cfg, write_missing_metadata=True)

    assert report["counts"]["backfilled untrusted"] >= 1
    meta = read_cache_metadata(p)
    assert meta is not None
    assert meta["output_stage"] == "labeled"
    assert meta["backfilled"] is True
    assert meta["trusted_for_reuse"] is False
    fresh, reason = cache_is_fresh(p, meta, cfg)
    assert not fresh
    assert reason == "untrusted backfill"


def test_cache_status_trusted_backfill_can_be_reused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "reports/metrics/example_metrics.json"
    p.parent.mkdir(parents=True)
    p.write_text('{"ok": true}', encoding="utf-8")
    cfg = RootConfig()

    cache_status("data", "artifacts", "reports", config=cfg, write_missing_metadata=True, trust_backfill=True)

    meta = read_cache_metadata(p)
    assert meta is not None
    assert meta["output_stage"] == "metrics_report"
    assert meta["trusted_for_reuse"] is True
    fresh, reason = cache_is_fresh(p, meta, cfg)
    assert fresh, reason
