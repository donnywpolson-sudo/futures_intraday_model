from __future__ import annotations

from pathlib import Path
from statistics import mean, median
from typing import Any

import numpy as np
import polars as pl

from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json
from pipeline.validation.experiment_comparison import _safe_div


FINAL_THRESHOLD_USED_CSV = Path("reports/validation/final_threshold_used.csv")
FINAL_THRESHOLD_USED_JSON = Path("reports/validation/final_threshold_used.json")
FINAL_EXPERIMENT_CSV = Path("reports/validation/final_experiment_comparison.csv")
FINAL_EXPERIMENT_JSON = Path("reports/validation/final_experiment_comparison.json")
FINAL_OUTLIERS_CSV = Path("reports/validation/final_threshold_outliers.csv")
FINAL_OUTLIERS_JSON = Path("reports/validation/final_threshold_outliers.json")
FINAL_PROFILE_COMPARISON_CSV = Path("reports/validation/final_threshold_profile_comparison.csv")
FINAL_PROFILE_COMPARISON_JSON = Path("reports/validation/final_threshold_profile_comparison.json")
FINAL_MIN_TRADES_NEAR_MISS_JSON = Path("reports/validation/final_min_trades_near_miss.json")

THRESHOLD_USED_FIELDS = [
    "run_id", "profile", "symbol", "split", "threshold_mode", "threshold_quantile",
    "train_prediction_nonnull", "train_abs_prediction_quantile", "long_threshold_used",
    "short_threshold_used", "test_prediction_nonnull", "test_active_bar_pct",
    "test_long_bars", "test_short_bars", "test_turnover",
]
COMPARISON_FIELDS = [
    "profile", "run_id", "expected_rows", "successful", "failed", "ACCEPT", "REJECT", "WARN", "MISSING",
    "active_splits", "median_active_bar_pct", "mean_active_bar_pct", "total_turnover",
    "gross_pnl", "net_pnl", "cost_drag", "cost_drag_pct_of_gross", "outlier_count",
    "outlier_pnl", "non_outlier_pnl", "best_symbol_by_net_pnl", "worst_symbol_by_net_pnl", "conclusion",
]
OUTLIER_FIELDS = [
    "run_id", "profile", "symbol", "split", "test_active_bar_pct", "test_turnover", "net_pnl", "reason",
]
PROFILE_COMPARISON_FIELDS = [
    "profile", "run_id", "threshold_quantile", "net_pnl", "gross_pnl", "cost_drag",
    "cost_drag_pct_of_gross", "total_turnover", "active_splits", "median_active_bar_pct",
    "ACCEPT", "REJECT", "outlier_count", "profitable_min_trades_rejects",
    "median_min_trades_shortfall", "accepted_splits", "best_symbol_by_net_pnl",
    "worst_symbol_by_net_pnl", "conclusion",
]


def build_final_threshold_used_row(
    *,
    run_id: str,
    profile: str,
    symbol: str,
    split: str | int,
    config: Any,
    train_predictions: Any,
    train_abs_prediction_quantile: float | None,
    threshold: float,
    test_result: pl.DataFrame,
    calibration_source: str,
) -> dict[str, Any]:
    if calibration_source != "train":
        raise RuntimeError("FINAL THRESHOLD LEAKAGE FAIL: threshold calibration must use train predictions only")
    train_arr = np.asarray(train_predictions, dtype=float)
    train_arr = train_arr[np.isfinite(train_arr)]
    pred = test_result["prediction"].cast(pl.Float64).drop_nulls() if "prediction" in test_result.columns else pl.Series([], dtype=pl.Float64)
    pos = test_result["position_after"].cast(pl.Float64) if "position_after" in test_result.columns else (
        test_result["position"].cast(pl.Float64) if "position" in test_result.columns else pl.Series([0.0] * test_result.height)
    )
    delta = test_result["position_delta"].abs().cast(pl.Float64) if "position_delta" in test_result.columns else pl.Series([0.0] * test_result.height)
    return {
        "run_id": run_id,
        "profile": profile,
        "symbol": symbol,
        "split": split,
        "threshold_mode": str(getattr(config.execution, "threshold_mode", "fixed")),
        "threshold_quantile": "" if getattr(config.execution, "threshold_quantile", None) is None else float(config.execution.threshold_quantile),
        "train_prediction_nonnull": int(train_arr.size),
        "train_abs_prediction_quantile": "" if train_abs_prediction_quantile is None else float(train_abs_prediction_quantile),
        "long_threshold_used": float(threshold),
        "short_threshold_used": -float(threshold),
        "test_prediction_nonnull": int(pred.len()),
        "test_active_bar_pct": 0.0 if test_result.height == 0 else float((pos != 0).sum() or 0) / float(test_result.height),
        "test_long_bars": int((pos > 0).sum() or 0) if len(pos) else 0,
        "test_short_bars": int((pos < 0).sum() or 0) if len(pos) else 0,
        "test_turnover": float(delta.sum() or 0.0) if len(delta) else 0.0,
    }


