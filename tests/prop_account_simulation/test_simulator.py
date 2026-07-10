from __future__ import annotations

from pathlib import Path

import pytest

from scripts.prop_account_simulation.simulator import (
    PropAccountSimulationError,
    simulate_prop_account_from_config,
)
from scripts.validation import prop_account_rules as prop_rules
from scripts.validation.prop_account_rules import load_prop_backtest_report_schema


def _copy_rules(tmp_path: Path) -> Path:
    path = tmp_path / prop_rules.DEFAULT_PROP_RULES_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (prop_rules.REPO_ROOT / prop_rules.DEFAULT_PROP_RULES_CONFIG).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return path


def _copy_report_schema(tmp_path: Path) -> Path:
    path = tmp_path / prop_rules.DEFAULT_REPORT_SCHEMA
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (prop_rules.REPO_ROOT / prop_rules.DEFAULT_REPORT_SCHEMA).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return path


def _qualifying_payout_events() -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for day in range(1, 6):
        events.append(
            {
                "timestamp": f"2026-01-0{day}T16:59:59-05:00",
                "event_type": "eod",
                "realized_pnl": 520.0,
                "unrealized_pnl": 0.0,
                "open_contracts": 0,
            }
        )
    events.append(
        {
            "timestamp": "2026-01-06T10:00:00-05:00",
            "event_type": "payout_request",
            "requested_payout_amount": 500.0,
            "unrealized_pnl": 0.0,
            "open_contracts": 0,
        }
    )
    events.append(
        {
            "timestamp": "2026-01-06T12:00:00-05:00",
            "event_type": "payout_approved",
            "approved_payout_amount": 500.0,
            "unrealized_pnl": 0.0,
            "open_contracts": 0,
        }
    )
    return events


def _six_approved_payout_events() -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for payout_number in range(1, 7):
        for day in range(1, 6):
            events.append(
                {
                    "timestamp": f"cycle-{payout_number}-day-{day}-eod",
                    "event_type": "eod",
                    "realized_pnl": 520.0,
                    "unrealized_pnl": 0.0,
                    "open_contracts": 0,
                }
            )
        events.append(
            {
                "timestamp": f"cycle-{payout_number}-request",
                "event_type": "payout_request",
                "requested_payout_amount": 500.0,
                "unrealized_pnl": 0.0,
                "open_contracts": 0,
            }
        )
        events.append(
            {
                "timestamp": f"cycle-{payout_number}-approval",
                "event_type": "payout_approved",
                "approved_payout_amount": 500.0,
                "unrealized_pnl": 0.0,
                "open_contracts": 0,
            }
        )
    return events


def test_synthetic_ledger_builds_prop_account_report(tmp_path: Path) -> None:
    result = simulate_prop_account_from_config(
        _qualifying_payout_events(),
        prop_rules_config=_copy_rules(tmp_path),
        strategy_name="unit_synthetic",
    )

    report = result.report
    assert report["account_name"] == "apex_50k_eod_pa"
    assert report["pa_status"] == "active"
    assert report["payout_status"] == "approved"
    assert report["total_cash_payouts"] == 500.0
    assert report["ending_balance"] == 52100.0
    assert report["safety_net_buffer"] == 0.0
    assert report["current_eod_threshold"] == 50100.0
    assert report["current_pa_tier"] == 2
    assert report["contract_limit_rejections"] == 0
    assert report["daily_loss_limit_hits"] == 0
    schema = load_prop_backtest_report_schema(_copy_report_schema(tmp_path))
    assert sorted(set(schema["required_fields"]) - set(report)) == []
    assert len(result.ledger) == 7


def test_contract_limit_rejection_and_dll_pause_do_not_close_pa(tmp_path: Path) -> None:
    result = simulate_prop_account_from_config(
        [
            {
                "timestamp": "2026-01-01T09:35:00-05:00",
                "event_type": "trade",
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "open_contracts": 3,
            },
            {
                "timestamp": "2026-01-01T10:00:00-05:00",
                "event_type": "trade",
                "realized_pnl": -1000.0,
                "unrealized_pnl": 0.0,
                "open_contracts": 1,
            },
        ],
        prop_rules_config=_copy_rules(tmp_path),
    )

    assert result.report["pa_status"] == "active"
    assert result.report["contract_limit_rejections"] == 1
    assert result.report["daily_loss_limit_hits"] == 1
    assert result.report["dll_pause_count"] == 1
    assert result.ledger[-1]["open_contracts"] == 0
    assert "daily_loss_limit_hit_liquidated_paused" in result.report["rule_violations"]


def test_eod_threshold_touch_closes_pa(tmp_path: Path) -> None:
    result = simulate_prop_account_from_config(
        [
            {
                "timestamp": "2026-01-01T09:35:00-05:00",
                "event_type": "trade",
                "realized_pnl": -2001.0,
                "unrealized_pnl": 0.0,
                "open_contracts": 1,
            }
        ],
        prop_rules_config=_copy_rules(tmp_path),
    )

    assert result.report["pa_status"] == "closed"
    assert result.report["pa_closure_reason"] == "eod_threshold_touch"
    assert "eod_threshold_touch_closed" in result.report["rule_violations"]


