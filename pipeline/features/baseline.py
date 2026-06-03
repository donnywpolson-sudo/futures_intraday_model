from __future__ import annotations

from pathlib import Path

import polars as pl

from pipeline.common.io_safe import atomic_write_json
from pipeline.common.cache import build_cache_metadata, cache_is_fresh, write_cache_metadata
from pipeline.data_gate.manifest import build_data_manifest
from pipeline.features.registry import write_column_registry


def build_baseline_features(df: pl.DataFrame) -> pl.DataFrame:
    exprs = []
    if "close" in df.columns:
        exprs += [
            pl.col("close").pct_change().fill_null(0).alias("ret_lag_1"),
            pl.col("close").pct_change().rolling_std(5).fill_null(0).alias("roll_vol_5"),
        ]
    if "volume" in df.columns:
        exprs.append(pl.col("volume").cast(pl.Float64).rolling_mean(5).fill_null(0).alias("roll_volume_5"))
    if {"high", "low", "close"}.issubset(df.columns):
        exprs.append(((pl.col("high") - pl.col("low")) / pl.col("close")).fill_null(0).alias("roll_range_1"))
    if "session_id" in df.columns:
        exprs.append(pl.col("session_id").cum_count().over("session_id").alias("session_bar_index"))
    out = df.with_columns(exprs) if exprs else df
    bad = [c for c in out.columns if c.startswith("future_")]
    if bad:
        return out.drop(bad)
    return out


def baseline_feature_root(in_root: str | Path = "data/labeled", out_root: str | Path = "data/feature_matrices/baseline", config=None) -> dict:
    in_root = Path(in_root)
    out_root = Path(out_root)
    rows = []
    sample = None
    src_manifest = in_root / "manifest.json"
    for p in sorted(in_root.glob("*/*.parquet")):
        out = out_root / p.parent.name / p.name
        out.parent.mkdir(parents=True, exist_ok=True)
        meta = build_cache_metadata(
            out,
            source_stage="labeled",
            output_stage="baseline_feature_matrix",
            source_paths=[src_manifest if src_manifest.exists() else p],
            config=config,
            config_sections=["features", "target", "pipeline"],
            code_paths=[__file__],
            symbol=p.parent.name,
            year=p.stem,
        ) if config is not None else None
        fresh, _ = cache_is_fresh(out, meta, config) if meta else (False, "no config")
        if fresh:
            sample = pl.read_parquet(out)
            rows.append({"input": str(p), "output": str(out), "status": "COMPLETED_CACHED"})
            continue
        mat = build_baseline_features(pl.read_parquet(p))
        mat.write_parquet(out)
        if meta:
            write_cache_metadata(out, meta)
        sample = mat
        rows.append({"input": str(p), "output": str(out), "status": "PASS"})
    report = {"status": "PASS", "files": rows}
    atomic_write_json("reports/metrics/baseline_feature_matrix_report.json", report)
    build_data_manifest(out_root, stage="baseline_feature_matrix")
    if sample is not None:
        write_column_registry(sample, out_root / "column_registry.json", source_stage="baseline", config=config, source_paths=[out_root / "manifest.json"])
    return report
