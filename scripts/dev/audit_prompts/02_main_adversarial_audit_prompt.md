# Main Adversarial Audit Prompt

Use in Codex Plan Mode / read-only.

MODE: PLAN / READ-ONLY AUDIT ONLY.
You are an adversarial quant/code auditor. Assume this intraday futures model is broken until proven otherwise.

Goal:
Find what is wrong and how to fix it. Be token-efficient. No reassurance. No generic ML advice. No long explanations. No clean-stage praise.

Allowed inspection only:
- Use static read-only commands only: `rg`, `git status/log/show/diff`, `Test-Path`, `Get-ChildItem`, `Get-Content`, and parse-only snippets that do not import project modules, write files, create caches, or run scripts.
- Do not run tests, `py_compile`, WFA, Phase 8, Phase 9 harnesses, rebuilds, report writers, ledger writers, freeze/final-holdout scripts, hygiene scripts, or artifact generators.
- If a command would create/overwrite data, reports, predictions, logs, JSON/CSV, parquet, DBN, zst, caches, model artifacts, or `artifacts/frozen`, list it only.

Identity gate:
- Confirm current directory, git branch/status with `git status --short --branch`, remote from `.git/config` or other read-only git metadata, and top-level files.
- Required repo identity paths:
  - `.git/`
  - `PIPELINE.md`
  - `AGENTS.md`
  - `configs/alpha_tiered.yaml`
  - `configs/models.yaml`
  - `configs/costs.yaml`
  - `configs/market_sessions.yaml`
  - `scripts/`
  - `scripts/dev/audit_prompts/`
  - `scripts/dev/audit_prompts/README.md`
  - `scripts/dev/audit_prompts/02_main_adversarial_audit_prompt.md`
  - `scripts/phase9_research/`
  - `tests/`
  - `manifests/`
  - `manifests/feature_sets/`
  - `manifests/feature_hypotheses/`
  - `manifests/target_hypotheses/`
- Generated evidence folders are optional audit targets when present, not identity requirements:
  - `data/`
  - `reports/`
  - `reports/pipeline_audit/`
  - `reports/phase8_failure_breakdown/`
  - `reports/model_selection/`
  - `reports/experiments/`
  - `reports/raw_readiness/`
  - `reports/source_gap_audit/`
  - `reports/raw_data_snapshot/`
  - `reports/validation/`
  - `reports/final_holdout/`
  - `artifacts/frozen/`
- If this is not the intraday futures model repo, stop with:
  Wrong repo selected - switch repo/folder before audit.

Canonical scripts to inspect, not run:
- `scripts/run_wfa.py`
- `scripts/phase1A_download/download_databento_raw.py`
- `scripts/phase1B_convert/convert_databento_raw.py`
- `scripts/phase1C_validate/audit_raw_dbn_alignment.py`
- `scripts/phase2_causal_base/build_causal_base_data.py`
- `scripts/phase3_labels/build_labels.py`
- `scripts/phase4_features/build_baseline_features.py`
- `scripts/phase5_wfa/build_wfa_splits.py`
- `scripts/phase6_wfa/run_wfa.py`
- `scripts/phase6_wfa/combine_wfa_predictions.py`
- `scripts/phase7_wfa/run_wfa.py`
- `scripts/phase7_wfa/combine_wfa_predictions.py`
- `scripts/phase8_model_selection/evaluate_predictions.py`
- `scripts/phase8_model_selection/audit_*.py`
- `scripts/phase9_research/feature_hypothesis_registry.py`
- `scripts/phase9_research/es_hypothesis_harness.py`
- `scripts/phase9_research/tier1_cost_clearability_event_harness.py`
- `scripts/phase9_research/tier1_market_balanced_cost_clearability_harness.py`
- `scripts/phase9_research/liquidity_cost_state_harness.py`
- `scripts/phase9_research/directional_path_quality_target_harness.py`
- relevant `scripts/validation/` raw-readiness, provenance, and data-audit guard scripts
- `scripts/experiments/run_anti_overfit_audit.py`
- `scripts/experiments/robustness_gate.py`
- `scripts/experiments/ledger.py`
- `scripts/final_holdout/guard_final_holdout.py`
- `scripts/artifact_freeze/freeze_research_artifacts.py`
- `scripts/check_git_hygiene.py`
- `scripts/utilities/precommit_block_generated_artifacts.py`

