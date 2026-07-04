# Futures Intraday Model Project Outline

## Current Status Note

- `AGENTS.md` is the active operating rulebook for scope, safety, validation, and final-response format.
- This file is the project outline, workflow, and runnable command authority for objective, layout, phase order, phase commands, acceptance standards, and stop conditions.
- `CODEX_HANDOFF.md` is mutable cross-run state. Use it for current blockers, latest decisions, and exact next recommended steps.
- Detailed runnable commands live in this file under `Detailed Pipeline Runbook`; `PIPELINE.md` is a compatibility pointer only.
- This file does not authorize broad data builds, WFA/model runs, provider downloads, cleanup, artifact promotion, live trading, or paper execution by itself.
- If this outline conflicts with `AGENTS.md`, follow `AGENTS.md`. If it conflicts with current repo evidence, reconcile against files, reports, command output, and `git status` before acting.

## Objective

Build a reproducible intraday futures research pipeline using Databento continuous-contract 1-minute OHLCV data.

The project goal is research-process correctness first:

- verify raw data coverage, lineage, and timestamp semantics before modeling;
- construct causal session-normalized datasets without leakage;
- build labels, features, WFA splits, predictions, and evaluation reports in a reproducible sequence;
- treat all alpha/model results as research and walk-forward validation evidence only.

This repository is not live-trading or production-ready by default.

## Research Discipline

- Treat data integrity, provenance, timestamp alignment, and cost assumptions as prerequisites to any model conclusion.
- Do not optimize, tune, expand markets, or revise targets because an observed metric looks favorable.
- Preserve locked holdout and forward profiles. Do not use holdout or forward results for model selection.
- Compare model outputs against simple baselines before accepting complex behavior.
- Record warnings, exclusions, costs, failure modes, validation windows, and generated artifact paths in reports or manifests.
- Treat generated `data/**`, `reports/**`, `models/**`, `outputs/**`, `logs/**`, and cache outputs as local artifacts unless explicitly approved for tracking.

## Source Of Truth Roles

- `AGENTS.md`: durable agent rules, safety policy, protected contracts, bounded-command gate, output format.
- `PROJECT_OUTLINE.md`: project objective, layout, phase workflow, detailed runnable commands, acceptance standards, and stop conditions.
- `CODEX_HANDOFF.md`: current state and continuation state for multi-step Codex work.
- `PIPELINE.md`: compatibility pointer for older references; do not add parallel phase checklists or runnable command catalogs there.
- `README.md`: setup and orientation.
- `configs/alpha_tiered.yaml`: profile ladder, markets, years, and research/holdout/forward profile definitions.
- `configs/*.yaml`: market sessions, costs, data manifest, model settings, and audit configuration.
- `manifests/**`: small durable metadata such as frozen feature sets and hypothesis registries.

## Active Layout

Primary code and metadata areas:

```text
configs/                       configuration and profile definitions
docs/                          durable documentation and audit notes
live_ops/                      live/paper-operation scaffolding; not research proof
manifests/                     small tracked rebuild/audit metadata
scripts/phase1A_download/      Databento DBN archive download planning/execution
scripts/phase1B_convert/       DBN to raw parquet conversion
scripts/phase1C_validate/      raw DBN/raw parquet readiness checks
scripts/phase2_causal_base/    causal/session-normalized base data builders
scripts/phase3_labels/         label and target construction
scripts/phase4_features/       baseline feature matrix builders
scripts/phase5_wfa/            WFA split builders
scripts/phase6_wfa/            WFA training and OOS prediction wrappers
scripts/phase7_wfa/            legacy WFA implementation package used by Phase 6
scripts/phase8_model_selection/ prediction evaluation and model-selection audits
scripts/phase9_research/       bounded research and robustness harnesses
scripts/validation/            audit, readiness, repair-planning, and proof utilities
scripts/final_holdout/         holdout guard utilities
tests/                         focused unit and validation tests
```

Ignored or generated local areas include:

```text
data/
reports/
models/
outputs/
logs/
cache/
artifacts/
```

Some generated artifacts may already be tracked from older history. Treat them as existing user work and do not refresh, delete, stage, or commit them without explicit approval.

## Profile Ladder

Profiles are defined in `configs/alpha_tiered.yaml`.

- `tier_0`: smoke only, never alpha evidence.
- `tier_1_research`: core research over ES, CL, ZN, and 6E for recent research years.
- `tier_1_holdout`: locked core holdout.
- `tier_1_forward`: locked core forward/current-year validation.
- `tier_2_research`: broader balanced-market robustness research.
- `tier_2_holdout` and `tier_2_forward`: locked broader validation.
- `tier_3_research`: full-universe long-history stress research.
- `tier_3_holdout` and `tier_3_forward`: locked full-universe validation.
- `all_raw`: inventory only, not research evidence.

Do not promote a broader profile, refresh canonical artifacts, or use locked profiles for tuning without explicit approval.

## Phase Workflow

This section is the authoritative workflow map. Detailed phase commands live in `Detailed Pipeline Runbook` below and still require approved bounded plans when broad, expensive, or mutating.

| Phase | Purpose | Main implementation area | Main output class |
| --- | --- | --- | --- |
| 1A | Download immutable Databento DBN/ZST archives | `scripts.phase1A_download.download_databento_raw` | `data/dbn/.../*.dbn.zst` |
| 1B | Convert DBN archives to raw parquet while preserving raw event semantics | `scripts.phase1B_convert.convert_databento_raw` | `data/raw/{market}/{year}.parquet` |
| 1C | Audit raw DBN/raw parquet coverage, schema, and alignment | `scripts.phase1C_validate.audit_raw_dbn_alignment` | `reports/raw_ingest/*` |
| 2 | Build causal base data with session normalization and synthetic/degraded row diagnostics | `scripts.phase2_causal_base.build_causal_base_data` | `data/causally_gated_normalized/{market}/{year}.parquet` |
| 3 | Build labels/targets with explicit entry lag and horizon semantics | `scripts.phase3_labels.build_labels` | `data/labeled/{market}/{year}.parquet` |
| 4 | Build baseline feature matrices from causal inputs only | `scripts.phase4_features.build_baseline_features` | `data/feature_matrices/baseline/{market}/{year}.parquet` |
| 5 | Build chronological WFA split plans with purge/embargo rules | `scripts.phase5_wfa.build_wfa_splits` | `reports/wfa/split_plan.json` |
| Support | Maintain legacy WFA implementation package consumed by Phase 6; not a downstream runnable phase | `scripts.phase7_wfa.*` | support code and combined predictions |
| 6 | Train WFA models and write out-of-sample predictions | `scripts.phase6_wfa.run_wfa` | `data/predictions/{run}/oos_predictions.parquet` |
| 8 | Evaluate predictions, costs, policy alignment, and promotion readiness | `scripts.phase8_model_selection.*` | `reports/phase8/*` |
| 9 | Run bounded research harnesses and adversarial audits | `scripts.phase9_research.*` | `reports/pipeline_audit/*` or focused reports |
| 10 | Guard locked holdout/forward evaluation | `scripts.final_holdout.guard_final_holdout` | holdout approval/block evidence |
| 11 | Freeze approved research artifacts only after explicit approval | `scripts.artifact_freeze.freeze_research_artifacts` | frozen artifact metadata |

`scripts.phase7_wfa` is support code for Phase 6, not a numbered downstream
pipeline phase. Changes to that package must be validated before Phase 6 runs
consume it.

## Non-Negotiable Data Rules

- Raw Databento DBN/ZST archives are immutable source artifacts.
- Phase 1 preserves raw event timestamp semantics.
- Phase 2 is the first phase allowed to session-normalize, mark synthetic/degraded rows, and convert into causal modeling inputs.
- Do not fill missing 1-minute bars before the causal base phase.
- Sparse trade-derived OHLCV markets require explicit no-trade and roll-window handling.
- Every research result must be traceable back to source data, config, profile, and report/manifest evidence.

## Label, Feature, And WFA Rules

- Labels must use only information available after the configured entry lag and within the configured horizon.
- Features must use data available through the feature timestamp only.
- Feature promotion requires an audit record for source, availability timestamp,
  update frequency, as-of join behavior, lookback, NaN/warmup handling,
  economic rationale, leakage risk, train-only transform status, and drift/decay
  checks.
- WFA splits must be chronological, never shuffled.
- Train-only transforms must be fit only on training folds.
- Purge/embargo rules must prevent horizon overlap.
- Holdout and forward profiles are evaluation-only and cannot drive parameter selection, feature selection, target changes, market selection, or cost changes.

## Evaluation Standard

Before trusting model or WFA results, verify:

- raw data coverage and missing-bar handling;
- instrument metadata, tick size, point value, roll logic, and session boundaries;
- target construction, timestamp alignment, feature windows, and NaN handling;
- WFA split boundaries, purge/embargo, and locked validation windows;
- commission, fees, spread, slippage, delay, capacity, and contract multiplier assumptions;
- simple baseline comparisons;
- model-risk controls, including hyperparameter budget, seed policy,
  calibration, class imbalance handling, regularization, and feature-importance
  stability;
- statistical-validity checks, including PBO, Deflated Sharpe, Probabilistic
  Sharpe, bootstrap confidence intervals, multiple-testing adjustment,
  parameter stability, and regime breakdowns;
- result manifests and reports recording config, data scope, validation windows, costs, warnings, and failure modes;
- no post-test retuning or cherry-picked metric is used as acceptance evidence.

## Mandatory Gates Before Model Trust

The following gates are required before any model, WFA, policy, promotion, or
artifact-freeze result can be treated as trust evidence. A phase name or
successful command exit is not sufficient; each gate must have explicit inputs,
outputs, acceptance checks, stop conditions, and downstream blockers recorded in
its manifest or report evidence.

### Raw Data And Metadata Gate

Placement: after Phase 1A/1B archive and raw-parquet preparation, before Phase 2
causal/session normalization.

Required inputs:

- immutable Databento OHLCV, definition, and required metadata DBN/ZST archives;
- raw parquet candidates with preserved raw event timestamps;
- exchange, dataset, schema, symbol mapping, and point-in-time instrument
  identity evidence;
- contract metadata for tick size, point value, multiplier, expiry, first
  notice, last trade, and roll eligibility;
- session, timezone, DST, holiday, early-close, and session-break definitions;
- roll/continuous-contract policy, including roll trigger and adjustment method;
- universe-construction record for selected markets and profiles, including
  inclusion/exclusion criteria, point-in-time availability, survivorship-bias
  review, selection-bias review, and rejected candidate markets;
- vendor caveat, correction, data-availability, and coverage notes.

Required outputs:

- raw DBN/archive manifest with path, schema, date span, size, hash, and provider
  provenance;
- raw parquet manifest with row counts, timestamp bounds, instrument coverage,
  definition coverage, and source hashes;
- metadata coverage report for every selected market-year and instrument id;
- universe and survivorship-bias report linking selected and rejected markets,
  profiles, and market-years to predeclared inclusion criteria and
  point-in-time data-availability evidence;
- missing-bar, duplicate, outlier, stale-quote, bad-tick, and correction report;
- explicit roll-window and continuous-contract suitability notes for downstream
  labels, features, and PnL.

Acceptance checks:

- every selected market-year has matching immutable source archives or is
  explicitly blocked;
- every OHLCV row has valid point-in-time instrument identity and required
  definition metadata;
- tick size, point value, multiplier, session, timezone, roll, and expiry
  metadata are non-null and consistent with the selected profile;
- selected markets, profiles, and market-years are justified by predeclared
  inclusion criteria rather than post-hoc performance, convenience exclusions,
  survivorship, or observed downstream data quality;
- raw timestamps preserve provider event semantics before Phase 2;
- continuous-contract adjusted prices are approved for research labels/features
  and are not treated as directly executable contract prices;
- coverage gaps, duplicate bars, outliers, stale quotes, and vendor corrections
  are either resolved or promoted as explicit downstream blockers.

Stop conditions:

- missing, stale, or mismatched source archive, hash, schema, or provider
  provenance;
- missing or nonpositive tick size, point value, multiplier, or contract
  identity fields;
- unresolved expiry, first-notice, last-trade, roll, or session metadata for a
  selected market-year;
- selected universe, profile, market, or market-year depends on post-hoc
  performance, convenience exclusions, survivorship, or unresolved
  selection-bias evidence;
- roll-adjustment method is unknown or unsuitable for the target being tested;
- data availability timestamps are missing where point-in-time use is required;
- raw coverage or quality failures would require silent fills or undocumented
  exclusions.

Downstream blockers:

- Phase 2 cannot consume market-years that fail this gate;
- Phase 3 labels cannot use market-years with unresolved roll/session or
  point-in-time metadata;
- Phase 4 features cannot promote raw metadata fields without a separate
  leakage-safe feature audit;
- Phase 5, Phase 6, and Phase 8 validation, model, and promotion claims cannot
  use markets or profiles without passed universe-construction and
  selection-bias evidence;
- Phase 8 PnL cannot be trusted until tick value, multiplier, costs, and
  executable-contract caveats are reconciled.

### Cleaning And Normalization Gate

Placement: after Raw Data And Metadata Gate evidence passes for selected
market-years, before Phase 3 labels or any feature, split, model, metrics, or
promotion work can consume derived data.

Required inputs:

- raw parquet artifacts and raw DBN/archive manifests that passed the Raw Data
  And Metadata Gate;
- deterministic cleaning and normalization specification, including timestamp
  column mapping, sort/deduplication rules, bad-bar handling, gap handling,
  synthetic-row policy, degraded-row policy, and rejected-row policy;
- session, timezone, DST, holiday, early-close, session-break, and roll-window
  configuration used by Phase 2;
- explicit statement that raw event timestamps, prices, and provider fields are
  not rewritten outside the documented Phase 2 transformations;
- causal feature-availability policy proving normalization uses only
  information available at or before each output row timestamp;
- selected market-year scope, profile, config hashes, input hashes, and expected
  output roots.

Required outputs:

- causal base parquet artifacts and manifest by market-year with input hashes,
  output hashes, row counts, timestamp bounds, selected scope, profile, and
  config provenance;
- before/after row-count reconciliation for raw rows, retained rows, rejected
  rows, synthetic rows, degraded rows, duplicate rows, bad bars, gap rows, and
  roll-window rows;
- rejected-row and excluded-window log with reason codes, affected timestamps,
  market-year, and source artifact reference;
- session-normalization report covering session ids, session boundaries,
  timezone/DST handling, holidays, early closes, and session breaks;
- derived-artifact version record proving output path, schema, config, and
  source hashes are reproducible and not stale.

Acceptance checks:

- every derived row is traceable to immutable raw inputs, documented synthetic
  construction, or an explicit rejected/excluded reason;
- cleaning and normalization rules are deterministic and profile/config driven,
  with no ad hoc market-year exceptions outside recorded accepted warnings;
- duplicate, bad-bar, missing-bar, stale, synthetic, degraded, and roll-window
  handling is counted before and after transformation;
- session normalization, timestamp alignment, and roll-window marking use no
  future bars or information unavailable at the output timestamp;
- rejected-row logs and row-count reconciliation match the output parquet and
  manifest for every selected market-year;
- output manifests record exact input selection, source hashes, output hashes,
  row counts, warnings, failures, and zero unclassified transformations.

Stop conditions:

- missing or stale raw manifest, source hash, config hash, output hash, or
  market-year scope evidence;
- any undocumented row deletion, row insertion, fill, timestamp rewrite, price
  rewrite, or schema change;
- cleaning or normalization rule depends on future bars, full-sample statistics,
  final-holdout evidence, or post-test decisions;
- rejected rows, synthetic rows, degraded rows, duplicate rows, bad bars, or
  gap rows cannot be reconciled to explicit counts and reason codes;
