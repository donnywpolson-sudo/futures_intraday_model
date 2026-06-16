# Current Pipeline

This project has a real research pipeline scaffold, but it is not yet a
complete alpha-generating or production backtesting system.

## Current Status

- `tier_1_research` has complete raw, causal, label, and baseline feature coverage.
- `tier_2_research` has complete raw, causal, and label coverage, but incomplete baseline feature coverage.
- `tier_3_research` has complete available raw, causal, and label coverage, but incomplete baseline feature coverage.
- Current Tier 1 model/research stack is `NO_GO` for promotion, tuning, and full WFA scale.
- Tier 1 data-audit universe is now guarded and marks all 8 Tier 1
  market-years usable: `ES`, `CL`, `ZN`, and `6E` for 2023-2024. This accepts
  Databento's documented OHLCV no-trade convention when local provenance
  passes. Guarded Phase 5 split smoke passed with
  `PASS WFA split plan: folds=48 markets=4 failures=0`. Guarded Phase 7
  one-fold smoke passed with
  `PASS WFA baseline: predictions=118188 models=4 folds=1 failures=0`.
- Guarded Phase 7 bounded 4-fold smoke passed structurally with
  `PASS WFA baseline: predictions=456712 models=4 folds=4 failures=0`.
  The first 4 split-plan folds are ES folds only. Phase 8 diagnostics on this
  smoke remain `NO_GO`: rows `114178`, trades `173`, net dollars `-4991.0`,
  `alpha_ready=False`, failures `0`. Anti-overfit robustness is `FAIL` with
  base net nonpositive, 1.5x and 2x cost-stress net nonpositive,
  single-market profit contribution above cap, and fold pass rate below
  minimum.
- Phase 8 policy diagnostics can evaluate saved predictions with costs, but they are not a live fill simulator or full execution backtester.
- Refreshed Phase 8 baseline evidence remains `NO_GO`: `baseline_refreshed`
  has 23 trades, `net_return_dollars=-2353.5`, and anti-overfit robustness
  `FAIL`.
- Latest Phase 9 ES-only checks remain stopped: `time_buckets` smoke stopped
  with discovery net `-25651.00` and confirmation net `-10929.00`;
  `post_shock_volume_confirmed_continuation` stopped with discovery net
  `-74112.00` and confirmation net `-259840.50`;
  `compression_breakout_participation_filter` stopped with discovery net
  `-121049.50` and confirmation net `-200103.00`.
- These Phase 9 checks failed the pre-registered stop rule. Do not tune or
  rerun variants from these results.

## Tier 1 No-Go Decision

- Decision: `TIER1_NO_GO_STOP_PROMOTION_TUNING_AND_FULL_WFA_SCALE`.
- Code state recorded in commit `c2794cf` (`Add Tier 1 ES research harness`).
- Do not continue full-market/full-fold WFA, model tuning, or promotion work from the current Tier 1 stack.
- The current evidence points to weak gross edge under the configured ES cost/slippage model, not a simple label-boundary issue.
- Refreshed anti-overfit audit failures are `base_net_nonpositive`,
  `cost_stress_1_5x_nonpositive`, `cost_stress_2x_nonpositive`,
  `single_market_profit_contribution_above_cap`, and
  `fold_pass_rate_below_minimum`.
- Guarded 4-fold data-audit smoke anti-overfit audit failures are also
  `base_net_nonpositive`, `cost_stress_1_5x_nonpositive`,
  `cost_stress_2x_nonpositive`,
  `single_market_profit_contribution_above_cap`, and
  `fold_pass_rate_below_minimum`; base net is `-4991.0` and fold pass rate is
  `0.25`.
- Data-audit universe:
  - usable: `ES 2023`, `ES 2024`, `CL 2023`, `CL 2024`, `ZN 2023`, `ZN 2024`, `6E 2023`, `6E 2024`
  - diagnostic-only: none under the current audited-universe policy
  - quarantined: none under the current audited-universe policy