def write_final_threshold_used(rows: list[dict[str, Any]]) -> tuple[Path, Path]:
    return write_csv_json(rows, csv_path=FINAL_THRESHOLD_USED_CSV, json_path=FINAL_THRESHOLD_USED_JSON, fields=THRESHOLD_USED_FIELDS)


def write_final_experiment_reports(
    *,
    run_id: str,
    profile: str,
    stage25_path: str | Path,
    expected_rows: int,
    stage27_status: str,
) -> dict[str, Any]:
    threshold_rows = [r for r in read_json_rows(FINAL_THRESHOLD_USED_JSON) if str(r.get("run_id")) == str(run_id)]
    breakdown = [r for r in read_json_rows("reports/validation/final_gate_breakdown.json") if str(r.get("run_id")) == str(run_id)]
    previous_comparisons = read_json_rows(FINAL_EXPERIMENT_JSON)
    df = pl.read_parquet(stage25_path)
    net_by_key = {(str(r["symbol"]), str(r["split"])): _float(r.get("net_pnl")) for r in breakdown}
    outliers = _outlier_rows(run_id, profile, threshold_rows, net_by_key)
    write_csv_json(outliers, csv_path=FINAL_OUTLIERS_CSV, json_path=FINAL_OUTLIERS_JSON, fields=OUTLIER_FIELDS)
    gross = float(df["gross_pnl"].sum() or 0.0) if "gross_pnl" in df.columns else 0.0
    net = float(df["net_pnl"].sum() or df["pnl"].sum() or 0.0)
    symbol_net = (
        df.group_by("symbol")
        .agg(pl.col("net_pnl" if "net_pnl" in df.columns else "pnl").sum().alias("net_pnl"))
        .sort("net_pnl")
    )
    status_counts = {"ACCEPT": 0, "REJECT": 0, "WARN": 0, "MISSING": 0}
    for row in breakdown:
        status = str(row.get("acceptance_status") or "MISSING")
        status_counts[status if status in status_counts else "MISSING"] += 1
    missing = max(int(expected_rows) - len(breakdown), 0)
    status_counts["MISSING"] += missing
    active_pcts = [_float(r.get("test_active_bar_pct")) for r in threshold_rows]
    outlier_pnl = sum(_float(r.get("net_pnl")) for r in outliers)
    comparison = {
        "profile": profile,
        "run_id": run_id,
        "expected_rows": int(expected_rows),
        "successful": len(breakdown),
        "failed": max(int(expected_rows) - len(breakdown), 0),
        **status_counts,
        "active_splits": sum(1 for x in active_pcts if x > 0.0),
        "median_active_bar_pct": float(median(active_pcts)) if active_pcts else 0.0,
        "mean_active_bar_pct": float(mean(active_pcts)) if active_pcts else 0.0,
        "total_turnover": sum(_float(r.get("test_turnover")) for r in threshold_rows),
        "gross_pnl": gross,
        "net_pnl": net,
        "cost_drag": gross - net,
        "cost_drag_pct_of_gross": _safe_div(gross - net, gross),
        "outlier_count": len(outliers),
        "outlier_pnl": outlier_pnl,
        "non_outlier_pnl": net - outlier_pnl,
        "best_symbol_by_net_pnl": str(symbol_net.tail(1)["symbol"][0]) if symbol_net.height else "",
        "worst_symbol_by_net_pnl": str(symbol_net.head(1)["symbol"][0]) if symbol_net.height else "",
        "conclusion": _conclusion(stage27_status, net),
    }
    write_csv_json([comparison], csv_path=FINAL_EXPERIMENT_CSV, json_path=FINAL_EXPERIMENT_JSON, fields=COMPARISON_FIELDS)
    _seed_profile_comparison(previous_comparisons, current=comparison)
    return comparison