- session, timezone, holiday, early-close, session-break, or roll-window
  behavior is missing, inconsistent, or uses a fallback calendar silently;
- derived artifacts are stale, overwritten without approval, or not reproducible
  from the recorded inputs and configs.

Downstream blockers:

- Phase 3 cannot build labels until the causal base manifest is exact-scope PASS
  or explicitly accepted WARN with documented limitations;
- Phase 4 cannot build features from market-years with unreconciled row counts,
  rejected rows, synthetic/degraded handling, or session-normalization blockers;
- Phase 5 cannot build splits until derived-data scope, row counts, and warning
  status are stable and recorded;
- Phase 6 and Phase 8 cannot treat any output as model-trust evidence if this
  gate is missing, stale, failing, or bypassed;
- artifact freeze cannot include derived-data lineage claims without this gate.

### Label And Target Gate

Placement: after Phase 2 causal base evidence, before Phase 4 feature matrices
or any WFA split generation.

Required inputs:

- Phase 2 causal base manifest and validation evidence for selected
  market-years;
- target formula and target column definitions;
- prediction timestamp, feature cutoff timestamp, entry timestamp, exit
  timestamp, configured entry lag, and horizon;
- same-session, roll-window, holiday, early-close, session-boundary, and
  missing-bar rules;
- configured costs required for cost-aware target validity flags;
- label invalidation rules for insufficient horizon, stale data, bad bars,
  synthetic/degraded rows, and roll/session conflicts.

Required outputs:

- label parquet artifacts and label manifest by market-year;
- label report with row counts, selected scope, input hashes, target columns,
  invalid-label counts, class/target distributions, and edge-case counts;
- timing diagram or equivalent manifest fields proving prediction, entry, and
  exit timestamps are ordered correctly;
- overlap-leakage, horizon, and session-validity diagnostics;
- downstream target/excluded-column registry evidence.

Acceptance checks:

- target construction uses only rows after the prediction timestamp and within
  the declared horizon;
- features available at the prediction timestamp cannot include the future label
  interval;
- entry lag, exit timestamp, and target horizon are explicit and match config;
- labels do not cross invalid sessions, holidays, early closes, roll windows, or
  missing-bar boundaries unless an explicit rule allows it;
- label distributions, flat/invalid classes, and edge cases are reported by
  market-year;
- label manifests record input selection, source hashes, output hashes, row
  counts, and zero failures.

Stop conditions:

- missing target formula or ambiguous prediction, entry, or exit timestamp;
- any feature or preprocessing step can see future bars used by the label;
- overlap leakage is possible without purge/embargo coverage downstream;
- invalid session, roll, holiday, early-close, or missing-bar labels are allowed
  silently;
- target, label, or forward-return columns can enter feature registries;
- label distribution collapses or class balance is outside predeclared limits
  without an explicit stop/research decision.

Downstream blockers:

- Phase 4 cannot build features until the label manifest is exact-scope PASS or
  explicitly accepted WARN with documented limitations;
- Phase 5 cannot build splits until label horizon and overlap rules are known;
- Phase 6 cannot train if target columns, forward returns, or invalid-label
  flags can leak into features;
- Phase 8 cannot compare policies if target semantics changed after validation
  or locked OOS review.

### Backtest And Cost Gate

Placement: after Phase 6 OOS predictions and before Phase 8 promotion or policy
acceptance. For diagnostics that score predictions inside Phase 8, this gate is
the hard boundary between structural metrics and believable PnL.

Required inputs:

- OOS predictions, prediction manifest, split-plan provenance, and feature/label
  provenance;
- contract metadata for tick size, point value, multiplier, and tradable
  contract caveats;
- commissions, exchange fees, clearing/NFA fees where applicable, spread,
  slippage, delay, and fill-assumption policy;
- position sizing, contract sizing, turnover, liquidity, capacity, and market
  impact assumptions;
- signal timestamp, order timestamp, fill timestamp, and rejected/partial-fill
  handling for research simulation;
- profile-specific cost policy and any provisional-cost flags.

Required outputs:

- costed metrics report with gross/net PnL, cost drag, turnover, trade count,
  active rows, and market/fold/year breakdowns;
- execution-assumption report covering delay, fill price, spread/slippage,
  partial fills, rejections, and capacity limits;
- contract-sizing report tying signal units to point value, multiplier, and
  realistic contract counts;
- blocker report separating structural prediction quality from costed policy
  acceptance;
- promotion decision that records cost assumptions and whether costs are final
  or provisional.

Acceptance checks:

- every PnL value uses explicit tick value, point value, multiplier, commission,
  fee, spread, slippage, and delay assumptions;
- cost model is applied consistently by market, fold, year, side, and turnover;
- fill assumptions are no better than signal-time availability permits;
- market impact, liquidity, and capacity limits are reported or explicitly
  block promotion;
- gross and net results, cost drag, and turnover are reported separately;
- cost or execution assumptions are not changed after locked OOS review to
  rescue a result.

Stop conditions:

- missing or provisional costs under a strict research/profile setting;
- missing contract multiplier, point value, tick size, or contract-sizing rule;
- fill, delay, slippage, spread, partial-fill, or rejection assumptions are
  undocumented;
- net results depend on unrealistic zero-cost, same-bar, or perfect-fill
  assumptions;
- capacity/liquidity/impact assumptions are absent for a strategy that would
  trade size or illiquid windows;
- post-test cost, threshold, sizing, or execution-rule retuning is detected.

Downstream blockers:

- Phase 8 cannot mark research alpha ready if this gate is missing or failing;
- artifact freeze cannot include PnL claims without passing cost evidence;
- portfolio/risk review cannot proceed without realistic sizing, turnover, and
  max-exposure inputs;
- live/paper readiness remains deferred even if this research cost gate passes,
  because continuous-contract artifacts are not directly executable.

### Portfolio And Risk Gate

Placement: after costed OOS policy evaluation and before statistical-validity
acceptance, promotion readiness, or artifact freeze. This gate decides whether a
costed policy has portfolio-level risk evidence, not whether it is executable
live.

Required inputs:

- costed OOS trade/policy rows with signal, side, size, timestamp, market, fold,
  year, and regime labels;
- contract metadata, point value, multiplier, margin, and currency assumptions
  used to convert signals into portfolio exposure;
- position-sizing, capital-base, leverage, volatility-targeting, rebalancing,
  and capital-allocation rules;
- per-market, cross-market, sector/asset-class, concentration, and correlation
  constraints;
- drawdown, stop-loss, max-loss, kill-switch, stale-data, stale-signal, and
  risk-off rules for research portfolio/risk evidence;
- turnover, liquidity, capacity, and stress-scenario inputs from the cost and
  execution evidence.

Required outputs:

- portfolio exposure report with gross/net exposure, leverage, margin use,
  position counts, concentration, and market/fold/year/regime breakdowns;
- drawdown and loss report with max drawdown, run-up/run-down, tail loss,
  stop/kill-switch breaches, and recovery-time diagnostics;
- volatility, correlation, beta/proxy exposure, regime, and stress-test report;
- capacity and liquidity-risk report tying turnover, contract counts, and
  market impact assumptions to proposed capital;
- portfolio/risk decision recording whether sizing and risk limits are approved,
  provisional, or blocked.

Acceptance checks:

- every portfolio metric is computed from locked OOS rows and the same cost,
  execution, and contract-sizing assumptions used by the Backtest And Cost Gate;
- position sizing, leverage, margin use, and capital allocation are deterministic
  and predeclared before locked OOS review;
- exposure, concentration, correlation, drawdown, tail-loss, and stress results
  are reported by market, fold, year, and regime;
- risk limits, kill-switches, max-loss rules, and capacity limits have explicit
  pass/fail evidence rather than narrative approval;
- stale-data guard evidence proves portfolio/risk metrics exclude, block, or
  explicitly flag stale input rows before sizing, exposure, drawdown, or
  risk-limit claims are accepted;
- portfolio aggregation does not diversify away missing or failing market-level
  cost, execution, liquidity, or statistical evidence;
- no sizing, allocation, threshold, or risk-limit rule is changed after locked
  OOS review to rescue a result.

Stop conditions:

- missing capital base, sizing rule, leverage cap, margin assumption, or
  contract-count conversion;
- missing or failing drawdown, tail-loss, concentration, correlation, capacity,
  liquidity, or stress evidence;
- missing or failing stale-data guard evidence for costed OOS policy rows,
  sizing inputs, exposure calculations, or drawdown/risk-limit evidence;
- portfolio pass depends on markets, folds, years, regimes, or stopped branches
  excluded after results were observed;
- aggregate performance hides a market-level, regime-level, cost, or execution
  failure that remains unresolved;
- post-test retuning of sizing, allocation, thresholds, stops, or risk limits is
  detected;
- risk controls are documented only for live/paper scaffolding and not proven on
  the research evidence being promoted.

Downstream blockers:

- statistical-validity review cannot claim portfolio-level credibility until
  this gate passes or explicitly blocks portfolio aggregation;
- Phase 8 promotion readiness must fail if sizing, exposure, drawdown, capacity,
  or risk-limit evidence is missing or failing;
- artifact freeze cannot include portfolio, capital efficiency, drawdown, or
  risk-adjusted claims without this gate;
- production/paper readiness remains deferred even if this gate passes, because
  execution mapping, monitoring, broker controls, and operational kill switches
  require a separate approved gate.

### Statistical Validity Gate

Placement: after costed OOS evaluation and before promotion readiness,
artifact freeze, or any claim that model results are statistically credible.

Required inputs:

- locked OOS predictions and costed metrics by fold, market, year, and regime;
- complete list of tested targets, feature families, model families,
  thresholds, cost assumptions, market scopes, and stopped branches;
- predeclared primary metrics, secondary diagnostics, stop rules, and promotion
  thresholds;
- random seed policy, hyperparameter budget, and parameter/search space records;
- benchmark and baseline results;
- regime labels or volatility/trend/liquidity partitions used for robustness
  checks.
- concept-drift diagnostic plan, or an explicit mapping that explains how
  regime and structural-break diagnostics cover concept-drift risk.

Required outputs:

- bootstrap or walk-forward confidence intervals for primary metrics;
- Probabilistic Sharpe Ratio and Deflated Sharpe Ratio, or explicit
  non-applicability reasons plus substitute evidence;
- PBO or equivalent overfit diagnostic for variant/search processes;
- multiple-testing adjustment covering tried targets, features, models,
  thresholds, markets, and policy variants;
- parameter stability, feature stability, and fold/market/year consistency
  report;
- regime breakdown, structural-break, and concept-drift diagnostics;
- final statistical-validity decision separate from structural pass and alpha
  promotion.

Acceptance checks:

- statistical tests use only locked OOS evidence appropriate for the decision;
- every tested variant and stopped branch is included in multiple-testing or
  overfit accounting;
- confidence intervals and Sharpe-like diagnostics support the same conclusion
  as the point estimate;
- parameters, thresholds, feature importance, and market/fold contributions are
  stable enough under predeclared criteria;
- regime and structural-break diagnostics do not show alpha concentrated in one
  fragile window without an explicit blocker;
- concept-drift diagnostics do not show unstable target/feature/performance
  relationships across locked OOS folds, regimes, or calendar windows without an
  explicit blocker;
- non-applicable tests include a documented reason and substitute evidence
  required before promotion.

Stop conditions:

- PBO, Deflated Sharpe, Probabilistic Sharpe, confidence intervals,
  multiple-testing adjustment, parameter stability, or regime evidence is
  missing without an approved non-applicability reason;
- significance depends on cherry-picked folds, markets, thresholds, or stopped
  branches;
- locked OOS or holdout results were used to retune targets, features, costs,
  thresholds, or model choices;
- parameter instability, feature instability, regime concentration, or
  structural breaks breach predeclared thresholds;
- concept-drift evidence is missing, uses non-locked evidence for the promotion
  decision, or breaches predeclared stability thresholds;
- benchmark/simple-baseline comparison is missing or contradicts the promotion
  claim.

Downstream blockers:

- Phase 8 promotion readiness must fail closed when statistical-validity
  evidence is missing, stale, not applicable without substitute evidence, or
  fails thresholds;
- Phase 9 research harness wins remain feasibility evidence only until this
  gate passes on an eligible validation design;
- artifact freeze cannot include alpha, model-trust, or stable-relationship
  claims without this gate;
- production/paper readiness remains deferred regardless of statistical pass
  until execution and monitoring gates are separately approved.

## Bounded Execution Policy

Any command that can download provider data, mutate `data/**` or `reports/**`, build broad artifacts, run WFA/modeling, produce predictions, promote data, freeze artifacts, or touch live/paper operations requires a bounded approval plan first.

The plan must specify:

- exact command family;
- maximum scope such as markets, years, rows, chunks, files, or profiles;
- timeout or stopping budget;
- output report/log path;
- forbidden command patterns;
- expected generated artifacts and tracking status;
- stop condition and required evidence before continuing.

If those fields are missing, do not run the command.

## Production Deferral Gate

This repository must not make live-trading or paper-trading readiness claims
from continuous-contract research artifacts alone.

Live/paper claims remain deferred until a separate approved gate defines and
verifies:

- contract-specific execution mapping from continuous symbols to tradable
  instruments;
- order generation, fill assumptions, partial fills, rejected orders, and broker
  failure handling;
- latency, stale-data guards, market-hours/session guards, and retry behavior;
- position limits, risk limits, max-loss handling, kill switches, and drawdown
  response;
- research-production mismatch checks between continuous-contract research
  artifacts and executable contract-specific paper/live inputs;
- training-serving skew checks covering future feature generation, timestamp
  availability, configs, model versions, and data transformations;
- prediction drift monitoring for future paper/live predictions, including
  distribution, calibration, confidence, missing/stale prediction, and
  regime-coverage alerts;
- monitoring, logging, alerting, rollback, and post-trade reconciliation.

Until that gate exists and passes, `live_ops/` content is scaffolding only and
must not be treated as research proof, production readiness, or permission to
trade.

## Detailed Pipeline Runbook

This runbook mixes general phase command patterns with explicitly bounded
candidate-specific workflow gates, such as ES 2026 notes. Candidate-specific
notes are scoped workflow state only; they are not general pipeline
requirements, approvals, or model-trust evidence unless reconciled against
current primary artifacts, manifests, command output, and a bounded approval.

Run commands from the repo root:

```powershell
cd C:\Users\donny\Desktop\futures_intraday_model
```

### 1A. Download DBN Archives

Purpose: archive immutable Databento DBN/ZST chunks. This phase downloads
source archives only; it does not create canonical raw parquet.

Command pattern:

```powershell
python -m scripts.phase1A_download.download_databento_raw --universe extended_cme --start-year 2010 --end-year 2026 --end-date 2026-06-10 --schema all --mode download-dbn --raw-format dbn-zstd --chunk year --workers 4 --resume
```

Smoke pattern before large runs:

```powershell
python -m scripts.phase1A_download.download_databento_raw --symbols ES --start 2026-01-01 --end 2026-01-03 --schema all --mode download-dbn --raw-format dbn-zstd --chunk year --workers 1 --resume --dry-run
```

Inputs:

- Databento API key from environment or local secret handling.
- Requested universe, dates, and schemas.

Outputs:

- OHLCV DBN: `data/dbn/ohlcv_1m/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst`
- Definition DBN: `data/dbn/definition/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst`
- Reports under `reports/raw_ingest/`, including DBN manifests.

Acceptance checks:

- `schema=all` produced both OHLCV and definition outputs.
- Sidecar manifests exist and match file path, size, hash, dataset, schema, and
  year range.
- No unexpected overwrite occurred.

Stop conditions:

- A market-year is missing from the current coverage audit after a supposedly
  successful run.
- A batch times out.
- A manifest hash/path/schema mismatch appears.
- The command would require broad `--overwrite` without an explicit audit reason.

