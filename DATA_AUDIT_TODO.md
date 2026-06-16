# Tier 1 Data Audit Status

Snapshot updated: 2026-06-16. Refresh generated reports before acting.

## Current State

- Tier 1 missing-minute records are complete for `ES CL ZN 6E`, 2010-2024:
  - records: `60 / 60`
  - status: all `PASS`
  - windows: `492996`
  - missing minutes: `803433`
  - failures: `0`
- Tier 1 OHLCV provenance/continuity reports are complete for `ES CL ZN 6E`, 2010-2024.
- Tier 1 decision table exists:
  - `reports/pipeline_audit/tier_1_data_audit_decisions.json`
  - `reports/pipeline_audit/tier_1_data_audit_decisions.md`
  - status: `PASS`
- Tier 1 data-audit universe exists:
  - `reports/pipeline_audit/tier_1_data_audit_universe.json`
  - `reports/pipeline_audit/tier_1_data_audit_universe.md`
  - status: `PASS`
  - usable: `ES 2023`, `ES 2024`, `CL 2023`, `CL 2024`, `ZN 2023`, `ZN 2024`, `6E 2023`, `6E 2024`
  - diagnostic-only: none under the current audited-universe policy
  - quarantined: none under the current audited-universe policy
- Guarded Phase 5 split smoke passed:
  - `reports/wfa_data_audit_guard_smoke/split_plan.json`
  - result: `PASS WFA split plan: folds=48 markets=4 failures=0`
  - fold markets: `ES`, `CL`, `ZN`, `6E`
  - failures: `0`
- Guarded Phase 7 one-fold smoke passed:
  - `reports/wfa_data_audit_guard_phase7_smoke/data_audit_guard_smoke_wfa_report.json`
  - `reports/wfa_data_audit_guard_phase7_smoke/data_audit_guard_smoke_predictions_manifest.json`
  - result: `PASS WFA baseline: predictions=118188 models=4 folds=1 failures=0`
  - predictions: `118188`
  - models: `4`
  - folds: `1`
  - failures: `0`

## Current Interpretation

- Databento documents `ohlcv-1m` as trade-derived and prints no OHLCV record when no trade occurs in an interval.
- The audited-universe policy now accepts that Databento OHLCV no-trade convention when local provenance passes.
- DBN-to-raw-parquet parity audit found no dropped rows and no OHLCV/timestamp mismatches for the previously blocked Tier 1 market-years:
  `CL 2023`, `CL 2024`, `ZN 2023`, `ZN 2024`, `6E 2023`, `6E 2024`.
- Acceptance relies on Databento's documented OHLCV convention plus local DBN/parquet provenance.
- No independent historical L1/trades verification is available under the current subscription, so the audit does not independently prove every missing OHLCV minute had no trade.
- No Phase 2/session/fill semantic changes are justified from the audit.

## What Is Done

1. Missing-minute verification for Tier 1 long years.
2. OHLCV provenance/continuity audit for Tier 1 long years.
3. Tier 1 decision table with roll/symbol/instrument synthetic counts.
4. Tier 1 usable/quarantined/diagnostic-only universe.
5. Optional WFA data-audit universe guard wired through Phase 5 and Phase 7.
6. Guarded Phase 5 split smoke, producing 48 folds across `ES`, `CL`, `ZN`, and `6E`.
7. Guarded Phase 7 one-fold smoke, recording current data-audit universe evidence.

## Next Valid Step

Decide whether to run a broader guarded Phase 7 check against the full audited Tier 1 split plan, or stop the data-audit workflow here and return to pre-registered hypothesis work.

Do not run full-market WFA scale, tune models, or search for alpha from this data-audit result.

## Reference Commands

Regenerate the Tier 1 decision table:

```powershell
python -m scripts.validation.build_tier_1_data_audit_decisions `
  --decision-table-json reports/pipeline_audit/tier_1_data_audit_decisions.json `
  --json-out reports/pipeline_audit/tier_1_data_audit_decisions.json `
  --md-out reports/pipeline_audit/tier_1_data_audit_decisions.md
```

Regenerate the Tier 1 universe:

```powershell
python -m scripts.validation.build_data_audit_universe `
  --decision-table-json reports/pipeline_audit/tier_1_data_audit_decisions.json `
  --profile tier_1 `
  --profile-config configs/alpha_tiered.yaml `
  --diagnostic-only-markets CL `
  --accept-databento-ohlcv-no-trade-convention `
  --json-out reports/pipeline_audit/tier_1_data_audit_universe.json `
  --md-out reports/pipeline_audit/tier_1_data_audit_universe.md `
  --require-usable
```

Regenerate the guarded Phase 5 split smoke:

```powershell
python -m scripts.phase5_wfa.build_wfa_splits `
  --profile tier_1 `
  --input-root data/feature_matrices/baseline `
  --reports-root reports/wfa_data_audit_guard_smoke `
  --profile-config configs/alpha_tiered.yaml `
  --models-config configs/models.yaml `
  --data-audit-universe-json reports/pipeline_audit/tier_1_data_audit_universe.json
```

Run the guarded Phase 7 one-fold smoke:

```powershell
python -m scripts.phase7_wfa.run_wfa `
  --profile tier_1 `
  --matrix baseline `
  --run data_audit_guard_smoke `
  --input-root data/feature_matrices/baseline `
  --split-plan reports/wfa_data_audit_guard_smoke/split_plan.json `
  --predictions-root data/predictions `
  --reports-root reports/wfa_data_audit_guard_phase7_smoke `
  --models-config configs/models.yaml `
  --max-folds 1 `
  --data-audit-universe-json reports/pipeline_audit/tier_1_data_audit_universe.json
```

## Do Not Do From This Audit Alone

- Do not change Phase 2/session/fill semantics.
- Do not run broad model tuning or full WFA scaling.
- Do not treat Databento OHLCV no-trade convention acceptance as independent historical L1/trades proof.
- Do not stage or commit generated `data/` or `reports/` artifacts.
