from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.io_safe import atomic_write_json


def fit_apply_train_scaler(
    train_df: pl.DataFrame,
    test_df: pl.DataFrame,
    feature_cols: list[str],
    context: dict[str, Any],
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    params: dict[str, dict[str, float]] = {}
    for c in feature_cols:
        s = train_df[c].cast(pl.Float64)
        median = float(s.median() or 0.0)
        mean = float(s.fill_null(median).mean() or 0.0)
        std = float(s.fill_null(median).std() or 0.0)
        if std == 0.0 or std != std:
            std = 1.0
        params[c] = {"median": median, "mean": mean, "std": std}

    train_scaled = _apply(train_df, params)
    test_scaled = _apply(test_df, params)
    cfg = context["config"]
    artifact = {
        "features": params,
        "train_start": context.get("train_start"),
        "train_end": context.get("train_end"),
        "test_start": context.get("test_start"),
        "test_end": context.get("test_end"),
        "modeling_mode": getattr(cfg.pipeline, "modeling_mode", "unknown"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    path = _scaler_path(context)
    atomic_write_json(path, artifact)
    artifact["path"] = str(path)
    return train_scaled, test_scaled, artifact


def _apply(df: pl.DataFrame, params: dict[str, dict[str, float]]) -> pl.DataFrame:
    exprs = []
    for c, p in params.items():
        exprs.append(((pl.col(c).cast(pl.Float64).fill_nan(None).fill_null(p["median"]) - p["mean"]) / p["std"]).alias(c))
    return df.with_columns(exprs) if exprs else df


def _scaler_path(context: dict[str, Any]) -> Path:
    run_id = str(context.get("run_id") or "default")
    symbol = str(context.get("symbol") or "UNKNOWN")
    split_id = str(context.get("split_id") or 1)
    return Path("artifacts/scalers") / run_id / f"{symbol}_split_{split_id}_scaler.json"

