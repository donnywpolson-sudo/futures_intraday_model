# Futures Intraday Model Pipeline

This file is the repo authority for pipeline rules, layout, runnable steps, and
current research status. The old `CURRENT_PIPELINE.md` and `project_layout.md`
stubs are archived under `_archive/pipeline_docs_migrated_to_pipeline_md/`; do
not reintroduce parallel phase checklists.

## Purpose

Build and audit an intraday futures research pipeline using Databento
continuous-contract 1-minute OHLCV data. The pipeline is for research, not live
trading. A strategy is not promotion-ready unless it passes structural,
economic, cost, holdout, and provenance gates.

Core principles:

- Correctness and reproducibility outrank model complexity.
- Continuous contracts are research series, not directly tradeable contracts.
- Pipeline integrity can pass while economic viability fails.
- Final holdout results must not choose features, models, calibration,
  thresholds, costs, or policy rules.
- Raw predictions are not positions. Deterministic policy and cost logic must
  convert predictions into evaluated signals.

## Non-Negotiable Rules

Data rules:

- Phase 1 preserves `ts_event`; Phase 2 converts `ts_event` to `ts`.
- Phase 1 must not fill missing 1-minute bars.
- Phase 2 is the first phase allowed to session-normalize, synthetic-mark, and
  causally gate rows.
- OHLCV DBN and definition DBN coverage are both required before raw parquet is
  trusted.
- Definition metadata must provide point-in-time `raw_symbol` and positive tick
  size metadata for every OHLCV instrument.
- Do not treat roll-adjustment artifacts as alpha.

Research rules:

- Fit preprocessing, feature selection, calibration, and models on train folds
  only.
- Generate predictions on test folds only.
- Keep final holdout isolated from research selection.
- Do not tune thresholds or rerun near-neighbor policy variants to rescue a
  locked failed baseline.
- Record tested variants, validation windows, costs, warnings, and stop rules.

Execution and risk rules:

- No overnight holds.
- Use realistic commission and slippage from `configs/costs.yaml`.
- Keep position policy deterministic and replayable from saved OOS predictions.
- Evaluate turnover, active-signal counts, market/year/fold concentration, cost
  drag, and stress scenarios before promotion.
- Live trading readiness is separate from research-pipeline readiness.

Artifact rules:

- Generated DBN/ZST/parquet/report/log/cache/model artifacts are local outputs
  and must remain untracked unless explicitly frozen under a reviewed artifact
  policy.
- Do not overwrite raw DBN archives or raw parquet unless intentionally using
  `--overwrite`.
- Existing non-empty final outputs are skipped by default by Phase 1A/1B unless
  `--overwrite` is set.
- Long data jobs must be smoke-first, bounded, and stopped after the first
  timeout or unexpected coverage mismatch.

## Active Layout

Important configs:

- `configs/alpha_tiered.yaml`: profile aliases, market sets, year sets.
- `configs/market_sessions.yaml`: session windows.
- `configs/costs.yaml`: commission/slippage/cost policy.
- `configs/models.yaml`: WFA, model, calibration, and holdout guardrails.

Profile policy from `configs/alpha_tiered.yaml`:

- Default profile: `tier_1`, aliasing to `tier_1_research`.
- Tier 0: smoke only, `ES` for 2024, never alpha evidence.
- Tier 1: core recent research, `ES`, `CL`, `ZN`, `6E` for 2023-2024.
- Tier 2: balanced robustness expansion, 15 markets for 2018-2024.
- Tier 3: full-universe stress, 33 markets for 2010-2024.
- Final holdout profiles use 2025 and forward profiles use 2026; both are
  locked validation scopes, not discovery tiers.

Core artifact flow:

```text
data/dbn/ohlcv_1m/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst
data/dbn/definition/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst
data/dbn/status/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst       (optional staged enrichment)
data/dbn/statistics/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst   (optional staged enrichment)
-> data/raw/{market}/{year}.parquet
-> reports/raw_ingest/raw_dbn_alignment*.{json,md}
-> data/causally_gated_normalized/{market}/{year}.parquet
-> data/labeled/{market}/{year}.parquet
-> data/feature_matrices/baseline/{market}/{year}.parquet
-> reports/wfa/split_plan.json
-> data/predictions/{run}/oos_predictions.parquet
-> reports/metrics/{run}_metrics.json
-> reports/phase8/alpha_promotion_decision.json
```

Implemented phase numbering:

| Phase | Name | Implemented entrypoint | Main output |
|---:|---|---|---|
| 1A | DBN archive download | `scripts.phase1A_download.download_databento_raw` | `data/dbn/.../*.dbn.zst` |
| 1B | Raw parquet stitch | `scripts.phase1B_convert.convert_databento_raw` | `data/raw/{market}/{year}.parquet` |
| 1C | Raw readiness gate | `scripts.validation.audit_raw_dbn_alignment` | `reports/raw_ingest/raw_dbn_alignment*.{json,md}` |
| 2 | Causal base | `scripts.phase2_causal_base.build_causal_base_data` | `data/causally_gated_normalized/{market}/{year}.parquet` |
| 3 | Labels/targets | `scripts.phase3_labels.build_labels` | `data/labeled/{market}/{year}.parquet` |
| 4 | Baseline features | `scripts.phase4_features.build_baseline_features` | `data/feature_matrices/baseline/{market}/{year}.parquet` |
| 5 | WFA split plan | `scripts.phase5_wfa.build_wfa_splits` | `reports/wfa/split_plan.json` |
| 6 | WFA model training/OOS predictions | `scripts.phase6_wfa.run_wfa` | `data/predictions/{run}/oos_predictions.parquet` |
| 7 | Legacy WFA implementation package | `scripts.phase7_wfa.*` | imported by Phase 6 wrappers |
| 8 | Prediction evaluation/model selection | `scripts.phase8_model_selection.evaluate_predictions` | `reports/phase8/alpha_promotion_decision.json` |
| 9 | Bounded research harnesses | `scripts.phase9_research.*` | `reports/pipeline_audit/...` |