### 1B. Convert DBN To Raw Parquet

Purpose: validate DBN chunks plus definition metadata and stitch them into one
OHLCV 1-minute grained raw market-year parquet dataset. Definition, status, and
statistics records are joined onto OHLCV rows as metadata/enrichment columns;
Phase 1B does not create separate parquet datasets for each DBN schema.

Command:

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --dbn-root data\dbn\ohlcv_1m --raw-root data\raw
```

Staged optional enrichment candidate:

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols ES,CL,ZN,6E --dbn-root data\dbn\ohlcv_1m --raw-root data\raw_enriched_candidate --reports-root reports\raw_ingest\raw_enriched_candidate_tier1 --include-optional-schemas status,statistics --optional-dbn-root data\dbn
```

Inputs:

- `data/dbn/ohlcv_1m/...`
- `data/dbn/definition/...`
- Optional staged enrichment inputs: `data/dbn/status/...` and
  `data/dbn/statistics/...`

Outputs:

- `data/raw/{market}/{year}.parquet`
- Optional staged candidate only: `data/raw_enriched_candidate/{market}/{year}.parquet`
- Raw parquet manifests under `reports/raw_ingest/`.

Acceptance checks:

- Required OHLCV schema is present.
- Definition-derived fields are present, including `raw_symbol` and `tick_size`.
- Raw rows preserve `ts_event`.
- No missing definition coverage for any OHLCV `instrument_id`.
- Optional status/statistics enrichment preserves OHLCV 1-minute grain: one row
  per OHLCV bar. Optional records are causal as-of joined by `instrument_id` and
  `ts_event`; they never define additional rows.
- Optional status/statistics enrichment is raw metadata/audit context until a
  separate leakage-safe feature-hypothesis change promotes any field to features.
- Optional enrichment is staged in `data/raw_enriched_candidate` first. Promotion
  into canonical `data/raw` requires a separate explicit approval after row-count
  and schema validation against the trusted baseline.

Stop conditions:

- Missing definition DBN for a market-year.
- Any null or nonpositive tick-size metadata.
- Missing manifest, hash mismatch, or raw schema mismatch.

### 1C. Raw Readiness Gate

Purpose: verify that canonical `data/raw` is complete, schema-valid,
DBN-derived, definition-enriched, and aligned to the current local DBN archive
before Phase 2 consumes it.

Command:

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config configs/alpha_tiered.yaml --profile tier_3 --dbn-root data\dbn --raw-root data\raw --json-out reports\raw_ingest\raw_dbn_alignment.json --md-out reports\raw_ingest\raw_dbn_alignment.md
```

Optional enrichment audit:

```powershell
python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn --schema ohlcv-1m --schema definition --schema status --schema statistics --optional-schema status --report-out reports\raw_readiness\dbn_four_schema_coverage_tier3_research_optional_status.json
python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_holdout --dbn-root data\dbn --schema ohlcv-1m --schema definition --schema status --schema statistics --optional-schema status --report-out reports\raw_readiness\dbn_four_schema_coverage_tier3_holdout_optional_status.json
python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_forward --dbn-root data\dbn --schema ohlcv-1m --schema definition --schema status --schema statistics --optional-schema status --end-date 2026-06-13 --report-out reports\raw_readiness\dbn_four_schema_coverage_tier3_forward_partial.json
python -m scripts.validation.audit_enriched_raw_optional_schemas --raw-root data\raw --dbn-root data\dbn --json-out reports\raw_readiness\raw_enriched_optional_schema_audit.json --md-out reports\raw_readiness\raw_enriched_optional_schema_audit.md
```

`status` is optional metadata in these checks; missing status archives/manifests
must remain visible as optional gaps. Forward 2026 coverage is bounded to the
known local archive horizon, `2026-06-13`, not a full-year archive expectation.

Candidate comparison commands:

```powershell
python -m scripts.validation.triage_raw_dbn_alignment compare-candidate --alignment-json reports\raw_ingest\raw_dbn_alignment.json --base-root data\raw --candidate-root data\raw_alignment_candidate_2026 --dbn-root data\dbn --key-source source_hash --json-out reports\raw_ingest\raw_alignment_2026_candidate_compare.json --md-out reports\raw_ingest\raw_alignment_2026_candidate_compare.md
python -m scripts.validation.triage_raw_dbn_alignment compare-candidate --alignment-json reports\raw_ingest\raw_dbn_alignment.json --base-root data\raw --candidate-root data\raw_alignment_candidate_definition_fix --dbn-root data\dbn --key-source definition --json-out reports\raw_ingest\raw_alignment_definition_candidate_compare.json --md-out reports\raw_ingest\raw_alignment_definition_candidate_compare.md
python -m scripts.validation.triage_raw_dbn_alignment promotion-manifest --alignment-json reports\raw_ingest\raw_dbn_alignment.json --raw-root data\raw --candidate-2026-root data\raw_alignment_candidate_2026 --definition-candidate-root data\raw_alignment_candidate_definition_fix --missing-candidate-root data\raw_alignment_candidate_missing_fill --json-out reports\raw_ingest\raw_alignment_promotion_manifest.json --md-out reports\raw_ingest\raw_alignment_promotion_manifest.md
```

Acceptance checks:

- Raw parquet schema/value checks pass.
- OHLCV and definition DBN sidecar manifests pass.
- No raw parquet exists without matching local DBN provenance.
- Missing canonical raw market-years are reported as Phase 1B conversion
  candidates, not silently ignored.
- Staged candidates are compared against canonical `data/raw` before any
  promotion decision.
- Optional status/statistics audit separates core OHLCV/definition readiness
  from optional-enrichment readiness and alpha-input caveats.

Streamlining policy:

- Keep Phase 1A and Phase 1B separate so immutable DBN provenance remains
  auditable.
- Do not run Phase 2 before Phase 1B and the raw readiness gate.
- Use Phase 1C as the single user-facing raw-data readiness check instead of
  folding causal/session validation into Phase 1B.

### 2. Build Causal Base

Purpose: re-check raw bar invariants, normalize sessions, identify roll windows, mark
synthetic rows, and causally gate data.

Command:

```powershell
python -m scripts.phase2_causal_base.build_causal_base_data --profile tier_1
```

Inputs:

- `data/raw/{market}/{year}.parquet`
- Local audit DBN archives:
  - `data/dbn/ohlcv_1m/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst`
  - `data/dbn/definition/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst`
  - `data/dbn/trades/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst`
- `configs/alpha_tiered.yaml`
- `configs/market_sessions.yaml`

Outputs:

- `data/causally_gated_normalized/{market}/{year}.parquet`
- `reports/causal_base/`
  - `local_trade_ohlcv_gap_crosscheck_2025_2026.json`
  - `local_trade_ohlcv_gap_crosscheck_2025_2026.md`

Bounded split recovery helper:

```powershell
python -m scripts.validation.run_local_trade_ohlcv_split --market HO --year 2026 --shard-index 4 --causal-root data\causal_proof_candidates\local_trade_2025_2026_v1 --max-shards 1 --max-gap-windows 10000 --max-trade-rows-scanned 200000000 --max-archives-read 2 --max-runtime-seconds 900
```

- Writes per-shard reports under
  `reports/pipeline_audit/local_trade_shards_20250618_20260613/{market}_{year}_split_v1/`.
- Defaults to one executable shard, skips existing `PASS` JSON reports, and stops
  on the first non-`PASS` shard or protected existing non-`PASS` report.
- Use `--dry-run` to inspect the planned shard command without running the
  underlying proof scan. Use `--rerun-existing` only with explicit approval.

Proof-status promotion gate:

```powershell
python -m scripts.validation.promote_local_trade_proof_status --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json
```

- Consumes the reviewed local-trade proof-status promotion proposal and promotes
  only proof-status rows that are backed by PASS source evidence.
- Defaults to console-only output. Optional `--json-out` and `--markdown-out`
  must be provided together and must stay under `reports/` as generated review
  artifacts.
- Does not promote candidate causal data to canonical data, stage generated
  artifacts, approve modeling, approve WFA, approve metrics/predictions, or
  approve live/paper execution.

Model-eligible scope gate:

```powershell
python -m scripts.validation.build_local_trade_model_eligible_scope --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json
```

- Consumes the promoted proof-status rows and separates model-eligible markets
  from uncovered canonical markets.
- Defaults to console-only output. Optional `--json-out` and `--markdown-out`
  must be provided together and must stay under `reports/` as generated review
  artifacts.
- Allows baseline scope planning only. It does not build labels, feature
  matrices, models, WFA splits, metrics, predictions, or live/paper artifacts.

Baseline readiness gate:

```powershell
python -m scripts.validation.build_local_trade_baseline_readiness --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json
```

- Consumes the model-eligible scope gate and assesses tracked source/config
  readiness for the 7 local-trade model-eligible markets.
- Defaults to console-only output. Optional `--json-out` and `--markdown-out`
  must be provided together and must stay under `reports/` as generated review
  artifacts.
- Checks that cost/profile config coverage exists and that Phase 3 labels plus
  Phase 4 baseline features have bounded `--markets`/`--years` controls, then
  checks for matching PASS causal-base manifest evidence before any label or
  feature generation is safe.
- Current expected status is
  `ACTION_REQUIRED_LOCAL_TRADE_BASELINE_READINESS`: the local-trade label and
  feature commands are bounded, and candidate-root `HO/NG/RB` 2025/2026 now has
  matching projected PASS manifest evidence. Matching PASS causal-base manifest
  evidence is still not available for the repaired-root `6E/CL/ES/ZN`
  2025/2026 Phase 3 label command groups. It does not build labels, feature
  matrices, models, WFA splits, metrics, predictions, or live/paper artifacts.

Upstream manifest evidence resolver gate:

```powershell
python -m scripts.validation.build_local_trade_upstream_manifest_evidence_resolver --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json
```

- Consumes the baseline readiness gate result and classifies blocked Phase 3
  causal-base manifest command groups.
- Defaults to console-only output and exposes no generated report writers.
- Classifies candidate-root `all_raw` PASS manifest projection feasibility and
  repaired-root WARN manifest evidence blockers, then proposes an
  approval-gated repair path.
- Does not write reports, create manifests, accept warnings, run causal-base
  builds, labels, feature matrices, models, WFA splits, metrics, predictions,
  proof scans, downloads, or live/paper artifacts.
- Current expected status is
  `UPSTREAM_MANIFEST_EVIDENCE_RESOLUTION_PLAN_READY`: after the approved
  candidate-root projection, there are zero candidate projection blockers and
  two repaired-root warning-evidence blockers. Repaired-root `6E/CL/ES/ZN`
  2025/2026 groups require bounded causal-base repair approval before
  labels/features.

Upstream manifest repair proposal gate:

```powershell
python -m scripts.validation.build_local_trade_upstream_manifest_repair_proposal --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json
```

- Consumes the upstream manifest evidence resolver and converts its blocker
  classifications into reviewable repair proposal items.
- Defaults to console-only output and exposes no generated report writers.
- Before the approved candidate projection, proposed candidate-root manifest
  profile projection for `HO/NG/RB` 2025/2026 and repaired-root warning
  resolution options for `ZN_2025` plus `6E/CL/ES/ZN_2026`.
- Documents that the existing Phase 3 `--accepted-readiness-exceptions`
  support is not reusable for the current local-trade repaired-root warnings
  because it is restricted to an older Tier 1 candidate root.
- Does not write reports, create manifest projections, create accepted-warning
  files, run causal-base builds, labels, feature matrices, models, WFA splits,
  metrics, predictions, proof scans, downloads, or live/paper artifacts.
- Current expected status is
  `REVIEW_READY_UPSTREAM_MANIFEST_REPAIR_PROPOSAL`: after the approved
  candidate-root projection, two repaired-root warning proposal items remain,
  with zero generated outputs and zero staged generated paths. Actual repaired
  root repair execution still requires separate explicit approval.

Repaired-root readiness diagnostic plan gate:

```powershell
python -m scripts.validation.build_local_trade_repaired_root_readiness_diagnostic_plan --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json
```

- Consumes the upstream manifest evidence resolver after candidate-root
  projection and builds a console-only readiness diagnostic plan for the
  remaining repaired-root warning groups.
- Defaults to console-only output and exposes no generated report writers. It
  reports planned include-list payloads and exact Phase 2 `--readiness-only`
  command families, but does not write include-list files or readiness reports.
- Current expected status is
  `REVIEW_READY_REPAIRED_ROOT_READINESS_DIAGNOSTIC_PLAN`: two repaired-root
  diagnostic groups cover `6E/CL/ES/ZN` for 2025 and 2026, candidate projection
  blockers are zero, generated outputs are zero, and staged generated paths are
  zero.
- Actual diagnostic execution still requires explicit approval because it would
  write generated include-list and readiness-report artifacts under `reports/`.
- Does not accept repaired-root warnings, create accepted-warning files, run
  causal-base builds, labels, feature matrices, models, WFA splits, metrics,
  predictions, proof scans, downloads, or live/paper artifacts.

Guarded repaired-root readiness diagnostic runner:

```powershell
python -m scripts.validation.run_local_trade_repaired_root_readiness_diagnostic --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json
```

- Defaults to dry-run and writes no include-list files or readiness reports.
- Dry-run expected status is
  `DRY_RUN_READY_REPAIRED_ROOT_READINESS_DIAGNOSTIC_EXECUTION` only when the
  diagnostic reports root has no stale files and upstream raw-alignment evidence
  is usable for the planned Phase 2 profiles.
- Execution requires both `--execute` and the exact approval token
  `APPROVE_REPAIRED_ROOT_READINESS_DIAGNOSTIC_V1`.
- The plan and runner accept per-group raw-alignment overrides with repeatable
  `--raw-alignment-report-for profile:year=path` arguments. Keep
  `--raw-alignment-report` as a fallback only; repaired-root local-trade
  diagnostics should use separate `tier_3_holdout` and `tier_3_forward`
  alignment reports once those generated reports are separately approved.
- When execution is approved, the runner writes only the generated include-list
  files under `reports/`, then invokes Phase 2 with argv lists bounded to
  `--readiness-only`; it rejects build-mode flags such as
  `--allow-broad-build-after-readiness-pass`, `--broad-build-approval-token`,
  `--build-max-market-years`, `--build-progress-checkpoint-jsonl`, and
  `--accepted-readiness-exceptions`.
- It stops after the first timeout or nonzero readiness command. It does not
  perform causal-base repair/build writes, accepted-warning packet writes,
  labels, feature matrices, WFA/modeling, metrics, predictions, proof scans,
  downloads, staging, commits, pushes, or live/paper execution.
- After any approved readiness command returns success, the runner verifies the
  expected include-list, readiness JSON, readiness markdown, and readiness
  checkpoint files exist and are readable. The readiness JSON must report
  `status=PASS` and the expected selected market-year count; otherwise the
  runner stops as no-go.
- The diagnostic reports root must have no pre-existing files before execution,
  and approved execution may create only the bounded expected files. Stale or
  unexpected files under the diagnostic reports root stop the runner as no-go.
- The diagnostic reports root must remain under `reports/`; the runner does not
  scan arbitrary outside trees for stale generated files.
- After executing any readiness command, the runner re-checks staged
  `data/`/`reports/` paths. Any staged generated artifact stops the runner as
  no-go.
- Console output reports command failure count, artifact failure count,
  unexpected generated output count, generated output count, staged generated
  path count, and post-execution staged generated path count.
- The approved 2026-07-02 execution returned
  `NO_GO_REPAIRED_ROOT_READINESS_DIAGNOSTIC_EXECUTION`: the first readiness
  command failed before readiness reports were created because
  `reports\raw_ingest\raw_dbn_alignment.json` is scoped to
  `tier_3/tier_3_research`, not `tier_3_holdout/tier_3_holdout`, and its
  expected alignment scope lacks the included 2025 market-years. Do not rerun
  this wrapper until raw-alignment evidence is resolved and stale diagnostic
  root disposition is separately approved.

Raw-alignment evidence resolver gate:

```powershell
python -m scripts.validation.build_local_trade_raw_alignment_evidence_resolver --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json
```

- Consumes the repaired-root readiness diagnostic plan and inspects existing
  `reports/**/*alignment*.json` artifacts for Phase 2-usable raw-alignment
  evidence.
- Defaults to console-only output and exposes no generated report writers. It
  does not refresh raw alignment, write raw-alignment JSON/markdown reports,
  rerun readiness diagnostics, run causal-base builds, labels, feature matrices,
  models, WFA splits, metrics, predictions, proof scans, downloads, staging,
  commits, pushes, or live/paper artifacts.
- Current expected status is
  `REVIEW_READY_RAW_ALIGNMENT_EVIDENCE_REPAIR_PROPOSAL`: after the approved
  bounded raw-alignment generation, 157 existing alignment candidates are
  inspected, two matching raw-alignment reports are found for the repaired-root
  diagnostic groups, generated outputs from the resolver itself are zero, and
  staged generated paths are zero.
- Current finding: generated reports under
  `reports\pipeline_audit\local_trade_raw_alignment_repair_v1\` are Phase
  2-usable for `tier_3_holdout` 2025 and `tier_3_forward` 2026. Older `all_raw`,
  `tier_0`, and stale `tier_3` alignment reports may observe selected raw files,
  but remain unusable for this diagnostic because profile, raw-root, or expected
  market-year scope does not match.
- Source/tests/docs-only per-group raw-alignment wiring is implemented in the
  diagnostic plan and runner. A later, separately approved generated-artifact
  step may create bounded
  `tier_3_holdout` and `tier_3_forward` raw-alignment reports under
  `reports\pipeline_audit\local_trade_raw_alignment_repair_v1\`.

If separately approved after the source/tests/docs runner wiring, the proposed
raw-alignment generation command family is:

```powershell
python -m scripts.validation.audit_raw_dbn_alignment --profile tier_3_holdout --dbn-root data\dbn --raw-root data\raw --expected-only --json-out reports\pipeline_audit\local_trade_raw_alignment_repair_v1\tier_3_holdout_2025_raw_dbn_alignment.json --md-out reports\pipeline_audit\local_trade_raw_alignment_repair_v1\tier_3_holdout_2025_raw_dbn_alignment.md

