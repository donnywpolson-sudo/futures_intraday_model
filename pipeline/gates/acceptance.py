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
    modeling_mode = (context or {}).get(
        "modeling_mode",
        getattr(getattr(cfg, "pipeline", object()), "modeling_mode", metrics_report.get("modeling_mode", "unknown")),
    )
    gates = []

    def check(name: str, ok: bool, value: Any, limit: Any, warn: bool = False) -> None:
        gates.append({"name": name, "status": "PASS" if ok else ("WARN" if warn else "FAIL"), "value": value, "limit": limit})

    min_sharpe = getattr(gate_cfg, "min_oos_sharpe", 0.25)
    min_trades = getattr(gate_cfg, "min_trades", 30)
    max_dd = getattr(gate_cfg, "max_drawdown_pct", -0.20)
    min_pf = getattr(gate_cfg, "min_profit_factor", 1.05)
    max_turn = getattr(gate_cfg, "max_turnover_per_bar", 10.0)
    pnl_value = _metric(metrics_report, "net_pnl", "total_pnl", "pnl", default=0)
    check("positive_net_pnl", float(pnl_value) > 0, pnl_value, ">0")
    check("min_oos_sharpe", float(_metric(metrics_report, "oos_sharpe", "sharpe", "sharpe_annualized", default=0)) >= min_sharpe, _metric(metrics_report, "oos_sharpe", "sharpe", "sharpe_annualized", default=0), min_sharpe)
    check("min_trades", int(_metric(metrics_report, "trades", "trade_count", default=0)) >= min_trades, _metric(metrics_report, "trades", "trade_count", default=0), min_trades)
    check("max_drawdown_pct", float(_metric(metrics_report, "max_drawdown_pct", default=-1.0)) >= max_dd, _metric(metrics_report, "max_drawdown_pct", default=-1.0), max_dd)
    check("min_profit_factor", float(_metric(metrics_report, "profit_factor", default=0)) >= min_pf, _metric(metrics_report, "profit_factor", default=0), min_pf)
    check("max_turnover_per_bar", float(_metric(metrics_report, "turnover_per_bar", default=float("inf"))) <= max_turn, _metric(metrics_report, "turnover_per_bar", default=float("inf")), max_turn)
    if leakage_report and getattr(gate_cfg, "fail_on_leakage", True):
        check("leakage", leakage_report.get("status") != "FAIL", leakage_report.get("status"), "not FAIL")
    if execution_report and getattr(gate_cfg, "fail_on_execution_trace_error", True):
        check("execution_trace", execution_report.get("status") != "FAIL", execution_report.get("status"), "not FAIL")
    if stress_report:
        scenarios = {s["scenario"]: s for s in stress_report.get("scenarios", [])}
        if getattr(gate_cfg, "require_positive_after_2x_costs", True) and "2x_costs" in scenarios:
            check("positive_after_2x_costs", scenarios["2x_costs"].get("net_pnl", 0) > 0, scenarios["2x_costs"].get("net_pnl"), ">0")
        elif getattr(gate_cfg, "require_positive_after_2x_costs", True):
            check("positive_after_2x_costs", False, "missing", "scenario present")
        if getattr(gate_cfg, "require_positive_after_1bar_delay", True) and "delayed_1_bar" in scenarios:
            check("positive_after_1bar_delay", scenarios["delayed_1_bar"].get("net_pnl", 0) > 0, scenarios["delayed_1_bar"].get("net_pnl"), ">0")
        elif getattr(gate_cfg, "require_positive_after_1bar_delay", True):
            check("positive_after_1bar_delay", False, "missing", "scenario present")
    else:
        if getattr(gate_cfg, "require_positive_after_2x_costs", True):
            check("positive_after_2x_costs", False, "missing_stress_report", "stress report required")
        if getattr(gate_cfg, "require_positive_after_1bar_delay", True):
            check("positive_after_1bar_delay", False, "missing_stress_report", "stress report required")

    if modeling_mode == "minimal_compatible":
        check("minimal_compatible_modeling_mode", False, modeling_mode, "full_research for strategy acceptance", warn=True)

    status = "REJECT" if any(g["status"] == "FAIL" for g in gates) else ("WARN" if any(g["status"] == "WARN" for g in gates) else "ACCEPT")
    result = {
        "status": status,
        "modeling_mode": modeling_mode,
        "acceptance_type": "RESEARCH_PIPELINE_ONLY" if modeling_mode == "minimal_compatible" else "STRATEGY_ACCEPTANCE",
        "warnings": ["minimal_compatible modeling is not strategy acceptance"] if modeling_mode == "minimal_compatible" else [],
        "gates": gates,
        "context": {k: v for k, v in (context or {}).items() if k != "config"},
    }
    out = (context or {}).get("out")
    if out:
        atomic_write_json(out, result)
    return result
