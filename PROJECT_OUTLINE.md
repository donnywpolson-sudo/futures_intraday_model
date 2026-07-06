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

## Data Manifest And Rule Index

Use this section as the first lookup point for data-phase rules, durable manifests,
and generated evidence locations. It is an index, not a second source of truth.

- Durable data rules live in this file:
  - `Non-Negotiable Data Rules` defines canonical active roots and source-of-truth
    handling.
  - `Detailed Pipeline Runbook` defines Phase 1A, Phase 1B, and Phase 2 command
    patterns, acceptance checks, stop conditions, and the standard DBN
    redownload/rebuild policy. The historical Phase 1C validator command is now
    treated as an internal Phase 1B validation step.
- Durable coverage and policy manifests:
  - `configs/data_manifest.yaml`: canonical Phase 1A/1B/2 coverage policy,
    expected markets/years, allowed missing/extra pairs, duplicate policy, and
    cleanup exclusions. Update this only when durable expected coverage or policy
    changes.
  - `configs/phase1a_required_schema_exceptions.yaml`: explicit required-schema
    exceptions for DBN coverage gates.
  - `configs/alpha_tiered.yaml`: profile market/year definitions consumed by
    data, research, holdout, and forward gates.
- Current generated data-health evidence:
  - `reports/data_manifest/`: generated master data health matrix and data
    manifest coverage reports.
  - `reports/raw_ingest/` and `reports/raw_readiness/`: Phase 1B raw/DBN
    alignment, optional-schema, and raw-readiness validation reports.
  - `reports/data_audit/current_state/`: current-state ledgers, disposition
    packets, cleanup/archive plans, active-root gates, and exact-scope repair
    evidence.
  - `reports/causal_base/**/causal_base_manifest.json`: Phase 2 build manifests
    for causal/session-normalized parquet outputs.
- Run-specific repair or redownload plans belong under
  `reports/data_audit/<topic>_<timestamp>/` or
  `reports/data_audit/current_state/<topic>_<timestamp>/`. They should record
  exact scope, commands, guards, artifacts, hashes, approvals, forbidden actions,
  and stop conditions. Do not encode one-off run packets inside
  `configs/data_manifest.yaml` unless they change durable coverage policy.
- Future DBN redownloads must follow the standard redownload/rebuild policy below:
  Phase 1A request-plan preflight before provider download, staged DBN
  acquisition only after that preflight passes or an explicit bounded override
  is approved, post-download DBN file/manifest validation before active
  replacement, Phase 1B raw parquet build plus immediate raw/DBN validation
  second, and Phase 2 readiness/staged causal rebuild last.

## Active Layout

Primary code and metadata areas:

