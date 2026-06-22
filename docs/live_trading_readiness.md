# Live Trading Readiness

Current status: paper/smoke scaffold only.

This repository does not contain a production live-trading implementation. The current live-ops work is a deterministic, non-GUI, paper/sim scaffold for validating safety gates, audit rows, operator status, and paper-broker behavior. There is no real broker execution path, no broker SDK import, no broker credentials, and no live orders.

## What Is Implemented

The finite smoke path runs this paper-only decision loop:

```text
synthetic bar -> data quality -> model readiness -> signal state -> risk decision -> paper broker response -> reconciliation -> audit row -> operator status
```

The smoke path uses deterministic synthetic data and requires no Databento key, broker key, account ID, chart, GUI, or live data feed.

## Focused Validation

Run the focused live-ops/chart tests:

```powershell
$job = Start-Job { python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -vv -s --tb=short --durations=20 }
if (-not (Wait-Job $job -Timeout 120)) {
    Receive-Job $job
    Stop-Job $job
    throw "focused live ops/chart tests hung"
} else {
    Receive-Job $job
}
```

Expected current result: `71 passed`.

## Smoke Validation

Run the deterministic smoke check:

```powershell
python scripts\smoke_live_trading.py
```

Expected current result:

```text
PASS live trading smoke scenarios=34 decision_cycles=34 audit_rows=34
```

The default smoke output writes `reports/live_trading_smoke/audit.jsonl`. `reports/` and `*.jsonl` are ignored by Git.

To write to a temporary directory:

```powershell
python scripts\smoke_live_trading.py --audit-dir C:\path\to\tmp\live_smoke
```

To prove the CLI returns nonzero on a deterministic forced failure:

```powershell
python scripts\smoke_live_trading.py --audit-dir C:\path\to\tmp\forced --force-failure
```

## Paper Controls

Kill switch controls only the paper/sim layer:

```powershell
python scripts\kill_switch_on.py
python scripts\kill_switch_off.py
```

Paper cancel and flatten scripts operate on persisted paper state only:

```powershell
python scripts\paper_cancel_all.py
python scripts\paper_flatten_all.py
```

## Smoke Scenario Coverage

The smoke runner proves:

* missing model output produces `NO_SIGNAL` and no order
* missing features produce `NO_SIGNAL` and no order
* default safe config rejects trading
* explicit paper override can produce a deterministic paper fill
* operator kill switch blocks broker submission
* operator trading-disabled control blocks broker submission
* operator pause-new-entries control blocks broker submission
* bad OHLC is blocked
* stale bar data is blocked
* stale heartbeat/feed state is blocked
* feed disconnect and missing heartbeat state are blocked
* duplicate timestamp default policy is `block`
* kill switch blocks orders
* oversized orders are blocked
* duplicate order IDs are rejected
* reconciliation mismatch blocks new trades
* reconnect timestamp gap is blocked
* reconnect backfill-required state is blocked
* reconnect pending state blocks until reconciled
* contract mismatch is blocked
* root-symbol mismatch is blocked
* outside-session trading is blocked
* missing session config fails closed
* known closed-session periods are blocked
* monitor-only state blocks trading
* unsafe live mode is blocked
* decision-cycle exceptions are logged and fail closed
* broker-simulation exceptions are audited and fail closed
* audit rows equal completed decision cycles
* each audit row includes a nullable `exception` field
* operator status is rendered from decision-loop state within bounded width

Focused unit coverage also proves audit append failures fail closed and restore simulated paper state before returning.

## Closeout Audit Map

Final paper/smoke scaffold status by part:

