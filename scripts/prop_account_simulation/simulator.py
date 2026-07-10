#!/usr/bin/env python3
"""Small standalone Apex PA rule simulator for synthetic event ledgers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.validation.prop_account_rules import load_prop_account_rules


DEFAULT_PROP_RULES_CONFIG = Path("configs/prop_rules/apex_50k_eod_pa_2026-07-03.yaml")


class PropAccountSimulationError(ValueError):
    """Raised when a synthetic prop-account simulation cannot proceed."""


@dataclass(frozen=True)
class PropAccountSimulationResult:
    report: dict[str, Any]
    ledger: list[dict[str, Any]]


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise PropAccountSimulationError(f"missing mapping section: {key}")
    return value


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    return int(value)


def _round_money(value: float) -> float:
    return round(float(value), 2)


def _tier_for_balance(rules: Mapping[str, Any], balance: float) -> Mapping[str, Any]:
    scaling = _mapping(rules, "pa_scaling")
    capital = _mapping(rules, "capital_model")
    starting_balance = _as_float(capital["nominal_starting_balance"])
    profit = balance - starting_balance
    selected: Mapping[str, Any] | None = None
    for tier in scaling.get("tiers", []):
        if not isinstance(tier, Mapping):
            continue
        min_profit = _as_float(tier.get("min_profit"))
        max_profit = tier.get("max_profit")
        if profit >= min_profit and (max_profit is None or profit <= _as_float(max_profit)):
            selected = tier
            break
    if selected is None:
        tiers = [tier for tier in scaling.get("tiers", []) if isinstance(tier, Mapping)]
        if not tiers:
            raise PropAccountSimulationError("pa_scaling.tiers is empty")
        selected = tiers[0]
    return selected


def _next_threshold(rules: Mapping[str, Any], highest_eod_balance: float, current_threshold: float) -> float:
    capital = _mapping(rules, "capital_model")
    max_drawdown = _as_float(_mapping(rules, "performance_account")["max_drawdown"])
    lock_balance = _as_float(capital["threshold_lock_balance"])
    locked_threshold = _as_float(capital["locked_eod_threshold"])
    candidate = locked_threshold if highest_eod_balance >= lock_balance else highest_eod_balance - max_drawdown
    return _round_money(max(current_threshold, min(candidate, locked_threshold)))


def _payout_cap(rules: Mapping[str, Any], next_payout_number: int) -> float:
    payout = _mapping(rules, "payout")
    caps = _mapping(payout, "max_request_by_payout_number")
    return _as_float(caps.get(next_payout_number) or caps.get(str(next_payout_number)))


def _consistency_ok(daily_profits: Sequence[float], max_fraction: float) -> bool:
    positive_days = [value for value in daily_profits if value > 0]
    total_profit = sum(positive_days)
    if total_profit <= 0:
        return False
    return max(positive_days) / total_profit <= max_fraction


def simulate_prop_account(
    events: Sequence[Mapping[str, Any]],
    *,
    rules: Mapping[str, Any],
    strategy_name: str = "synthetic_fixture",
) -> PropAccountSimulationResult:
    capital = _mapping(rules, "capital_model")
    performance = _mapping(rules, "performance_account")
    payout = _mapping(rules, "payout")
    consistency = _mapping(payout, "consistency_rule")

    starting_balance = _as_float(performance["starting_balance"])
    balance = starting_balance
    session_start_balance = starting_balance
    highest_eod_balance = starting_balance
    eod_threshold = _as_float(performance["initial_eod_threshold"])
    safety_net = _as_float(capital["safety_net"])
    min_request_balance = _as_float(payout["minimum_balance_to_request"])
    min_qualifying_days = _as_int(payout["minimum_qualifying_trading_days"])
    min_daily_profit = _as_float(payout["minimum_daily_profit_per_qualifying_day"])
    max_consistency_fraction = _as_float(consistency["max_single_profitable_day_fraction"])

    current_tier = _tier_for_balance(rules, balance)
    open_contracts = 0
    current_day_realized = 0.0
    daily_profits_since_payout: list[float] = []
    ledger: list[dict[str, Any]] = []
    eod_threshold_path: list[dict[str, Any]] = []
    realized_pnl = 0.0
    lowest_equity = starting_balance
    max_intraday_drawdown = 0.0
    max_eod_drawdown = 0.0
    dll_hits = 0
    dll_pause_count = 0
    contract_rejections = 0
    tier_down_events = 0
    approved_payout_count = 0
    total_cash_payouts = 0.0
    requested_payout_amount = 0.0
    approved_payout_amount = 0.0
    pending_requested_payout_amount = 0.0
    payout_status = "ineligible"
    pa_status = "active"
    closure_reason: str | None = None
    paused_until_next_session = False

    for index, event in enumerate(events):
        event_type = str(event.get("event_type", "trade"))
        timestamp = str(event.get("timestamp", f"event-{index}"))
        if event_type not in {"trade", "eod", "payout_request", "payout_approved", "payout_denied"}:
            raise PropAccountSimulationError(f"unknown event_type: {event_type}")
        if pa_status in {"closed", "completed"}:
            raise PropAccountSimulationError(f"event received after PA {pa_status}: {event_type}")

        rule_events: list[str] = []
        realized_delta = _as_float(event.get("realized_pnl"))
        unrealized_pnl = _as_float(event.get("unrealized_pnl"))
        balance = _round_money(balance + realized_delta)
        realized_pnl = _round_money(realized_pnl + realized_delta)
        current_day_realized = _round_money(current_day_realized + realized_delta)

        requested_contracts = _as_int(event.get("open_contracts"), open_contracts)
        max_contracts = _as_int(current_tier["max_contracts"])
        if abs(requested_contracts) > max_contracts:
            contract_rejections += 1
            rule_events.append("contract_limit_rejected")
        elif pa_status == "active" and not paused_until_next_session:
            open_contracts = requested_contracts

        equity = _round_money(balance + unrealized_pnl)
        lowest_equity = min(lowest_equity, equity)
        max_intraday_drawdown = min(max_intraday_drawdown, _round_money(equity - session_start_balance))

        daily_loss_limit = _as_float(current_tier["daily_loss_limit"])
        if pa_status == "active" and not paused_until_next_session:
            if session_start_balance - equity >= daily_loss_limit:
                dll_hits += 1
                dll_pause_count += 1
                paused_until_next_session = True
                open_contracts = 0
                rule_events.append("daily_loss_limit_hit_liquidated_paused")

        if pa_status == "active" and equity <= eod_threshold:
            pa_status = "closed"
            closure_reason = "eod_threshold_touch"
            open_contracts = 0
            rule_events.append("eod_threshold_touch_closed")

        if event_type == "eod":
            prior_tier_number = _as_int(current_tier["tier"])
            highest_eod_balance = max(highest_eod_balance, balance)
            eod_threshold = _next_threshold(rules, highest_eod_balance, eod_threshold)
            current_tier = _tier_for_balance(rules, balance)
            if _as_int(current_tier["tier"]) < prior_tier_number:
                tier_down_events += 1
                rule_events.append("pa_tier_down")
            if current_day_realized >= min_daily_profit:
                daily_profits_since_payout.append(current_day_realized)
            max_eod_drawdown = min(max_eod_drawdown, _round_money(balance - highest_eod_balance))
            eod_threshold_path.append(
                {
                    "timestamp": timestamp,
                    "balance": _round_money(balance),
                    "threshold": _round_money(eod_threshold),
                    "tier": _as_int(current_tier["tier"]),
                }
            )
            current_day_realized = 0.0
            session_start_balance = balance
            paused_until_next_session = False

        qualifying_days = len(daily_profits_since_payout)
        eligible_amount = max(0.0, _round_money(balance - safety_net))
        payout_eligible = (
            pa_status == "active"
            and balance >= min_request_balance
            and qualifying_days >= min_qualifying_days
            and _consistency_ok(daily_profits_since_payout, max_consistency_fraction)
        )
        if payout_eligible and payout_status == "ineligible":
            payout_status = "eligible"

        if event_type == "payout_request":
            requested = _as_float(event.get("requested_payout_amount"))
            next_payout_number = approved_payout_count + 1
            cap = _payout_cap(rules, next_payout_number)
            if not payout_eligible:
                raise PropAccountSimulationError("payout request is not eligible")
            if requested <= 0 or requested > eligible_amount or requested > cap:
                raise PropAccountSimulationError("payout request exceeds eligible amount or cap")
            requested_payout_amount = _round_money(requested)
            pending_requested_payout_amount = requested_payout_amount
            balance = _round_money(balance - requested_payout_amount)
            equity = _round_money(balance + unrealized_pnl)
            payout_status = "requested"
            rule_events.append("payout_requested_balance_reduced")

        if event_type == "payout_approved":
            approved = _as_float(event.get("approved_payout_amount"))
            if payout_status != "requested" or pending_requested_payout_amount <= 0:
                raise PropAccountSimulationError("payout approval requires pending request")
            if approved <= 0:
                raise PropAccountSimulationError("approved payout amount must be positive")
            if approved != pending_requested_payout_amount:
                raise PropAccountSimulationError("approved payout must equal requested amount")
            approved_payout_count += 1
            approved_payout_amount = _round_money(approved)
            total_cash_payouts = _round_money(total_cash_payouts + approved_payout_amount)
            payout_status = "approved"
            pending_requested_payout_amount = 0.0
            daily_profits_since_payout = []
            if approved_payout_count >= _as_int(payout["max_payouts_per_account"]):
                pa_status = "completed"
                closure_reason = "sixth_approved_payout"
                rule_events.append("sixth_payout_completed")

        if event_type == "payout_denied":
            if payout_status != "requested" or pending_requested_payout_amount <= 0:
                raise PropAccountSimulationError("payout denial requires pending request")
            balance = _round_money(balance + pending_requested_payout_amount)
            equity = _round_money(balance + unrealized_pnl)
            pending_requested_payout_amount = 0.0
            payout_status = "denied"
            rule_events.append("payout_denied_balance_restored")

        ledger.append(
            {
                "timestamp": timestamp,
                "event_type": event_type,
                "balance": _round_money(balance),
                "equity": _round_money(equity),
                "open_contracts": open_contracts,
                "pa_status": pa_status,
                "payout_status": payout_status,
                "current_tier": _as_int(current_tier["tier"]),
                "daily_loss_limit": _round_money(_as_float(current_tier["daily_loss_limit"])),
                "eod_threshold": _round_money(eod_threshold),
                "rule_events": rule_events,
            }
        )

    backtest_start = str(events[0].get("timestamp")) if events else None
    backtest_end = str(events[-1].get("timestamp")) if events else None
    simulated_account_pnl = _round_money(balance - starting_balance + total_cash_payouts)
    report = {
        "account_name": rules["account_name"],
        "provider": rules["provider"],
        "program": rules["program"],
        "rule_version_date": str(rules["version_date"]),
        "strategy_name": strategy_name,
        "backtest_start": backtest_start,
        "backtest_end": backtest_end,
        "pa_status": pa_status,
        "status_date": backtest_end,
        "ending_balance": _round_money(balance),
        "realized_pnl": _round_money(realized_pnl),
        "max_intraday_drawdown": _round_money(max_intraday_drawdown),
        "max_end_of_day_drawdown": _round_money(max_eod_drawdown),
        "eod_threshold_path": eod_threshold_path,
        "daily_loss_limit_hits": dll_hits,
        "contract_limit_rejections": contract_rejections,
        "payout_eligibility": payout_eligible if events else False,
        "payout_status": payout_status,
        "payout_number": approved_payout_count + (1 if payout_status == "requested" else 0),
        "requested_payout_amount": _round_money(requested_payout_amount),
        "approved_payout_amount": _round_money(approved_payout_amount),
        "balance_after_requested_payout": _round_money(balance),
        "safety_net_buffer": _round_money(balance - safety_net),
        "dll_pause_count": dll_pause_count,
        "pa_closure_reason": closure_reason,
        "total_cash_payouts": _round_money(total_cash_payouts),
        "simulated_account_pnl": simulated_account_pnl,
        "capital_efficiency": _round_money(
            simulated_account_pnl / _as_float(capital["initial_practical_risk_budget"])
        ),
        "lowest_equity": _round_money(lowest_equity),
        "highest_eod_balance": _round_money(highest_eod_balance),
        "current_eod_threshold": _round_money(eod_threshold),
        "current_pa_tier": _as_int(current_tier["tier"]),
        "qualifying_payout_days": len(daily_profits_since_payout),
        "eligible_payout_amount": _round_money(max(0.0, balance - safety_net)),
        "tier_down_events": tier_down_events,
        "rule_violations": [
            item
            for row in ledger
            for item in row["rule_events"]
            if item
            in {
                "contract_limit_rejected",
                "daily_loss_limit_hit_liquidated_paused",
                "eod_threshold_touch_closed",
            }
        ],
    }
    return PropAccountSimulationResult(report=report, ledger=ledger)


def simulate_prop_account_from_config(
    events: Sequence[Mapping[str, Any]],
    *,
    prop_rules_config: Path = DEFAULT_PROP_RULES_CONFIG,
    strategy_name: str = "synthetic_fixture",
) -> PropAccountSimulationResult:
    rules = load_prop_account_rules(prop_rules_config)
    return simulate_prop_account(events, rules=rules, strategy_name=strategy_name)
