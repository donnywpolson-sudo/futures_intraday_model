# opening_range_acceptance_continuation_30m_v1 First-Touch Feasibility Packet

## Summary

- Status: draft only.
- Purpose: evaluate whether the path-opportunity target can be translated into a tradable first-touch policy before any rescue, retirement, tuning, WFA/modeling, promotion, paper, or live decision.
- Inputs to use if separately approved: existing WFA predictions, executed-trades CSV, ES 2024 materialized bars, and `configs/costs.yaml`.

## Required Contract

- Target payoff basis: `path_favorable_excursion`.
- Compatible policy basis: `first_touch_path_capture`.
- Incompatible final decision basis: `fixed_horizon_exit`.
- Same-bar TP+SL handling must be explicit: report ambiguous counts and a stop-first conservative variant.

## Future Diagnostic Requirements

- Scope: `opening_range_acceptance_continuation_30m_v1`, ES only, 2024 only, 2,668 previously executed single-target policy trades.
- Grid: fixed TP/SL ticks such as `2,3,4,5,8,10`; no tuning and no winner selection.
- Outputs: one ignored JSON report and one ignored CSV grid under a future `reports/` root.
- Stop conditions: missing joins, duplicate trade keys, missing OHLC bars, non-ES market, generated output already present, unignored output path, staged generated artifact, or any request to tune/select/promote.
- Review fields: failure count, ambiguous same-bar count, stop-first net PnL, ambiguous-excluded net PnL, per-fold results, TP/SL grid rows, and generated-artifact hygiene.

## Do Not Do

- Do not run this packet without separate approval.
- Do not select a TP/SL pair from this diagnostic as a tuned policy.
- Do not mutate registry/status, rerun WFA/modeling, promote, stage, commit, push, paper, or live trade from this packet.
