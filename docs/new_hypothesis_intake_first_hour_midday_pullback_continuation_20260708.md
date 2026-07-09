# New Hypothesis Intake: first_hour_midday_pullback_continuation_30m_v1

Status: `APPROVED_FOR_BOUNDED_SOURCE_TEST_CONVERSION_PLAN_ONLY`

This intake records the user-provided hypothesis only as a doc-only research gate. It does not register a target hypothesis, mutate the trial ledger, implement target construction, run source tests, run discovery, run WFA/modeling, run Phase 8, promote artifacts, freeze artifacts, paper trade, or live trade.

## Proposed Candidate

- Hypothesis ID: `first_hour_midday_pullback_continuation_30m_v1`
- Target family: `es_first_hour_midday_pullback_continuation_30m`
- Market/year scope: ES only, 2023-2024 research scope.
- Setup: after a strong first-hour directional move, wait for a midday pullback that retraces 35-60% of that move without breaking the same-session midpoint.
- Entry idea: enter in the first-hour direction when price resumes after the pullback, using only information available at the event timestamp.
- Exit idea: fixed 30-minute same-session exit.
- Cost assumption: existing configured ES costs only; this intake does not approve cost-config mutation.

## Evidence Reviewed

Primary repo evidence:

- `CODEX_HANDOFF.md`
- `PROJECT_OUTLINE.md`
- `manifests/target_hypotheses/registry.json`
- `manifests/target_hypotheses/trial_statuses.jsonl`

Draft context reviewed, not model-trust evidence:

- `reports/pipeline_audit/strategy_candidate_ideation/005_trend_day_pullback_continuation_30m_v1.{md,json}`
- `reports/pipeline_audit/strategy_candidate_ideation/008_trend_day_pullback_continuation_60m_v1.{md,json}`

## Verified Facts

- The worktree was not clean at intake start because previous doc-only closeout files were already uncommitted; no generated artifact command was run for this intake.
- The target registry still has exactly one non-rejected target: `opening_range_acceptance_continuation_30m_v1`, status `FROZEN`, `wfa_allowed=true`, and `next_allowed_actions=["PREPARE_BOUNDED_NEXT_PHASE_PLAN"]`.
- The trial ledger records `opening_range_acceptance_continuation_30m_v1` as frozen after discovery, confirmation, and locked target-construction smokes. That evidence is target-smoke readiness only, not promotion or trading evidence.
- Recent ES target branches including ORAC v2, VWAP reclaim, opening-drive failed-followthrough, session compression, late-session range resolution, and volume pace are `REJECTED`.
- The existing trend-day pullback ideation cards are explicitly proposal-only, not runnable, and `not_model_trust_evidence`.

## Material Difference Review

This hypothesis is materially different enough for a source/test conversion plan because it combines a first-hour directional-state prerequisite, a midday 35-60% controlled pullback, a session-midpoint invalidation rule, and continuation entry after resumption.

- Not Tier 1 directional baseline: this is a sparse event target, not a broad baseline target over all feature rows.
- Not ORAC v1/v2: it is not keyed to first opening-range acceptance, opening-range high/low acceptance, ORAC event capture, or ORAC rescue diagnostics.
- Not VWAP reclaim/reversion: it does not use VWAP distance, excursion, or reclaim as the event condition.
- Not opening-drive failed-followthrough: it is continuation after a controlled pullback, not reversal after failed opening-drive continuation.
- Not session-compression breakout: it does not use compression boxes or percentile compression thresholds.
- Not late-session range resolution: it is a midday resumption setup, not a session-close range-resolution setup.
- Not volume-pace breakout: it does not require elevated volume pace or a volume-confirmed range break.
- Not a pure draft replay: the user-selected version tightens the draft trend-pullback idea with first-hour state, 35-60% retrace, session-midpoint invalidation, and a 30-minute exit.

## Required Controls

- No-trade baseline.
- Random-entry baseline matched by session, event count, and direction.
- Simple trend baseline.
- Simple mean-reversion baseline.
- Intraday seasonality baseline.
- Duplicate-overlap review against current accepted/stopped ES target families, especially ORAC/opening-range, opening-drive, and trend-direction targets.
- Full trial-log plan before any future model-trust or promotion-facing claim.
- Statistical-validity plan covering PBO, Deflated Sharpe, Probabilistic Sharpe, multiple-testing adjustment, parameter stability, and regime breakdowns before any promotion-facing claim.

## Stop Criteria

Stop before any next phase if any of these occur:

- The candidate cannot be specified causally using only event-time information.
- The first-hour trend, pullback retrace, midpoint invalidation, or resumption rule would require post-event data.
- Material difference against stopped branches cannot be maintained.
- Duplicate overlap exceeds the predeclared cap.
- Event counts or class balance collapse.
- Base-cost or 2x-cost economics are nonpositive.
- Fewer than half of scoped folds are positive.
- Comparable baselines are missing or beat the candidate.
- Registry or trial-ledger evidence conflicts with this intake.

## Forbidden Actions

- Do not mutate `data/**`, `reports/**`, `logs/**`, configs, registry, or trial ledger from this intake.
- Do not implement target construction, edit `TARGET_SPECS`, run source tests, run the wizard, run discovery, run WFA/modeling, run Phase 8, promote, freeze artifacts, paper trade, or live trade from this intake.
- Do not tune thresholds, costs, folds, markets, years, features, labels, pullback percentages, midpoint rules, or session windows after seeing source-test or discovery output.
- Do not reuse stopped branches under a new name.
- Do not stage, commit, or push without separate explicit approval.

## Next Allowed Phase

Only a future bounded source/test conversion plan is approved for consideration. That future plan may propose exact target construction rules, source tests, registry/trial-ledger changes that would be needed later, expected files, stop conditions, and validation.

That future phase must remain plan-only unless the user separately approves implementation. It must not run discovery, WFA/modeling, Phase 8, provider/download, promotion, artifact freeze, final holdout, paper/live, staging, commit, push, registry/trial-ledger mutation, config generation, or generated-report commands.

