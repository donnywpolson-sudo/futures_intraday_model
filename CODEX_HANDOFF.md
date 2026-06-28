# Codex Handoff

## Side-Aware Commit Execution - 2026-06-28

- Updated at local time: 2026-06-28T15:49:59-07:00.
- Scope selected: user explicitly approved staging and committing the verified side-aware commit candidate.
- Staging rule for this run: stage only the files listed in `Side-Aware Commit Candidate - 2026-06-28`.
- Exclusions remain active: `AGENTS.md`, `data/**`, preserved quarantine, smoke report roots, generated reports/data artifacts, logs, caches, model artifacts, and any unlisted live/production/model-promotion artifacts.
- Safety checks before staging:
  - Repo path verified as `C:\Users\donny\Desktop\futures_intraday_model`.
  - `data\_quarantine\actual_cleanup_v1_20260628_130232` exists.
  - `git diff --name-only -- data` returned no paths.
- Commands for this selected scope: stage the candidate files, compare staged files to the candidate list, commit only if the staged scope matches, then report `git status --short` and `git log -1 --oneline` in the final response.
- This commit execution still does not claim production/live readiness, model promotion, cleanup/archive approval, or approval of historical model results.

### Exact Next Recommended Step

```text
None after the verified side-aware commit is created and remaining worktree state is reported.
If staging reveals a scope mismatch, stop before committing and resolve the mismatch only.
```

## Side-Aware Commit Candidate - 2026-06-28

- Updated at local time: 2026-06-28T13:20:55-07:00.
- Scope executed: prepared a commit candidate for the accepted side-aware current work without staging or committing.
- Final pre-commit verification:
  - `git diff --check -- configs scripts tests CODEX_HANDOFF.md` -> passed; output contained CRLF conversion warnings only.
  - `python -m scripts.validation.model_registry --config configs\models.yaml` -> passed; printed config hash `318ab6f793f17dfbb981886f601e91b68eefc1d5bb89c02e67462f6107bdc483`.
  - `python -B -m pytest -p no:cacheprovider tests\phase8_model_selection tests\validation\test_model_registry.py tests\phase3_labels\test_build_labels.py::test_fade_and_30m_regime_labels tests\phase3_labels\test_build_labels.py::test_side_aware_30m_trend_labels_require_valid_30m_path tests\phase4_features\test_build_baseline_features.py::test_registry_excludes_targets_audit_source_and_forbidden_columns tests\phase7_wfa\test_run_wfa.py::test_classification_predictions_route_target_specific_probability_columns tests\live\test_live_shadow_runner.py tests\live\test_export_live_shadow_bundle.py` -> `123 passed, 58 warnings`.
  - Pytest warnings were `PerformanceWarning` messages from `scripts\phase4_features\build_baseline_features.py` during live-shadow feature construction; no test failed.
- Candidate files to include in a side-aware commit:
  - `CODEX_HANDOFF.md`
  - `configs\alpha_tiered.yaml`
  - `configs\models.yaml`
  - `configs\tier_3.yaml`
  - `scripts\phase3_labels\build_labels.py`
  - `scripts\phase4_features\build_baseline_features.py`
  - `scripts\phase7_wfa\run_wfa.py`
  - `scripts\phase8_model_selection\audit_direction_edge_calibration.py`
  - `scripts\phase8_model_selection\audit_event_level_edge_feasibility.py`
  - `scripts\phase8_model_selection\audit_label_feature_sanity.py`
  - `scripts\phase8_model_selection\audit_mr_tail_risk.py`
  - `scripts\phase8_model_selection\audit_policy_failure.py`
  - `scripts\phase8_model_selection\audit_policy_run_level_overlap.py`
  - `scripts\phase8_model_selection\audit_policy_signal_alignment.py`
  - `scripts\phase8_model_selection\audit_signal_trade_quality.py`
  - `scripts\phase8_model_selection\audit_threshold_and_target_sanity.py`
  - `scripts\phase8_model_selection\audit_trade_failure_drilldown.py`
  - `scripts\phase8_model_selection\evaluate_predictions.py`
  - `scripts\validation\feature_leakage_guard.py`
  - `scripts\validation\model_registry.py`
  - `tests\phase3_labels\test_build_labels.py`
  - `tests\phase4_features\test_build_baseline_features.py`
  - `tests\phase7_wfa\test_run_wfa.py`
  - `tests\phase8_model_selection\side_aware_fixture.py`
  - `tests\phase8_model_selection\test_audit_direction_edge_calibration.py`
  - `tests\phase8_model_selection\test_audit_event_level_edge_feasibility.py`
  - `tests\phase8_model_selection\test_audit_label_feature_sanity.py`
  - `tests\phase8_model_selection\test_audit_mr_tail_risk.py`
  - `tests\phase8_model_selection\test_audit_policy_failure.py`
  - `tests\phase8_model_selection\test_audit_policy_run_level_overlap.py`
  - `tests\phase8_model_selection\test_audit_policy_signal_alignment.py`
  - `tests\phase8_model_selection\test_audit_signal_trade_quality.py`
  - `tests\phase8_model_selection\test_audit_threshold_and_target_sanity.py`
  - `tests\phase8_model_selection\test_audit_trade_failure_drilldown.py`
  - `tests\phase8_model_selection\test_evaluate_predictions.py`
  - `tests\validation\test_model_registry.py`
- Files and paths to exclude from this side-aware commit candidate:
  - `AGENTS.md`
  - `data/**`, including `data\_quarantine\actual_cleanup_v1_20260628_130232`
  - `reports\side_aware_trend_smoke_v1`
  - `reports\side_aware_trend_smoke_v2_tier1_core`
  - `reports\side_aware_trend_smoke_v3_tier1_core`
  - all generated parquet/dbn/zst/csv/json reports, logs, model artifacts, and cache/build outputs
  - any live/production/model-promotion artifacts not explicitly listed in the candidate include list
- Safety:
  - No staging or commit was performed.
  - No data files, quarantine folders, report evidence roots, cleanup/archive actions, or model artifact writers were touched.
  - This candidate still does not claim production/live readiness, model promotion, cleanup/archive approval, or approval of historical model results.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: stage and commit the verified side-aware commit candidate, only if the user explicitly wants a commit.
Rules:
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Preserve data/_quarantine/actual_cleanup_v1_20260628_130232 for rollback.
- Do not delete or overwrite reports/side_aware_trend_smoke_v1, reports/side_aware_trend_smoke_v2_tier1_core, or reports/side_aware_trend_smoke_v3_tier1_core.
- Do not include AGENTS.md.
- Do not include generated reports, parquet/dbn/zst files, logs, caches, model artifacts, or data outputs.
- Do not claim production/live readiness, model promotion, cleanup/archive approval, or approval of historical model results.
Task:
- Stage only the files listed under "Candidate files to include in a side-aware commit" in CODEX_HANDOFF.md.
- Commit them with a message that describes the side-aware trend label/prediction/policy/live-shadow contract.
- After committing, run git status --short and report any remaining uncommitted or excluded files.
Stop when:
- The verified side-aware commit is created and remaining worktree state is reported, or staging reveals a scope mismatch that must be resolved before committing.
```

## Final Side-Aware Diff Disposition - 2026-06-28

- Updated at local time: 2026-06-28T13:22:00-07:00.
- Scope executed: reviewed current dirty tracked side-aware source/config/test diffs, the successful report-scoped v3 smoke evidence, and live-shadow side-aware gating verification.
- Final disposition: accept the preserved side-aware source/config/test diffs as intentional current work in the working tree.
- Disposition applies to:
  - `configs\alpha_tiered.yaml`
  - `configs\models.yaml`
  - `configs\tier_3.yaml`
  - `scripts\phase3_labels\build_labels.py`
  - `scripts\phase4_features\build_baseline_features.py`
  - `scripts\phase7_wfa\run_wfa.py`
  - `scripts\phase8_model_selection\audit_direction_edge_calibration.py`
  - `scripts\phase8_model_selection\audit_event_level_edge_feasibility.py`
  - `scripts\phase8_model_selection\audit_label_feature_sanity.py`
  - `scripts\phase8_model_selection\audit_mr_tail_risk.py`
  - `scripts\phase8_model_selection\audit_policy_failure.py`
  - `scripts\phase8_model_selection\audit_policy_run_level_overlap.py`
  - `scripts\phase8_model_selection\audit_policy_signal_alignment.py`
  - `scripts\phase8_model_selection\audit_signal_trade_quality.py`
  - `scripts\phase8_model_selection\audit_threshold_and_target_sanity.py`
  - `scripts\phase8_model_selection\audit_trade_failure_drilldown.py`
  - `scripts\phase8_model_selection\evaluate_predictions.py`
  - `scripts\validation\feature_leakage_guard.py`
  - `scripts\validation\model_registry.py`
  - `tests\phase3_labels\test_build_labels.py`
  - `tests\phase4_features\test_build_baseline_features.py`
  - `tests\phase7_wfa\test_run_wfa.py`
  - `tests\phase8_model_selection\test_audit_direction_edge_calibration.py`
  - `tests\phase8_model_selection\test_audit_event_level_edge_feasibility.py`
  - `tests\phase8_model_selection\test_audit_label_feature_sanity.py`
  - `tests\phase8_model_selection\test_audit_mr_tail_risk.py`
  - `tests\phase8_model_selection\test_audit_policy_failure.py`
  - `tests\phase8_model_selection\test_audit_policy_run_level_overlap.py`
  - `tests\phase8_model_selection\test_audit_policy_signal_alignment.py`
  - `tests\phase8_model_selection\test_audit_signal_trade_quality.py`
  - `tests\phase8_model_selection\test_audit_threshold_and_target_sanity.py`
  - `tests\phase8_model_selection\test_audit_trade_failure_drilldown.py`
  - `tests\phase8_model_selection\test_evaluate_predictions.py`
  - `tests\validation\test_model_registry.py`
  - `tests\phase8_model_selection\side_aware_fixture.py`
- Evidence supporting acceptance:
  - Focused side-aware implementation validation previously passed: Phase 8 tests, targeted Phase 3/4/7/model-registry tests, model registry validation, grep scans, and `git diff --check`.
  - Report-scoped v3 smoke passed through fresh Phase 3 labels, Phase 4 features/manifest gate, Phase 5 splits, bounded Phase 6 predictions, prediction schema, and Phase 8 policy metrics under `reports\side_aware_trend_smoke_v3_tier1_core`.
  - Live-shadow gating verification passed with side-aware adverse probabilities and aggregate-only trend danger failing closed: `python -m pytest tests\live\test_live_shadow_runner.py tests\live\test_export_live_shadow_bundle.py` -> `18 passed`.
- Explicit limits:
  - Acceptance means these diffs are intentional current source/config/test behavior in the working tree.
  - Acceptance does not stage, commit, promote, or claim production/live readiness.
  - Acceptance does not approve historical model results, archive decisions, cleanup decisions, closeout claims, or model promotion.
  - `AGENTS.md` is not included in this side-aware disposition and remains outside this decision.
- Minimum validation gate before any pipeline, model result, archive decision, cleanup decision, closeout claim, or promotion claim relies on the side-aware implementation:
  1. Re-run static/source checks on the exact candidate worktree: `git diff --check -- configs scripts tests CODEX_HANDOFF.md` and `python -m scripts.validation.model_registry --config configs\models.yaml`.
  2. Re-run focused tests covering side-aware labels, Phase 4 target registry/leakage guard, Phase 7 target-specific prediction routing, Phase 8 policy/audit behavior, model registry, and live-shadow bundle/gating.
  3. Re-run or preserve a fresh report-scoped smoke equivalent to `reports\side_aware_trend_smoke_v3_tier1_core` from Phase 3 through Phase 8, using only report-scoped fresh labels/features/predictions/metrics and no historical prediction artifacts.
  4. For any claim beyond structural smoke, run the intended pipeline scope from fresh current inputs and verify its own manifests, row counts, prediction schema, warnings/failures, cost assumptions, purge/embargo, and promotion/closeout gates. The v3 smoke is not sufficient for those broader claims by itself.
  5. Verify `git diff --name-only -- data` remains empty unless a later user-approved task explicitly allows data mutation.
- Safety:
  - No data files, quarantine folders, report evidence roots, staging, or commits were changed in this disposition step.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: prepare a user-approved commit candidate for the accepted side-aware current work.
Rules:
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Preserve data/_quarantine/actual_cleanup_v1_20260628_130232 for rollback.
- Do not delete or overwrite reports/side_aware_trend_smoke_v1, reports/side_aware_trend_smoke_v2_tier1_core, or reports/side_aware_trend_smoke_v3_tier1_core.
- Do not stage or commit unless explicitly requested in that prompt.
- Do not include AGENTS.md in the side-aware commit scope unless the user explicitly says to include it.
- Do not claim production/live readiness, model promotion, cleanup/archive approval, or approval of historical model results.
Task:
- Review the accepted side-aware source/config/test/handoff diff scope.
- Run final pre-commit verification only: git diff --check -- configs scripts tests CODEX_HANDOFF.md, python -m scripts.validation.model_registry --config configs\models.yaml, and the focused side-aware/live-shadow pytest set documented in CODEX_HANDOFF.md.
- Report the exact files that would be included in a side-aware commit and any files that must remain excluded.
Stop when:
- The commit candidate scope and final verification status are documented, with no staging or commit performed.
```

## Live-Shadow Side-Aware Trend Gating Decision - 2026-06-28

- Updated at local time: 2026-06-28T13:14:14-07:00.
- Scope executed: inspected `scripts\live_shadow_runner.py`, `tests\live\test_live_shadow_runner.py`, and `tests\live\test_export_live_shadow_bundle.py` only.
- Decision: live-shadow uses side-aware adverse trend probabilities and fails closed when only legacy aggregate trend danger is available.
- Verified current live-shadow contract:
  - Required bundle targets are `target_ret_15m`, `target_sign_with_deadzone`, `target_fade_success_15m`, `target_trend_adverse_long_30m`, and `target_trend_adverse_short_30m`.
  - Legacy aggregate `target_trend_danger_30m` is not a required live-shadow target.
  - Model inference emits `p_trend_adverse_long_30m` and `p_trend_adverse_short_30m`.
  - Long fade gating selects only `p_trend_adverse_long_30m`.
  - Short fade gating selects only `p_trend_adverse_short_30m`.
  - Missing selected side-aware adverse probability adds `missing_side_aware_trend_adverse_probability` and `trend_danger_block`.
  - Legacy aggregate `p_trend_danger` is not included in the live-shadow signal payload and does not override side-aware adverse probabilities.
- Focused validation:
  - `python -m pytest tests\live\test_live_shadow_runner.py tests\live\test_export_live_shadow_bundle.py` -> `18 passed, 58 warnings`.
  - Warnings were `PerformanceWarning` messages from `scripts\phase4_features\build_baseline_features.py` feature construction during focused live tests; no test failed.
- Files changed in this scope:
  - No source or test edits were required. `CODEX_HANDOFF.md` was updated to record the verified disposition.
- Safety:
  - No WFA/modeling, Phase 8 over repo predictions, prediction generation, label generation over repo data, or model artifact writers were run.
  - No `data/**` mutation, cleanup, archive, quarantine deletion, report evidence deletion/overwrite, staging, or commit was performed.
