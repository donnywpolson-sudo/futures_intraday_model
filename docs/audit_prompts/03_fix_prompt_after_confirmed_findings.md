# Fix Prompt After Confirmed FATAL/HIGH Findings

Use in regular/write-capable Codex mode, not Plan Mode.

```text
MODE: IMPLEMENT CONFIRMED FATAL/HIGH FIXES ONLY.
You are fixing confirmed audit findings in the current intraday futures repo.
Do not run in read-only/Plan Mode.
Do not fix anything unless the finding is confirmed by repo evidence.
Do not refactor unrelated code.
Do not change modeling assumptions.
Do not tune thresholds, model hyperparameters, costs, policy gates, feature selection, or labels to improve failed evidence.
Do not regenerate large artifacts.
Do not overwrite data/reports/predictions.
Do not run WFA, Phase 8, prediction-combine scripts, feature/label/causal rebuilds, full pytest, or experiment ledger writers unless explicitly requested after the fix is validated.
Do not write generated reports, data, predictions, model artifacts, logs, generated JSON/CSV, parquet, DBN, zst, pickles, or caches intentionally.
Do not stage.
Do not commit.
Do not delete, move, rename, or archive files.
Do not touch generated artifacts except isolated temporary test fixtures.
Add tests for every guard you implement.
Run only targeted tests.
FIRST: Verify repo identity.
Confirm current directory, git branch, git status --short, and that this repo has:
- configs/alpha_tiered.yaml
- configs/models.yaml
- configs/costs.yaml
- configs/market_sessions.yaml
- PIPELINE.md
- manifests/
- manifests/feature_sets/
- manifests/feature_hypotheses/
- reports/pipeline_audit/
- reports/phase8_failure_breakdown/
- reports/model_selection/
- reports/experiments/
- scripts/phase2_causal_base/build_causal_base_data.py
- scripts/phase3_labels/build_labels.py
- scripts/phase4_features/build_baseline_features.py
- scripts/phase5_wfa/build_wfa_splits.py
- scripts/phase7_wfa/run_wfa.py
- scripts/phase8_model_selection/evaluate_predictions.py
- scripts/phase9_research/
- tests/
If this is not the intraday futures model repo, stop and say:
Wrong repo selected - switch repo/folder before fixing.
Confirmed findings to fix:
<PASTE ONLY CONFIRMED FATAL/HIGH FINDINGS HERE>
Rules:
- Fix only confirmed bugs.
- If a finding is ambiguous, stale, unsupported, or not reproducible from current repo evidence, do not patch it; report why.
- Before editing any file with existing modifications, inspect git diff for that file and avoid overwriting user changes.
- Keep diffs minimal and local to the confirmed finding.
- Preserve public contracts unless the confirmed finding is that the contract is wrong:
  - CLI args
  - config keys
  - column names
  - file paths
  - output schemas
  - report fields
  - manifests
- For protected quant logic, add a regression test before or with the fix:
  - labels/targets
  - feature computation
  - session normalization
  - causal gating
  - WFA/train/test splits
  - purge/embargo
  - cost/slippage/commission math
  - position policy
  - metrics/reports/manifests
  - timestamp alignment, NaN handling, row counts, and output formats
- Add tests for each fix.
- Run the narrowest relevant tests only.
- Keep generated artifacts out of git.
- Do not rebuild full Tier 1 artifacts.
- If a rebuild is needed, list the command only.
- Do not update PIPELINE.md unless the pasted finding explicitly requires a documentation update.
- Do not change manifests/feature_sets/ or manifests/feature_hypotheses/ unless the pasted finding explicitly concerns registry/status correctness.
- Do not mark any feature set FROZEN or WFA-allowed from rejected/no-go evidence.
- Do not advance rejected Phase 9 branches:
  - liquidity_cost_state_features_v1 is REJECTED from bounded smoke evidence.
  - cost-clearability and market-balanced cost-clearability branches are stopped/no-go unless current evidence proves otherwise.
- Do not recommend WFA, Phase 8, feature freezing, threshold tuning, or near-neighbor rescue runs from rejected/no-go Phase 9 evidence.
Output format:
# Findings Addressed
- finding id:
- status: Fixed/Not fixed
- evidence:
# Files Changed
- path: reason
# Guards/Fixes Added
- item:
# Tests Added
- test path/name:
- what it proves:
# Tests Run
- command:
- result:
# Generated Artifacts
- tracked: Yes/No
- untracked generated artifacts intentionally kept: Yes/No/path
# Git Status
- summary:
# Not Done
List anything intentionally not fixed.
# Manual Commands To Run Later, Not Now
List rebuild/WFA/Phase 8 commands only if guards/tests pass and the finding actually requires rebuilding.
# Final Verdict
Ready to rebuild Tier 1 artifacts: Yes/No
Why:
Next exact action:
```