Scope:
- Repo: current working directory only.
- Audit only Tier 1 alias resolved from `configs/alpha_tiered.yaml`.
- Current expected alias to verify: `tier_1 -> tier_1_research`.
- Current expected Tier 1 research scope to verify: `ES`, `CL`, `ZN`, `6E` for years `2023`, `2024`.
- Do not audit `tier_1_holdout` or `tier_1_forward` except for leakage/contamination checks.
- Use `PIPELINE.md` as orientation; independently verify all claims.
- Treat root docs/planning files as orientation only, not pipeline truth: `README.md`, `README_RUNBOOK.md`, `RESOURCES.md`, `RESEARCH_METRICS.html`.
- Ignore `_archive/` and cleanup folders unless auditing provenance explicitly.

Current feature/target research state to verify, not assume:
- `manifests/feature_sets/baseline_current.json` is the only WFA-allowed frozen feature set.
- `baseline_current` expected `feature_count` is `122`; verify against `baseline_current_features.txt` and `data/feature_matrices/baseline/feature_cols.json`.
- `manifests/feature_hypotheses/registry.json` and `trial_statuses.jsonl` are authoritative for feature hypothesis status.
- `manifests/target_hypotheses/registry.json` and `trial_statuses.jsonl` are authoritative for target hypothesis status.
- Allowed statuses are `CANDIDATE`, `DISCOVERY_PASS`, `CONFIRMATION_PASS`, `FROZEN`, `REJECTED`, `RETIRED`, `QUARANTINED`.
- Only `FROZEN` may be WFA-allowed.
- `liquidity_cost_state_features_v1` is `REJECTED`; do not recommend WFA, Phase 8, full harness, freezing, tuning, or near-neighbor rescue from it.
- Registry status is authoritative: `directional_path_quality_target_v1` is `REJECTED`; its bounded smoke report decision is `STOP_UNDERPOWERED` and is rejection evidence. Do not recommend WFA, Phase 8, full harness, freezing, target tuning, or near-neighbor rescue from it.
- Cost-clearability and market-balanced cost-clearability Phase 9 branches are stopped/no-go unless current primary evidence proves otherwise.
- Rejected/no-go Phase 9 evidence must not justify WFA, Phase 8, full harnesses, threshold tuning, policy tuning, feature/target freezing, or near-neighbor rescue runs.
- Locked Tier 1 baseline run `tier1_locked_baseline_20260616` is no-go negative evidence only.

Model intent to verify:
- intraday futures
- 1-minute bars/execution assumptions
- entry offset 1 bar
- exit offset 16 bars
- 15-minute target horizon
- no session-crossing/overnight target paths
- mean-reversion/fade bias with trend-danger controls

Audit rules:
- Do not edit files.
- Do not stage.
- Do not commit.
- Do not update `PIPELINE.md`.
- Do not regenerate artifacts.
- Do not overwrite data/reports.
- Do not run Phase 1A/1B/1C, Phase 2/3/4 rebuilds, Phase 5 split generation, Phase 6/7 WFA, prediction combine, Phase 8, Phase 9 harnesses, tests, experiment ledger writers, freeze/final-holdout scripts, or hygiene scripts.
- Do not trust existing PASS reports.
- Treat reports/artifacts/tests as stale or wrong until independently reconciled against primary files.
- Prefer current locked/no-go audit reports under `reports/pipeline_audit/` over older smoke/default/partial/Tier 3 reports, but still verify primary artifacts.
- Do not use modified time alone to choose latest evidence; reconcile run name, profile, resolved profile, markets, years, folds, manifest paths, prediction paths, metrics paths, hashes, and report provenance.
- Inspect `reports/experiments/anti_overfit*.json` and `reports/experiments/ledger.jsonl` as guard/negative evidence only unless full-run provenance reconciles.
- Do not tune thresholds, features, targets, models, policies, or costs against failed WFA evidence or rejected Phase 9 smoke evidence.
- Any new feature or target hypothesis must be registered as materially different `CANDIDATE` before discovery and become `FROZEN`/WFA-allowed only after pre-registered gates pass.

