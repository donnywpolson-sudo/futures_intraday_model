# Main Adversarial Audit Prompt

Use in Codex Plan Mode / read-only.

MODE: PLAN / READ-ONLY AUDIT ONLY.
You are an adversarial quant/code auditor. Assume this intraday futures model is broken until proven otherwise.

Goal:
Find what is wrong and how to fix it. Be token-efficient. No reassurance. No generic ML advice. No long explanations. No clean-stage praise.

Identity gate:
- Confirm current directory, git remote, git branch, and git status --short --branch.
- Treat pre-existing changes as user-owned.
- Confirm top-level files and existence of:
  - PIPELINE.md
  - configs/alpha_tiered.yaml
  - configs/models.yaml
  - configs/costs.yaml
  - configs/market_sessions.yaml
  - data/
  - data/dbn/ohlcv_1m/
  - data/dbn/definition/
  - data/raw/
  - data/causally_gated_normalized/
  - data/labeled/
  - data/feature_matrices/baseline/
  - data/predictions/
  - reports/
  - reports/raw_ingest/
  - reports/causal_base/
  - reports/labels/
  - reports/features_baseline/
  - reports/wfa/
  - reports/metrics/
  - reports/phase8/
  - reports/pipeline_audit/
  - reports/phase8_failure_breakdown/
  - reports/model_selection/
  - reports/experiments/
  - manifests/
  - manifests/feature_sets/
  - manifests/feature_hypotheses/
  - manifests/target_hypotheses/
  - tests/
  - configs/
  - scripts/
  - docs/audit_prompts/
- Confirm canonical scripts exist:
  - scripts/phase1A_download/download_databento_raw.py
  - scripts/phase1B_convert/convert_databento_raw.py
  - scripts/phase2_causal_base/build_causal_base_data.py
  - scripts/phase3_labels/build_labels.py
  - scripts/phase4_features/build_baseline_features.py
  - scripts/phase5_wfa/build_wfa_splits.py
  - scripts/phase6_wfa/run_wfa.py
  - scripts/phase6_wfa/combine_wfa_predictions.py
  - scripts/phase7_wfa/run_wfa.py
  - scripts/phase7_wfa/combine_wfa_predictions.py
  - scripts/phase8_model_selection/evaluate_predictions.py
  - scripts/phase9_research/feature_hypothesis_registry.py
  - scripts/phase9_research/tier1_cost_clearability_event_harness.py
  - scripts/phase9_research/tier1_market_balanced_cost_clearability_harness.py
  - scripts/phase9_research/liquidity_cost_state_harness.py
  - scripts/phase9_research/directional_path_quality_target_harness.py
- If this is not the intraday futures model repo, stop with:
  Wrong repo selected - switch repo/folder before audit.

Scope:
- Repo: current working directory only.
- Audit only Tier 1 alias resolved from configs/alpha_tiered.yaml.
- Expected current alias: tier_1 -> tier_1_research.
- Expected current Tier 1 research scope: ES, CL, ZN, 6E for 2023-2024; verify from config instead of hardcoding.
- Do not audit tier_1_holdout or tier_1_forward except for leakage/contamination checks.
- Use PIPELINE.md as orientation; independently verify all claims.
- Treat root planning/docs files as orientation only, not pipeline truth:
  - RESOURCES.md
- Ignore _archive/ unless auditing cleanup/provenance explicitly.
- Current feature/target research state to verify, not assume:
  - manifests/feature_sets/baseline_current.json is the only WFA-allowed frozen feature set.
  - baseline_current expected feature_count is 122; verify against manifest and feature list.
  - manifests/feature_hypotheses/registry.json and trial_statuses.jsonl are authoritative for feature hypothesis status.
  - manifests/target_hypotheses/registry.json and trial_statuses.jsonl are authoritative for target hypothesis status.
  - allowed statuses are CANDIDATE, DISCOVERY_PASS, CONFIRMATION_PASS, FROZEN, REJECTED, RETIRED, QUARANTINED.
  - only FROZEN may be WFA-allowed.
  - liquidity_cost_state_features_v1 is REJECTED; do not recommend WFA, Phase 8, full harness, freezing, or tuning from it.
  - directional_path_quality_target_v1 is REJECTED; do not recommend WFA, Phase 8, full harness, freezing, target tuning, or near-neighbor rescue from it.
  - Cost-clearability and market-balanced cost-clearability Phase 9 branches are STOP_BRANCH_PERMANENTLY unless current reports prove otherwise.
  - Locked Tier 1 baseline run tier1_locked_baseline_20260616 is no-go negative evidence only.
- Model intent:
  - intraday futures
  - 1-minute bars/execution assumptions
  - entry offset 1 bar
  - exit offset 16 bars
  - 15-minute target horizon
  - no session-crossing/overnight target paths
  - mean-reversion/fade bias with trend-danger controls

Rules:
- Do not edit files.
- Do not commit.
- Do not regenerate artifacts.
- Do not overwrite data/reports.
- Do not stage.
- Do not update PIPELINE.md.
- Do not run Phase 1A/1B, Phase 2/3/4 rebuilds, Phase 6 WFA, Phase 6 prediction-combine, Phase 8, Phase 9 harnesses, full pytest, or experiment ledger writers.
- Do not run dry-run commands if they write reports, logs, JSON, CSV, parquet, DBN, zst, cache, predictions, or model artifacts.
- Do not write or overwrite data, reports, predictions, logs, caches, generated JSON/CSV, model artifacts, DBN, zst, or parquet.
- Prefer static inspection.
- Run targeted tests only if known not to write pipeline artifacts; otherwise list the command only.
- You may inspect files and run small read-only verification snippets.
- If a command would overwrite or generate artifacts, list it only.
- Do not trust existing PASS reports.
- Treat reports/artifacts/tests as stale or wrong until independently verified.
- Prefer current locked/no-go audit reports under reports/pipeline_audit/ over older smoke/default/partial/Tier 3 reports, but still verify primary artifacts.
- Do not use modified time alone to choose latest evidence; reconcile run name, profile, resolved profile, markets, years, folds, manifest paths, prediction paths, metrics paths, hashes, and report provenance.
- Do not tune thresholds, features, targets, models, policies, or costs against failed WFA evidence or rejected Phase 9 smoke evidence.
- Any new feature or target hypothesis must be registered as CANDIDATE before discovery and FROZEN/WFA-allowed only after pre-registered gates pass.

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
11. rejected/no-go Phase 9 branches being reused as if valid
12. missing adversarial tests

Minimum checks:
- Parse configs/alpha_tiered.yaml and state exact resolved Tier 1 scope.
- Inspect configs/models.yaml, configs/costs.yaml, and configs/market_sessions.yaml.
- Compare Tier 1 scope to:
  - data/dbn/ohlcv_1m
  - data/dbn/definition
  - data/raw
  - data/causally_gated_normalized
  - data/labeled
  - data/feature_matrices/baseline
  - data/predictions
  - reports/raw_ingest
  - reports/causal_base
  - reports/labels
  - reports/features_baseline
  - reports/wfa
  - reports/metrics
  - reports/phase8
- Inspect current no-go/audit evidence under:
  - reports/pipeline_audit/tier1_failed_full_wfa_oos_audit.md
  - reports/pipeline_audit/tier1_consolidated_no_go_report.md
  - reports/pipeline_audit/tier1_stop_go_report.md
  - reports/pipeline_audit/phase9_cost_clearability_harness_audit_20260617.md
  - reports/pipeline_audit/phase9_market_balanced_cost_clearability_harness_audit_20260617.md
  - reports/pipeline_audit/liquidity_cost_state_features_v1_smoke_20260617T045008Z.*
  - reports/pipeline_audit/directional_path_quality_target_v1_smoke_20260617T095912Z.*
  - reports/phase8_failure_breakdown/
  - reports/model_selection/
  - reports/experiments/
- Inspect manifests and research state:
  - manifests/feature_sets/baseline_current.json
  - manifests/feature_sets/baseline_current_features.txt
  - manifests/feature_hypotheses/registry.json
  - manifests/feature_hypotheses/trial_statuses.jsonl
  - manifests/target_hypotheses/registry.json
  - manifests/target_hypotheses/trial_statuses.jsonl
  - data/feature_matrices/baseline/feature_cols.json
  - data/feature_matrices/baseline/target_cols.json
  - data/feature_matrices/baseline/metadata_cols.json
  - data/feature_matrices/baseline/excluded_cols.json
  - reports/experiments/anti_overfit*.json
  - reports/experiments/ledger.jsonl
- Verify WFA-allowed features are FROZEN and not REJECTED/CANDIDATE/DISCOVERY_PASS/CONFIRMATION_PASS/RETIRED/QUARANTINED.
- Verify rejected feature and target hypotheses are not recommended for full harness, Phase 8, WFA, freezing, or tuning.
- Verify any proposed new feature or target work starts as a materially different pre-registered CANDIDATE hypothesis.
- Inspect Phase 1A-8 scripts, Phase 9 harnesses, and matching tests.
- Independently verify label math:
  - entry = open[t+1]
  - exit = open[t+16]
  - target_horizon_bars = 15
  - target path does not cross session_segment_id
  - invalidates session_segment_cross, synthetic_path, invalid_ohlcv_path, boundary_session_path, roll_path, missing entry/exit, and invalid entry/exit prices
  - separately audit degraded-row handling via causal/trainable data-quality columns
- Verify no target/label/future/path/cost columns enter model X.
- Verify rolling/EMA/RSI/VWAP/features are past-only and session-safe.
- Verify WFA has no train/test/session overlap and purge matches configs/models.yaml.
- Verify Phase 6 WFA wrapper and Phase 7 implementation fit scaler/imputer/model/calibration on train only.
- Verify Phase 8 PnL uses saved OOS predictions and executable returns, not labels as tradable returns.
- Verify costs/turnover/flips/tick values/slippage/commission units from configs/costs.yaml.
- Verify promotion gates cannot pass economically useless net-negative/cost-dominated results.
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