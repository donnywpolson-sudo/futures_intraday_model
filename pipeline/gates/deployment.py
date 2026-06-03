from __future__ import annotations

from typing import Any

from pipeline.common.io_safe import atomic_write_json


def run_deployment_readiness(config: Any, out: str = "reports/acceptance/deployment_readiness.json") -> dict:
    d = config.deployment
    failures = []
    warnings = []
    if d.mode == "research_only":
        warnings.append("research_only mode: live deployment intentionally NOT_READY")
    for name in ["paper_trading_required", "live_shadow_required", "require_kill_switch", "require_post_trade_reconciliation"]:
        if not getattr(d, name):
            failures.append(f"{name}=false")
    if d.max_daily_loss <= 0:
        failures.append("max_daily_loss must be positive")
    status = "FAIL" if failures else ("NOT_READY" if warnings or not d.enabled else "READY")
    report = {"status": status, "failures": failures, "warnings": warnings, "deployment": d.model_dump()}
    atomic_write_json(out, report)
    return report


def run_deployment_readiness_gate(config: Any, out: str = "reports/acceptance/deployment_readiness.json") -> dict:
    return run_deployment_readiness(config, out)
