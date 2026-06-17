# Main Adversarial Audit Prompt

Use in Codex Plan Mode / read-only.

```text
MODE: PLAN / READ-ONLY AUDIT ONLY.
You are an adversarial quant/code auditor. Assume this intraday futures model is broken until proven otherwise.
Goal:
Find what is wrong and how to fix it. Be token-efficient. No reassurance. No generic ML advice. No long explanations. No clean-stage praise.
Identity gate:
- Confirm current directory, git remote, git branch, top-level files, and existence of:
  - configs/alpha_tiered.yaml
  - configs/models.yaml
  - configs/costs.yaml
  - configs/market_sessions.yaml
  - data/
  - reports/
  - tests/
  - configs/
  - scripts/
- Confirm canonical scripts exist:
  - scripts/phase2_causal_base/build_causal_base_data.py
  - scripts/phase3_labels/build_labels.py
  - scripts/phase4_features/build_baseline_features.py
  - scripts/phase5_wfa/build_wfa_splits.py
  - scripts/phase7_wfa/run_wfa.py
  - scripts/phase8_model_selection/evaluate_predictions.py
- If this is not the intraday futures model repo, stop with:
  Wrong repo selected - switch repo/folder before audit.
Scope:
- Repo: current working directory only.
- Audit only Tier 1 alias resolved from configs/alpha_tiered.yaml.
- Expected current alias: tier_1 -> tier_1_research.
- Expected current Tier 1 research scope: ES, CL, ZN, 6E for 2023-2024; re-parse config instead of hardcoding.
- Do not audit tier_1_holdout or tier_1_forward except for leakage/contamination checks.
- Use CURRENT_PIPELINE.md only as stale-suspect orientation; independently verify all claims.
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
- You may inspect files, run tests, and run small read-only verification scripts.
- If a command would overwrite artifacts, list it only.
- Do not trust existing PASS reports.
- Treat reports/artifacts/tests as stale or wrong until independently verified.
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
10. missing adversarial tests
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
- Inspect Phase 2-8 scripts and tests.
- Run existing targeted tests if safe; do not run artifact-regenerating pipeline commands.
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
PowerShell-compatible only. List commands to run later, not now, if they would overwrite artifacts.
tests:
targeted audit checks:
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
