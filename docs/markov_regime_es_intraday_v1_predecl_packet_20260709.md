# Markov Regime ES Intraday V1 Predeclaration Packet

Hypothesis ID: `markov_regime_es_intraday_v1`

Status: `DOC_ONLY_PREDECLARATION_READY_NO_EXECUTION`

Evidence date: 2026-07-09

Scope: ES only, 2023/2024 research folds only.

Allowed use: predeclaration evidence review only. This packet does not approve target implementation, feature implementation, registry or trial-ledger mutation, config generation, source-test execution, discovery-run, WFA/modeling, Phase 8 refresh, provider downloads, generated-report commands, cleanup, staging, commit, push, promotion, artifact freeze, final holdout, paper trading, live trading, or HMM work.

## Verified Primary Evidence

- `CODEX_HANDOFF.md` records that current modeling is paused, the current Tier 1 line is closed for alpha evidence, and future modeling must start only as a separate predeclared evidence program with explicit baseline/null/statistical/execution scope.
- `reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/alpha_evidence_gap_matrix.md` reports `verdict=PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE`, `alpha_evidence_ready=False`, and `stability_regime_breakdowns=FAIL` because explicit causal regime evidence is not present.
- `reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/alpha_evidence_completion_closeout.md` reports `verdict=CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE`, `modeling_pause_required=True`, `future_modeling_allowed=False`, and `promotion_allowed=False`.
- `docs/adversarial_current_project_evidence_gate_audit_20260709.md` says proceed status is no for model promotion, artifact freeze, final holdout acceptance, paper/live trading, or treating stopped/frozen/rejected branches as tradable alpha; proceed status is yes only for a separately predeclared evidence program.
- `PROJECT_OUTLINE.md` requires causal regime labels, chronological WFA splits, train-only transforms, matching baselines, null tests, statistical-validity evidence, and regime/structural-break diagnostics before model-trust or promotion claims.
- `manifests/target_hypotheses/registry.json` records recent ES target branches as rejected except `opening_range_acceptance_continuation_30m_v1`, which is `FROZEN` target-smoke readiness evidence only and not a trading approval.

## Evidence Boundary

This packet is a diagnostic evidence-program predeclaration, not a target-hypothesis registration and not a trading strategy.

The Markov regime diagnostic must not be used to rescue the current Tier 1 line, relabel a stopped branch, size current predictions, override the July 9 closeout, or justify paper/live readiness.

No performance claim is established by this packet. Any future claim must be based on separately approved, train-fold-only, out-of-sample evidence with comparable baselines, null checks, and statistical-validity accounting.

## Predeclared Diagnostic Question

Research question: using only causal intraday ES information available at each decision timestamp, do simple three-state Markov regime labels provide stable, out-of-sample evidence about next-state behavior that helps fill the missing causal regime-evidence bucket without creating a new alpha or promotion claim?

Primary diagnostic objective:

- Estimate train-fold-only transition matrices for `bull/up`, `bear/down`, and `sideways` intraday regimes.
- Measure regime stickiness, sparse-state coverage, entropy, stationary distribution, and multi-step convergence behavior.
- Score next-state forecasts on held-out WFA test folds against simple non-Markov baselines.
- Report whether any relationship is stable across folds, sessions, and calendar windows.

## Predeclared Regime Design

Any later implementation plan must preserve these design constraints unless a separate doc-only amendment is approved before execution:

- Market and years: ES only, 2023/2024 research folds only.
- Observation grid: completed 30-minute ES intraday bars or existing ES decision timestamps, chosen before execution.
- State inputs: causal OHLCV-derived returns and volatility available at the state timestamp only.
- Primary state rule: trailing causal return over the prior 60 minutes normalized by train-fold trailing realized volatility.
- `bull/up`: normalized trailing return >= `+1.0`.
- `bear/down`: normalized trailing return <= `-1.0`.
- `sideways`: otherwise.
- Thresholds, warmup handling, session boundaries, NaN policy, and minimum state-count rules must be fixed before scoring any test fold.
- Train-only fitting: regime thresholds and transition matrices may be fit or calibrated only on each WFA train fold.
- Test-fold scoring: test rows may be used only once for out-of-sample scoring and cannot drive threshold, horizon, session-window, cost, or feature changes.

