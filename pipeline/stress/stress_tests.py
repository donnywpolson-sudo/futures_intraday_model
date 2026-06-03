from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.io_safe import atomic_write_json, write_csv_rows


def _pnl_col(df: pl.DataFrame) -> str:
    return "net_pnl" if "net_pnl" in df.columns else "pnl"


def _summary(df: pl.DataFrame, name: str) -> dict[str, Any]:
    col = _pnl_col(df)
    pnl = df[col].cast(pl.Float64)
    mean = float(pnl.mean() or 0.0)
    std = float(pnl.std() or 0.0)
    sharpe = 0.0 if std == 0 else mean / std * (252**0.5)
    return {"scenario": name, "net_pnl": float(pnl.sum() or 0.0), "sharpe": sharpe, "trades": df.height}


def run_stress_tests(df: pl.DataFrame, config: Any | None = None, out_prefix: str | Path | None = None) -> dict[str, Any]:
    rows = [_summary(df, "base")]
    col = _pnl_col(df)
    costs = pl.col("costs") if "costs" in df.columns else ((pl.col("fees") if "fees" in df.columns else 0) + (pl.col("slippage") if "slippage" in df.columns else 0))
    gross = pl.col("gross_pnl") if "gross_pnl" in df.columns else pl.col(col)
    for mult in getattr(getattr(config, "stress_tests", object()), "cost_multipliers", [2.0, 3.0]):
        stressed = df.with_columns((gross - costs * float(mult)).alias(col))
        rows.append(_summary(stressed, f"{mult:g}x_costs"))
    for delay in getattr(getattr(config, "stress_tests", object()), "delayed_entry_bars", [1]):
        if delay:
            shifted = df.with_columns(pl.col(col).shift(int(delay)).fill_null(0).alias(col))
            rows.append(_summary(shifted, f"delayed_{delay}_bar"))
    for ticks in getattr(getattr(config, "stress_tests", object()), "adverse_fill_ticks", [1]):
        if ticks:
            stressed = df.with_columns((pl.col(col) - pl.col("position_delta").abs().fill_null(0) * float(ticks)).alias(col)) if "position_delta" in df.columns else df
            rows.append(_summary(stressed, f"adverse_fill_{ticks}_tick"))
    for pct in getattr(getattr(config, "stress_tests", object()), "remove_top_trade_percentiles", [0.05]):
        if pct:
            cutoff = df[col].quantile(1.0 - float(pct))
            trimmed = df.with_columns(pl.when(pl.col(col) >= cutoff).then(0).otherwise(pl.col(col)).alias(col))
            rows.append(_summary(trimmed, f"remove_top_{pct:g}"))
    modeling_mode = getattr(getattr(config, "pipeline", object()), "modeling_mode", "unknown")
    warnings = ["minimal_compatible modeling is not strategy evidence"] if modeling_mode == "minimal_compatible" else []
    report = {"status": "PASS", "modeling_mode": modeling_mode, "warnings": warnings, "scenarios": rows}
    if out_prefix:
        out_prefix = Path(out_prefix)
        atomic_write_json(out_prefix.with_suffix(".json"), report)
        write_csv_rows(out_prefix.with_suffix(".csv"), rows)
    return report
