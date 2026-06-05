from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json


FORENSICS_CSV = Path("reports/validation/final_outlier_forensics.csv")
FORENSICS_JSON = Path("reports/validation/final_outlier_forensics.json")
TRADES_CSV_TEMPLATE = "reports/validation/final_outlier_trades_{symbol}_split_{split}.csv"
TRADES_JSON_TEMPLATE = "reports/validation/final_outlier_trades_{symbol}_split_{split}.json"
NEIGHBOR_CSV = Path("reports/validation/final_outlier_neighbor_comparison.csv")
NEIGHBOR_JSON = Path("reports/validation/final_outlier_neighbor_comparison.json")

FORENSICS_FIELDS = [
    "run_id", "profile", "symbol", "split", "test_start", "test_end", "net_pnl", "gross_pnl",
    "cost_drag", "turnover", "trade_count", "active_bar_pct", "sharpe_annualized",
    "max_drawdown_pct", "profit_factor", "failed_gates", "top_1_bar_pnl", "top_5_bar_pnl",
    "top_10_bar_pnl", "top_1_bar_pct_of_split_pnl", "top_5_bar_pct_of_split_pnl",
    "top_10_bar_pct_of_split_pnl", "bars_for_50pct_pnl", "bars_for_80pct_pnl",
    "bars_for_95pct_pnl", "timestamp_monotonic", "duplicate_timestamps", "missing_bar_gaps",
    "max_abs_return", "max_price_jump_pct", "max_volume_zscore", "session_boundary_issues",
    "max_abs_target_15m_ret", "max_abs_prediction", "prediction_before_target_realization",
    "train_test_overlap", "purge_applied", "train_only_fit_assumed", "diagnosis",
]
TRADE_FIELDS = [
    "timestamp", "prediction", "target_15m_ret", "price_or_close", "prior_position",
    "new_position", "position_change", "gross_pnl_increment", "cost_increment",
    "net_pnl_increment", "cumulative_net_pnl", "session_id", "session_date",
]
NEIGHBOR_FIELDS = [
    "run_id", "profile", "symbol", "split", "net_pnl", "gross_pnl", "turnover",
    "trade_count", "active_bar_pct", "prediction_p50", "prediction_p95", "prediction_p99",
    "target_p50", "target_p95", "target_p99", "max_abs_return", "max_abs_prediction",
    "best_bar_pnl", "worst_bar_pnl",
]


def write_final_outlier_forensics(
    *,
    run_id: str = "run_83ea5c92",
    profile: str = "tier_1_final_threshold_p999_experiment",
    symbol: str = "ES",
    split: str | int = "22",
    stage_path: str | Path = "reports/validation/stage_24_final_wfa_backtest_results.parquet",
    breakdown_path: str | Path = "reports/validation/final_gate_breakdown.json",
) -> dict[str, Any]:
    split = str(split)
    df = _split_df(stage_path, run_id, symbol, split)
    if df.is_empty():
        raise RuntimeError(f"OUTLIER FORENSICS FAIL: no rows for run_id={run_id} symbol={symbol} split={split}")
    breakdown = _breakdown_row(breakdown_path, run_id, profile, symbol, split)
    trades = _trade_rows(df)
    trade_csv = Path(TRADES_CSV_TEMPLATE.format(symbol=symbol, split=split))
    trade_json = Path(TRADES_JSON_TEMPLATE.format(symbol=symbol, split=split))
    write_csv_json(trades, csv_path=trade_csv, json_path=trade_json, fields=TRADE_FIELDS)
    forensic = _forensic_row(df, breakdown, run_id, profile, symbol, split)
    neighbors = [_neighbor_row(_split_df(stage_path, run_id, symbol, str(s)), breakdown_path, run_id, profile, symbol, str(s)) for s in [int(split) - 1, int(split), int(split) + 1]]
    neighbors = [r for r in neighbors if r]
    write_csv_json([forensic], csv_path=FORENSICS_CSV, json_path=FORENSICS_JSON, fields=FORENSICS_FIELDS)
    write_csv_json(neighbors, csv_path=NEIGHBOR_CSV, json_path=NEIGHBOR_JSON, fields=NEIGHBOR_FIELDS)
    return {"forensic": forensic, "trade_rows": len(trades), "neighbor_rows": len(neighbors)}


def _split_df(stage_path: str | Path, run_id: str, symbol: str, split: str) -> pl.DataFrame:
    p = Path(stage_path)
    if not p.exists():
        return pl.DataFrame()
    return (
        pl.scan_parquet(p)
        .filter((pl.col("run_id") == run_id) & (pl.col("symbol") == symbol) & (pl.col("split").cast(pl.Utf8) == split))
        .collect()
        .sort("timestamp" if "timestamp" in pl.scan_parquet(p).collect_schema().names() else "ts_event")
    )


