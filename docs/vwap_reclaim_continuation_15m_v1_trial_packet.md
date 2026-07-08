# VWAP Reclaim Continuation 15m Trial Packet

Hypothesis ID: `vwap_reclaim_continuation_15m_v1`

Status: `CANDIDATE`

Allowed use: source/tests and preflight packet only. This document does not approve discovery, WFA, Phase 8, promotion, artifact freeze, paper trading, or live trading.

## Context

Verified local evidence before this packet:

- Current Tier 1 Phase 8 economics are diagnostic research only and fail alpha/promotion readiness.
- The direct `vwap_reversion_30m_v1` branch is stopped and must not be reused as a new hypothesis.
- ORAC v2 is stopped by `STOP_CLASS_COLLAPSE`; do not rerun ORAC v2 discovery or tune from its output.
- Proposal-only strategy ideation for this candidate is not model-trust evidence; it is a draft handoff only.

## Predeclared Hypothesis

Market: ES only.

Years: 2023 and 2024 research folds only.

Behavior: after ES makes a causal same-session excursion away from VWAP, a reclaim through causal session VWAP may identify continuation in the reclaim direction.

Entry timing: enter at the next bar open after the reclaim event.

Exit horizon: 15-minute same-session fixed-horizon exit.

Target rule: long events require a prior below-VWAP excursion and upward reclaim; short events require a prior above-VWAP excursion and downward reclaim. Direction is nonflat only when the terminal 15-minute move in the reclaim direction clears the predeclared threshold.

Threshold: Round-turn cost ticks plus `min_profit_ticks`, compared against prior 60-bar one-minute close-diff volatility scaled by `sqrt(15)`. Use the larger value.

Costs: use existing `configs/costs.yaml`; do not mutate costs from this packet.

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

- Long, short, or flat class balance collapses.
- Discovery top net is nonpositive.
- Fewer than half of discovery folds have positive top net.
- Duplicate overlap with the current 15-minute deadzone target exceeds the registered cap.
- Net dollars are nonpositive under base costs or 2x costs.
- Average net dollars per trade is nonpositive.
- The best simple baseline beats the candidate.
- PBO is at least `0.20`.
- Probabilistic Sharpe or Deflated Sharpe probability is below `0.95`.
- Regime results depend on one narrow pocket.

## Forbidden Actions From This Packet

- Do not run discovery, WFA, Phase 8, promotion, artifact freeze, paper trading, or live trading from this packet.
- Do not rerun ORAC v2 discovery.
- Do not mutate `configs/costs.yaml` from this packet.
- Do not run provider downloads from this packet.
- Do not tune thresholds, features, costs, folds, markets, or years after seeing source-test, preflight, packet, or discovery output.
- Do not use holdout or forward rows for selection.