```text
configs/                       configuration and profile definitions
docs/                          durable documentation and audit notes
live_ops/                      live/paper-operation scaffolding; not research proof
manifests/                     small tracked rebuild/audit metadata
scripts/phase1A_download/      Databento DBN archive download planning/execution
scripts/phase1B_convert/       DBN to raw parquet conversion
scripts/phase1C_validate/      legacy/internal Phase 1B raw DBN/parquet validators
scripts/phase2_causal_base/    causal/session-normalized base data builders
scripts/phase3_labels/         label and target construction
scripts/phase4_features/       baseline feature matrix builders
scripts/phase5_wfa/            WFA split builders
scripts/phase6_wfa/            WFA training, shard-combine, and OOS prediction wrappers
scripts/phase7_wfa/            legacy internal WFA engine; not a runnable workflow phase
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
| 1A | Preflight planned DBN requests before provider download, then download/stage DBNs and validate files/manifests | `scripts.phase1A_download.download_databento_raw` | `data/dbn/.../*.dbn.zst`, manifests, and validation reports |
| 1B | Recheck accepted Phase 1A DBN evidence, convert DBNs to raw parquet, then immediately validate raw parquet against DBNs, manifests, source hashes, sidecars, definition joins, and row/schema sanity | `scripts.phase1B_convert.convert_databento_raw`; internal validator `scripts.phase1C_validate.audit_raw_dbn_alignment` | `data/raw/{market}/{year}.parquet` and `reports/raw_ingest/*` |
| 2 | Run readiness gate, build causal/session-normalized data, then validate causal outputs | `scripts.phase2_causal_base.build_causal_base_data` | `data/causally_gated_normalized/{market}/{year}.parquet` |
| 3 | Build labels/targets with explicit entry lag and horizon semantics | `scripts.phase3_labels.build_labels` | `data/labeled/{market}/{year}.parquet` |
| 4 | Build baseline feature matrices from causal inputs only | `scripts.phase4_features.build_baseline_features` | `data/feature_matrices/baseline/{market}/{year}.parquet` |
| 5 | Build chronological WFA split plans with purge/embargo rules | `scripts.phase5_wfa.build_wfa_splits` | `reports/wfa/split_plan.json` |
| Internal | Legacy internal WFA engine used by Phase 6; not a runnable pipeline phase | `scripts.phase7_wfa.*` | no standalone output; internal implementation only |
| 6 | Train WFA models and write out-of-sample predictions, then combine prediction shards | `scripts.phase6_wfa.run_wfa`; `scripts.phase6_wfa.combine_wfa_predictions` | `data/predictions/{run}/oos_predictions.parquet` and WFA reports/manifests |
| 8 | Evaluate predictions, costs, policy alignment, and promotion readiness | `scripts.phase8_model_selection.*` | `reports/phase8/*` |
| 9 | Run bounded research harnesses and adversarial audits | `scripts.phase9_research.*` | `reports/pipeline_audit/*` or focused reports |
| 10 | Guard locked holdout/forward evaluation | `scripts.final_holdout.guard_final_holdout` | holdout approval/block evidence |
| 11 | Freeze approved research artifacts only after explicit approval | `scripts.artifact_freeze.freeze_research_artifacts` | frozen artifact metadata |

`scripts.phase7_wfa` is the legacy internal WFA engine, not a runnable pipeline
phase. Run Phase 6 through `scripts.phase6_wfa.*`; changes to the legacy engine
must be validated as Phase 6 WFA changes before Phase 6 runs consume them.

## Non-Negotiable Data Rules

- Raw Databento DBN/ZST archives are immutable source artifacts.
- Active data-root chain: `data/dbn` -> `data/raw` ->
  `data/causally_gated_normalized` -> `data/labeled` ->
  `data/feature_matrices` -> `data/predictions`.
- Each root is the only active/source-of-truth root for its corresponding
  artifact class in code defaults, manifests, readiness checks, and pipeline
  decisions:
  - `data/dbn`: DBN/ZST source archives.
  - `data/raw`: raw parquet.
  - `data/causally_gated_normalized`: causal/session-normalized modeling
    inputs.
  - `data/labeled`: labels and target-ready datasets.
  - `data/feature_matrices`: feature matrices and feature-registry outputs.
  - `data/predictions`: model prediction artifacts.
- DBN `stype_in` policy is schema-specific:
  - `definition` DBNs are the current approved exception and may use
    `stype_in=parent` with `{MARKET}.FUT` symbols. Definition manifests should
    not be redownloaded only because a parent-stype audit flags them.
  - Canonical `ohlcv-1m`, `status`, and `statistics` DBNs should use
    `stype_in=continuous` with `{MARKET}.v.0` symbols unless a separate
    row-specific exception is explicitly approved.
  - A parent-stype manifest audit is therefore not one defect class: definition
    parent rows are accepted by policy, while non-definition parent rows require
    row-level disposition, redownload, equality proof, or an explicit exception.
- Candidate, staging, repair, quarantine, and report-provenance roots may be
  temporary evidence only; they are not active/source-of-truth roots unless a
  bounded approval explicitly promotes their artifacts into the canonical chain.
- `data/archive` may contain old copies only as stale/dead archive evidence; it
  is not an active/source-of-truth root and must not be used for code defaults,
  manifests, readiness checks, pipeline decisions, or pipeline inputs.
- Phase 1 preserves raw event timestamp semantics.
- Phase 2 is the first phase allowed to session-normalize, mark synthetic/degraded rows, and convert into causal modeling inputs.
- Do not fill missing 1-minute bars before the causal base phase.
- Sparse trade-derived OHLCV markets require explicit no-trade and roll-window handling.
- Every research result must be traceable back to source data, config, profile, and report/manifest evidence.

### Degraded Data Policy

Degraded vendor sessions may exist in raw and causal files for auditability, but
they are not trainable data unless a separate proof shows the degraded flag was
incorrectly assigned.

- `degraded_raw_quality` readiness exceptions are file-creation exceptions only;
  they do not approve labels, features, WFA, model training, model selection,
  paper, or live use of degraded sessions.
- Phase 2 owns degraded-session gating. Every causal parquet must persist
  `data_quality_degraded`, `session_data_quality_degraded`,
  `trainable_data_quality`, `causal_valid`, and `causal_invalid_reason`.
- Any session containing degraded raw rows must remain
  `session_data_quality_degraded=true`, `trainable_data_quality=false`, and
  `causal_valid=false`.
- Degraded-only rows must have `causal_invalid_reason=degraded_session`;
  degraded rows with additional invalid gates must include `degraded_session` in
  the pipe-delimited `causal_invalid_reason`.
- Downstream phases must treat `causal_valid=false` as a hard exclusion from
  labels, features, WFA, model training, and model-selection evidence.
- Do not add global degraded-row threshold waivers. Any future exception must be
  market/year/profile scoped with evidence paths.

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

Baseline taxonomy before model trust:

- `flat/no-trade`: confirms evaluation, costs, and reporting do not manufacture
  PnL when no position is taken.
- `cost-only sanity`: applies the configured cost model to known turnover or
  simple activity assumptions before alpha claims.
- `simple trend`: uses causal price/momentum inputs only and must obey the same
  splits, costs, and risk rules as complex models.
- `simple mean-reversion`: uses causal reversal or distance-from-recent-price
  inputs only and must be evaluated under identical gates.
- `volatility-regime`: tests whether behavior survives high/low volatility or
  session/regime partitions without using future information.
- `order-flow/volume/liquidity-proxy`: allowed only when the underlying fields
  have passed feature-availability and leakage audits.

Baseline acceptance and reporting criteria:

- `flat/no-trade` must report zero-position PnL, turnover, costs, and metric
  sanity checks so the evaluation path cannot manufacture alpha from reporting
  or aggregation errors.
- `cost-only sanity` must use the same cost, split, session, and position
  assumptions as the candidate policy and must show the cost drag implied by
  the tested turnover before any alpha claim is accepted.
- `simple trend` must predeclare lookback windows, causal price inputs, and
  signal direction, then report fold/market/year gross and net metrics under
  the same WFA and risk rules as the candidate model.
- `simple mean-reversion` must predeclare reversal windows, distance measures,
  and session/regime handling, then report the same fold/market/year and
  high/low-volatility breakdowns as the candidate model.
- `volatility-regime` must use only causal regime labels, report high/low
  volatility and session/regime partitions, and state whether the candidate
  edge survives outside a single favorable regime.
- `order-flow/volume/liquidity-proxy` baselines are accepted only when the
  fields are available at decision time, pass feature/leakage audits, and use
  the same fill, cost, split, and risk assumptions as the candidate model.
- Every baseline report must include scope, causal inputs, feature set, config
  hash or path, split plan, cost policy, gross/net metrics, fold coverage,
  warnings, failure modes, and a no-retune statement.

Complex models cannot be trusted unless they beat the simplest relevant
baseline under the same data scope, split plan, cost model, position policy,
and risk assumptions. A baseline failure is diagnostic evidence, not a reason to
retune the complex model after locked OOS review.

## Mandatory Gates Before Model Trust

The following gates are required before any model, WFA, policy, promotion, or
artifact-freeze result can be treated as trust evidence. A phase name or
successful command exit is not sufficient; each gate must have explicit inputs,
outputs, acceptance checks, stop conditions, and downstream blockers recorded in
its manifest or report evidence.

Shared gate evidence format:

- Scope: profile, markets, years, rows/files, configs, source hashes, output
  roots, report paths, and whether outputs are active, staged, or historical.
- Acceptance: exact pass/warn/fail criteria, allowed warnings, and required
  primary evidence paths.
- Stop conditions: data gaps, stale artifacts, schema/hash mismatches, leakage
  risks, provisional costs, post-test retuning, or missing provenance that
  blocks downstream use.
- Downstream use: which later phases may consume the evidence, which claims are
  still blocked, and which generated artifacts must remain untracked.

Phase sections below list only phase-specific command patterns and deltas.
Generic model-trust blockers are governed by the shared gates in this section.

### Raw Data And Metadata Gate

Placement: after Phase 1A DBN/archive validation and Phase 1B raw parquet
build plus raw/DBN validation, before Phase 2 causal/session normalization.

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

minimum execution-realism evidence:

- Spread evidence must name the source, timestamp alignment, sampling window,
  and whether the simulation crosses, joins, or otherwise models the spread.
- Commission, exchange fee, clearing/NFA fee, and broker-fee evidence must cite
  the configured source and effective date or explicitly mark costs provisional.
- Slippage and delay evidence must state the assumed delay from signal to order
  and order to fill, the price reference used, and why the assumption is not
  better than signal-time availability permits.
- Fill, partial-fill, rejection, and queue-position assumptions must be explicit;
  missing evidence blocks promotion rather than defaulting to perfect fills.
- Contract multiplier, tick value, point value, and contract-count conversion
  must reconcile signal units to dollars by market and profile.
- Liquidity, capacity, and market-impact limits must be reported for every
  promoted policy; absent evidence blocks promotion for size-sensitive or
  illiquid-window strategies.
- Provisional spread, slippage, fill, fee, capacity, or multiplier evidence may
  support diagnostics only and must be recorded as a downstream blocker before
  promotion, artifact freeze, paper, or live claims.

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

Portfolio/risk minimum evidence records:

- capital base, account currency, allocation scope, and whether capital is
  hypothetical, provisional, or approved for research comparison only;
- contract multiplier, tick value, contract-count conversion, and margin source
  used for every market in the evaluated policy;
- leverage cap, per-trade loss limit, daily loss limit, drawdown limit,
  position limit, concentration limit, and volatility-targeting or sizing rule;
- broker, exchange, and account constraints that could reject, reduce, or
  throttle a proposed position;
- liquidity, capacity, market-impact, and turnover limits tied to the same
  spread/slippage/fill evidence used by the Backtest And Cost Gate;
- stale-data, stale-signal, order-throttle, risk-off, and kill-switch controls
  required before any portfolio/risk claim is accepted;
- stress scenarios covering gap moves, volatility shocks, liquidity droughts,
  correlated market losses, margin increases, and missing or delayed inputs.

Each record must be labeled `PASS`, `WARN`, or `FAIL`. `WARN` and manual-review
items remain downstream blockers until the report names the accepted exception,
review owner, evidence path, stale-risk note, and claims still disallowed.

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

Statistical validity applicability and threshold policy:

- PBO, or an explicitly equivalent overfit diagnostic, is required for any
  search process that compares multiple targets, feature families, models,
  thresholds, markets, cost assumptions, sizing policies, or stopped branches.
- Deflated Sharpe Ratio and Probabilistic Sharpe Ratio are required for any
  Sharpe-like promotion claim. If the primary metric is not Sharpe-like, the
  report must mark the item `NOT_APPLICABLE_WITH_REASON` and name the substitute
  uncertainty and multiple-testing evidence.
- Bootstrap or walk-forward confidence intervals are required for every primary
  metric used in a promotion, freeze, or model-trust claim.
- Multiple-testing adjustment must cover the complete tested search surface,
  including failed, stopped, and diagnostic-only variants that could otherwise
  create false confidence.
- Parameter stability, feature stability, and fold/market/year/regime
  consistency are required before any stable-edge or robust-alpha claim.
- Every item must record `PASS`, `FAIL`, or
  `NOT_APPLICABLE_WITH_REASON`. Missing evidence is `FAIL` for promotion,
  artifact freeze, and model-trust claims.
- Numeric thresholds must be predeclared in an approved config, protocol, or
  report before locked review. If no threshold authority exists, the result is
  blocked rather than accepted by narrative judgment.

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

Paper/Live Readiness Gate:

- This gate is future and non-authorizing. It must not be used as promotion,
  paper-trading, live-trading, broker, or production-readiness evidence until a
  separate approved runbook, validation suite, and evidence manifest exist.
- Required future evidence includes contract-specific symbol mapping, broker
  account constraints, margin and buying-power checks, order type semantics,
  order simulation, fill/partial-fill/rejection handling, latency and delay
  assumptions, order throttles, market-hours/session guards, stale-data guards,
  stale-prediction guards, and self-match or duplicate-order prevention.
- Required future risk controls include position limits, leverage limits,
  max-loss rules, drawdown response, volatility and liquidity shock handling,
  kill-switch controls, manual override, rollback, incident logging, and
  post-trade reconciliation.
- Required future model/ops controls include frozen production config,
  model-version mapping, feature generation parity, training-serving skew
  checks, prediction drift monitoring, calibration monitoring, missing-input
  handling, alert routing, and operator acceptance criteria.
- Until those controls have primary evidence, every paper/live readiness item is
  `manual evidence review only` and remains a blocker for paper/live claims.

Until that gate exists and passes, `live_ops/` content is scaffolding only and
must not be treated as research proof, production readiness, or permission to
trade.

## Detailed Pipeline Runbook

This runbook defines reusable phase command patterns and gate requirements.
Historical/current-state candidate workflow notes live in the Current Status
Appendix only. Appendix notes are scoped workflow state; they are not general
pipeline requirements, approvals, or model-trust evidence unless reconciled
against current primary artifacts, manifests, command output, and a bounded
approval.

Run commands from the repo root:

```powershell
cd C:\Users\donny\Desktop\futures_intraday_model
```

### 1A. Download Or Stage DBN Archives

Purpose: download or stage immutable Databento DBN/ZST chunks and validate DBN
request plans before provider work starts. Phase 1A must first build a
download plan, validate request parameters, validate output paths and overwrite
guards, run dry-run/cost gates when applicable, and stop before provider
download if any severe preflight failure exists. After download, Phase 1A
validates the actual DBN files and manifests before any active replacement or
raw parquet conversion is considered. This phase writes source archives only
into an approved DBN root; normal broad downloads use the active
source-of-truth DBN root `data/dbn`, while redownload or repair work must stage
outside active roots until a separate bounded replacement approval exists. This
phase does not create canonical raw parquet. DBN files under `data/archive` are
stale/dead archive evidence only, not Phase 1A source inputs.

Required pre-download plan command, no provider API calls:

```powershell
python -m scripts.phase1A_download.download_databento_raw --universe extended_cme --start-year 2010 --end-year 2026 --end-date 2026-06-10 --schema all --mode download-dbn --raw-format dbn-zstd --chunk year --workers 4 --resume --dry-run --reports-root reports\raw_ingest
```

Cost estimate evidence, when provider metadata calls are approved but before
any download. This estimates cost only; it is not a zero-cost blocking gate by
itself:

```powershell
python -m scripts.phase1A_download.download_databento_raw --universe extended_cme --start-year 2010 --end-year 2026 --end-date 2026-06-10 --schema all --mode download-dbn --raw-format dbn-zstd --chunk year --workers 4 --resume --estimate-cost --reports-root reports\raw_ingest
```

Exact zero-cost blocking gate, when the approved policy requires only exact
zero-cost downloadable tasks:

```powershell
python -m scripts.phase1A_download.download_databento_raw --universe extended_cme --start-year 2010 --end-year 2026 --end-date 2026-06-10 --schema all --mode download-dbn --raw-format dbn-zstd --chunk year --workers 4 --resume --estimate-cost --zero-cost-only --reports-root reports\raw_ingest
```

Provider download command, only after pre-download plan and cost evidence are
accepted under a bounded approval. If exact zero-cost is required, the
zero-cost gate above must pass first:

```powershell
python -m scripts.phase1A_download.download_databento_raw --universe extended_cme --start-year 2010 --end-year 2026 --end-date 2026-06-10 --schema all --mode download-dbn --raw-format dbn-zstd --chunk year --workers 4 --resume --reports-root reports\raw_ingest
```

Inputs:

- Databento API key from environment or local secret handling.
- Requested universe, dates, and schemas.

Outputs:

- OHLCV DBN: `data/dbn/ohlcv_1m/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst`
- Definition DBN: `data/dbn/definition/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst`
- Optional sidecar DBNs:
  `data/dbn/status/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst` and
  `data/dbn/statistics/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst`
- Reports under `reports/raw_ingest/`, including DBN manifests.

Pre-download request preflight:

- Exact market/year/schema scope is approved and bounded.
- Planned `schema` matches the intended folder/task: manifest schema
  `ohlcv-1m` maps to `data/dbn/ohlcv_1m`; manifest schemas `status`,
  `statistics`, and `definition` map to matching schema folders.
- Planned `market`, `start`, and `end` match the intended market-year window.
- Planned `stype_in` matches policy: normal canonical `ohlcv-1m`, `status`,
  and `statistics` use `continuous`; current `definition` uses `parent` unless
  a separate approved downloader policy change says otherwise.
- Planned `stype_out=instrument_id`.
- Planned `symbols_requested` matches `stype_in`: normally `{MARKET}.v.0` for
  `continuous` and `{MARKET}.FUT` for `parent`.
- Planned `encoding=dbn`, `compression=zstd`, `vendor=databento`, and
  `dataset=GLBX.MDP3`.
- Planned output path is under the approved staging or active DBN root, matches
  the schema/market/year/date-window layout, and does not contain forbidden
  path patterns for the run.
- No planned output would overwrite an existing file unless that exact
  overwrite is separately approved.
- Dry-run/cost evidence is reviewed when applicable.

Pre-download stop or override policy:

- Default behavior is fail closed: pause or stop before provider download,
  write a report explaining the failed check, and require an explicit decision.
- Severe failures must not be overridden in normal runs: wrong schema, wrong
  `stype_in`, wrong symbol, wrong market/year/date window, wrong output root,
  active overwrite risk, forbidden path pattern, missing approval, or
  unapproved cost.
- Only documented non-severe warnings may be overridden, and only by explicit
  bounded approval that names the warning code, scope, report path, timeout,
  forbidden actions, and stop condition. Do not use a generic broad override.

Post-download DBN file/manifest validation:

- Required DBN files and sidecar manifests exist for the exact approved
  market/year/schema scope.
- Manifest identity fields match the request and folder/task: `vendor`,
  `dataset`, `schema`, `market`, `symbols_requested`, `start`, `end`,
  `stype_in`, `stype_out`, `encoding`, `compression`, `path`,
  `file_size_bytes`, `file_sha256`, and `request_status`.
- Normal canonical `ohlcv-1m`, `status`, and `statistics` requests use
  `stype_in=continuous`, `stype_out=instrument_id`, and
  `symbols_requested={MARKET}.v.0`; the current repo downloader forces
  `definition` to `stype_in=parent` with `symbols_requested={MARKET}.FUT`
  unless a separate policy/code change is explicitly approved.
- `encoding=dbn`, `compression=zstd`, `vendor=databento`,
  `dataset=GLBX.MDP3`, and `request_status=ok`.
- Manifest `path` points to the actual DBN file, `file_size_bytes` is positive,
  and `file_sha256` equals the actual DBN bytes.
- No unexpected overwrite occurred.

Stop conditions:

- A market-year is missing from the current coverage audit after a supposedly
  successful run.
- A pre-download request preflight has any severe failure.
- A batch times out.
- A manifest hash/path/schema mismatch appears.
- The command would require broad `--overwrite` without an explicit audit reason.

### 1B. Build And Validate Raw Parquet

Purpose: recheck accepted Phase 1A DBN evidence immediately before conversion,
then stitch accepted DBN chunks into one OHLCV 1-minute grained raw market-year
parquet dataset. Definition, status, and statistics records are joined onto
OHLCV rows as metadata/enrichment columns; Phase 1B does not create separate
parquet datasets for each DBN schema. Phase 1B also immediately validates the
converted raw parquet against the DBN files/manifests that produced it:
`source_file`, `source_sha256`, required sidecars, definition joins, and
row/schema sanity must pass before Phase 2 can consume the raw data.

Required Phase 1B command sequence. Phase 1B is incomplete unless both the
conversion command and the raw/DBN validation command pass for the same scope.
The bounded approval must name the scope once, then the conversion and
validation commands must use that same scope. Do not mix a broad conversion
with a narrow validation report, or a narrow conversion with a broad validation
report.

Convert DBNs to raw parquet:

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --dbn-root data\dbn\ohlcv_1m --raw-root data\raw
```

Validate converted raw parquet against DBNs:

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config configs/alpha_tiered.yaml --profile tier_3 --dbn-root data\dbn --raw-root data\raw --json-out reports\raw_ingest\raw_dbn_alignment.json --md-out reports\raw_ingest\raw_dbn_alignment.md
```

For bounded market/year repair work, use matching `--symbols`, date/year bounds,
profile, or include-list artifacts in both commands. The validation command's
`--profile` or `--market-year-include-list` must describe exactly the raw files
converted in the paired conversion command.

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
- Raw parquet manifests and raw/DBN validation reports under `reports/raw_ingest/`.

Acceptance checks:

- Evidence recheck aborts before writing raw parquet if any scoped Phase 1A DBN
  validation report is missing/stale or any scoped DBN manifest is missing,
  unreadable, stale, or inconsistent with its file.
- `schema` matches the folder/task: manifest `ohlcv-1m` under
  `data/dbn/ohlcv_1m`, or manifest `status`, `statistics`, or `definition`
  under the matching schema folder.
- `market` matches the folder market.
- `start` and `end` match the market-year window.
- `stype_in` matches policy: normal canonical `ohlcv-1m`, `status`, and
  `statistics` use `continuous`; current `definition` uses `parent` unless a
  separate approved downloader policy change says otherwise.
- `stype_out=instrument_id`.
- `symbols_requested` matches `stype_in`: normally `{MARKET}.v.0` for
  `continuous` and `{MARKET}.FUT` for `parent`.
- `encoding=dbn`, `compression=zstd`, `vendor=databento`,
  `dataset=GLBX.MDP3`, and `request_status=ok`.
- Manifest `path` points to the actual DBN file, `file_size_bytes` is positive
  and matches the file, and `file_sha256` equals the actual DBN bytes.
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

- Any DBN evidence recheck failure before conversion.
- Missing definition DBN for a market-year.
- Any null or nonpositive tick-size metadata.
- Missing manifest, hash mismatch, or raw schema mismatch.
- Post-conversion raw/DBN validation fails on source file, source hash,
  required sidecars, definition join, or row/schema sanity.

#### Phase 1B Raw/DBN Validation Gate

Purpose: independently validate that converted canonical `data/raw` parquet is
complete, schema-valid, DBN-derived, definition-enriched, and aligned to the
current local DBN archive before Phase 2 consumes it. This is now the validation
gate inside Phase 1B. The script path still contains `phase1C_validate` for
backward compatibility with existing code, tests, and historical reports, but
it is no longer a separate public pipeline phase.

Internal validator command:

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
- OHLCV, definition, and required optional DBN sidecar manifests pass for the
  exact active scope.
- No raw parquet exists without matching local DBN provenance.
- Raw parquet `source_file` and `source_sha256` lineage match the actual DBN
  files and manifests used to build it.
- Required status/statistics source columns are populated where policy requires
  them.
- Definition joins pass for every scoped market-year that is not covered by an
  explicit accepted exception.
- Missing canonical raw market-years are reported as Phase 1B conversion
  candidates, not silently ignored.
- Staged candidates are compared against canonical `data/raw` before any
  promotion decision.
- Optional status/statistics audit separates core OHLCV/definition readiness
  from optional-enrichment readiness and alpha-input caveats.

Streamlining policy:

- Keep Phase 1A and Phase 1B separate so immutable DBN provenance remains
  auditable.
- Phase 1A must fail fast before provider download when the planned request is
  invalid, unsafe, too expensive, or outside approval bounds.
- Phase 1B must still recheck accepted DBN evidence before raw parquet
  conversion because files, manifests, or approvals can drift between phases.
  Do not spend conversion time on a scope that cannot pass the DBN evidence
  recheck.
- Do not run Phase 2 before Phase 1B raw parquet build and Phase 1B raw/DBN
  validation both pass.
- Keep the raw/DBN validation command independent inside Phase 1B so conversion
  output is audited after it is written. Do not fold causal/session validation
  into Phase 1B.

Standard redownload/rebuild policy:

- Do not hand-edit DBN manifests to change request semantics, such as
  `stype_in`, symbols, dates, schema, hashes, file sizes, or job metadata.
- Any replacement DBN download must run Phase 1A request preflight first, with
  exact market/year/schema scope, expected request parameters, output-root and
  overwrite guards, cost/dry-run evidence when applicable, and no active
  `data/dbn` overwrite during acquisition.
- Before provider download, severe Phase 1A request-preflight failures must
  stop the run and explain the issue. Only explicit bounded approvals may
  override documented non-severe warnings.
- After provider download and before promotion, staged DBNs and manifests must
  pass file hash, path, schema, date-window, request-parameter, decoded-schema,
  decoded-row, and record-level comparison checks against the intended policy
  baseline.
- Active DBN replacement requires a separate bounded approval and must archive
  the prior active DBN/manifests; it must not delete provenance evidence.
- After any active DBN replacement, rebuild affected `data/raw` market-years
  from canonical `data/dbn` sources. Phase 1B must recheck Phase 1A validation
  evidence and abort before conversion if any scoped report, manifest, or DBN
  file fails. Do not treat a DBN replacement alone as a completed downstream
  repair.
- Run the Phase 1B raw/DBN validation gate on the exact affected market-years
  after conversion and require raw/DBN source hashes, schema checks, required
  DBN coverage, sidecar lineage, row/schema sanity, and definition joins to pass
  before Phase 2.
- Run Phase 2 readiness-only first for the exact affected market-years. Only
  after readiness passes may staged causal parquet be built, validated, and
  separately approved for active replacement.
- Keep downstream labels, features, WFA, predictions, model selection, paper,
  and live workflows out of scope unless separately approved after the causal
  rebuild evidence is accepted.

### 2. Build Causal Base

Purpose: run a readiness gate against accepted raw parquet evidence, then
re-check raw bar invariants, normalize sessions, identify roll windows, mark
synthetic rows, and causally gate data. Phase 2 must validate causal output
row counts, raw input paths/hashes, manifests, and row/hash evidence before any
staged causal parquet is promoted to an active root.

Required Phase 2 command sequence. Phase 2 is incomplete unless readiness,
build, and output validation all pass for the same scope. The bounded approval
must name the scope once, and the readiness/build commands plus generated
manifest/validation reports must match that scope.

Readiness gate only, no causal parquet build:

```powershell
python -m scripts.phase2_causal_base.build_causal_base_data --readiness-only --profile tier_1 --raw-root data\raw --output-root data\causally_gated_normalized --raw-alignment-report reports\raw_ingest\raw_dbn_alignment.json --readiness-json-out reports\causal_base\tier_1_readiness_summary.json --readiness-md-out reports\causal_base\tier_1_readiness_summary.md
```

Build causal parquet only after readiness passes:

```powershell
python -m scripts.phase2_causal_base.build_causal_base_data --profile tier_1 --raw-root data\raw --output-root data\causally_gated_normalized --reports-root reports\causal_base\tier_1 --raw-alignment-report reports\raw_ingest\raw_dbn_alignment.json
```

Required post-build validation evidence:

- `reports/causal_base/tier_1/causal_base_manifest.json`
- `reports/causal_base/tier_1/causal_base_validation.json`
- `reports/causal_base/tier_1/causal_base_validation.csv`

Phase 2 does not pass unless readiness status is `PASS`, the causal manifest is
`PASS`, causal validation is `PASS`, raw input paths/hashes match the accepted
Phase 1B raw parquet evidence, and output hashes/row counts match the causal
validation evidence.

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
- `reports/causal_base/{profile}/causal_base_manifest.json`
- `reports/causal_base/{profile}/causal_base_validation.json`
- `reports/causal_base/{profile}/causal_base_validation.csv`
- explicitly scoped readiness JSON/markdown/checkpoint reports under the
  approved reports root, when a readiness-only run is approved.

Historical/current-state Phase 2 local-trade diagnostic workflow notes live
under `Historical Local-Trade Phase 2 Diagnostic Workflow State` in the Current
Status Appendix. Those notes are not reusable Phase 2 runbook authority,
model-trust evidence, or approval for downstream work unless refreshed against
current primary artifacts and a bounded approval.


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

- Phase 5/6/8 cannot consume feature matrices with missing audit records,
  target/leakage columns, stale registries, row mismatches, or provisional-cost
  blockers.
- Phase 9 feature hypotheses remain feasibility work until they produce the
  same audit record required for promoted Phase 4 features.

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

- Phase 6/8 cannot use missing, stale, mismatched, contaminated, or
  non-positive-fold split plans.
- Statistical-validity, promotion, artifact-freeze, final-holdout, and forward
  claims remain blocked until the split design proves chronological OOS
  separation, purge/embargo, and the guarded evaluation path.

### 6. Train WFA Models And Save OOS Predictions

Purpose: fit baseline models on train folds and write out-of-sample predictions
for test folds. Phase 6 also owns combining prediction shards through the
`scripts.phase6_wfa.combine_wfa_predictions` wrapper.

Prediction-write command template:

```powershell
python -m scripts.phase6_wfa.run_wfa `
  --profile tier_1 `
  --matrix baseline `
  --run baseline `
  --input-root data/feature_matrices/baseline `
  --split-plan reports/wfa/split_plan.json `
  --predictions-root data/predictions `
  --reports-root reports/wfa `
  --models-config configs/models.yaml `
  --profile-config configs/alpha_tiered.yaml `
  --feature-set path/to/frozen_feature_set_manifest.json `
  --data-audit-universe-json path/to/data_audit_universe.json `
  --write-predictions
```

A bounded execution plan must replace placeholder paths with accepted current
artifacts before running Phase 6. Tier 1 WFA requires a frozen feature-set
manifest and data-audit universe evidence. Prediction parquet is written only
when `--write-predictions` and `--predictions-root` are both supplied.

Shard pattern for large runs:

```powershell
python -m scripts.phase6_wfa.run_wfa `
  --profile tier_1 `
  --matrix baseline `
  --run baseline_s1of8 `
  --input-root data/feature_matrices/baseline `
  --split-plan reports/wfa/split_plan.json `
  --predictions-root data/predictions `
  --reports-root reports/wfa `
  --models-config configs/models.yaml `
  --profile-config configs/alpha_tiered.yaml `
  --feature-set path/to/frozen_feature_set_manifest.json `
  --data-audit-universe-json path/to/data_audit_universe.json `
  --fold-shard-count 8 `
  --fold-shard-index 1 `
  --write-predictions

python -m scripts.phase6_wfa.run_wfa `
  --profile tier_1 `
  --matrix baseline `
  --run baseline_s2of8 `
  --input-root data/feature_matrices/baseline `
  --split-plan reports/wfa/split_plan.json `
  --predictions-root data/predictions `
  --reports-root reports/wfa `
  --models-config configs/models.yaml `
  --profile-config configs/alpha_tiered.yaml `
  --feature-set path/to/frozen_feature_set_manifest.json `
  --data-audit-universe-json path/to/data_audit_universe.json `
  --fold-shard-count 8 `
  --fold-shard-index 2 `
  --write-predictions

python -m scripts.phase6_wfa.combine_wfa_predictions `
  --manifest-pattern "reports/wfa/baseline_s*of8_predictions_manifest.json" `
  --run baseline `
  --predictions-root data/predictions `
  --reports-root reports/wfa `
  --split-plan reports/wfa/split_plan.json `
  --require-all-folds
```

Repeat the shard run for each 1-based shard index and use a unique shard run
name, such as `baseline_s1of8` through `baseline_s8of8`, before combining.
Shard prediction combines are Phase 6 work; do not call `scripts.phase7_wfa`
directly from runbooks or execution packets.

Inputs:

- `data/feature_matrices/baseline/`
- frozen feature-set manifest accepted for WFA, or an explicitly scoped
  non-Tier-1 `feature_cols.json` path when allowed by the bounded plan
- `reports/wfa/split_plan.json`
- data-audit universe JSON when required by the profile
- `configs/models.yaml`
- `configs/alpha_tiered.yaml`

Outputs:

- `data/predictions/{run}/oos_predictions.parquet`
- `reports/wfa/{run}_predictions_manifest.json`
- `reports/wfa/{run}_wfa_report.json`
- combined prediction parquet and manifest when shard-combine mode is used

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

- Phase 8 and later gates require matching prediction parquet, manifest, WFA
  report, split-plan provenance, artifact evidence, and model-risk metadata.
- Fold failures, stale outputs, unapproved search expansion, post-OOS changes,
  or collapsed predictions block promotion unless a separate diagnostic decision
  keeps the run in scope.

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

- `C:\Users\donny\Desktop\futures_intraday_model\RUN_ALPHA_DISCOVERY.bat` is
  the repo-local user-facing launcher, not pipeline authority. It is the only
  supported project `.bat` launcher. Static self-check requires that repo-local
  launcher path before wizard work starts.
- Default launcher behavior delegates to
  `python -m scripts.validation.run_alpha_discovery_wizard`. `--self-check`
  runs the marker check. `--generate-candidates` delegates to
  `python -m scripts.validation.generate_alpha_discovery_candidates`; without
  `--spec` it is proposal-only, target-only, horizon-agnostic ideation and
  writes no files, while `--spec` writes preflight-only candidate configs and
  one queue JSON under `configs/`. `--config` runs one candidate through
  `python -m scripts.validation.run_alpha_discovery`; `--queue` runs a serial
  queue through `python -m scripts.validation.run_alpha_discovery_queue`.
- `C:\Users\donny\Desktop\futures_intraday_model\RUN_STRATEGY_CANDIDATE_IDEATION.bat`
  is the double-click proposal-only ideation launcher. With no arguments, it
  writes up to 10 numbered Markdown/JSON review pairs under ignored
  `reports/pipeline_audit/strategy_candidate_ideation/` and prompts for an
  optional implementation shortlist. Candidate Markdown is a short human review
  card; JSON is a `schema_version: 2` draft-only dossier with
  `generated_by: strategy_candidate_ideation_v2`, `draft_only: true`,
  `applied: false`, `conversion_required: true`,
  `current_wizard_compatible: false`, horizon/exit-rule metadata, and
  `evidence_status: not_model_trust_evidence`. A selection writes only
  `implementation_selection.json` with selected JSON paths and SHA-256 hashes.
  With `--self-check`, it runs the repo-local marker check. It must not mutate
  registry/status, runnable harness specs, configs, data, logs, models,
  staging, commits, pushes, WFA, Phase 8, promotion, paper, or live execution.
- Allowed modes are `preflight`, `source-tests`, `discovery-packet`,
  `discovery-run`, and `review`; the runner must stop at the current approved
  discovery boundary.
- Proposal-only ideation emits review drafts only. Console ideation writes no
  files; review-packet output is limited to ignored Markdown/JSON candidate
  files under `reports/pipeline_audit/strategy_candidate_ideation/`. Matching
  v2-marked generated files may be overwritten on rerun; matching v1 or
  unmarked current files are moved to `_archive/<timestamp>/` by direct-file
  pattern only. JSON dossiers use `proposed_implementation_contract`,
  `registry_patch_draft`, `trial_status_patch_draft`, and
  `post_registration_config_spec_draft` with `runnable: false`; old
  `draft_registry_entry` and `draft_trial_status_entry` fields are not emitted.
  Ideation never registers, implements, runs, stages, commits, pushes, or writes
  data/logs/models/configs, and `implementation_selection.json` is not approval
  for implementation, registry/status mutation, or discovery.
- A selected ideation JSON becomes wizard-consumable only after a later explicit
  conversion/implementation phase chooses or builds a compatible Phase 9 harness,
  implements target construction, adds source tests, appends real registry/status
  rows after approval, generates config/queue artifacts, and stops at
  `WIZARD_PREFLIGHT_COMPLETE` unless separate bounded discovery approval exists.
- Spec-driven candidate artifact generation is config-only: explicit candidate
  list, 100-candidate hard cap, no overwrites, output only under `configs/`,
  generated configs forced to `preflight`, and no discovery or registry/status,
  report, data, log, model, staging, commit, or push mutation. Candidate specs
  must already be clean canonical Phase 9 target-discovery candidates in
  `manifests/target_hypotheses/registry.json` and
  `manifests/target_hypotheses/trial_statuses.jsonl`, use canonical
  registry/status paths, and match the ES 30m target smoke harness `TARGET_SPECS`.
- Wizard autopsy is separate from generation. Readiness autopsy writes under
  `reports/pipeline_audit/alpha_discovery_autopsy/<batch>/readiness/`.
  `discovery-run` additionally requires `--approve-discovery-run`, approval
  phrase `RUN_PHASE9_DISCOVERY_ONCE`, absent/ignored expected outputs, approved
  queue entries when used, and one generated JSON/MD review before any next
  decision. Queue discovery is serial, defaults to at most 10 candidates, has an
  absolute 100-candidate cap, and stops on infrastructure failure, timeout,
  missing JSON, nonzero wrapper error, unapproved output path, or malformed
  candidate decision.
- A runner-completed status means only that the wrapper finished. Candidate
  pass/fail must be read from generated JSON, any `STOP_*` decision stops that
  candidate, and autopsy reports must carry
  `FEASIBILITY ONLY - NOT MODEL-TRUST EVIDENCE - DO NOT RETUNE FROM THIS AUTOPSY`.
  The runner cannot approve confirmation smoke, locked smoke, WFA/modeling,
  Phase 8 diagnostics, tuning, promotion, registry/status mutation, artifact
  staging, commits, pushes, paper trading, or live trading.

Current implemented harnesses live under `scripts/phase9_research/`.


### 10. Guard Locked Holdout/Forward Evaluation

Purpose: guard locked holdout and forward evaluation so final evaluation uses
only frozen, pre-approved research artifacts and cannot become a new tuning,
feature-selection, calibration, or policy-selection loop.

Command template:

```powershell
python -m scripts.final_holdout.guard_final_holdout `
  --frozen-artifact-id <freeze_id> `
  --freeze-root artifacts/frozen `
  --run-id final_holdout_<run_id> `
  --reports-root reports/final_holdout/<run_id>
```

Inputs:

- `artifacts/frozen/<freeze_id>/manifest.json`
- Phase 8 promotion fields copied into the frozen manifest
- anti-overfit status and failures copied into the frozen manifest
- frozen run, profile, and resolved-profile identifiers

Outputs:

- `reports/final_holdout/<run_id>/final_metrics.json`
- console status showing `PASS` or `FAIL` and failure count

Acceptance checks:

- The frozen manifest exists, is marked `frozen=true`, and has
  `failure_count=0`.
- The frozen manifest records `final_holdout_consumes_frozen_only=true`.
- Phase 8 fields in the frozen manifest show `phase8_promoted=true`,
  `phase8_model_promotion_allowed=true`, and no Phase 8 blockers.
- Anti-overfit fields in the frozen manifest show `PASS` and no failures.
- The final-holdout run does not set `--allow-tuning`,
  `--allow-feature-selection`, `--allow-calibration-change`, or
  `--allow-policy-change`.

Stop conditions:

- Missing, stale, unfrozen, unpromoted, blocked, or failed frozen manifest.
- Any requested tuning, feature selection, calibration change, or policy change
  during final-holdout evaluation.
- Missing run/profile/resolved-profile identity in the frozen manifest.
- Anti-overfit evidence missing, failed, or inconsistent with the frozen run.

Downstream blockers:

- Final-holdout results cannot support promotion, paper, live, or artifact
  claims unless the guard output is `PASS` and consumes frozen artifacts only.
- Any final-holdout failure keeps the run diagnostic-only and requires a new
  predeclared research line before further model-selection work.

### 11. Freeze Approved Research Artifacts

Purpose: freeze only approved research artifacts after Phase 8 promotion and
anti-overfit evidence pass, before any final-holdout evaluation can consume the
run.

Command template:

```powershell
python -m scripts.artifact_freeze.freeze_research_artifacts `
  --freeze-id <freeze_id> `
  --freeze-root artifacts/frozen `
  --feature-root <accepted_feature_root> `
  --phase4-audit reports/phase4/feature_coverage_audit.json `
  --split-plan reports/wfa/split_plan.json `
  --predictions-manifest reports/wfa/baseline_predictions_manifest.json `
  --phase8-decision reports/phase8/alpha_promotion_decision.json `
  --anti-overfit-audit reports/experiments/anti_overfit_audit.json `
  --models-config configs/models.yaml `
  --costs-config configs/costs.yaml `
  --feature-manifest reports/phase4/baseline_feature_manifest.json
```

`--feature-root` is required and must name the exact accepted feature matrix
root. Do not rely on an implicit default.

Inputs:

- Accepted feature root plus `feature_cols.json`, `target_cols.json`,
  `metadata_cols.json`, and `excluded_cols.json`
- Phase 4 feature coverage audit and baseline feature manifest
- WFA split plan and prediction manifest
- Phase 8 promotion decision
- anti-overfit audit
- models and costs configs used by the promoted run

Outputs:

- `artifacts/frozen/<freeze_id>/manifest.json`
- copied frozen feature registries, configs, split plan, prediction manifest,
  Phase 8 decision, anti-overfit audit, and feature manifest under the freeze
  directory

Acceptance checks:

- Phase 4 coverage audit has no missing Tier 3 feature coverage for the freeze
  scope.
- Split plan has selectable research folds and no selection-allowed final
  holdout folds.
- Prediction manifest has `failure_count=0`, no stale output flag, and
  `artifact_evidence_ready=true`.
- Phase 8 decision is promoted, allows model promotion, has no blockers, has no
  failures, has not touched final holdout, and has not changed trading
  semantics.
- Anti-overfit audit is `PASS`, has no failures, and matches the frozen profile
  when profile is present.
- Feature registry files exist and match the feature manifest schema.

Stop conditions:

- Missing Phase 4 audit, feature manifest, split plan, prediction manifest,
  Phase 8 decision, anti-overfit audit, model config, cost config, or feature
  registry.
- Phase 8 blockers, non-promotion, final-holdout contamination, trading
  semantics changes, stale predictions, failed prediction manifest, failed
  anti-overfit evidence, or schema mismatch.
- Existing freeze output for the same `freeze_id` unless a separate bounded
  replacement plan explicitly approves disposition.

Downstream blockers:

- Phase 10 cannot run until Phase 11 writes a frozen manifest with
  `frozen=true`, `failure_count=0`, and `final_holdout_consumes_frozen_only=true`.
- Frozen artifacts are research evidence only. They do not approve paper or live
  trading without the separate production deferral gate.

## Validation Commands

These commands are narrow checks or documentation gates. They do not approve
provider downloads, broad data builds, WFA/modeling, prediction generation,
Phase 8 report generation, artifact freeze execution, final-holdout execution,
paper, live paths, staging, commits, or pushes.

Major trust gate checks:

| Gate | Narrow check or status |
| --- | --- |
| Coordination docs | `python -m scripts.validation.check_coordination_docs` |
| Raw Data And Metadata Gate / Phase 1A | `python -m pytest -q tests/phase1A_download/test_download_databento_raw.py tests/validation/test_check_dbn_archive_coverage.py` |
| Phase 1B raw/DBN validation | `python -m pytest -q tests/validation/test_audit_raw_dbn_alignment.py tests/validation/test_audit_enriched_raw_optional_schemas.py` |
| Cleaning And Normalization Gate / Phase 2 | `python -m pytest -q tests/phase2_causal_base/test_build_causal_base_data.py tests/validation/test_audit_phase2_readiness.py tests/validation/test_check_phase2_manifest_trust.py` |
| Label And Target Gate / Phase 3 | `python -m pytest -q tests/phase3_labels/test_build_labels.py tests/validation/test_target_policy_contract.py` |
| Feature audit / Phase 4 | `python -m pytest -q tests/phase4_features/test_build_baseline_features.py tests/phase8_model_selection/test_audit_label_feature_sanity.py` |
| WFA split gate / Phase 5 | `python -m pytest -q tests/phase5_wfa/test_build_wfa_splits.py` |
| Phase 6 wrapper surface | `python -c "import scripts.phase6_wfa.run_wfa as r; import scripts.phase6_wfa.combine_wfa_predictions as c; assert callable(r.main); assert callable(c.main)"` |
| Phase 8 / Backtest And Cost Gate | `python -m pytest -q tests/phase8_model_selection/test_evaluate_predictions.py tests/phase8_model_selection/test_audit_return_model_scale.py tests/phase8_model_selection/test_audit_policy_signal_alignment.py` |
| Portfolio And Risk Gate | `python -m pytest -q tests/phase8_model_selection/test_audit_mr_tail_risk.py tests/phase8_model_selection/test_audit_policy_failure.py`; manual evidence review only for capital, margin, broker, capacity, and portfolio aggregation claims. |
| Statistical Validity Gate | Manual evidence review only unless the scoped Phase 8 report explicitly records PBO, Deflated Sharpe, Probabilistic Sharpe, bootstrap confidence intervals, multiple-testing adjustment, parameter stability, regime breakdowns, and `PASS` / `FAIL` / `NOT_APPLICABLE_WITH_REASON` status for each item. |
| Production Deferral Gate | Manual evidence review only; no paper/live command is authorized by this file. |
| Paper/Live Readiness Gate | Manual evidence review only; future and non-authorizing until a separate runbook, validation suite, and evidence manifest exist. |
| Phase 10 final holdout guard | `python -m pytest -q tests/final_holdout/test_guard_final_holdout.py` |
| Phase 11 artifact freeze | `python -m pytest -q tests/artifact_freeze/test_freeze_research_artifacts.py` |
| Doc hygiene | `rg -n "Historical Local-Trade Phase 2|Statistical validity applicability|Portfolio/risk minimum evidence|Baseline acceptance|Paper/Live Readiness|Verified|Inferred|Assumed|Not established" PROJECT_OUTLINE.md`; `git diff --check`; `git status --short` |

Runbook-focused validation after editing this file:

```powershell
python -m scripts.validation.check_coordination_docs
python -m pytest -q tests/validation/test_check_coordination_docs.py tests/final_holdout/test_guard_final_holdout.py tests/artifact_freeze/test_freeze_research_artifacts.py
rg -n "Historical Local-Trade Phase 2|Statistical validity applicability|Portfolio/risk minimum evidence|Baseline acceptance|Paper/Live Readiness|Verified|Inferred|Assumed|Not established" PROJECT_OUTLINE.md
git diff --check
git status --short
```

Coverage and artifact-readiness check, report-only when scoped by a bounded
approval:

```powershell
python -m scripts.validation.check_tier_2_coverage --profile tier_1 --stage all
```

Focused WFA/Phase 8 tests:

```powershell
python -m pytest tests/phase7_wfa/test_run_wfa.py tests/phase7_wfa/test_combine_wfa_predictions.py tests/phase8_model_selection/test_evaluate_predictions.py -q
```

## Current Status Appendix

Status date: June 17, 2026 local project notes.

This appendix is historical context only, not current model-trust evidence or
approval. Refresh any claim here from primary artifacts, manifests, command
output, and current repo state before using it for research conclusions,
promotion, artifact freeze, or follow-on execution.

### Historical Local-Trade Phase 2 Diagnostic Workflow State

This subsection is historical/current-state context only. It is not reusable
Phase 2 runbook authority, not model-trust evidence, and not approval for
causal-base repair/build, labels, features, WFA/modeling, metrics, proof
scans, promotion, artifact freeze, staging, commit, push, paper, or live
execution unless refreshed against current primary artifacts and a bounded
approval.
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

- Command class: Phase 1B raw DBN/parquet validation audits only, using the
  legacy/internal `phase1C_validate` command path.
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


Historical/current-state Phase 2 workflow notes for the ES 2026 P1 path live
under `Historical ES 2026 P1 Workflow State` in `Current Status Appendix`. Those
notes are not reusable Phase 2 runbook authority, model-trust evidence, or
approval for downstream work unless refreshed against current primary artifacts
and a bounded approval.


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


### Historical ES 2026 P1 Workflow State

This subsection is historical/current-state context only. It is not reusable
Phase 2 runbook authority, not model-trust evidence, and not approval for
causal-base repair/build, labels, features, WFA/modeling, metrics, proof
scans, promotion, artifact freeze, staging, commit, push, paper, or live
execution unless refreshed against current primary artifacts and a bounded
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

- Locked Tier 1 baseline run: `tier1_locked_baseline_20260616`, scope
  `tier_1 -> tier_1_research`, markets `ES`, `CL`, `ZN`, `6E`, years
  2023-2024.
- Key artifacts: predictions
  `data/predictions/tier1_locked_baseline_20260616/oos_predictions.parquet`,
  WFA manifest `reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json`,
  metrics `reports/metrics/tier1_locked_baseline_20260616_metrics.json`, and
  promotion decision `reports/phase8/alpha_promotion_decision.json`.
- Phase posture at the time: Phase 2 `WARN`, Phase 3 `PASS`, Phase 4 `WARN`,
  Phase 5 `PASS`, Phase 6 shard-combined with `artifact_evidence_ready=true`,
  and Phase 8 structurally evaluated but not promoted.
- Costed OOS result was negative: gross dollars `-20,287.50`, costs
  `22,357.88`, net dollars `-42,645.38`, net Sharpe-like `-5.1086`,
  `research_alpha_ready=false`, `model_promotion_allowed=false`, and
  `promoted=false`.
- Decision: `TIER1_LOCKED_BASELINE_NO_GO`. Do not promote, threshold-tune,
  rerun near-neighbor rescue variants, rerun full-market/full-fold WFA for the
  same baseline line, or treat small positive threshold pockets as alpha.
- Stopped branches: Tier 1 cost-clearability feasibility and market-balanced
  cost-clearability follow-up are both `STOP_BRANCH_PERMANENTLY`;
  oracle/feasibility evidence from those branches is not executable PnL or a
  route to direction modeling, policy work, or full Tier 1 WFA.
- Next valid research must be a separate pre-registered target-construction,
  feature-generation, or genuinely new ES-only custom hypothesis. Do not reuse
  the failed built-in ES feature-family sweep, stopped Phase 9 hypotheses, or
  cost-clearability rescue variants as "new" work.

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

Every material research, model-trust, execution, promotion, artifact-freeze,
paper, or live-readiness claim must be labeled:

- `Verified`: directly supported by primary evidence such as repo files,
  manifests, command output, raw data, or reproducible local checks.
- `Inferred`: reasoned from primary evidence, but not directly proven by the
  cited artifact.
- `Assumed`: required for interpretation, but not established by current
  evidence.
- `Not established`: absent, stale, contradicted, or not reviewed enough to
  support the claim.

Prefer:

- finding;
- claim label;
- evidence path, command, or metric;
- interpretation and stale-risk note;
- blocker or next gate.

Do not present gross-only results as tradable evidence. Do not present failed
or warning-status outputs as promotion-ready. Do not present `Inferred`,
`Assumed`, or `Not established` claims as model-trust, promotion,
artifact-freeze, paper, or live-readiness evidence without naming the downstream
blocker and independent verification needed.

## Final Research Posture

The project can only support research conclusions after the relevant phase gates pass with reproducible local evidence. A favorable metric is not enough. A valid conclusion requires audited data lineage, leakage-safe targets/features, locked validation, realistic costs, documented failures, and reproducible reports.