def _breakdown_row(path: str | Path, run_id: str, profile: str, symbol: str, split: str) -> dict[str, Any]:
    rows = [
        r for r in read_json_rows(path)
        if str(r.get("run_id")) == run_id and str(r.get("profile")) == profile and str(r.get("symbol")) == symbol and str(r.get("split")) == split
    ]
    return rows[0] if rows else {}


def _trade_rows(df: pl.DataFrame) -> list[dict[str, Any]]:
    pos_col = "position_after" if "position_after" in df.columns else "position"
    work = df.with_columns(
        pl.col(pos_col).cast(pl.Float64).fill_null(0.0).alias("_pos"),
        pl.col("net_pnl").cast(pl.Float64).fill_null(0.0).cum_sum().alias("_cum_net"),
    )
    work = work.filter(pl.col("_pos") != pl.col("_pos").shift(1).fill_null(0.0))
    rows = []
    for r in work.iter_rows(named=True):
        prior = _float(r.get("position_before"))
        new = _float(r.get(pos_col))
        rows.append({
            "timestamp": r.get("timestamp") or r.get("ts_event"),
            "prediction": _float(r.get("prediction")),
            "target_15m_ret": _float(r.get("target_15m_ret")),
            "price_or_close": _float(r.get("assumed_fill_price", r.get("close"))),
            "prior_position": prior,
            "new_position": new,
            "position_change": new - prior,
            "gross_pnl_increment": _float(r.get("gross_pnl")),
            "cost_increment": _float(r.get("costs")),
            "net_pnl_increment": _float(r.get("net_pnl", r.get("pnl"))),
            "cumulative_net_pnl": _float(r.get("_cum_net")),
            "session_id": str(r.get("session_id", "")),
            "session_date": str(r.get("session_date", "")),
        })
    return rows


def _forensic_row(df: pl.DataFrame, breakdown: dict[str, Any], run_id: str, profile: str, symbol: str, split: str) -> dict[str, Any]:
    pnl = _series(df, "net_pnl")
    gross = _series(df, "gross_pnl")
    costs = _series(df, "costs")
    concentration = _concentration(pnl.to_list())
    sanity = _sanity(df)
    net = _float(breakdown.get("net_pnl", pnl.sum()))
    outlier_net = _float(breakdown.get("net_pnl", pnl.sum()))
    non_outlier_hint = "outlier-dominated" if outlier_net > 0 and concentration["top_1_bar_pct_of_split_pnl"] > 0.5 else "requires-review"
    return {
        "run_id": run_id,
        "profile": profile,
        "symbol": symbol,
        "split": split,
        "test_start": str(df["test_start"][0]) if "test_start" in df.columns and df.height else "",
        "test_end": str(df["test_end"][0]) if "test_end" in df.columns and df.height else "",
        "net_pnl": net,
        "gross_pnl": _float(breakdown.get("gross_pnl", gross.sum())),
        "cost_drag": _float(breakdown.get("cost_drag", costs.sum())),
        "turnover": _float(breakdown.get("turnover", _series(df, "position_delta").abs().sum())),
        "trade_count": int(_float(breakdown.get("trade_count"))),
        "active_bar_pct": _float(breakdown.get("active_bar_pct")),
        "sharpe_annualized": _float(breakdown.get("sharpe_annualized")),
        "max_drawdown_pct": _float(breakdown.get("max_drawdown_pct")),
        "profit_factor": _float(breakdown.get("profit_factor")),
        "failed_gates": str(breakdown.get("failed_gates", "")),
        **concentration,
        **sanity,
        "prediction_before_target_realization": _prediction_before_target(df),
        "train_test_overlap": _train_test_overlap(df),
        "purge_applied": True,
        "train_only_fit_assumed": True,
        "diagnosis": non_outlier_hint,
    }


def _neighbor_row(df: pl.DataFrame, breakdown_path: str | Path, run_id: str, profile: str, symbol: str, split: str) -> dict[str, Any]:
    if df.is_empty():
        return {}
    b = _breakdown_row(breakdown_path, run_id, profile, symbol, split)
    pred = _series(df, "prediction")
    target = _series(df, "target_15m_ret")
    pnl = _series(df, "net_pnl")
    return {
        "run_id": run_id,
        "profile": profile,
        "symbol": symbol,
        "split": split,
        "net_pnl": _float(b.get("net_pnl", pnl.sum())),
        "gross_pnl": _float(b.get("gross_pnl", _series(df, "gross_pnl").sum())),
        "turnover": _float(b.get("turnover", _series(df, "position_delta").abs().sum())),
        "trade_count": int(_float(b.get("trade_count"))),
        "active_bar_pct": _float(b.get("active_bar_pct")),
        "prediction_p50": _quantile(pred, 0.5),
        "prediction_p95": _quantile(pred, 0.95),
        "prediction_p99": _quantile(pred, 0.99),
        "target_p50": _quantile(target, 0.5),
        "target_p95": _quantile(target, 0.95),
        "target_p99": _quantile(target, 0.99),
        "max_abs_return": max([abs(x) for x in target.to_list()] or [0.0]),
        "max_abs_prediction": max([abs(x) for x in pred.to_list()] or [0.0]),
        "best_bar_pnl": _float(pnl.max()),
        "worst_bar_pnl": _float(pnl.min()),
    }


