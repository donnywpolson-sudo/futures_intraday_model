from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any

import polars as pl

from pipeline.validation.diagnostic_io import write_csv_json
from pipeline.validation.prediction_thresholds import build_prediction_threshold_diagnostics
from pipeline.validation.signal_activation import build_signal_activation_row


FINAL_SIGNAL_CSV = Path("reports/validation/final_signal_activation_debug.csv")
FINAL_SIGNAL_JSON = Path("reports/validation/final_signal_activation_debug.json")
FINAL_THRESHOLD_CSV = Path("reports/validation/final_prediction_threshold_diagnostics.csv")
FINAL_THRESHOLD_JSON = Path("reports/validation/final_prediction_threshold_diagnostics.json")
FINAL_GRID_CSV = Path("reports/validation/final_threshold_candidate_grid.csv")
FINAL_GRID_JSON = Path("reports/validation/final_threshold_candidate_grid.json")

SIGNAL_FIELDS = [
    "run_id", "profile", "symbol", "split", "prediction_count", "prediction_nonnull",
    "prediction_min", "prediction_max", "prediction_mean", "prediction_std", "prediction_abs_max",
    "long_threshold_used", "short_threshold_used", "long_bars", "short_bars", "flat_bars",
    "active_bar_pct", "position_turnover", "trade_count", "reason_if_flat",
]
THRESHOLD_FIELDS = [
    "run_id", "profile", "symbol", "split",
    "prediction_p90", "prediction_p95", "prediction_p99", "prediction_p995", "prediction_p999",
    "abs_prediction_p90", "abs_prediction_p95", "abs_prediction_p99", "abs_prediction_p995", "abs_prediction_p999",
    "current_threshold", "bars_above_current_long", "bars_below_current_short", "active_pct_at_current_threshold",
]
GRID_FIELDS = [
    "run_id", "profile", "symbol", "split", "threshold_type", "threshold_value",
    "long_bars", "short_bars", "active_bar_pct", "turnover_proxy",
]
GRID_TYPES = {"p99", "p995", "p999", "fixed_0.001", "fixed_0.0025", "fixed_0.005", "fixed_0.01", "fixed_0.025", "fixed_0.05", "fixed_0.1", "fixed_0.25"}


def write_final_threshold_diagnostics(
    *,
    df: pl.DataFrame,
    config: Any,
    run_id: str,
    profile: str,
) -> dict[str, Any]:
    signal_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    grid_rows: list[dict[str, Any]] = []
    for keys, part in df.partition_by(["symbol", "split"], as_dict=True).items():
        symbol, split = map(str, keys if isinstance(keys, tuple) else (keys, ""))
        signal_rows.append(_signal_row(part, run_id, profile, symbol, split, config))
        threshold_row, grid = build_prediction_threshold_diagnostics(part, symbol=symbol, split=split, config=config)
        threshold_rows.append(_threshold_row(threshold_row, run_id, profile, symbol, split))
        grid_rows.extend(_grid_row(r, run_id, profile, symbol, split) for r in grid if r.get("threshold_type") in GRID_TYPES)

    signal_rows.sort(key=lambda r: (r["symbol"], int(r["split"])))
    threshold_rows.sort(key=lambda r: (r["symbol"], int(r["split"])))
    grid_rows.sort(key=lambda r: (r["symbol"], int(r["split"]), str(r["threshold_type"])))
    write_csv_json(signal_rows, csv_path=FINAL_SIGNAL_CSV, json_path=FINAL_SIGNAL_JSON, fields=SIGNAL_FIELDS)
    write_csv_json(threshold_rows, csv_path=FINAL_THRESHOLD_CSV, json_path=FINAL_THRESHOLD_JSON, fields=THRESHOLD_FIELDS)
    write_csv_json(grid_rows, csv_path=FINAL_GRID_CSV, json_path=FINAL_GRID_JSON, fields=GRID_FIELDS)
    return {
        "signal_rows": len(signal_rows),
        "threshold_rows": len(threshold_rows),
        "grid_rows": len(grid_rows),
        "current_active_splits": sum(1 for r in threshold_rows if float(r["active_pct_at_current_threshold"] or 0.0) > 0.0),
        "expected_splits": len(threshold_rows),
        "current_active_median": _median([float(r["active_pct_at_current_threshold"] or 0.0) for r in threshold_rows]),
        "p995_active_median": _median([float(r["active_bar_pct"] or 0.0) for r in grid_rows if r["threshold_type"] == "p995"]),
        "p999_active_median": _median([float(r["active_bar_pct"] or 0.0) for r in grid_rows if r["threshold_type"] == "p999"]),
    }


