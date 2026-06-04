from __future__ import annotations

from pathlib import Path
from statistics import mean, median
from typing import Any

import polars as pl

from pipeline.analytics.aggregate import compute_backtest_metrics, compute_ic
from pipeline.gates.acceptance import run_acceptance_gate
from pipeline.stress.stress_tests import run_stress_tests
from pipeline.validation.alpha_evidence import ALPHA_EVIDENCE_CSV, ALPHA_EVIDENCE_FIELDS, ALPHA_EVIDENCE_JSON
from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json
from pipeline.validation.experiment_comparison import _safe_div


FINAL_GATE_BREAKDOWN_CSV = Path("reports/validation/final_gate_breakdown.csv")
FINAL_GATE_BREAKDOWN_JSON = Path("reports/validation/final_gate_breakdown.json")
FINAL_GATE_THRESHOLDS_CSV = Path("reports/validation/final_gate_thresholds.csv")
FINAL_GATE_THRESHOLDS_JSON = Path("reports/validation/final_gate_thresholds.json")
FINAL_NEAR_MISS_CSV = Path("reports/validation/final_near_miss.csv")
FINAL_NEAR_MISS_JSON = Path("reports/validation/final_near_miss.json")
FINAL_SYMBOL_CONTRIBUTION_CSV = Path("reports/validation/final_symbol_contribution.csv")
FINAL_SYMBOL_CONTRIBUTION_JSON = Path("reports/validation/final_symbol_contribution.json")

BREAKDOWN_FIELDS = [
    "run_id", "profile", "symbol", "split", "acceptance_status", "failed_gates", "failed_gate_count",
    "pnl", "gross_pnl", "net_pnl", "cost_drag", "sharpe_annualized", "max_drawdown_pct",
    "profit_factor", "trade_count", "turnover", "active_bar_pct", "oos_rows",
]
THRESHOLD_FIELDS = ["gate", "required_value", "observed_value", "pass_fail", "margin_to_pass", "symbol", "split"]
NEAR_MISS_FIELDS = [
    "run_id", "profile", "symbol", "split", "net_pnl", "sharpe_annualized", "acceptance_status",
    "failed_gates", "failed_gate_count", "profitable_reject", "positive_sharpe_reject",
    "failed_only_min_trades", "failed_only_max_drawdown_pct", "failed_only_min_oos_sharpe",
    "failed_exactly_two_gates", "best_rejected_by_net_pnl", "best_rejected_by_sharpe",
]
SYMBOL_FIELDS = [
    "run_id", "profile", "symbol", "splits", "accepted", "rejected", "gross_pnl", "net_pnl",
    "cost_drag", "turnover", "median_sharpe", "mean_sharpe", "median_drawdown",
    "worst_drawdown", "total_trades",
]


def write_final_gate_diagnostics(
    *,
    config: Any,
    run_id: str,
    profile: str,
    stage25_path: str | Path = "reports/validation/stage_25_final_oos_predictions.parquet",
    stage27_status: str = "",
) -> dict[str, Any]:
    df = pl.read_parquet(stage25_path)
    breakdown: list[dict[str, Any]] = []
    thresholds: list[dict[str, Any]] = []
    for keys, part in df.partition_by(["symbol", "split"], as_dict=True).items():
        symbol, split = map(str, keys if isinstance(keys, tuple) else (keys, ""))
        metrics = compute_backtest_metrics(part)
        metrics["modeling_mode"] = "full_research"
        gate = run_acceptance_gate(metrics, run_stress_tests(part, config), context={"config": config, "modeling_mode": "full_research"})
        failed = [str(g["name"]) for g in gate.get("gates", []) if g.get("status") == "FAIL"]
        net = float(metrics.get("net_pnl", 0.0) or 0.0)
        gross = float(metrics.get("gross_pnl", 0.0) or 0.0)
        turnover = float(metrics.get("position_turnover", metrics.get("turnover", 0.0)) or 0.0)
        active = _active_bar_pct(part)
        row = {
            "run_id": run_id,
            "profile": profile,
            "symbol": symbol,
            "split": split,
            "acceptance_status": gate.get("strategy_acceptance_status") or gate.get("status"),
            "failed_gates": ",".join(failed),
            "failed_gate_count": len(failed),
            "pnl": net,
            "gross_pnl": gross,
            "net_pnl": net,
            "cost_drag": gross - net,
            "sharpe_annualized": float(metrics.get("sharpe_annualized", 0.0) or 0.0),
            "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0) or 0.0),
            "profit_factor": float(metrics.get("profit_factor", 0.0) or 0.0),
            "trade_count": int(metrics.get("trade_count", metrics.get("trades", 0)) or 0),
            "turnover": turnover,
            "active_bar_pct": active,
            "oos_rows": int(part.height),
        }
        breakdown.append(row)
        thresholds.extend(_threshold_rows(gate, symbol, split))

    breakdown.sort(key=lambda r: (str(r["symbol"]), int(r["split"])))
    write_csv_json(breakdown, csv_path=FINAL_GATE_BREAKDOWN_CSV, json_path=FINAL_GATE_BREAKDOWN_JSON, fields=BREAKDOWN_FIELDS)
    write_csv_json(thresholds, csv_path=FINAL_GATE_THRESHOLDS_CSV, json_path=FINAL_GATE_THRESHOLDS_JSON, fields=THRESHOLD_FIELDS)
    near = _near_miss_rows(run_id, profile, breakdown)
    write_csv_json(near, csv_path=FINAL_NEAR_MISS_CSV, json_path=FINAL_NEAR_MISS_JSON, fields=NEAR_MISS_FIELDS)
    symbols = _symbol_rows(run_id, profile, breakdown)
    write_csv_json(symbols, csv_path=FINAL_SYMBOL_CONTRIBUTION_CSV, json_path=FINAL_SYMBOL_CONTRIBUTION_JSON, fields=SYMBOL_FIELDS)
    alpha = _write_final_alpha_evidence(
        run_id=run_id,
        profile=profile,
        df=df,
        breakdown=breakdown,
        stage27_status=stage27_status,
    )
    return {
        "breakdown_rows": len(breakdown),
        "threshold_rows": len(thresholds),
        "near_miss_rows": len(near),
        "symbol_rows": len(symbols),
        "alpha_conclusion": alpha["conclusion"],
        "common_failed_gates": _common_failed_gates(breakdown),
        "best_net": _best(near, "net_pnl"),
        "best_sharpe": _best(near, "sharpe_annualized"),
    }