def update_final_threshold_profile_comparison(
    *,
    comparison: dict[str, Any],
    config: Any,
    trade_audit: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = [_profile_row(r, config=None, trade_audit=None) for r in read_json_rows(FINAL_PROFILE_COMPARISON_JSON)]
    row = _profile_row(comparison, config=config, trade_audit=trade_audit)
    rows = [r for r in rows if not (str(r.get("profile")) == str(row["profile"]) and str(r.get("run_id")) == str(row["run_id"]))]
    rows.append(row)
    rows.sort(key=lambda r: (str(r.get("profile")), str(r.get("run_id"))))
    write_csv_json(rows, csv_path=FINAL_PROFILE_COMPARISON_CSV, json_path=FINAL_PROFILE_COMPARISON_JSON, fields=PROFILE_COMPARISON_FIELDS)
    return rows


def _seed_profile_comparison(previous_comparisons: list[dict[str, Any]], *, current: dict[str, Any]) -> None:
    prior = [
        r for r in previous_comparisons
        if not (str(r.get("profile")) == str(current.get("profile")) and str(r.get("run_id")) == str(current.get("run_id")))
    ]
    if not prior:
        return
    existing = [_profile_row(r, config=None, trade_audit=_trade_summary_for(r)) for r in read_json_rows(FINAL_PROFILE_COMPARISON_JSON)]
    keys = {(str(r.get("profile")), str(r.get("run_id"))) for r in existing}
    for r in prior:
        key = (str(r.get("profile")), str(r.get("run_id")))
        if key not in keys:
            existing.append(_profile_row(r, config=None, trade_audit=_trade_summary_for(r)))
            keys.add(key)
    existing.sort(key=lambda r: (str(r.get("profile")), str(r.get("run_id"))))
    write_csv_json(existing, csv_path=FINAL_PROFILE_COMPARISON_CSV, json_path=FINAL_PROFILE_COMPARISON_JSON, fields=PROFILE_COMPARISON_FIELDS)


def _outlier_rows(run_id: str, profile: str, threshold_rows: list[dict[str, Any]], net_by_key: dict[tuple[str, str], float]) -> list[dict[str, Any]]:
    rows = []
    for r in threshold_rows:
        active = _float(r.get("test_active_bar_pct"))
        turnover = _float(r.get("test_turnover"))
        reasons = []
        if active > 0.03:
            reasons.append("active_bar_pct_gt_0.03")
        if turnover > 300:
            reasons.append("turnover_gt_300")
        if reasons:
            symbol = str(r.get("symbol"))
            split = str(r.get("split"))
            rows.append({
                "run_id": run_id,
                "profile": profile,
                "symbol": symbol,
                "split": split,
                "test_active_bar_pct": active,
                "test_turnover": turnover,
                "net_pnl": net_by_key.get((symbol, split), 0.0),
                "reason": ",".join(reasons),
            })
    return rows


def _conclusion(stage27_status: str, net_pnl: float) -> str:
    if str(stage27_status) == "ACCEPT" and net_pnl > 0:
        return "PASS_GATE_RESEARCH_READY"
    return "WEAK_ALPHA_RESEARCH_ONLY" if net_pnl > 0 else "NO_ALPHA_FOUND"


def _profile_row(comparison: dict[str, Any], *, config: Any | None, trade_audit: dict[str, Any] | None) -> dict[str, Any]:
    profile = str(comparison.get("profile", ""))
    threshold_quantile = getattr(getattr(config, "execution", object()), "threshold_quantile", None) if config is not None else None
    if threshold_quantile is None:
        threshold_quantile = _infer_quantile(profile)
    trade_audit = trade_audit or {
        "profitable_min_trades_rejects": comparison.get("profitable_min_trades_rejects", 0),
        "median_shortfall": comparison.get("median_min_trades_shortfall", 0),
    }
    return {
        "profile": profile,
        "run_id": str(comparison.get("run_id", "")),
        "threshold_quantile": "" if threshold_quantile is None else float(threshold_quantile),
        "net_pnl": _float(comparison.get("net_pnl")),
        "gross_pnl": _float(comparison.get("gross_pnl")),
        "cost_drag": _float(comparison.get("cost_drag")),
        "cost_drag_pct_of_gross": _float(comparison.get("cost_drag_pct_of_gross")),
        "total_turnover": _float(comparison.get("total_turnover")),
        "active_splits": int(_float(comparison.get("active_splits"))),
        "median_active_bar_pct": _float(comparison.get("median_active_bar_pct")),
        "ACCEPT": int(_float(comparison.get("ACCEPT"))),
        "REJECT": int(_float(comparison.get("REJECT"))),
        "outlier_count": int(_float(comparison.get("outlier_count"))),
        "profitable_min_trades_rejects": int(_float(trade_audit.get("profitable_min_trades_rejects"))),
        "median_min_trades_shortfall": _float(trade_audit.get("median_shortfall")),
        "accepted_splits": int(_float(comparison.get("ACCEPT"))),
        "best_symbol_by_net_pnl": str(comparison.get("best_symbol_by_net_pnl", "")),
        "worst_symbol_by_net_pnl": str(comparison.get("worst_symbol_by_net_pnl", "")),
        "conclusion": str(comparison.get("conclusion", "")),
    }


def _trade_summary_for(comparison: dict[str, Any]) -> dict[str, Any]:
    run_id = str(comparison.get("run_id", ""))
    profile = str(comparison.get("profile", ""))
    rows = [
        r for r in read_json_rows(FINAL_MIN_TRADES_NEAR_MISS_JSON)
        if str(r.get("run_id")) == run_id and str(r.get("profile")) == profile
    ]
    shortfalls = [_float(r.get("trades_shortfall")) for r in rows]
    return {
        "profitable_min_trades_rejects": len(rows),
        "median_shortfall": float(median(shortfalls)) if shortfalls else 0.0,
    }


def _infer_quantile(profile: str) -> float | None:
    if "p999" in profile:
        return 0.999
    if "p995" in profile:
        return 0.995
    return None


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