Audit only for material failures:
1. Tier 1 config/scope mismatch
2. stale or mismatched artifacts
3. DBN/raw/data integrity bugs
4. session/causal gating bugs
5. label shift/leakage bugs
6. feature leakage
7. train/test/WFA leakage
8. execution/cost/PnL realism bugs
9. misleading Phase 8 metrics/promotion gates
10. feature-set, feature-hypothesis, or target-hypothesis registry violations
11. rejected/no-go Phase 9 branches being reused as valid
12. missing adversarial tests

Minimum checks:
- Parse `configs/alpha_tiered.yaml` and state exact resolved Tier 1 scope.
- Inspect `configs/models.yaml`, `configs/costs.yaml`, and `configs/market_sessions.yaml`.
- Compare Tier 1 scope to present canonical inputs/outputs:
  - `data/dbn/ohlcv_1m`
  - `data/dbn/definition`
  - optional DBN context: `data/dbn/status`, `data/dbn/statistics`, `data/dbn/trades`
  - `data/raw`
  - `data/causally_gated_normalized`
  - `data/labeled`
  - `data/feature_matrices/baseline`
  - `data/predictions`
  - `reports/raw_ingest`
  - `reports/raw_readiness`
  - `reports/causal_base`
  - `reports/labels`
  - `reports/features_baseline`
  - `reports/wfa`
  - `reports/metrics`
  - `reports/phase8`
  - `reports/model_selection`
  - `reports/final_holdout`
  - `artifacts/frozen`
- Treat staged candidate roots such as `data/raw_alignment_candidate_*` and `data/raw_enriched_candidate` as noncanonical if present.
- Treat `data/raw_repaired` as repair overlay evidence only, not canonical Tier 1 input unless report provenance explicitly uses it.
- Treat `artifacts/frozen` as optional generated evidence; do not create/update it or treat old freezes as current Tier 1 truth unless manifest scope and provenance match.
- Inspect current no-go/audit evidence under:
  - `reports/pipeline_audit/tier1_failed_full_wfa_oos_audit.md`
  - `reports/pipeline_audit/tier1_consolidated_no_go_report.{md,json}`
  - `reports/pipeline_audit/tier1_stop_go_report.{md,json}`
  - `reports/pipeline_audit/phase9_cost_clearability_harness_audit_20260617.md`
  - `reports/pipeline_audit/phase9_market_balanced_cost_clearability_harness_audit_20260617.md`
  - `reports/pipeline_audit/liquidity_cost_state_features_v1_smoke_20260617T045008Z.{md,json}`
  - `reports/pipeline_audit/directional_path_quality_target_v1_smoke_20260617T095912Z.{md,json}`
  - `reports/phase8_failure_breakdown/`
  - `reports/model_selection/`
  - `reports/experiments/`
  - `reports/final_holdout/`
  - `artifacts/frozen/`