python -m scripts.validation.audit_raw_dbn_alignment --profile tier_3_forward --dbn-root data\dbn --raw-root data\raw --expected-only --json-out reports\pipeline_audit\local_trade_raw_alignment_repair_v1\tier_3_forward_2026_raw_dbn_alignment.json --md-out reports\pipeline_audit\local_trade_raw_alignment_repair_v1\tier_3_forward_2026_raw_dbn_alignment.md
```

Raw-alignment generation scope and stop conditions:

- Command class: Phase 1C raw DBN alignment audits only.
- Maximum scope: two expected-only profile audits, one for `tier_3_holdout`
  2025 and one for `tier_3_forward` 2026. Each profile covers configured
  profile market-years for one year; the repaired-root diagnostic still remains
  limited to `6E,CL,ES,ZN` include-list rows.
- Timeout budget: 900 seconds per audit command; stop after the first timeout,
  Python traceback, nonzero exit, generated-artifact staging, status other than
  `PASS`, non-full audit completeness, unchecked definition join, or raw-root /
  profile mismatch.
- Expected generated artifacts if separately approved: two raw-alignment JSON
  reports and two markdown summaries under
  `reports\pipeline_audit\local_trade_raw_alignment_repair_v1\`; all are
  generated local reports and must remain unstaged.
- Forbidden patterns: Phase 2 causal-base build/repair, accepted-warning packet
  writes, labels, feature matrices, WFA/modeling, metrics, predictions, proof
  scans, provider downloads, cleanup, live/paper artifacts, staging, committing,
  or pushing.

If the repaired-root readiness diagnostic execution is explicitly approved, the
guarded wrapper command family should pass the generated per-group raw-alignment
reports and use a fresh diagnostic root because
`reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v1\`
contains stale output from the prior no-go execution:

```powershell
python -m scripts.validation.run_local_trade_repaired_root_readiness_diagnostic --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json --diagnostic-reports-root reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2 --raw-alignment-report-for tier_3_holdout:2025=reports\pipeline_audit\local_trade_raw_alignment_repair_v1\tier_3_holdout_2025_raw_dbn_alignment.json --raw-alignment-report-for tier_3_forward:2026=reports\pipeline_audit\local_trade_raw_alignment_repair_v1\tier_3_forward_2026_raw_dbn_alignment.json --execute --approval-token APPROVE_REPAIRED_ROOT_READINESS_DIAGNOSTIC_V1
```

The bounded Phase 2 command family produced by that wrapper is:

```powershell
# Write generated include-list inputs under reports/ only.
# 2025 include list rows: 6E, CL, ES, ZN for 2025.
# 2026 include list rows: 6E, CL, ES, ZN for 2026.

python -m scripts.phase2_causal_base.build_causal_base_data --readiness-only --profile tier_3_holdout --raw-root data\raw --output-root data\causally_gated_normalized --reports-root reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_holdout_2025 --raw-alignment-report reports\pipeline_audit\local_trade_raw_alignment_repair_v1\tier_3_holdout_2025_raw_dbn_alignment.json --market-year-include-list reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\include_6E_CL_ES_ZN_2025.json --readiness-json-out reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_holdout_2025\phase2_readiness_summary.json --readiness-md-out reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_holdout_2025\phase2_readiness_summary.md --readiness-checkpoint-jsonl reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_holdout_2025\phase2_readiness.progress.jsonl --readiness-max-market-years 4 --readiness-stop-after-blockers 4 --readiness-progress

