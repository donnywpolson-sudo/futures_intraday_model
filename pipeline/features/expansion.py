from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from pipeline.data_gate.manifest import build_data_manifest
from pipeline.features.registry import build_column_registry, write_column_registry
from pipeline.common.cache import build_cache_metadata, cache_is_fresh, write_cache_metadata
from pipeline.validation.diagnostic_io import write_csv_json


STAGE20_MANIFEST_CSV = Path("reports/validation/stage_20_feature_expansion_manifest.csv")
STAGE20_MANIFEST_JSON = Path("reports/validation/stage_20_feature_expansion_manifest.json")
MANIFEST_FIELDS = [
    "feature", "family", "lookback", "causal", "session_safe", "required_input_columns",
    "missing_pct", "zero_variance_flag", "created_at",
]


def expand_features(df: pl.DataFrame, config: Any | None = None) -> pl.DataFrame:
    if config is not None and not getattr(getattr(config, "pipeline", object()), "enable_expansion", True):
        return df
    registry = build_column_registry(df, source_stage="pre_expansion")
    features = [c for c in registry["feature_columns"] if c in df.columns]
    exprs = []
    exprs.extend(_ohlcv_feature_exprs(df))
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
        _write_stage20_manifest(out_root, config)
    return {"status": "PASS", "files": rows}


def _ohlcv_feature_exprs(df: pl.DataFrame) -> list[pl.Expr]:
    cols = set(df.columns)
    has_session = "session_id" in cols

    def sess(expr: pl.Expr) -> pl.Expr:
        return expr.over("session_id") if has_session else expr

    def finite(expr: pl.Expr) -> pl.Expr:
        return pl.when(expr.is_finite()).then(expr).otherwise(None).fill_null(0.0)

    exprs: list[pl.Expr] = []
    if "close" in cols:
        for n in [1, 3, 5, 15, 30, 60]:
            ret = sess(pl.col("close").pct_change(n))
            exprs.append(finite(ret).alias(f"ret_{n}"))
        ret1 = sess(pl.col("close").pct_change(1))
        for n in [1, 3, 5, 15]:
            exprs.append(finite(sess(ret1.shift(n))).alias(f"ret_lag_{n}"))
        for n in [5, 15, 30, 60]:
            exprs.append(finite(sess(ret1.rolling_std(n))).alias(f"roll_vol_{n}"))
        for n in [5, 15, 30, 60]:
            ema = sess(pl.col("close").ewm_mean(span=n, adjust=False))
            exprs.append(finite((pl.col("close") / (ema + 1e-12)) - 1.0).alias(f"dist_ema_{n}"))
        for n in [15, 30, 60]:
            ema = sess(pl.col("close").ewm_mean(span=n, adjust=False))
            exprs.append(finite(ema - sess(ema.shift(n))).alias(f"slope_ema_{n}"))
    if {"high", "low", "close"}.issubset(cols):
        bar_range = pl.col("high") - pl.col("low")
        exprs.append(finite(bar_range / (pl.col("close").abs() + 1e-12)).alias("bar_range"))
        for n in [5, 15, 30, 60]:
            exprs.append(finite(sess((bar_range / (pl.col("close").abs() + 1e-12)).rolling_mean(n))).alias(f"roll_range_{n}"))
        for n in [15, 30, 60]:
            hi = sess(pl.col("high").rolling_max(n))
            lo = sess(pl.col("low").rolling_min(n))
            exprs.append(finite((pl.col("close") - lo) / ((hi - lo) + 1e-12)).alias(f"pos_in_{n}m_range"))
    if "volume" in cols:
        for n in [5, 15, 30, 60]:
            exprs.append(finite(sess(pl.col("volume").cast(pl.Float64).rolling_mean(n))).alias(f"roll_volume_{n}"))
        for n in [15, 60]:
            vol = pl.col("volume").cast(pl.Float64)
            mu = sess(vol.rolling_mean(n))
            sd = sess(vol.rolling_std(n))
            exprs.append(finite((vol - mu) / (sd + 1e-12)).alias(f"volume_z_{n}"))
    if {"open", "high", "low", "close"}.issubset(cols):
        rng = pl.col("high") - pl.col("low")
        body = pl.col("close") - pl.col("open")
        exprs.extend([
            finite(body).alias("body"),
            finite(pl.col("high") - pl.max_horizontal("open", "close")).alias("upper_wick"),
            finite(pl.min_horizontal("open", "close") - pl.col("low")).alias("lower_wick"),
            finite(body / (rng + 1e-12)).alias("body_to_range"),
            finite((pl.col("close") - pl.col("low")) / (rng + 1e-12)).alias("close_position_in_range"),
        ])
    if "ts_event" in cols and getattr(df.schema.get("ts_event"), "is_temporal", lambda: False)():
        minute = pl.col("ts_event").dt.hour() * 60 + pl.col("ts_event").dt.minute()
        exprs.extend([
            (2.0 * 3.141592653589793 * minute / 1440.0).sin().alias("minute_of_day_sin"),
            (2.0 * 3.141592653589793 * minute / 1440.0).cos().alias("minute_of_day_cos"),
            pl.col("ts_event").dt.weekday().cast(pl.Float64).alias("day_of_week"),
        ])
    return exprs


