# Main Adversarial Audit Prompt

Use in Codex Plan Mode / read-only.

```text
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
  - tests/
  - configs/
  - scripts/
  - docs/audit_prompts/
- Confirm canonical scripts exist:
  - scripts/phase2_causal_base/build_causal_base_data.py
  - scripts/phase3_labels/build_labels.py
  - scripts/phase4_features/build_baseline_features.py
  - scripts/phase5_wfa/build_wfa_splits.py
  - scripts/phase7_wfa/run_wfa.py
  - scripts/phase8_model_selection/evaluate_predictions.py
  - scripts/phase9_research/feature_hypothesis_registry.py
  - scripts/phase9_research/tier1_cost_clearability_event_harness.py
  - scripts/phase9_research/tier1_market_balanced_cost_clearability_harness.py
  - scripts/phase9_research/liquidity_cost_state_harness.py
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
- Current feature-set/research-process state to verify, not assume:
  - manifests/feature_sets/baseline_current.json is the only WFA-allowed frozen feature set.
  - manifests/feature_hypotheses/registry.json and trial_statuses.jsonl track CANDIDATE/DISCOVERY_PASS/FROZEN/REJECTED states.
  - liquidity_cost_state_features_v1 is REJECTED from smoke evidence; do not recommend WFA, Phase 8, or full harness from it.
  - Cost-clearability and market-balanced cost-clearability Phase 9 branches are stopped/no-go unless current reports prove otherwise.
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
- Do not run WFA, Phase 8, prediction-combine scripts, feature/label/causal rebuilds, or experiment ledger writers.
- Do not write or overwrite data, reports, predictions, logs, caches, generated JSON/CSV, or model artifacts.
- Prefer static inspection.
- Run targeted tests only if known not to write pipeline artifacts; otherwise list the command only.
- Do not run full pytest unless explicitly asked.
- You may inspect files and run small read-only verification snippets.
- If a command would overwrite artifacts, list it only.
- Do not trust existing PASS reports.
- Treat reports/artifacts/tests as stale or wrong until independently verified.
- Prefer current locked/no-go audit reports under reports/pipeline_audit/ over older smoke/default/partial/Tier 3 reports, but still verify primary artifacts.
- Do not use modified time alone to choose latest evidence; reconcile run name, profile, resolved profile, markets, years, folds, manifest paths, prediction paths, metrics paths, hashes, and report provenance.
- Do not tune thresholds, features, models, policies, or costs against failed WFA evidence or rejected Phase 9 smoke evidence.
- Any new feature hypothesis must be registered as CANDIDATE before discovery and FROZEN/WFA-allowed only after pre-registered gates pass.
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
10. feature-set registry or hypothesis-status violations
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
  - relevant reports/
- Inspect current audit/no-go evidence under:
  - reports/pipeline_audit/
  - reports/phase8_failure_breakdown/
  - reports/model_selection/
  - reports/experiments/
- Inspect manifests and feature-research state:
  - manifests/feature_sets/baseline_current.json
  - manifests/feature_sets/baseline_current_features.txt
  - manifests/feature_hypotheses/registry.json
  - manifests/feature_hypotheses/trial_statuses.jsonl
  - reports/experiments/anti_overfit*.json
  - reports/experiments/ledger.jsonl
- Verify WFA-allowed features are FROZEN and not REJECTED/CANDIDATE/DISCOVERY_PASS.
- Verify rejected hypotheses are not recommended for full harness, Phase 8, or WFA.
- Verify any proposed new feature work starts as a materially different pre-registered CANDIDATE hypothesis.
- Inspect Phase 2-9 scripts and matching tests.
- Prefer static inspection; do not run artifact-generating pipeline commands.
- Independently verify label math:
  - entry = open[t+1]
  - exit = open[t+16]
  - target_horizon_bars = 15
  - target path does not cross session segment
  - invalidates synthetic_path, invalid_ohlcv_path, boundary_session_path, roll_path, missing entry/exit, and invalid entry/exit prices
  - separately audit degraded-row handling via causal/trainable data-quality columns
- Verify no target/label/future columns enter model X.
- Verify rolling/EMA/RSI/VWAP/features are past-only and session-safe.
- Verify WFA has no train/test/session overlap and purge matches configs/models.yaml.
- Verify scaler/imputer/model fitting/calibration fit train only.
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
# Feature/Research State
Frozen feature set:
WFA-allowed features:
Candidate hypotheses:
Rejected hypotheses:
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
Phase 9 no-go checks:
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
```