Resolved drift:

- `project_layout.md` previously described an aspirational 22-phase model and
  referenced future metrics, gate, and execution-cost commands that do not
  exist in the current repo.
- Current runnable docs must use the implemented Phase 5 split builder, Phase 6
  WFA wrapper, legacy Phase 7 implementation package, and Phase 8 evaluator.

Generated staging roots:

- `data/raw_alignment_candidate_2026`: temporary replacement candidates for
  raw parquet files whose canonical `data/raw` source hashes are stale versus
  current 2026 OHLCV DBNs.
- `data/raw_alignment_candidate_definition_fix`: temporary candidates used to
  diagnose definition metadata mismatches.
- `data/raw_alignment_candidate_missing_fill`: temporary candidates for missing
  canonical raw market-years that have local OHLCV and definition DBNs.
- `data/raw_enriched_candidate`: temporary status/statistics enrichment
  candidate output. It remains OHLCV 1-minute grained and is not a separate
  schema-level parquet dataset.

These staging roots are ignored generated artifacts. They are not normal
downstream inputs, and promotion into `data/raw` requires separate explicit
approval.

## Pipeline Runbook

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
python -m scripts.validation.audit_raw_dbn_alignment --config configs/alpha_tiered.yaml --profile tier_3 --dbn-root data\dbn --raw-root data\raw --json-out reports\raw_ingest\raw_dbn_alignment.json --md-out reports\raw_ingest\raw_dbn_alignment.md
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

Purpose: validate raw bars, normalize sessions, identify roll windows, mark
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
python -m scripts.phase3_labels.build_labels --profile tier_1
```

Inputs:

- `data/causally_gated_normalized/{market}/{year}.parquet`
- `configs/costs.yaml`

Outputs:

- `data/labeled/{market}/{year}.parquet`
- `reports/labels/`

Acceptance checks:

- Label horizons respect intraday/session validity.
- Target columns are present and separated from feature columns downstream.
- Cost-aware validity flags are generated from configured costs, not ad hoc
  assumptions.

Stop conditions:

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

Acceptance checks:

- Feature registry excludes target, leakage, timestamp, and metadata columns.
- Raw status/statistics enrichment columns are excluded from default features;
  model use requires a later feature-hypothesis change with leakage checks and
  registry updates.
- Feature rows line up with label rows.
- Baseline features are causal and do not use final-holdout full-sample
  statistics.

Stop conditions:

- Any target/leakage column enters `feature_cols.json`.
- Cost config is provisional under strict research settings.
- Feature matrix row count or market-year scope does not match labels.

### 5. Build WFA Splits

Purpose: build deterministic train/test fold definitions with purge and embargo.

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
- Final-holdout rows are excluded unless an explicit final-holdout split run is
  being built with the appropriate guard.

Stop conditions:

- Empty folds.
- Profile/year/market mismatch.
- Missing provenance required by downstream WFA.

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

Acceptance checks:

- Imputer/scaler/model fit happens on train fold only.
- Predictions are test-fold rows only.
- Prediction manifest hash, row count, path, profile, resolved profile, markets,
  years, and split-plan provenance match actual artifacts.
- `artifact_evidence_ready=true`.

Stop conditions:

- Any stale output path is detected.
- Prediction manifest does not match actual parquet.
- Fold failure count is nonzero.
- Model collapses to constant or class-prior-only predictions without an
  explicit diagnostic decision.

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

Acceptance checks:

- Prediction manifest matches actual prediction parquet.
- Final holdout is not consumed for selection/calibration.
- Costs, turnover, active-signal rows, market/fold/year breakdowns, and blocker
  reasons are reported.
- Structural pass and alpha promotion are separate decisions.

Stop conditions:

- `final_holdout_touched=true` for research selection.
- Artifact evidence is stale or mismatched.
- Gross/net/cost gates fail.
- Promotion check fails; this is expected for the locked negative Tier 1
  baseline and must not be "rescued" with threshold tuning.

### 9. Research Harnesses

Purpose: run bounded feasibility tests for new target/feature hypotheses after
baseline failure.

Rules:

- Pre-register hypothesis, scope, controls, metrics, and stop rules.
- Run smoke first.
- Do not use a stopped branch as a "new" hypothesis.
- Do not proceed from oracle/feasibility evidence directly to full WFA.
- Require materially different target or feature work after a stopped branch.

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
rg -n "scripts\.(buil[d]_|run_execution_cost[s]|run_gat[e])|Phase (7[A]|8[A]|2[2])" PIPELINE.md README.md README_RUNBOOK.md docs
git diff --check
git status --short
```

## Current Status Appendix

Status date: June 17, 2026 local project notes.

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
