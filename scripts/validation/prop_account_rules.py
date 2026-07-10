#!/usr/bin/env python3
"""Read-only loader for prop-account rule configs used by backtest reporting."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROP_RULES_CONFIG = Path("configs/prop_rules/apex_50k_eod_pa_2026-07-03.yaml")
DEFAULT_REPORT_SCHEMA = Path("configs/report_schema/prop_backtest_report.yaml")

REQUIRED_PROP_RULE_SECTIONS = (
    "account_nature",
    "capital_model",
    "performance_account",
    "session_rules",
    "drawdown",
    "daily_loss_limit",
    "rule_outcomes",
    "pa_scaling",
    "payout",
    "payout_lifecycle",
    "balance_after_payout",
    "simulator_behavior_contract",
    "checks",
    "execution_assumptions",
)

REQUIRED_REPORT_FIELDS = (
    "pa_status",
    "status_date",
    "payout_status",
    "payout_number",
    "requested_payout_amount",
    "approved_payout_amount",
    "balance_after_requested_payout",
    "safety_net_buffer",
    "dll_pause_count",
    "pa_closure_reason",
    "total_cash_payouts",
    "simulated_account_pnl",
    "capital_efficiency",
)


class PropRuleConfigError(ValueError):
    """Raised when a prop-account config cannot be safely consumed."""


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_yaml_object(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise PropRuleConfigError(f"missing YAML config: {path.as_posix()}") from exc
    except yaml.YAMLError as exc:
        raise PropRuleConfigError(f"invalid YAML config: {path.as_posix()}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PropRuleConfigError(f"YAML config must be an object: {path.as_posix()}")
    return payload


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise PropRuleConfigError(f"{key} must be a mapping")
    return value


def _number(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise PropRuleConfigError(f"{key} must be numeric")
    return float(value)


def load_prop_account_rules(path: Path) -> dict[str, Any]:
    payload = _read_yaml_object(path)
    failures: list[str] = []
    for key in ("schema_version", "provider", "account_name", "account_phase", "account_size", "version_date"):
        if key not in payload:
            failures.append(f"missing top-level key: {key}")
    for section in REQUIRED_PROP_RULE_SECTIONS:
        if not isinstance(payload.get(section), Mapping):
            failures.append(f"missing or invalid section: {section}")
    if payload.get("account_phase") != "performance_account":
        failures.append("account_phase must be performance_account")
    if payload.get("account_size") != 50000:
        failures.append("account_size must be 50000 for this config")

    if failures:
        raise PropRuleConfigError("; ".join(failures))
    _validate_apex_50k_pa_invariants(payload)
    return payload


def load_prop_backtest_report_schema(path: Path) -> dict[str, Any]:
    payload = _read_yaml_object(path)
    required_fields = payload.get("required_fields")
    if not isinstance(required_fields, list) or not all(isinstance(item, str) for item in required_fields):
        raise PropRuleConfigError("report schema required_fields must be a string list")
    missing = sorted(set(REQUIRED_REPORT_FIELDS) - set(required_fields))
    if missing:
        raise PropRuleConfigError(f"report schema missing required prop fields: {missing}")
    return payload


def _validate_apex_50k_pa_invariants(payload: Mapping[str, Any]) -> None:
    capital = _mapping(payload, "capital_model")
    performance = _mapping(payload, "performance_account")
    drawdown = _mapping(payload, "drawdown")
    dll = _mapping(payload, "daily_loss_limit")
    scaling = _mapping(payload, "pa_scaling")
    payout = _mapping(payload, "payout")
    lifecycle = _mapping(payload, "payout_lifecycle")
    balance_after_payout = _mapping(payload, "balance_after_payout")
    rule_outcomes = _mapping(payload, "rule_outcomes")

    start = _number(capital, "nominal_starting_balance")
    max_drawdown = _number(performance, "max_drawdown")
    initial_fail = _number(capital, "initial_fail_level")
    threshold_lock_balance = _number(capital, "threshold_lock_balance")
    locked_threshold = _number(capital, "locked_eod_threshold")
    safety_net = _number(capital, "safety_net")
    minimum_balance = _number(payout, "minimum_balance_to_request")
    minimum_payout = _number(payout, "minimum_payout_request")

    failures: list[str] = []
    if start != 50000:
        failures.append("nominal_starting_balance must be 50000")
    if initial_fail != start - max_drawdown:
        failures.append("initial_fail_level must equal nominal_starting_balance - max_drawdown")
    if locked_threshold != threshold_lock_balance - max_drawdown:
        failures.append("locked_eod_threshold must equal threshold_lock_balance - max_drawdown")
    if safety_net != threshold_lock_balance:
        failures.append("safety_net must equal threshold_lock_balance")
    if minimum_balance != safety_net + minimum_payout:
        failures.append("minimum_balance_to_request must equal safety_net + minimum_payout_request")
    if drawdown.get("close_pa_on_touch") is not True:
        failures.append("drawdown.close_pa_on_touch must be true")
    if dll.get("closes_pa_on_touch") is not False:
        failures.append("daily_loss_limit.closes_pa_on_touch must be false")
    if _mapping(rule_outcomes, "daily_loss_limit_hit").get("close_pa_permanently") is not False:
        failures.append("daily loss limit hit must not close PA permanently")
    if _mapping(rule_outcomes, "eod_threshold_touch").get("close_pa_permanently") is not True:
        failures.append("EOD threshold touch must close PA permanently")
    if balance_after_payout.get("permanent_safety_net") != safety_net:
        failures.append("balance_after_payout.permanent_safety_net must match payout safety net")
    if lifecycle.get("max_approved_payouts") != payout.get("max_payouts_per_account"):
        failures.append("payout lifecycle max must match payout.max_payouts_per_account")
    if scaling.get("tier_can_move_down") is not True:
        failures.append("pa_scaling.tier_can_move_down must be true")
    if scaling.get("max_tier") != 4:
        failures.append("pa_scaling.max_tier must be 4")
    tiers = scaling.get("tiers")
    if not isinstance(tiers, list) or len(tiers) != 4:
        failures.append("pa_scaling.tiers must contain four tiers")
    elif tiers[-1].get("min_profit") != 6000:
        failures.append("50K PA tier 4 must start at 6000 profit")

    if failures:
        raise PropRuleConfigError("; ".join(failures))


def build_prop_account_rules_summary(
    *,
    repo_root: Path,
    prop_rules_config: Path = DEFAULT_PROP_RULES_CONFIG,
    report_schema: Path = DEFAULT_REPORT_SCHEMA,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    prop_path = resolve_path(repo_root, prop_rules_config)
    report_path = resolve_path(repo_root, report_schema)
    rules = load_prop_account_rules(prop_path)
    schema = load_prop_backtest_report_schema(report_path)
    capital = _mapping(rules, "capital_model")
    payout = _mapping(rules, "payout")
    scaling = _mapping(rules, "pa_scaling")
    return {
        "status": "PASS_PROP_ACCOUNT_RULES_LOADED",
        "prop_rules_config": rel(prop_path, repo_root),
        "report_schema": rel(report_path, repo_root),
        "provider": rules["provider"],
        "account_name": rules["account_name"],
        "account_phase": rules["account_phase"],
        "account_size": rules["account_size"],
        "version_date": str(rules["version_date"]),
        "nominal_starting_balance": capital["nominal_starting_balance"],
        "initial_practical_risk_budget": capital["initial_practical_risk_budget"],
        "initial_fail_level": capital["initial_fail_level"],
        "safety_net": capital["safety_net"],
        "minimum_balance_to_request": payout["minimum_balance_to_request"],
        "max_approved_payouts": payout["max_payouts_per_account"],
        "pa_tier_count": len(scaling["tiers"]),
        "report_required_field_count": len(schema["required_fields"]),
        "strategy_logic_changed": False,
        "wfa_modeling_approved": False,
        "paper_or_live_trading_approved": False,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--prop-rules-config", default=DEFAULT_PROP_RULES_CONFIG.as_posix())
    parser.add_argument("--report-schema", default=DEFAULT_REPORT_SCHEMA.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    try:
        summary = build_prop_account_rules_summary(
            repo_root=Path(args.repo_root),
            prop_rules_config=Path(args.prop_rules_config),
            report_schema=Path(args.report_schema),
        )
    except PropRuleConfigError as exc:
        print(f"prop_account_rules status=FAIL_PROP_ACCOUNT_RULES error={exc}")
        return 1
    print(
        "prop_account_rules "
        f"status={summary['status']} "
        f"account={summary['account_name']} "
        f"phase={summary['account_phase']} "
        f"risk_budget={summary['initial_practical_risk_budget']} "
        f"safety_net={summary['safety_net']} "
        f"max_payouts={summary['max_approved_payouts']} "
        f"strategy_logic_changed={summary['strategy_logic_changed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
