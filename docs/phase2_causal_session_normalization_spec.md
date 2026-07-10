# Phase 2 Causal Session-Normalization Specification

Status: active specification for Phase 2 causal/session-normalized data.

## Scope

Phase 2 converts Phase 1B raw 1-minute futures parquet into causal,
session-normalized rows for downstream labels and features. The output remains
research data only. This spec does not approve provider downloads, broad data
rebuilds, labels, features, WFA, model training, promotion, paper trading, or
live trading.

## Timestamp And Availability Contract

- Canonical parquet timestamps are UTC.
- Exchange-local time is used only to classify session membership from
  `configs/market_sessions.yaml`.
- A bar's `open`, `high`, `low`, `close`, and `volume` are not available as
  same-bar features at `ts`.
- Phase 2 writes `bar_available_ts = ts + 1 minute`. Any downstream feature
  using that row's OHLCV must have a decision timestamp at or after
  `bar_available_ts`.
- `normalization_rule_version` records the active rule contract used for each
  normalized row.

## Session Contract

- Session boundaries must come from `configs/market_sessions.yaml`; hardcoded
  fallback calendars are test-only and fail audits outside that path.
- Current configured CME futures sessions use the exchange-local
  `America/Chicago` Globex session template.
- Pre-market and post-market are not separate concepts in the current full
  Globex policy. Rows are either inside the configured session or invalid.
- Holidays, early closes, and intraday breaks must be represented from the
  configured calendar. Silent fallback to inferred price patterns is forbidden.
- Session open/close flags are derived from observed rows within each
  `session_segment_id`; boundary sessions remain not ready unless adjacent
  context proves they are complete.

## Gap, Halt, And Auction Contract

- Missing in-session minutes may be represented only as explicit synthetic
  marker rows.
- Synthetic rows are not evidence of trades or quotes.
- Synthetic rows must have `raw_row_present=false`, `is_synthetic=true`,
  `phase2_ready=false`, blank OHLCV values, no `source_row_number`, and a
  non-empty invalid reason.
- Copying prior close/high/low/volume into synthetic rows is forbidden unless a
  future separately approved external-proof mode is implemented.
- Gaps, halts, and auctions must not be smoothed into trainable data.

## Readiness Contract

- `phase2_ready` is the deterministic downstream readiness flag.
- `phase2_ready` must equal `causal_valid`.
- `phase2_not_ready_reason` must equal `causal_invalid_reason`.
- Invalid rows must have at least one supported reason. Valid rows must have a
  blank reason.
- Supported reasons are:
  `raw_row_missing`, `synthetic`, `invalid_ohlcv`, `outside_session`,
  `degraded_session`, `roll_window`, `boundary_session`, and
  `missing_required_raw_cols`.
- Readiness must not depend on labels, predictions, execution outcomes, future
  liquidity, future spreads, or any target result.

## Lineage Contract

- Every raw-present normalized row must reconcile to raw parquet by
  `source_path`, `source_file_hash`, and `source_row_number`.
- Raw-present row OHLCV and timestamp values must match the referenced raw row.
- Synthetic marker rows are traceable only as gap markers and must not be
  counted as raw evidence.
- Output counts must reconcile as in-year raw rows plus explicit synthetic
  marker rows.

## Leakage Assessment

- Calendar-derived fields are causal because they use timestamp plus static
  session configuration.
- Gap and boundary flags may use adjacent rows, including future context, but
  only as exclusion flags. They cannot make a row ready.
- Roll-window flags may use next roll-boundary context, but only as exclusion
  flags. They cannot make a row ready.
- Phase 3 labels must reject any current, entry, 30-minute, or 60-minute target
  path that intersects a `phase2_ready=false` row.

## Required Audit

Run the read-only audit for exact scoped outputs after Phase 2 code or artifact
changes:

```powershell
python -m scripts.validation.audit_phase2_causal_session_normalization --causal-root data/causally_gated_normalized --raw-root data/raw --session-config configs/market_sessions.yaml
```

Use `--markets`, `--years`, and `--max-files` for bounded review. Do not run a
broad active-root audit as approval for rebuilds or downstream modeling unless a
separate bounded prompt authorizes that scope.
