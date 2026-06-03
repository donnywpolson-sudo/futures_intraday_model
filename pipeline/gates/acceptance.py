from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io_safe import atomic_write_json


def _metric(report: dict[str, Any], *names: str, default: Any = None) -> Any:
    for n in names:
        if n in report:
            return report[n]
    metrics = report.get("metrics") or {}
    for n in names:
        if n in metrics:
            return metrics[n]
    return default


def run_acceptance_gate(metrics_report: dict[str, Any], stress_report: dict[str, Any] | None = None, leakage_report: dict[str, Any] | None = None, execution_report: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = (context or {}).get("config")
    gate_cfg = getattr(cfg, "acceptance_gate", None)
    gates = []

    def check(name: str, ok: bool, value: Any, limit: Any) -> None:
        gates.append({"name": name, "status": "PASS" if ok else "FAIL", "value": value, "limit": limit})

    min_sharpe = getattr(gate_cfg, "min_oos_sharpe", 0.25)
    min_trades = getattr(gate_cfg, "min_trades", 30)
    max_dd = getattr(gate_cfg, "max_drawdown_pct", -0.20)
    min_pf = getattr(gate_cfg, "min_profit_factor", 1.05)
    max_turn = getattr(gate_cfg, "max_turnover_per_bar", 10.0)
    check("min_oos_sharpe", float(_metric(metrics_report, "oos_sharpe", "sharpe", "sharpe_annualized", default=0)) >= min_sharpe, _metric(metrics_report, "oos_sharpe", "sharpe", "sharpe_annualized", default=0), min_sharpe)
    check("min_trades", int(_metric(metrics_report, "trades", "trade_count", default=0)) >= min_trades, _metric(metrics_report, "trades", "trade_count", default=0), min_trades)
    check("max_drawdown_pct", float(_metric(metrics_report, "max_drawdown_pct", default=0)) >= max_dd, _metric(metrics_report, "max_drawdown_pct", default=0), max_dd)
    check("min_profit_factor", float(_metric(metrics_report, "profit_factor", default=0)) >= min_pf, _metric(metrics_report, "profit_factor", default=0), min_pf)
    check("max_turnover_per_bar", float(_metric(metrics_report, "turnover_per_bar", default=0)) <= max_turn, _metric(metrics_report, "turnover_per_bar", default=0), max_turn)
    if leakage_report and getattr(gate_cfg, "fail_on_leakage", True):
        check("leakage", leakage_report.get("status") != "FAIL", leakage_report.get("status"), "not FAIL")
    if execution_report and getattr(gate_cfg, "fail_on_execution_trace_error", True):
        check("execution_trace", execution_report.get("status") != "FAIL", execution_report.get("status"), "not FAIL")
    if stress_report:
        scenarios = {s["scenario"]: s for s in stress_report.get("scenarios", [])}
        if getattr(gate_cfg, "require_positive_after_2x_costs", True) and "2x_costs" in scenarios:
            check("positive_after_2x_costs", scenarios["2x_costs"].get("net_pnl", 0) > 0, scenarios["2x_costs"].get("net_pnl"), ">0")
        if getattr(gate_cfg, "require_positive_after_1bar_delay", True) and "delayed_1_bar" in scenarios:
            check("positive_after_1bar_delay", scenarios["delayed_1_bar"].get("net_pnl", 0) > 0, scenarios["delayed_1_bar"].get("net_pnl"), ">0")
    status = "REJECT" if any(g["status"] == "FAIL" for g in gates) else "ACCEPT"
    result = {"status": status, "gates": gates, "context": {k: v for k, v in (context or {}).items() if k != "config"}}
    out = (context or {}).get("out")
    if out:
        atomic_write_json(out, result)
    return result