def test_post_closure_event_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PropAccountSimulationError, match="event received after PA closed"):
        simulate_prop_account_from_config(
            [
                {
                    "timestamp": "2026-01-01T09:35:00-05:00",
                    "event_type": "trade",
                    "realized_pnl": -2001.0,
                    "unrealized_pnl": 0.0,
                    "open_contracts": 1,
                },
                {
                    "timestamp": "2026-01-01T09:40:00-05:00",
                    "event_type": "trade",
                    "realized_pnl": 500.0,
                    "unrealized_pnl": 0.0,
                    "open_contracts": 1,
                },
            ],
            prop_rules_config=_copy_rules(tmp_path),
        )


def test_ineligible_payout_request_fails(tmp_path: Path) -> None:
    with pytest.raises(PropAccountSimulationError, match="payout request is not eligible"):
        simulate_prop_account_from_config(
            [
                {
                    "timestamp": "2026-01-01T10:00:00-05:00",
                    "event_type": "payout_request",
                    "requested_payout_amount": 500.0,
                    "unrealized_pnl": 0.0,
                    "open_contracts": 0,
                }
            ],
            prop_rules_config=_copy_rules(tmp_path),
        )


def test_payout_approval_without_request_fails(tmp_path: Path) -> None:
    with pytest.raises(PropAccountSimulationError, match="payout approval requires pending request"):
        simulate_prop_account_from_config(
            [
                {
                    "timestamp": "2026-01-01T12:00:00-05:00",
                    "event_type": "payout_approved",
                    "approved_payout_amount": 500.0,
                    "unrealized_pnl": 0.0,
                    "open_contracts": 0,
                }
            ],
            prop_rules_config=_copy_rules(tmp_path),
        )


def test_sixth_approved_payout_completes_pa(tmp_path: Path) -> None:
    result = simulate_prop_account_from_config(
        _six_approved_payout_events(),
        prop_rules_config=_copy_rules(tmp_path),
    )

    assert result.report["pa_status"] == "completed"
    assert result.report["pa_closure_reason"] == "sixth_approved_payout"
    assert result.report["payout_number"] == 6
    assert result.report["total_cash_payouts"] == 3000.0
    assert "sixth_payout_completed" in result.ledger[-1]["rule_events"]


def test_partial_payout_approval_is_rejected_until_explicitly_modeled(tmp_path: Path) -> None:
    events = _qualifying_payout_events()
    events[-1]["approved_payout_amount"] = 250.0

    with pytest.raises(PropAccountSimulationError, match="approved payout must equal requested amount"):
        simulate_prop_account_from_config(
            events,
            prop_rules_config=_copy_rules(tmp_path),
        )


def test_payout_denial_restores_requested_balance_without_closing_pa(tmp_path: Path) -> None:
    events = _qualifying_payout_events()
    events[-1] = {
        "timestamp": "2026-01-06T12:00:00-05:00",
        "event_type": "payout_denied",
        "unrealized_pnl": 0.0,
        "open_contracts": 0,
    }

    result = simulate_prop_account_from_config(
        events,
        prop_rules_config=_copy_rules(tmp_path),
    )

    assert result.report["pa_status"] == "active"
    assert result.report["payout_status"] == "denied"
    assert result.report["ending_balance"] == 52600.0
    assert result.report["total_cash_payouts"] == 0.0
    assert result.report["requested_payout_amount"] == 500.0
    assert result.report["approved_payout_amount"] == 0.0
    assert result.report["safety_net_buffer"] == 500.0
    assert "payout_denied_balance_restored" in result.ledger[-1]["rule_events"]


def test_payout_denial_without_request_fails(tmp_path: Path) -> None:
    with pytest.raises(PropAccountSimulationError, match="payout denial requires pending request"):
        simulate_prop_account_from_config(
            [
                {
                    "timestamp": "2026-01-01T12:00:00-05:00",
                    "event_type": "payout_denied",
                    "unrealized_pnl": 0.0,
                    "open_contracts": 0,
                }
            ],
            prop_rules_config=_copy_rules(tmp_path),
        )


def test_tier_can_move_down_after_prior_eod_balance_drop(tmp_path: Path) -> None:
    result = simulate_prop_account_from_config(
        [
            {
                "timestamp": "2026-01-01T16:59:59-05:00",
                "event_type": "eod",
                "realized_pnl": 3200.0,
                "unrealized_pnl": 0.0,
                "open_contracts": 0,
            },
            {
                "timestamp": "2026-01-02T16:59:59-05:00",
                "event_type": "eod",
                "realized_pnl": -1900.0,
                "unrealized_pnl": 0.0,
                "open_contracts": 0,
            },
        ],
        prop_rules_config=_copy_rules(tmp_path),
    )

    assert [row["tier"] for row in result.report["eod_threshold_path"]] == [3, 1]
    assert result.report["tier_down_events"] == 1
    assert "pa_tier_down" in result.ledger[-1]["rule_events"]
