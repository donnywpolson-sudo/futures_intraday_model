# Apex 50K EOD PA Simulator Design

Status: plan-only design plus smallest viable implementation target.

This design is for a standalone prop-account simulation layer. It must remain separate from Phase 8 model selection and must not change strategy signals, target construction, position policy, WFA/modeling, provider/download commands, registry/ledger files, promotion, artifact freeze, final holdout, paper/live, staging, commit, or push.

## Goal

Create a small, testable rule engine that consumes a synthetic trade/event ledger and the read-only Apex 50K EOD PA config:

- `configs/prop_rules/apex_50k_eod_pa_2026-07-03.yaml`
- `configs/report_schema/prop_backtest_report.yaml`

The first implementation target is not a full backtest connector. It should prove that PA-specific constraints can be modeled independently before any real Phase 8 output is connected.

## Non-Goals

- No Phase 8 execution or generated Phase 8 report refresh.
- No WFA/modeling execution.
- No strategy, target, feature, prediction, cost, or position-policy changes.
- No real account, broker, paper, or live trading integration.
- No payout request automation.
- No provider/download commands.
- No registry or trial-ledger mutation.

## Inputs

The simulator accepts synthetic event rows with these minimum fields:

- `timestamp`: ISO timestamp string.
- `event_type`: `trade`, `eod`, `payout_request`, `payout_approved`, or `payout_denied`.
- `realized_pnl`: realized PnL delta for the event.
- `unrealized_pnl`: current unrealized PnL after the event.
- `open_contracts`: desired total open contracts after the event.
- `requested_payout_amount`: only for payout request events.
- `approved_payout_amount`: only for payout approval events.
- `payout_denied` events do not require a payout amount; they apply only to the pending request already deducted from simulator balance.

The ledger is intentionally generic. A later connector can translate Phase 8 policy rows or a fill ledger into this format without changing the rule engine.

## Event Order

For each event, apply:

1. Update realized PnL and balance.
2. Reject orders whose absolute requested open contracts exceed the current PA tier limit.
3. Compute equity as balance plus unrealized PnL.
4. Check intraday DLL against session-start balance and current tier DLL.
5. If DLL is hit, liquidate positions and pause trading until the next session.
6. Check EOD trailing threshold against equity.
7. If the EOD threshold is touched, liquidate and close the PA permanently.
8. At EOD events, update daily net PnL, qualifying payout days, highest EOD balance, EOD threshold, next-session tier, and session-start balance.
9. For payout requests, enforce minimum balance, safety-net buffer, qualifying day count, and consistency rule.
10. If configured, subtract requested payout immediately from risk-check balance.
11. For payout approvals, increase cash payouts and close the PA as completed after payout number six.
12. For payout denials, restore the pending requested payout balance and leave the PA active.

## Initial Supported Rules

- Starting balance and initial fail level.
- EOD trailing threshold with permanent lock at `50100` after highest EOD balance reaches `52100`.
- Permanent safety net of `52100`.
- Daily loss limit by PA scaling tier.
- PA contract scaling by prior EOD balance, including tier down.
- Contract-limit rejection across all open instruments combined.
- DLL liquidation and pause without permanent PA closure.
- EOD threshold liquidation and permanent PA closure.
- Payout eligibility using qualifying profit days, safety-net buffer, minimum request balance, payout caps, and 50% consistency.
- Payout denial handling that restores the request-deducted balance and does not close the PA.
- Sixth approved payout closes the account as completed.

## Output

The simulator returns two in-memory objects:

- `report`: a compact prop-account report dictionary matching the current report-schema fields as far as the synthetic input supports.
- `ledger`: per-event rule-state snapshots for debugging and tests.

No files are written by the initial simulator. A later bounded report-writer step can serialize these objects under `reports/prop_account_backtests/<run>/` after separate approval.

## Stop Conditions

Stop and report a failure if:

- The prop-rule config cannot be loaded.
- Required PA-only rule fields are missing.
- A synthetic event type is unknown.
- A payout request exceeds the eligible amount or payout cap.
- A payout approval or denial arrives without a pending request.
- A payout approval amount differs from the pending requested amount while partial approvals remain unsupported.
- The simulator would need strategy-specific assumptions not present in the synthetic ledger.

## Future Separate Connector

A later change may add a connector from Phase 8 output into this synthetic event schema. That connector must be reviewed separately and must not alter Phase 8 strategy logic or model-selection behavior.
