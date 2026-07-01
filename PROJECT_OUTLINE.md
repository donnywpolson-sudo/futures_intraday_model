# Futures Intraday Model Project Outline

## Current Status Note

- `AGENTS.md` is the active operating rulebook for scope, safety, validation, and final-response format.
- `CODEX_HANDOFF.md` is mutable cross-run state. Use it for current blockers, latest decisions, and exact next recommended steps.
- `PIPELINE.md`, when present in the active worktree, is the runnable workflow authority for phase order, commands, acceptance checks, and stop conditions.
- This file is reference and planning material. It does not authorize broad data builds, WFA/model runs, provider downloads, cleanup, artifact promotion, live trading, or paper execution by itself.
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
- `CODEX_HANDOFF.md`: current state and continuation state for multi-step Codex work.
- `PIPELINE.md`: runnable phase workflow authority when present.
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

This section mirrors the repo's implemented workflow at a planning level. Use the active `PIPELINE.md` or an approved bounded plan for exact commands.

| Phase | Purpose | Main implementation area | Main output class |
| --- | --- | --- | --- |
| 1A | Download immutable Databento DBN/ZST archives | `scripts.phase1A_download.download_databento_raw` | `data/dbn/.../*.dbn.zst` |
| 1B | Convert DBN archives to raw parquet while preserving raw event semantics | `scripts.phase1B_convert.convert_databento_raw` | `data/raw/{market}/{year}.parquet` |
| 1C | Audit raw DBN/raw parquet coverage, schema, and alignment | `scripts.phase1C_validate.audit_raw_dbn_alignment` | `reports/raw_ingest/*` |
| 2 | Build causal base data with session normalization and synthetic/degraded row diagnostics | `scripts.phase2_causal_base.build_causal_base_data` | `data/causally_gated_normalized/{market}/{year}.parquet` |
| 3 | Build labels/targets with explicit entry lag and horizon semantics | `scripts.phase3_labels.build_labels` | `data/labeled/{market}/{year}.parquet` |
| 4 | Build baseline feature matrices from causal inputs only | `scripts.phase4_features.build_baseline_features` | `data/feature_matrices/baseline/{market}/{year}.parquet` |
| 5 | Build chronological WFA split plans with purge/embargo rules | `scripts.phase5_wfa.build_wfa_splits` | `reports/wfa/split_plan.json` |
| 6 | Train WFA models and write out-of-sample predictions | `scripts.phase6_wfa.run_wfa` | `data/predictions/{run}/oos_predictions.parquet` |
| 7 | Maintain legacy WFA implementation package consumed by Phase 6 | `scripts.phase7_wfa.*` | support code and combined predictions |
| 8 | Evaluate predictions, costs, policy alignment, and promotion readiness | `scripts.phase8_model_selection.*` | `reports/phase8/*` |
| 9 | Run bounded research harnesses and adversarial audits | `scripts.phase9_research.*` | `reports/pipeline_audit/*` or focused reports |
| 10 | Guard locked holdout/forward evaluation | `scripts.final_holdout.guard_final_holdout` | holdout approval/block evidence |
| 11 | Freeze approved research artifacts only after explicit approval | `scripts.artifact_freeze.freeze_research_artifacts` | frozen artifact metadata |

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
- result manifests and reports recording config, data scope, validation windows, costs, warnings, and failure modes;
- no post-test retuning or cherry-picked metric is used as acceptance evidence.

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
