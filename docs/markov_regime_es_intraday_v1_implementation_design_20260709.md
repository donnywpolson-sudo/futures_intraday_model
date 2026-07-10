# Markov Regime ES Intraday V1 Bounded Implementation Design

Status: `BOUNDED_IMPLEMENTATION_DESIGN_ONLY`

Date: 2026-07-09

Related predeclaration: `docs/markov_regime_es_intraday_v1_predecl_packet_20260709.md`

This design does not approve implementation code, diagnostics execution, generated reports, registry or trial-ledger mutation, config mutation, data/model/log mutation, WFA/modeling, provider/download commands, cleanup, staging, commit, push, promotion, artifact freeze, final holdout, paper/live work, or HMM work.

## Review Result

The predeclaration packet is phase-correct for a bounded design step. It identifies a real missing evidence bucket: explicit causal regime evidence is absent from the July 9 alpha evidence matrix, while the current Tier 1 line is closed for alpha evidence.

Proceed only to a separately approved implementation pass. Do not treat this diagnostic as a target, alpha signal, sizing overlay, strategy, model rescue, or promotion path.

## Exact Read-Only Inputs

Implementation must read only these repo-local inputs:

- `docs/markov_regime_es_intraday_v1_predecl_packet_20260709.md`
- `PROJECT_OUTLINE.md`
- `CODEX_HANDOFF.md`
- `data/feature_matrices/ES/2023.parquet`
- `data/feature_matrices/ES/2024.parquet`
- `reports/wfa/tier1_core_phase5_split_plan_20260706/split_plan.json`
- `reports/wfa/tier1_core_phase6_wfa_runner_preflight_20260706/tier1_core_active_feature_set.json`
- `reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/alpha_evidence_gap_matrix.json`
- `reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/alpha_evidence_completion_closeout.json`

Required input columns in the ES feature parquets:

- `ts`
- `market`
- `year`
- `session_segment_id`
- `close`
- `feature_row_valid`
- `training_row_valid`

If any required input or column is missing, stop with `STOP_INPUT_FAILURE`.

## Exact Scope

- Market: `ES`
- Years: `2023,2024`
- Folds: only `ES_research_0001` through `ES_research_0012` from `reports/wfa/tier1_core_phase5_split_plan_20260706/split_plan.json`
- Holdout/forward rows: forbidden
- Provider/network access: forbidden
- Registry/trial-ledger/config mutation: forbidden
- Data/model/log mutation: forbidden

## Proposed Implementation Surface

Future implementation may add only these source files:

- `scripts/validation/build_markov_regime_es_intraday_diagnostic.py`
- `tests/validation/test_build_markov_regime_es_intraday_diagnostic.py`

The script must be report-only. It must fail if the output root already exists, and it must write only the exact expected output files listed below.

## Observation Grid And State Rule

Use a 30-minute observation grid derived from valid same-session ES rows:

- Sort rows by `ts`.
- Keep rows where `market == "ES"`, `year in {2023,2024}`, `feature_row_valid == true`, and `training_row_valid == true`.
- Within each `session_segment_id`, assign a valid-row counter.
- Observation rows are valid rows where the counter is divisible by 30 and the counter is at least 90.
- Do not create cross-session observations or transitions.

For each observation row:

- `return_60m_ticks = (close_t - close_t_minus_60_valid_rows) / 0.25`
- `prior_vol_60m_ticks = std(diff(close) / 0.25 over the prior 60 valid same-session rows)`
- `train_vol_floor_ticks = train-fold 10th percentile of positive prior_vol_60m_ticks`
- `normalized_return = return_60m_ticks / max(prior_vol_60m_ticks, train_vol_floor_ticks)`

State labels:

- `bull_up`: `normalized_return >= 1.0`
- `bear_down`: `normalized_return <= -1.0`
- `sideways`: otherwise

The next state is the state at the next 30-minute observation inside the same `session_segment_id`.

## Train-Only Fitting Rule

For each ES WFA fold:

- Fit `train_vol_floor_ticks` using train-fold observations only.
- Build the 3x3 transition matrix from train-fold state transitions only.
- Score only the matching test fold.
- Do not use test rows to choose thresholds, state definitions, horizons, windows, output filtering, or pass/fail thresholds.

## State-Count Rules

Hard input sufficiency rules:

- All 12 ES folds must be present in the split plan.
- Each evaluated fold must have at least `1000` train observations.
- Each evaluated fold must have at least `100` test observations.
- Each train state must have at least `50` observations.
- Each train state must have at least `30` outgoing transitions.
- Each test state must have at least `10` observations for stratified score reporting.

If any hard rule fails, mark the run `STOP_SPARSE_STATE_COVERAGE` and do not report model-trust readiness.

Transition matrix rules:

- Primary matrix uses raw counts normalized row-wise.
- Do not use pseudocount smoothing for the primary score.
- Optional Laplace-smoothed matrix with alpha `1.0` may be reported as diagnostic only and must not drive pass/fail status.

## Forecast Scores

Primary scores:

- next-state log loss versus realized next state;
- multiclass Brier score versus realized next state;
- fold-level score deltas versus baselines.

Required baselines:

- train-fold unconditional next-state base-rate forecast;
- same-state persistence forecast;
- shuffled-label null using fixed seed `20260709`;
- timing-shift null using one observation-step shift within each session.

No PnL, sizing, signal, or trading score is allowed in this diagnostic.

## Exact Output Paths

If implementation is later approved, the only allowed output root is:

`reports/model_trust_audit/markov_regime_es_intraday_v1/`

Expected files:

- `reports/model_trust_audit/markov_regime_es_intraday_v1/input_manifest.json`
- `reports/model_trust_audit/markov_regime_es_intraday_v1/markov_regime_es_intraday_v1_report.json`
- `reports/model_trust_audit/markov_regime_es_intraday_v1/markov_regime_es_intraday_v1_report.md`
- `reports/model_trust_audit/markov_regime_es_intraday_v1/fold_state_counts.csv`
- `reports/model_trust_audit/markov_regime_es_intraday_v1/fold_transition_matrices.csv`
- `reports/model_trust_audit/markov_regime_es_intraday_v1/fold_forecast_scores.csv`
- `reports/model_trust_audit/markov_regime_es_intraday_v1/baseline_null_scores.csv`
- `reports/model_trust_audit/markov_regime_es_intraday_v1/stress_grid_results.csv`
- `reports/model_trust_audit/markov_regime_es_intraday_v1/trial_accounting.json`

The script must stop if the output root already exists or if any unexpected output path would be created.

## Stress Grid

Stress-grid execution is optional and still requires explicit approval. If approved, the only allowed initial grid is:

- lookbacks: `30,60,120` minutes;
- normalized thresholds: `0.75,1.0,1.25`;
- forecast horizon: one 30-minute observation step for scoring;
- matrix powers `P^2`, `P^4`, and `P^8` for convergence diagnostics only.

Every grid row must be written to `trial_accounting.json` and `stress_grid_results.csv`. Do not select a winner from the grid.

## Runtime Budget

Maximum approved future runtime:

- Wall-clock timeout: `600` seconds.
- Scope limit: two ES parquet files, 12 ES folds, 9 stress-grid combinations.
- Network/provider calls: `0`.
- Generated output root: exactly one report root under `reports/model_trust_audit/markov_regime_es_intraday_v1/`.
- Stop immediately on missing input, existing output root, unexpected generated path, sparse-state blocker, cross-session transition, or test-fold leakage.

## Tests

Future implementation must include focused tests for:

- required input path and column validation;
- 30-minute same-session observation-grid construction;
- rejection of cross-session transitions;
- causal state construction using only prior rows;
- train-only `train_vol_floor_ticks` fitting;
- transition count and row-normalization math;
- sparse-state blocker behavior;
- baseline and null forecast construction;
- deterministic shuffled-label null with seed `20260709`;
- existing-output-root fail-closed behavior;
- exact expected output path enforcement.

Focused test command:

```powershell
python -m pytest -q -p no:cacheprovider tests\validation\test_build_markov_regime_es_intraday_diagnostic.py
```

## Validation Checks

Before any future execution:

- `git status --short` must be reviewed.
- `Test-Path reports\model_trust_audit\markov_regime_es_intraday_v1` must return `False`.
- All exact input paths above must exist.
- Implementation tests must pass.

After any future execution:

- `python -m pytest -q -p no:cacheprovider tests\validation\test_build_markov_regime_es_intraday_diagnostic.py`
- `python -m scripts.validation.check_coordination_docs` if coordination docs are edited.
- `git diff --check`
- `git status --short`
- Verify only the exact expected report files were created.
- Verify report JSON records input hashes, fold IDs, state-count status, baseline/null status, and a non-approval statement.

## Stop Conditions

Stop without execution or acceptance if:

- any input path, required column, or ES fold is missing;
- any output root already exists;
- any implementation needs holdout/forward rows;
- any implementation mutates registry, ledger, configs, data, logs, models, predictions, or existing reports;
- any state-count rule fails;
- baseline/null comparisons fail or are missing;
- stress-grid accounting is incomplete;
- any result is framed as alpha, sizing, trading, promotion, paper/live readiness, or rescue of a stopped line;
- HMM work is proposed before a separate approval packet.

## Next Allowed Step

If approved later, implement only `scripts/validation/build_markov_regime_es_intraday_diagnostic.py` and `tests/validation/test_build_markov_regime_es_intraday_diagnostic.py`, then stop after focused tests and no execution. Diagnostic execution remains a separate approval.