def _write_stage20_manifest(out_root: Path, config: Any | None) -> None:
    paths = sorted(out_root.glob("*/*.parquet"))
    if not paths:
        return
    schema = pl.scan_parquet(paths[0]).collect_schema()
    feature_cols = build_column_registry(pl.read_parquet(paths[0], n_rows=5), source_stage="expanded")["feature_columns"]
    rows = []
    from datetime import datetime, timezone

    created_at = datetime.now(timezone.utc).isoformat()
    for feature in feature_cols:
        if feature not in schema.names():
            continue
        rows.append({
            "feature": feature,
            "family": _family(feature),
            "lookback": _lookback(feature),
            "causal": True,
            "session_safe": True,
            "required_input_columns": _required_inputs(feature),
            **_feature_stats(paths, feature),
            "created_at": created_at,
        })
    write_csv_json(rows, csv_path=STAGE20_MANIFEST_CSV, json_path=STAGE20_MANIFEST_JSON, fields=MANIFEST_FIELDS)


def _feature_stats(paths: list[Path], feature: str) -> dict[str, Any]:
    stats = pl.scan_parquet(paths).select(
        pl.len().alias("n"),
        pl.col(feature).null_count().alias("nulls"),
        pl.col(feature).cast(pl.Float64, strict=False).std().alias("std"),
    ).collect().row(0, named=True)
    n = float(stats.get("n") or 0)
    nulls = float(stats.get("nulls") or 0)
    std = float(stats.get("std") or 0.0)
    return {
        "missing_pct": 0.0 if n == 0 else nulls / n,
        "zero_variance_flag": bool(std == 0.0),
    }


def _lookback(feature: str) -> str:
    import re

    found = re.findall(r"_(\d+)(?:m)?(?:_|$)", feature)
    return found[-1] if found else ""


def _family(feature: str) -> str:
    if feature.startswith(("ret_", "ret_lag_")):
        return "returns"
    if feature.startswith("roll_vol_"):
        return "rolling_volatility"
    if feature.startswith("roll_range_") or feature == "bar_range":
        return "rolling_range"
    if feature.startswith("roll_volume_"):
        return "rolling_volume"
    if feature.startswith("volume_z_"):
        return "volume_zscore"
    if feature in {"body", "upper_wick", "lower_wick", "body_to_range", "close_position_in_range"}:
        return "bar_shape"
    if feature.startswith(("dist_ema_", "slope_ema_")):
        return "moving_average"
    if feature.startswith("pos_in_"):
        return "rolling_high_low_position"
    if feature in {"minute_of_day_sin", "minute_of_day_cos", "day_of_week"}:
        return "time"
    return "interaction" if feature.startswith("xp_") else "other"


def _required_inputs(feature: str) -> str:
    if feature.startswith(("ret_", "ret_lag_", "roll_vol_", "dist_ema_", "slope_ema_")):
        return "close"
    if feature.startswith("roll_volume_") or feature.startswith("volume_z_"):
        return "volume"
    if feature.startswith("pos_in_") or feature.startswith("roll_range_") or feature in {"bar_range", "body", "upper_wick", "lower_wick", "body_to_range", "close_position_in_range"}:
        return "open,high,low,close"
    if feature.startswith("minute_") or feature == "day_of_week":
        return "ts_event"
    if feature.startswith("xp_"):
        return "derived_features"
    return ""