python -m scripts.phase2_causal_base.build_causal_base_data --readiness-only --profile tier_3_forward --raw-root data\raw --output-root data\causally_gated_normalized --reports-root reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_forward_2026 --raw-alignment-report reports\pipeline_audit\local_trade_raw_alignment_repair_v1\tier_3_forward_2026_raw_dbn_alignment.json --market-year-include-list reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\include_6E_CL_ES_ZN_2026.json --readiness-json-out reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_forward_2026\phase2_readiness_summary.json --readiness-md-out reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_forward_2026\phase2_readiness_summary.md --readiness-checkpoint-jsonl reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_forward_2026\phase2_readiness.progress.jsonl --readiness-max-market-years 4 --readiness-stop-after-blockers 4 --readiness-progress
```

Diagnostic execution scope and stop conditions:

- Command class: Phase 2 causal-base readiness diagnostics only.
- Maximum scope: exactly 8 repaired-root market-years, split into two 4-row
  yearly runs: `6E,CL,ES,ZN` for 2025 and 2026.
- Timeout budget: 900 seconds per readiness command; stop after the first
  timeout, Python traceback, nonzero exit, generated-artifact staging,
  unexpected selected-market-year count, or unreadable report.
- Expected generated artifacts: two include-list JSON files, two readiness JSON
  summaries, two readiness markdown summaries, and two readiness progress JSONL
  files under
  `reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\`;
  all are generated local reports and must remain unstaged.
- Forbidden patterns: non-readiness Phase 2 build mode,
  `--allow-broad-build-after-readiness-pass`, `--broad-build-approval-token`,
  `--build-max-market-years`, `--build-progress-checkpoint-jsonl`,
  `--accepted-readiness-exceptions`, causal-base parquet writes,
  accepted-warning packet writes, labels, feature matrices, WFA/modeling,
  metrics, predictions, proof scans, provider downloads, cleanup, live/paper
  artifacts, staging, committing, or pushing.
- Required evidence before any further step: both readiness reports inspected,
  generated `data/**` and `reports/**` staging checks empty, and a refreshed
  baseline-readiness/resolver decision recorded. Even if both diagnostics PASS,
  do not run a causal-base repair build or labels/features without separate
  approval.

Current diagnostic result: the v2 guarded wrapper was approved and executed on
2026-07-02. It returned
`NO_GO_REPAIRED_ROOT_READINESS_DIAGNOSTIC_EXECUTION` after generating the
expected eight ignored local reports. `tier_3_holdout_2025` passed 4/4 selected
market-years. `tier_3_forward_2026` failed on `ES 2026` with one degraded-row
warning (`rows_pct=1.74227`, `bars=2760`, `sessions=3`) and three selected 2026
market-years still pending. Do not rerun the wrapper against the occupied v2
root, accept warnings, run causal-base repair/build, labels/features, WFA,
proof scans, promotion, or stage generated artifacts without separate approval.

The first approved ES 2026 triage command failed on 2026-07-02 with
`checkpoint row 1 missing market/year` because row 1 was
`stage=phase2_readiness_checkpoint_start`; no `ES_2026_*` reports were written.
The source/tests/docs-only loader repair is now implemented:
`load_checkpoint_rows` ignores only known checkpoint metadata rows without
`market`/`year` (`phase2_readiness_checkpoint_start` and
`phase2_readiness_checkpoint_summary`) while still failing closed on unknown
malformed rows. Focused validation passed:

```powershell
python -m pytest tests\validation\test_audit_phase2_readiness.py tests\validation\test_summarize_phase2_readiness_blockers.py tests\validation\test_drilldown_phase2_readiness_blockers.py tests\validation\test_build_phase2_repair_work_order.py
```

Result: `32 passed`.

Bounded ES 2026 repair-planning gate result: approved and executed on
2026-07-02. The summary, drilldown, and repair work-order commands generated
six ignored local reports under
`reports\pipeline_audit\local_trade_repaired_root_readiness_diagnostic_v2\tier_3_forward_2026\`.
The command exit codes were nonzero because the generated diagnostics are
fail-closed `FAIL` reports, not because of tracebacks. Scope validation found
exactly `ES 2026`: one degraded blocker, 116 raw UTC gaps, 113 Phase2 session
candidate gaps, max session gap 16 minutes, synthetic missing estimate 1681,
2760 degraded rows, and 6 missing/stale statistics-enrichment rows. The repair
work order has one `P1` item with actions
`repair_status_statistics_enrichment`, `review_degraded_raw_quality`, and
`exclude_only_if_explicitly_approved`; the P0 starter batch is empty. Generated
reports remain ignored and unstaged. Do not accept this warning, exclude ES
2026, run causal-base repair/build, labels/features, WFA, proof scans,
promotion, or stage generated artifacts without separate approval.

ES 2026 P1 repair proposal gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_repair_proposal
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_repair_proposal.py
```

Current status: implemented and review-ready. The console-only gate reads the
generated ES 2026 work-order and drilldown reports, verifies exact scope
`ES 2026`, and proposes three non-executed repair-direction items: repair or
refresh statistics-enrichment evidence, review degraded raw-quality evidence,
and keep exclusion diagnostic-only unless explicitly approved. The gate returned
`REVIEW_READY_ES2026_P1_REPAIR_PROPOSAL` with 3 proposal items, 1 P1 work
order, 0 generated outputs, 0 staged generated paths, and 0 failures. Focused
tests passed (`4 passed`). No generated reports, causal-base repair/build
writes, accepted-warning packets, labels, feature matrices, WFA/modeling,
metrics, predictions, proof scans, downloads, live/paper artifacts, staging,
committing, or pushing were performed.

Direction decision: approved direction only. The approved direction is to
repair/refresh statistics-enrichment evidence and review degraded raw-quality
evidence for exactly `ES 2026`, while keeping exclusion diagnostic-only unless
explicitly approved. This approval does not approve generated report writes,
causal-base repair/build, accepted-warning packets, labels/features,
WFA/modeling, proof scans, staging, commits, pushes, downloads, or live/paper
execution.

ES 2026 P1 repair-plan gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_repair_plan --print-plan-json
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_repair_plan.py
```

Current status: implemented and review-ready. The console-only gate reads the
approved ES 2026 P1 repair proposal evidence, verifies exact ES 2026 scope, and
returns a bounded plan with 3 plan items and 7 approval-required command
families. It returns `REVIEW_READY_ES2026_P1_REPAIR_PLAN` with 0 generated
outputs, 0 staged generated paths, and 0 failures. With `--print-plan-json`, it
prints the exact non-executed repair-path commands, expected artifacts,
required preconditions, stop conditions, and generated-artifact hygiene. Focused
tests pass (`6 passed`). No dry-run plans, generated reports, provider
downloads, data mutation, candidate raw writes, readiness reruns, causal-base
repair/build, accepted-warning packets, exclusions, labels/features,
WFA/modeling, proof scans, staging, committing, pushing, or live/paper
execution were performed.

ES 2026 P1 repair-path diagnostic runner:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_repair_diagnostic
```

Focused validation:

```powershell
python -m pytest -q tests\validation\test_run_local_trade_es2026_p1_repair_diagnostic.py
```

Current status: implemented and run under bounded diagnostic-only approval. The
runner reads the existing ES 2026 work order, candidate raw-quality drilldown,
candidate conversion evidence, optional status/statistics audit, and candidate
raw parquet. It writes ignored review reports only under
`reports\pipeline_audit\local_trade_es2026_p1_repair_plan_v2\repair_diagnostics\`.
Against the current repo it returned
`REVIEW_READY_ES2026_P1_REPAIR_DIAGNOSTIC` with recommended disposition
`accepted_warning_review_required`, 2 generated report outputs, 0 staged
generated paths, 0 post-execution staged generated paths, and 0 failures.
Evidence: candidate raw has 0 degraded/unavailable rows, status issue rows are
0, and statistics issue rows are 6 at `2026-03-18T00:00:00Z` through
`2026-03-18T00:05:00Z`. This diagnostic does not approve readiness reruns,
accepted-warning packet writes, ES 2026 exclusion, causal-base repair/build,
labels/features, WFA/modeling, proof scans, staging, commits, pushes, or
live/paper execution.

ES 2026 P1 accepted-warning criteria review runner:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_accepted_warning_review
```

Focused validation:

```powershell
python -m pytest -q tests\validation\test_run_local_trade_es2026_p1_accepted_warning_review.py
```

Current status: implemented and run under bounded criteria-review-only
approval. The runner reads the repair-path diagnostic, validates exact
`ES 2026` / `tier_3_forward` scope, requires the review to be limited to the 6
statistics enrichment rows, verifies output reports are ignored under
`reports/**`, and checks generated `data/**` or `reports/**` artifacts are not
staged. It writes ignored review reports only under
`reports\pipeline_audit\local_trade_es2026_p1_repair_plan_v2\accepted_warning_review\`.
Against the current repo it returned
`REVIEW_READY_ES2026_P1_ACCEPTED_WARNING_CRITERIA_REVIEW` with criteria status
`ACCEPTED_WARNING_PACKET_NOT_READY`, 2 generated report outputs, 0 staged
generated paths, 0 post-execution staged generated paths, and 0 failures.
Evidence: the six statistics rows are isolated, candidate raw has 0
degraded/unavailable rows and 0 status issue rows. Phase 2 now supports the
source-level `statistics_enrichment_sparse` accepted-readiness exception
category for statistics-only warnings. This criteria review was superseded by
the bounded readiness-warning evidence refresh below for exact current Phase 2
warning evidence. It does not approve accepted-warning packet writes, readiness
reruns, data mutation, candidate raw rewrites, ES 2026 exclusion, causal-base
repair/build, labels/features, WFA/modeling, proof scans, staging, commits,
pushes, or live/paper execution.

ES 2026 P1 readiness-warning evidence runner:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_readiness_warning_evidence
```

Focused validation:

```powershell
python -m pytest -q tests\validation\test_run_local_trade_es2026_p1_readiness_warning_evidence.py
```

Current status: implemented and run under bounded readiness-warning-evidence
approval. The runner reads the repair-path diagnostic and candidate raw parquet,
validates exact `ES 2026` / `tier_3_forward` scope, calls Phase 2
`process_file` in memory with `write_output=False`, and writes ignored evidence
reports only under
`reports\pipeline_audit\local_trade_es2026_p1_repair_plan_v2\readiness_warning_evidence\`.
Against the current repo it returned
`REVIEW_READY_ES2026_P1_READINESS_WARNING_EVIDENCE` with evidence status
`ACCEPTED_WARNING_PACKET_PREPARATION_READY`, 2 generated report outputs, 0
staged generated paths, 0 post-execution staged generated paths, and 0
failures. Exact current Phase 2 evidence is `WARN` with only
`statistics enrichment sparse: missing_rows=6 stale_rows=6`; status enrichment
missing/stale rows are 0, degraded bar rows are 0, and no synthetic, roll, or
degraded-threshold warning contamination is present. This runner did not write
an accepted-warning packet, mutate data, rewrite candidate raw, run statistics
repair, exclude ES 2026, build causal-base data, build labels/features, run
WFA/modeling, proof scan, stage, commit, push, or run live/paper execution.

ES 2026 P1 accepted-warning packet:

Current status: prepared in `configs/alpha_tiered.yaml` under
`tier_3_forward` as one source-level `accepted_readiness_exceptions` entry
scoped exactly to `ES 2026`, category `statistics_enrichment_sparse`, and
warning string `statistics enrichment sparse: missing_rows=6 stale_rows=6`.
The packet references the current ignored evidence reports:
`reports\pipeline_audit\local_trade_es2026_p1_repair_plan_v2\readiness_warning_evidence\ES_2026_readiness_warning_evidence.json`
and `.md`. This packet does not rerun readiness or change current workflow
status by itself; ES 2026 remains fail-closed until a separate bounded
readiness rerun is approved and verified.

Focused validation:

```powershell
python -m pytest -q tests\validation\test_es2026_accepted_warning_packet.py
```

Stop conditions: do not mutate data, rewrite candidate raw, execute statistics
repair, exclude ES 2026, run causal-base build/repair, build labels/features,
run WFA/modeling, proof scan, stage, commit, push, or run live/paper paths as
part of this packet preparation.

ES 2026 P1 optional status/statistics dry-run diagnostic wrapper:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_dry_run_diagnostics
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_repair_plan.py tests\validation\test_run_local_trade_es2026_p1_dry_run_diagnostics.py
```

Current status: implemented and approval-bound for corrected v2 scope. The
guarded wrapper builds the repair plan, extracts only the status/statistics
Phase 1A `--dry-run` command families, verifies exact `ES 2026` scope through
`2026-06-13`, verifies the planned v2 outputs are ignored by git before
execution, and writes nothing unless `--execute` is passed with the exact
approval token. Against the current repo it returns
`DRY_RUN_READY_ES2026_P1_DRY_RUN_DIAGNOSTICS` with 2 planned commands, 0
executed commands, 2 expected generated outputs under
`reports\pipeline_audit\local_trade_es2026_p1_repair_plan_v2\`, 2 ignored
expected generated outputs, 0 unignored expected generated outputs, 0 generated
outputs, 0 staged generated paths, and 0 failures. Older v1 dry-run evidence
ending `2027-01-01` is historical only and must not drive the next action.

Post-execution dry-run review gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_dry_run_review
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_dry_run_review.py
```

Current status: implemented and fail-closed until the corrected v2 dry-run
plans are generated. The console-only gate reads only
`databento_download_plan_dry_run.json` for status/statistics under the ES 2026
repair reports root, validates exact `ES 2026` one-task scope through
`2026-06-13`, verifies the generated plans are ignored by git and unstaged, and
writes no reports. Against the current repo it returns no-go because the v2
dry-run plans are absent; older v1 plans ending `2027-01-01` are historical
only.

Optional archive availability diagnostic gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_optional_archive_availability
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_optional_archive_availability.py
```

Current status: implemented and review-ready. The console-only gate reloads the
corrected v2 `ES 2026` status/statistics dry-run plans, inspects only their
planned optional DBN `output_path` archives and manifests under `data/`,
verifies those planned archive artifacts are ignored by git, accepts
repo-relative archive paths in manifests when they match the repo-relative
planned archive path, and writes no reports. Against the current repo it
returns `REVIEW_READY_ES2026_P1_OPTIONAL_ARCHIVE_AVAILABILITY` with 2 planned
archives, 4 ignored planned generated artifacts, 2 local-ready archives, 0
missing archives, 0 missing manifests, 0 invalid manifests, 0 generated
outputs, 0 staged generated paths, and 0 failures.

All-market optional archive inventory gate:

```powershell
python -m scripts.validation.build_local_trade_optional_archive_inventory
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_optional_archive_inventory.py
```

Current status: implemented and review-ready as console-only local evidence. The
gate inventories local optional `statistics,status` DBN archives under
`data\dbn\`, defaults to `2026-01-01` through `2026-06-13`, validates archive
manifests, confirms expected 33-market coverage, checks no generated
`data/**` or `reports/**` artifacts are staged, and writes no output files.
Against the current repo it returns
`REVIEW_READY_LOCAL_TRADE_OPTIONAL_ARCHIVE_INVENTORY` with 33 markets, 33 ready
markets, 66 valid archives, 0 invalid archives, 0 generated outputs, 0 staged
generated paths, and 0 failures.

Candidate raw conversion plan gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_candidate_conversion_plan
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_candidate_conversion_plan.py
```

Current status: implemented and review-ready for a separate human approval
decision. The console-only gate preserves the repair-plan candidate raw
conversion and optional schema audit command families as approval-required,
verifies the six planned candidate conversion outputs are ignored generated
artifacts, writes no reports, and does not convert candidate raw. Against the
current repo it returns `REVIEW_READY_ES2026_P1_CANDIDATE_CONVERSION_PLAN`
with 2 command families, 2 approval-required commands, 6 ignored expected
generated outputs, 0 generated outputs, 0 staged generated paths, and 0
failures.

Guarded candidate raw conversion runner:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_candidate_conversion
```

Focused validation:

```powershell
python -m pytest tests\validation\test_run_local_trade_es2026_p1_candidate_conversion.py
```

Current status: implemented. The wrapper defaults to no execution, requires
`--execute --approval-token APPROVE_ES2026_P1_CANDIDATE_CONVERSION_V1` before
candidate raw writes, validates the generated candidate parquet plus optional
schema audit reports after execution, verifies planned candidate outputs are
ignored generated artifacts before execution, checks for unexpected outputs, and
rechecks staged generated artifacts. The approved bounded execution returned
`EXECUTED_ES2026_P1_CANDIDATE_CONVERSION` with 2 planned commands, 2 executed
commands, 6 expected/generated outputs, 0 unexpected outputs, 0 staged
generated paths, and 0 failures. The candidate conversion command uses local
OHLCV DBN input root `data/dbn/ohlcv_1m` and local optional schema root
`data/dbn`; no provider download or canonical raw overwrite was performed.

Post-execution candidate conversion review gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_candidate_conversion_review
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_candidate_conversion_review.py
```

Current status: implemented and review-ready after the guarded candidate
conversion runner produced the expected candidate raw parquet and optional
schema audit outputs. The console-only gate verifies the candidate ES 2026
parquet, conversion reports, PASS optional schema audit, exact candidate output
set, ignored generated-artifact status, and unstaged generated artifacts, then
exposes the next raw-quality drilldown and readiness-only command families as
approval-required only. Against the current repo it returns
`REVIEW_READY_ES2026_P1_CANDIDATE_CONVERSION_REVIEW` with 6 expected candidate
outputs, 6 ignored expected candidate outputs, 0 unignored expected candidate
outputs, 0 generated outputs from the review gate itself, 0 staged generated
paths, and 0 failures.

Candidate readiness plan gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_candidate_readiness_plan
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_candidate_readiness_plan.py
```

Current status: implemented and review-ready. The console-only gate plans the candidate raw-quality
drilldown, an exact `ES 2026` candidate raw-alignment audit with an explicit
include-list artifact, and the bounded readiness-only rerun with the candidate
raw-alignment report wired in. It verifies planned readiness outputs are ignored
generated artifacts, writes no include lists or reports, and does not run
readiness. Against the current repo it returns
`REVIEW_READY_ES2026_P1_CANDIDATE_READINESS_PLAN` with 3 command families, 8
expected generated outputs, 8 ignored expected generated outputs, 0 unignored
expected generated outputs, 0 generated outputs, 0 staged generated paths, and
0 failures.

Guarded candidate readiness runner:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_candidate_readiness
```

Focused validation:

```powershell
python -m pytest tests\validation\test_run_local_trade_es2026_p1_candidate_readiness.py
```

Current status: implemented and fail-closed after the approved bounded
diagnostic execution. The wrapper defaults to no execution, requires
`--execute --approval-token APPROVE_ES2026_P1_CANDIDATE_READINESS_V1` before
writing include lists or running diagnostics, validates the raw-quality
drilldown, candidate raw-alignment report, and readiness summary after
execution, verifies planned readiness outputs are ignored generated artifacts
before execution, checks unexpected outputs, and rechecks staged generated
artifacts. The approved command returned
`NO_GO_ES2026_P1_CANDIDATE_READINESS_EXECUTION` with 3 planned commands, 1
executed command, 1 command failure, 10 output failures, 8 expected generated
outputs, 8 ignored expected generated outputs, 0 unignored expected generated
outputs, 1 generated output, 0 unexpected generated outputs, 0 staged generated
paths, 0 post-execution staged generated paths, and 2 failures. The only
generated file was the ignored raw-quality drilldown
`reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/ES_2026_candidate_raw_quality_drilldown.json`,
which reported `status=FAIL` because ES 2026 candidate raw data breached the
degraded threshold (`rows_pct=1.74227`, `bars=2760`, `sessions=3`). No
candidate raw-alignment or readiness-only outputs were generated.

Post-execution candidate readiness review gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_candidate_readiness_review
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_candidate_readiness_review.py
```

Current status: implemented and fail-closed until the guarded candidate
readiness runner produces the expected raw-quality, raw-alignment, and
readiness-only outputs. The console-only gate verifies exact ES 2026 candidate
diagnostics, PASS readiness evidence, ignored generated-artifact status, and
unstaged generated artifacts. It writes no reports and does not approve
causal-base builds, labels, features, WFA/modeling, proof scans, or promotion.
Against the current repo it returns
`REVIEW_READY_ES2026_P1_CANDIDATE_READINESS_REVIEW` with 8 expected readiness
outputs, 8 ignored expected readiness outputs, 0 unignored expected readiness
outputs, 0 generated outputs, 0 staged generated paths, and 0 failures.

ES 2026 P1 workflow status gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_workflow_status
```

Optional console approval-packet output:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_workflow_status --print-boundary-json
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_workflow_status.py
```

Current status: implemented and console-only. The gate summarizes the ES 2026
P1 repair-plan, dry-run, archive-availability, candidate-conversion, and
candidate-readiness gates, reports the current gate, writes no reports, and
fails closed if the current approval-boundary expected generated outputs are
not all ignored by git. The current approval boundary also carries a bounded
plan object with command family, exact ES 2026 scope, per-command timeout,
expected generated artifacts, forbidden patterns/argument flags, and stop
condition; artifact-generating approval boundaries fail closed if that bounded
plan packet is incomplete. The future optional archive/provider decision,
candidate conversion, and candidate readiness approval boundaries also expose
bounded plan packets before they can become actionable. Approval-boundary
ignored/unignored counts are normalized to the exact expected artifact set for
the current boundary, so broader ignored-path context cannot overcount future
step artifacts. The active dry-run wrapper also normalizes Windows-style
backslash paths before comparing supplied ignored paths to planned outputs;
the downstream dry-run review, archive availability, candidate conversion, and
candidate readiness gates use the same normalized exact-set filtering. The
optional `--print-boundary-json` flag prints the current approval boundary
packet to stdout after the default status line; it does not write reports and
includes the recommended command, approval token, generated-artifact hygiene
counts, bounded plan fields, and supporting optional-archive inventory evidence
needed for the next approval decision.
The status chain advances past reviewed candidate readiness to the guarded
downstream label wrapper only when that wrapper is dry-run ready. Against the
current repo it now fails closed with `NO_GO_ES2026_P1_WORKFLOW_STATUS`,
current gate `downstream_label_build_execution`, current gate status
`NO_GO_ES2026_P1_DOWNSTREAM_LABEL_BUILD_EXECUTION`, next action kind
`fix_or_repair_gate`, optional inventory status
`REVIEW_READY_LOCAL_TRADE_OPTIONAL_ARCHIVE_INVENTORY`, 33 optional-inventory
ready markets, 0 optional-inventory invalid archives, 0 expected generated
outputs, 0 ignored expected generated outputs, 0 unignored expected generated
outputs, 0 generated outputs, 0 staged generated paths, and 1 failure. With
`--print-boundary-json`, it prints no approval token and no recommended
execution command. The current blocker is that the ES 2026 candidate
causal-base manifest carries one accepted upstream warning, but Phase 3 label
execution is not yet wired to consume the approved ES 2026 accepted-warning
evidence. After accepted-warning handling is wired and a separately approved
label build completes, the status chain can advance past the label wrapper's
expected overwrite-protection no-go to the guarded downstream feature wrapper
when that wrapper is dry-run ready; that future boundary carries approval token
`APPROVE_ES2026_P1_PHASE4_FEATURE_BUILD_V1`, expected feature artifacts, and a
bounded Phase 4 stop condition. After feature evidence is complete, workflow
status evaluates the downstream WFA split gate and either exposes its bounded
Phase 5 split-plan approval packet or reports its fail-closed blocker. After
completed WFA split artifacts exist, workflow status can advance to the
guarded Phase 6 model-smoke wrapper with approval token
`APPROVE_ES2026_P1_PHASE6_MODEL_SMOKE_V1`; after completed model-smoke
prediction artifacts exist, it can advance to the guarded Phase 8 metrics
wrapper with approval token `APPROVE_ES2026_P1_PHASE8_METRICS_V1`. These
future boundaries keep the same bounded-plan packet checks. After completed
Phase 8 metrics artifacts exist, workflow status advances through the
console-only post-metrics review gate; it does not approve model promotion,
artifact freeze, proof scans, staging, commit, push, or live/paper execution,
and the boundary packet keeps explicit downstream `non_approval` flags.
Workflow status summaries and boundary packets distinguish human review from
execution approval with `execution_approval_required`.
None of these future boundaries changes the current repo boundary.

ES 2026 P1 blocker proposal gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_blocker_proposal --print-plan-json
```

Focused validation:

```powershell
python -m pytest -q tests\validation\test_build_local_trade_es2026_p1_blocker_proposal.py
```

Current status: implemented and console-only. The gate is for the earlier
candidate-readiness no-go boundary; the current workflow has advanced to the
downstream label wrapper repair boundary. Against the current repo it returns
`NO_GO_ES2026_P1_BLOCKER_PROPOSAL` with current gate
`downstream_label_build_execution`, current gate status
`NO_GO_ES2026_P1_DOWNSTREAM_LABEL_BUILD_EXECUTION`, candidate-readiness review
status `REVIEW_READY_ES2026_P1_CANDIDATE_READINESS_REVIEW`, optional inventory
status `REVIEW_READY_LOCAL_TRADE_OPTIONAL_ARCHIVE_INVENTORY`, raw-quality
status `FAIL`, zero proposal items, zero generated outputs, zero staged
generated paths, and 2 failures. With `--print-plan-json`, it prints no
bounded source/tests/docs-only plan while this no-go boundary is inactive. It
does not approve readiness reruns, provider downloads or cost diagnostics,
causal-base repair/build, accepted-warning packets, ES 2026 exclusion,
labels/features, WFA/modeling, proof scans, staging, commits, pushes, or
live/paper execution.

ES 2026 P1 disposition plan gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_disposition_plan --print-disposition-json
```

Focused validation:

```powershell
python -m pytest -q tests\validation\test_build_local_trade_es2026_p1_disposition_plan.py
```

Current status: implemented and console-only. The gate is for the earlier
candidate-readiness no-go boundary; the current workflow has advanced to the
downstream label wrapper repair boundary. Against the current repo it returns
`NO_GO_ES2026_P1_DISPOSITION_PLAN` with current gate
`downstream_label_build_execution`, current gate status
`NO_GO_ES2026_P1_DOWNSTREAM_LABEL_BUILD_EXECUTION`, raw-quality status `FAIL`,
recommended option `None`, zero disposition options, zero generated outputs,
zero staged generated paths, and 3 failures. With
`--print-disposition-json`, it prints a deterministic review packet comparing
`repair_path`, `accepted_warning_policy`, and `es2026_exclusion`. It does not
approve repairs, readiness reruns, provider downloads or cost diagnostics,
causal-base repair/build, accepted-warning packets, ES 2026 exclusion,
labels/features, WFA/modeling, proof scans, staging, commits, pushes, or
live/paper execution.

Current repair-path decision: `repair_path` is the chosen bounded disposition
direction. The approved repair-path diagnostic found the candidate raw rebuild
does not currently need another raw repair/rebuild for degraded data-quality
rows, but 6 statistics enrichment rows remain missing/stale. The
accepted-warning criteria review found the issue is isolated to those 6
statistics rows, and Phase 2 now has a statistics-only accepted-warning
exception category. The bounded readiness-warning evidence refresh captured the
exact current Phase 2 warning string
`statistics enrichment sparse: missing_rows=6 stale_rows=6` with no status,
degraded, synthetic, or roll warning contamination. The accepted-warning packet
is prepared in `configs/alpha_tiered.yaml`.

Current status: the approved bounded ES 2026 packet-aware readiness rerun passed
against candidate raw root `data/raw_es2026_p1_repair_candidate`. Candidate raw
alignment is PASS for exactly `ES 2026`; Phase 2 readiness is PASS with one
accepted `statistics_enrichment_sparse` exception, original status `WARN`,
blockers 0, failures 0, and accepted exception failures 0. Workflow status is
now `ACTION_REQUIRED_ES2026_P1_WORKFLOW_STATUS` at current gate
`downstream_label_build_execution` because the separate bounded causal-base
build was approved, completed, and reviewed. The active next human decision is
whether to approve the guarded Phase 3 label wrapper. Do not rerun causal-base
builds, exclude ES 2026, build labels/features, run WFA/modeling, proof scan,
stage, commit, push, or run live/paper paths without a separate bounded
decision.

ES 2026 P1 causal-base repair/build proposal gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_causal_base_build_proposal --print-proposal-json
```

Focused validation:

```powershell
python -m pytest tests\validation\test_build_local_trade_es2026_p1_causal_base_build_proposal.py
```

Current status: implemented, previously approved, and now superseded by the
completed build evidence. Against the current repo the console-only proposal
gate returns `NO_GO_ES2026_P1_CAUSAL_BASE_BUILD_PROPOSAL` because the workflow
has advanced to `downstream_label_build_execution` and the six expected
causal-build artifacts already exist. It reports 6 expected generated outputs,
6 ignored expected generated outputs, 0 unignored expected generated outputs,
6 existing expected generated outputs, 0 generated outputs, 0 commands
executed, 0 staged generated paths, and 2 failures.

The reviewed proposal defined this exact build command before approval:

```powershell
python -m scripts.phase2_causal_base.build_causal_base_data --profile tier_3_forward --raw-root data/raw_es2026_p1_repair_candidate --output-root data/causally_gated_normalized/local_trade_es2026_p1_candidate --reports-root reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1 --profile-config configs/alpha_tiered.yaml --session-config configs/market_sessions.yaml --raw-alignment-report reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/ES_2026_candidate_raw_dbn_alignment.json --market-year-include-list reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1/include_ES_2026.json --build-max-market-years 1 --build-progress-checkpoint-jsonl reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1/phase2_build.progress.jsonl
```

Bounded proposal packet:

- Command class: Phase 2 causal-base non-readiness build, exact scope only.
- Maximum scope: exactly `ES 2026`, `tier_3_forward`, candidate raw root
  `data/raw_es2026_p1_repair_candidate`, candidate output root
  `data/causally_gated_normalized/local_trade_es2026_p1_candidate`, and build
  reports root `reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1`.
- Required pre-run artifact, only if the reviewed proposal is later approved:
  `reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1/include_ES_2026.json`
  with exactly `{"market_years": [{"market": "ES", "year": 2026}]}`.
- Timeout budget: external 1800-second process timeout; stop on timeout,
  Python traceback, nonzero exit, readiness preflight failure, or output-root
  guard failure.
- Expected ignored artifacts under the current source policy: the include list,
  `ES/2026.parquet`, build progress JSONL, `causal_base_manifest.json`,
  `causal_base_validation.json`, and `causal_base_validation.csv`. Local-trade
  gap report artifacts are required only if the target profile is mandatory in
  `MANDATORY_LOCAL_TRADE_GAP_AUDIT_PROFILES`.
- Required validation checks after any separately approved build: all expected
  artifacts exist and are non-empty; no unexpected outputs exist under the build
  reports root or ES candidate output path; manifest status is `PASS` for
  exactly one `ES 2026` output; `accepted_exception_count=1`,
  category `statistics_enrichment_sparse`, and
  `accepted_exception_failure_count=0`; validation JSON status is `PASS` with
  one file, zero failures, and the local-trade OHLCV gap gate matches current
  source policy. For current `tier_3_forward` policy, that postcondition is
  `SKIPPED` / `profile_not_required` with vendor-backed OHLCV provenance status
  `synthetic_thresholds_diagnostic_vendor_backed_provenance`, and
  `git diff --cached --name-only -- data reports` is empty.
- Forbidden without separate approval: canonical data mutation, candidate raw
  rewrite, provider download/cost diagnostic, accepted-warning packet write,
  ES 2026 exclusion, labels/features, WFA/modeling, metrics/predictions,
  proof scan, staging/commit/push, and live/paper execution.

Execution result: approved and run on 2026-07-03. The build command returned
exit code 0 within the 1800-second timeout and generated ignored candidate
artifacts only. Manifest and validation reports are `PASS` for exactly
`ES 2026`, with one accepted `statistics_enrichment_sparse` exception and zero
accepted-exception failures. The local-trade OHLCV gap gate recorded `SKIPPED`
/ `profile_not_required`; no local-trade gap reports were created. A later
source/tests/docs-only proposal update made this postcondition policy-aware:
current source sets `MANDATORY_LOCAL_TRADE_GAP_AUDIT_PROFILES` to an empty
tuple, so `tier_3_forward` is expected to skip the local-trade gate while
retaining vendor-backed OHLCV provenance evidence. Downstream labels/features
still require a separate bounded approval gate.

Gap-gate policy review gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_gap_gate_policy_review --print-review-json
```

- Console-only; writes no reports, changes no policy, and runs no proof/build
  command.
- Verifies the existing ES 2026 candidate build reports are exact-scope `PASS`,
  the policy-aware proposal expects `SKIPPED` / `profile_not_required`, the
  generated build evidence matches that skipped-gate postcondition, current
  source does not require the target profile, current validation evidence records
  vendor-backed OHLCV provenance status, and generated `data/**` / `reports/**`
  paths are unstaged.
- Returns `REVIEW_READY_ES2026_P1_GAP_GATE_POLICY_REVIEW` with
  `postcondition_alignment_status=ALIGNED` when the source policy, proposal
  postcondition, and generated build evidence agree. This resolves only the
  gap-gate postcondition mismatch.
- Does not permit downstream labels/features, WFA/modeling, proof scans,
  provider actions, staging, commit, push, or live/paper execution.

ES 2026 downstream label approval gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_downstream_label_gate --print-gate-json
```

- Console-only; writes no reports, creates no labels, and runs no build command.
- Verifies the ES 2026 gap-gate review is aligned, the candidate causal-base
  manifest is exact-scope `PASS`, the candidate causal parquet exists and its
  hash matches the manifest, `tier_3_forward` contains `ES 2026`, ES costs are
  non-provisional, Phase 3 has bounded market/year controls, the approved
  ES 2026 accepted-warning packet is exact in `configs/alpha_tiered.yaml`,
  planned label artifacts are ignored and absent, generated `data/**` /
  `reports/**` paths are unstaged, and Phase 3 accepted-warning handling is
  wired when the upstream causal manifest contains accepted exceptions.
- Current status after the approved label execution: this pre-execution gate
  returns `NO_GO_ES2026_P1_DOWNSTREAM_LABEL_GATE` because the three planned
  label artifacts already exist. Before execution, it returned
  `REVIEW_READY_ES2026_P1_DOWNSTREAM_LABEL_GATE` with approval token
  `APPROVE_ES2026_P1_PHASE3_LABEL_BUILD_V1`, 3 expected ignored outputs, 0
  existing expected outputs, 0 generated outputs, 0 executed commands, 0 staged
  generated paths, and 0 failures.
- The bounded approval command exposed by the gate is:

```powershell
python -m scripts.phase3_labels.build_labels --profile tier_3_forward --input-root data/causally_gated_normalized/local_trade_es2026_p1_candidate --output-root data/labeled/local_trade_es2026_p1_candidate --reports-root reports/labels/local_trade_es2026_p1_candidate --costs-config configs/costs.yaml --profile-config configs/alpha_tiered.yaml --causal-base-manifest reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1/causal_base_manifest.json --accepted-readiness-exceptions configs/alpha_tiered.yaml --markets ES --years 2026
```

- Maximum scope: exactly `ES 2026`; no network; no canonical data mutation;
  candidate causal input root `data/causally_gated_normalized/local_trade_es2026_p1_candidate`;
  candidate label output root `data/labeled/local_trade_es2026_p1_candidate`;
  candidate label reports root `reports/labels/local_trade_es2026_p1_candidate`.
- Timeout budget: external 900-second process timeout.
- Expected ignored artifacts after a separate execution approval:
  `ES/2026.parquet`, `label_manifest.json`, and `label_report.json` under the
  candidate label output/report roots.
- Stop if approved ES 2026 accepted-warning evidence is missing or drifts, any
  expected label artifact already exists, Phase 3 returns nonzero,
  manifest-gate or cost/config checks fail, an unexpected output is written, the
  label manifest is not exact-scope `PASS` for `ES 2026`, or generated `data/**`
  / `reports/**` artifacts are staged.
- Does not approve feature matrices, WFA/modeling, metrics, predictions, proof
  scans, provider actions, staging, commit, push, or live/paper execution.

ES 2026 guarded downstream label execution wrapper:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_downstream_label_build
```

- Dry-run by default; writes no labels and runs no Phase 3 subprocess. The
  `--execute --approval-token APPROVE_ES2026_P1_PHASE3_LABEL_BUILD_V1` path is
  approval-bound and must not be run without explicit approval.
- Starts from the downstream label approval gate, verifies the exact bounded
  Phase 3 command, confirms expected outputs are ignored and absent, fails
  closed on stale candidate label output/report roots, and checks generated
  `data/**` / `reports/**` paths are unstaged before any execution.
- Approved execution returned `EXECUTED_ES2026_P1_DOWNSTREAM_LABEL_BUILD` with
  1 planned command, 1 executed command, 0 command failures, 0 output failures,
  3 expected ignored generated outputs, 3 generated outputs, 0 unexpected
  outputs, 0 staged generated paths, and 0 failures. Later dry-runs recognize
  the exact completed label artifacts as
  `EXECUTED_ES2026_P1_DOWNSTREAM_LABEL_BUILD` with 0 commands executed.
- If separately approved, the wrapper will run only the gate-defined ES 2026
  label command and then validate the label parquet, `label_manifest.json`, and
  `label_report.json`: exact
  `ES 2026`, `labels` stage, `PASS`, one selected input, matching candidate
  roots, matching causal-base manifest gate, matching accepted-warning evidence
  path, matching output hash, no unexpected files, and no staged generated
  artifacts.
- Does not approve feature matrices, WFA/modeling, metrics, predictions, proof
  scans, provider actions, staging, commit, push, or live/paper execution.

ES 2026 downstream feature approval gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_downstream_feature_gate --print-gate-json
```

- Console-only; writes no reports, creates no feature matrices, and runs no
  build command.
- Starts from the guarded label wrapper. Before labels exist, that wrapper must
  be dry-run ready without an upstream accepted-warning blocker; after a
  separately approved label build, exact completed label artifacts are accepted
  only when they are the planned wrapper outputs, generated-artifact hygiene is
  clean, and the label manifest is exact-scope `PASS`. Current repo state has
  completed ignored Phase 4 feature artifacts, so this pre-execution gate now
  fail-closes with 10 expected ignored feature artifacts, 10 existing expected
  feature artifacts, 0 generated outputs, 0 staged generated paths, and
  1 overwrite-protection failure.
- When labels exist, the gate verifies exact `ES 2026` label manifest scope,
  matching label output hash, `PASS` causal-base manifest gate embedded in the
  label manifest, Phase 4 bounded market/year controls, planned feature
  artifacts ignored and absent, and generated `data/**` / `reports/**` paths
  unstaged.
- Approval command exposed only when label evidence exists and candidate feature
  roots are empty:

```powershell
python -m scripts.phase4_features.build_baseline_features --profile tier_3_forward --input-root data/labeled/local_trade_es2026_p1_candidate --output-root data/feature_matrices/local_trade_es2026_p1_candidate --reports-root reports/features_baseline/local_trade_es2026_p1_candidate --costs-config configs/costs.yaml --profile-config configs/alpha_tiered.yaml --label-manifest reports/labels/local_trade_es2026_p1_candidate/label_manifest.json --markets ES --years 2026
```

- Maximum scope: exactly `ES 2026`; no network; no canonical data mutation;
  candidate label input root `data/labeled/local_trade_es2026_p1_candidate`;
  candidate feature output root
  `data/feature_matrices/local_trade_es2026_p1_candidate`; candidate feature
  reports root `reports/features_baseline/local_trade_es2026_p1_candidate`.
- Timeout budget: external 900-second process timeout.
- Expected ignored artifacts after later separate approval: `ES/2026.parquet`,
  registry JSONs under the candidate feature output root, and
  `baseline_feature_manifest.json`, `baseline_feature_report.json`,
  `feature_registry.json`, `feature_audit.json`, and
  `feature_correlation_report.csv` under the candidate feature reports root.
- Does not approve WFA/modeling, metrics, predictions, proof scans, provider
  actions, staging, commit, push, or live/paper execution.

ES 2026 guarded downstream feature execution wrapper:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_downstream_feature_build
```

- Dry-run by default; writes no feature matrices and runs no Phase 4 subprocess
  unless the feature gate is ready and
  `--execute --approval-token APPROVE_ES2026_P1_PHASE4_FEATURE_BUILD_V1` is
  supplied.
- Current repo state returns
  `NO_GO_ES2026_P1_DOWNSTREAM_FEATURE_BUILD_EXECUTION` on a default dry run
  because completed Phase 4 candidate artifacts already exist and the upstream
  pre-execution feature gate fail-closes to avoid overwriting them.
- When the feature gate is ready, the wrapper validates the exact bounded
  Phase 4 command, expected ignored outputs, stale candidate feature roots, and
  generated-artifact staging before execution.
- If separately approved, the wrapper runs only the gate-defined ES 2026
  feature command and then validates the feature parquet, registry JSONs,
  `baseline_feature_manifest.json`, `baseline_feature_report.json`,
  `feature_audit.json`, and `feature_correlation_report.csv`: exact `ES 2026`,
  `PASS`/`WARN` with zero failures, matching candidate roots, matching
  label-manifest gate, positive feature count, matching feature-audit records,
  no forbidden feature leakage failures, matching output hash, no unexpected
  files, and no staged generated artifacts.
- Does not approve WFA/modeling, metrics, predictions, proof scans, provider
  actions, staging, commit, push, or live/paper execution.

ES 2026 downstream WFA split approval gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_downstream_wfa_split_gate --print-gate-json
```

- Console-only; writes no reports, creates no split plans, and runs no Phase 5
  subprocess.
- Starts from verified exact `ES 2026` Phase 4 feature evidence. The completed
  ES 2026 research-smoke split plan now lives at
  `reports/wfa/local_trade_es2026_p1_candidate/split_plan.json` with
  `profile=local_trade_es2026_p1_research_smoke`, exact `ES 2026`,
  `fold_count=4`, 4 selectable research folds, `failure_count=0`, and
  purge/embargo `31/31`.
- The gate uses the bounded `local_trade_es2026_p1_research_smoke` profile for
  research-smoke split evidence while validating the upstream
  `tier_3_forward` feature manifest. Existing valid split outputs are
  overwrite-protected; do not rerun this wrapper unless a separate repair or
  rerun plan is approved.
- The exact ES-only fully unavailable intermarket/Tier 1 feature warning is
  accepted for Phase 5 split planning only. It does not approve model training,
  imputation behavior, feature rescue, metrics, promotion, or live/paper work.
- Does not approve model training, model selection, metrics, predictions, proof
  scans, provider actions, staging, commit, push, or live/paper execution.

ES 2026 guarded downstream WFA split execution wrapper:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_downstream_wfa_split_build
```

- Dry-run by default; writes no split reports and runs no Phase 5 subprocess
  unless the WFA split gate is ready and
  `--execute --approval-token APPROVE_ES2026_P1_PHASE5_WFA_SPLIT_BUILD_V1` is
  supplied.
- The approved repair execution returned
  `EXECUTED_ES2026_P1_DOWNSTREAM_WFA_SPLIT_BUILD`: 1 planned command, 1 executed
  command, 0 command failures, 0 output failures, 2 expected ignored WFA report
  outputs, 2 generated outputs, 0 unexpected outputs, 0 staged generated paths,
  and 0 failures.
- The wrapper executed the exact bounded Phase 5 command:

```powershell
python -m scripts.phase5_wfa.build_wfa_splits --profile local_trade_es2026_p1_research_smoke --input-root data/feature_matrices/local_trade_es2026_p1_candidate --reports-root reports/wfa/local_trade_es2026_p1_candidate --profile-config configs/alpha_tiered.yaml --models-config configs/models.yaml --feature-manifest reports/features_baseline/local_trade_es2026_p1_candidate/baseline_feature_manifest.json --markets ES --years 2026
```

- The generated `reports/wfa/local_trade_es2026_p1_candidate/split_plan.json`
  is exact `ES 2026`, records feature-manifest gate `PASS`, purge/embargo
  `31/31`, `fold_count=4`, 4 selectable research folds, and `failure_count=0`.
- Does not approve model training, model selection, metrics, predictions, proof
  scans, provider actions, staging, commit, push, or live/paper execution.

ES 2026 downstream Phase 6 model gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_downstream_model_gate --print-gate-json
```

- Console-only; writes no reports, creates no predictions, and runs no Phase 6
  subprocess.
- Starts from exact ES 2026 feature registry evidence, an exact ES 2026 WFA
  split plan, safe model config, explicit Phase 6 CLI controls, and ignored /
  absent prediction and WFA model report artifacts.
- After the repaired split plan, this gate exposed
  `APPROVE_ES2026_P1_PHASE6_MODEL_SMOKE_V1` for one first-fold model smoke with
  `--max-folds 1` and `--write-predictions`. That wrapper has now been executed
  and produced prediction evidence, so the gate should now be treated as
  completed/overwrite-protected for this run.
- Does not approve metrics, model selection, proof scans, provider actions,
  staging, commit, push, or live/paper execution.

ES 2026 guarded downstream Phase 6 model wrapper:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_downstream_model_build
```

- Dry-run by default; writes no predictions or model reports and runs no Phase 6
  subprocess unless the model gate is ready and
  `--execute --approval-token APPROVE_ES2026_P1_PHASE6_MODEL_SMOKE_V1` is
  supplied.
- The approved wrapper returned
  `EXECUTED_ES2026_P1_DOWNSTREAM_MODEL_BUILD`: 1 planned command, 1 executed
  command, 0 command failures, 0 output failures, 3 expected ignored generated
  outputs, 3 generated outputs, 0 unexpected outputs, 0 staged generated paths,
  and 0 failures.
- Current prediction evidence is exact ES 2026 with
  `profile=local_trade_es2026_p1_research_smoke`, `run=local_trade_es2026_p1_model_smoke`,
  1 executed fold from 4 selectable folds, 122 features, 106,640 prediction
  rows, zero duplicate predictions, `artifact_evidence_ready=true`, and
  `failure_count=0`.
- When the model gate becomes ready, the wrapper validates the exact bounded
  Phase 6 command, expected ignored outputs, stale candidate model roots, and
  generated-artifact staging before execution.
- If separately approved, the wrapper runs only the gate-defined first-fold
  model smoke command and then validates the prediction parquet,
  `{run}_predictions_manifest.json`, and `{run}_wfa_report.json`: exact
  `ES 2026`, writes enabled, positive prediction count, zero duplicate
  predictions, artifact evidence ready, matching output hash, no unexpected
  files, and no staged generated artifacts.
- Does not approve metrics, model selection, proof scans, provider actions,
  staging, commit, push, or live/paper execution.

ES 2026 downstream Phase 8 metrics gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_downstream_metrics_gate --print-gate-json
```

- Console-only; writes no metrics/model-selection reports and runs no Phase 8
  subprocess.
- Starts from verified ES 2026 Phase 6 model-smoke prediction evidence, existing
  costs/model configs, explicit Phase 8 CLI controls, and ignored / absent
  metrics, model-selection, and phase8 report artifacts.
- After model-smoke evidence existed, this gate exposed
  `APPROVE_ES2026_P1_PHASE8_METRICS_V1` for one bounded diagnostics command
  with fixed policy/promotion thresholds. It does not use
  `--require-promotion-ready` and does not relax market/fold net blockers. The
  diagnostics have now been generated, so the gate should be treated as
  completed/overwrite-protected for this run.
- Does not approve model promotion, artifact freeze, proof scans, provider
  actions, staging, commit, push, or live/paper execution.

ES 2026 guarded downstream Phase 8 metrics wrapper:

```powershell
python -m scripts.validation.run_local_trade_es2026_p1_downstream_metrics_build
```

- Dry-run by default; writes no metrics/model-selection reports and runs no
  Phase 8 subprocess unless the metrics gate is ready and
  `--execute --approval-token APPROVE_ES2026_P1_PHASE8_METRICS_V1` is supplied.
- The approved Phase 8 diagnostics command generated the expected 8 ignored
  reports under `reports/metrics/local_trade_es2026_p1_candidate_model`,
  `reports/model_selection/local_trade_es2026_p1_candidate_model`, and
  `reports/phase8/local_trade_es2026_p1_candidate_model`.
- Current diagnostics are exact ES 2026 and structurally review-ready after the
  wrapper validator was aligned to the evaluator's `prediction_manifest_path`
  selection-report field. The generated outputs validate with zero output
  contract failures.
- When the metrics gate becomes ready, the wrapper validates the exact bounded
  Phase 8 command, expected ignored report outputs, stale candidate metrics
  roots, and generated-artifact staging before execution.
- If separately approved, the wrapper runs only the gate-defined Phase 8
  diagnostics command and then validates the metrics/model-selection JSON and
  CSV outputs: exact `ES 2026` prediction inputs, zero Phase 8 failures, no
  final-holdout use, no trading-semantics changes, diagnostics-only model
  selection, no unexpected report files, and no staged generated artifacts.
- Does not approve model promotion, artifact freeze, proof scans, provider
  actions, staging, commit, push, or live/paper execution.

ES 2026 downstream Phase 8 metrics review gate:

```powershell
python -m scripts.validation.build_local_trade_es2026_p1_downstream_metrics_review --print-review-json
```

- Console-only; writes no reports and runs no Phase 8, proof, promotion,
  staging, commit, push, or live/paper command.
- `--print-review-json` includes the empty `approval_gate` plus explicit
  `non_approval` flags for promotion/freeze, proof scans, generated outputs,
  and command execution.
- Starts from exact ES 2026 model-smoke prediction evidence plus the full
  expected Phase 8 metrics/model-selection artifact set.
- Current repo state returns
  `REVIEW_READY_ES2026_P1_DOWNSTREAM_METRICS_REVIEW` with model output `PASS`,
  metrics output `PASS`, 8 expected ignored existing reports, 0 generated
  outputs, 0 staged generated paths, and 0 failures.
- Current result decision: kill/revise this exact ES 2026 P1 baseline/model-smoke
  candidate rather than continue it as alpha evidence. The diagnostics report
  `research_alpha_ready=false`, `model_promotion_allowed=false`,
  `alpha_promoted=false`, negative gross return, negative net return, high cost
  drag, one market, one traded fold, nonpositive ES/fold net return, and missing
  statistical-validity evidence including PBO, Deflated Sharpe, Probabilistic
  Sharpe, bootstrap confidence intervals, multiple-testing adjustment,
  parameter stability, and regime breakdowns.
- Does not approve model promotion, artifact freeze, proof scans, provider
  actions, staging, commit, push, or live/paper execution.

Candidate-root manifest profile projection gate:

```powershell
python -m scripts.validation.project_local_trade_candidate_manifest_profile --proposal reports\pipeline_audit\local_trade_proof_status_promotion_proposal_20250618_20260613.json --source-manifest reports\pipeline_audit\causal_proof_candidates\local_trade_2025_2026_v1\causal_base_manifest.json --reports-root reports\pipeline_audit\local_trade_candidate_manifest_profile_projection --approved-markets HO,NG,RB --approved-years 2025,2026
```

- Projects only approved candidate-root `all_raw` PASS manifest metadata to the
  Phase 3 target profiles for `HO/NG/RB` 2025/2026.
- With `--reports-root`, writes one generated `causal_base_manifest.json` and
  one markdown summary per approved year under `reports/`; without it, remains
  console-only. The command never mutates parquet data.
- Fails closed if the candidate scope differs from the approved market-years,
  the source manifest is not PASS `all_raw`, selected outputs have warnings or
  failures, selected output hashes are missing/stale, or generated `data/**` or
  `reports/**` paths are staged.
- Does not accept repaired-root warnings, create accepted-warning files, run
  causal-base builds, labels, feature matrices, models, WFA splits, metrics,
  predictions, proof scans, downloads, or live/paper artifacts.

Acceptance checks:

- Output market-years match the resolved profile.
- `ts_event` has been converted to `ts`.
- Session, synthetic-row, roll-window, and degraded-row warnings are explicit.
- Staged status/statistics enrichment columns, when present, remain raw
  metadata/audit fields and are reported with missing/stale counts.
- For each processed market, synthetic missing OHLCV-1m minutes in
  `[2025-06-18, 2026-06-13)` are cross-checked against local `trades` DBN
  archives. A passing market validates older years by Databento no-trade
  convention evidence only; older years are not independently re-proven.
- The local trades gate proves no trade rows inside scanned synthetic OHLCV gap
  windows only; it is not a universal proof that no trades occurred everywhere.
- Production/research profiles fail when strict raw metadata is missing.

Stop conditions:

- Missing raw inputs for expected profile market-years.
- Missing or invalid OHLCV, definition, or trades DBN coverage for the
  `[2025-06-18, 2026-06-13)` local-trades audit window.
- Trade rows, unresolved adjacent contract context, or unverified coverage
  appear inside synthetic missing OHLCV-1m minutes.
- Synthetic/degraded/roll-window thresholds exceed configured limits.
- Session config is missing or hardcoded calendar fallback is required without
  an explicit reason.

### 3. Build Labels

Purpose: create future-looking labels and cost-aware target validity flags.

Command:

```powershell
python -m scripts.phase3_labels.build_labels --profile tier_1 --input-root data\causally_gated_normalized
```

Bounded market/year filters:

```powershell
python -m scripts.phase3_labels.build_labels --profile tier_3_holdout --input-root data\causally_gated_normalized --output-root data\labeled --reports-root reports\labels\local_trade_baseline\data_causally_gated_normalized_2025 --markets 6E,CL,ES,ZN --years 2025
```

Inputs:

- `data/causally_gated_normalized/{market}/{year}.parquet`
- Optional explicit causal candidate roots, such as
  `data/causal_proof_candidates/local_trade_2025_2026_v1/{market}/{year}.parquet`
- `configs/costs.yaml`

Outputs:

- `data/labeled/{market}/{year}.parquet`
- `reports/labels/`

Acceptance checks:

- Label horizons respect intraday/session validity.
- Target columns are present and separated from feature columns downstream.
- Cost-aware validity flags are generated from configured costs, not ad hoc
  assumptions.
- `--markets` and `--years` filters select only market-years inside the
  resolved profile, and label manifests record `input_selection`.

Stop conditions:

- Selected market/year filters resolve to no Phase 3 inputs.
- Target construction uses future rows beyond the allowed horizon.
- Session boundary logic permits invalid overnight or cross-session labels.
- Cost config is missing or provisional where a strict profile requires final
  costs.

### 4. Build Baseline Feature Matrix

Purpose: build OHLCV-only baseline and L0 regime features plus metadata, target,
and registry columns.

Command:

```powershell
python -m scripts.phase4_features.build_baseline_features --profile tier_1
```

Inputs:

- `data/labeled/{market}/{year}.parquet`
- `configs/costs.yaml`

Outputs:

- `data/feature_matrices/baseline/{market}/{year}.parquet`
- `data/feature_matrices/baseline/feature_cols.json`
- `data/feature_matrices/baseline/target_cols.json`
- `data/feature_matrices/baseline/metadata_cols.json`
- `data/feature_matrices/baseline/excluded_cols.json`
- `reports/features_baseline/`

Feature audit gate:

- Every feature admitted to a registry must have source column/artifact,
  availability timestamp, update frequency, as-of join behavior, lookback
  window, NaN/warmup handling, economic rationale, leakage-risk classification,
  train-only transform status, and drift/decay check status.
- Optional or staged metadata fields, including status/statistics enrichment,
  require an explicit feature-hypothesis approval before model use.
- New Phase 9 feature hypotheses must produce the same audit record before they
  can advance from feasibility work to WFA or promotion review.

Acceptance checks:

- Feature registry excludes target, leakage, timestamp, and metadata columns.
- Raw status/statistics enrichment columns are excluded from default features;
  model use requires a later feature-hypothesis change with leakage checks and
  registry updates.
- Feature audit records exist and match `feature_cols.json`.
- Feature rows line up with label rows.
- Baseline features are causal and do not use final-holdout full-sample
  statistics.

Stop conditions:

- Any target/leakage column enters `feature_cols.json`.
- Any feature lacks source, availability timestamp, update frequency, as-of join
  behavior, lookback, NaN/warmup handling, economic rationale, leakage-risk
  classification, train-only transform status, or drift/decay status.
- Cost config is provisional under strict research settings.
- Feature matrix row count or market-year scope does not match labels.

Downstream blockers:

- Phase 5 cannot build split plans from feature matrices with missing audit
  records, target/leakage columns, stale registries, or label row mismatches.
- Phase 6 cannot train from unaudited features, provisional-cost feature
  matrices, or feature registries that do not exactly match the matrix columns.
- Phase 8, promotion review, and artifact freeze cannot cite feature-derived
  evidence unless Phase 4 feature audit, registry, row-alignment, and
  generated-artifact hygiene evidence passes.
- Phase 9 feature hypotheses remain feasibility work only until they produce
  the same audit record required for promoted Phase 4 features.

### 5. Build WFA Splits

Purpose: build deterministic train/test fold definitions with purge and embargo.

Validation design policy:

- Chronological WFA with purge and embargo is the approved validation design for
  this pipeline unless a separate bounded plan explicitly approves a purged-CV
  design.
- Shuffled CV, full-dataset CV, and any CV that lacks documented purge/embargo
  coverage are blocked before Phase 6.

Validation role definitions:

- Training rows are the only rows used to fit feature transforms, imputers,
  scalers, models, and any train-fold statistics.
- Validation rows, when used, must be an inner or nested split inside the
  training window and are the only rows allowed for model-family,
  hyperparameter, threshold, feature-family, or policy selection.
- If no inner validation split is defined, model, threshold, feature, and policy
  choices must be fixed by predeclared config or hypothesis records before the
  WFA test fold is scored.
- Test rows are WFA out-of-sample rows used for fold scoring only; they cannot
  drive training, feature selection, threshold selection, model selection,
  cost/sizing changes, or retry decisions.
- Locked holdout and forward rows are evaluation-only and cannot be used as
  training or validation evidence unless a separate guarded final-holdout run is
  explicitly approved.

Command:

```powershell
python -m scripts.phase5_wfa.build_wfa_splits --profile tier_1
```

Inputs:

- `data/feature_matrices/baseline/`
- `configs/alpha_tiered.yaml`
- `configs/models.yaml`

Outputs:

- `reports/wfa/split_plan.json`

Acceptance checks:

- Every fold has positive train and test rows.
- Split plan profile, resolved profile, markets, years, config hash, purge, and
  embargo are recorded.
- Every split row or window is assigned exactly one role: train, inner
  validation when used, test/OOS, locked holdout, or locked forward.
- Model, threshold, feature, and policy selection evidence is limited to
  training rows and declared inner-validation rows; test, holdout, and forward
  rows remain selection-free.
- Final-holdout rows are excluded unless an explicit final-holdout split run is
  being built with the appropriate guard.

Stop conditions:

- Empty folds.
- Profile/year/market mismatch.
- Missing, overlapping, or ambiguous train/validation/test/holdout/forward role
  assignments after purge and embargo are applied.
- Any full-dataset feature selection, model selection, threshold tuning, cost
  tuning, or policy selection uses WFA test rows, locked holdout rows, or locked
  forward rows.
- Missing provenance required by downstream WFA.

Downstream blockers:

- Phase 6 cannot train until the split plan records exact scope, positive folds,
  train/validation/test/holdout role assignments, purge/embargo, and provenance.
- Phase 8 cannot evaluate predictions from runs whose split plan is missing,
  stale, mismatched to the feature matrix, or contaminated by selection on test,
  locked holdout, or forward rows.
- Statistical-validity, promotion, and artifact-freeze claims cannot cite WFA
  results unless the split design proves chronological OOS separation and
  horizon-overlap controls.
- Final-holdout or forward-validation use remains blocked unless the appropriate
  guarded evaluation path is separately approved.

### 6. Train WFA Models And Save OOS Predictions

Purpose: fit baseline models on train folds and write out-of-sample predictions
for test folds.

Command:

```powershell
python -m scripts.phase6_wfa.run_wfa --profile tier_1 --matrix baseline --run baseline
```

Shard pattern for large runs:

```powershell
python -m scripts.phase6_wfa.run_wfa --profile tier_1 --matrix baseline --run baseline_s1of8 --fold-shard-count 8 --fold-shard-index 1
python -m scripts.phase6_wfa.run_wfa --profile tier_1 --matrix baseline --run baseline_s2of8 --fold-shard-count 8 --fold-shard-index 2
python -m scripts.phase6_wfa.combine_wfa_predictions --manifest-pattern "reports/wfa/baseline_s*of8_predictions_manifest.json" --run baseline --split-plan reports/wfa/split_plan.json --require-all-folds
```

Repeat the shard run for each 1-based shard index and use a unique shard run
name, such as `baseline_s1of8` through `baseline_s8of8`, before combining.

Inputs:

- `data/feature_matrices/baseline/`
- `data/feature_matrices/baseline/feature_cols.json`
- `reports/wfa/split_plan.json`
- `configs/models.yaml`

Outputs:

- `data/predictions/{run}/oos_predictions.parquet`
- `reports/wfa/{run}_predictions_manifest.json`
- `reports/wfa/{run}_wfa_report.json`

Model risk gate:

- Phase 6 results are not trust evidence unless the run records the model family
  rationale, hyperparameter search budget, deterministic seed policy,
  regularization settings, class imbalance handling, calibration method/checks,
  and feature-importance stability checks.
- Hyperparameter, threshold, target, feature, market, and cost decisions must be
  made before locked OOS/holdout review and must not be changed to rescue a
  completed result.

Acceptance checks:

- Imputer/scaler/model fit happens on train fold only.
- Predictions are test-fold rows only.
- Model-risk metadata records hyperparameter budget, seeds, calibration, class
  imbalance handling, regularization, and feature-importance stability.
- Prediction manifest hash, row count, path, profile, resolved profile, markets,
  years, and split-plan provenance match actual artifacts.
- `artifact_evidence_ready=true`.

Stop conditions:

- Any stale output path is detected.
- Missing model-risk metadata or a model run that exceeds its predeclared
  hyperparameter budget.
- Prediction manifest does not match actual parquet.
- Fold failure count is nonzero.
- Model collapses to constant or class-prior-only predictions without an
  explicit diagnostic decision.

Downstream blockers:

- Phase 8 cannot evaluate a run unless prediction parquet, prediction manifest,
  WFA report, split-plan provenance, and artifact evidence match exactly.
- Costed metrics, statistical-validity checks, promotion review, and artifact
  freeze cannot cite model outputs with missing model-risk metadata, fold
  failures, stale outputs, or unapproved hyperparameter/search expansion.
- Model-selection, threshold, feature, target, market, or cost changes after
  locked OOS review block promotion and require a new predeclared research line.
- Constant, class-prior-only, or collapsed predictions remain diagnostic only
  unless an explicit approved diagnostic decision keeps the run in scope.

### 8. Evaluate Predictions

Purpose: score saved OOS predictions with deterministic policy, costs, model
selection diagnostics, and promotion gates.

Command:

```powershell
python -m scripts.phase8_model_selection.evaluate_predictions --run baseline
```

Locked-run structural check pattern:

```powershell
python -m scripts.phase8_model_selection.evaluate_predictions --predictions data/predictions/tier1_locked_baseline_20260616/oos_predictions.parquet --predictions-manifest reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json --run tier1_locked_baseline_20260616 --require-promotion-ready
```

Inputs:

- `data/predictions/{run}/oos_predictions.parquet`
- `reports/wfa/{run}_predictions_manifest.json`
- `configs/costs.yaml`
- `configs/models.yaml`

Outputs:

- `reports/metrics/{run}_metrics.json`
- `reports/model_selection/`
- `reports/phase8/metrics.json`
- `reports/phase8/alpha_promotion_decision.json`

Statistical validity gate:

- Phase 8 promotion review must report Probability of Backtest Overfitting
  (PBO) or an explicit no-PBO applicability reason, Deflated Sharpe,
  Probabilistic Sharpe, bootstrap confidence intervals, multiple-testing
  adjustment, parameter stability, and regime breakdowns.
- Gross/net metrics, Sharpe-like summaries, and isolated fold/market wins are
  diagnostic only until statistical-validity evidence passes.
- If a test is not applicable to the current run, the report must state the
  reason and the substitute evidence required before promotion.

Acceptance checks:

- Prediction manifest matches actual prediction parquet.
- Final holdout is not consumed for selection/calibration.
- Costs, turnover, active-signal rows, market/fold/year breakdowns, and blocker
  reasons are reported.
- Statistical-validity evidence is present, including PBO or applicability
  decision, Deflated Sharpe, Probabilistic Sharpe, bootstrap confidence
  intervals, multiple-testing adjustment, parameter stability, and regime
  breakdowns.
- Structural pass and alpha promotion are separate decisions.

Stop conditions:

- `final_holdout_touched=true` for research selection.
- Artifact evidence is stale or mismatched.
- Gross/net/cost gates fail.
- Statistical-validity evidence is missing, stale, not run, not applicable
  without substitute evidence, or fails promotion thresholds.
- Promotion check fails; this is expected for the locked negative Tier 1
  baseline and must not be "rescued" with threshold tuning.

### 9. Research Harnesses

Purpose: run bounded feasibility tests for new target/feature hypotheses after
baseline failure.

Rules:

- Pre-register hypothesis, scope, controls, metrics, and stop rules.
- Run smoke first.
- Feature hypotheses require the Phase 4 feature audit gate before WFA or
  promotion review.
- Research harnesses that compare variants must define multiple-testing,
  parameter-stability, and regime-breakdown evidence before promotion.
- Do not use a stopped branch as a "new" hypothesis.
- Do not proceed from oracle/feasibility evidence directly to full WFA.
- Require materially different target or feature work after a stopped branch.

Guarded alpha discovery batch runner:

- `run_alpha_discovery.bat` is a launcher, not pipeline authority; it delegates
  to `python -m scripts.validation.run_alpha_discovery` and writes ignored logs
  under `logs/alpha_discovery/`.
- Allowed modes are `preflight`, `source-tests`, `discovery-packet`,
  `discovery-run`, and `review`; the runner must stop at the current approved
  discovery boundary.
- `discovery-run` requires `--approve-discovery-run`, the exact configured
  approval token, absent/ignored expected outputs, and one generated JSON/MD
  review before any next decision.
- A runner-completed status means the wrapper finished its bounded job, not
  that the candidate passed. Candidate pass/fail must be read from the
  generated JSON decision, and any `STOP_*` decision stops that candidate
  boundary even if the subprocess exit code is zero.
- The runner cannot approve confirmation smoke, locked smoke, WFA/modeling,
  Phase 8 diagnostics, tuning, promotion, registry/status mutation, artifact
  staging, commits, pushes, paper trading, or live trading.

Current implemented harnesses live under `scripts/phase9_research/`.

## Validation Commands

Coverage and artifact-readiness check:

```powershell
python -m scripts.validation.check_tier_2_coverage --profile tier_1 --stage all
```

Focused WFA/Phase 8 tests:

```powershell
python -m pytest tests\phase7_wfa\test_run_wfa.py tests\phase8_model_selection\test_evaluate_predictions.py -q
```

Common smoke checks:

```powershell
python -m pytest -q tests\phase1A_download\test_download_databento_raw.py tests\validation\test_model_registry.py
python -m py_compile scripts\phase1A_download\download_databento_raw.py scripts\phase1B_convert\convert_databento_raw.py scripts\phase2_causal_base\build_causal_base_data.py scripts\phase3_labels\build_labels.py scripts\phase4_features\build_baseline_features.py scripts\phase5_wfa\build_wfa_splits.py scripts\phase6_wfa\run_wfa.py scripts\phase8_model_selection\evaluate_predictions.py
```

Doc-only validation after editing this file:

```powershell
rg -n "scripts\.(buil[d]_|run_execution_cost[s]|run_gat[e])|Phase (7[A]|8[A]|2[2])" PROJECT_OUTLINE.md README.md docs
git diff --check
git status --short
```

## Current Status Appendix

Status date: June 17, 2026 local project notes.

Historical/non-authoritative note: this appendix is dated local status context,
not current model-trust evidence or approval. Refresh any claim here from
primary artifacts, manifests, command output, and current repo state before
using it for research conclusions, promotion, artifact freeze, or follow-on
execution.

Locked Tier 1 baseline:

- Run: `tier1_locked_baseline_20260616`.
- Scope: `tier_1 -> tier_1_research`, markets `ES`, `CL`, `ZN`, `6E`,
  years 2023-2024.
- Predictions:
  `data/predictions/tier1_locked_baseline_20260616/oos_predictions.parquet`.
- Manifest:
  `reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json`.
- Metrics: `reports/metrics/tier1_locked_baseline_20260616_metrics.json`.
- Promotion decision: `reports/phase8/alpha_promotion_decision.json`.
- Phase 2 causal data: `WARN`, full Tier 1 scope, `authoritative=true`,
  failures `0`, warnings `4`.
- Phase 3 labels: `PASS`, full Tier 1 scope, failures `0`.
- Phase 4 baseline features: `WARN`, full Tier 1 scope, failures `0`.
- Phase 5 split plan: `PASS`, folds `48`, markets `4`, failures `0`.
- Phase 6 WFA: shard-combined, predictions `4,616,712`, folds `48`,
  failures `0`, `artifact_evidence_ready=true`.
- Phase 8: structural evaluation passed, promotion failed.

Costed OOS policy result:

- Policy rows: `1,154,178`.
- Trades/active signal rows: `780`.
- Gross dollars: `-20,287.50`.
- Costs: `22,357.88`.
- Net dollars: `-42,645.38`.
- Net Sharpe-like: `-5.1086`.
- Cost drag to absolute gross: `1.1021`.
- `research_alpha_ready=false`.
- `model_promotion_allowed=false`.
- `promoted=false`.

Current decision:

- Decision: `TIER1_LOCKED_BASELINE_NO_GO`.
- Do not promote this model or policy.
- Do not tune thresholds against this locked run.
- Do not rerun near-neighbor policy variants to rescue this baseline.
- Do not run full-market/full-fold WFA again for this same baseline line.
- Do not treat small positive threshold pockets as alpha.

Stopped research branches:

- Tier 1 cost-clearability feasibility:
  `STOP_BRANCH_PERMANENTLY`.
- Market-balanced cost-clearability follow-up:
  `STOP_BRANCH_PERMANENTLY`.
- Both are oracle/feasibility evidence only, not executable PnL or strategy PnL.
- Do not proceed from either branch to direction modeling, policy work, or full
  Tier 1 WFA.

Next valid work:

- A separate research direction with a new hypothesis and pre-registered stop
  rules.
- Acceptable categories: new target-construction research, new feature-generation
  research, or a genuinely new ES-only custom hypothesis on unused folds from
  `reports/wfa_phase9_es_tier2_refresh/split_plan.json`.
- Do not reuse the failed built-in ES feature-family sweep, the stopped Phase 9
  hypotheses, or cost-clearability rescue variants as "new" work.

## Known Limitations

- Continuous-contract research artifacts do not define directly tradable
  contract execution.
- Contract-specific execution mapping is still required before live-readiness
  claims.
- Independent historical L1/trades proof for all gap cases is unavailable under
  the current subscription; Phase 2 local-trades gap proof is limited to
  `[2025-06-18, 2026-06-13)` and older years rely on a documented convention
  inference.
- Several future-stage concepts from the old `project_layout.md` were
  aspirational and are not current runnable commands. This file documents the
  current implemented command surface.


## Reporting Standard

Reports should be concise, evidence-oriented, and reproducible.

Prefer:

- finding;
- evidence path or metric;
- interpretation;
- blocker or next gate.

Do not present gross-only results as tradable evidence. Do not present failed or warning-status outputs as promotion-ready.

## Final Research Posture

The project can only support research conclusions after the relevant phase gates pass with reproducible local evidence. A favorable metric is not enough. A valid conclusion requires audited data lineage, leakage-safe targets/features, locked validation, realistic costs, documented failures, and reproducible reports.
