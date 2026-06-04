from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.io_safe import atomic_write_json, write_csv_rows
from pipeline.common.cache import build_cache_metadata, cache_is_fresh, write_cache_metadata
from pipeline.data_gate.manifest import build_data_manifest
from pipeline.validation.target_integrity import (
    add_forward_return_target,
    inspect_target_integrity,
    target_col_from_config,
    validate_target_integrity_row,
    write_target_integrity_report,
)


def add_labels(df: pl.DataFrame, *, horizon: int = 15, entry_lag_bars: int = 1, target_col: str = "target_15m_ret", target_scale_factor: float = 1.0, price_col: str = "open") -> pl.DataFrame:
    out, _, _ = add_forward_return_target(
        df,
        horizon=horizon,
        entry_lag_bars=entry_lag_bars,
        target_col=target_col,
        target_scale_factor=target_scale_factor,
        price_col=price_col,
    )
    return out


def label_root(in_root: str | Path = "data/causally_gated_normalized", out_root: str | Path = "data/labeled", config: Any | None = None) -> dict:
    in_root = Path(in_root)
    out_root = Path(out_root)
    horizon = getattr(getattr(config, "target", object()), "target_15m_horizon", 15)
    scale = getattr(getattr(config, "target", object()), "target_scale_factor", 1.0)
    lag = getattr(getattr(config, "execution", object()), "entry_lag_bars", 1)
    target_col = target_col_from_config(config)
    if target_col != "target_15m_ret":
        raise RuntimeError(f"TARGET CONFIG DRIFT FAIL: active target_col={target_col!r}; expected 'target_15m_ret'")
    rows = []
    integrity_rows = []
    src_manifest = in_root / "manifest.json"
    for p in sorted(in_root.glob("*/*.parquet")):
        out = out_root / p.parent.name / p.name
        out.parent.mkdir(parents=True, exist_ok=True)
        meta = build_cache_metadata(
            out,
            source_stage="causally_gated_normalized",
            output_stage="labeled",
            source_paths=[src_manifest if src_manifest.exists() else p],
            config=config,
            config_sections=["target", "execution", "pipeline"],
            code_paths=[__file__],
            symbol=p.parent.name,
            year=p.stem,
        ) if config is not None else None
        fresh, reason = cache_is_fresh(out, meta, config) if meta else (False, "no config")
        if fresh:
            cached = pl.read_parquet(out)
            row = inspect_target_integrity(cached, symbol=p.parent.name, file=str(out), target_col=target_col)
            validate_target_integrity_row(row)
            integrity_rows.append(row)
            rows.append({"input": str(p), "output": str(out), "status": "COMPLETED_CACHED"})
            continue
        labeled, price_col, group_cols = add_forward_return_target(
            pl.read_parquet(p),
            horizon=horizon,
            entry_lag_bars=lag,
            target_col=target_col,
            target_scale_factor=scale,
        )
        row = inspect_target_integrity(
            labeled,
            symbol=p.parent.name,
            file=str(out),
            target_col=target_col,
            close_col_used=price_col,
            group_col_used=group_cols,
        )
        validate_target_integrity_row(row)
        integrity_rows.append(row)
        labeled.write_parquet(out)
        if meta:
            write_cache_metadata(out, meta)
        rows.append({"input": str(p), "output": str(out), "status": "PASS"})
    report = {"status": "PASS", "files": rows}
    atomic_write_json("reports/validation/label_generation_report.json", report)
    write_csv_rows("reports/validation/label_generation_summary.csv", rows or [{"input": "", "output": "", "status": "WARN"}])
    write_target_integrity_report(integrity_rows)
    build_data_manifest(out_root, stage="labeled")
    return report
