from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.config import config
from pipeline.common.io_safe import atomic_write_json


def _as_lf(df: pl.DataFrame | pl.LazyFrame) -> pl.LazyFrame:
    return df.lazy() if isinstance(df, pl.DataFrame) else df


def run_leakage_audit(df: pl.DataFrame | pl.LazyFrame, feature_cols: list[str], target_col: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    lf = _as_lf(df)
    cols = lf.collect_schema().names()
    failures: list[str] = []
    warnings: list[str] = []
    forbidden = getattr(config, "LEAKAGE_FORBIDDEN_FEATURE_PREFIXES", ["target_", "future_", "label_"])
    meta_forbidden = getattr(config, "LEAKAGE_FORBIDDEN_MODEL_METADATA_PREFIXES", ["continuous_", "roll_", "front_contract", "back_contract"])
    max_corr = getattr(config, "LEAKAGE_MAX_ALLOWED_FEATURE_TARGET_ABS_CORR", 0.999)
    for c in feature_cols:
        if any(c.startswith(p) for p in forbidden):
            failures.append(f"forbidden feature prefix: {c}")
        if any(c.startswith(p) for p in meta_forbidden):
            failures.append(f"forbidden model metadata feature: {c}")
        if c not in cols:
            failures.append(f"missing feature column: {c}")
    if target_col not in cols:
        failures.append(f"missing target column: {target_col}")
    pred_col = getattr(config, "POINT_IN_TIME_PREDICTION_TIME_COL", "prediction_time")
    suffix = getattr(config, "POINT_IN_TIME_AVAILABILITY_TIME_SUFFIX", "_available_at")
    if pred_col in cols:
        for c in feature_cols:
            ac = c + suffix
            if ac in cols:
                bad = lf.select((pl.col(ac) > pl.col(pred_col)).sum().alias("bad")).collect()["bad"][0]
                if bad:
                    failures.append(f"availability after prediction_time: {c} rows={bad}")
    numeric = [c for c in feature_cols + [target_col] if c in cols]
    if numeric:
        bad_exprs = [(~pl.col(c).is_finite()).sum().alias(c) for c in numeric]
        bads = lf.select(bad_exprs).collect().row(0, named=True)
        for c, n in bads.items():
            if n:
                failures.append(f"non-finite values: {c} rows={n}")
    for c in feature_cols:
        if c in cols and target_col in cols:
            try:
                corr = lf.select(pl.corr(c, target_col).abs().alias("corr")).collect()["corr"][0]
                if corr is not None and corr >= max_corr:
                    failures.append(f"near-perfect feature/target correlation: {c} corr={corr}")
            except Exception as exc:
                warnings.append(f"corr skipped for {c}: {exc}")
    status = "FAIL" if failures else ("WARN" if warnings else "PASS")
    report = {"status": status, "failures": failures, "warnings": warnings, "context": context}
    out = context.get("out")
    if out:
        atomic_write_json(out, report)
    return report
