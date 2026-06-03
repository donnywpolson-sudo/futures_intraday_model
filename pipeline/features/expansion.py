from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from pipeline.data_gate.manifest import build_data_manifest
from pipeline.features.registry import build_column_registry, write_column_registry
from pipeline.common.cache import build_cache_metadata, cache_is_fresh, write_cache_metadata


def expand_features(df: pl.DataFrame, config: Any | None = None) -> pl.DataFrame:
    if config is not None and not getattr(getattr(config, "pipeline", object()), "enable_expansion", True):
        return df
    registry = build_column_registry(df, source_stage="pre_expansion")
    features = [c for c in registry["feature_columns"] if c in df.columns]
    exprs = []
    if len(features) >= 2:
        exprs.append((pl.col(features[0]) * pl.col(features[1])).alias(f"xp_{features[0]}__x__{features[1]}"))
    if "roll_vol_5" in df.columns and "ret_lag_1" in df.columns:
        exprs.append((pl.col("ret_lag_1") / (pl.col("roll_vol_5").abs() + 1e-9)).alias("xp_ret_vol_ratio"))
    return df.with_columns(exprs) if exprs else df


def expanded_feature_root(in_root: str | Path = "data/feature_matrices/baseline", out_root: str | Path = "data/feature_matrices/expanded", config: Any | None = None) -> dict:
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
            source_stage="baseline_feature_matrix",
            output_stage="expanded_feature_matrix",
            source_paths=[src_manifest if src_manifest.exists() else p],
            config=config,
            config_sections=["features", "pipeline"],
            code_paths=[__file__],
            symbol=p.parent.name,
            year=p.stem,
        ) if config is not None else None
        fresh, _ = cache_is_fresh(out, meta, config) if meta else (False, "no config")
        if fresh:
            sample = pl.read_parquet(out)
            rows.append({"input": str(p), "output": str(out), "status": "COMPLETED_CACHED"})
            continue
        mat = expand_features(pl.read_parquet(p), config)
        mat.write_parquet(out)
        if meta:
            write_cache_metadata(out, meta)
        sample = mat
        rows.append({"input": str(p), "output": str(out), "status": "PASS"})
    build_data_manifest(out_root, stage="expanded_feature_matrix")
    if sample is not None:
        write_column_registry(sample, out_root / "column_registry.json", source_stage="expanded", config=config, source_paths=[out_root / "manifest.json"])
    return {"status": "PASS", "files": rows}