## Transition Diagnostics

Required diagnostics for any later implementation:

- 3x3 train-fold transition matrix for `state_t -> state_t+1`.
- Diagonal stickiness by state and fold.
- Sparse-cell and minimum-count warnings by fold/session segment.
- Transition entropy and stationary distribution.
- Multi-step matrices `P^2`, `P^4`, and `P^8` as diagnostics only.
- Explicit warning if multi-step forecasts converge quickly to the stationary distribution.
- Fold/session/calendar consistency report.

## Baselines And Nulls

Any later implementation must compare against:

- unconditional train-fold next-state base-rate forecast;
- same-state persistence forecast;
- shuffled-label null;
- timing-shift null;
- simple trend baseline under the same split policy;
- simple mean-reversion baseline under the same split policy;
- no-trade / no-position sanity if any PnL-style diagnostic is attached.

If any baseline is missing or not comparable, the result is diagnostic-only and blocked for model-trust use.

## Statistical And Trial Accounting

Required before any model-trust or promotion-facing interpretation:

- append-only trial ledger covering every state definition, lookback, threshold, horizon, session partition, and stopped diagnostic;
- confidence intervals for primary forecast-score deltas;
- PBO or equivalent if multiple variants are compared;
- multiple-testing adjustment covering all compared variants;
- fold/market/year/session/regime stability report;
- explicit `PASS`, `FAIL`, or `NOT_APPLICABLE_WITH_REASON` status for each required statistical-validity item.

Missing statistical evidence is a blocker, not a narrative caveat.

## Threshold Stress Tests

If stress testing is later approved, the only allowed initial grid is:

- lookbacks: `30`, `60`, and `120` minutes;
- normalized thresholds: `0.75`, `1.0`, and `1.25`;
- forecast horizons: one-step primary, with `P^2`, `P^4`, and `P^8` diagnostics only.

Every grid point must be counted in the trial ledger and multiple-testing adjustment. Do not pick a winning threshold after seeing test-fold results.

## Execution Evidence Boundary

No execution evidence is required for a pure next-state forecast diagnostic.

Execution evidence becomes mandatory before any sizing, signal, PnL, strategy, paper, or live interpretation. Required execution evidence would include cost stress, delay stress, spread/slippage, liquidity window, capacity/depth, partial-fill/reject assumptions, and contract-roll execution mapping.

## HMM Deferral

Hidden Markov Model work is explicitly deferred.

Do not implement or plan HMM until the simple three-state Markov diagnostic passes out-of-sample forecast-score comparison, state-count sufficiency, fold/session stability, baseline/null checks, and statistical-validity accounting under a separately approved review.

HMM requires a separate predeclaration packet because latent-state inference adds model-selection, search-space, and overfit risk.

## Stop Conditions

Stop before implementation or execution if:

- the diagnostic cannot be specified using only causal event-time information;
- any threshold, regime label, or transition matrix uses test-fold, holdout, or forward rows for fitting;
- state counts are too sparse for fold-level transition estimates;
- out-of-sample scores fail to beat unconditional and same-state persistence baselines;
- any benefit is isolated to one fold, session segment, or calendar window;
- shuffled-label or timing-shift nulls contradict the claimed evidence;
- any grid search is not included in trial-ledger and multiple-testing accounting;
- any result is used to rescue current Tier 1, ORAC v1, or a rejected branch;
- any step attempts target discovery, WFA/modeling, Phase 8 refresh, provider/download work, generated-report commands, registry/ledger/config/data/log/model mutation, cleanup, staging, commit, push, promotion, artifact freeze, final holdout, paper/live, or HMM work from this packet.

## Next Allowed Step

Plan only a bounded implementation design for `markov_regime_es_intraday_v1`. That future plan may propose exact read-only inputs, output report paths, tests, runtime budget, state-count rules, and validation checks, but must stop before writing code, running diagnostics, generating reports, mutating registry/ledger/config/data/log/model files, or executing WFA/modeling.