def _threshold_rows(gate: dict[str, Any], symbol: str, split: str) -> list[dict[str, Any]]:
    rows = []
    for g in gate.get("gates", []):
        observed = g.get("value")
        required = g.get("limit")
        rows.append({
            "gate": g.get("name"),
            "required_value": required,
            "observed_value": observed,
            "pass_fail": "PASS" if g.get("status") == "PASS" else "FAIL",
            "margin_to_pass": _margin(str(g.get("name")), observed, required),
            "symbol": symbol,
            "split": split,
        })
    return rows


def _margin(name: str, observed: Any, required: Any) -> str | float:
    try:
        obs = float(observed)
    except Exception:
        return ""
    try:
        req = float(required)
    except Exception:
        return obs if str(required).startswith(">") else ""
    if name.startswith("max_"):
        return req - obs
    return obs - req


def _near_miss_rows(run_id: str, profile: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rejected = [r for r in rows if str(r.get("acceptance_status")) == "REJECT"]
    best_net = _best_key(rejected, "net_pnl")
    best_sharpe = _best_key(rejected, "sharpe_annualized")
    out = []
    for r in rejected:
        failed = set(filter(None, str(r.get("failed_gates", "")).split(",")))
        key = (r["symbol"], r["split"])
        out.append({
            "run_id": run_id,
            "profile": profile,
            "symbol": r["symbol"],
            "split": r["split"],
            "net_pnl": r["net_pnl"],
            "sharpe_annualized": r["sharpe_annualized"],
            "acceptance_status": r["acceptance_status"],
            "failed_gates": r["failed_gates"],
            "failed_gate_count": r["failed_gate_count"],
            "profitable_reject": bool(float(r["net_pnl"]) > 0),
            "positive_sharpe_reject": bool(float(r["sharpe_annualized"]) > 0),
            "failed_only_min_trades": failed == {"min_trades"},
            "failed_only_max_drawdown_pct": failed == {"max_drawdown_pct"},
            "failed_only_min_oos_sharpe": failed == {"min_oos_sharpe"},
            "failed_exactly_two_gates": len(failed) == 2,
            "best_rejected_by_net_pnl": key == best_net,
            "best_rejected_by_sharpe": key == best_sharpe,
        })
    return out


def _symbol_rows(run_id: str, profile: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for symbol in sorted({str(r["symbol"]) for r in rows}):
        sr = [r for r in rows if str(r["symbol"]) == symbol]
        sharpes = [float(r["sharpe_annualized"]) for r in sr]
        dds = [float(r["max_drawdown_pct"]) for r in sr]
        gross = sum(float(r["gross_pnl"]) for r in sr)
        net = sum(float(r["net_pnl"]) for r in sr)
        out.append({
            "run_id": run_id,
            "profile": profile,
            "symbol": symbol,
            "splits": len(sr),
            "accepted": sum(1 for r in sr if r["acceptance_status"] == "ACCEPT"),
            "rejected": sum(1 for r in sr if r["acceptance_status"] == "REJECT"),
            "gross_pnl": gross,
            "net_pnl": net,
            "cost_drag": gross - net,
            "turnover": sum(float(r["turnover"]) for r in sr),
            "median_sharpe": float(median(sharpes)) if sharpes else 0.0,
            "mean_sharpe": float(mean(sharpes)) if sharpes else 0.0,
            "median_drawdown": float(median(dds)) if dds else 0.0,
            "worst_drawdown": min(dds) if dds else 0.0,
            "total_trades": sum(int(r["trade_count"]) for r in sr),
        })
    return out


def _write_final_alpha_evidence(*, run_id: str, profile: str, df: pl.DataFrame, breakdown: list[dict[str, Any]], stage27_status: str) -> dict[str, Any]:
    metrics = compute_backtest_metrics(df)
    gross = float(metrics.get("gross_pnl", 0.0) or 0.0)
    net = float(metrics.get("net_pnl", 0.0) or 0.0)
    symbols = sorted({str(r["symbol"]) for r in breakdown})
    per_symbol_net = {s: sum(float(r["net_pnl"]) for r in breakdown if r["symbol"] == s) for s in symbols}
    per_symbol_accept = {
        s: {
            "ACCEPT": sum(1 for r in breakdown if r["symbol"] == s and r["acceptance_status"] == "ACCEPT"),
            "REJECT": sum(1 for r in breakdown if r["symbol"] == s and r["acceptance_status"] == "REJECT"),
            "WARN": 0,
            "MISSING": 0,
        }
        for s in symbols
    }
    ic_vals = _ic_values(df)
    accepted = 1 if stage27_status == "ACCEPT" else 0
    rejected = 1 if stage27_status == "REJECT" else 0
    conclusion = "PASS_GATE_RESEARCH_READY" if accepted and net > 0 else ("WEAK_ALPHA_RESEARCH_ONLY" if net > 0 else "NO_ALPHA_FOUND")
    row = {
        "profile": profile,
        "run_id": run_id,
        "stage_scope": "final",
        "symbols": ",".join(symbols),
        "splits": str(len({str(r["split"]) for r in breakdown})),
        "gross_pnl": gross,
        "net_pnl": net,
        "cost_drag": gross - net,
        "cost_drag_pct_of_gross": _safe_div(gross - net, gross),
        "gross_sharpe": metrics.get("gross_sharpe_annualized", ""),
        "net_sharpe": metrics.get("sharpe_annualized", 0.0),
        "ic_median": float(median(ic_vals)) if ic_vals else 0.0,
        "ic_mean": float(mean(ic_vals)) if ic_vals else 0.0,
        "turnover": metrics.get("position_turnover", 0.0),
        "active_bar_pct": _active_bar_pct(df),
        "ACCEPT": accepted,
        "REJECT": rejected,
        "WARN": 0,
        "MISSING": 0,
        "outlier_count": 0,
        "outlier_pnl": 0,
        "non_outlier_pnl": net,
        "per_symbol_net_pnl": "|".join(f"{s}:{per_symbol_net[s]:.6f}" for s in symbols),
        "per_symbol_acceptance_count": "|".join(
            f"{s}:A{per_symbol_accept[s]['ACCEPT']}/R{per_symbol_accept[s]['REJECT']}/W0/M0" for s in symbols
        ),
        "conclusion": conclusion,
    }
    existing = [
        r for r in read_json_rows(ALPHA_EVIDENCE_JSON)
        if not (str(r.get("run_id")) == str(run_id) and str(r.get("profile")) == str(profile) and str(r.get("stage_scope")) == "final")
    ]
    write_csv_json(existing + [row], csv_path=ALPHA_EVIDENCE_CSV, json_path=ALPHA_EVIDENCE_JSON, fields=ALPHA_EVIDENCE_FIELDS)
    return row


def _ic_values(df: pl.DataFrame) -> list[float]:
    vals = []
    for _keys, part in df.partition_by(["symbol", "split"], as_dict=True).items():
        if "prediction" not in part.columns or "target_15m_ret" not in part.columns:
            continue
        ic = compute_ic(part["prediction"], part["target_15m_ret"]).get("spearman_ic")
        if ic is not None:
            vals.append(float(ic))
    return vals


def _active_bar_pct(df: pl.DataFrame) -> float:
    pos = "position" if "position" in df.columns else "position_after"
    if pos not in df.columns or df.height == 0:
        return 0.0
    return float((df[pos] != 0).sum() or 0) / float(df.height)


def _common_failed_gates(rows: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        for gate in filter(None, str(row.get("failed_gates", "")).split(",")):
            counts[gate] = counts.get(gate, 0) + 1
    return "|".join(f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _best(rows: list[dict[str, Any]], field: str) -> str:
    if not rows:
        return ""
    row = max(rows, key=lambda r: float(r.get(field) or 0.0))
    return f"{row['symbol']}_split_{row['split']}"


def _best_key(rows: list[dict[str, Any]], field: str) -> tuple[str, str] | None:
    if not rows:
        return None
    row = max(rows, key=lambda r: float(r.get(field) or 0.0))
    return str(row["symbol"]), str(row["split"])