def print_final_threshold_summary(summary: dict[str, Any]) -> None:
    print(
        f"[FINAL THRESHOLD DIAG] current threshold active splits={summary['current_active_splits']}/{summary['expected_splits']} "
        f"active_bar_pct_median={float(summary['current_active_median']):.6g}",
        flush=True,
    )
    print(
        f"[FINAL THRESHOLD DIAG] candidate p995 active_bar_pct_median={float(summary['p995_active_median']):.6g}",
        flush=True,
    )
    print(
        f"[FINAL THRESHOLD DIAG] candidate p999 active_bar_pct_median={float(summary['p999_active_median']):.6g}",
        flush=True,
    )


def _signal_row(part: pl.DataFrame, run_id: str, profile: str, symbol: str, split: str, config: Any) -> dict[str, Any]:
    base = build_signal_activation_row(part, symbol=symbol, split=split, config=config)
    return {
        "run_id": run_id,
        "profile": profile,
        "symbol": symbol,
        "split": split,
        "prediction_count": base["prediction_count"],
        "prediction_nonnull": base["prediction_nonnull"],
        "prediction_min": base["prediction_min"],
        "prediction_max": base["prediction_max"],
        "prediction_mean": base["prediction_mean"],
        "prediction_std": base["prediction_std"],
        "prediction_abs_max": base["prediction_abs_max"],
        "long_threshold_used": base["signal_threshold_long"],
        "short_threshold_used": base["signal_threshold_short"],
        "long_bars": base["long_bars"],
        "short_bars": base["short_bars"],
        "flat_bars": base["flat_bars"],
        "active_bar_pct": base["active_bar_pct"],
        "position_turnover": base["position_turnover"],
        "trade_count": int((part["position_delta"].abs() > 0).sum() or 0) if "position_delta" in part.columns else 0,
        "reason_if_flat": base["reason_if_flat"],
    }


def _threshold_row(row: dict[str, Any], run_id: str, profile: str, symbol: str, split: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "profile": profile,
        "symbol": symbol,
        "split": split,
        "prediction_p90": row.get("prediction_p90", ""),
        "prediction_p95": row.get("prediction_p95", ""),
        "prediction_p99": row.get("prediction_p99", ""),
        "prediction_p995": row.get("prediction_p995", ""),
        "prediction_p999": row.get("prediction_p999", ""),
        "abs_prediction_p90": row.get("abs_prediction_p90", ""),
        "abs_prediction_p95": row.get("abs_prediction_p95", ""),
        "abs_prediction_p99": row.get("abs_prediction_p99", ""),
        "abs_prediction_p995": row.get("abs_prediction_p995", ""),
        "abs_prediction_p999": row.get("abs_prediction_p999", ""),
        "current_threshold": row.get("current_long_threshold", ""),
        "bars_above_current_long": row.get("bars_above_current_long", 0),
        "bars_below_current_short": row.get("bars_below_current_short", 0),
        "active_pct_at_current_threshold": row.get("active_pct_at_current_threshold", 0.0),
    }


def _grid_row(row: dict[str, Any], run_id: str, profile: str, symbol: str, split: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "profile": profile,
        "symbol": symbol,
        "split": split,
        "threshold_type": row.get("threshold_type", ""),
        "threshold_value": row.get("threshold_value", 0.0),
        "long_bars": row.get("long_bars", 0),
        "short_bars": row.get("short_bars", 0),
        "active_bar_pct": row.get("active_bar_pct", 0.0),
        "turnover_proxy": row.get("turnover_proxy", 0.0),
    }


def _median(vals: list[float]) -> float:
    return float(median(vals)) if vals else 0.0