- DBN-to-raw-parquet parity audit found no dropped rows and no
  OHLCV/timestamp mismatches for the previously blocked Tier 1 market-years:
  `CL 2023`, `CL 2024`, `ZN 2023`, `ZN 2024`, `6E 2023`, `6E 2024`.
- Source-level validation is blocked by Databento access: the available
  subscription only covers one year of L1 access, not the historical `trades`
  windows needed here.
- Databento documents `ohlcv-1m` as trade-derived with no record printed when
  no trade occurs in the interval. The audit now accepts that convention for
  audited universe decisions when local DBN/parquet provenance passes. This is
  not independent historical L1/trades proof; no Phase 2/session/fill semantic
  changes are justified from the current evidence.

Primary reports:

- `reports/pipeline_audit/tier1_consolidated_no_go_report.md`
- `reports/pipeline_audit/tier1_es_break_even_cost_audit.md`
- `reports/pipeline_audit/tier1_es_locked_selectivity_recheck.md`
- `reports/pipeline_audit/tier1_es_harness_family_sweep.md`
- `reports/metrics/baseline_refreshed/baseline_refreshed_metrics.json`
- `reports/experiments/anti_overfit_audit_refreshed.json`
- `reports/pipeline_audit/phase9_smoke_time_buckets_1x1_hypothesis_harness.md`
- `reports/pipeline_audit/phase9_post_shock_volume_confirmed_continuation_hypothesis_harness.md`
- `reports/pipeline_audit/phase9_compression_breakout_participation_filter_hypothesis_harness.md`
- `reports/pipeline_audit/tier_1_data_audit_decisions.md`
- `reports/pipeline_audit/tier_1_data_audit_universe.md`
- `reports/wfa_data_audit_guard_smoke/split_plan.json`
- `reports/wfa_data_audit_guard_phase7_smoke/data_audit_guard_smoke_wfa_report.json`
- `reports/wfa_data_audit_guard_phase7_smoke/data_audit_guard_smoke_predictions_manifest.json`
- `reports/wfa_data_audit_guard_tier1_smoke/data_audit_guard_tier1_smoke_wfa_report.json`
- `reports/wfa_data_audit_guard_tier1_smoke/data_audit_guard_tier1_smoke_predictions_manifest.json`
- `reports/metrics/data_audit_guard_tier1_smoke/data_audit_guard_tier1_smoke_metrics.json`
- `reports/experiments/anti_overfit_audit_data_audit_guard_tier1_smoke.json`

## Promotion Gates

Before calling the system research-alpha ready:

- Phase 4 baseline features must exist for the intended profile scope.
- Phase 7 must produce non-stale out-of-sample predictions across the intended WFA folds.
- Phase 8 must pass the costed promotion gate.
- Model promotion must remain blocked when net PnL, net Sharpe-like metrics, cost drag, or per-market/per-fold stability fail.

Before live or paper-live use:

- Contract-specific execution mapping must exist.
- Exchange calendar and early-close data must be refreshed.
- Fixed research slippage assumptions must be replaced by a live/paper fill model.
- A real execution layer must handle order lifecycle, fills, rejects, position state, risk limits, and audit logs.

## Phases In Simple Terms

- Phase 1A: download Databento DBN archives.
- Phase 1B: convert DBN archives into raw yearly parquet files.
- Phase 2: clean and normalize bars into causal session-aware data.
- Phase 3: create future-looking labels and cost-aware targets.
- Phase 4: build model features while excluding target and leakage columns.
- Phase 5: build walk-forward train/test splits with purge and embargo.
- Phase 6: no separate implemented phase in this repo.
- Phase 7: train baseline models and save out-of-sample predictions.
- Phase 8: score predictions with a deterministic research policy, costs, and promotion gates.

## Useful Checks

```powershell
python -m scripts.validation.check_tier_2_coverage --profile tier_1 --stage all
python -m scripts.validation.check_tier_2_coverage --profile tier_3 --stage features
python -m scripts.phase8_model_selection.evaluate_predictions --run baseline --require-promotion-ready
```
