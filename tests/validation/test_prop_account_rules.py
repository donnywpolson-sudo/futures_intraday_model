from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.validation import prop_account_rules as prop_rules


def _write_yaml(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _valid_rules() -> dict[str, object]:
    return {
        "schema_version": 1,
        "provider": "apex_trader_funding",
        "program": "eod_no_fee",
        "account_name": "apex_50k_eod_pa",
        "account_phase": "performance_account",
        "account_size": 50000,
        "currency": "USD",
        "version_date": "2026-07-03",
        "account_nature": {
            "simulated_funded_account": True,
            "live_brokerage_capital": False,
            "user_capital_at_risk": False,
            "payout_rights_based_on_simulated_pnl": True,
        },
        "capital_model": {
            "nominal_starting_balance": 50000,
            "initial_fail_level": 48000,
            "initial_practical_risk_budget": 2000,
            "initial_daily_loss_cap": 1000,
            "threshold_lock_profit": 2100,
            "threshold_lock_balance": 52100,
            "locked_eod_threshold": 50100,
            "safety_net": 52100,
            "minimum_balance_to_request_first_payout": 52600,
        },
        "performance_account": {"starting_balance": 50000, "max_drawdown": 2000},
        "session_rules": {},
        "drawdown": {"close_pa_on_touch": True},
        "daily_loss_limit": {"closes_pa_on_touch": False},
        "rule_outcomes": {
            "daily_loss_limit_hit": {"close_pa_permanently": False},
            "eod_threshold_touch": {"close_pa_permanently": True},
        },
        "pa_scaling": {
            "tier_can_move_down": True,
            "max_tier": 4,
            "tiers": [
                {"tier": 1, "min_profit": 0},
                {"tier": 2, "min_profit": 1500},
                {"tier": 3, "min_profit": 3000},
                {"tier": 4, "min_profit": 6000},
            ],
        },
        "payout": {
            "safety_net": 52100,
            "minimum_balance_to_request": 52600,
            "minimum_payout_request": 500,
            "max_payouts_per_account": 6,
        },
        "payout_lifecycle": {"max_approved_payouts": 6},
        "balance_after_payout": {"permanent_safety_net": 52100},
        "simulator_behavior_contract": {},
        "checks": {},
        "execution_assumptions": {},
    }


def _valid_report_schema() -> dict[str, object]:
    return {
        "schema_version": 1,
        "report_name": "prop_account_backtest_report",
        "required_fields": [
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
        ],
    }


def test_default_repo_prop_rules_load_without_strategy_logic_change() -> None:
    summary = prop_rules.build_prop_account_rules_summary(repo_root=prop_rules.REPO_ROOT)

    assert summary["status"] == "PASS_PROP_ACCOUNT_RULES_LOADED"
    assert summary["account_phase"] == "performance_account"
    assert summary["account_size"] == 50000
    assert summary["initial_practical_risk_budget"] == 2000
    assert summary["safety_net"] == 52100
    assert summary["max_approved_payouts"] == 6
    assert summary["strategy_logic_changed"] is False


def test_loader_rejects_eval_phase(tmp_path: Path) -> None:
    payload = _valid_rules()
    payload["account_phase"] = "evaluation"
    path = _write_yaml(tmp_path / "rules.yaml", payload)

    with pytest.raises(prop_rules.PropRuleConfigError, match="performance_account"):
        prop_rules.load_prop_account_rules(path)


def test_loader_rejects_inconsistent_safety_net(tmp_path: Path) -> None:
    payload = _valid_rules()
    capital = payload["capital_model"]
    assert isinstance(capital, dict)
    capital["safety_net"] = 52000
    path = _write_yaml(tmp_path / "rules.yaml", payload)

    with pytest.raises(prop_rules.PropRuleConfigError, match="safety_net"):
        prop_rules.load_prop_account_rules(path)


def test_report_schema_requires_prop_payout_fields(tmp_path: Path) -> None:
    schema = _valid_report_schema()
    path = _write_yaml(tmp_path / "report_schema.yaml", schema)

    loaded = prop_rules.load_prop_backtest_report_schema(path)

    assert loaded["report_name"] == "prop_account_backtest_report"


def test_report_schema_rejects_missing_payout_field(tmp_path: Path) -> None:
    schema = _valid_report_schema()
    required = schema["required_fields"]
    assert isinstance(required, list)
    required.remove("payout_status")
    path = _write_yaml(tmp_path / "report_schema.yaml", schema)

    with pytest.raises(prop_rules.PropRuleConfigError, match="payout_status"):
        prop_rules.load_prop_backtest_report_schema(path)


def test_cli_prints_summary(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = prop_rules.main(["--repo-root", str(prop_rules.REPO_ROOT)])

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS_PROP_ACCOUNT_RULES_LOADED" in stdout
    assert "strategy_logic_changed=False" in stdout