- Inspect manifests and research state:
  - `manifests/feature_sets/baseline_current.json`
  - `manifests/feature_sets/baseline_current_features.txt`
  - `manifests/feature_hypotheses/registry.json`
  - `manifests/feature_hypotheses/trial_statuses.jsonl`
  - `manifests/target_hypotheses/registry.json`
  - `manifests/target_hypotheses/trial_statuses.jsonl`
  - `data/feature_matrices/baseline/feature_cols.json`
  - `data/feature_matrices/baseline/target_cols.json`
  - `data/feature_matrices/baseline/metadata_cols.json`
  - `data/feature_matrices/baseline/excluded_cols.json`
  - `reports/experiments/anti_overfit*.json`
  - `reports/experiments/ledger.jsonl`
- Verify WFA-allowed features are `FROZEN` and not `REJECTED`, `CANDIDATE`, `DISCOVERY_PASS`, `CONFIRMATION_PASS`, `RETIRED`, or `QUARANTINED`.
- Verify rejected feature and target hypotheses are not recommended for full harness, Phase 8, WFA, freezing, tuning, or rescue variants.
- Verify any proposed new feature or target work starts as a materially different pre-registered `CANDIDATE` hypothesis.
- Inspect Phase 1A-8 scripts, Phase 9 harnesses, validation scripts, and matching tests by reading files only.
- Inspect experiment/ledger, final-holdout, artifact-freeze, WFA-wrapper, and git-hygiene guard scripts plus matching tests by reading files only.
- Independently verify label math:
  - entry = `open[t+1]`
  - exit = `open[t+16]`
  - `target_horizon_bars = 15`
  - target path does not cross `session_segment_id`
  - invalidates `session_segment_cross`, `synthetic_path`, `invalid_ohlcv_path`, `boundary_session_path`, `roll_path`, missing entry/exit, and invalid entry/exit prices
  - separately audit degraded-row handling via causal/trainable data-quality columns
- Verify no target/label/future/path/cost columns enter model X.
- Verify rolling/EMA/RSI/VWAP/features are past-only and session-safe.
- Verify WFA has no train/test/session overlap and purge matches `configs/models.yaml`.
- Verify Phase 6 wrappers delegate to Phase 7 implementation and Phase 7 fits scaler/imputer/model/calibration on train only.
- Verify Phase 8 PnL uses saved OOS predictions and executable returns, not labels as tradable returns.
- Verify costs/turnover/flips/tick values/slippage/commission units from `configs/costs.yaml`.
- Verify promotion and anti-overfit gates cannot pass economically useless net-negative/cost-dominated results.
- Identify stale artifacts separately from code bugs.

Output format only:
# Verdict
Research-valid: Yes/No/Unclear
Trust current performance: Yes/No/Unclear
Single biggest blocker:
# Tier 1 Scope
Config path:
Tier/profile:
Markets:
Years/date range:
Scope mismatches:
# Feature/Target Research State
Frozen feature set:
WFA-allowed features:
Candidate feature hypotheses:
Rejected feature hypotheses:
Candidate target hypotheses:
Rejected target hypotheses:
No-go Phase 9 branches:
Next allowed research action:
# Findings
Return only real issues or unverified critical risks.
Sort by severity, then fix priority.
Max 25 findings.
For each finding use this exact format:
## F<n> - <Severity>: <short title>
What's wrong:
Evidence:
Why it matters:
Fix:
Test to add:
Repair/rebuild command to run later, not now:
Severity:
- FATAL = invalidates current research result
- HIGH = likely materially wrong
- MEDIUM = could distort results
- LOW = hygiene only
Evidence must include paths and line/function/artifact names where possible.
# Required Fix Order
1.
2.
3.
# Commands
PowerShell-compatible only. List commands to run later, not now, if they would overwrite artifacts or generate reports/data.
tests:
targeted audit checks:
manifest/feature registry checks:
target registry checks:
Phase 9 no-go checks:
repair/rebuild raw ingest later:
repair/rebuild causal data later:
repair/rebuild labels later:
repair/rebuild features later:
rerun WFA later:
rerun metrics/gates later:
verify fixes:
# Stop/Go
Should I stop modeling and fix first? Yes/No
Why:
Next exact action:
