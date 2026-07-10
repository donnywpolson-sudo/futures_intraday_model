from __future__ import annotations

import pytest

from scripts.prop_account_simulation.trade_fill_connector import (
    TradeFillConnectorError,
    convert_trade_fill_ledger,
)


def _row(
    event_id: str,
    timestamp: str,
    event_type: str,
    *,
    realized_pnl: float = 0.0,
    unrealized_pnl: float = 0.0,
    open_contracts: float = 0.0,
    payout_amount: float | None = None,
    sequence_number: int | None = None,
    **extra: object,
) -> dict[str, object]:
    row: dict[str, object] = {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "open_contracts": open_contracts,
    }
    if payout_amount is not None:
        row["payout_amount"] = payout_amount
    if sequence_number is not None:
        row["sequence_number"] = sequence_number
    row.update(extra)
    return row


def test_fill_mark_and_eod_rows_map_to_synthetic_events() -> None:
    result = convert_trade_fill_ledger(
        [
            _row(
                "fill-1",
                "2026-01-05T09:35:00-05:00",
                "fill",
                realized_pnl=125.0,
                unrealized_pnl=10.0,
                open_contracts=1,
            ),
            _row(
                "mark-1",
                "2026-01-05T10:00:00-05:00",
                "mark",
                unrealized_pnl=30.0,
                open_contracts=1,
            ),
            _row("eod-1", "2026-01-05T16:59:59-05:00", "session_eod"),
        ],
        source_id="unit-ledger",
    )

    assert result.events == [
        {
            "timestamp": "2026-01-05T09:35:00-05:00",
            "event_type": "trade",
            "realized_pnl": 125.0,
            "unrealized_pnl": 10.0,
            "open_contracts": 1.0,
        },
        {
            "timestamp": "2026-01-05T10:00:00-05:00",
            "event_type": "trade",
            "realized_pnl": 0.0,
            "unrealized_pnl": 30.0,
            "open_contracts": 1.0,
        },
        {
            "timestamp": "2026-01-05T16:59:59-05:00",
            "event_type": "eod",
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "open_contracts": 0.0,
        },
    ]
    assert result.metadata["source_id"] == "unit-ledger"
    assert result.metadata["row_count_in"] == 3
    assert result.metadata["event_count_out"] == 3
    assert result.metadata["validation_status"] == "PASS"


def test_same_timestamp_rows_require_deterministic_sequence_number() -> None:
    result = convert_trade_fill_ledger(
        [
            _row(
                "fill-1",
                "2026-01-05T09:35:00-05:00",
                "fill",
                sequence_number=1,
                open_contracts=1,
            ),
            _row(
                "mark-1",
                "2026-01-05T09:35:00-05:00",
                "mark",
                sequence_number=2,
                unrealized_pnl=10.0,
                open_contracts=1,
            ),
            _row("eod-1", "2026-01-05T16:59:59-05:00", "session_eod", sequence_number=3),
        ]
    )

    assert [event["event_type"] for event in result.events] == ["trade", "trade", "eod"]
    assert result.metadata["same_timestamp_ordering"] == "sequence_number"


def test_same_timestamp_rows_reject_mixed_ordering_scheme() -> None:
    with pytest.raises(TradeFillConnectorError, match="one deterministic ordering scheme"):
        convert_trade_fill_ledger(
            [
                _row("fill-1", "2026-01-05T09:35:00-05:00", "fill", open_contracts=1),
                _row(
                    "mark-1",
                    "2026-01-05T09:35:00-05:00",
                    "mark",
                    sequence_number=2,
                    unrealized_pnl=10.0,
                    open_contracts=1,
                ),
                _row("eod-1", "2026-01-05T16:59:59-05:00", "session_eod", sequence_number=3),
            ]
        )


def test_eod_timestamp_is_normalized_to_apex_snapshot_timezone() -> None:
    result = convert_trade_fill_ledger(
        [
            _row("fill-1", "2026-01-05T09:35:00-05:00", "fill", open_contracts=1),
            _row("eod-1", "2026-01-05T21:59:59+00:00", "session_eod"),
        ]
    )

    assert result.events[-1] == {
        "timestamp": "2026-01-05T16:59:59-05:00",
        "event_type": "eod",
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "open_contracts": 0.0,
    }


def test_eod_timestamp_must_match_apex_snapshot_time() -> None:
    with pytest.raises(TradeFillConnectorError, match="Apex EOD snapshot time"):
        convert_trade_fill_ledger(
            [
                _row("fill-1", "2026-01-05T09:35:00-05:00", "fill", open_contracts=1),
                _row("eod-1", "2026-01-05T16:59:58-05:00", "session_eod"),
            ]
        )


