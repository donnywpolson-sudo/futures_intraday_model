# Apex 50K EOD PA Trade/Fill Connector Design

Status: plan-only connector design. No connector code is approved by this document.

This design defines how a real trade/fill ledger should be mapped into the standalone prop-account simulator's synthetic event schema. It must remain separate from Phase 8 model selection, strategy logic, WFA/modeling, promotion, paper/live, provider/download commands, registry/ledger mutation, staging, commit, and push.

## Goal

Create a future connector that converts an already-existing trade/fill ledger into the synthetic event rows consumed by:

- `scripts/prop_account_simulation/simulator.py`
- `configs/prop_rules/apex_50k_eod_pa_2026-07-03.yaml`

The connector should only translate validated execution/accounting records. It should not generate trades, alter strategy entries or exits, infer model signals, rebuild costs, or run Phase 8.

## Non-Goals

- No connector implementation in this step.
- No Phase 8 execution, report refresh, or payload mutation.
- No WFA/modeling execution.
- No strategy signal, target, feature, prediction, cost, or position-policy changes.
- No generated prop-account report writer.
- No provider/download commands.
- No registry, trial-ledger, data, log, or model mutation.
- No paper/live trading integration.

## Required Source Ledger Fields

A future connector should require one row per account-impacting event, ordered by event time:

- `timestamp`: timezone-aware event timestamp.
- `event_id`: stable unique event identifier.
- `sequence_number`: optional stable ordering key; required when rows can share a timestamp and `event_id` does not encode source-order deterministically.
- `event_type`: source-side type such as `fill`, `mark`, `session_eod`, `payout_request`, `payout_approved`, or `payout_denied`.
- `market`: instrument or market code, when applicable.
- `side`: `buy`, `sell`, `long`, `short`, or flat marker, when applicable.
- `quantity`: signed or side-qualified contract count.
- `fill_price`: execution price for fills.
- `mark_price`: current mark price for unrealized PnL events.
- `realized_pnl`: realized PnL delta after commissions, fees, spread, and slippage.
- `unrealized_pnl`: total current unrealized PnL across all open positions after the event.
- `open_contracts`: total open contract exposure across all instruments after the event, standard-contract equivalent.
- `commission`: commission delta, if separated from realized PnL.
- `exchange_fees`: exchange/regulatory fee delta, if separated from realized PnL.
- `slippage`: slippage estimate or actual delta, if separated from realized PnL.
- `payout_amount`: payout request, approval, or denial amount when applicable.

If costs are supplied separately from `realized_pnl`, the connector must document whether it folds them into simulator `realized_pnl` or rejects the ledger until a normalized net-PnL field exists.

## Synthetic Event Mapping

The connector should output only these simulator event types:

| Source event | Synthetic `event_type` | Required synthetic fields |
| --- | --- | --- |
| Fill or realized PnL update | `trade` | `timestamp`, `realized_pnl`, `unrealized_pnl`, `open_contracts` |
| Mark-only unrealized PnL update | `trade` | `timestamp`, `realized_pnl: 0`, `unrealized_pnl`, `open_contracts` |
| End-of-day account snapshot | `eod` | `timestamp`, `realized_pnl`, `unrealized_pnl`, `open_contracts` |
| Payout request | `payout_request` | `timestamp`, `requested_payout_amount`, `unrealized_pnl`, `open_contracts` |
| Payout approval | `payout_approved` | `timestamp`, `approved_payout_amount`, `unrealized_pnl`, `open_contracts` |
| Payout denial | `payout_denied` | `timestamp`, `unrealized_pnl`, `open_contracts` |

The connector must preserve chronological order. If multiple source rows share the same timestamp, ordering must be deterministic using an explicit `sequence_number` or an `event_id` whose ordering semantics are documented and stable. If neither field can prove ordering, validation must fail before simulator execution.

## Timestamp Rules

- Source timestamps must be timezone-aware.
- EOD events must align to the configured Apex EOD snapshot time: `16:59:59 America/New_York`.
- Trading-day reset must be represented by the next EOD/session boundary, not by mutating prior events.
- Events after PA closure or completion should not be emitted; if present in the source ledger, the connector should fail validation before simulator execution.
- Payout events must occur after the event sequence that creates eligibility.

## PnL Rules

- `realized_pnl` must be an event delta, not cumulative account PnL.
- `unrealized_pnl` must be total account-level unrealized PnL after the event.
- `open_contracts` must be total combined exposure across all instruments after the event.
- Costs must not be double-counted. Either source `realized_pnl` is already net of costs, or costs are folded in exactly once by the connector.
- Liquidation fills, if present in the source ledger, should be represented as normal `trade` events with realized/unrealized PnL after the fill.

## EOD Marker Rules

The connector must emit one `eod` event per trading day included in the simulation, even if no trade occurred that day and the source ledger has a valid account snapshot.

Each EOD event should carry:

- event-day ending realized PnL delta since the previous simulator event;
- current total unrealized PnL;
- current open contracts, expected to be `0` if holding through market close is prohibited and enforced upstream;
- the snapshot timestamp normalized to the configured EOD time.

If an EOD snapshot is missing for a day with activity, validation should fail rather than infer the EOD balance.

## Payout Event Rules

- `payout_request` must include the requested amount.
- `payout_approved` must include the approved amount and should match the pending request unless partial approval is explicitly modeled later.
- `payout_denied` restores the request-deducted balance in the simulator and must not close the PA.
- Denial reason can be carried as connector metadata later, but the current simulator schema does not require it.

## Validation Gates

A future implementation should fail closed before simulator execution if:

- Required source fields are missing.
- Timestamps are naive, unsorted, duplicated without deterministic `sequence_number` or documented ordered `event_id`, or outside the requested backtest window.
- `realized_pnl` appears cumulative instead of delta-based.
- `unrealized_pnl` is missing for any event after positions are opened.
- `open_contracts` is missing, negative when unsigned, or not standard-contract equivalent.
- EOD snapshots are missing for active trading days.
- Payout approval or denial appears without a prior request.
- Payout approval amount differs from request amount while partial approval remains unsupported.
- Events exist after a source-side account closure/completion marker.
- Costs cannot be reconciled as exactly once.

## Output Contract

The connector should return an in-memory list of synthetic events plus connector metadata:

- source ledger path or identifier;
- source ledger hash;
- row count in and event count out;
- rejected row count;
- normalization assumptions;
- validation status and failures.

The first implementation should not write files. A later report-writer step can serialize connector metadata and simulator output only after separate approval.

## Test Plan For Future Implementation

Focused tests should use tiny synthetic source ledgers and assert:

- fill rows map to `trade` events with net realized PnL deltas;
- mark-only rows update unrealized PnL without realized PnL;
- EOD markers are required and correctly ordered;
- payout request/approval/denial rows map to simulator payout events;
- missing EOD, naive timestamps, cumulative PnL, duplicate timestamps without deterministic ordering, and post-closure rows fail validation;
- costs are not double-counted.

## Stop Condition

Stop after the design is reviewed. Implementation of the connector, report writer, Phase 8 adapter, or any generated report command requires separate explicit approval.
