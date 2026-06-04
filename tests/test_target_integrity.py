import pytest
import polars as pl

from pipeline.common.config import DataSectionConfig, ExecutionConfig, RootConfig, TargetConfig, WalkforwardConfig
from pipeline.data_gate.checkpoint import validate_checkpoint_stage
from pipeline.features.baseline import baseline_feature_root
from pipeline.labels.generate import add_labels
from pipeline.validation.target_integrity import validate_target_integrity_root


def _base(n=20):
    return pl.DataFrame(
        {
            "ts_event": list(range(n)),
            "open": [100.0 + i for i in range(n)],
            "high": [101.0 + i for i in range(n)],
            "low": [99.0 + i for i in range(n)],
            "close": [100.0 + i for i in range(n)],
            "volume": [100 + i for i in range(n)],
            "symbol": ["ES"] * n,
            "session_id": ["s1"] * n,
            "session_date": ["2025-01-01"] * n,
        }
    )


def _cfg():
    return RootConfig(
        symbols=["ES"],
        start_year=2025,
        end_year=2025,
        target=TargetConfig(target_15m_horizon=2, target_scale_factor=1.0),
        execution=ExecutionConfig(entry_lag_bars=1),
    )


def test_all_null_target_fails_during_baseline_feature_matrix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "data/labeled/ES/2025.parquet"
    p.parent.mkdir(parents=True)
    _base().with_columns(pl.lit(None).cast(pl.Float64).alias("target_15m_ret")).write_parquet(p)
    with pytest.raises(RuntimeError, match="target column all null"):
        baseline_feature_root("data/labeled", "data/feature_matrices/baseline", _cfg())


def test_target_valid_true_and_target_null_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "data/labeled/ES/2025.parquet"
    p.parent.mkdir(parents=True)
    _base().with_columns(
        pl.lit(None).cast(pl.Float64).alias("target_15m_ret"),
        pl.lit(True).alias("target_valid"),
    ).write_parquet(p)
    with pytest.raises(RuntimeError, match="target_valid true but target null"):
        baseline_feature_root("data/labeled", "data/feature_matrices/baseline", _cfg())


def test_config_target_col_missing_from_matrix_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "data/feature_matrices/baseline"
    p = root / "ES/2025.parquet"
    p.parent.mkdir(parents=True)
    _base().with_columns(pl.lit(0.1).alias("other_target")).write_parquet(p)
    cfg = _cfg()
    cfg.walkforward.walkforward_target = "target_15m_ret"
    with pytest.raises(RuntimeError, match="config target_col missing"):
        validate_target_integrity_root(root, cfg)


def test_valid_grouped_target_has_only_expected_horizon_tail_nulls():
    out = add_labels(_base(20), horizon=2, entry_lag_bars=1, target_col="target_15m_ret", target_scale_factor=1.0)
    assert out["target_15m_ret"].drop_nulls().len() == 17
    assert out.filter(pl.col("target_valid")).height == 17
    assert out.tail(3)["target_15m_ret"].null_count() == 3


def test_checkpoint_stale_all_null_target_fails_before_wfa(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "data/feature_matrices/baseline"
    p = root / "ES/2025.parquet"
    p.parent.mkdir(parents=True)
    _base().with_columns(
        pl.lit(None).cast(pl.Float64).alias("target_15m_ret"),
        pl.lit(True).alias("target_valid"),
        pl.lit(1.0).alias("ret_lag_1"),
    ).write_parquet(p)
    (root / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "_manifest.csv").write_text("path\n", encoding="utf-8")
    (root / "column_registry.json").write_text("{}", encoding="utf-8")
    report = validate_checkpoint_stage("baseline_feature_matrix", str(root), _cfg(), ["ES"], 2025, 2025)
    assert report["status"] == "FAIL"
    assert "target integrity" in "; ".join(report["failures"])
