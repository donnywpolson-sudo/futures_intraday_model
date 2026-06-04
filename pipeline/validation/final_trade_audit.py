from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any

import polars as pl

from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json


FINAL_TRADE_AUDIT_CSV = Path("reports/validation/final_trade_count_audit.csv")
FINAL_TRADE_AUDIT_JSON = Path("reports/validation/final_trade_count_audit.json")
FINAL_MIN_TRADES_NEAR_MISS_CSV = Path("reports/validation/final_min_trades_near_miss.csv")
FINAL_MIN_TRADES_NEAR_MISS_JSON = Path("reports/validation/final_min_trades_near_miss.json")
FINAL_GATE_BREAKDOWN_JSON = Path("reports/validation/final_gate_breakdown.json")

TRADE_AUDIT_FIELDS = [
    "run_id", "profile", "symbol", "split", "trade_count_used_by_gate",
    "position_turnover", "position_change_events", "round_trip_count_estimate",
    "long_entries", "short_entries", "exits_to_flat", "flips_long_to_short",
    "flips_short_to_long", "active_bar_pct", "active_bars", "oos_rows",
    "net_pnl", "gross_pnl", "cost_drag", "sharpe_annualized",
    "acceptance_status", "failed_gates", "trade_count_contract", "flip_cost_contract",
]
MIN_TRADES_FIELDS = [
    "run_id", "profile", "symbol", "split", "trade_count", "required_min_trades",
    "trades_shortfall", "net_pnl", "pnl_per_trade", "sharpe_annualized",
    "max_drawdown_pct", "profit_factor", "failed_gates", "failed_gate_count",
]


def write_final_trade_count_audit(
    *,
    run_id: str,
    profile: str,
    config: Any,
    stage25_path: str | Path = "reports/validation/stage_25_final_oos_predictions.parquet",
    breakdown_path: str | Path = FINAL_GATE_BREAKDOWN_JSON,
) -> dict[str, Any]:
    df = pl.read_parquet(stage25_path)
    breakdown = {
        (str(r.get("symbol")), str(r.get("split"))): r
        for r in read_json_rows(breakdown_path)
        if str(r.get("run_id")) == str(run_id)
    }
    rows = []
    for keys, part in df.partition_by(["symbol", "split"], as_dict=True).items():
        symbol, split = map(str, keys if isinstance(keys, tuple) else (keys, ""))
        b = breakdown.get((symbol, split), {})
        rows.append(_audit_row(part, b, run_id=run_id, profile=profile, symbol=symbol, split=split))
    rows.sort(key=lambda r: (r["symbol"], int(r["split"])))
    write_csv_json(rows, csv_path=FINAL_TRADE_AUDIT_CSV, json_path=FINAL_TRADE_AUDIT_JSON, fields=TRADE_AUDIT_FIELDS)
    near = _min_trades_near_miss_rows(rows, config)
    write_csv_json(near, csv_path=FINAL_MIN_TRADES_NEAR_MISS_CSV, json_path=FINAL_MIN_TRADES_NEAR_MISS_JSON, fields=MIN_TRADES_FIELDS)
    shortfalls = [float(r["trades_shortfall"]) for r in near]
    return {
        "audit_rows": len(rows),
        "near_miss_rows": len(near),
        "profitable_min_trades_rejects": len(near),
        "median_shortfall": float(median(shortfalls)) if shortfalls else 0.0,
        "best_net_pnl": max((float(r["net_pnl"]) for r in near), default=0.0),
    }


def _audit_row(part: pl.DataFrame, breakdown: dict[str, Any], *, run_id: str, profile: str, symbol: str, split: str) -> dict[str, Any]:
    pos_col = "position_after" if "position_after" in part.columns else "position"
    pos = part[pos_col].cast(pl.Float64).fill_null(0.0) if pos_col in part.columns else pl.Series([0.0] * part.height)
    prev = pos.shift(1).fill_null(0.0)
    delta = pos - prev
    position_change_events = int((delta.abs() > 0).sum() or 0)
    position_turnover = float(delta.abs().sum() or 0.0)
    long_entries = int(((prev <= 0) & (pos > 0)).sum() or 0)
    short_entries = int(((prev >= 0) & (pos < 0)).sum() or 0)
    exits_to_flat = int(((prev != 0) & (pos == 0)).sum() or 0)
    flips_l2s = int(((prev > 0) & (pos < 0)).sum() or 0)
    flips_s2l = int(((prev < 0) & (pos > 0)).sum() or 0)
    active_bars = int((pos != 0).sum() or 0)
    gross = _float(breakdown.get("gross_pnl"))
    net = _float(breakdown.get("net_pnl", breakdown.get("pnl")))
    return {
        "run_id": run_id,
        "profile": profile,
        "symbol": symbol,
        "split": split,
        "trade_count_used_by_gate": int(_float(breakdown.get("trade_count"))),
        "position_turnover": position_turnover,
        "position_change_events": position_change_events,
        "round_trip_count_estimate": exits_to_flat + flips_l2s + flips_s2l,
        "long_entries": long_entries,
        "short_entries": short_entries,
        "exits_to_flat": exits_to_flat,
        "flips_long_to_short": flips_l2s,
        "flips_short_to_long": flips_s2l,
        "active_bar_pct": 0.0 if part.height == 0 else active_bars / part.height,
        "active_bars": active_bars,
        "oos_rows": int(part.height),
        "net_pnl": net,
        "gross_pnl": gross,
        "cost_drag": gross - net,
        "sharpe_annualized": _float(breakdown.get("sharpe_annualized")),
        "max_drawdown_pct": _float(breakdown.get("max_drawdown_pct")),
        "profit_factor": _float(breakdown.get("profit_factor")),
        "acceptance_status": str(breakdown.get("acceptance_status", "")),
        "failed_gates": str(breakdown.get("failed_gates", "")),
        "trade_count_contract": "gate trade_count is position-change events, not round trips",
        "flip_cost_contract": "long-short flips count as one gate event and turnover/cost abs(delta)=2",
    }


def _min_trades_near_miss_rows(rows: list[dict[str, Any]], config: Any) -> list[dict[str, Any]]:
    required = int(getattr(getattr(config, "acceptance_gate", object()), "min_trades", 30) or 30)
    out = []
    for r in rows:
        failed = str(r.get("failed_gates", ""))
        net = _float(r.get("net_pnl"))
        tc = int(_float(r.get("trade_count_used_by_gate")))
        if str(r.get("acceptance_status")) != "REJECT" or net <= 0 or "min_trades" not in failed:
            continue
        out.append({
            "run_id": r["run_id"],
            "profile": r["profile"],
            "symbol": r["symbol"],
            "split": r["split"],
            "trade_count": tc,
            "required_min_trades": required,
            "trades_shortfall": max(required - tc, 0),
            "net_pnl": net,
            "pnl_per_trade": 0.0 if tc == 0 else net / tc,
            "sharpe_annualized": r["sharpe_annualized"],
            "max_drawdown_pct": _breakdown_field(r, "max_drawdown_pct"),
            "profit_factor": _breakdown_field(r, "profit_factor"),
            "failed_gates": failed,
            "failed_gate_count": len([g for g in failed.split(",") if g]),
        })
    out.sort(key=lambda r: (-float(r["net_pnl"]), r["symbol"], int(r["split"])))
    return out


def _breakdown_field(row: dict[str, Any], field: str) -> float:
    # Kept for schema stability; full values are available in final_gate_breakdown.
    return _float(row.get(field))


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
