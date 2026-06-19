# Fix Prompt After Confirmed FATAL/HIGH Findings

Use in regular/write-capable Codex mode, not Plan Mode.

MODE: IMPLEMENT CONFIRMED FATAL/HIGH FIXES ONLY.

You are fixing confirmed audit findings in the current intraday futures repo.

Do not run in read-only/Plan Mode.
Do not fix anything unless the finding is confirmed by current repo evidence.
Do not refactor unrelated code.
Do not change modeling assumptions.
Do not tune thresholds, model hyperparameters, costs, policy gates, feature selection, or labels to improve failed evidence.
Do not stage.
Do not commit.
Do not delete, move, rename, or archive files.
Do not regenerate large artifacts.
Do not overwrite data/reports/predictions.
Do not intentionally write generated reports, data, predictions, model artifacts, logs, generated JSON/CSV, parquet, DBN, zst, pickles, or caches.
Do not run WFA, Phase 8 scripts, Phase 9 harnesses, prediction-combine scripts, feature/label/causal rebuilds, Phase 1A/1B/1C scripts, full pytest, or experiment ledger writers unless explicitly requested after the fix is validated.
Do not touch generated artifacts except isolated temporary test fixtures.
Use `tmp_path` or equivalent for any test fixtures.
Run only targeted tests.

FIRST: Verify repo identity.
Confirm current directory, git branch, `git status --short`, and that this repo has:
- `.git/`
- `AGENTS.md`
- `PIPELINE.md`
- `configs/alpha_tiered.yaml`
- `configs/models.yaml`
- `configs/costs.yaml`
- `configs/market_sessions.yaml`
- `scripts/`
- `scripts/dev/audit_prompts/`
- `scripts/phase2_causal_base/build_causal_base_data.py`
- `scripts/phase3_labels/build_labels.py`
- `scripts/phase4_features/build_baseline_features.py`
- `scripts/phase5_wfa/build_wfa_splits.py`
- `scripts/phase6_wfa/run_wfa.py`
- `scripts/phase6_wfa/combine_wfa_predictions.py`
- `scripts/phase7_wfa/run_wfa.py`
- `scripts/phase7_wfa/combine_wfa_predictions.py`
- `scripts/phase8_model_selection/evaluate_predictions.py`
- `scripts/phase9_research/`
- `scripts/validation/`
- `manifests/`
- `manifests/feature_sets/`
- `manifests/feature_hypotheses/`
- `manifests/target_hypotheses/`
- `tests/`

Generated evidence folders are optional evidence targets when present, not repo identity requirements:
- `data/`
- `reports/`
- `reports/pipeline_audit/`
- `reports/phase8_failure_breakdown/`
- `reports/model_selection/`
- `reports/experiments/`

If this is not the intraday futures model repo, stop and say:
Wrong repo selected - switch repo/folder before fixing.

Current state to verify, not assume:
- `configs/alpha_tiered.yaml` resolves `tier_1 -> tier_1_research`.
- Tier 1 research scope is `ES`, `CL`, `ZN`, `6E` for `2023`, `2024`.
- `manifests/feature_sets/baseline_current.json` is the only WFA-allowed frozen feature set and has `feature_count` 122.
- `manifests/feature_hypotheses/registry.json` and `trial_statuses.jsonl` are authoritative for feature hypothesis status.
- `manifests/target_hypotheses/registry.json` and `trial_statuses.jsonl` are authoritative for target hypothesis status.
- `liquidity_cost_state_features_v1` is `REJECTED`.
- `directional_path_quality_target_v1` is `REJECTED`.
- Cost-clearability and market-balanced cost-clearability Phase 9 branches are stopped/no-go unless current primary evidence proves otherwise.
- Rejected/no-go Phase 9 evidence must not justify WFA, Phase 8, full harnesses, threshold tuning, policy tuning, feature/target freezing, or near-neighbor rescue runs.

Confirmed findings to fix:

<PASTE ONLY CONFIRMED FATAL/HIGH FINDINGS HERE>

Rules:
- If no confirmed FATAL/HIGH findings are pasted, stop.
- For each pasted finding, first classify it as Confirmed or Not confirmed using current repo evidence.
- If a finding is ambiguous, stale, unsupported, or not reproducible from current repo evidence, do not patch it; report why.
- Before editing any file with existing modifications, inspect `git diff -- <path>` and avoid overwriting user changes.
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
- After validation, run `git status --short`.
- Keep generated artifacts out of git.
- Do not rebuild full Tier 1 artifacts.
- If a rebuild is needed, list the command only.
- Do not update `PIPELINE.md` unless the pasted finding explicitly requires a documentation update.
- Do not change `manifests/feature_sets/`, `manifests/feature_hypotheses/`, or `manifests/target_hypotheses/` unless the pasted finding explicitly concerns registry/status correctness.
- Do not mark any feature set, feature hypothesis, or target hypothesis `FROZEN` or WFA-allowed from rejected/no-go evidence.
- Do not recommend WFA, Phase 8, feature freezing, target freezing, threshold tuning, policy tuning, or near-neighbor rescue runs from rejected/no-go Phase 9 evidence.

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
List rebuild/WFA/Phase 8/Phase 9 commands only if guards/tests pass and the finding actually requires them.
# Final Verdict
Ready to rebuild Tier 1 artifacts: Yes/No
Why:
Next exact action: