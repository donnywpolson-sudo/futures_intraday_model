# ORAC v2 Trial Packet

Hypothesis ID: `opening_range_acceptance_continuation_event_capture_30m_v2`

Status: `CANDIDATE`

Allowed use: predeclared research packet only. This document does not approve target construction, discovery, WFA, Phase 8, promotion, paper trading, or live trading.

## Context

The current Tier 1 model and `opening_range_acceptance_continuation_30m_v1` are failed trading candidates. Existing reports may motivate this packet, but they must not be used to rescue-tune v1 or select post-hoc winners for v2.

Verified local evidence before this packet:

- Current Tier 1 Phase 8 economics were negative: no-trade was not beaten and average net dollars per trade was `-41.57031551596151`.
- ORAC v1 target-smoke evidence passed, but later executable-policy evidence failed. Treat v1 as target-research evidence only, not a tradable line.

## Predeclared Hypothesis

Market: ES only.

Session: RTH opening-range setup only. The opening range is the completed first 30 session bars.

Behavior: after the 30-minute opening range is complete, the first causal acceptance outside the range may predict continuation over the next 30 minutes.

Entry timing: enter at the next bar open after the first qualifying acceptance event. Allow at most one event per session.

Exit horizon: fixed 30-minute timeout exit is the pass/fail economic policy. First-touch and stop-first diagnostics may be reported, but they must not be used to select take-profit or stop-loss parameters for v2.

Expected edge source: reducing ORAC v1 turnover to one first acceptance event per session should increase expected move size relative to round-turn cost. The candidate must still prove the edge under base costs and 2x cost stress.

## Feature Rules

Allowed features:

- Causal pre-entry opening-range state.
- Causal pre-entry session timing fields.
- Causal pre-entry volatility fields.
- Causal pre-entry volume and liquidity fields if already available.
- Causal pre-entry term-structure or carry fields where data supports them.

Forbidden features and tuning:

- No post-entry values.
- No target-derived columns.
- No future path data.
- No post-hoc UTC hour filters selected from ORAC v1 diagnostics.
- No feature, threshold, cost, fold, market, or year change after seeing v2 results.
- No reuse of holdout or forward rows for selection.

## Cost Rules

Before any rerun, refresh the base round-turn cost assumption from primary sources:

- IBKR futures commission page: `https://www.interactivebrokers.com/en/pricing/commissions-futures.php`
- CME clearing and trading fee page: `https://www.cmegroup.com/company/clearing-fees.html`

The cost refresh must record commission, exchange, clearing, venue, membership or non-membership assumption, effective date, tick conversion, and the resulting ES round-turn dollar and tick costs.

If the primary-source cost refresh is unavailable, block reruns rather than reuse stale costs.

## Required Baselines

The candidate must beat all applicable simple baselines under the same scope and costs:

- No-trade.
- Random-entry matched by session, count, and direction.
- Simple trend.
- Simple mean-reversion.
- Intraday seasonality.
- Carry or term-structure where data supports it.

## Trial Log And Statistical Validity

Every future run must log:

- Run ID.
- Hypothesis ID.
- Data hashes.
- Cost config hash.
- Model, label, and policy parameters.
- Baseline results.
- PBO.
- Probabilistic Sharpe.
- Deflated Sharpe.
- Multiple-testing family.
- Regime breakdowns.
- Final stop or pass decision.

Statistical pass thresholds:

- PBO must be below `0.20`.
- Probabilistic Sharpe probability must be at least `0.95`.
- Deflated Sharpe probability must be at least `0.95`.
- Multiple-testing family must be recorded before execution.
- Regime breakdowns must be recorded before any pass decision.

## Kill Criteria

Stop the branch if any condition is true:

- Net dollars are nonpositive under base costs.
- Net dollars are nonpositive under 2x costs.
- Any locked fold is net negative.
- Average net dollars per trade is nonpositive.
- The best simple baseline beats the candidate.
- PBO is at least `0.20`.
- Probabilistic Sharpe or Deflated Sharpe probability is below `0.95`.
- Regime results depend on one narrow pocket.
- Execution realism evidence is unavailable before any trading conclusion.

## Execution Realism Gate

Before any trading conclusion, paper-trading claim, or live-trading claim, require:

- Actual contract mapping.
- Roll handling.
- Spread and depth assumptions.
- Latency assumptions.
- Partial fill and reject assumptions.
- Capacity.
- Margin.
- Position sizing.
- Loss limits.
- Kill switch.

## Forbidden Actions From This Packet

- Do not run discovery, WFA, Phase 8, promotion, artifact freeze, paper trading, or live trading from this packet.
- Do not mutate `configs/costs.yaml` from this packet.
- Do not run provider downloads from this packet.
- Do not add this hypothesis to a runnable target harness without a separate bounded target-implementation plan.
- Do not use ORAC v1 results to tune thresholds, hours, take-profit, stop-loss, features, folds, markets, or years.