| Part | Status | Evidence and remaining production-live work |
| --- | --- | --- |
| A | production-depth deferred | Bounded operator/status logging exists; explicit debug/verbose logging mode remains minimal. |
| B | complete for paper/smoke scaffold | Finite timeout behavior is covered by focused chart/feed tests; do not use `--no-timeout` for validation. |
| C | production-depth deferred | Bar parity, contract windows, final/partial bars, sessions, stale/feed/reconnect guards are covered; full historical/live contract coverage, rollover policy, no-trade intervals, and model feature exclusion remain production work. |
| D | complete for paper/smoke scaffold | Order-intent generation and validation are broker-agnostic and covered before broker submission. |
| E | complete for paper/smoke scaffold | Safe defaults keep trading disabled unless explicit paper mode is configured. |
| F | production-depth deferred | Model readiness and feature-order checks exist; concrete production model artifact adapters remain deferred. |
| G | complete for paper/smoke scaffold | Risk blocks disabled/live mode, unsafe live broker flags, kill switch, session/data/model/reconciliation failures, limits, duplicate order IDs, cooldowns, and position limits. |
| H | production-depth deferred | Kill switch and paper-control scripts are paper/sim-only and idempotent; optional cancel/flatten-on-kill runtime action remains deferred. |
| I | production-depth deferred | PaperBroker persists positions, open orders, fills, duplicate IDs, cancel-all, flatten-all, and deterministic paper fills; next-bar-open fill policy and direct broker-owned audit append remain deferred. |
| J | production-depth deferred | Position/open-order reconciliation failures block new approvals; stale open orders are represented; deeper audit-state reconciliation remains deferred. |
| K | production-depth deferred | JSONL audit appends are redacted, flush/fsync-backed, one row per smoke decision cycle, and fail closed on audit write/append failure; atomic multi-system durability and broader runtime durability remain deferred. |
| L | production-depth deferred | Feed disconnect, heartbeat, stale data, reconnect gap, and backfill-required guards are covered; system clock drift, low disk warnings, and full reconnect/backfill policy remain deferred. |
| M | production-depth deferred | Root/contract mismatch checks exist; rollover calendar automation remains deferred. |
| N | production-depth deferred | Session guard, closed-session, missing-session, monitor-only, and flatten-before-close configuration surfaces exist; production flatten-before-close runtime behavior remains deferred. |
| O | production-depth deferred | Operator status is bounded and decision-loop-derived in smoke; live chart status is display-only and not wired to a full live decision-loop state feed. |
| P | complete for paper/smoke scaffold | `python scripts\smoke_live_trading.py` is finite, deterministic, non-GUI, and reports 34 scenarios. |
| Q | complete for paper/smoke scaffold | Focused live-ops/chart tests and broad bounded pytest pass under wrappers. |
| R | complete for paper/smoke scaffold | Safe config defaults are disabled, paper-only unless explicitly overridden, and no live broker path is enabled. |
| S | complete for paper/smoke scaffold | This readiness document separates paper/smoke status from production-live requirements. |

## Known Limitations

Remaining Medium production-depth blockers by Part ID:

* A: explicit debug/verbose logging mode remains minimal.
* C: full historical/live data contract coverage for sessions, rollover policy, no-trade intervals, and model feature exclusion remains incomplete outside smoke/parity checks.
* F: imputer/scaler object integration is still represented by readiness flags, not concrete model artifact adapters.
* H: optional cancel/flatten-on-kill config action is not wired as runtime behavior.
* I: next-bar-open paper fill policy and direct broker-owned audit append remain deferred.
* J: audit-state reconciliation remains minimal.
* K: finite smoke audit integration fsyncs JSONL appends and restores paper state if audit append fails; atomic multi-system durability and broader runtime durability remain deferred.
* L: system clock drift, low disk warnings, and full reconnect/backfill policy remain deferred.
* M: rollover calendar automation/interface remains deferred beyond explicit active-contract checks.
* N: monitor-only outside session and flatten-before-close runtime behavior remain deferred.
* O: finite smoke operator status uses decision-loop state, but live chart status is not wired to a full live decision-loop state feed.
* Q: focused tests cover the paper/smoke path, but bounded broader validation and best-effort system-check tests/scripts remain deferred.

Bounded chart command validation was skipped because `live_chart_feed.py` constructs and shows a chart object inside `run_live_chart`; this phase forbids opening a blocking GUI/chart. The focused chart tests use fake chart and Databento objects instead.

Broad bounded validation currently passes: `732 passed, 58 warnings`.

## Go-Live Checklist

Live broker implementation remains disabled until explicitly approved. Before any live order path is considered, prove all of the following:

* live model output proven
* live-derived bars match historical feature contract
* data quality gate passes
* model readiness gate passes
* risk manager passes
* paper broker passes smoke tests
* kill switch works
* cancel all works
* flatten all works
* reconciliation works
* stale-data shutoff works
* session guard works
* contract rollover guard works
* audit logging works
* at least 2 weeks paper/shadow logs reviewed
* one-symbol / one-contract max for first live test
* manual broker-side limits configured
* real order types manually tested in broker UI before API use
* live broker implementation remains disabled until explicitly approved
