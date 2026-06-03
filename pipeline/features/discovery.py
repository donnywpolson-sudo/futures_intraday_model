from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.io_safe import atomic_write_json
from pipeline.common.cache import build_cache_metadata, write_cache_metadata


def select_features_train_only(
    train_df: pl.DataFrame,
    test_df: pl.DataFrame,
    feature_cols: list[str],
    target_col: str,
    context: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    cfg = context["config"]
    max_features = int(getattr(cfg.discovery, "max_selected_features", 1000))
    seed = int(getattr(cfg.preprocessing, "seed", 42))
    available = [c for c in feature_cols if c in train_df.columns and c in test_df.columns]
    rejected = [c for c in feature_cols if c not in available]
    rankings = []
    for c in available:
        score = _abs_corr(train_df, c, target_col)
        if score is None:
            rejected.append(c)
        else:
            rankings.append({"feature": c, "score": score})
    rankings.sort(key=lambda r: (-r["score"], r["feature"]))
    selected = [r["feature"] for r in rankings[:max_features]]
    feature_set_id = _feature_set_id(selected)
    artifact = {
        "selected_features": selected,
        "rejected_features": sorted(set(rejected)),
        "feature_set_id": feature_set_id,
        "target_col": target_col,
        "train_start": context.get("train_start"),
        "train_end": context.get("train_end"),
        "test_start": context.get("test_start"),
        "test_end": context.get("test_end"),
        "selection_method": "train_abs_corr",
        "random_seed": seed,
        "feature_ranking": rankings,
        "source_stage": "train_only_feature_selection",
        "output_stage": "frozen_feature_set",
        "modeling_mode": getattr(cfg.pipeline, "modeling_mode", "unknown"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    path = _selector_path(context)
    atomic_write_json(path, artifact)
    meta = build_cache_metadata(
        path,
        source_stage="feature_discovery",
        output_stage="frozen_feature_set",
        source_paths=[context.get("source_manifest") or ""],
        config=cfg,
        config_sections=["features", "discovery", "pipeline"],
        code_paths=[__file__],
        symbol=context.get("symbol"),
        split_id=context.get("split_id"),
        train_start=context.get("train_start"),
        train_end=context.get("train_end"),
        test_start=context.get("test_start"),
        test_end=context.get("test_end"),
    )
    write_cache_metadata(path, meta)
    artifact["path"] = str(path)
    return selected, artifact


def _abs_corr(df: pl.DataFrame, feature: str, target_col: str) -> float | None:
    if df.height < 2:
        return None
    try:
        row = df.select(pl.corr(feature, target_col).alias("corr")).row(0, named=True)
        val = row["corr"]
        if val is None or val != val:
            return None
        return abs(float(val))
    except Exception:
        return None


def _selector_path(context: dict[str, Any]) -> Path:
    run_id = str(context.get("run_id") or "default")
    symbol = str(context.get("symbol") or "UNKNOWN")
    split_id = str(context.get("split_id") or 1)
    return Path("artifacts/selectors") / run_id / f"{symbol}_split_{split_id}_features.json"


def _feature_set_id(features: list[str]) -> str:
    import hashlib

    return hashlib.sha256("\n".join(features).encode("utf-8")).hexdigest()[:16]
