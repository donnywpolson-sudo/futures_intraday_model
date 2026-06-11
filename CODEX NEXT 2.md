You are working in my `quant_project` repo.

Task: implement the downstream ML planning/layout changes we discussed, while preserving the already-built phases 1-4. This is primarily a project-structure, config, schema, and test update. Do not build a full production ML training system unless matching scaffolding already exists and the change is minimal.

Hard constraints:

* Do not rewrite phases 1-4.
* Do not add neural nets, transformers, reinforcement learning, alternative data, order book data, or hyperparameter tuning.
* Do not change data artifacts.
* Do not commit generated parquet/dbn/zst/model binary artifacts.
* Do not introduce final-holdout leakage.
* Do not use random train/test splits.
* Keep the existing causal/WFA/cost/turnover discipline intact.
* Prefer minimal, explicit, auditable changes.
* If a requested file path does not exist, create the smallest appropriate version.
* If similar repo conventions already exist, follow them instead of inventing a parallel structure.

Current context:

* Phases 1-4 are complete.
* Downstream ML has not been built yet.
* The current layout is strong on data, labels, features, WFA, costs, and gates.
* The weak point is that the downstream ML layer is too Ridge-only / vague.
* We need to preserve a staged downstream plan:

  1. Phase 7A linear controls.
  2. Phase 7B sklearn nonlinear challenger.
  3. Phase 7C optional LightGBM/XGBoost challenger.
  4. Phase 8A calibration/model comparison.
  5. Phase 15 frozen feature + model + calibration + policy set.
* The highest-priority future classifier is trend-danger / do-not-fade, because the strategy style is vulnerable to fading real trend days.

First inspect:

* `project_layout.md`
* `configs/`
* `scripts/`
* `pipeline/`
* `tests/`
* any existing model/WFA/target/schema config files
* existing test style and naming conventions

Then implement the following changes.

1. Update `project_layout.md`

Edit `project_layout.md` so the downstream ML layer is explicit.

Keep phases 1-4 structurally unchanged.

Add a downstream ML policy section:

```text
Downstream ML model policy

The pipeline treats model choice as a staged research comparison, not a single hardcoded model.

Required staged order:
- Phase 7A: linear control models
- Phase 7B: sklearn nonlinear challenger
- Phase 7C: optional LightGBM/XGBoost challenger
- Phase 8A: probability calibration and model comparison
- Phase 15: frozen feature + model + calibration + policy set

Do not use neural nets, transformers, or reinforcement learning until simpler tabular models survive WFA, costs, turnover, final holdout, and prop-firm simulation.
```

Add approved initial model families:

```text
ridge_return
logistic_direction
logistic_fade_success
logistic_trend_danger
hist_gradient_boosting_direction
hist_gradient_boosting_fade_success
hist_gradient_boosting_trend_danger
lightgbm_direction_optional
xgboost_direction_optional
```

State that all models must use:

* train-fold-only fitting
* train-only imputation
* train-only scaling where applicable
* test-fold-only prediction
* no random train/test split
* no final-holdout tuning
* `model_id` recorded in all prediction/metric reports
* model config hash recorded in all prediction/metric reports
* feature config hash recorded in all prediction/metric reports

2. Fix WFA purge policy

Find any place where purge is hardcoded as:

```text
purge_bars = 15
```

or equivalent.

Change the layout/spec/config so purge is auto-resolved:

```text
entry_lag_bars = 1
target_horizon_bars = 15
purge_bars = auto
resolved_purge_bars = entry_lag_bars + target_horizon_bars
default resolved_purge_bars = 16
```

Reason:

* Features use completed bar `t`.
* Entry occurs on bar `t+1`.
* 15-minute target exits at `t+1+15`.
* Therefore target touches through `t+16`.
* Purge must cover that full dependency window.

If there is existing code that resolves purge, update it minimally. If no code exists yet, add only a small helper and tests if that fits repo structure.

3. Add target groups to the layout/spec

Add or update target groups so downstream ML tasks are explicit.

Required target groups:

```yaml
return_target:
  - target_ret_15m
  - target_ret_ticks_15m
  - target_net_ticks_after_est_cost
  - target_net_dollars_after_est_cost

direction_target:
  - target_sign_15m
  - target_sign_with_deadzone
  - target_tradeable_after_cost

fade_success_target:
  - target_fade_long_success_15m
  - target_fade_short_success_15m
  - target_fade_success_15m

trend_danger_target:
  - target_trend_danger_long_30m
  - target_trend_danger_short_30m
  - target_trend_danger_30m
```

Important:

* Fade-success and trend-danger labels are targets only.
* They may be built using future information inside target construction.
* They must never be used as features.
* They must be excluded from feature matrices.

If there is an existing target registry file, update it. If not, document this in `project_layout.md` and create the smallest appropriate registry/config file only if repo conventions support that.

4. Replace Ridge-only Phase 7 language

Where Phase 7 currently says or implies:

```text
model = Ridge baseline
```

replace with staged model policy:

```yaml
Phase 7A linear controls:
  ridge_return_v1:
    model_family: ridge_regression
    task: regression
    target: target_ret_15m

  logistic_direction_v1:
    model_family: logistic_regression
    task: classification
    target: target_sign_with_deadzone

  logistic_fade_success_v1:
    model_family: logistic_regression
    task: classification
    target: target_fade_success_15m

  logistic_trend_danger_v1:
    model_family: logistic_regression
    task: classification
    target: target_trend_danger_30m

Phase 7B nonlinear challengers:
  histgb_direction_v1:
    model_family: hist_gradient_boosting
    task: classification
    target: target_sign_with_deadzone

  histgb_fade_success_v1:
    model_family: hist_gradient_boosting
    task: classification
    target: target_fade_success_15m

  histgb_trend_danger_v1:
    model_family: hist_gradient_boosting
    task: classification
    target: target_trend_danger_30m

Phase 7C optional serious nonlinear challengers:
  lightgbm_*:
    model_family: lightgbm
    enabled_by_default: false
    cpu_first: true

  xgboost_*:
    model_family: xgboost
    enabled_by_default: false
    cpu_first: true
```

State clearly:

* Ridge/logistic are controls.
* HistGradientBoosting is the first nonlinear challenger.
* LightGBM/XGBoost are optional downstream challengers.
* Optional external dependencies must not be required for baseline tests to pass.

5. Add `configs/models.yaml`

Create or update:

```text
configs/models.yaml
```

It should be valid YAML and should define a staged model registry.

Use this as the intended content unless existing repo conventions require small adjustments:

```yaml
version: 1

policy:
  random_splits_allowed: false
  final_holdout_tuning_allowed: false
  neural_nets_allowed: false
  reinforcement_learning_allowed: false
  hyperparameter_tuning_allowed_initially: false
  optional_external_model_dependencies_required: false

purge:
  entry_lag_bars: 1
  target_horizon_bars: 15
  purge_bars: auto
  resolved_purge_bars: 16

model_stages:
  phase_7a_linear_controls:
    required: true
    description: "Linear control models used as the first honest benchmark."

  phase_7b_sklearn_nonlinear:
    required: false
    description: "First nonlinear challenger using sklearn histogram gradient boosting."

  phase_7c_optional_boosted_trees:
    required: false
    description: "Optional LightGBM/XGBoost challengers, CPU-first."

models:
  ridge_return_v1:
    stage: phase_7a_linear_controls
    family: ridge_regression
    task: regression
    target: target_ret_15m
    enabled: true
    requires_optional_dependency: false

  logistic_direction_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_sign_with_deadzone
    enabled: true
    requires_optional_dependency: false

  logistic_fade_success_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_fade_success_15m
    enabled: true
    requires_optional_dependency: false

  logistic_trend_danger_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_trend_danger_30m
    enabled: true
    requires_optional_dependency: false

  histgb_direction_v1:
    stage: phase_7b_sklearn_nonlinear
    family: hist_gradient_boosting
    task: classification
    target: target_sign_with_deadzone
    enabled: false
    requires_optional_dependency: false

  histgb_fade_success_v1:
    stage: phase_7b_sklearn_nonlinear
    family: hist_gradient_boosting
    task: classification
    target: target_fade_success_15m
    enabled: false
    requires_optional_dependency: false

  histgb_trend_danger_v1:
    stage: phase_7b_sklearn_nonlinear
    family: hist_gradient_boosting
    task: classification
    target: target_trend_danger_30m
    enabled: false
    requires_optional_dependency: false

  lightgbm_direction_v1:
    stage: phase_7c_optional_boosted_trees
    family: lightgbm
    task: classification
    target: target_sign_with_deadzone
    enabled: false
    cpu_first: true
    requires_optional_dependency: true

  xgboost_direction_v1:
    stage: phase_7c_optional_boosted_trees
    family: xgboost
    task: classification
    target: target_sign_with_deadzone
    enabled: false
    cpu_first: true
    requires_optional_dependency: true
```

If existing config style is different, adapt while preserving all semantic requirements.

6. Add prediction schema for multi-model OOS outputs

Update `project_layout.md` and any schema/config/test files so OOS prediction tables can support multiple models and targets.

Required columns:

```text
market
year
fold_id
timestamp
session_id or session_segment_id if available
model_id
model_family
target_name
prediction_type
y_true
y_pred_raw
y_pred_calibrated
p_long
p_short
p_flat
p_fade_success
p_trend_danger
calibration_id
model_config_hash
feature_config_hash
execution_open
execution_close
target_valid
```

Rules:

* Regression models may leave probability columns null.
* Classification models should populate relevant probability columns when available.
* Raw predictions and calibrated predictions must be separate.
* Position policy must consume calibrated/model-score fields, not blindly trade raw predictions.

7. Add model-selection reports to the layout/spec

Add these report artifacts:

```text
reports/model_selection/model_comparison.csv
reports/model_selection/model_selection_report.json
reports/model_selection/calibration_report.json
```

Reports must be grouped by:

* `model_id`
* `model_family`
* `target_name`
* market
* fold
* train/test window
* config hash

Model comparison must include, where available:

* gross return
* net return
* gross Sharpe
* net Sharpe
* max drawdown
* turnover/bar
* trade count
* cost drag
* per-market metrics
* per-fold stability
* trend-day behavior
* fade-allowed vs fade-blocked behavior
* final-holdout excluded from selection

8. Add calibration phase/spec

Add Phase 8A or equivalent:

```text
Phase 8A: Signal calibration and model comparison
```

Rules:

* Calibration is fit on train fold or train-internal calibration split only.
* Calibration cannot be fit on the test fold.
* Calibration cannot use final holdout.
* Calibration outputs must have `calibration_id`.
* Raw model score and calibrated score must both be preserved.
* Calibration can be skipped for a model, but the skip must be explicit in reports.

Allowed calibration approaches:

* none
* logistic/Platt style
* isotonic only if enough data and train-only fitting is enforced

Do not implement expensive calibration if no infrastructure exists. At minimum, document the schema and add tests/config validation hooks.

9. Update position policy language

Update layout/spec so Phase 9 position policy consumes multiple model outputs.

Required policy inputs may include:

```text
expected_return
p_long
p_short
p_flat
p_fade_success
p_trend_danger
```

Required rule:

* `p_trend_danger` can block fade trades.
* `p_fade_success` can allow or disallow fade trades.
* raw return prediction alone should not directly become trades.
* deterministic policy converts model scores into flat/long/short/size/add/no-add decisions.
* all policy choices must be replayable from saved OOS predictions and config.

10. Update Phase 15 freeze policy

Rename or update Phase 15 from:

```text
Frozen Feature + Policy Set
```

to:

```text
Frozen Feature + Model + Calibration + Policy Set
```

Required frozen artifacts:

```text
data/frozen_features/phase5_v1/feature_cols.json
data/frozen_features/phase5_v1/selected_features.csv
data/frozen_features/phase5_v1/rejected_features.csv
data/frozen_features/phase5_v1/policy_config.json
data/frozen_features/phase5_v1/manifest.json

data/frozen_models/phase5_v1/model_config.yaml
data/frozen_models/phase5_v1/model_selection_report.json
data/frozen_models/phase5_v1/calibration_config.yaml
data/frozen_models/phase5_v1/manifest.json
```

Rules:

* Final holdout may only use frozen features, frozen model config, frozen calibration config, and frozen policy config.
* Final holdout cannot choose a model.
* Final holdout cannot tune thresholds.
* Final holdout cannot change calibration.
* Final holdout cannot change features.
* Frozen artifacts must include config hashes.

11. Add validation/tests

Add or update tests using the repo’s existing test style.

Required tests, names may vary to fit repo style:

A. Model registry validation

* `configs/models.yaml` parses.
* required linear control models exist.
* optional LightGBM/XGBoost models are disabled by default.
* no neural net / transformer / RL families are enabled.
* every model has model id, family, task, target, stage, enabled flag.

B. Purge auto-resolution

* entry_lag_bars=1 and target_horizon_bars=15 resolves to 16.
* hardcoded 15 is not accepted as resolved purge for this target alignment.
* if a helper exists, test it directly.

C. Target group exclusion

* return/direction/fade/trend-danger targets are target columns, not feature columns.
* fade-success and trend-danger targets are excluded from X/features.

D. Multi-model prediction schema

* required OOS prediction columns are defined.
* schema supports multiple `model_id` values.
* schema supports raw and calibrated predictions separately.
* probability columns are allowed to be null for regression.

E. Calibration train-only discipline

* calibration is specified as train-only.
* final holdout is excluded from calibration.
* reports must include `calibration_id` or explicit no-calibration marker.

F. Model selection excludes final holdout

* model comparison/report spec says final holdout is excluded.
* frozen model is selected before final holdout.

G. Frozen model immutability

* final holdout consumes frozen features/model/calibration/policy only.
* frozen config hashes are required.

H. Project layout consistency

* `project_layout.md` mentions:

  * Phase 7A linear controls
  * Phase 7B HistGradientBoosting challengers
  * Phase 7C optional LightGBM/XGBoost challengers
  * Phase 8A calibration/model comparison
  * Phase 15 frozen feature + model + calibration + policy set
  * trend-danger / do-not-fade classifier

12. Optional lightweight implementation

If the repo already has validation scripts for configs/schemas, add minimal support for:

* loading `configs/models.yaml`
* validating allowed model families
* resolving purge
* emitting/validating model config hash if an existing hash utility exists

Do not create a large framework. Keep it small and testable.

13. Run checks

Run the relevant tests. Prefer:

```powershell
pytest
```

If full tests are too slow, run targeted tests first, then explain what was not run.

Also run any existing formatting/linting commands if they are clearly part of the repo workflow.

14. Final response

Return:

* files changed
* tests run
* any tests not run
* any assumptions made
* exact follow-up command I should run next if needed

Do not include generic ML advice.
Do not praise the project.
Do not suggest unrelated refactors.