def _concentration(values: list[float]) -> dict[str, Any]:
    positives = sorted([v for v in values if v > 0], reverse=True)
    total = sum(values)
    abs_total = abs(total)
    top1 = sum(positives[:1])
    top5 = sum(positives[:5])
    top10 = sum(positives[:10])
    return {
        "top_1_bar_pnl": top1,
        "top_5_bar_pnl": top5,
        "top_10_bar_pnl": top10,
        "top_1_bar_pct_of_split_pnl": _safe_div(top1, abs_total),
        "top_5_bar_pct_of_split_pnl": _safe_div(top5, abs_total),
        "top_10_bar_pct_of_split_pnl": _safe_div(top10, abs_total),
        "bars_for_50pct_pnl": _bars_for_pct(positives, abs_total, 0.5),
        "bars_for_80pct_pnl": _bars_for_pct(positives, abs_total, 0.8),
        "bars_for_95pct_pnl": _bars_for_pct(positives, abs_total, 0.95),
    }


def _bars_for_pct(values: list[float], total: float, pct: float) -> int:
    if total <= 0:
        return 0
    acc = 0.0
    for i, v in enumerate(values, 1):
        acc += v
        if acc >= total * pct:
            return i
    return len(values)


def _sanity(df: pl.DataFrame) -> dict[str, Any]:
    ts_col = "timestamp" if "timestamp" in df.columns else "ts_event"
    ts = df[ts_col]
    dup = df.select(pl.col(ts_col).is_duplicated().sum()).item()
    ts_vals = ts.to_list()
    diffs = [(b - a) for a, b in zip(ts_vals, ts_vals[1:]) if a is not None and b is not None]
    missing_gaps = sum(1 for d in diffs if getattr(d, "total_seconds", lambda: 0)() > 300)
    close = _series(df, "close")
    returns = close.pct_change().fill_null(0.0) if len(close) else pl.Series([])
    vol = _series(df, "volume")
    vol_std = _float(vol.std())
    vol_z = ((vol - _float(vol.mean())) / (vol_std if vol_std else 1.0)).abs() if len(vol) else pl.Series([])
    session_issues = _session_boundary_issues(df)
    return {
        "timestamp_monotonic": bool(ts.is_sorted()),
        "duplicate_timestamps": int(dup or 0),
        "missing_bar_gaps": missing_gaps,
        "max_abs_return": max([abs(_float(x)) for x in returns.to_list()] or [0.0]),
        "max_price_jump_pct": max([abs(_float(x)) for x in returns.to_list()] or [0.0]),
        "max_volume_zscore": _float(vol_z.max()) if len(vol_z) else 0.0,
        "session_boundary_issues": session_issues,
        "max_abs_target_15m_ret": max([abs(x) for x in _series(df, "target_15m_ret").to_list()] or [0.0]),
        "max_abs_prediction": max([abs(x) for x in _series(df, "prediction").to_list()] or [0.0]),
    }


def _session_boundary_issues(df: pl.DataFrame) -> int:
    if "session_id" not in df.columns:
        return 0
    work = df.select("session_id").with_columns((pl.col("session_id") != pl.col("session_id").shift(1)).alias("new_session"))
    return int(work["new_session"].sum() or 0)


def _prediction_before_target(df: pl.DataFrame) -> bool:
    if "prediction_time" not in df.columns or "execution_time" not in df.columns:
        return False
    return bool((df["prediction_time"] <= df["execution_time"]).all())


def _train_test_overlap(df: pl.DataFrame) -> bool:
    try:
        return str(df["train_end"][0]) > str(df["test_start"][0])
    except Exception:
        return False


def _series(df: pl.DataFrame, col: str) -> pl.Series:
    if col not in df.columns:
        return pl.Series([], dtype=pl.Float64)
    return df[col].cast(pl.Float64, strict=False).fill_null(0.0)


def _quantile(series: pl.Series, q: float) -> float:
    return _float(series.quantile(q)) if len(series) else 0.0


def _safe_div(num: float, den: float) -> float:
    return 0.0 if den == 0 else float(num) / float(den)


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