- Current evidence limits:
  - This verifies the live-shadow code path is side-aware/fail-closed at the focused unit/export-test level.
  - This still does not claim production/live readiness, model promotion, or approval of historical model results.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: decide final disposition of the preserved side-aware implementation diffs after successful report-scoped smoke and live-shadow gating verification.
Rules:
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Preserve data/_quarantine/actual_cleanup_v1_20260628_130232 for rollback.
- Do not delete or overwrite reports/side_aware_trend_smoke_v1, reports/side_aware_trend_smoke_v2_tier1_core, or reports/side_aware_trend_smoke_v3_tier1_core.
- Do not stage or commit unless explicitly requested.
- Do not claim production/live readiness, model promotion, cleanup/archive approval, or approval of historical model results.
Task:
- Review CODEX_HANDOFF.md sections for side-aware implementation, successful v3 smoke evidence, and live-shadow gating verification.
- Decide whether the preserved side-aware source/config/test diffs should remain future unapproved work, be accepted as intentional current work, or be prepared for a user-approved commit.
- If accepting as current work, define the minimum remaining validation needed before any pipeline, model result, archive decision, cleanup decision, closeout claim, or promotion claim relies on it.
Stop when:
- The preserved side-aware diffs have an explicit final disposition and any remaining validation gate is documented.
```

## Report-Scoped Side-Aware Smoke Success - 2026-06-28

- Updated at local time: 2026-06-28T10:41:38-07:00.
- Scope executed: completed a corrected report-scoped side-aware smoke under `reports\side_aware_trend_smoke_v3_tier1_core`.
- Why v3 was required:
  - The planned v2 command created `reports\side_aware_trend_smoke_v2_tier1_core` but stopped at Phase 3.
  - Phase 3 rejected the tier-1 causal manifest because the command omitted the approved `--accepted-readiness-exceptions` file required for the documented 6E 2023/2024 synthetic-threshold warnings.
  - No later phases were run under v2.
  - v1 and v2 are preserved as stopped smoke evidence roots and were not deleted or overwritten.
- Inputs used read-only:
  - `data\causal_base_candidates\tier1_rebuild_v1`
  - `reports\data_audit\causal_base_repair_plan\tier1_candidate_v1\causal_base_manifest.json`
  - `reports\data_audit\causal_base_repair_plan\tier1_candidate_v1\accepted_readiness_exceptions.json`
  - `reports\data_audit\wfa_research\tier1_rebuild_v1\preflight\data_audit_universe_tier1_rebuild_v1.json`
- Generated v3 evidence:
  - Phase 3 labels: `reports\side_aware_trend_smoke_v3_tier1_core\phase3\label_manifest.json`
  - Phase 4 features: `reports\side_aware_trend_smoke_v3_tier1_core\phase4\baseline_feature_manifest.json`
  - Phase 5 splits: `reports\side_aware_trend_smoke_v3_tier1_core\phase5\split_plan.json`
  - Phase 6 predictions: `reports\side_aware_trend_smoke_v3_tier1_core\smoke_data\predictions\side_aware_trend_smoke_v3_tier1_core\oos_predictions.parquet`
  - Phase 6 manifest: `reports\side_aware_trend_smoke_v3_tier1_core\phase6\side_aware_trend_smoke_v3_tier1_core_predictions_manifest.json`
  - Phase 8 decision: `reports\side_aware_trend_smoke_v3_tier1_core\phase8\phase8\alpha_promotion_decision.json`
- Successful checks:
  - Preflight verified correct repo path, preserved rollback quarantine, preserved v1/v2 evidence roots, absent v3 root, no tracked `data/**` diff, PASS tier-1 causal manifest, eight causal input parquet files, and two approved report-only 6E readiness exceptions.
  - Phase 3 generated labels for all 8 tier-1 market-years with zero failures.
  - Label schema check found all four side-aware target columns in all 8 fresh label parquet files.
  - Phase 4 generated all 8 feature matrices with `status=WARN`, `failure_count=0`, `warning_count=8`.
  - Direct Phase 5-style manifest gate check passed with 8 accepted same-market intermarket warnings.
  - Smoke-only feature-set manifest was written under `reports\side_aware_trend_smoke_v3_tier1_core\preflight\side_aware_trend_smoke_v3_feature_set.json` and validated with 122 features.
  - Phase 5 produced a PASS WFA split plan: 48 folds, 4 markets, `feature_manifest_gate.status=PASS`, resolved purge bars `31`, failures `0`.
  - Phase 6 command output ended with `PASS WFA baseline: predictions=231168 models=8 folds=1 failures=0`.
  - Phase 6 shell wrapper returned a timeout code after the PASS line, so the artifacts were verified directly: prediction manifest exists with `failure_count=0`, `prediction_count=231168`, output hash present, and no failures.
  - Prediction parquet schema check passed: 231168 rows, all four side-aware probability columns present, and all four side-aware target rows present.
  - Phase 8 completed: `PASS model diagnostics: rows=28896 trades=50 net_dollars=-237.5 alpha_ready=False failures=0`.
  - Phase 8 decision check passed: `failure_count=0`, `model_promotion_allowed=false`.
  - Final safety check: `git diff --name-only -- data` returned no paths.
- Current evidence limits:
  - This smoke proves the future side-aware labels, Phase 4 manifest contract, Phase 5 gate, bounded Phase 6 WFA prediction generation, prediction manifest, prediction schema, and Phase 8 policy metrics can run end-to-end from fresh report-scoped artifacts.
  - This remains structural smoke evidence only. It does not approve historical model results, archive decisions, cleanup decisions, closeout claims, live execution, production readiness, or model promotion.
  - `scripts\live_shadow_runner.py` remains out of scope and still requires a separate side-aware gating decision before any live-shadow readiness claim.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: decide whether to update or disable live-shadow trend gating after side-aware trend labels and the successful report-scoped side-aware smoke.
Rules:
- Do not run WFA/modeling, Phase 8 over repo predictions, prediction generation, label generation over repo data, or model artifact writers.
- Do not mutate data/**, delete quarantine, run cleanup, delete/overwrite reports/side_aware_trend_smoke_v1, reports/side_aware_trend_smoke_v2_tier1_core, or reports/side_aware_trend_smoke_v3_tier1_core, or claim production/live readiness.
- Do not stage or commit unless explicitly requested.
- Keep aggregate p_trend_danger as legacy/context only; do not use it as a side-aware risk control.
Task:
- Inspect scripts/live_shadow_runner.py and its focused tests only.
- Decide whether live-shadow should fail closed until side-aware estimators are available, or be updated to require target_trend_adverse_long_30m and target_trend_adverse_short_30m model outputs.
- If a safe small edit exists, implement only that live-shadow gating contract and focused tests.
- Otherwise document why live-shadow remains blocked for side-aware trend gating.
Stop when:
- live-shadow either blocks aggregate p_trend_danger gating explicitly or uses side-aware adverse trend probabilities with tests.
```

## Report-Scoped Side-Aware Smoke Attempt - 2026-06-28

- Updated at UTC: 2026-06-28T16:37:43Z.
- Scope executed: attempted the approved report-scoped side-aware smoke under `reports\side_aware_trend_smoke_v1`, reusing only `reports\data_path_audit_20260628T152225Z\phase2\causal_base_manifest.json` and `reports\data_path_audit_20260628T152225Z\smoke_data\causally_gated_normalized\ES\2024.parquet` as upstream causal input.
- Stop status: stopped at Phase 5 as required by the smoke plan's first-failure stop condition. Phase 6 WFA prediction generation and Phase 8 policy evaluation were not run.
- Files/artifacts generated under `reports\side_aware_trend_smoke_v1`:
  - `phase3\label_manifest.json`
  - `phase3\label_report.json`
  - `phase4\baseline_feature_manifest.json`
  - `phase4\baseline_feature_report.json`
  - `phase4\feature_correlation_report.csv`
  - `phase4\feature_registry.json`
  - `smoke_data\labeled\ES\2024.parquet`
  - `smoke_data\feature_matrices\baseline\ES\2024.parquet`
  - `smoke_data\feature_matrices\baseline\feature_cols.json`
  - `smoke_data\feature_matrices\baseline\target_cols.json`
  - `smoke_data\feature_matrices\baseline\metadata_cols.json`
  - `smoke_data\feature_matrices\baseline\excluded_cols.json`
- Successful checks:
  - Preflight verified correct repo path, preserved rollback quarantine exists, no tracked `data/**` diff existed before the smoke, the report root did not already exist, and the upstream Phase 2 causal manifest/input parquet existed.
  - Phase 3 label generation completed: `PASS ES 2024: rows=355065 valid=337861 invalid=17204 warnings=0 failures=0`.
  - Label schema check passed for `target_trend_adverse_long_30m`, `target_trend_favorable_long_30m`, `target_trend_adverse_short_30m`, and `target_trend_favorable_short_30m`.
  - Phase 4 feature generation completed with zero failures: `WARN ES 2024: rows=355065 features=122 input_valid=349549 training_valid=337861 warnings=1 failures=0`.
  - Phase 4 manifest check passed for the four side-aware target columns and `failure_count == 0`; manifest status is `WARN` with `warning_count == 1`.
  - Post-failure safety check: `git diff --name-only -- data` returned no paths.
- Phase 5 failed command:
  - `python -m scripts.phase5_wfa.build_wfa_splits --profile tier_0 --input-root reports\side_aware_trend_smoke_v1\smoke_data\feature_matrices\baseline --reports-root reports\side_aware_trend_smoke_v1\phase5 --profile-config configs\alpha_tiered.yaml --models-config configs\models.yaml`
- Failure evidence:
  - CLI default for `--feature-manifest` is `auto`, so omitting the flag still triggers Phase 5's upstream feature manifest gate.
  - The auto gate failed and reported: `feature_manifest_gate failed`.
  - Direct check of the fresh manifest showed the fresh output hash exists, but the manifest gate still fails because the single-market tier-0 Phase 4 output warning is not in Phase 5's accepted warning set:
    - `features fully unavailable: feature_rel_ret_vs_ES_15,feature_rel_ret_vs_ZN_15,feature_rel_ret_vs_CL_15,feature_rel_ret_vs_6E_15,feature_corr_vs_ES_60,feature_corr_vs_ZN_60,feature_corr_vs_CL_60,feature_corr_vs_6E_60,feature_es_zn_divergence_30,feature_cl_es_divergence_30,feature_tier1_direction_agreement_15,feature_tier1_return_dispersion_15,feature_tier1_risk_on_score_30,feature_es_zn_risk_regime_30,feature_cl_es_macro_divergence_30`
  - The prior upstream causal fixture contains only `ES\2024.parquet`, so the planned tier-0/single-market smoke is not compatible with the current Phase 5 manifest warning policy.
- Current evidence limits:
  - Fresh side-aware labels and Phase 4 target manifest compatibility are smoke-verified only through Phase 4.
  - No fresh WFA predictions, prediction manifest, Phase 8 metrics, Phase 8 promotion decision, model artifact, archive decision, cleanup decision, closeout claim, promotion claim, or live-readiness claim was produced or validated by this smoke.
  - `reports\side_aware_trend_smoke_v1` now exists and should be treated as a failed/stopped smoke evidence root, not reused for a fresh rerun unless a future task explicitly approves overwriting or deleting report artifacts.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: redesign the report-scoped side-aware smoke so Phase 5's feature_manifest_gate can pass without weakening validation.
Rules:
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Preserve data/_quarantine/actual_cleanup_v1_20260628_130232 for rollback.
- Do not delete or overwrite reports/side_aware_trend_smoke_v1; treat it as failed/stopped smoke evidence.
- Do not stage or commit unless explicitly asked.
- Do not treat historical model results, archive decisions, cleanup decisions, closeout claims, promotion claims, or reports/side_aware_trend_smoke_v1 as side-aware-approved.
Task:
- Inspect Phase 5 feature_manifest_gate requirements and Phase 4 warning semantics.
- Choose a corrected report-scoped smoke design that makes the upstream Phase 4 manifest gate pass, preferably by generating a fresh multi-market report-scoped input/feature fixture rather than weakening the gate.
- Produce exact commands, output roots under a new reports/** root, success criteria, and stop conditions for rerunning Phase 3 through Phase 8.
- Do not run Phase 6 or Phase 8 until Phase 5 succeeds under the corrected design.
Stop when:
- The corrected smoke plan is decision-complete, or it is proven that a source/config/test change is required before the smoke can validly run.
```

## Latest Side-Aware Trend Label Contract Implementation

This section supersedes the older "Dirty Worktree Reconciliation" section only for side-aware implementation status. Older cleanup, quarantine, checkpoint, and data-path caveats remain in force.

- Updated at UTC: 2026-06-28T16:18:28Z.
- Purpose: implement and validate the side-aware adverse/favorable 30m trend label contract without generating repo labels, predictions, WFA outputs, model artifacts, cleanup, archive actions, or live-readiness claims.
- Current status: implementation and focused validation complete. No staging or commit was performed.
- Label schema added:
  - `target_trend_adverse_long_30m`
  - `target_trend_favorable_long_30m`
  - `target_trend_adverse_short_30m`
  - `target_trend_favorable_short_30m`
- Implemented semantics:
  - Entry anchor remains the next 1m open.
  - 30m trend labels require the existing valid 30m path through `REGIME_OFFSET_BARS = 31`.
  - Long adverse uses future low moving down by the adverse threshold.
  - Long favorable uses future high moving up by the favorable threshold.
  - Short adverse uses future high moving up by the adverse threshold.
  - Short favorable uses future low moving down by the favorable threshold.
  - Initial favorable threshold equals the adverse threshold.
  - Legacy aggregate `target_trend_danger_30m` is preserved for context/backward compatibility.
- Contract updates completed:
  - Feature leakage guard and Phase 4 required label contract include the four new target columns.
  - `configs\models.yaml` adds `side_aware_trend_target`, four required linear classifier controls, four side-aware prediction columns, side-aware policy inputs, and `side_aware_trend_blocks_fade_trades: true`.
  - `p_trend_danger_blocks_fade_trades` remains `false`; model registry validation fails if aggregate `p_trend_danger` is re-enabled as a trend blocker.
  - Purge policy now resolves to `entry_lag_bars + max(target_horizon_bars, trend_horizon_bars) = 31`, and `configs\alpha_tiered.yaml` / `configs\tier_3.yaml` defaults were updated to 31.
  - Phase 7 prediction routing maps each side-aware target to its own probability column.
  - Phase 8 policy evaluation and audit diagnostics require side-aware trend target rows and block using side-matched `trend_adverse_probability`, not aggregate `p_trend_danger`.
- Validation run:
  - `python -B -m pytest -p no:cacheprovider tests\phase8_model_selection` -> `87 passed`
  - `python -B -m pytest -p no:cacheprovider tests\validation\test_model_registry.py tests\phase3_labels\test_build_labels.py::test_fade_and_30m_regime_labels tests\phase3_labels\test_build_labels.py::test_side_aware_30m_trend_labels_require_valid_30m_path tests\phase4_features\test_build_baseline_features.py::test_registry_excludes_targets_audit_source_and_forbidden_columns tests\phase7_wfa\test_run_wfa.py::test_classification_predictions_route_target_specific_probability_columns` -> `18 passed`
  - `python -B scripts\validation\model_registry.py` -> exited 0 and printed config hash `318ab6f793f17dfbb981886f601e91b68eefc1d5bb89c02e67462f6107bdc483`
  - Required post-change `rg` scan over `scripts tests configs docs` completed.
  - `git diff --check` passed with CRLF warnings only.
  - `git diff --name-status` and `git status --short` show tracked source/config/test/handoff edits plus untracked `tests\phase8_model_selection\side_aware_fixture.py`; no tracked `data/**` or `reports/**` changes.
- Remaining blocker:
  - `scripts\live_shadow_runner.py` still uses legacy aggregate `target_trend_danger_30m` / `p_trend_danger` for live-shadow trend gating. It was intentionally left unchanged because this run scoped research schema/contracts and explicitly did not claim production/live readiness.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: decide whether to update or disable live-shadow trend gating after side-aware trend labels.
Rules:
- Do not run WFA/modeling, Phase 8 over repo predictions, prediction generation, label generation over repo data, or model artifact writers.
- Do not mutate data/**, delete quarantine, run cleanup, or claim production/live readiness.
- Do not stage or commit unless explicitly requested.
- Keep aggregate p_trend_danger as legacy/context only; do not use it as a side-aware risk control.
Task:
- Inspect scripts/live_shadow_runner.py and its focused tests only.
- Decide whether live-shadow should fail closed until side-aware estimators are available, or be updated to require target_trend_adverse_long_30m and target_trend_adverse_short_30m model outputs.
- If a safe small edit exists, implement only that live-shadow gating contract and focused tests.
- Otherwise document why live-shadow remains blocked for side-aware trend gating.
Stop when:
- live-shadow either blocks aggregate p_trend_danger gating explicitly or uses side-aware adverse trend probabilities with tests.
```

## Dirty Worktree Reconciliation - 2026-06-28

This section is the current authoritative reconciliation for the dirty worktree. It supersedes older handoff sections where they conflict.

- Current repo path verified: `C:\Users\donny\Desktop\futures_intraday_model`.
- Current `HEAD` verified: `99b028a Disable aggregate trend-danger hard blocker`.
- External checkpoint reviewed: `C:\Users\donny\Desktop\You_are_here_updated_current_FINAL_20260628.txt`.
- The checkpoint is useful but not fully current: cleanup/quarantine and Phase 8 closeout claims are repo-supported, but its `Git worktree: CLEAN` claim is false in the current workspace.

### Verified checkpoint facts

- Cleanup/quarantine evidence exists:
  - `reports\data_audit\final\actual_cleanup_v1\actual_cleanup_summary.md`
  - `reports\data_audit\final\actual_cleanup_v1\actual_cleanup_safety_gate.json`
  - `reports\data_audit\final\actual_cleanup_v1\actual_cleanup_candidate_counts_before_after.csv`
  - `reports\data_audit\final\post_cleanup_validation_v1\post_cleanup_validation_summary.md`
  - `reports\data_audit\final\post_cleanup_validation_v1\post_cleanup_validation_safety_gate.json`
- Quarantine root exists: `data\_quarantine\actual_cleanup_v1_20260628_130232`.
- Old candidate paths are absent at their original locations:
  - `data\causally_gated_normalized`
  - `data\raw\_repair_candidates`
  - `data\feature_matrices\baseline`
  - `data\predictions`
  - `data\dbn_sr_parent_candidate`
- Cleanup was reversible quarantine/move only: deletion executed `false`, counts matched `true`, bytes matched `true`, protected path overlap found `false`, rollback available `true`.
- Phase 8 closeout evidence exists and says the current policy line is `stopped_non_viable`.
- `reports\data_audit\wfa_research\tier1_rebuild_v1\metrics_artifacts\diagnostics\current_phase8_policy_line_closeout_v1\closeout_safety_gate.json` verifies: `config_changed=false`, `scripts_changed=false`, `tests_changed=false`, `predictions_generated=false`, `wfa_modeling_rerun=false`, `data_modified=false`, and `quarantine_deleted=false`.

### Dirty worktree disposition

- Expected checkpoint/handoff work:
  - `CODEX_HANDOFF.md`: expected documentation drift from the data-path audit, supplemental checkpoint review, reconciliation note, and this disposition update.
- Disposition selected for source/config/test drift: preserve as unapproved future side-aware trend implementation work. Do not treat these diffs as current approved pipeline behavior, current closeout work, model-result evidence, or archive-decision evidence.
- Preserved tracked future-work diffs:
  - `configs\alpha_tiered.yaml`
  - `configs\models.yaml`
  - `configs\tier_3.yaml`
  - `scripts\phase3_labels\build_labels.py`
  - `scripts\phase4_features\build_baseline_features.py`
  - `scripts\phase7_wfa\run_wfa.py`
  - `scripts\phase8_model_selection\audit_direction_edge_calibration.py`
  - `scripts\phase8_model_selection\audit_event_level_edge_feasibility.py`
  - `scripts\phase8_model_selection\audit_label_feature_sanity.py`
  - `scripts\phase8_model_selection\audit_mr_tail_risk.py`
  - `scripts\phase8_model_selection\audit_policy_failure.py`
  - `scripts\phase8_model_selection\audit_policy_run_level_overlap.py`
  - `scripts\phase8_model_selection\audit_policy_signal_alignment.py`
  - `scripts\phase8_model_selection\audit_signal_trade_quality.py`
  - `scripts\phase8_model_selection\audit_threshold_and_target_sanity.py`
  - `scripts\phase8_model_selection\audit_trade_failure_drilldown.py`
  - `scripts\phase8_model_selection\evaluate_predictions.py`
  - `scripts\validation\feature_leakage_guard.py`
  - `scripts\validation\model_registry.py`
  - `tests\phase3_labels\test_build_labels.py`
  - `tests\phase4_features\test_build_baseline_features.py`
  - `tests\phase7_wfa\test_run_wfa.py`
  - `tests\phase8_model_selection\test_audit_direction_edge_calibration.py`
  - `tests\phase8_model_selection\test_audit_event_level_edge_feasibility.py`
  - `tests\phase8_model_selection\test_audit_label_feature_sanity.py`
  - `tests\phase8_model_selection\test_audit_mr_tail_risk.py`
  - `tests\phase8_model_selection\test_audit_policy_failure.py`
  - `tests\phase8_model_selection\test_audit_policy_run_level_overlap.py`
  - `tests\phase8_model_selection\test_audit_policy_signal_alignment.py`
  - `tests\phase8_model_selection\test_audit_signal_trade_quality.py`
  - `tests\phase8_model_selection\test_audit_threshold_and_target_sanity.py`
  - `tests\phase8_model_selection\test_audit_trade_failure_drilldown.py`
  - `tests\phase8_model_selection\test_evaluate_predictions.py`
  - `tests\validation\test_model_registry.py`
- Preserved untracked future-work support file:
  - `tests\phase8_model_selection\side_aware_fixture.py`

### Side-aware future-work scope

- The preserved diffs span label generation, feature contract columns, WFA prediction schema/routing, Phase 8 policy evaluation, Phase 8 audit behavior, model registry validation, purge horizon config, and tests.
- The implementation appears internally coherent as future work, but it is not validated for current pipeline use.
- The verified Phase 8 closeout evidence allows only plan-only or diagnostic-only future research paths and explicitly does not approve implementation/config/script/test behavior changes.
- Before any pipeline run, model result, archive decision, cleanup decision, closeout claim, or promotion claim relies on these diffs, a separate implementation validation plan is required.

### Current safety rules

- Do not delete quarantine.
- Do not mutate `data/**`.
- Do not treat the side-aware implementation diffs as approved current pipeline behavior without a separate validation plan and explicit user confirmation.
- Do not stage or commit unless explicitly asked.
- Do not revert any tracked source/config/test change unless explicitly requested.
- Do not run pipeline phases, WFA/modeling, model selection, cleanup, dry-run cleanup, archive, or quarantine workflows to validate these diffs in this disposition-only scope.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: build a validation plan for preserved future side-aware trend implementation diffs.
Rules:
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Preserve data/_quarantine/actual_cleanup_v1_20260628_130232 for rollback.
- Do not stage or commit unless explicitly asked.
- Do not revert tracked source/config/test changes unless explicitly requested.
Task:
- Treat the side-aware code/config/test diffs and tests/phase8_model_selection/side_aware_fixture.py as preserved future implementation work, not approved current pipeline behavior.
- Design a validation plan that proves or rejects the side-aware trend implementation before any pipeline run, model result, archive decision, cleanup decision, closeout claim, or promotion claim relies on it.
- Include required static checks, focused tests, schema/manifest compatibility checks, and explicit stop conditions for any failing validation.
Stop when:
- The future side-aware implementation has a decision-complete validation plan, or the user explicitly chooses to revert or accept the diffs as intentional current work.
```

## Latest Data Path Audit Smoke Run

- Updated at UTC: 2026-06-28T15:48:31Z.
- Purpose: map Phase 1A, 1B, 1C, and 2 smoke data paths; verify tested scripts against the project pipeline entrypoints; compare active/smoke-used folders to every discovered `.parquet` and `.dbn.zst` artifact folder; identify strict archive candidates; and complete a Phase 1-9 smoke excluding archive candidates.
- Run root: `reports\data_path_audit_20260628T152225Z`.
- Summary report: `reports\data_layout_audit_20260628.md`.
- Evidence JSON: `reports\data_path_audit_20260628T152225Z\data_path_audit_evidence.json`.
- Artifact folder inventory: `reports\data_path_audit_20260628T152225Z\artifact_dirs.csv` captured 4274 pre-smoke artifact folders. A post-smoke whole-repo refresh found 4279 artifact folders after adding 5 report-scoped smoke output dirs under `reports\data_path_audit_20260628T152225Z\smoke_data\...`; those 5 are active smoke evidence, not archive candidates.
- Worktree before the run was clean. Generated audit outputs are under ignored `reports\`.
- No `data/**` folder or file was deleted, moved, archived, quarantined, renamed, or intentionally mutated.
- Supplemental checkpoint reviewed: `C:\Users\donny\Desktop\You_are_here_updated_current_FINAL_20260628.txt`.
- Valuable verified checkpoint information was incorporated into the audit report:
  - Actual cleanup evidence exists under `reports\data_audit\final\actual_cleanup_v1`.
  - Post-cleanup validation evidence exists under `reports\data_audit\final\post_cleanup_validation_v1`.
  - Quarantine root exists: `data\_quarantine\actual_cleanup_v1_20260628_130232`.
  - Old candidate paths are absent at their original locations: `data\causally_gated_normalized`, `data\raw\_repair_candidates`, `data\feature_matrices\baseline`, `data\predictions`, and `data\dbn_sr_parent_candidate`.
  - Actual cleanup was reversible quarantine/move only: deletion executed `false`, counts matched `true`, bytes matched `true`, protected path overlap found `false`, rollback available `true`.
  - These five stale roots are not current archive candidates because they have already been quarantined and must be preserved for rollback until explicitly approved for deletion.
- Supplemental checkpoint caveat: its `Git worktree: CLEAN` claim is stale for the current workspace. Current `git status --short` shows tracked modifications in source/config/test files plus `CODEX_HANDOFF.md`; do not treat the external checkpoint as a fully current handoff until that is reconciled.
- Pipeline entrypoint check:
  - Phase 1A: `scripts.phase1A_download.download_databento_raw`, matched `PIPELINE.md`.
  - Phase 1B: `scripts.phase1B_convert.convert_databento_raw`, matched `PIPELINE.md` wrapper over convert-parquet.
  - Phase 1C: `scripts.phase1C_validate.audit_raw_dbn_alignment`, matched `PIPELINE.md`.
  - Phase 2: `scripts.phase2_causal_base.build_causal_base_data`, actual CLI requires explicit `--output-root`.
  - Phase 3: `scripts.phase3_labels.build_labels`, actual CLI requires explicit `--input-root`.
  - Phase 4: `scripts.phase4_features.build_baseline_features`, actual CLI requires explicit `--output-root`.
  - Phase 5: `scripts.phase5_wfa.build_wfa_splits`, actual CLI requires explicit `--input-root`.
  - Phase 6: `scripts.phase6_wfa.run_wfa`, wrapper imports Phase 7 implementation.
  - Phase 7: `scripts.phase7_wfa.run_wfa`, legacy implementation package.
  - Phase 8: `scripts.phase8_model_selection.evaluate_predictions`, explicit prediction path required.
  - Phase 9: `scripts.phase9_research.directional_path_quality_target_harness`, representative implemented harness.
- Phase/data path smoke results:
  - Phase 1A dry run exited 0 and planned `data\dbn\ohlcv_1m` plus `reports\data_path_audit_20260628T152225Z\phase1a`.
  - Phase 1B staged ES 2024 exited 0 using `data\dbn\ohlcv_1m` and `data\dbn\definition`, writing staged raw parquet under `reports\data_path_audit_20260628T152225Z\smoke_data\raw`.
  - Phase 1C alignment exited 0 using `data\dbn` and staged raw parquet, writing `reports\data_path_audit_20260628T152225Z\phase1c\raw_dbn_alignment.json`.
  - Phase 2 exited 0 using staged raw parquet, writing staged causal parquet under `reports\data_path_audit_20260628T152225Z\smoke_data\causally_gated_normalized`.
  - Phase 3 exited 0 using staged causal parquet, writing staged labels under `reports\data_path_audit_20260628T152225Z\smoke_data\labeled`.
  - Phase 4 exited 0 using staged labels, writing staged features under `reports\data_path_audit_20260628T152225Z\smoke_data\feature_matrices\baseline`; the staged feature manifest carried a warning because only ES 2024 was staged and intermarket features were unavailable.
  - Staged Phase 5 Tier 0 exited 1 because `feature_manifest_gate` rejected unavailable intermarket feature warnings.
  - Active protected Tier 1 Phase 5 fallback exited 0 using `data\feature_matrices\baseline_tier1_rebuild_v1`, `reports\data_audit\wfa_research\tier1_rebuild_v1\preflight\data_audit_universe_tier1_rebuild_v1.json`, and `reports\data_audit\wfa_research\tier1_rebuild_v1\preflight\tier1_rebuild_v1_feature_set.json`; output root was `reports\data_path_audit_20260628T152225Z\phase5_tier1_active`.
  - Initial Phase 6 ES one-fold Tier 1 smoke timed out after 900 seconds with empty stdout/stderr and no new prediction output under `reports\data_path_audit_20260628T152225Z\smoke_data\predictions` or `reports\data_path_audit_20260628T152225Z\phase6`.
  - Follow-up Phase 6 bounded ZN smoke exited 0 using the same active protected Tier 1 input root, split plan, feature set, data-audit universe, and models config. It selected `ZN_research_0011` with `--markets ZN --fold-shard-count 12 --fold-shard-index 11 --max-folds 1`, wrote `reports\data_path_audit_20260628T152225Z\smoke_data\predictions_zn_min\data_path_smoke_20260628T152225Z_zn_min\oos_predictions.parquet`, and wrote manifest `reports\data_path_audit_20260628T152225Z\phase6_zn_min\data_path_smoke_20260628T152225Z_zn_min_predictions_manifest.json`.
  - Follow-up Phase 6 manifest result: `failure_count=0`, `artifact_evidence_ready=true`, `prediction_count=84608`, `fold_count=1`, `prediction_markets=["ZN"]`, `prediction_years=[2024]`.
  - Follow-up Phase 8 exited 0 against the fresh bounded Phase 6 prediction artifact and manifest, writing reports under `reports\data_path_audit_20260628T152225Z\phase8_zn_min`.
  - Follow-up Phase 8 result: `failure_count=0`, `warning_count=1`, `research_policy_metrics_ready=true`, `row_count=21152`, `trade_count=16`, `gross_return_dollars=562.5`, `cost_dollars=553.44`, `net_return_dollars=9.059999999999945`, `research_alpha_ready=false`, `model_promotion_allowed=false`, `live_execution_ready=false`.
  - Phase 9 active Tier 1 directional harness exited 0 using `data\feature_matrices\baseline_tier1_rebuild_v1` and `reports\data_path_audit_20260628T152225Z\phase5_tier1_active\split_plan.json`; output root was `reports\data_path_audit_20260628T152225Z\phase9`.
- Data folder comparison:
  - Discovered artifact folders with `.parquet` or `.dbn.zst`: `4279` current; `4274` in the pre-smoke inventory CSV plus 5 generated report-scoped smoke output folders.
  - Suspicious/classified roots: `53`.
  - Active/protected roots: `53`.
  - Safe archive candidates under denylist-only rules: `0`.
  - Physical-exclusion-test blockers: `0`.
  - Proceed status: `yes with medium blockers` because the supplemental checkpoint's worktree-clean claim is not current.
- Archive decision:
  - No folder is approved as safe to archive from this run.
  - No physical exclusion smoke test was needed because no strict archive candidates were found.
  - Keep `data\dbn`, `data\raw`, `data\causal_base_candidates\tier1_rebuild_v1`, `data\labeled\tier1_rebuild_v1`, `data\feature_matrices\baseline_tier1_rebuild_v1`, and `reports\data_audit\**` protected.
  - Keep `data\_quarantine\actual_cleanup_v1_20260628_130232` preserved for rollback; do not delete quarantine without a new explicit approval workflow.

### Exact Next Recommended Step

Reconcile the dirty tracked worktree before treating `C:\Users\donny\Desktop\You_are_here_updated_current_FINAL_20260628.txt` as a fully current handoff. Do not delete, move, rename, archive, quarantine, or mutate `data/**`; preserve `data\_quarantine\actual_cleanup_v1_20260628_130232` for rollback unless a new explicit approval workflow authorizes deletion.

## Latest Phase 8 Research Metrics Run

- Updated at UTC: 2026-06-28.
- Purpose: run Phase 8 gross/net research metrics from the existing report-scoped WFA prediction artifact only.
- Prediction artifact used: `reports\data_audit\wfa_research\tier1_rebuild_v1\metrics_artifacts\tier1_rebuild_v1_research_metrics_artifacts\oos_predictions.parquet`.
- Prediction manifest used: `reports\data_audit\wfa_research\tier1_rebuild_v1\metrics_artifacts\wfa_prediction_rerun\tier1_rebuild_v1_research_metrics_artifacts_predictions_manifest.json`.
- Output roots:
  - `reports\data_audit\wfa_research\tier1_rebuild_v1\metrics_artifacts\phase8_metrics`
  - `reports\data_audit\wfa_research\tier1_rebuild_v1\metrics_artifacts\model_selection`
  - `reports\data_audit\wfa_research\tier1_rebuild_v1\metrics_artifacts\phase8`
- Command exited 0 with `PASS model diagnostics: rows=1146552 trades=261 net_dollars=-9955.740000000023 alpha_ready=False failures=0`.
- Report files written:
  - `phase8_metrics\tier1_rebuild_v1_research_metrics_artifacts_metrics.csv`
  - `phase8_metrics\tier1_rebuild_v1_research_metrics_artifacts_metrics.json`
  - `phase8_metrics\turnover_diagnostics.csv`
  - `model_selection\calibration_report.json`
  - `model_selection\model_comparison.csv`
  - `model_selection\model_selection_report.json`
  - `phase8\alpha_promotion_decision.json`
  - `phase8\metrics.json`
- Metrics summary from `model_selection_report.json`:
  - rows: `1146552`
  - trades: `261`
  - candidate trades: `938`
  - gross_return_dollars: `-2380.0000000000236`
  - cost_dollars: `7575.74`
  - net_return_dollars: `-9955.740000000023`
  - gross_sharpe_like: `-0.33961880966612407`
  - net_sharpe_like: `-1.4156866011544051`
  - cost_drag_to_abs_gross: `3.183084033613414`
  - turnover_per_bar: `0.00045353372546556983`
  - slippage_cost_dollars: `6395.0`
  - commission_cost_dollars: `1180.74`
  - win_rate_net_positive: `0.4444444444444444`
- Selection/promotion result:
  - `selection_status=NOT_SELECTED_BASELINE_DIAGNOSTICS_ONLY`
  - `research_alpha_ready=false`
  - `model_promotion_allowed=false`
  - `live_execution_ready=false`
  - `failure_count=0`
  - `warning_count=1`
  - warning: policy economics use max-one-contract non-overlapping target-window execution; partial fills, order rejection, latency, and capacity remain outside Phase 8.
- Safety:
  - No cleanup or dry-run cleanup.
  - No `data/**` mutation.
  - No `data\predictions\**` output.
  - No new predictions generated.
  - No model artifacts written.
  - No WFA/modeling rerun.
  - Research-only; no production/live readiness.

## Latest Cleanup Reference Readiness Run

- Updated at UTC: 2026-06-28T06:56:47Z
- Latest scoped pass: protected causal reference classification in allowed manifest/audit-policy files only.
- Result: `data/causally_gated_normalized` remains a protected cleanup blocker; cleanup remains blocked and dry-run cleanup remains unsafe.
- Files inspected in scoped pass:
  - `configs\data_manifest.yaml`
  - `scripts\audit_databento_phase0.py`
  - `scripts\audit_databento_phase4.py`
  - `scripts\audit_databento_phase5.py`
  - `tests\test_audit_databento_phase0.py`
  - `tests\test_audit_databento_phase4.py`
  - `tests\test_audit_databento_phase5.py` was requested but is absent.
- Safe references retired in scoped pass:
  - `scripts\audit_databento_phase0.py`: stale final map text no longer names `data/causally_gated_normalized` as current causal/modeling base.
  - `scripts\audit_databento_phase4.py`: labels expected source/trace fields now say `configured_modeling_input` instead of hardcoding `data/causally_gated_normalized`.
  - `tests\test_audit_databento_phase4.py`: explicit rebuild fixture now preserves protected keep root `data/causal_base_candidates/tier1_rebuild_v1`.
- Remaining protected final blockers in allowed scope:
  - `configs\data_manifest.yaml`: canonical causal parquet pattern plus repair/audit artifact policy for `data/causally_gated_normalized`.
  - `scripts\audit_databento_phase5.py`: approved causal base policy is hardcoded to `data/causally_gated_normalized` and has no focused test file in this repo.
  - `scripts\audit_databento_phase0.py`: scanner/classifier strings for current derived and pre-replace backup classification.
  - `scripts\audit_databento_phase4.py`: scanner/classifier/modeling-root strings and causal audit variables/rows.
  - `tests\test_audit_databento_phase0.py`: pre-replace backup classification fixture.
- Validation in scoped pass:
  - `python -m pytest tests\test_audit_databento_phase0.py tests\test_audit_databento_phase4.py` -> `11 passed`
  - Required `rg` including `tests\test_audit_databento_phase5.py` returned matches plus missing-file error for that absent test.
  - Re-run `rg` on existing allowed files succeeded and showed only the documented protected/scanner/test references.
  - `git diff --check -- ...` passed with CRLF warnings only.
- Safety:
  - No dry-run cleanup or actual cleanup.
  - No `data/**` mutation.
  - No raw path edits.
  - No WFA/modeling/metrics or prediction/model artifacts.
  - No staging or commit.

- Updated at UTC: 2026-06-28T06:43:33Z
- Purpose: cleanup-reference readiness review after retiring feature/causal root defaults.
- Repo: `C:\Users\donny\Desktop\futures_intraday_model`
- Result: cleanup remains blocked; dry-run cleanup remains unsafe; actual cleanup is not approved.

### Current Status

- Created focused commits:
  - `21ea413 Neutralize central feature matrix root defaults`
  - `d8609c1 Require explicit Phase 3 label input root`
  - `1a9bbbf Require explicit Phase 2 causal output root`
  - `e97603a Require explicit Phase 2 readiness output root`
  - `03d7eb1 Require explicit raw session audit causal root`
  - `fb7bc54 Require explicit external OHLCV audit causal root`
  - `3de6d7f Require explicit OHLCV provenance causal root`
  - `108e2bb Require explicit local trade audit causal root`
  - `900fb95 Require explicit missing minute manifest causal root`
  - `0f4e2df Require explicit tier coverage causal root`
  - `cb7f2ef Neutralize central causal base root defaults`
- Central configs now have `feature_matrix_root: null` and `causal_base_root: null`.
- Direct Phase 2/3 causal defaults and validation `--causal-root` defaults were changed to require explicit roots.
- Ignored final report summaries under `reports\data_audit\final\` were refreshed as report-only evidence and must remain unstaged unless explicitly approved.

### Validation

- `python -m pytest tests\phase4_features\test_build_baseline_features.py tests\test_audit_databento_phase4.py` -> `47 passed`
- `python -m pytest tests\phase3_labels\test_build_labels.py` -> `28 passed`
- `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py` -> `124 passed`
- `python -m pytest tests\validation\test_audit_phase2_readiness.py` -> `13 passed`
- `python -m pytest tests\validation\test_audit_raw_session_gaps.py` -> `5 passed`
- `python -m pytest tests\validation\test_audit_external_ohlcv_gaps.py` -> `12 passed`
- `python -m pytest tests\validation\test_audit_ohlcv_provenance_continuity.py` -> `6 passed`
- `python -m pytest tests\validation\test_audit_local_trade_ohlcv_gaps.py` -> `12 passed`
- `python -m pytest tests\validation\test_build_missing_minute_verification_manifest.py` -> `14 passed`
- `python -m pytest tests\validation\test_tier_2_coverage.py` -> `20 passed`
- `python -m pytest tests\test_audit_databento_phase4.py` -> `8 passed`
- `git diff --check` passed before each committed batch; Git emitted only CRLF warnings.

### Remaining Blockers

- `data/causally_gated_normalized` remains an active cleanup blocker because current `rg` still finds protected manifest/audit-policy references:
  - `configs\data_manifest.yaml` canonical causal pattern and repair/audit policy entries.
  - `scripts\audit_databento_phase0.py`, `scripts\audit_databento_phase4.py`, and `scripts\audit_databento_phase5.py` audit policy labels/approved causal-base logic.
  - `PIPELINE.md`, hygiene guards, and explicit test fixtures.
- `data/raw` and `data/raw/_repair_candidates` remain active blockers and must be left for a separate raw-specific pass.
- No dry-run cleanup or actual cleanup was run. No `data\` mutation, WFA/modeling/metrics, predictions, provider/network, or live/paper actions were run.

### Files Changed In Latest Run

- Source/config/test commits changed:
  - `configs\alpha_tiered.yaml`
  - `configs\tier_3.yaml`
  - `scripts\phase3_labels\build_labels.py`
  - `scripts\phase2_causal_base\build_causal_base_data.py`
  - `scripts\validation\audit_phase2_readiness.py`
  - `scripts\validation\audit_raw_session_gaps.py`
  - `scripts\validation\audit_external_ohlcv_gaps.py`
  - `scripts\validation\audit_ohlcv_provenance_continuity.py`
  - `scripts\validation\audit_local_trade_ohlcv_gaps.py`
  - `scripts\validation\build_missing_minute_verification_manifest.py`
  - `scripts\validation\check_tier_2_coverage.py`
  - `scripts\audit_databento_phase4.py`
  - related focused tests under `tests\`
- Report-only ignored files refreshed:
  - `reports\data_audit\final\manual_review_classification_refresh.csv`
  - `reports\data_audit\final\manual_review_classification_refresh.md`
  - `reports\data_audit\final\manual_review_classification_safety_gate.json`
  - `reports\data_audit\final\cleanup_blocker_refresh.csv`
  - `reports\data_audit\final\cleanup_blocker_refresh.md`
  - `reports\data_audit\final\cleanup_blocker_safety_gate.json`

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: decide and implement the disposition of remaining data/causally_gated_normalized cleanup blockers in protected manifest/audit-policy references only.
Rules:
- Do not run dry-run cleanup or actual cleanup.
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Do not run WFA/modeling/metrics, generate predictions/model artifacts, or claim production/live readiness.
- Do not touch raw-root defaults or data/raw cleanup blockers in this scope.
- Do not stage generated reports or ignored artifacts.
Task:
- Establish state with Get-Location and git status --short, then read CODEX_HANDOFF.md.
- Inspect only configs/data_manifest.yaml, scripts/audit_databento_phase0.py, scripts/audit_databento_phase4.py, scripts/audit_databento_phase5.py, and their focused tests.
- Decide whether each data/causally_gated_normalized reference is an active protected policy reference that must remain a blocker, or a stale/default claim that can be safely changed to fail closed or point to explicit rebuilt evidence.
- If a safe one-batch edit exists, implement only that batch and run its focused tests plus targeted rg; otherwise update the final blocker report/handoff without code changes.
Stop when:
- data/causally_gated_normalized is either fully retired from active manifest/audit-policy references, or the remaining protected references are documented as final blockers with cleanup_eligible_now=false and dry_run_cleanup_safe_next=false.
```

## Older Data-Readiness History

- Updated at UTC: 2026-06-27T00:46:50Z
- Purpose: Current futures data-readiness/provenance state after final global Phase 1-2 reconciliation of the approved campaign rows.
- Repo: `C:\Users\donny\Desktop\futures_intraday_model`

## Current Verified State

- Worktree is dirty in pre-existing tracked/untracked files. No staging or commit was performed.
- Provider/network commands were not run.
- Latest canonical mutation was approved and limited to `data\causally_gated_normalized\KE\2023.parquet`.
- Latest generated artifacts were limited to ZS 2021/2022 fail-closed decision packet reports under `reports\phase2_readiness`.
- Latest tracked mutations are the focused decision-packet tooling/tests and this handoff refresh.

## Current PASS Canonical Evidence

- `SR1 2020` and `SR3 2020` have current canonical raw and canonical Phase 2 causal PASS evidence:
  - `reports\phase2_readiness\sr1_sr3_2020_phase2_causal_build_after_parent_overwrite_20260626\causal_base\causal_base_manifest.json`
  - manifest `status=PASS`, `processed_market_year_count=2`, `summary.pass_count=2`, `summary.fail_count=0`, `failure_count=0`, `warning_count=0`, `summary.synthetic_rows=0`, `summary.degraded_bar_rows=0`
- `KE 2019`, `KE 2021`, and `KE 2024` have current canonical raw and canonical Phase 2 causal PASS evidence under accepted `parent_sparse_ohlcv_no_trade`:
  - `reports\phase2_readiness\ke_2019_2021_2024_phase2_causal_build_after_sparse_exception_correction_20260626\causal_base\causal_base_manifest.json`
  - manifest `status=PASS`, `processed_market_year_count=3`, `summary.pass_count=3`, `summary.fail_count=0`, `failure_count=0`, `accepted_exception_count=3`, `accepted_exception_failure_count=0`
- `HE 2016`, `HE 2019`, `HE 2020`, `LE 2016`, and `LE 2020` have current canonical Phase 2 causal PASS evidence under row-specific accepted exceptions:
  - `reports\phase2_readiness\he_le_accepted_phase2_causal_build_after_exception_correction_20260626\causal_base\causal_base_manifest.json`
  - manifest `status=PASS`, `processed_market_year_count=5`, `summary.pass_count=5`, `summary.fail_count=0`, `failure_count=0`, `accepted_exception_count=5`, `accepted_exception_failure_count=0`

## Latest KE 2023 Reports-Only Candidate Result

- Source audit:
  - command exited 0
  - report: `reports\phase2_readiness\ke_2023_parent_candidate_20260626\source_audit.json`
  - `status=PASS`
  - `repair_source_ready_count=1`
  - `blocked_count=0`
- Verified KE 2023 parent source evidence:
  - `data\dbn\ohlcv_1m_parent\KE\2023\2023-01-01_2024-01-01.dbn.zst` sha256 `9c039b073f9480327e5d7fd7f52f17c8cb8b97797f8fc74321db73b84a735fe0`, schema `ohlcv-1m`, `stype_in=parent`
  - `data\dbn\status_parent\status\KE\2023\2023-01-01_2024-01-01.dbn.zst` sha256 `2da4c2bc412035dd486d501c6ef8fd9fb8a072c0cf28e86ae30f7899f20693f1`, schema `status`, `stype_in=parent`
  - `data\dbn\statistics_parent\statistics\KE\2023\2023-01-01_2024-01-01.dbn.zst` sha256 `5dee0be3a302f26241ea3007528150eb0037035778b860c19fe10a06d1133b11`, schema `statistics`, `stype_in=parent`
  - `data\dbn\definition\KE\2023\2023-01-01_2024-01-01.dbn.zst` sha256 `96ee1d9549404ec972ced7116798ddfcc33ee9bc8c79f3741bd640c5965f0f20`, schema `definition`, `stype_in=parent`
- Candidate validation:
  - command exited 0
  - manifest: `reports\phase2_readiness\ke_2023_parent_candidate_20260626\sr_front_contract_candidate_manifest.json`
  - raw alignment: `reports\phase2_readiness\ke_2023_parent_candidate_20260626\sr_front_contract_candidate_raw_alignment.json`
  - manifest `status=PASS`, `output_count=1`, `failures=[]`
  - raw alignment `status=PASS`, `expected_market_year_count=1`, `raw_market_year_count=1`, `missing_raw_count=0`, `raw_schema_failure_count=0`, `source_hash_mismatch_count=0`
- Candidate raw output:
  - `reports\phase2_readiness\ke_2023_parent_candidate_20260626\raw\KE\2023.parquet`
  - sha256 `9496be59af2f0708bd8c6eecf3dc0a3258b093f03b9e75846b0c774f26010b83`
  - length `2785064`
  - rows `102470`
  - market values only `KE`
  - year values only `2023`
  - source columns point to:
    - `data/dbn/ohlcv_1m_parent/KE/2023/2023-01-01_2024-01-01.dbn.zst`
    - `data/dbn/status_parent/status/KE/2023/2023-01-01_2024-01-01.dbn.zst`
    - `data/dbn/statistics_parent/statistics/KE/2023/2023-01-01_2024-01-01.dbn.zst`

## Latest KE 2023 Reports-Only Readiness Result

- Focused parent-sparse tests passed:
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -k "parent_sparse"`
  - `13 passed, 101 deselected`
- Corrected tracked contract/config:
  - `scripts\phase2_causal_base\build_causal_base_data.py`: added exact allowlist row `("KE", 2023)` for `parent_sparse_ohlcv_no_trade`.
  - `configs\alpha_tiered.yaml`: added exact KE 2023 `accepted_readiness_exceptions` row with warning `synthetic threshold breached: rows_pct=53.439024 max_gap_minutes=116` and KE 2023 candidate manifest/alignment evidence paths.
  - `tests\phase2_causal_base\test_build_causal_base_data.py`: added focused KE 2023 parent-sparse accepted-exception coverage.
- Reports-only readiness rerun command exited 0.
- Report root: `reports\phase2_readiness\ke_2023_parent_candidate_readiness_after_sparse_exception_correction_20260626`
- Generated files:
  - `reports\phase2_readiness\ke_2023_parent_candidate_readiness_after_sparse_exception_correction_20260626\phase2_readiness.json`
  - `reports\phase2_readiness\ke_2023_parent_candidate_readiness_after_sparse_exception_correction_20260626\phase2_readiness.jsonl`
- `phase2_readiness.json`:
  - `status=PASS`
  - `selected_market_year_count=1`
  - `expected_market_year_count=1`
  - `checked_market_year_count=1`
  - `pass_count=1`
  - `blocker_count=0`
  - `failure_count=0`
  - `failures=[]`
  - `reason_counts={}`
  - enrichment totals are zero for status/statistics missing/stale rows.
- `phase2_readiness.jsonl` contains one row:
  - `market=KE`
  - `year=2023`
  - `status=PASS`
  - `original_status=WARN`
  - `output_rows=220077`
  - `synthetic_rows=117607`
  - `synthetic_rows_pct=53.439024`
  - `max_synthetic_gap_minutes=116`
  - `degraded_bar_rows=0`
  - `warnings=["synthetic threshold breached: rows_pct=53.439024 max_gap_minutes=116"]`
  - `accepted_readiness_exception.category=parent_sparse_ohlcv_no_trade`
  - accepted evidence paths:
    - `reports/phase2_readiness/ke_2023_parent_candidate_20260626/sr_front_contract_candidate_manifest.json`
    - `reports/phase2_readiness/ke_2023_parent_candidate_20260626/sr_front_contract_candidate_raw_alignment.json`
  - accepted exception status/statistics missing/stale rows are all zero.

## Latest KE 2023 Canonical Raw Promotion Preflight Result

- Result: `ke_2023_raw_promotion_preflight_blocked_conflicting_destination`
- Candidate raw source:
  - `reports\phase2_readiness\ke_2023_parent_candidate_20260626\raw\KE\2023.parquet`
  - size `2785064`
  - sha256 `9496be59af2f0708bd8c6eecf3dc0a3258b093f03b9e75846b0c774f26010b83`
  - rows `102470`
  - market values only `KE`
  - year values only `2023`
- Canonical destination:
  - `data\raw\KE\2023.parquet`
  - exists
  - size `3763292`
  - sha256 `bb0f99a710ea3cda235270d5a72a6d1e5cfaddfa6938560510805c3876775fc2`
  - classification `conflicting`
- No canonical raw copy, overwrite, promotion, provider command, Phase 2 causal build, or report generation was performed.

## Latest KE 2023 Canonical Raw Conflict Audit Result

- Result: `ke_2023_raw_conflict_audit_destination_stale_wrong_source`
- Candidate raw:
  - `reports\phase2_readiness\ke_2023_parent_candidate_20260626\raw\KE\2023.parquet`
  - rows `102470`
  - size `2785064`
  - sha256 `9496be59af2f0708bd8c6eecf3dc0a3258b093f03b9e75846b0c774f26010b83`
  - market values only `KE`
  - year values only `2023`
  - source file `data/dbn/ohlcv_1m_parent/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - status source file `data/dbn/status_parent/status/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - statistics source file `data/dbn/statistics_parent/statistics/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - status/statistics missing/stale rows all zero
  - degraded rows `0`
  - duplicate timestamp rows `0`
  - maturity backsteps `0`
- Canonical destination:
  - `data\raw\KE\2023.parquet`
  - rows `141741`
  - size `3763292`
  - sha256 `bb0f99a710ea3cda235270d5a72a6d1e5cfaddfa6938560510805c3876775fc2`
  - market values only `KE`
  - year values only `2023`
  - source file `data/dbn/ohlcv_1m/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - status source file `data/dbn/status/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - statistics source file `data/dbn/statistics/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - status/statistics missing/stale rows all zero
  - degraded rows `0`
  - duplicate timestamp rows `0`
  - maturity backsteps `0`
- Candidate and destination source paths/source hashes are not equal. The canonical destination uses non-parent roots and is stale for the current parent-source repair path.
- No canonical raw copy, overwrite, promotion, provider command, Phase 2 causal build, or report generation was performed.

## Latest KE 2023 Canonical Raw Overwrite Result

- Decision: `approve_ke_2023_canonical_raw_overwrite_parent_source_only`
- Mutated only approved canonical raw file:
  - `data\raw\KE\2023.parquet`
- Source copied:
  - `reports\phase2_readiness\ke_2023_parent_candidate_20260626\raw\KE\2023.parquet`
  - pre-copy sha256 `9496be59af2f0708bd8c6eecf3dc0a3258b093f03b9e75846b0c774f26010b83`
  - pre-copy rows `102470`
  - parent source columns under `data/dbn/ohlcv_1m_parent`, `data/dbn/status_parent`, and `data/dbn/statistics_parent`
- Destination before copy:
  - `data\raw\KE\2023.parquet`
  - sha256 `bb0f99a710ea3cda235270d5a72a6d1e5cfaddfa6938560510805c3876775fc2`
  - rows `141741`
  - non-parent source columns under `data/dbn/ohlcv_1m`, `data/dbn/status`, and `data/dbn/statistics`
- Destination after copy:
  - `data\raw\KE\2023.parquet`
  - sha256 `9496be59af2f0708bd8c6eecf3dc0a3258b093f03b9e75846b0c774f26010b83`
  - size `2785064`
  - rows `102470`
  - market values only `KE`
  - year values only `2023`
  - source file `data/dbn/ohlcv_1m_parent/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - status source file `data/dbn/status_parent/status/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - statistics source file `data/dbn/statistics_parent/statistics/KE/2023/2023-01-01_2024-01-01.dbn.zst`
  - degraded rows `0`
  - status/statistics missing/stale rows all zero
  - duplicate timestamp rows `0`
  - maturity backsteps `0`
- No DBN source, provider, live/paper, WFA/model/feature/label/prediction, reports, tracked code/config/tests, staging, or commits were mutated.

## Latest KE 2023 Canonical Raw Validation/Readiness Result

- Report root: `reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626`
- First alignment-only command with unsupported `--candidate-root` failed before writing `canonical_raw_alignment.json`.
- Rerun with current supported CLI exited 0:
  - `python -m scripts.validation.promote_sr_roll_repair_candidate --alignment-only-existing-raw --raw-root data\raw --candidate-manifest reports\phase2_readiness\ke_2023_parent_candidate_20260626\sr_front_contract_candidate_manifest.json --readiness-summary reports\phase2_readiness\ke_2023_parent_candidate_readiness_after_sparse_exception_correction_20260626\phase2_readiness.json --promoted-raw-alignment-out reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626\canonical_raw_alignment.json`
- `canonical_raw_alignment.json`:
  - `status=PASS`
  - `raw_root=data/raw`
  - `expected_market_year_count=1`
  - `raw_market_year_count=1`
  - `missing_raw_count=0`
  - `raw_schema_failure_count=0`
  - `source_hash_mismatch_count=0`
  - market-years exactly `KE 2023`
- Reports-only readiness command exited 0:
  - `python -m scripts.validation.audit_phase2_readiness --profile tier_3_research --raw-root data\raw --raw-alignment-report reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626\canonical_raw_alignment.json --output-root reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626\causal_readiness_only --profile-config configs\alpha_tiered.yaml --session-config configs\market_sessions.yaml --markets KE --years 2023 --jobs 1 --summary-only --top-blockers 20 --json-out reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626\phase2_readiness.json --checkpoint-jsonl reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626\phase2_readiness.jsonl`
- `phase2_readiness.json`:
  - `status=PASS`
  - `selected_market_year_count=1`
  - `expected_market_year_count=1`
  - `checked_market_year_count=1`
  - `pass_count=1`
  - `blocker_count=0`
  - `failure_count=0`
  - `failures=[]`
  - `reason_counts={}`
  - enrichment totals are zero for status/statistics missing/stale rows.
- `phase2_readiness.jsonl` contains exactly `KE 2023`:
  - `status=PASS`
  - `original_status=WARN`
  - `synthetic_rows=117607`
  - `synthetic_rows_pct=53.439024`
  - `max_synthetic_gap_minutes=116`
  - `degraded_bar_rows=0`
  - `accepted_readiness_exception.category=parent_sparse_ohlcv_no_trade`
  - accepted warning preserved: `synthetic threshold breached: rows_pct=53.439024 max_gap_minutes=116`
  - status/statistics missing/stale rows all zero.

## Latest KE 2023 Phase 2 Causal Build Preflight Result

- Result: `ke_2023_phase2_build_preflight_pass`
- Verified canonical alignment:
  - `reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626\canonical_raw_alignment.json`
  - `status=PASS`
  - `raw_root=data/raw`
  - `expected_market_year_count=1`
  - `raw_market_year_count=1`
  - `missing_raw_count=0`
  - `raw_schema_failure_count=0`
  - `source_hash_mismatch_count=0`
  - market-years exactly `KE 2023`
- Verified canonical readiness:
  - `reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626\phase2_readiness.json`
  - `status=PASS`
  - `pass_count=1`
  - `blocker_count=0`
  - `failure_count=0`
  - `failures=[]`
- Verified readiness JSONL has exactly `KE 2023 PASS` with `accepted_readiness_exception.category=parent_sparse_ohlcv_no_trade`, degraded rows `0`, and status/statistics missing/stale rows `0`.
- Verified canonical raw hash:
  - `data\raw\KE\2023.parquet` sha256 `9496be59af2f0708bd8c6eecf3dc0a3258b093f03b9e75846b0c774f26010b83`
- Current build CLI supports `--raw-root`, `--output-root`, `--reports-root`, `--profile-config`, `--session-config`, `--raw-alignment-report`, and `--market-year-include-list`.
- Future output root is absent:
  - `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626`

## Latest KE 2023 Reports-Only Phase 2 Causal Build Result

- Report root: `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626`
- Include list:
  - `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\eligible_market_years.json`
  - exact content: `[{"market":"KE","year":2023}]`
- Build command exited 0:
  - `python -m scripts.phase2_causal_base.build_causal_base_data --profile tier_3_research --raw-root data\raw --output-root reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\causally_gated_normalized --reports-root reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\causal_base --profile-config configs\alpha_tiered.yaml --session-config configs\market_sessions.yaml --raw-alignment-report reports\phase2_readiness\ke_2023_canonical_raw_after_parent_overwrite_20260626\canonical_raw_alignment.json --market-year-include-list reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\eligible_market_years.json`
- Build stdout preserved original warning evidence:
  - `WARN KE 2023: raw=102470 out=220077 synthetic=117607 warnings=1 failures=0`
  - `local_trade_ohlcv_gap_gate status=SKIPPED`
- `causal_base_validation.json`:
  - `status=PASS`
  - `summary.file_count=1`
  - `summary.pass_count=1`
  - `summary.fail_count=0`
  - `failure_count=0`
  - `summary.warn_count=0`
  - `warning_count=1` because original warning evidence is retained
  - `accepted_exception_count=1`
  - `accepted_exception_failure_count=0`
  - `accepted_readiness_exception_failures=[]`
  - `summary.synthetic_rows=117607`
  - `summary.degraded_bar_rows=0`
  - `summary.causal_valid_rows=102297`
  - `summary.causal_invalid_rows=117780`
- `causal_base_manifest.json`:
  - `status=PASS`
  - `processed_market_year_count=1`
  - processed market-years exactly `KE 2023`
  - `summary.pass_count=1`
  - `summary.fail_count=0`
  - `summary.warn_count=0`
  - `accepted_exception_count=1`
  - `accepted_exception_failure_count=0`
  - original warning preserved under `accepted_readiness_exception.category=parent_sparse_ohlcv_no_trade`
- Reports-only output:
  - `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\causally_gated_normalized\KE\2023.parquet`
  - size `7009186`
  - sha256 `e22c229bb4f10c09b24aab62255e141d64a8be1dcf34aed94d12a0e04956e55d`
- No canonical causal output, provider state, live/paper, WFA/model/feature/label/prediction, staging, or commits were mutated.

## Latest KE 2023 Canonical Phase 2 Causal Promotion Preflight Result

- Result: `ke_2023_phase2_causal_promotion_preflight_pass_destination_missing_or_identical`
- Reports-only causal validation:
  - `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\causal_base\causal_base_validation.json`
  - `status=PASS`
  - `summary.pass_count=1`
  - `summary.fail_count=0`
  - `failure_count=0`
  - `accepted_exception_count=1`
  - `accepted_exception_failure_count=0`
  - `accepted_readiness_exception_failures=[]`
  - `summary.degraded_bar_rows=0`
  - original KE 2023 synthetic warning preserved as accepted exception evidence.
- Reports-only causal manifest:
  - `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\causal_base\causal_base_manifest.json`
  - `status=PASS`
  - `processed_market_year_count=1`
  - processed market-years exactly `KE 2023`
  - `summary.pass_count=1`
  - `summary.fail_count=0`
  - `accepted_exception_count=1`
  - `accepted_exception_failure_count=0`
- Reports-only causal source output:
  - `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\causally_gated_normalized\KE\2023.parquet`
  - size `7009186`
  - sha256 `e22c229bb4f10c09b24aab62255e141d64a8be1dcf34aed94d12a0e04956e55d`
- Canonical destination:
  - `data\causally_gated_normalized\KE\2023.parquet`
  - classification `missing`
- No canonical causal copy, overwrite, provider command, Phase 2 rebuild, WFA/model/feature/label/prediction, staging, or commits were performed.

## Latest KE 2023 Canonical Phase 2 Causal Promotion Result

- Decision: `approve_ke_2023_phase2_causal_promotion_canonical_only`
- Mutated only approved canonical Phase 2 causal file:
  - `data\causally_gated_normalized\KE\2023.parquet`
- Source copied:
  - `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\causally_gated_normalized\KE\2023.parquet`
  - pre-copy sha256 `e22c229bb4f10c09b24aab62255e141d64a8be1dcf34aed94d12a0e04956e55d`
  - pre-copy size `7009186`
- Destination before copy:
  - `data\causally_gated_normalized\KE\2023.parquet`
  - classification `missing`
- Destination after copy:
  - `data\causally_gated_normalized\KE\2023.parquet`
  - sha256 `e22c229bb4f10c09b24aab62255e141d64a8be1dcf34aed94d12a0e04956e55d`
  - size `7009186`
- Verified supporting reports before copy:
  - `causal_base_validation.json` status `PASS`, `summary.pass_count=1`, `summary.fail_count=0`, `failure_count=0`, `accepted_exception_count=1`, `accepted_exception_failure_count=0`, `summary.degraded_bar_rows=0`
  - `causal_base_manifest.json` status `PASS`, `processed_market_year_count=1`, processed market-years exactly `KE 2023`
- No `data\raw`, DBN source, provider, live/paper, WFA/model/feature/label/prediction, reports, tracked code/config/tests, staging, or commits were mutated.

## Latest KE 2023 Canonical Phase 2 Causal Validation Result

- Result: `ke_2023_canonical_phase2_causal_validation_pass`
- Canonical file is byte-identical to the reports-only source:
  - canonical: `data\causally_gated_normalized\KE\2023.parquet`
  - reports-only source: `reports\phase2_readiness\ke_2023_phase2_causal_build_after_parent_overwrite_20260626\causally_gated_normalized\KE\2023.parquet`
  - sha256 `e22c229bb4f10c09b24aab62255e141d64a8be1dcf34aed94d12a0e04956e55d`
  - size `7009186`
- Read-only parquet inspection:
  - rows `220077`
  - `market=KE` only
  - `year=2023` only
  - `is_synthetic_true=117607`
  - `data_quality_degraded_true=0`
  - `session_data_quality_degraded_true=0`
  - `status_missing_true=0`
  - `status_stale_true=0`
  - `statistics_missing_true=0`
  - `statistics_stale_true=0`
  - `source_path=data/raw/KE/2023.parquet`
  - `source_file_hash=9496be59af2f0708bd8c6eecf3dc0a3258b093f03b9e75846b0c774f26010b83`
  - `causal_valid_true=102297`
  - `causal_valid_false=117780`
  - invalid reasons: blank `102297`, `raw_row_missing|synthetic=117544`, `raw_row_missing|synthetic|roll_window=63`, `roll_window=92`, `outside_session=81`
- No file changed during the read-only validation after the approved canonical promotion.

## Latest ZC 2019-2024 Read-Only Source/Readiness Audit Result

- Result: `zc_2019_2024_fail_closed_wrong_source_type_no_parent_source`
- Current local parent/explicit source evidence:
  - `data\dbn\ohlcv_1m_parent\ZC\2019` through `data\dbn\ohlcv_1m_parent\ZC\2024`: missing
  - `data\dbn\status_parent\status\ZC\2019` through `data\dbn\status_parent\status\ZC\2024`: missing
  - `data\dbn\statistics_parent\statistics\ZC\2019` through `data\dbn\statistics_parent\statistics\ZC\2024`: missing
  - `data\dbn\definition\ZC\2019` through `data\dbn\definition\ZC\2024`: present, manifest readable, schema `definition`, `stype_in=parent`, size/hash metadata matched
- Current local continuous source evidence:
  - `data\dbn\ohlcv_1m\ZC\2019` through `data\dbn\ohlcv_1m\ZC\2024`: present, manifest readable, schema `ohlcv-1m`, `stype_in=continuous`, `symbols_requested=["ZC.v.0"]`, size/hash metadata matched
  - `data\dbn\status\ZC\2019` through `data\dbn\status\ZC\2024`: present, manifest readable, schema `status`, `stype_in=continuous`, `symbols_requested=["ZC.v.0"]`, size/hash metadata matched
  - `data\dbn\statistics\ZC\2019` through `data\dbn\statistics\ZC\2024`: present, manifest readable, schema `statistics`, `stype_in=continuous`, `symbols_requested=["ZC.v.0"]`, size/hash metadata matched
- Current canonical raw source columns:
  - `data\raw\ZC\2019.parquet`: rows `188301`, source `data/dbn/ohlcv_1m/ZC/2019/2019-01-01_2020-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZC\2020.parquet`: rows `209069`, source `data/dbn/ohlcv_1m/ZC/2020/2020-01-01_2021-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZC\2021.parquet`: rows `239474`, source `data/dbn/ohlcv_1m/ZC/2021/2021-01-01_2022-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZC\2022.parquet`: rows `231953`, source `data/dbn/ohlcv_1m/ZC/2022/2022-01-01_2023-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZC\2023.parquet`: rows `213492`, source `data/dbn/ohlcv_1m/ZC/2023/2023-01-01_2024-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZC\2024.parquet`: rows `198626`, source `data/dbn/ohlcv_1m/ZC/2024/2024-01-01_2025-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
- Current report/config evidence:
  - `configs\alpha_tiered.yaml` has no `accepted_readiness_exceptions` row for `ZC`.
  - `scripts\phase2_causal_base\build_causal_base_data.py` `PARENT_SPARSE_OHLCV_NO_TRADE_ALLOWED_MARKET_YEARS` includes only `KE 2019`, `KE 2021`, `KE 2023`, and `KE 2024`, not `ZC`.
  - Existing ZC decision packets remain `ACTION_REQUIRED` and fail-closed:
    - `reports\phase2_readiness\ZC_2019_scope_20260624\ZC_2019_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=85270`, `synthetic_rows_pct=31.169239`, `max_synthetic_gap_minutes=58`, `degraded_bar_rows=2405`
    - `reports\phase2_readiness\ZC_2020_scope_20260624\ZC_2020_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=65635`, `synthetic_rows_pct=23.89299`, `max_synthetic_gap_minutes=99`, `degraded_bar_rows=1683`
    - `reports\phase2_readiness\ZC_2021_scope_20260624\ZC_2021_decision_packet_20260624.json`: `decision=keep_fail_closed`, `synthetic_rows=36032`, `synthetic_rows_pct=13.078481`, `max_synthetic_gap_minutes=73`, `degraded_bar_rows=0`
    - `reports\phase2_readiness\ZC_2022_scope_20260624\ZC_2022_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=41642`, `synthetic_rows_pct=15.220307`, `max_synthetic_gap_minutes=48`, `degraded_bar_rows=0`
    - `reports\phase2_readiness\ZC_2023_scope_20260624\ZC_2023_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=58193`, `synthetic_rows_pct=21.419291`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
    - `reports\phase2_readiness\ZC_2024_scope_20260624\ZC_2024_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=75184`, `synthetic_rows_pct=27.458457`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
- ZC compact evidence matrix:
  - `ZC 2019`: `wrong_source_type`
  - `ZC 2020`: `wrong_source_type`
  - `ZC 2021`: `wrong_source_type`
  - `ZC 2022`: `wrong_source_type`
  - `ZC 2023`: `wrong_source_type`
  - `ZC 2024`: `wrong_source_type`
- No files or reports were generated during the read-only audit. No provider, build, promotion, WFA/model/feature/label, staging, or commit action was performed.

## Latest ZL 2019-2023 Read-Only Source/Readiness Audit Result

- Result: `zl_2019_2023_fail_closed_wrong_source_type_no_parent_source`
- Current local parent/explicit source evidence:
  - `data\dbn\ohlcv_1m_parent\ZL\2019` through `data\dbn\ohlcv_1m_parent\ZL\2023`: missing
  - `data\dbn\status_parent\status\ZL\2019` through `data\dbn\status_parent\status\ZL\2023`: missing
  - `data\dbn\statistics_parent\statistics\ZL\2019` through `data\dbn\statistics_parent\statistics\ZL\2023`: missing
  - `data\dbn\definition\ZL\2019` through `data\dbn\definition\ZL\2023`: present, manifest readable, schema `definition`, `stype_in=parent`, size/hash metadata matched
- Current local continuous source evidence:
  - `data\dbn\ohlcv_1m\ZL\2019` through `data\dbn\ohlcv_1m\ZL\2023`: present, manifest readable, schema `ohlcv-1m`, `stype_in=continuous`, size/hash metadata matched
  - `data\dbn\status\ZL\2019` through `data\dbn\status\ZL\2023`: present, manifest readable, schema `status`, `stype_in=continuous`, size/hash metadata matched
  - `data\dbn\statistics\ZL\2019` through `data\dbn\statistics\ZL\2023`: present, manifest readable, schema `statistics`, `stype_in=continuous`, size/hash metadata matched
- Current canonical raw source columns:
  - `data\raw\ZL\2019.parquet`: rows `197664`, source `data/dbn/ohlcv_1m/ZL/2019/2019-01-01_2020-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZL\2020.parquet`: rows `238335`, source `data/dbn/ohlcv_1m/ZL/2020/2020-01-01_2021-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZL\2021.parquet`: rows `237368`, source `data/dbn/ohlcv_1m/ZL/2021/2021-01-01_2022-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZL\2022.parquet`: rows `220438`, source `data/dbn/ohlcv_1m/ZL/2022/2022-01-01_2023-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZL\2023.parquet`: rows `219695`, source `data/dbn/ohlcv_1m/ZL/2023/2023-01-01_2024-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
- Current report/config evidence:
  - `configs\alpha_tiered.yaml` has no `accepted_readiness_exceptions` row for `ZL`.
  - `scripts\phase2_causal_base\build_causal_base_data.py` `PARENT_SPARSE_OHLCV_NO_TRADE_ALLOWED_MARKET_YEARS` does not include `ZL`.
  - Existing ZL decision packets remain `ACTION_REQUIRED` and fail-closed:
    - `reports\phase2_readiness\ZL_2019_scope_20260624\ZL_2019_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=75483`, `synthetic_rows_pct=27.63457`, `max_synthetic_gap_minutes=117`, `degraded_bar_rows=2886`
    - `reports\phase2_readiness\ZL_2020_scope_20260624\ZL_2020_decision_packet_20260624.json`: `decision=keep_fail_closed`, `synthetic_rows=36163`, `synthetic_rows_pct=13.174231`, `max_synthetic_gap_minutes=109`, `degraded_bar_rows=1756`
    - `reports\phase2_readiness\ZL_2021_scope_20260624\ZL_2021_decision_packet_20260624.json`: `decision=keep_fail_closed`, `synthetic_rows=38137`, `synthetic_rows_pct=13.84258`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
    - `reports\phase2_readiness\ZL_2022_scope_20260624\ZL_2022_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=53157`, `synthetic_rows_pct=19.429083`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
    - `reports\phase2_readiness\ZL_2023_scope_20260624\ZL_2023_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=51990`, `synthetic_rows_pct=19.136132`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
- ZL compact evidence matrix:
  - `ZL 2019`: `wrong_source_type`
  - `ZL 2020`: `wrong_source_type`
  - `ZL 2021`: `wrong_source_type`
  - `ZL 2022`: `wrong_source_type`
  - `ZL 2023`: `wrong_source_type`
- No files or reports were generated during the read-only audit. No provider, build, promotion, WFA/model/feature/label, staging, or commit action was performed.

## Latest ZM 2019-2024 Read-Only Source/Readiness Audit Result

- Result: `zm_2019_2024_fail_closed_wrong_source_type_no_parent_source`
- Current local parent/explicit source evidence:
  - `data\dbn\ohlcv_1m_parent\ZM\2019` through `data\dbn\ohlcv_1m_parent\ZM\2024`: missing
  - `data\dbn\status_parent\status\ZM\2019` through `data\dbn\status_parent\status\ZM\2024`: missing
  - `data\dbn\statistics_parent\statistics\ZM\2019` through `data\dbn\statistics_parent\statistics\ZM\2024`: missing
  - `data\dbn\definition\ZM\2019` through `data\dbn\definition\ZM\2024`: present, manifest readable, schema `definition`, `stype_in=parent`, size/hash metadata matched
- Current local continuous source evidence:
  - `data\dbn\ohlcv_1m\ZM\2019` through `data\dbn\ohlcv_1m\ZM\2024`: present, manifest readable, schema `ohlcv-1m`, `stype_in=continuous`, size/hash metadata matched
  - `data\dbn\status\ZM\2019` through `data\dbn\status\ZM\2024`: present, manifest readable, schema `status`, `stype_in=continuous`, size/hash metadata matched
  - `data\dbn\statistics\ZM\2019` through `data\dbn\statistics\ZM\2024`: present, manifest readable, schema `statistics`, `stype_in=continuous`, size/hash metadata matched
- Current canonical raw source columns:
  - `data\raw\ZM\2019.parquet`: rows `174022`, source `data/dbn/ohlcv_1m/ZM/2019/2019-01-01_2020-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZM\2020.parquet`: rows `196479`, source `data/dbn/ohlcv_1m/ZM/2020/2020-01-01_2021-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZM\2021.parquet`: rows `214610`, source `data/dbn/ohlcv_1m/ZM/2021/2021-01-01_2022-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZM\2022.parquet`: rows `205667`, source `data/dbn/ohlcv_1m/ZM/2022/2022-01-01_2023-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZM\2023.parquet`: rows `207959`, source `data/dbn/ohlcv_1m/ZM/2023/2023-01-01_2024-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
  - `data\raw\ZM\2024.parquet`: rows `209903`, source `data/dbn/ohlcv_1m/ZM/2024/2024-01-01_2025-01-01.dbn.zst`, status/statistics missing/stale rows all `0`
- Current report/config evidence:
  - `configs\alpha_tiered.yaml` has no `accepted_readiness_exceptions` row for `ZM`.
  - `scripts\phase2_causal_base\build_causal_base_data.py` `PARENT_SPARSE_OHLCV_NO_TRADE_ALLOWED_MARKET_YEARS` does not include `ZM`.
  - Existing ZM decision packets remain `ACTION_REQUIRED` and fail-closed:
    - `reports\phase2_readiness\ZM_2019_scope_20260624\ZM_2019_decision_packet_20260624.json`: `decision=record ZM 2019 fail-closed and move to the next eligible blocker`, `synthetic_rows=98800`, `synthetic_rows_pct=36.214088`, `max_synthetic_gap_minutes=114`, `degraded_bar_rows=2751`
    - `reports\phase2_readiness\ZM_2020_scope_20260624\ZM_2020_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=78201`, `synthetic_rows_pct=28.469856`, `max_synthetic_gap_minutes=109`, `degraded_bar_rows=1260`
    - `reports\phase2_readiness\ZM_2021_scope_20260624\ZM_2021_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=60895`, `synthetic_rows_pct=22.103047`, `max_synthetic_gap_minutes=47`, `degraded_bar_rows=0`
    - `reports\phase2_readiness\ZM_2022_scope_20260624\ZM_2022_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=67802`, `synthetic_rows_pct=24.793304`, `max_synthetic_gap_minutes=65`, `degraded_bar_rows=0`
    - `reports\phase2_readiness\ZM_2023_scope_20260624\ZM_2023_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=63726`, `synthetic_rows_pct=23.45584`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
    - `reports\phase2_readiness\ZM_2024_scope_20260624\ZM_2024_decision_packet_20260624.json`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=63907`, `synthetic_rows_pct=23.339907`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
- ZM compact evidence matrix:
  - `ZM 2019`: `wrong_source_type`
  - `ZM 2020`: `wrong_source_type`
  - `ZM 2021`: `wrong_source_type`
  - `ZM 2022`: `wrong_source_type`
  - `ZM 2023`: `wrong_source_type`
  - `ZM 2024`: `wrong_source_type`
- No files or reports were generated during the read-only audit. No provider, build, promotion, WFA/model/feature/label, staging, or commit action was performed.

## Latest ZS 2019-2024 Read-Only Source/Readiness Audit Result

- Result: `zs_2019_2024_partial_fail_closed_missing_decision_packets`
- Current local parent/explicit source evidence:
  - `data\dbn\ohlcv_1m_parent\ZS\2019` through `data\dbn\ohlcv_1m_parent\ZS\2024`: missing
  - `data\dbn\status_parent\status\ZS\2019` through `data\dbn\status_parent\status\ZS\2024`: missing
  - `data\dbn\statistics_parent\statistics\ZS\2019` through `data\dbn\statistics_parent\statistics\ZS\2024`: missing
  - `data\dbn\definition\ZS\2019` through `data\dbn\definition\ZS\2024`: present, manifest readable, schema `definition`, `stype_in=parent`
- Current local continuous source evidence:
  - `data\dbn\ohlcv_1m\ZS\2019` through `data\dbn\ohlcv_1m\ZS\2024`: present, manifest readable, schema `ohlcv-1m`, `stype_in=continuous`, size/hash metadata matched
  - `data\dbn\status\ZS\2019` through `data\dbn\status\ZS\2024`: present, manifest readable, schema `status`, `stype_in=continuous`, size/hash metadata matched
  - `data\dbn\statistics\ZS\2019` through `data\dbn\statistics\ZS\2024`: present, manifest readable, schema `statistics`, `stype_in=continuous`, size/hash metadata matched
- Current canonical raw source columns:
  - `data\raw\ZS\2019.parquet`: rows `211193`, sha256 `671ea02a47dcf04e5e704bb72cffdae0ca7a2bc8a184dbbb2c32e13991de42f4`, source `data/dbn/ohlcv_1m/ZS/2019/2019-01-01_2020-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `3063`
  - `data\raw\ZS\2020.parquet`: rows `234627`, sha256 `dd804d48561d081a23f688749f4257bd7937b9d8f576b3ca127fe5c374b6e6c5`, source `data/dbn/ohlcv_1m/ZS/2020/2020-01-01_2021-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `1746`
  - `data\raw\ZS\2021.parquet`: rows `245785`, sha256 `794f429a950dde451468495d47ff95862d6845ecafc3aeb15b65e1ea716d37b5`, source `data/dbn/ohlcv_1m/ZS/2021/2021-01-01_2022-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `0`
  - `data\raw\ZS\2022.parquet`: rows `243037`, sha256 `abb8f21867bdc9301fb6c6b36732b71f840e95ea3c330422abf4699969c896ef`, source `data/dbn/ohlcv_1m/ZS/2022/2022-01-01_2023-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `0`
  - `data\raw\ZS\2023.parquet`: rows `238574`, sha256 `d355e716af72e345a6fe57949c7c46873629c7fb387a41d314a48b07b51310dd`, source `data/dbn/ohlcv_1m/ZS/2023/2023-01-01_2024-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `0`
  - `data\raw\ZS\2024.parquet`: rows `234475`, sha256 `4dec7baff8b6aacbada095fd91cb771982c8a9a8f88d6eebba39ae08e060edad`, source `data/dbn/ohlcv_1m/ZS/2024/2024-01-01_2025-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `0`
- Current report/config evidence:
  - `configs\alpha_tiered.yaml` has no `accepted_readiness_exceptions` row for `ZS`.
  - `scripts\phase2_causal_base\build_causal_base_data.py` `PARENT_SPARSE_OHLCV_NO_TRADE_ALLOWED_MARKET_YEARS` does not include `ZS`.
  - Existing decision packets are fail-closed for `ZS 2019`, `ZS 2020`, `ZS 2023`, and `ZS 2024`.
  - `ZS 2019`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=62144`, `synthetic_rows_pct=22.735305`, `max_synthetic_gap_minutes=89`, `degraded_bar_rows=3063`
  - `ZS 2020`: `decision=keep_fail_closed`, `synthetic_rows=39997`, `synthetic_rows_pct=14.564277`, `max_synthetic_gap_minutes=99`, `degraded_bar_rows=1746`
  - `ZS 2023`: `decision_policy_result.decision=keep_fail_closed`, `synthetic_rows=33111`, `synthetic_rows_pct=12.187276`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
  - `ZS 2024`: `decision=keep_fail_closed`, `synthetic_rows=39335`, `synthetic_rows_pct=14.365801`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
  - No decision packet exists for `ZS 2021` or `ZS 2022`.
  - Current JSONL WARN evidence exists for `ZS 2021` and `ZS 2022` in `reports\phase2_readiness\tier3_research_after_status_sparse_exceptions_20260624.jsonl` and `reports\phase2_readiness\tier3_research_after_phase1b_rebuild_20260624_bounded10.jsonl`.
  - `ZS 2021`: `status=WARN`, warnings `roll maturity sequence not monotonic: backsteps=1` and `synthetic threshold breached: rows_pct=10.787787 max_gap_minutes=46`, `synthetic_rows=29721`, `degraded_bar_rows=0`, status/statistics missing/stale rows all `0`
  - `ZS 2022`: `status=WARN`, warning `synthetic threshold breached: rows_pct=11.169064 max_gap_minutes=46`, `synthetic_rows=30558`, `degraded_bar_rows=0`, status/statistics missing/stale rows all `0`
- ZS compact evidence matrix:
  - `ZS 2019`: `wrong_source_type` with fail-closed decision packet
  - `ZS 2020`: `wrong_source_type` with fail-closed decision packet
  - `ZS 2021`: `stale_or_ambiguous`; parent source missing and no decision packet
  - `ZS 2022`: `stale_or_ambiguous`; parent source missing and no decision packet
  - `ZS 2023`: `wrong_source_type` with fail-closed decision packet
  - `ZS 2024`: `wrong_source_type` with fail-closed decision packet
- Current script discovery found no exact supported decision-packet generator. Existing supported CLIs cover repair work orders, blocker summaries, and drilldowns:
  - `python -m scripts.validation.build_phase2_repair_work_order --help`
  - `python -m scripts.validation.diagnose_phase2_readiness_blockers --help`
  - `python -m scripts.validation.drilldown_phase2_readiness_blockers --help`
  - `python -m scripts.validation.summarize_phase2_readiness_blockers --help`
- No files or reports were generated during the read-only audit. No provider, build, promotion, WFA/model/feature/label, staging, or commit action was performed.

## Latest ZS 2021-2022 Fail-Closed Decision Packet Result

- Added focused tracked tooling:
  - `scripts\validation\build_phase2_decision_packets.py`
  - `tests\validation\test_build_phase2_decision_packets.py`
- Focused test command passed:
  - `python -m pytest tests\validation\test_build_phase2_decision_packets.py`
  - `4 passed`
- Generated only approved packet artifacts:
  - `reports\phase2_readiness\ZS_2021_scope_20260626\ZS_2021_decision_packet_20260626.json`
  - `reports\phase2_readiness\ZS_2021_scope_20260626\ZS_2021_decision_packet_20260626.md`
  - `reports\phase2_readiness\ZS_2022_scope_20260626\ZS_2022_decision_packet_20260626.json`
  - `reports\phase2_readiness\ZS_2022_scope_20260626\ZS_2022_decision_packet_20260626.md`
- Verification:
  - `ZS 2021`: `status=ACTION_REQUIRED`, `decision_status=BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED`, `decision=keep_fail_closed`, `accepted_readiness_exception_added=false`, `diagnostic_use_approved=false`, `thresholds_loosened=false`, `provider_command_approved=false`, `source_repair_approved=false`, `canonical_raw_overwrite_approved=false`, `canonical_phase2_rebuild_approved=false`
  - `ZS 2021`: `synthetic_rows=29721`, `synthetic_rows_pct=10.787787`, `max_synthetic_gap_minutes=46`, `roll_maturity_backstep_count=1`, `degraded_bar_rows=0`, status/statistics missing/stale rows all `0`
  - `ZS 2021`: canonical raw row count `245785`, sha256 `794f429a950dde451468495d47ff95862d6845ecafc3aeb15b65e1ea716d37b5`, raw source `data/dbn/ohlcv_1m/ZS/2021/2021-01-01_2022-01-01.dbn.zst`
  - `ZS 2022`: `status=ACTION_REQUIRED`, `decision_status=BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED`, `decision=keep_fail_closed`, `accepted_readiness_exception_added=false`, `diagnostic_use_approved=false`, `thresholds_loosened=false`, `provider_command_approved=false`, `source_repair_approved=false`, `canonical_raw_overwrite_approved=false`, `canonical_phase2_rebuild_approved=false`
  - `ZS 2022`: `synthetic_rows=30558`, `synthetic_rows_pct=11.169064`, `max_synthetic_gap_minutes=46`, `roll_maturity_backstep_count=0`, `degraded_bar_rows=0`, status/statistics missing/stale rows all `0`
  - `ZS 2022`: canonical raw row count `243037`, sha256 `abb8f21867bdc9301fb6c6b36732b71f840e95ea3c330422abf4699969c896ef`, raw source `data/dbn/ohlcv_1m/ZS/2022/2022-01-01_2023-01-01.dbn.zst`
- No data/raw, DBN source, canonical Phase 2, provider, live/paper, WFA/model/feature/label, staging, or commit action was performed.

## Latest ZW 2019/2020/2022/2023/2024 Read-Only Source/Readiness Audit Result

- Result: `zw_2019_2020_2022_2023_2024_fail_closed_wrong_source_type_no_parent_source`
- Current local parent/explicit source evidence:
  - `data\dbn\ohlcv_1m_parent\ZW\2019`, `2020`, `2022`, `2023`, `2024`: missing
  - `data\dbn\status_parent\status\ZW\2019`, `2020`, `2022`, `2023`, `2024`: missing
  - `data\dbn\statistics_parent\statistics\ZW\2019`, `2020`, `2022`, `2023`, `2024`: missing
  - `data\dbn\definition\ZW\2019`, `2020`, `2022`, `2023`, `2024`: present, manifest readable, schema `definition`, `stype_in=parent`
- Current local continuous source evidence:
  - `data\dbn\ohlcv_1m\ZW\2019`, `2020`, `2022`, `2023`, `2024`: present, manifest readable, schema `ohlcv-1m`, `stype_in=continuous`, size/hash metadata matched
  - `data\dbn\status\ZW\2019`, `2020`, `2022`, `2023`, `2024`: present, manifest readable, schema `status`, `stype_in=continuous`, size/hash metadata matched
  - `data\dbn\statistics\ZW\2019`, `2020`, `2022`, `2023`, `2024`: present, manifest readable, schema `statistics`, `stype_in=continuous`, size/hash metadata matched
- Current canonical raw source columns:
  - `data\raw\ZW\2019.parquet`: rows `192334`, sha256 `fccbe9d1fe3e0ffa40c0417f700548f4e24f044fb61d0c2388dd33305bd7afb2`, source `data/dbn/ohlcv_1m/ZW/2019/2019-01-01_2020-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `3166`
  - `data\raw\ZW\2020.parquet`: rows `212535`, sha256 `71d2a3d5597400096c05c328909feaf84cda150717006d4a851e266f40458adc`, source `data/dbn/ohlcv_1m/ZW/2020/2020-01-01_2021-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `2152`
  - `data\raw\ZW\2022.parquet`: rows `212406`, sha256 `a2619771660483182f23d0fa529ce2a71a0b028ed6581dccaf27dd924698ed84`, source `data/dbn/ohlcv_1m/ZW/2022/2022-01-01_2023-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `0`
  - `data\raw\ZW\2023.parquet`: rows `205147`, sha256 `1780ef9d573613f381f0e30bc204ecde9fdc238fb15828f77286605562a2674a`, source `data/dbn/ohlcv_1m/ZW/2023/2023-01-01_2024-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `0`
  - `data\raw\ZW\2024.parquet`: rows `205094`, sha256 `157c85bc0cd87f30c7f11d227ade4ad9c578e42b1944b5412762f0778adf4aff`, source `data/dbn/ohlcv_1m/ZW/2024/2024-01-01_2025-01-01.dbn.zst`, status/statistics missing/stale rows all `0`, degraded rows `0`
- Existing ZW decision packets are `ACTION_REQUIRED` and fail-closed:
  - `ZW 2019`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=81236`, `synthetic_rows_pct=29.694776`, `max_synthetic_gap_minutes=53`, `degraded_bar_rows=3166`
  - `ZW 2020`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=62491`, `synthetic_rows_pct=22.721852`, `max_synthetic_gap_minutes=98`, `degraded_bar_rows=2152`
  - `ZW 2022`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=61187`, `synthetic_rows_pct=22.364242`, `max_synthetic_gap_minutes=118`, `degraded_bar_rows=0`
  - `ZW 2023`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=66536`, `synthetic_rows_pct=24.490307`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
  - `ZW 2024`: `decision=keep_fail_closed_move_to_next_eligible_blocker`, `synthetic_rows=68716`, `synthetic_rows_pct=25.096235`, `max_synthetic_gap_minutes=46`, `degraded_bar_rows=0`
- ZW compact evidence matrix:
  - `ZW 2019`: `wrong_source_type` with fail-closed decision packet
  - `ZW 2020`: `wrong_source_type` with fail-closed decision packet
  - `ZW 2022`: `wrong_source_type` with fail-closed decision packet
  - `ZW 2023`: `wrong_source_type` with fail-closed decision packet
  - `ZW 2024`: `wrong_source_type` with fail-closed decision packet
- No files or reports were generated during the ZW read-only audit. No provider, build, promotion, WFA/model/feature/label, staging, or commit action was performed.

## Latest Global Phase 1-2 Completion Reconciliation Result

- Result: `complete_for_current_approved_scope`
- Command shape: read-only Python reconciliation to stdout, plus `git status --short`.
- Verified campaign rows:
  - `canonical_phase2_pass`: 11 rows (`SR1 2020`, `SR3 2020`, `KE 2019`, `KE 2021`, `KE 2023`, `KE 2024`, `HE 2016`, `HE 2019`, `HE 2020`, `LE 2016`, `LE 2020`)
  - `fail_closed_with_decision_packet`: 28 rows (`ZC 2019-2024`, `ZL 2019-2023`, `ZM 2019-2024`, `ZS 2019-2024`, `ZW 2019`, `ZW 2020`, `ZW 2022`, `ZW 2023`, `ZW 2024`)
  - `unresolved`: 0 rows
- PASS rows were verified against current `causal_base_manifest.json` reports and current canonical `data\causally_gated_normalized` hashes.
- Fail-closed rows were verified against current decision packet JSON or Markdown and current raw/source posture. Seven rows used Markdown fallback because their JSON packet files are unreadable/empty: `ZC 2021`, `ZC 2022`, `ZL 2020`, `ZL 2021`, `ZS 2020`, `ZS 2023`, `ZS 2024`.
- Current `git status --short` remains dirty in pre-existing tracked/untracked files. No staging or commit was performed.

## Latest Report-Only Master Data Health Refresh Result

- Result: `complete_report_only_master_data_health_refresh`.
- Stuck-command resolution: repeated `apply_patch` and Python launches were blocked by the Windows sandbox helper before project code ran. The stale Codex PowerShell AST helper was stopped, then bounded local-only commands were used; sandbox pre-launch failures were rerun with scoped approval. No provider/network command was run.
- Added report-only refresh tooling:
  - `scripts\validation\refresh_master_data_health_matrix.py`
  - `tests\validation\test_refresh_master_data_health_matrix.py`
- Focused test passed:
  - `python -m pytest tests\validation\test_refresh_master_data_health_matrix.py`
  - result: `3 passed`
- Regenerated report-only outputs:
  - `reports\data_manifest\master_data_health_matrix.json`
  - `reports\data_manifest\master_data_health_summary.md`
- Current refreshed outline:
  - expected rows: `527`
  - `OK_SOURCE_PRESENT`: `45`
  - `POLICY_REVIEW_REQUIRED`: `473`
  - `EXCLUDED_FROM_PHASE2`: `9`
  - `UNKNOWN_REVIEW_REQUIRED`: `0`
  - raw parquet: `527/527`
  - OHLCV DBN: `527/527`
  - definition DBN: `527/527`
  - statistics DBN: `527/527`
  - status DBN: `460/527`, missing `67`
  - current canonical causal parquet: `107/527`, missing `420`
  - approved PASS rows: `11/11` present in current canonical causal parquet
  - fail-closed rows with decision packet: `28`
  - unresolved rows: `0`
- Stale/conflicting evidence now called out in the summary:
  - prior matrix generated at `2026-06-23T02:42:17Z` reported causal parquet `461/527`
  - current canonical filesystem evidence reports causal parquet `107/527`, correction `-354`
  - row-level matrix status DBN evidence remains `460/527`, while current raw optional audit status-archive evidence reports `status_archive_market_year_count=529` and `missing_status_archive_market_year_count=0`; these are preserved as separate evidence scopes.
- Safety: no data/raw, DBN source, data/causally_gated_normalized, provider state, live/paper path, WFA/model/features/labels, staging, or commit action was performed.

## Commands Run In Latest Report Refresh Run

- `Get-Location`
- `git status --short`
- `Get-Content reports\data_manifest\master_data_health_summary.md -TotalCount 140`
- `python -m pytest tests\validation\test_refresh_master_data_health_matrix.py`
- `python -m scripts.validation.refresh_master_data_health_matrix --repo-root .`
- `git diff -- reports/data_manifest/master_data_health_summary.md`
- Local-only Python writer commands for the requested script/test and handoff update, used because `apply_patch` repeatedly hung.

## Files Changed In Latest Report Refresh Run

- `CODEX_HANDOFF.md`
- `scripts\validation\refresh_master_data_health_matrix.py`
- `tests\validation\test_refresh_master_data_health_matrix.py`
- `reports\data_manifest\master_data_health_matrix.json`
- `reports\data_manifest\master_data_health_summary.md`

## Remaining Blockers

- No unresolved rows remain from the known LE-like synthetic-blocker list for the current approved scope.
- Worktree remains dirty in pre-existing tracked/untracked files and approved data-readiness code/config/test changes. This is now the remaining Phase 1-2 completion blocker.
- Do not proceed to WFA/model/features/labels until the intended modeling scope is backed by current source/raw/alignment/causal evidence or explicit fail-closed exclusions.

## Commands Run In Latest Run

- `Get-Location`
- `git status --short`
- `Get-Content -Raw CODEX_HANDOFF.md`
- `rg -n "ZS|ZS\.v\.0|parent_sparse_ohlcv_no_trade|accepted_readiness_exception|accepted_readiness_exceptions|source_audit|canonical_raw_alignment|decision_packet" configs scripts tests reports\phase2_readiness reports\raw_ingest reports\raw_readiness reports\data_manifest -S`
- `Get-ChildItem -Recurse -File data\dbn\ohlcv_1m_parent\ZS,data\dbn\status_parent\status\ZS,data\dbn\statistics_parent\statistics\ZS,data\dbn\definition\ZS,data\dbn\ohlcv_1m\ZS,data\dbn\status\ZS,data\dbn\statistics\ZS -ErrorAction SilentlyContinue`
- `Get-ChildItem -Recurse -File reports\phase2_readiness -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'ZS_20(19|20|21|22|23|24)|zs_20(19|20|21|22|23|24)|ZS|zs' }`
- Parsed ZS 2019-2024 DBN manifests, source type, schema, file size, and hash/size metadata matches.
- Parsed ZS 2019-2024 canonical raw source columns, row counts, source files, status/statistics missing/stale counts, degraded rows, market values, and year values.
- Parsed ZS 2019, ZS 2020, ZS 2023, and ZS 2024 decision packets under `reports\phase2_readiness\ZS_*_scope_20260624`.
- Parsed ZS 2021 and ZS 2022 WARN rows from `reports\phase2_readiness\tier3_research_after_status_sparse_exceptions_20260624.jsonl` and `reports\phase2_readiness\tier3_research_after_phase1b_rebuild_20260624_bounded10.jsonl`.
- `rg -n "decision_packet|decision packet|ACTION_REQUIRED|keep_fail_closed|phase2.*decision|BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED|repair_work_order|decision_policy_result|policy_decision" scripts tests docs CODEX_HANDOFF.md -S`
- `rg --files scripts tests docs | rg "decision|packet|phase2|readiness|blocker|repair"`
- `python -m scripts.validation.build_phase2_repair_work_order --help`
- `python -m scripts.validation.diagnose_phase2_readiness_blockers --help`
- `python -m scripts.validation.drilldown_phase2_readiness_blockers --help`
- `python -m scripts.validation.summarize_phase2_readiness_blockers --help`
- Added `scripts\validation\build_phase2_decision_packets.py`.
- Added `tests\validation\test_build_phase2_decision_packets.py`.
- `python -m pytest tests\validation\test_build_phase2_decision_packets.py`
- `Test-Path -LiteralPath reports\phase2_readiness\ZS_2021_scope_20260626`
- `Test-Path -LiteralPath reports\phase2_readiness\ZS_2022_scope_20260626`
- `python -m scripts.validation.build_phase2_decision_packets --checkpoint-jsonl reports\phase2_readiness\tier3_research_after_status_sparse_exceptions_20260624.jsonl --raw-root data\raw --reports-root reports\phase2_readiness --markets ZS --years 2021 2022 --date-tag 20260626`
- Parsed and verified generated ZS 2021/2022 decision packet JSON fields.
- Parsed ZW 2019/2020/2022/2023/2024 DBN manifests, source type, schema, file size, and hash/size metadata matches.
- Parsed ZW 2019/2020/2022/2023/2024 canonical raw source columns, row counts, source files, status/statistics missing/stale counts, degraded rows, market values, and year values.
- Parsed ZW 2019/2020/2022/2023/2024 decision packets under `reports\phase2_readiness\ZW_*_scope_20260624`.
- Read-only global reconciliation verified 11 `canonical_phase2_pass` rows, 28 `fail_closed_with_decision_packet` rows, and 0 unresolved rows.
- `git status --short`

## Files Changed In Latest Run

- `CODEX_HANDOFF.md`
- `scripts\validation\build_phase2_decision_packets.py`
- `tests\validation\test_build_phase2_decision_packets.py`
- `reports\phase2_readiness\ZS_2021_scope_20260626\ZS_2021_decision_packet_20260626.json`
- `reports\phase2_readiness\ZS_2021_scope_20260626\ZS_2021_decision_packet_20260626.md`
- `reports\phase2_readiness\ZS_2022_scope_20260626\ZS_2022_decision_packet_20260626.json`
- `reports\phase2_readiness\ZS_2022_scope_20260626\ZS_2022_decision_packet_20260626.md`

## Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: decide and implement the disposition of remaining data/causally_gated_normalized cleanup blockers in protected manifest/audit-policy references only.
Rules:
- Do not run dry-run cleanup or actual cleanup.
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Do not run WFA/modeling/metrics, generate predictions/model artifacts, or claim production/live readiness.
- Do not touch raw-root defaults or data/raw cleanup blockers in this scope.
- Do not stage generated reports or ignored artifacts.
Task:
- Establish state with Get-Location and git status --short.
- Read CODEX_HANDOFF.md, then inspect only configs/data_manifest.yaml, scripts/audit_databento_phase0.py, scripts/audit_databento_phase4.py, scripts/audit_databento_phase5.py, and their focused tests.
- Decide whether each data/causally_gated_normalized reference is an active protected policy reference that must remain a blocker, or a stale/default claim that can be safely changed to fail closed or point to explicit rebuilt evidence.
- If a safe one-batch edit exists, implement only that batch and run its focused tests plus targeted rg; otherwise update the final blocker report/handoff without code changes.
Stop when:
- data/causally_gated_normalized is either fully retired from active manifest/audit-policy references, or the remaining protected references are documented as final blockers with cleanup_eligible_now=false and dry_run_cleanup_safe_next=false.
```
# Final Cleanup Blocker State - 2026-06-28

Authoritative current state for the next run. Older historical sections below are retained as evidence, but this section supersedes them.

## Current status

- Latest reviewed commit: `ebc283e Retire stale causal audit references`.
- Worktree before final documentation: clean (`git status --short` returned no rows).
- Documentation scope only: no code, config, script, test, or `data/**` changes.
- Cleanup remains blocked.
- Dry-run cleanup remains unsafe.
- Actual cleanup remains unsafe.
- Do not run cleanup.
- Do not run dry-run cleanup.
- Do not delete, move, rename, archive, quarantine, or mutate `data/**`.
- Do not touch raw paths without a separate human-approved raw-specific decision.

## Active blockers remaining

- `data/causally_gated_normalized`: active protected blocker. Current evidence still includes protected manifest/audit-policy references in `configs/data_manifest.yaml` and `scripts/audit_databento_phase5.py`. This remains protected/active until a separate human decision or broader policy change.
- `data/raw`: active blocker. Current evidence still includes runtime/config raw source references.
- `data/raw/_repair_candidates`: active blocker. Current evidence still includes raw repair-candidate config/report references.

## Candidate future quarantine plan only

- `data/feature_matrices/baseline`: no active blocker; candidate future quarantine plan only.
- `data/dbn_sr_parent_candidate`: candidate future quarantine plan only.
- `data/predictions`: candidate future quarantine plan only.

## Unsafe to touch

- `data/raw/ES`
- `data/raw/RTY`
- `data/raw/ZS`

## Protected keep paths

- `data/dbn`
- `data/causal_base_candidates/tier1_rebuild_v1`
- `data/labeled/tier1_rebuild_v1`
- `data/feature_matrices/baseline_tier1_rebuild_v1`
- `reports/data_audit/**`

## Cleanup gate

- cleanup_eligible_now: `false`
- dry_run_cleanup_safe_next: `false`
- actual_cleanup_safe_now: `false`
- dry-run approval plan available: `no`
- actual cleanup safe now: `no`

## Final documentation written

- `reports/data_audit/final/final_cleanup_blockers.md`
- `reports/data_audit/final/final_cleanup_blockers.json`

## Next safe options

1. Pause cleanup work.
2. Run Phase 8 gross/net research metrics using a report-scoped prediction artifact only.
3. Separately review policy decision for `data/causally_gated_normalized` and raw blockers.

Forbidden next actions without explicit later approval: cleanup, dry-run cleanup, deletion, archive/quarantine execution, raw path retirement, WFA/modeling/metrics, prediction generation, and model artifact writes.