def test_activity_after_apex_reset_requires_next_session_eod() -> None:
    with pytest.raises(TradeFillConnectorError, match="2026-01-06"):
        convert_trade_fill_ledger(
            [
                _row("eod-1", "2026-01-05T16:59:59-05:00", "session_eod"),
                _row("fill-1", "2026-01-05T18:30:00-05:00", "fill", open_contracts=1),
            ]
        )


def test_payout_request_approval_and_denial_rows_map_to_simulator_events() -> None:
    approval = convert_trade_fill_ledger(
        [
            _row("request-1", "2026-01-06T10:00:00-05:00", "payout_request", payout_amount=500.0),
            _row("approved-1", "2026-01-06T12:00:00-05:00", "payout_approved", payout_amount=500.0),
        ],
        require_eod_for_activity=False,
    )
    denial = convert_trade_fill_ledger(
        [
            _row("request-2", "2026-01-07T10:00:00-05:00", "payout_request", payout_amount=500.0),
            _row("denied-1", "2026-01-07T12:00:00-05:00", "payout_denied", payout_amount=500.0),
        ],
        require_eod_for_activity=False,
    )

    assert approval.events == [
        {
            "timestamp": "2026-01-06T10:00:00-05:00",
            "event_type": "payout_request",
            "requested_payout_amount": 500.0,
            "unrealized_pnl": 0.0,
            "open_contracts": 0.0,
        },
        {
            "timestamp": "2026-01-06T12:00:00-05:00",
            "event_type": "payout_approved",
            "approved_payout_amount": 500.0,
            "unrealized_pnl": 0.0,
            "open_contracts": 0.0,
        },
    ]
    assert denial.events[-1]["event_type"] == "payout_denied"


def test_missing_eod_for_active_day_fails() -> None:
    with pytest.raises(TradeFillConnectorError, match="missing EOD snapshot"):
        convert_trade_fill_ledger(
            [
                _row(
                    "fill-1",
                    "2026-01-05T09:35:00-05:00",
                    "fill",
                    open_contracts=1,
                )
            ]
        )


def test_naive_timestamp_fails() -> None:
    with pytest.raises(TradeFillConnectorError, match="timezone-aware"):
        convert_trade_fill_ledger(
            [
                _row("fill-1", "2026-01-05T09:35:00", "fill"),
                _row("eod-1", "2026-01-05T16:59:59-05:00", "session_eod"),
            ]
        )


def test_duplicate_timestamp_without_ordering_fails() -> None:
    with pytest.raises(TradeFillConnectorError, match="duplicate timestamp requires"):
        convert_trade_fill_ledger(
            [
                _row("fill-1", "2026-01-05T09:35:00-05:00", "fill"),
                _row("mark-1", "2026-01-05T09:35:00-05:00", "mark"),
                _row("eod-1", "2026-01-05T16:59:59-05:00", "session_eod"),
            ]
        )


def test_cumulative_realized_pnl_fails() -> None:
    with pytest.raises(TradeFillConnectorError, match="event delta"):
        convert_trade_fill_ledger(
            [
                _row(
                    "fill-1",
                    "2026-01-05T09:35:00-05:00",
                    "fill",
                    pnl_basis="cumulative",
                ),
                _row("eod-1", "2026-01-05T16:59:59-05:00", "session_eod"),
            ]
        )


def test_post_closure_source_rows_fail() -> None:
    with pytest.raises(TradeFillConnectorError, match="after account closure"):
        convert_trade_fill_ledger(
            [
                _row(
                    "eod-1",
                    "2026-01-05T16:59:59-05:00",
                    "session_eod",
                    account_status="closed",
                ),
                _row("fill-1", "2026-01-06T09:35:00-05:00", "fill"),
            ],
            require_eod_for_activity=False,
        )


def test_cost_double_count_risk_fails_by_default() -> None:
    with pytest.raises(TradeFillConnectorError, match="costs cannot be reconciled"):
        convert_trade_fill_ledger(
            [
                _row(
                    "fill-1",
                    "2026-01-05T09:35:00-05:00",
                    "fill",
                    commission=2.5,
                ),
                _row("eod-1", "2026-01-05T16:59:59-05:00", "session_eod"),
            ]
        )


def test_payout_lifecycle_failures_are_rejected() -> None:
    with pytest.raises(TradeFillConnectorError, match="requires prior request"):
        convert_trade_fill_ledger(
            [_row("approved-1", "2026-01-06T12:00:00-05:00", "payout_approved", payout_amount=500.0)],
            require_eod_for_activity=False,
        )

    with pytest.raises(TradeFillConnectorError, match="differs from request"):
        convert_trade_fill_ledger(
            [
                _row("request-1", "2026-01-06T10:00:00-05:00", "payout_request", payout_amount=500.0),
                _row("approved-1", "2026-01-06T12:00:00-05:00", "payout_approved", payout_amount=250.0),
            ],
            require_eod_for_activity=False,
        )
