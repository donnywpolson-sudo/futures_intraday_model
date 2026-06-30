# Codex Handoff

## Phase 2 Candidate Audit Readiness Verified - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: implement the plan to resolve dirty worktree and Phase 2 causal coverage blockers.
- Current status: blocker resolution complete for audit-baseline purposes.
- Docs-only baseline commit:
  - `d5d9583 Document audit readiness baseline`
  - Staged/committed only:
    - `CODEX_HANDOFF.md`
    - `PIPELINE.md`
    - `README_RUNBOOK.md`
    - `docs\audit_readiness_packet.md`
  - Pre-commit staged check showed no data, reports, configs, scripts, or tests staged.
- Phase 2 candidate verification:
  - Candidate output root exists: `data\causal_base_candidates\broad_manifest_527_rebuild_v1`.
  - Paired reports root exists: `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1`.
  - Parquet count: `460`.
  - `causal_base_manifest.json` status: `PASS`.
  - `causal_base_validation.json` status: `PASS`.
  - Manifest output count: `460`.
  - Forbidden `6M\2012.parquet`: absent.
  - Forbidden `2025.parquet` count: `0`.
  - Forbidden `2026.parquet` count: `0`.
  - Scoped status check for `data\causal_base_candidates\broad_manifest_527_rebuild_v1`, paired reports, `data\raw`, `data\dbn`, and `configs\data_manifest.yaml` returned no tracked changes.
- Audit readiness packet update:
  - `docs\audit_readiness_packet.md` now records `CONDITIONAL_GO_RAW_SOURCE_AND_PHASE2_CANDIDATE_460_ONLY`.
  - Raw/source formal audit is go from committed documentation baseline.
  - Phase 2 candidate formal audit is conditional go for exactly the 460 built-not-promoted research rows.
  - Promoted/canonical Phase 2 formal audit remains no-go.
- Validation:
  - `git diff --cached --name-only` before baseline commit showed only the four docs/handoff files.
  - `git diff --cached --check` before baseline commit passed.
  - Candidate evidence PowerShell parse returned count/status/exclusion checks above.
  - `python -m pytest tests/validation/test_build_broad_manifest_527_rebuild.py tests/validation/test_alpha_tier_ladder_policy.py -q` -> `12 passed`.
- Safety:
  - No provider/network call, data mutation, raw/DBN rebuild, Phase 2 build, cleanup, staging outside docs/handoff, modeling, WFA, metrics, predictions, promotion, config promotion, or live/paper action was performed.
  - Existing generated candidate data and reports were read only.
- Remaining blockers:
  - Medium: worktree still contains unrelated pre-existing/user changes outside the committed/docs audit baseline.
  - Medium: promoted/canonical Phase 2 remains no-go until a separate config/canonical promotion gate reconciles `configs\data_manifest.yaml` and current canonical coverage.
  - Medium: 2025/2026 remain holdout/forward evidence only, and `6M:2012` remains fail-closed/excluded.

### Exact Next Recommended Step

Start the formal audit only with scope `raw/source plus broad_manifest_527_rebuild_v1 candidate 460`; do not include promoted/canonical Phase 2, modeling, WFA, metrics, predictions, promotion, cleanup, or live/paper execution.

## Audit Readiness Baseline Stabilized - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: implement the plan to stabilize the repo baseline, restore/replace missing tracked docs, define audit scope, create an authoritative audit readiness packet, and rerun narrow readiness checks.
- Current status: docs-only baseline stabilization complete; formal audit scope is raw/source only.
- Scope completed:
  - Restored deleted tracked docs from `HEAD`:
    - `PIPELINE.md`
    - `README_RUNBOOK.md`
    - `DATA REBUILD.md`
    - `RESOURCES.md`
    - `docs\ARTIFACT_AND_BACKUP_POLICY.md`
    - `docs\audit_databento_runner.md`
    - `docs\audit_prompt_meta_audit.md`
    - `docs\live_trading_readiness.md`
    - `docs\phase1b_manifest_reconciliation.md`
    - `docs\visual_reports.md`
  - Added `docs\audit_readiness_packet.md`.
  - Added pointers to the packet in `PIPELINE.md` and `README_RUNBOOK.md`.
- Audit scope now documented:
  - `CONDITIONAL_GO_RAW_SOURCE_ONLY`.
  - In scope: `data\dbn`, `data\raw`, DBN sidecar manifests, source hashes, raw schema/value checks, optional status/statistics raw enrichment posture, and raw/source lineage reports.
  - Out of scope: raw plus causal Phase 2, labels, features, predictions, models, WFA, metrics, promotion, cleanup, and live/paper execution.
- Evidence captured in the packet:
  - Current master data health summary reports `raw_parquet_present=527/527`, `ohlcv_1m_dbn_present=527/527`, `definition_dbn_present=527/527`, and `causal_parquet_present=8/527`.
  - Current raw DBN alignment report is `PASS`, with raw schema/value failures `0`, source hash mismatches `0`, and definition join mismatches `0`.
  - Current enriched raw optional schema audit is `PASS`, with files `530`, rows `130086009`, duplicate key rows `0`, source hash mismatches `0`, and alpha input readiness `LIMITED_RESEARCH_INPUT_ONLY`.
- Validation:
  - `Test-Path PIPELINE.md` -> `True`.
  - `Test-Path docs` -> `True`.
  - `rg -n "audit_readiness_packet|PIPELINE.md|raw/source|Phase 2" README.md PIPELINE.md README_RUNBOOK.md docs` found the new packet and doc pointers.
  - `git diff --check` -> no whitespace errors; Git emitted line-ending warnings only.
  - `python -m pytest tests/validation/test_refresh_master_data_health_matrix.py tests/validation/test_audit_raw_dbn_alignment.py -q` -> `31 passed`.
  - `git status --short -- data reports` showed only pre-existing tracked report modifications under `reports\data_manifest`; no `data/**` changes.
- Safety:
  - No provider/network call, data mutation, raw/DBN rebuild, Phase 2 build, cleanup, staging, commit, modeling, WFA, metrics, predictions, promotion, or live/paper action was performed.
  - Generated reports were not intentionally refreshed.
- Unresolved blockers:
  - Medium: worktree remains dirty with pre-existing/user changes outside this docs-only scope.
  - Medium: raw/source formal audit readiness remains conditional until the docs-only baseline is accepted or committed.
  - Medium: raw plus causal Phase 2 formal audit remains no-go because current canonical causal coverage is incomplete and stale/conflicting generated evidence remains documented.

### Exact Next Recommended Step

Human decision: accept the docs-only raw/source audit-readiness baseline as local-only, explicitly commit it as documentation-only scope, or request a scope revision before starting a formal raw/source audit.

## Holdout Forward Evidence Complete - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: implement the separate 2025/2026 holdout-forward evidence plan.
- Current status: report-only evidence gate complete and verified `PASS`.
- Scope completed:
  - Added `scripts\validation\build_holdout_forward_evidence.py`.
  - Added `tests\validation\test_build_holdout_forward_evidence.py`.
  - Generated report-only artifacts:
    - `reports\data_audit\holdout_forward_evidence\broad_manifest_527_rebuild_v1\holdout_forward_evidence.json`
    - `reports\data_audit\holdout_forward_evidence\broad_manifest_527_rebuild_v1\holdout_forward_evidence.md`
- Evidence result:
  - Checked rows: `66`.
  - 2025 locked holdout candidates: `33`.
  - 2026 forward candidates: `33`.
  - Blocked rows: `0`.
  - Not-checked rows: `0`.
  - 2026 partial/current-year caveat rows: `33`.
  - `build_approved`, `research_use_allowed`, `modeling_approved`, `wfa_approved`, `metrics_approved`, `predictions_approved`, `promotion_approved`, and `config_promotion_approved` all remain `false`.
- Verification:
  - `python -m pytest tests\validation\test_build_holdout_forward_evidence.py tests\validation\test_alpha_tier_ladder_policy.py -q` -> `11 passed`.
  - `python -m scripts.validation.build_holdout_forward_evidence` -> `status=PASS holdout=33 forward=33 blocked=0 not_checked=0`.
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py tests\test_profile_scope.py -q` -> `150 passed`.
  - No `2025.parquet` or `2026.parquet` outputs exist under `data\causal_base_candidates\broad_manifest_527_rebuild_v1`.
  - Scoped `git status --short -- data\raw data\dbn configs\data_manifest.yaml data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned no tracked changes.
  - Scoped `git status --short -- reports\data_audit\holdout_forward_evidence\broad_manifest_527_rebuild_v1` returned no tracked changes.
- Safety:
  - No provider/network call, raw/dbn/config mutation, parquet candidate write, broad rebuild, cleanup, staging, commit, promotion, modeling, WFA, metrics, predictions, feature matrix generation, or research-use action was performed.
  - The 2025/2026 rows remain evidence-only holdout/forward candidates and are not approved for tuning, model selection, research/training rows, promotion, or broader use.
- Unresolved blockers:
  - None for this evidence gate.

### Exact Next Recommended Step

None.

## 6M 2012 Fail-Closed Resolution Complete - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: resolve `6M:2012`.
- Current status: resolved fail-closed with exact token `KEEP_6M_2012_FAIL_CLOSED_NO_BUILD`.
- Resolution evidence:
  - Diagnosis status: `PASS`.
  - Disposition call: `vendor_continuous_roll_backstep_policy_mismatch`.
  - Computed/readiness roll-maturity backsteps: `1`, matches readiness.
  - Selected disposition packet status: `RESOLVED_6M_2012_FAIL_CLOSED_NO_BUILD`.
  - Build execution, broader modeling, config promotion, and research-use flags all remain `false`.
- Generated report-only artifacts:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_roll_maturity_resolution_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_roll_maturity_resolution_diagnosis.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2012_roll_maturity_resolved_fail_closed.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2012_roll_maturity_resolved_fail_closed.md`
- Code/test changes in this scope:
  - `scripts\validation\diagnose_roll_maturity_blocker.py`: added selected-disposition validation and fail-closed resolved packet status.
  - `tests\validation\test_diagnose_roll_maturity_blocker.py`: added fail-closed and invalid-token coverage.
- Verification:
  - `python -m pytest tests\validation\test_diagnose_roll_maturity_blocker.py -q` -> `7 passed`.
  - 460 candidate parquet outputs remain present.
  - Manifest status `PASS`; validation status `PASS`; manifest outputs `460`.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1\6M\2012.parquet` remains absent.
  - No `2025.parquet` or `2026.parquet` outputs exist under the candidate root.
  - Scoped `git status --short -- data\raw data\dbn configs\data_manifest.yaml data\causal_base_candidates\broad_manifest_527_rebuild_v1 reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628` returned no tracked changes.
- Safety:
  - No provider/network call, raw/dbn/config mutation, broad rebuild, `6M:2012` candidate build, cleanup, staging, commit, promotion, modeling, WFA, metrics, predictions, feature matrix generation, or research-use action was performed.
  - `6M:2012` remains excluded from built candidates; this is a disposition resolution, not an inclusion or repair.
- Unresolved blockers:
  - Medium: 2025/2026 remain locked holdout/forward candidates only, not research/training rows.
  - Medium: worktree remains dirty with pre-existing/user changes outside this scope.

### Exact Next Recommended Step

None.

## Broad Manifest 527 Rebuild 460 Complete - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: implement the 460-row broad causal candidate rebuild for `broad_manifest_527_rebuild_v1`, with a local-only stuck/loop checker and no cross-project process touching.
- Current status: build complete and verified; outputs are generated candidates only, built-not-promoted, and not approved for modeling, WFA, metrics, predictions, promotion, or research-use.
- Scope completed:
  - Added bounded runner: `scripts\validation\build_broad_manifest_527_rebuild.py`.
  - Added focused tests: `tests\validation\test_build_broad_manifest_527_rebuild.py`.
  - Added local-only helper wrappers used for restart/checker hardening:
    - `scripts\validation\run_broad_manifest_527_step_loop.py`
    - `scripts\validation\run_broad_manifest_527_step_loop.ps1`
    - `scripts\validation\monitor_broad_manifest_527_rebuild.py`
  - Built exactly the approved 460 rows from the final include/readiness artifacts, excluding `6M:2012`, 2025, and 2026.
- Local-only process safety:
  - Runner/helper paths are repo-relative and guarded to run only from `C:\Users\donny\Desktop\futures_intraday_model`.
  - Live process command-line inspection found no active broad loop touching another project; unrelated processes were left untouched.
  - Direct batch mode was used after wrapper instability; it processes bounded chunks of at most 25 rows and emits `direct_batch_checker` progress lines.
- Generated artifacts:
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1\**\*.parquet`
  - `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\causal_base_manifest.json`
  - `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\causal_base_validation.json`
  - `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\causal_base_validation.csv`
  - `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\build_progress.jsonl`
  - `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\build_result_payloads.jsonl`
- Final validation evidence:
  - Build command class used: `python -m scripts.validation.build_broad_manifest_527_rebuild`.
  - Final build status: `PASS`.
  - Parquet output count: `460`.
  - Manifest status: `PASS`.
  - Validation status: `PASS`.
  - Manifest output count: `460`.
  - Forbidden outputs: `6M\2012.parquet` absent; no `2025.parquet`; no `2026.parquet`.
  - Scoped generated/raw status check returned no tracked changes for:
    - `data\causal_base_candidates\broad_manifest_527_rebuild_v1`
    - `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1`
    - `data\raw`
    - `data\dbn`
    - `configs\data_manifest.yaml`
- Tests/checks run:
  - `python -m pytest tests\validation\test_build_broad_manifest_527_rebuild.py -q` -> `8 passed`.
  - `python -m pytest tests\validation\test_build_broad_manifest_527_rebuild.py tests\validation\test_alpha_tier_ladder_policy.py -q` -> `12 passed`.
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py tests\test_profile_scope.py -q` -> `150 passed`.
  - Final Python artifact check -> parquet count `460`, manifest `PASS`, validation `PASS`, manifest outputs `460`, forbidden count `0`.
- Safety:
  - No provider/network command, `data\raw`, `data\dbn`, `configs\data_manifest.yaml`, models, predictions, feature matrices, WFA, metrics, cleanup target, staging, commit, config promotion, or research-use action was performed.
  - Generated `data\` and `reports\` outputs remain ignored/untracked by scoped status checks.
- Unresolved blockers:
  - Medium: `6M:2012` remains the known excluded blocker.
  - Medium: 2025/2026 remain locked holdout/forward candidates only, not research/training rows.
  - Medium: worktree remains dirty with pre-existing/user changes outside this rebuild scope.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.

Context:
- broad_manifest_527_rebuild_v1 460-row generated candidate build is complete and verified PASS.
- Outputs are built-not-promoted generated candidates only.
- `6M:2012` remains excluded.
- 2025/2026 remain holdout/forward candidates only.
- No modeling, WFA, metrics, predictions, promotion, config promotion, or research-use is approved.

Goal:
- Produce one decision-complete plan for the next gate: either resolve `6M:2012`, plan separate holdout/forward evidence, or freeze the current 460-row generated candidates as built-not-promoted with no further action.

Rules:
- Do not edit files.
- Do not mutate `data/raw/**`, `data/dbn/**`, `configs/data_manifest.yaml`, models, predictions, feature matrices, WFA, metrics, cleanup targets, staging, commits, config promotion, or research-use.
- Do not treat generated candidate outputs as promoted or modeling evidence.
- Keep research build, holdout/forward evidence, `6M:2012` disposition, promotion, and research-use as separate explicit gates.

Plan output required:
1. Output one complete `<proposed_plan>` block.
2. If a decision-complete plan cannot be produced, output only the exact missing user decision.
```

## Alpha Tier YAML Simplified And Guarded - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: adversarially audit and simplify the alpha tier YAML into a professional, common-sense testing ladder.
- Current status: small config wording/test guard complete; no build or modeling work performed.
- Scope completed:
  - Clarified the public ladder comments in `configs\alpha_tiered.yaml`.
  - Renamed tier profile descriptions only:
    - `tier_1_research`: Core Research, 2023-2024.
    - `tier_2_research`: Robustness Research, 2018-2024.
    - `tier_3_research`: Stress Research, 2010-2024.
    - `*_holdout`: Locked Holdout, 2025 only.
    - `*_forward`: Forward, 2026 current/partial year.
  - Added `tests\validation\test_alpha_tier_ladder_policy.py`.
- Guarded policy:
  - Research profiles exclude 2025/2026.
  - Holdout profiles are exactly 2025 and `forbid_research_use=true`.
  - Forward profiles are exactly 2026 and `forbid_research_use=true`.
  - Primary aliases `tier_1`, `tier_2`, and `tier_3` resolve only to research profiles.
- Validation:
  - `python -m pytest tests\validation\test_alpha_tier_ladder_policy.py -q` -> `4 passed`.
  - `python -m pytest tests\validation\test_audit_tier_research_ladder.py -q` -> `3 passed`.
  - `git diff --name-only -- configs\data_manifest.yaml data` -> no output.
- Safety:
  - No `data/**`, `configs\data_manifest.yaml`, provider/network, broad build, modeling, WFA, predictions, metrics, cleanup, staging, commit, config promotion, or research-use action was performed.
  - `configs\alpha_tiered.yaml` was already dirty before this scope; unrelated pending changes in that file were preserved.
- Unresolved blockers:
  - Medium: `6M:2012` remains the known blocked market-year.
  - Medium: 2025/2026 remain inspected holdout/forward candidates only, not research/training rows.
  - Medium: worktree remains dirty with pre-existing/user changes outside this scope.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current state:
- Alpha tier YAML now presents the simple ladder: Core Research, Robustness Research, Stress Research, Locked Holdout, Forward.
- Guard test exists: tests/validation/test_alpha_tier_ladder_policy.py.
- 2025/2026 remain locked out of research/model selection.
- Known blocker remains 6M:2012.
- broad_manifest_527_rebuild_v1 output root was previously deleted and is absent per prior handoff evidence.

Goal:
- Produce a decision-complete plan for the next gated step: keep the policy as-is, pursue the 460-row research rebuild, separately plan holdout/forward evidence, or resolve 6M:2012.

Rules:
- Do not edit files.
- Do not mutate data/**, configs/data_manifest.yaml, predictions, models, feature matrices, cleanup targets, staging, commits, config promotion, modeling, WFA, metrics, or research-use.
- Keep research build, holdout/forward inspection/build, 6M:2012 disposition, promotion, and research-use as separate explicit gates.

Plan output required:
1. Output only one copy-paste GOAL MODE prompt under 3,500 chars.
2. If a decision is missing, list exact allowed decision tokens.
```

## Tier Research Ladder Adversarial Audit Complete - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: adversarially audit the tier approach so the project distinguishes best valid research data points from holdout/forward rows.
- Current status: report-only tier audit complete; no build output exists.
- Scope completed:
  - Added `scripts\validation\audit_tier_research_ladder.py`.
  - Added `tests\validation\test_audit_tier_research_ladder.py`.
  - Wrote generated reports:
    - `reports\data_audit\tier_research_ladder_audit\tier_research_ladder_audit.json`
    - `reports\data_audit\tier_research_ladder_audit\tier_research_ladder_audit.md`
  - The audit reads current tier config, data manifest, broad prebuild plan, raw/source readiness, final 460-row readiness evidence, and report-only checks 2025/2026 deferred rows through raw/source/hash plus Phase 2 `process_file(..., write_output=False)`.
- Audit result:
  - Overall audit status: `FAIL` only because one known policy/data blocker remains.
  - Bucket counts:
    - `research_valid`: 460
    - `locked_holdout_candidate`: 33
    - `forward_candidate`: 33
    - `blocked`: 1
    - `not_checked`: 0
  - Blocked pair: `6M:2012`, reason `confirmed roll-maturity backstep excluded from final 460-row scope`.
  - 2025 rows: all 33 classified as locked holdout candidates after inspection; still not allowed for tuning/model/feature/threshold/market selection.
  - 2026 rows: all 33 classified as forward candidates after inspection; still not a full historical year and carries partial/current-year caveat.
  - Profile audit: `PASS`; 2025/2026 are not configured in research profiles, and holdout/forward profiles have `forbid_research_use=true`.
- Validation:
  - `python -m pytest tests\validation\test_audit_tier_research_ladder.py -q` -> `3 passed`.
  - `python -m pytest tests\validation\test_audit_tier_research_ladder.py tests\validation\test_validate_broad_causal_raw_source_readiness.py -q` -> `8 passed`.
  - `git diff --name-only -- configs\data_manifest.yaml data` -> no output.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` -> `False`.
  - Scoped generated-path `git status --short -- reports\data_audit\tier_research_ladder_audit data\causal_base_candidates\broad_manifest_527_rebuild_v1 reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1` -> no tracked changes.
- Safety:
  - No broad build, data/raw mutation, data/dbn mutation, config promotion, modeling, WFA, predictions, metrics, staging, commit, cleanup, or research-use approval was performed.
  - Generated audit reports remain untracked/ignored.
- Unresolved blockers:
  - Medium: audit status is `FAIL` because `6M:2012` remains blocked; this is expected fail-closed behavior.
  - Medium: 2025/2026 are valid holdout/forward candidates, not research/training rows.
  - Medium: worktree remains dirty with pre-existing/user changes outside this audit scope.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current tier audit state:
- Report-only tier audit is complete.
- Audit buckets: research_valid=460, locked_holdout_candidate=33, forward_candidate=33, blocked=1, not_checked=0.
- Blocked: 6M:2012 roll-maturity backstep.
- 2025 rows are inspected holdout candidates only.
- 2026 rows are inspected forward candidates only with partial/current-year caveat.
- broad_manifest_527_rebuild_v1 output root remains absent.

Goal:
- Produce a decision-complete plan for the next gated step: either keep the current tier policy, plan a 460-row research rebuild, separately approve holdout/forward candidate build evidence, or resolve 6M:2012.

Rules:
- Do not edit files.
- Do not mutate data/**, configs/data_manifest.yaml, predictions, models, feature matrices, staging, commits, cleanup, modeling, WFA, metrics, promotion, or research-use.
- Keep research build, holdout/forward build, 6M:2012 disposition, promotion, and research-use as separate gates.

Plan output required:
1. Output only one copy-paste GOAL MODE prompt under 3,500 chars.
2. If a decision is missing, list exact allowed decision tokens.
```

## Manifest-Aware Broad Artifacts Deleted - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: implement the approved manifest-aware disposition plan to delete both generated broad paths.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, newest `CODEX_HANDOFF.md`, process scans, exact path resolution, pre-delete file counts, tracked-file checks, deletion, and post-delete verification.
  - Pre-delete process scan found no unsafe broad-build/report loop. The only active Python process was unrelated HF Data Library downloader PID 10804:
    - `scripts\phase1A_download\download_hf_data_library.py download-daily ... --run-id hfdl_daily_broad_force_2010_current_bfb_brkb_20260630 ...`
    - Left untouched.
  - Verified exact resolved deletion targets:
    - `C:\Users\donny\Desktop\futures_intraday_model\data\causal_base_candidates\broad_manifest_527_rebuild_v1`
    - `C:\Users\donny\Desktop\futures_intraday_model\reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1`
  - Pre-delete counts:
    - Protected output root: 460 files.
    - Paired report root: 3 files.
  - `git ls-files data/causal_base_candidates/broad_manifest_527_rebuild_v1 reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1` returned no tracked files.
  - Scoped pre-delete generated-path `git status --short` returned no tracked generated changes.
  - Deleted exactly the two approved generated directories with:
    - `Remove-Item -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\data\causal_base_candidates\broad_manifest_527_rebuild_v1','C:\Users\donny\Desktop\futures_intraday_model\reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1' -Recurse -Force`
  - Post-delete checks:
    - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` -> `False`.
    - `Test-Path reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1` -> `False`.
    - Scoped generated-path `git status --short -- data\causal_base_candidates\broad_manifest_527_rebuild_v1 reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628` returned no tracked generated changes.
    - Final process scan again found only unrelated HF downloader PID 10804; no unsafe broad-build/report loop.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
- Deletion status:
  - Complete for the approved manifest-aware disposition.
  - The protected broad output root and paired report root are absent.
- Safety:
  - No broad build, readiness retry, validation/certification of generated files, provider/network command, `data\raw`, `data\dbn`, config promotion, modeling, WFA, predictions, staging, commit, archive, quarantine, or research-use action was performed by this session.
  - Future `broad_manifest_527_rebuild_v1` work must start from the clean absent protected roots and use a separate approved plan with the hardened broad-build gates.
- Unresolved blockers:
  - Medium: worktree remains dirty with pre-existing/user changes outside this manifest-aware disposition.

### Exact Next Recommended Step

```text
No immediate next step for the manifest-aware disposition: the approved generated output root and paired report directory were deleted and verified absent.

If future broad_manifest_527_rebuild_v1 work is requested, start from a fresh Plan Mode prompt, first verify both protected paths are absent, then produce a bounded plan using the hardened approval token, checkpoint, and build chunk guards. Do not run broad build, readiness retry, promotion, modeling, WFA, predictions, staging, commit, or research-use without separate explicit approval.
```

## SR1 Policy Implemented; Manifest-Aware Disposition Active - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request in this run: implement the proposed `SR1:2018` roll-window plan and continue the approved `broad_manifest_527_rebuild_v1` path through validation.
- Current status: implementation and generated validation evidence completed; the active next gate remains manifest-aware disposition because a newer handoff section found the protected output root has a paired manifest and blocked exact-root orphan deletion.
- Scope completed in this run:
  - Implemented sparse elapsed roll-window threshold as diagnostic only when Databento continuous DBN/raw/definition identity evidence is proven.
  - Updated protected broad-build approval token to:
    `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY_UNDER_VENDOR_OHLCV_POLICY`.
  - Fixed `scripts\profile_scope.py` so identity aliases such as `all_raw: all_raw` resolve as identity while real alias cycles still fail.
  - Added focused tests for sparse roll-window diagnostic behavior and profile-scope identity alias handling.
  - Generated paired report files under `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1`.
- Evidence from this run:
  - Readiness report: `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_sparse_roll_window_policy.json`.
  - Readiness status `PASS`; selected `460`; checked `460`; pending `0`; blockers `0`.
  - Candidate output root: `data\causal_base_candidates\broad_manifest_527_rebuild_v1`, with `460` parquet files.
  - Manifest status `PASS`; validation status `PASS`; manifest outputs `460`; validation files `460`.
  - Forbidden rows absent: `6M:2012` absent and 2025/2026 deferred outputs absent.
  - Manifest metadata records `build_status=built_not_promoted`, `broader_modeling_approved=false`, `config_promotion_approved=false`, and `research_use_allowed=false`.
- Files changed in this run:
  - `scripts\phase2_causal_base\build_causal_base_data.py`
  - `scripts\profile_scope.py`
  - `tests\phase2_causal_base\test_build_causal_base_data.py`
  - `tests\test_profile_scope.py`
  - `CODEX_HANDOFF.md`
- Commands/checks run:
  - JSON parse checks for readiness/manifest/validation status and counts.
  - Chunked 460-row `process_file(... write_output=False)` validation assembled through `write_reports(...)`.
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py tests\test_profile_scope.py -q` -> `150 passed in 27.16s`.
  - `git diff --name-only -- configs\data_manifest.yaml` -> no output.
  - `git diff --name-only -- data` -> no output.
  - Stale validation child PID `15528` was stopped. A later final process scan found unrelated HF Data Library downloader PID `10804` running `scripts\phase1A_download\download_hf_data_library.py`; it was left untouched.
- Safety:
  - No provider/network command, `data\raw`, `data\dbn`, `configs\data_manifest.yaml`, predictions, models, feature matrices, cleanup target, staging, commit, config promotion, modeling, WFA, metrics, or research-use action was performed.
  - Generated `data\` and `reports\` artifacts remain ignored/untracked by scoped status checks.
- Unresolved blockers:
  - Severe: active disposition state now requires a manifest-aware decision for both the protected output root and paired ignored report/manifest set before deletion, promotion, research-use, or another broad path.
  - Medium: worktree remains dirty with pre-existing/user changes outside this scope.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current state:
- SR1 sparse roll-window policy/code fix and focused tests are complete.
- broad_manifest_527_rebuild_v1 has 460 generated candidate outputs plus paired manifest/validation reports.
- A newer handoff section blocked exact-root orphan deletion because the paired manifest exists.
- Do not treat the 460 files or paired reports as promoted/modeling/research evidence until a separate manifest-aware decision is selected.

Goal:
- Produce a decision-complete manifest-aware disposition plan for both:
  1. data/causal_base_candidates/broad_manifest_527_rebuild_v1
  2. reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1

Rules:
- Do not edit files.
- Do not delete, move, archive, quarantine, mutate data/** or reports/**, promote configs, run modeling/WFA/predictions/metrics, stage, commit, or use outputs for research.
- Preserve generated-artifact hygiene and separate deletion, promotion, and research-use gates.

Plan output required:
1. Output only one copy-paste GOAL MODE prompt under 3,500 chars.
2. If a decision is missing, list exact allowed disposition tokens.
```

## Orphan Root Deletion Blocked By Unexpected Manifest - 2026-06-30

- Updated at UTC date: 2026-06-30.
- User request: implement the approved disposition plan to delete only `data\causal_base_candidates\broad_manifest_527_rebuild_v1`.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, newest `CODEX_HANDOFF.md`, process scans, protected output/report checks, and generated-path status checks.
  - Pre-delete process scan found no unsafe broad-build loop. Active Python processes were unrelated to the protected broad build:
    - HF Data Library downloader PID 15528.
    - Later scan also showed a pytest run PID 12084 for `tests\phase2_causal_base\test_build_causal_base_data.py tests\test_profile_scope.py -q`.
  - Verified protected output root resolved exactly to `C:\Users\donny\Desktop\futures_intraday_model\data\causal_base_candidates\broad_manifest_527_rebuild_v1`.
  - Verified protected output root still contains 460 files.
  - Stop condition fired before deletion because the paired manifest now exists:
    - `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\causal_base_manifest.json`
    - Last write time: `2026-06-29 17:53:00` local.
  - Paired report directory currently contains 3 files:
    - `causal_base_manifest.json`
    - `causal_base_validation.json`
    - `causal_base_validation.csv`
  - `git status --short -- data\causal_base_candidates\broad_manifest_527_rebuild_v1 reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628` returned no tracked generated changes.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
- Deletion status:
  - Not performed.
  - Reason: approved deletion plan was specifically for an orphan generated root with absent paired manifest, and the manifest-aware stop condition fired.
- Safety:
  - No broad build, readiness retry, validation/certification of the 460 files, provider/network command, raw/dbn mutation, modeling, WFA, predictions, config promotion, staging, commit, cleanup, deletion, archive, or quarantine action was performed by this session.
  - Do not treat the protected output root or paired report files as accepted research evidence without a separate manifest-aware audit/disposition plan.
- Unresolved blockers:
  - Severe: protected broad output root now has both 460 generated files and a paired ignored report/manifest set from `2026-06-29 17:53`; exact-root orphan deletion is no longer the approved safe disposition.
  - Medium: worktree remains dirty with pre-existing repo/user work outside this blocked deletion attempt.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current broad_manifest_527_rebuild_v1 disposition state:
- Exact-root deletion was not performed.
- Stop condition fired because paired manifest now exists:
  reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1/causal_base_manifest.json
- Protected output root remains present with 460 files:
  data/causal_base_candidates/broad_manifest_527_rebuild_v1
- Paired report directory contains 3 files: causal_base_manifest.json, causal_base_validation.json, causal_base_validation.csv.
- Generated-path git status showed no tracked generated changes.
- No unsafe broad-build loop was active in this session's scans; unrelated HF downloader and pytest processes were left untouched.

Goal:
- Produce a decision-complete manifest-aware disposition plan for the protected broad output root and paired ignored report/manifest set.

Rules:
- Do not run broad build.
- Do not run readiness retry.
- Do not validate, certify, promote, or use the 460 files or paired manifest as research evidence.
- Do not delete, move, archive, quarantine, or mutate data/** or reports/** unless the plan asks for one exact later human approval decision covering both the output root and paired report directory.
- Do not run provider/network commands, modeling, WFA, predictions, config promotion, staging, or commit.
- Preserve generated-artifact hygiene.

Plan output required:
1. Output one complete <proposed_plan> block.
2. Include pre-run process scan, exact disposition options for both the protected output root and paired report directory, stop conditions, generated-artifact tracking checks, and evidence required before any later protected broad path can be considered.
```

## Broad Build Restart Guard Hardened; Direct Report Loop Stopped - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the proposed plan to fix the other-session loop, audit why it happened, and prevent recurrence on restart.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, targeted process scans, protected output/report checks, focused tests, full focused-file tests, and final scans.
  - Initial process scan found no unsafe broad-build Python process; only an unrelated HF Data Library downloader was active at PID 17792 and was left untouched.
  - During validation, a new unsafe stale loop appeared and was stopped:
    - `powershell.exe` PID 11044
    - `python.exe` PID 9560
    - Command shape: `python.exe -` direct loop importing `process_file` and `write_reports`, targeting `data\causal_base_candidates\broad_manifest_527_rebuild_v1`, using `process_file(... write_output=False, allow_broad_build_after_readiness_pass=True)` and then `write_reports(...)`.
    - The loop used an older approval token string for a `6M:2012` vendor-policy build path, not the current hardened token.
    - Evidence before stop: Python CPU about 122 seconds, working set about 2.7 GB.
    - Stopped with `Stop-Process -Id 9560,11044 -Force`.
  - Final process scan found no active `python.exe` process.
  - Final protected output check found `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still exists with 460 files.
  - Final protected manifest check found `reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\causal_base_manifest.json` is absent.
  - Final generated-path `git status --short -- data\causal_base_candidates\broad_manifest_527_rebuild_v1 reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628` returned no tracked changes.
- Files changed in this scope:
  - `scripts\phase2_causal_base\build_causal_base_data.py`
  - `tests\phase2_causal_base\test_build_causal_base_data.py`
  - `CODEX_HANDOFF.md`
- Workflow implemented:
  - Added exact protected broad-build token requirement: `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY`.
  - Hardened protected broad CLI builds to require all of:
    - `--allow-broad-build-after-readiness-pass`
    - exact `--broad-build-approval-token`
    - `--build-progress-checkpoint-jsonl`
    - `--build-max-market-years <= 25`
    - no existing protected-root parquet files without paired Phase 2 manifest
  - Hardened direct `process_file(...)` protected-root writes to require the exact token, not just the boolean approval flag.
  - Hardened direct `write_reports(...)` protected broad report writes to require the exact token before creating the report directory, closing the observed stale validation/report bypass.
  - Left readiness-only behavior unchanged.
- Validation:
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q -k "broad_build_approval or protected_broad_output_root or build_max_market_years or build_checkpoint or orphaned_protected_broad_outputs or uncheckpointed_protected_broad_build or unbounded_protected_broad_build or protected_broad_reports"` -> `11 passed, 137 deselected`.
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q` -> `148 passed`.
- Build state and safety:
  - Broad build was not restarted.
  - Readiness retry was not run.
  - The existing 460-file protected broad output root is generated/orphaned and must not be treated as valid research evidence.
  - No provider/network command, raw/dbn mutation, config promotion, modeling, WFA, staging, commit, cleanup, deletion, archive, quarantine, or research-use action was performed by this session.
- Unresolved blockers:
  - Medium: orphan generated output remains at `data\causal_base_candidates\broad_manifest_527_rebuild_v1` with 460 files and no paired manifest; it needs an explicit cleanup/disposition plan before any future broad path.
  - Medium: any still-open stale external session should be closed or interrupted before continuation. Final scan is clean, and restarted old commands should now fail after loading the hardened code.
  - Medium: worktree remains dirty with pre-existing repo/user work outside this process-control and guard implementation.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current broad_manifest_527_rebuild_v1 restart-guard state:
- Unsafe direct report loop PID 9560/11044 was stopped.
- Final scan found no active python.exe process.
- Protected root exists with 460 generated files: data/causal_base_candidates/broad_manifest_527_rebuild_v1
- Protected paired manifest is absent: reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1/causal_base_manifest.json
- Hardened guard now requires exact token APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY, checkpoint, build max <=25, and no orphaned protected-root parquet before any protected broad CLI build.
- Direct process_file protected writes and direct write_reports protected report writes now require the same exact token.

Goal:
- Produce a decision-complete plan for disposition of the orphan generated protected broad output root before any readiness retry, broad build, report certification, cleanup, or research-use action.

Rules:
- Do not run broad build.
- Do not run readiness retry.
- Do not validate or certify the existing 460 files as research evidence.
- Do not delete, move, archive, quarantine, or mutate data/** unless the plan explicitly asks for a later human approval decision for that exact action.
- Do not run provider/network commands, modeling, WFA, predictions, config promotion, staging, or commit.
- Preserve generated-artifact hygiene.

Plan output required:
1. Output one complete <proposed_plan> block.
2. Include pre-run process scan, exact disposition options for the orphan generated root, stop conditions, generated-artifact tracking checks, and evidence required before any later protected broad path can be considered.
```

## Unsafe Broad Build Recurrence Stopped; Build Guard Workflow Implemented - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: adversarially audit whether another session was stuck/looping, restart if needed, and implement workflow so processes do not get stuck again.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, process scans, broad output-root checks, generated-artifact checks, focused tests, and final process scan.
  - Stopped active unsafe broad build pair:
    - `powershell.exe` PID 15580
    - `python.exe` PID 12560
    - Evidence before stop: command line was `python.exe -`, CPU about 2802 seconds, working set about 1.5 GB, and `data\causal_base_candidates\broad_manifest_527_rebuild_v1` had fresh writes through `HE` at `2026-06-29 14:05:27 -07:00`.
    - Stopped with `Stop-Process -Id 12560,15580 -Force`.
  - Stopped recurrence after the first stop:
    - `powershell.exe` PID 19092
    - `python.exe` PID 9344
    - Evidence before stop: command line was `python.exe -`, CPU about 308 seconds, working set about 3.6 GB, and the broad output root had fresh writes through `HG` at `2026-06-29 14:10:17 -07:00`.
    - Stopped with `Stop-Process -Id 9344,19092 -Force`.
  - Stopped second recurrence after final validation began:
    - `powershell.exe` PID 19812
    - `python.exe` PID 12120
    - Evidence before stop: command line was `python.exe - 172 182`, CPU about 57 seconds, working set about 3.7 GB, and the broad output root had fresh writes through `HO` at `2026-06-29 14:14:50 -07:00`.
    - Stopped with `Stop-Process -Id 12120,19812 -Force`.
  - Stopped additional post-guard recurrences:
    - `powershell.exe` PID 6932 / `python.exe` PID 6888, stopped with `Stop-Process -Id 6888,6932 -Force`.
    - `powershell.exe` PID 13372 / `python.exe` PID 9440, stopped with `Stop-Process -Id 9440,13372 -Force`.
    - `powershell.exe` PID 11908 / `python.exe` PID 17688 exited before the stop command reached it.
    - `powershell.exe` PID 14852 / `python.exe` PID 11784, stopped with `Stop-Process -Id 11784,14852 -Force`.
    - Post-guard recurrences no longer advanced the partial output after `HO` at `2026-06-29 14:16:05 -07:00`, consistent with the new protected-root write guard failing before additional writes.
  - Final process scan found no active `python.exe` process.
  - Final generated-output check found the partial ignored broad root exists with `176` files and latest market directory `HO` at `2026-06-29 14:16:05 -07:00`.
  - `git status --short -- data\causal_base_candidates\broad_manifest_527_rebuild_v1 reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628` returned no tracked changes.
- Files changed in this scope:
  - `scripts\phase2_causal_base\build_causal_base_data.py`
  - `tests\phase2_causal_base\test_build_causal_base_data.py`
  - `CODEX_HANDOFF.md`
- Workflow implemented:
  - Added protected broad output-root CLI approval gate for non-readiness builds targeting `data/causal_base_candidates/broad_manifest_527_rebuild_v1`.
  - Added explicit CLI flag `--allow-broad-build-after-readiness-pass`; readiness PASS alone is not accepted as build approval.
  - Added build controls `--build-max-market-years` and `--build-progress-checkpoint-jsonl`.
  - Added build checkpoint JSONL records: start, one row per processed market-year, and final summary.
  - Reused the existing checkpoint path policy so build checkpoints under `data/**` fail closed.
  - Added a lower-level `process_file(...)` write guard so direct `python -` loops cannot write into the protected broad root without explicit approval passed by the CLI build path.
- Validation:
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q -k "broad_build_approval or build_only_options or protected_broad_output_root or build_max_market_years or build_checkpoint_under_data"` -> `6 passed, 134 deselected`.
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q` -> `140 passed`.
  - `git diff --check -- scripts\phase2_causal_base\build_causal_base_data.py tests\phase2_causal_base\test_build_causal_base_data.py CODEX_HANDOFF.md` -> no diff-check errors; only Windows LF-to-CRLF warnings.
- Build state and safety:
  - Broad build was stopped, not restarted.
  - The existing partial broad output root is generated/ignored and must not be treated as a valid build artifact or research evidence.
  - No provider/network command, raw/dbn mutation, config promotion, modeling, WFA, staging, commit, cleanup, deletion, archive, quarantine, or research-use action was performed by this session.
- Unresolved blockers:
  - Medium: partial ignored generated output now exists at `data\causal_base_candidates\broad_manifest_527_rebuild_v1` with 176 files; it needs an explicit cleanup/disposition plan before any future broad path.
  - Severe: another session repeatedly relaunched `python.exe -` after stops. Final scan was clean, but that other session should be interrupted/closed or coordinated before continuing.
  - Medium: worktree remains dirty with pre-existing repo/user work outside this process-control and guard implementation.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current broad_manifest_527_rebuild_v1 process-control state:
- Unsafe broad build pair PID 12560/15580 was stopped.
- Recurring unsafe broad build pair PID 9344/19092 was stopped.
- Recurring unsafe broad build pair PID 12120/19812 was stopped.
- Additional post-guard recurrence PIDs 6888/6932, 9440/13372, and 11784/14852 were stopped; PID 17688/11908 exited before stop.
- Final scan found no active python.exe process.
- Partial ignored generated broad output exists: data/causal_base_candidates/broad_manifest_527_rebuild_v1
- Final partial output count observed: 176 files, latest market directory HO at 2026-06-29 14:16:05 -07:00.
- No tracked generated output was detected under the checked broad output/report paths.
- Guard workflow is implemented and tested in scripts/phase2_causal_base/build_causal_base_data.py and tests/phase2_causal_base/test_build_causal_base_data.py.

Goal:
- Produce a decision-complete plan to clear the repeated external respawn blocker before any cleanup, readiness, or build work continues.

Rules:
- Do not run broad build.
- Do not run readiness retry.
- Do not clean up partial broad output in this phase.
- Do not treat data/causal_base_candidates/broad_manifest_527_rebuild_v1 as valid research evidence.
- Do not delete, move, archive, quarantine, or mutate data/**.
- Do not mutate data/raw, data/dbn, configs/data_manifest.yaml, predictions, models, feature matrices, staging, commits, config promotion, modeling, WFA, metrics, or research-use.
- Preserve generated-artifact hygiene.

Plan output required:
1. Output one complete <proposed_plan> block.
2. Include the human/session precondition for closing or interrupting the other Codex session, the pre-run and post-wait process scans, stop conditions, and the evidence required before a later partial-output disposition plan can be produced.
```

## Stuck/Unsafe Broad Build Session Stopped; No Output Root Created - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: another session in this project seemed stuck/looping.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, newest `CODEX_HANDOFF.md`, targeted process inspection, output-root checks, and generated-artifact status checks.
  - Found a stale no-checkpoint readiness pair:
    - `powershell.exe` PID 4696
    - `python.exe` PID 8776
    - Command used `build_phase2_readiness_report(... fail_fast=True)` with no checkpoint path.
    - Evidence before it exited: started 2026-06-29 12:28:27 PM local, Python CPU about 2225 seconds, working set about 7.9 GB, target JSON/MD absent.
    - `Stop-Process -Id 8776,4696 -Force` found both PIDs already gone.
  - Found and stopped an unsafe broad build pair:
    - `powershell.exe` PID 14868
    - `python.exe` PID 11212
    - Command ran `python -m scripts.phase2_causal_base.build_causal_base_data ...` without `--readiness-only`, targeting `data\causal_base_candidates\broad_manifest_527_rebuild_v1`.
    - Stopped with `Stop-Process -Id 11212,14868 -Force`.
  - Verified stopped PIDs 11212/14868/4696/8776 were absent after the stop attempt.
  - Verified `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - Verified `git status --short -- data\causal_base_candidates\broad_manifest_527_rebuild_v1 reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1` returned no tracked changes.
  - Final command-line scan found no active broad readiness/build Python process; it only matched a short monitor command checking `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` and the scan itself.
  - Left separate Tiingo EOD downloader PID 19988 and its monitor sleep processes untouched; that process is unrelated to the broad causal rebuild.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
- Validation and evidence:
  - No tests were run; this was a process-control intervention.
  - Broad build output root remained absent after stopping the unsafe build pair.
  - No tracked generated output appeared under the broad build output/report paths checked above.
- Build state and safety:
  - Broad build is still not approved.
  - No provider/network command, raw/dbn mutation, config promotion, modeling, WFA, staging, commit, cleanup, or research-use action was performed by this session.
  - Do not restart any command that omits `--readiness-only` for `broad_manifest_527_rebuild_v1` unless the user gives exact broad-build approval after readiness PASS.
  - Do not restart no-checkpoint readiness or direct broad `process_file(...)` loops.
- Unresolved blockers:
  - Medium: another live session attempted an unapproved broad build; coordinate or close stale sessions before continuing this path.
  - Medium: broader readiness remains incomplete; latest safe resume point remains include index `301` with 159 pending market-years from the prior handoff section.
  - Medium: worktree remains dirty with pre-existing user/repo work outside this process-control intervention.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current broad_manifest_527_rebuild_v1 process-control state:
- Stale no-checkpoint readiness pair PID 4696/8776 was observed consuming CPU/RAM with no target JSON/MD, then exited before termination.
- Unsafe broad build pair PID 14868/11212 was stopped.
- Build root remains absent: data/causal_base_candidates/broad_manifest_527_rebuild_v1
- No tracked generated output was detected under the broad build output/report paths checked.
- Separate Tiingo EOD downloader PID 19988 was left untouched because it is unrelated to the broad causal rebuild.
- Latest safe readiness resume point from prior handoff remains include index 301 with 159 pending market-years.

Goal:
- Produce a decision-complete plan to continue only the checkpointed readiness retry from include index 301 in bounded chunks, after first verifying no active unsafe broad readiness/build/process-file command remains.

Rules:
- Do not run broad build.
- Do not run commands that omit --readiness-only for broad_manifest_527_rebuild_v1.
- Do not use no-checkpoint readiness loops or direct process_file(...) loops over a broad tail range.
- Do not mutate data/**, data/raw, data/dbn, configs/data_manifest.yaml, predictions, models, feature matrices, cleanup targets, staging, commits, config promotion, modeling, WFA, metrics, or research-use.
- Preserve generated-artifact hygiene.
- If running readiness, use per-row checkpoint JSONL, stop_after_blockers=1, chunk size no larger than 5 unless a plan justifies it, and a bounded timeout per chunk.

Plan output required:
1. Output one complete <proposed_plan> block.
2. Include the pre-run process scan, exact next chunk command or wrapper approach, timeout/stop conditions, checkpoint/report output paths, and evidence required before trusting the next blocker or PASS.
```

## Stuck Readiness Sessions Stopped; Bounded Chunk Restart Advanced To Index 301 - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: check whether the rewrite/new-agent readiness session was stuck again; if stuck, stop it and restart without repeating another unbounded stuck run.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, newest `CODEX_HANDOFF.md`, targeted readiness CLI/API inspection, generated-output checks, and process inspection.
  - Stopped stale no-checkpoint readiness process pair:
    - `powershell.exe` PID 7388
    - `python.exe` PID 7076
  - Restarted from the prior resume point in bounded chunks using `build_phase2_readiness_report(...)` with:
    - `skip_market_years=include[:275]` or later chunk offset
    - `max_market_years` of 1, then 10, then 10, then 5
    - `stop_after_blockers=1`
    - per-row checkpoint JSONL flush
    - bounded tool timeouts
  - Stopped a second unbounded new-agent/process-file loop that appeared during the run:
    - `powershell.exe` PID 6336
    - `python.exe` PID 2456
  - Confirmed no remaining `broad_manifest_527`, `build_phase2`, or `process_file` readiness process after stopping those pairs.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - Generated ignored readiness chunk reports:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_275_1.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_275_1.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_275_1_checkpoint.jsonl`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_276_10.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_276_10.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_276_10_checkpoint.jsonl`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_286_10.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_286_10.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_286_10_checkpoint.jsonl`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_296_5.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_296_5.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_296_5_checkpoint.jsonl`
- Validation and evidence:
  - `SR1:2019` single-row chunk completed in about 4 seconds and PASSed.
  - Chunk `276_10` completed in about 40 seconds; rows `SR1:2020` through `SR3:2022` all PASSed.
  - Chunk `286_10` completed in about 136 seconds; rows `SR3:2023` through `TN:2023` all PASSed.
  - Chunk `296_5` completed in about 54 seconds; rows `TN:2024` through `UB:2013` all PASSed.
  - Latest chunk summary: `checked_market_year_count=301`, `resumed_market_year_count=296`, `pending_market_year_count=159`, `blocker_count=0`, `failure_count=0`.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - `git status --short -- reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628` returned no tracked changes for generated readiness reports.
- Build state and safety:
  - Broad build was not run.
  - No provider/network command, raw/dbn mutation, config promotion, modeling, WFA, staging, commit, cleanup, or research-use action was performed.
  - Do not use the stopped unbounded patterns again:
    - no no-checkpoint `build_phase2_readiness_report(...)` over many rows
    - no direct `process_file(...)` loop over `include[285:]` or any broad tail range
- Unresolved blockers:
  - Medium: broader readiness remains incomplete; latest safe resume point is include index `301` with 159 pending market-years.
  - Medium: worktree remains dirty with pre-existing user/repo work outside this bounded restart.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current broad_manifest_527_rebuild_v1 restart state:
- Stale no-checkpoint readiness pair PID 7388/7076 was stopped.
- Second unbounded new-agent process-file loop PID 6336/2456 was stopped.
- No `broad_manifest_527`, `build_phase2`, or `process_file` readiness process remained after verification.
- Bounded chunk restart advanced through include index 300.
- Latest generated evidence:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_296_5.json
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_after_sr1_2018_chunk_296_5_checkpoint.jsonl
- Latest summary: checked=301, resumed=296, pending=159, blockers=0, failures=0.
- Build root is still absent: data/causal_base_candidates/broad_manifest_527_rebuild_v1

Goal:
- Produce a decision-complete plan to continue the checkpointed broader readiness retry from include index 301 in bounded chunks until the next blocker or PASS, without running broad build.

Rules:
- Do not run broad build.
- Do not use unbounded readiness loops or direct `process_file(...)` loops over a broad tail range.
- Do not mutate data/**, data/raw, data/dbn, configs/data_manifest.yaml, predictions, models, feature matrices, cleanup targets, staging, commits, config promotion, modeling, WFA, metrics, or research-use.
- Preserve generated-artifact hygiene.
- If running readiness, use per-row checkpoint JSONL, `stop_after_blockers=1`, a chunk size no larger than 5 unless a plan justifies it, and a bounded timeout per chunk.

Plan output required:
1. Output one complete <proposed_plan> block.
2. Include exact next chunk command or wrapper approach, timeout/stop conditions, checkpoint/report output paths, and evidence required before trusting the next blocker or PASS.
```

## Checkpointed Readiness CLI Implemented - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the proposed plan to add or expose a bounded/checkpointed readiness path before any broader readiness retry.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, newest `CODEX_HANDOFF.md`, and targeted readiness CLI/API search.
  - Added CLI exposure for existing readiness bounds and progress controls in `scripts\phase2_causal_base\build_causal_base_data.py`.
  - Added append-only readiness checkpoint JSONL output with a start record, one row per checked market-year, and a final summary record.
  - Added guard that rejects checkpoint paths under `data/**`.
  - Added focused CLI tests for checkpoint JSONL, `--readiness-max-market-years`, `--readiness-stop-after-blockers`, and preserving no-output readiness-only behavior.
- Files changed in this scope:
  - `scripts\phase2_causal_base\build_causal_base_data.py`
  - `tests\phase2_causal_base\test_build_causal_base_data.py`
  - `CODEX_HANDOFF.md`
- New CLI flags:
  - `--readiness-checkpoint-jsonl <path>`
  - `--readiness-max-market-years <int>`
  - `--readiness-stop-after-blockers <int>`
  - `--readiness-progress`
- Validation:
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q` -> `134 passed`.
  - `git diff --check -- scripts\phase2_causal_base\build_causal_base_data.py tests\phase2_causal_base\test_build_causal_base_data.py CODEX_HANDOFF.md` -> no diff-check errors; only Windows LF-to-CRLF warnings.
  - `git status --short` remains dirty with pre-existing repo/user work plus this scope's touched code/test/handoff files.
- Build state and safety:
  - Full 460-row readiness was not rerun.
  - Broad build was not run.
  - No provider/network commands, `data/**` mutation, raw/dbn mutation, config promotion, modeling, WFA, staging, commit, cleanup, or research-use action was performed.
- Unresolved blockers:
  - Medium: the checkpointed CLI is implemented and tested, but the broader 460-row readiness retry has not yet been run with checkpointing.
  - Medium: worktree remains dirty with pre-existing user/repo work outside this checkpointed-readiness implementation.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current broad_manifest_527_rebuild_v1 restart state:
- SR1:2018 bounded readiness evidence is PASS and confirms the sparse roll-window threshold is diagnostic under vendor-continuous identity proof.
- Checkpointed readiness CLI is implemented and tested.
- Build root is still absent: data/causal_base_candidates/broad_manifest_527_rebuild_v1
- Full 460-row readiness has not been rerun after SR1:2018 cleared.

Goal:
- Produce a decision-complete plan for the first checkpointed broader readiness retry that stops after the next blocker and does not run broad build.

Rules:
- Do not run broad build.
- Do not mutate data/**, data/raw, data/dbn, configs/data_manifest.yaml, predictions, models, feature matrices, cleanup targets, staging, commits, config promotion, modeling, WFA, metrics, or research-use.
- Preserve generated-artifact hygiene.
- If running readiness, use --readiness-checkpoint-jsonl and --readiness-stop-after-blockers 1, and run under a bounded timeout.

Plan output required:
1. Output one complete <proposed_plan> block.
2. Include exact command, timeout/stop conditions, checkpoint output paths, and evidence required before trusting the next blocker or PASS.
```

## SR1 2018 Sparse Roll Window Bounded Restart PASS - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the restart plan for the stopped sparse-roll-window readiness session without repeating the unbounded 460-row readiness loop.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, newest `CODEX_HANDOFF.md`, sparse-roll-window output check, raw SR1:2018 presence check, and build-root absence check.
  - Statically inspected readiness-only, fail-fast, sparse roll-window, and report-writing hooks in `scripts\phase2_causal_base\build_causal_base_data.py`.
  - Confirmed config state in `configs\alpha_tiered.yaml` and `configs\tier_3.yaml`: `SR1`/`SR3` are sparse trade-derived OHLCV markets, sparse roll window is 15 minutes, and vendor-trusted OHLCV applies to full markets.
  - Ran a bounded single-row SR1:2018 readiness reproduction through the Python API, not the full 460-row CLI.
  - Extracted row-level SR1:2018 evidence with `process_file(..., write_output=False)` because PASS rows are not included in the readiness report blockers list.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - Generated ignored diagnostic reports:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\SR1_2018_sparse_roll_window_bounded_readiness.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\SR1_2018_sparse_roll_window_bounded_readiness.md`
- Validation and evidence:
  - Initial `Start-Process` wrapper failed before Python launched with Windows `PATH`/`Path` environment collision; this is not project readiness evidence.
  - Direct bounded Python stdin rerun completed in about 3 seconds and printed `PASS 1 0 0`.
  - `SR1_2018_sparse_roll_window_bounded_readiness.json` parsed with:
    - `status=PASS`
    - `selected_market_year_count=1`
    - `checked_market_year_count=1`
    - `pending_market_year_count=0`
    - `blocker_count=0`
    - `failure_count=0`
  - Row-level SR1:2018 `process_file(..., write_output=False)` evidence:
    - `status=PASS`
    - `roll_window_policy=elapsed_minutes_sparse_ohlcv`
    - `roll_window_minutes=15`
    - `roll_window_threshold_breached=true`
    - `roll_window_rows=116`
    - `roll_window_rows_pct=7.426376`
    - `sparse_roll_window_threshold_policy=sparse_elapsed_roll_window_vendor_continuous`
    - `sparse_roll_window_threshold_status=roll_window_threshold_diagnostic_sparse_vendor_continuous`
    - `vendor_continuous_identity_evidence_status=PASS`
    - `vendor_continuous_roll_backstep_status=roll_backsteps_diagnostic_vendor_continuous_identity_proven`
    - `warnings=[]`
    - diagnostic warning records the roll exclusion threshold as diagnostic under sparse elapsed-minute vendor-continuous identity proof.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` stayed `False`.
  - `git diff --name-only -- ...SR1_2018_sparse_roll_window_bounded_readiness... data` returned no tracked paths.
- Build state and safety:
  - Full 460-row readiness was not rerun.
  - Broad build was not run.
  - No provider/network commands, `data/**` mutation, raw/dbn mutation, config promotion, modeling, WFA, staging, commit, cleanup, or research-use action was performed.
- Unresolved blockers:
  - Medium: SR1:2018 is cleared only by bounded single-row evidence; the next full-scope readiness attempt still needs a bounded/checkpointed path before it can be trusted not to repeat a no-output long run.
  - Medium: `git status --short` remains dirty with pre-existing user/repo work outside this bounded diagnostic.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current broad_manifest_527_rebuild_v1 restart state:
- Prior unbounded sparse-roll-window readiness-only process was stopped after >60 minutes with no JSON/MD.
- New bounded SR1:2018 diagnostic evidence exists:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/SR1_2018_sparse_roll_window_bounded_readiness.json
- SR1:2018 bounded readiness is PASS with selected=1 checked=1 pending=0 blockers=0.
- Row-level evidence confirms SR1:2018 roll-window threshold is diagnostic under sparse elapsed-minute vendor-continuous identity proof.
- Build root still absent: data/causal_base_candidates/broad_manifest_527_rebuild_v1
- Full 460-row readiness has not been rerun after SR1:2018 cleared.

Goal:
- Produce a decision-complete plan to add or expose a bounded/checkpointed readiness path before any broader readiness retry.

Rules:
- Do not run the full 460-row readiness command until the bounded/checkpointed path is available and approved.
- Do not run broad build.
- Do not mutate data/**, data/raw, data/dbn, configs/data_manifest.yaml, predictions, models, feature matrices, cleanup targets, staging, commits, config promotion, modeling, WFA, metrics, or research-use.
- Preserve generated-artifact hygiene.

Plan output required:
1. Output one complete <proposed_plan> block.
2. Include the minimum CLI/API changes or existing-command usage needed to emit partial readiness evidence, stop after the next blocker, and avoid no-output long runs.
```

## Broad Manifest 527 Vendor Continuous Roll Policy Stopped On SR1 2018 Roll Window - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: fix the `HE:2010` roll-maturity blocker as a bounded Databento continuous-contract policy mismatch, not by redownloading, then continue the `broad_manifest_527_rebuild_v1` path only through readiness-only unless readiness `PASS` and exact build approval exists.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, and `Get-Content CODEX_HANDOFF.md -TotalCount 120`.
  - Added fail-closed vendor-continuous roll identity proof for roll maturity backsteps.
  - Updated the report-only roll diagnostic to classify `vendor_continuous_roll_backstep_policy_mismatch` only when local OHLCV DBN, raw parquet, definition enrichment, and manifest evidence all match.
  - Updated Phase 2 readiness so proven Databento continuous roll backsteps are diagnostic, while non-vendor, non-continuous, missing-proof, DBN/raw mismatch, definition mismatch, and unreadable-source cases remain blockers.
  - Generated HE:2010 report-only evidence and reran the 460-row readiness-only preflight.
- Files changed in this scope:
  - `scripts\phase2_causal_base\build_causal_base_data.py`
  - `scripts\validation\diagnose_roll_maturity_blocker.py`
  - `tests\phase2_causal_base\test_build_causal_base_data.py`
  - `tests\validation\test_diagnose_roll_maturity_blocker.py`
  - `CODEX_HANDOFF.md`
  - Generated reports:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\HE_2010_vendor_continuous_roll_policy_diagnosis.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\HE_2010_vendor_continuous_roll_policy_diagnosis.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_vendor_continuous_roll_policy.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_vendor_continuous_roll_policy.md`
- Validation:
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py tests\validation\test_diagnose_roll_maturity_blocker.py -q` -> `133 passed`.
  - HE:2010 diagnostic:
    - `status=PASS`
    - `disposition_call=vendor_continuous_roll_backstep_policy_mismatch`
    - `vendor_continuous_identity_evidence.status=PASS`
    - `ohlcv_dbn_row_count=63251`
    - `enriched_row_count=63251`
    - `definition_row_count=14270`
    - `identity_mismatch_counts={}`
  - New readiness-only result:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_vendor_continuous_roll_policy.json`
    - `status=FAIL`
    - `selected_market_year_count=460`
    - `checked_market_year_count=275`
    - `pending_market_year_count=185`
    - blocker: `SR1:2018`
    - reason: `roll exclusion threshold breached: rows_pct=7.426376 rows=116`
    - the SR1:2018 roll maturity backstep itself had `vendor_continuous_roll_backstep_status=roll_backsteps_diagnostic_vendor_continuous_identity_proven`; the remaining blocker is the roll-window threshold.
- Command caveat:
  - The readiness-only command emitted `phase2_readiness_only status=FAIL checked=275 blockers=1 ...` and wrote parseable JSON, but the shell wrapper returned timeout exit code `124` after the report was written. A subsequent `Get-Process python` check returned no running Python process.
- Build state and safety:
  - Broad build was not run because readiness-only did not pass.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - `git diff --name-only -- data` returned no paths.
  - No provider/network commands were run.
  - No `data/raw`, `data/dbn`, `configs/data_manifest.yaml`, predictions, models, feature matrices, cleanup, staging, commit, config promotion, modeling, WFA, metrics, or research-use action was performed.
- Unresolved blocker:
  - Severe: 460-row readiness-only preflight now fails on `SR1:2018` roll-window threshold, not on `HE:2010` roll maturity.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current broad_manifest_527_rebuild_v1 vendor-policy rerun state:
- HE:2010 roll maturity blocker was fixed as a proven Databento continuous-contract diagnostic.
- Current include:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_460_excluding_6M_2012_vendor_ohlcv_policy.json
- Current readiness:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_vendor_continuous_roll_policy.json
- Current blocker: SR1:2018, reason `roll exclusion threshold breached: rows_pct=7.426376 rows=116`.
- Build root still absent: data/causal_base_candidates/broad_manifest_527_rebuild_v1
- Broad build has not run.

Goal:
- Produce a decision-complete plan to diagnose and disposition the SR1:2018 roll-window threshold blocker, then continue the broad_manifest_527_rebuild_v1 path only if explicit gates pass.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**, data/raw, data/dbn, configs/data_manifest.yaml, predictions, models, feature matrices, cleanup targets, staging, commits, config promotion, modeling, WFA, metrics, or research-use.
- Do not run the broad build unless readiness-only PASS and exact build approval covers the final scope.
- Keep broader_modeling_approved=false, config_promotion_approved=false, research_use_allowed=false.

Plan output required:
1. Output only one fenced text GOAL MODE prompt.
2. Keep the fenced GOAL prompt under 3,500 chars.
```

## Broad Manifest 527 Vendor Policy Rerun Stopped On HE 2010 Roll Maturity - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: rerun the full `broad_manifest_527_rebuild_v1` approval-to-build path under vendor-backed OHLCV no-trade policy, restoring policy-stale source-gap exclusions and excluding only confirmed non-OHLCV blocker `6M:2012`.
- Scope executed:
  - Established state with `Get-Location`, `git status --short`, `Get-Content -Raw CODEX_HANDOFF.md`, and build-root checks.
  - Confirmed `vendor_trusted_ohlcv_no_trade_markets: *full_markets` is active in `configs\alpha_tiered.yaml` and `configs\tier_3.yaml`.
  - Confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` does not exist.
  - Created restored 460-row include from the original 461-row include, removing exactly `6M:2012` and restoring 42 policy-stale source-gap fail-closed rows.
  - Ran readiness-only preflight for the restored 460-row scope.
- New include artifact:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_460_excluding_6M_2012_vendor_ohlcv_policy.json`
  - `market_years=460`
  - removed pair: `6M:2012`
  - deferred rows still excluded: `66`
  - restored policy-stale source-gap rows: `42`
  - `build_approved=true` because the exact fresh token was present in the user prompt:
    `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY_UNDER_VENDOR_OHLCV_POLICY`
  - `broader_modeling_approved=false`, `config_promotion_approved=false`, `research_use_allowed=false`
- Readiness-only result:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_vendor_ohlcv_policy.json`
  - `status=FAIL`
  - `selected_market_year_count=460`
  - `checked_market_year_count=135`
  - `pending_market_year_count=325`
  - blocker: `HE:2010`
  - reason: `roll maturity sequence not monotonic: backsteps=1`
  - example: previous `HEV0` maturity `24130` -> current `HEQ0` maturity `24128` at `2010-07-30T00:01:00+00:00`
  - `synthetic_gap_threshold_action=diagnostic`
  - `vendor_trusted_ohlcv_no_trade_status=synthetic_thresholds_diagnostic_vendor_backed_provenance`
  - `status_enrichment_missing_rows=57806`
  - `statistics_enrichment_missing_rows=0`
- Build state:
  - Broad build was not run because readiness-only did not pass.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False` after readiness-only.
  - `git diff --name-only -- data` returned no paths.
- Command caveat:
  - The readiness-only command emitted `phase2_readiness_only status=FAIL checked=135 blockers=1 ...` and wrote parseable JSON, but the shell wrapper returned timeout exit code `124` after the report was written. A subsequent `Get-Process python` check returned no running Python process.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - Generated reports:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_460_excluding_6M_2012_vendor_ohlcv_policy.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_vendor_ohlcv_policy.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_vendor_ohlcv_policy.md`
- Safety:
  - No provider/network commands were run.
  - No `data/raw`, `data/dbn`, `configs/data_manifest.yaml`, predictions, models, feature matrices, cleanup, staging, commit, config promotion, modeling, WFA, metrics, or research-use action was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Current blocker: broad_manifest_527_rebuild_v1 vendor-policy rerun readiness-only failed on HE:2010, reason `roll maturity sequence not monotonic: backsteps=1`.
Current include:
reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_460_excluding_6M_2012_vendor_ohlcv_policy.json
Current readiness:
reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_vendor_ohlcv_policy.json
Build root still absent: data/causal_base_candidates/broad_manifest_527_rebuild_v1
Broad build has not run.

Goal:
- Produce a decision-complete plan to diagnose and disposition the HE:2010 roll maturity blocker, then continue the broad_manifest_527_rebuild_v1 path only if explicit gates pass.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**, data/raw, data/dbn, or configs/data_manifest.yaml.
- Do not run broad build unless a later exact disposition is selected and readiness-only PASS is reached.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.

Plan output required:
1. Output only one fenced text GOAL MODE prompt.
2. Keep the fenced GOAL prompt under 3,500 chars.
```

## Phase 2 Vendor-Backed OHLCV No-Trade Provenance Policy Implemented - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: remove the project requirement to prove every missing OHLCV minute from local L1/trades and replace that Phase 2 readiness behavior with vendor-backed provenance.
- Scope executed:
  - Updated Phase 2 readiness so Databento OHLCV no-bar minutes are handled by `vendor_trusted_ohlcv_no_trade_markets` vendor provenance instead of a mandatory local L1/local-trades gate.
  - Kept the local trades audit tooling available as explicit diagnostics, but removed it from automatic Phase 2 profile exit gating.
  - Removed the hard-coded HE/LE-only vendor-trusted exception allowlist and the HE/LE broad-market config rejection.
  - Allowed exact `vendor_trusted_ohlcv_no_trade` accepted exceptions for any market-year when evidence and exact current warning strings match.
  - Allowed vendor-trusted OHLCV exceptions to preserve/report optional status/statistics enrichment gaps without using those counts as an OHLCV no-trade blocker.
  - Updated `vendor_trusted_ohlcv_no_trade_markets` to `*full_markets` in both active tier configs.
- Files changed in this scope:
  - `scripts\phase2_causal_base\build_causal_base_data.py`
  - `configs\alpha_tiered.yaml`
  - `configs\tier_3.yaml`
  - `tests\phase2_causal_base\test_build_causal_base_data.py`
  - `CODEX_HANDOFF.md`
- Validation:
  - `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q` -> `126 passed`.
  - `git diff --check -- scripts\phase2_causal_base\build_causal_base_data.py tests\phase2_causal_base\test_build_causal_base_data.py configs\alpha_tiered.yaml configs\tier_3.yaml` -> no diff-check errors; only Windows LF-to-CRLF warnings.
  - Config load check returned `vendor_market_count=33`, `has_6M=True`, `has_HE=True`, `has_ZN=True`.
  - Read-only `process_file(..., profile="all_raw", write_output=False)` check for `data\raw\6M\2015.parquet` returned:
    - `status=PASS`
    - `synthetic_gap_threshold_breached=True`
    - `synthetic_gap_threshold_action=diagnostic`
    - `warnings=[]`
    - `synthetic_rows_pct=42.062657`
    - `max_synthetic_gap_minutes=118`
    - `vendor_policy=databento_ohlcv_1m_trade_derived_no_bar_no_trade`
    - `vendor_status=synthetic_thresholds_diagnostic_vendor_backed_provenance`
    - `status_missing=181845`
    - `statistics_missing=192`
  - `Test-Path data\causal_base_candidates\_not_written\6M\2015.parquet` returned `False`.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - `git diff --name-only -- configs\data_manifest.yaml data` returned no paths.
- Important current state:
  - The previously generated readiness report `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_418_source_gap_fail_closed.json` is stale under the new policy. It still records the old `6M:2015` FAIL because it was generated before this change.
  - Under current code/config, the direct read-only `6M:2015` check no longer fails on synthetic OHLCV gaps.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build was not run.
  - No provider/network commands, DBN source mutation, `data/raw` mutation, `configs/data_manifest.yaml` change, prediction/model/feature output, cleanup, staging, commit, config promotion, or research-use approval occurred.
- Unresolved blockers:
  - Severe: broad readiness evidence must be regenerated under the new vendor-backed policy before any build.
  - Severe: prior source-gap fail-closed include artifacts are now policy-stale for the OHLCV no-trade issue. They should not be treated as the final desired broad scope without a fresh readiness reconciliation.
  - Severe: non-OHLCV blockers, especially the confirmed `6M:2012` roll-maturity backstep, remain separate and are not fixed by vendor-backed OHLCV no-trade provenance.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.

Current repo/task state:
- Phase 2 code/config now uses vendor-backed OHLCV no-trade provenance instead of requiring local L1/local-trades self-proof for every missing OHLCV minute.
- Changed files from the policy implementation:
  - scripts/phase2_causal_base/build_causal_base_data.py
  - configs/alpha_tiered.yaml
  - configs/tier_3.yaml
  - tests/phase2_causal_base/test_build_causal_base_data.py
  - CODEX_HANDOFF.md
- Focused tests passed: python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q -> 126 passed.
- Read-only current-code check for data/raw/6M/2015.parquet returned status=PASS with synthetic_rows_pct=42.062657 and synthetic_gap_threshold_action=diagnostic.
- The old 418-row readiness report is stale because it was generated before the vendor-backed policy change.
- Candidate build root still does not exist:
  data/causal_base_candidates/broad_manifest_527_rebuild_v1
- Broad build has not run.

Goal:
- Produce a decision-complete plan for the next broad_manifest_527_rebuild_v1 step under the new vendor-backed OHLCV no-trade policy.
- The plan must reconcile stale source-gap fail-closed include artifacts, regenerate bounded readiness-only evidence, preserve separate handling for non-OHLCV blockers like 6M:2012 roll maturity, and continue to scoped build only if explicit gates pass.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not run broad build unless a fresh readiness-only preflight reaches PASS for an exact approved include scope.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or broader research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Output only the final copy-paste GOAL MODE prompt in one fenced text block.
2. The GOAL MODE prompt must:
   - start from Get-Location, git status --short, and CODEX_HANDOFF.md;
   - verify the vendor-backed policy is active;
   - choose the correct include scope under the new policy, preferably restoring source-gap rows that are now vendor-provenance diagnostic while preserving/excluding true non-OHLCV blockers only with explicit approval;
   - run readiness-only preflight first;
   - stop if readiness fails, scope broadens, or an approval is missing;
   - run the scoped build only after readiness-only PASS;
   - validate built-not-promoted status and stop before config promotion/modeling/research use.
```

## Broad Manifest 527 6M 2014 Source-Gap Excluded; 418-Row Readiness Blocked On 6M 2015 - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the conditional `6M:2014` disposition path from the pasted GOAL MODE prompt. Diagnose `6M:2014`, fail-closed exclude it only if it proves the same true source-gap pattern, then continue to readiness-only preflight and build only if readiness passes.
- Scope executed:
  - Confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` did not exist before this gate.
  - Confirmed the 419-row include contained `6M:2014`, excluded `6M:2013` and `6M:2012`, had 42 fail-closed pairs, and kept 66 deferred policy-review pairs excluded.
  - Confirmed the 419-row readiness blocker was exactly `6M:2014` with `synthetic threshold breached: rows_pct=52.265632 max_gap_minutes=116`.
  - Ran report-only source-vs-raw diagnosis for `6M:2014`.
  - Because the diagnosis proved the same source-gap pattern, ran exactly one source-gap fail-closed loop iteration.
  - Stopped before broad build because the new 418-row readiness-only preflight returned `FAIL`.
- Diagnosis result:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2014_source_vs_raw_gap_diagnosis.json`
  - `status=PASS`
  - `source_vs_raw_call=raw_timestamp_set_matches_ohlcv_dbn_source_gaps`
  - `timestamp_sets_match=true`
  - `dbn_timestamps_missing_from_raw_count=0`
  - `raw_timestamps_missing_from_dbn_count=0`
  - `interpretation.source_gap_evidence=true`
  - `interpretation.conversion_bug_evidence=false`
  - `raw_rows=160250`
  - `dbn_rows=160250`
- New include artifact:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_418_source_gap_fail_closed.json`
  - `market_years=418`
  - removed pair: `6M:2014`
  - `6M:2013` and `6M:2012` remain absent
  - `excluded_fail_closed_pairs=43`
  - `excluded_deferred_policy_review_pairs=66`
  - `approval_token=APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_418_ROWS_EXCLUDING_SOURCE_GAP_FAIL_CLOSED_ROWS_ONLY`
  - `latest_excluded_pair_due_to_readiness_failure=6M:2014`
  - `latest_excluded_pair_disposition=fail_closed_source_gap_evidence`
  - `broader_modeling_approved=false`
  - `config_promotion_approved=false`
  - `research_use_allowed=false`
- New readiness-only result:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_418_source_gap_fail_closed.json`
  - `status=FAIL`
  - `selected_market_year_count=418`
  - `checked_market_year_count=38`
  - `pending_market_year_count=380`
  - blocker: `6M:2015`
  - reason: `synthetic threshold breached: rows_pct=42.062657 max_gap_minutes=118`
  - `roll_maturity_backstep_count=0`
  - `status_enrichment_missing_rows=181845`
  - `statistics_enrichment_missing_rows=192`
- Loop summary:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2014_fail_closed_loop_summary.json`
  - `status=STOPPED`
  - `stop_reason=max_iterations_reached_1`
  - `iterations=1`
  - `build_executed=false`
  - `provider_or_network_call=false`
  - `data_raw_mutated=false`
  - `config_mutated=false`
- Build state:
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - Generated report artifacts:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2014_source_vs_raw_gap_diagnosis.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2014_source_vs_raw_gap_diagnosis.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_418_source_gap_fail_closed.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_418_source_gap_fail_closed.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_418_source_gap_fail_closed.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2014_fail_closed_loop_summary.json`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\50401f24-302f-4dc6-a57f-495fd1b2257c\pasted-text-1.txt`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 170`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Parsed and asserted current 419-row include/readiness state.
  - `python -m scripts.validation.diagnose_6a_2010_source_vs_raw_gaps --market 6M --year 2014 --raw-root data\raw --dbn-root data\dbn\ohlcv_1m --readiness-json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_419_source_gap_fail_closed.json --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2014_source_vs_raw_gap_diagnosis.json --md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2014_source_vs_raw_gap_diagnosis.md`
  - Parsed and asserted `6M:2014` source-vs-raw diagnosis gate fields.
  - `python -m scripts.validation.run_broad_manifest_source_gap_fail_closed_loop --include reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_419_source_gap_fail_closed.json --readiness reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_419_source_gap_fail_closed.json --max-iterations 1 --summary-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2014_fail_closed_loop_summary.json`
  - Parsed and asserted the 418-row include, 418-row readiness, and loop summary.
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
- Validation:
  - `6M:2014` diagnosis proved true source-gap pattern and no conversion bug evidence.
  - 418-row include parse checks passed: removed exactly `6M:2014`; no added rows; count `418`; deferred count `66`; fail-closed count `43`; approval token present; promotion/research flags false.
  - 418-row readiness-only preflight ran and returned `FAIL` before build execution.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Unresolved blockers:
  - Severe: 418-row readiness-only preflight failed on `6M:2015`.
  - Severe: broad build remains blocked because readiness-only status is `FAIL`.
- Safety:
  - No provider/network commands were run.
  - No DBN source, `data/raw`, configs, predictions, models, feature matrices, cleanup targets, staging, commit, config promotion, or research-use action was performed.
  - No broad build was run.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.

Current blocker:
- `6M:2014` has been fail-closed excluded after source-vs-raw diagnosis proved the same true source-gap pattern.
- Current include:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_418_source_gap_fail_closed.json
- Current readiness:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_418_source_gap_fail_closed.json
- Current severe blocker:
  - market-year=6M:2015
  - reason=synthetic threshold breached: rows_pct=42.062657 max_gap_minutes=118
  - roll_maturity_backstep_count=0
  - status_missing=181845
  - statistics_missing=192
  - selected_market_year_count=418
  - checked_market_year_count=38
  - pending_market_year_count=380
- data/causal_base_candidates/broad_manifest_527_rebuild_v1 still does not exist.
- Broad build was not run.

Goal:
- Produce a decision-complete implementation plan to diagnose and disposition the `6M:2015` synthetic-gap blocker, then continue the broad_manifest_527_rebuild_v1 approval-to-build path only if explicit gates pass.
- If row-level evidence proves the same true source-gap pattern as the previously fail-closed source-gap rows, plan the exact next fail-closed exclusion path.
- If evidence points to a different blocker type, stop at the appropriate decision gate.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml or configs/alpha_tiered.yaml.
- Do not run the broad build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Output only the final copy-paste GOAL MODE prompt in one fenced text block.
2. The GOAL MODE prompt must cover read-only row-level diagnosis of `6M:2015`, exact disposition options, approval gates, stop conditions, readiness-only verification, and built-not-promoted stopping rules if the path later reaches PASS.
```

## Broad Manifest 527 6M 2013 Source-Gap Excluded; 419-Row Readiness Blocked On 6M 2014 - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the conditional `6M:2013` disposition path from the pasted GOAL MODE prompt. Diagnose `6M:2013`, fail-closed exclude it only if it proves the same true source-gap pattern, then continue to readiness-only preflight and build only if readiness passes.
- Scope executed:
  - Confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` did not exist before this gate.
  - Confirmed the 420-row include contained `6M:2013`, excluded `6M:2012`, had 41 fail-closed pairs, and kept 66 deferred policy-review pairs excluded.
  - Confirmed the 420-row readiness blocker was exactly `6M:2013` with `synthetic threshold breached: rows_pct=49.085867 max_gap_minutes=113`.
  - Ran report-only source-vs-raw diagnosis for `6M:2013`.
  - Because the diagnosis proved the same source-gap pattern, ran exactly one source-gap fail-closed loop iteration.
  - Stopped before broad build because the new 419-row readiness-only preflight returned `FAIL`.
- Diagnosis result:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2013_source_vs_raw_gap_diagnosis.json`
  - `status=PASS`
  - `source_vs_raw_call=raw_timestamp_set_matches_ohlcv_dbn_source_gaps`
  - `timestamp_sets_match=true`
  - `dbn_timestamps_missing_from_raw_count=0`
  - `raw_timestamps_missing_from_dbn_count=0`
  - `interpretation.source_gap_evidence=true`
  - `interpretation.conversion_bug_evidence=false`
  - `raw_rows=174219`
  - `dbn_rows=174219`
- New include artifact:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_419_source_gap_fail_closed.json`
  - `market_years=419`
  - removed pair: `6M:2013`
  - `6M:2012` remains absent
  - `excluded_fail_closed_pairs=42`
  - `excluded_deferred_policy_review_pairs=66`
  - `approval_token=APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_419_ROWS_EXCLUDING_SOURCE_GAP_FAIL_CLOSED_ROWS_ONLY`
  - `latest_excluded_pair_due_to_readiness_failure=6M:2013`
  - `latest_excluded_pair_disposition=fail_closed_source_gap_evidence`
  - `broader_modeling_approved=false`
  - `config_promotion_approved=false`
  - `research_use_allowed=false`
- New readiness-only result:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_419_source_gap_fail_closed.json`
  - `status=FAIL`
  - `selected_market_year_count=419`
  - `checked_market_year_count=38`
  - `pending_market_year_count=381`
  - blocker: `6M:2014`
  - reason: `synthetic threshold breached: rows_pct=52.265632 max_gap_minutes=116`
  - `roll_maturity_backstep_count=0`
  - `status_enrichment_missing_rows=160250`
  - `statistics_enrichment_missing_rows=149`
- Loop summary:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2013_fail_closed_loop_summary.json`
  - `status=STOPPED`
  - `stop_reason=max_iterations_reached_1`
  - `iterations=1`
  - `build_executed=false`
  - `provider_or_network_call=false`
  - `data_raw_mutated=false`
  - `config_mutated=false`
- Build state:
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - Generated report artifacts:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2013_source_vs_raw_gap_diagnosis.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2013_source_vs_raw_gap_diagnosis.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_419_source_gap_fail_closed.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_419_source_gap_fail_closed.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_419_source_gap_fail_closed.md`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2013_fail_closed_loop_summary.json`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\11360027-686d-47e4-9f44-416a25cd2caa\pasted-text-1.txt`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 160`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Parsed and asserted current 420-row include/readiness state.
  - `python -m scripts.validation.diagnose_6a_2010_source_vs_raw_gaps --market 6M --year 2013 --raw-root data\raw --dbn-root data\dbn\ohlcv_1m --readiness-json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_420_excluding_6M_2012_roll_maturity.json --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2013_source_vs_raw_gap_diagnosis.json --md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2013_source_vs_raw_gap_diagnosis.md`
  - Parsed and asserted `6M:2013` source-vs-raw diagnosis gate fields.
  - `python -m scripts.validation.run_broad_manifest_source_gap_fail_closed_loop --include reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_420_excluding_6M_2012_roll_maturity.json --readiness reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_420_excluding_6M_2012_roll_maturity.json --max-iterations 1 --summary-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2013_fail_closed_loop_summary.json`
  - Parsed and asserted the 419-row include, 419-row readiness, and loop summary.
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
- Validation:
  - `6M:2013` diagnosis proved true source-gap pattern and no conversion bug evidence.
  - 419-row include parse checks passed: removed exactly `6M:2013`; no added rows; count `419`; deferred count `66`; fail-closed count `42`; approval token present; promotion/research flags false.
  - 419-row readiness-only preflight ran and returned `FAIL` before build execution.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Unresolved blockers:
  - Severe: 419-row readiness-only preflight failed on `6M:2014`.
  - Severe: broad build remains blocked because readiness-only status is `FAIL`.
- Safety:
  - No provider/network commands were run.
  - No DBN source, `data/raw`, configs, predictions, models, feature matrices, cleanup targets, staging, commit, config promotion, or research-use action was performed.
  - No broad build was run.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.

Current blocker:
- `6M:2013` has been fail-closed excluded after source-vs-raw diagnosis proved the same true source-gap pattern.
- Current include:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_419_source_gap_fail_closed.json
- Current readiness:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_419_source_gap_fail_closed.json
- Current severe blocker:
  - market-year=6M:2014
  - reason=synthetic threshold breached: rows_pct=52.265632 max_gap_minutes=116
  - roll_maturity_backstep_count=0
  - status_missing=160250
  - statistics_missing=149
  - selected_market_year_count=419
  - checked_market_year_count=38
  - pending_market_year_count=381
- data/causal_base_candidates/broad_manifest_527_rebuild_v1 still does not exist.
- Broad build was not run.

Goal:
- Produce a decision-complete implementation plan to diagnose and disposition the `6M:2014` synthetic-gap blocker, then continue the broad_manifest_527_rebuild_v1 approval-to-build path only if explicit gates pass.
- If row-level evidence proves the same true source-gap pattern as the previously fail-closed source-gap rows, plan the exact next fail-closed exclusion path.
- If evidence points to a different blocker type, stop at the appropriate decision gate.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml or configs/alpha_tiered.yaml.
- Do not run the broad build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Output only the final copy-paste GOAL MODE prompt in one fenced text block.
2. The GOAL MODE prompt must cover read-only row-level diagnosis of `6M:2014`, exact disposition options, approval gates, stop conditions, readiness-only verification, and built-not-promoted stopping rules if the path later reaches PASS.
```

## Broad Manifest 527 6M 2012 Fail-Closed Excluded; 420-Row Readiness Blocked On 6M 2013 - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement selected fail-closed disposition for `6M:2012` using approval token `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY`, then continue only through the readiness-only gate and build only if readiness passes.
- Scope executed:
  - Confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` did not exist before the gate.
  - Confirmed the 421-row include contained `6M:2012`, with 421 included market-years, 40 fail-closed pairs, and 66 deferred policy-review pairs.
  - Confirmed post-refresh readiness was still `FAIL` on `6M:2012` with `roll maturity sequence not monotonic: backsteps=1`.
  - Generated the 420-row include that removes exactly `6M:2012` and adds it to fail-closed exclusions.
  - Ran the 420-row readiness-only preflight.
  - Stopped before broad build because readiness-only status was `FAIL`.
- New include artifact:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_420_excluding_6M_2012_roll_maturity.json`
  - `market_years=420`
  - removed pair: `6M:2012`
  - `excluded_fail_closed_pairs=41`
  - `excluded_deferred_policy_review_pairs=66`
  - `approval_token=APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY`
  - `build_approved=true`
  - `broader_modeling_approved=false`
  - `config_promotion_approved=false`
  - `research_use_allowed=false`
- New readiness-only result:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_420_excluding_6M_2012_roll_maturity.json`
  - `status=FAIL`
  - `selected_market_year_count=420`
  - `checked_market_year_count=38`
  - `pending_market_year_count=382`
  - blocker: `6M:2013`
  - reason: `synthetic threshold breached: rows_pct=49.085867 max_gap_minutes=113`
  - `roll_maturity_backstep_count=0`
  - `status_enrichment_missing_rows=174219`
  - `statistics_enrichment_missing_rows=15`
- Build state:
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - Generated report artifacts:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_420_excluding_6M_2012_roll_maturity.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_420_excluding_6M_2012_roll_maturity.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_420_excluding_6M_2012_roll_maturity.md`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\aceb5bca-69bf-4cd6-b89a-dd26d4ea999a\pasted-text-1.txt`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Parsed the 421-row include and post-refresh readiness JSON.
  - Generated the 420-row include with structured JSON parsing/writing.
  - Parsed the 420-row include and asserted exact one-row exclusion, counts, approval token, and false promotion/research flags.
  - `rg -n "APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY|broader_modeling_approved|config_promotion_approved|research_use_allowed|6M:2012" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_420_excluding_6M_2012_roll_maturity.json`
  - `python -m scripts.phase2_causal_base.build_causal_base_data --profile all_raw --raw-root data\raw --output-root data\causal_base_candidates\broad_manifest_527_rebuild_v1 --reports-root reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 --raw-alignment-report reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_all_raw_alignment.json --market-year-include-list reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_420_excluding_6M_2012_roll_maturity.json --readiness-only --readiness-json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_420_excluding_6M_2012_roll_maturity.json --readiness-md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_420_excluding_6M_2012_roll_maturity.md`
  - Parsed the 420-row readiness JSON.
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `git status --short`
- Validation:
  - 420-row include parse checks passed: removed exactly `6M:2012`; no added rows; count `420`; deferred count `66`; fail-closed count `41`; approval token present; promotion/research flags false.
  - 420-row readiness-only preflight ran and returned `FAIL` before build execution.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False` after the failed readiness gate.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Unresolved blockers:
  - Severe: 420-row readiness-only preflight failed on `6M:2013`.
  - Severe: broad build remains blocked because readiness-only status is `FAIL`.
- Safety:
  - No provider/network commands were run.
  - No DBN source, `data/raw`, configs, predictions, models, feature matrices, cleanup targets, staging, commit, config promotion, or research-use action was performed.
  - No broad build was run.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.

Current blocker:
- `6M:2012` has been fail-closed excluded under approval token `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY`.
- Current include:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_420_excluding_6M_2012_roll_maturity.json
- Current readiness:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_420_excluding_6M_2012_roll_maturity.json
- Current severe blocker:
  - market-year=6M:2013
  - reason=synthetic threshold breached: rows_pct=49.085867 max_gap_minutes=113
  - roll_maturity_backstep_count=0
  - status_missing=174219
  - statistics_missing=15
  - selected_market_year_count=420
  - checked_market_year_count=38
  - pending_market_year_count=382
- data/causal_base_candidates/broad_manifest_527_rebuild_v1 still does not exist.
- Broad build was not run.

Goal:
- Produce a decision-complete implementation plan to diagnose and disposition the `6M:2013` synthetic-gap blocker, then continue the broad_manifest_527_rebuild_v1 approval-to-build path only if explicit gates pass.
- If row-level evidence proves the same true source-gap pattern as the previously fail-closed source-gap rows, plan the exact next fail-closed exclusion path.
- If evidence points to a different blocker type, stop at the appropriate decision gate.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml or configs/alpha_tiered.yaml.
- Do not run the broad build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Output only the final copy-paste GOAL MODE prompt in one fenced text block.
2. The GOAL MODE prompt must cover read-only row-level diagnosis of `6M:2013`, exact disposition options, approval gates, stop conditions, readiness-only verification, and built-not-promoted stopping rules if the path later reaches PASS.
```

## Broad Manifest 527 6M 2012 Scoped Refresh Completed But Readiness Still Failed - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: try a scoped provider refresh for only `6M:2012` OHLCV + definition, rebuild only `data/raw/6M/2012.parquet`, then rerun diagnostics and readiness-only preflight. Do not run broad build.
- Explicit approval token used:
  - `APPROVE_6M_2012_SCOPED_PROVIDER_REFRESH_OHLCV_DEFINITION_AND_RAW_REBUILD_ONLY`
- Scope executed:
  - Confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` did not exist.
  - Confirmed current readiness was blocked on `6M:2012`, reason `roll maturity sequence not monotonic: backsteps=1`.
  - Estimated provider refresh cost for exactly `6M:2012` OHLCV and definition only.
  - Refreshed exactly two DBN source files.
  - Rebuilt exactly `data/raw/6M/2012.parquet`.
  - Reran source-vs-raw diagnosis, roll-maturity diagnosis, and 421-row readiness-only preflight.
  - Stopped before broad build because post-refresh readiness remained `FAIL`.
- Current result:
  - Provider estimates:
    - OHLCV `6M:2012`: `$0.0000`, `TOTAL_ESTIMATE_ERRORS 0`.
    - Definition `6M:2012`: `$0.0000`, `TOTAL_ESTIMATE_ERRORS 0`.
  - Refreshed DBN targets:
    - `data/dbn/ohlcv_1m/6M/2012/2012-01-01_2013-01-01.dbn.zst`
      - job `GLBX-20260629-YBUSRP7MBY`
      - sha256 `94ccf0ce87022a60d964b214b87378b4d566f43e56218780443353e89b389022`
      - bytes `1836661`
    - `data/dbn/definition/6M/2012/2012-01-01_2013-01-01.dbn.zst`
      - job `GLBX-20260629-WKX7RALQGA`
      - sha256 `7abf6ccaaa2d40a305f2d6dafa2ea7ea01526c95be1db2b0cd4d90912d07bcad`
      - bytes `364179`
  - Raw conversion:
    - output `data/raw/6M/2012.parquet`
    - rows `186495`
    - sha256 `c120b360abdb21d5546e053e31588bf0589737e5a9fdb56982587e3b794a02f8`
    - first timestamp `2012-01-03T11:00:00+00:00`
    - last timestamp `2012-12-31T21:57:00+00:00`
    - optional schema warning count `0`
    - status matched rows `2386`, status missing rows `184109`, match rate `0.012794`
    - statistics matched rows `186366`, statistics missing rows `129`, match rate `0.999308`
  - Post-refresh source-vs-raw diagnosis:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_source_vs_raw_gap_diagnosis.json`
    - `status=PASS`
    - `source_vs_raw_call=raw_timestamp_set_matches_ohlcv_dbn_source_gaps`
    - `raw_rows=186495`
    - `dbn_rows=186495`
    - `timestamp_sets_match=true`
    - `dbn_timestamps_missing_from_raw_count=0`
    - `raw_timestamps_missing_from_dbn_count=0`
  - Post-refresh roll-maturity diagnosis:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_roll_maturity_diagnosis.json`
    - `status=PASS`
    - `disposition_call=roll_maturity_backstep_confirmed_in_raw`
    - `computed_backstep_count=1`
    - `readiness_roll_maturity_backstep_count=1`
    - `computed_matches_readiness=true`
  - Post-refresh readiness-only preflight:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6M_2012_refresh.json`
    - `status=FAIL`
    - `selected_market_year_count=421`
    - `checked_market_year_count=38`
    - `pending_market_year_count=383`
    - blocker `6M:2012`
    - reason `roll maturity sequence not monotonic: backsteps=1`
    - warning also present: `synthetic threshold breached: rows_pct=46.563343 max_gap_minutes=116`
    - `status_enrichment_missing_rows=184109`
    - `statistics_enrichment_missing_rows=129`
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - Approved data mutations:
    - `data\dbn\ohlcv_1m\6M\2012\2012-01-01_2013-01-01.dbn.zst`
    - `data\dbn\ohlcv_1m\6M\2012\2012-01-01_2013-01-01.dbn.zst.manifest.json`
    - `data\dbn\definition\6M\2012\2012-01-01_2013-01-01.dbn.zst`
    - `data\dbn\definition\6M\2012\2012-01-01_2013-01-01.dbn.zst.manifest.json`
    - `data\raw\6M\2012.parquet`
- Generated report artifacts in this scope:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_ohlcv_1m_estimate_plan.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_definition_estimate_plan.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_ohlcv_1m_download_plan.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_definition_download_plan.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_convert\databento_convert_results.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_convert\raw_ingest_manifest.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_convert\raw_parquet_manifest.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_source_vs_raw_gap_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_source_vs_raw_gap_diagnosis.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_roll_maturity_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_roll_maturity_diagnosis.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6M_2012_refresh.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6M_2012_refresh.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\6a0920b1-084c-4c49-a376-9515147649eb\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 140`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Parsed current 421-row include and readiness artifacts.
  - `python -m scripts.phase1A_download.download_databento_raw --universe custom --markets 6M --schema ohlcv-1m --start 2012-01-01 --end 2013-01-01 --dbn-root data\dbn\ohlcv_1m --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628 --plan-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_ohlcv_1m_estimate_plan.json --mode download-dbn --workers 1 --estimate-cost --overwrite`
  - `python -m scripts.phase1A_download.download_databento_raw --universe custom --markets 6M --schema definition --start 2012-01-01 --end 2013-01-01 --dbn-root data\dbn --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628 --plan-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_definition_estimate_plan.json --mode download-dbn --workers 1 --estimate-cost --overwrite`
  - `python -m scripts.phase1A_download.download_databento_raw --universe custom --markets 6M --schema ohlcv-1m --start 2012-01-01 --end 2013-01-01 --dbn-root data\dbn\ohlcv_1m --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628 --plan-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_ohlcv_1m_download_plan.json --mode download-dbn --workers 1 --overwrite`
  - `python -m scripts.phase1A_download.download_databento_raw --universe custom --markets 6M --schema definition --start 2012-01-01 --end 2013-01-01 --dbn-root data\dbn --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628 --plan-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_definition_download_plan.json --mode download-dbn --workers 1 --overwrite`
  - `python -m scripts.phase1B_convert.convert_databento_raw --universe custom --markets 6M --start 2012-01-01 --end 2013-01-01 --dbn-root data\dbn\ohlcv_1m --raw-root data\raw --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_convert --include-optional-schemas status,statistics --optional-dbn-root data\dbn --definition-dbn-root data\dbn\definition --optional-schema-policy require --offline-local-conditions --overwrite`
  - `python -m scripts.validation.diagnose_6a_2010_source_vs_raw_gaps --market 6M --year 2012 --raw-root data\raw --dbn-root data\dbn\ohlcv_1m --readiness-json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_421_source_gap_fail_closed.json --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_source_vs_raw_gap_diagnosis.json --md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_source_vs_raw_gap_diagnosis.md`
  - `python -m scripts.validation.diagnose_roll_maturity_blocker --market 6M --year 2012 --raw-root data\raw --readiness-json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_421_source_gap_fail_closed.json --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_roll_maturity_diagnosis.json --md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_refresh_roll_maturity_diagnosis.md`
  - `python -m scripts.phase2_causal_base.build_causal_base_data --profile all_raw --raw-root data\raw --output-root data\causal_base_candidates\broad_manifest_527_rebuild_v1 --reports-root reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 --raw-alignment-report reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_all_raw_alignment.json --market-year-include-list reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_421_source_gap_fail_closed.json --readiness-only --readiness-json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6M_2012_refresh.json --readiness-md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6M_2012_refresh.md`
  - `python -m pytest tests\validation\test_diagnose_roll_maturity_blocker.py tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py tests\phase1A_download\test_download_databento_raw.py tests\phase2_causal_base\test_build_causal_base_data.py`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `git status --short`
- Validation:
  - Focused tests passed: `227 passed`.
  - Final `git diff --name-only -- configs` returned no paths.
  - Final `git diff --name-only -- data` returned no paths because approved refreshed data artifacts are not tracked.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
- Unresolved blockers:
  - Severe: post-refresh 421-row readiness-only preflight still failed on `6M:2012`.
  - Severe: `6M:2012` roll maturity backstep remains confirmed in refreshed raw evidence.
  - Severe: broad build remains blocked because readiness-only status is `FAIL`.
- Safety:
  - Provider/network commands were run only for `6M:2012` OHLCV and definition.
  - No status/statistics provider refresh was run.
  - No DBN source outside `data/dbn/ohlcv_1m/6M/2012/**` and `data/dbn/definition/6M/2012/**` was intentionally mutated.
  - No raw file outside `data/raw/6M/2012.parquet` was intentionally mutated.
  - No `configs/**` mutation was performed.
  - No broad build, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, config promotion, or research-use approval was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.

Current blocker:
- Scoped OHLCV + definition refresh for 6M:2012 completed, and data/raw/6M/2012.parquet was rebuilt.
- Post-refresh readiness still fails on 6M:2012:
  - reason=roll maturity sequence not monotonic: backsteps=1
  - synthetic_rows_pct=46.563343
  - max_gap_minutes=116
  - status_missing=184109
  - statistics_missing=129
- Broad build has not run.
- data/causal_base_candidates/broad_manifest_527_rebuild_v1 still does not exist.

Goal:
- Produce a decision-complete implementation plan to clear or disposition the still-confirmed 6M:2012 blocker after scoped refresh failed to repair it.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml or configs/alpha_tiered.yaml.
- Do not run the broad build unless an exact selected disposition approves the next gated path and readiness-only preflight reaches PASS.
- Preserve broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Decision options to include:
- KEEP_6M_2012_FAIL_CLOSED_NO_BUILD
- APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY
- APPROVE_6M_2012_ACCEPTED_ROLL_MATURITY_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY

Plan output required:
1. Output only one final copy-paste GOAL MODE prompt if an exact disposition token is selected.
2. If no exact token is selected, output only the missing-decision blocker and exact token choices.
```

## Broad Manifest 527 6M 2012 Roll Maturity Diagnosis Blocked On Disposition - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: diagnose and disposition the current `6M:2012` roll maturity blocker; continue the broad_manifest_527_rebuild_v1 approval-to-build path only if explicit gates pass.
- Scope executed:
  - Confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` does not exist.
  - Confirmed the current 421-row readiness-only artifact is still blocked on `6M:2012`, reason `roll maturity sequence not monotonic: backsteps=1`.
  - Ran source-vs-raw context only for `6M:2012`.
  - Added a focused report-only roll-maturity diagnostic and tests.
  - Ran the real `6M:2012` roll-maturity diagnosis and wrote an explicit disposition request.
  - Stopped before generating a 420-row include or build because selected disposition is `NONE_SELECTED`.
- Current result:
  - Current include artifact:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_421_source_gap_fail_closed.json`
    - `market_years=421`
    - includes `6M:2012`
    - `excluded_fail_closed_pairs=40`
    - `excluded_deferred_policy_review_pairs=66`
    - `broader_modeling_approved=false`
    - `config_promotion_approved=false`
    - `research_use_allowed=false`
  - Current readiness-only artifact:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_421_source_gap_fail_closed.json`
    - `status=FAIL`
    - blocker: `6M:2012`
    - reason: `roll maturity sequence not monotonic: backsteps=1`
    - warning also present: `synthetic threshold breached: rows_pct=46.563343 max_gap_minutes=116`
  - Source-vs-raw context:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_vs_raw_gap_diagnosis.json`
    - `status=PASS`
    - `source_vs_raw_call=raw_timestamp_set_matches_ohlcv_dbn_source_gaps`
    - `raw_rows=186495`
    - `dbn_rows=186495`
    - `timestamp_sets_match=true`
    - `dbn_timestamps_missing_from_raw_count=0`
    - `raw_timestamps_missing_from_dbn_count=0`
  - Roll-maturity diagnosis:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_roll_maturity_diagnosis.json`
    - `status=PASS`
    - `disposition_call=roll_maturity_backstep_confirmed_in_raw`
    - `computed_backstep_count=1`
    - `readiness_roll_maturity_backstep_count=1`
    - `computed_matches_readiness=true`
    - `raw_rows=186495`
    - `status_missing_rows=184109`
    - `statistics_missing_rows=129`
  - Disposition request:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2012_roll_maturity_disposition_request.json`
    - `status=AWAITING_HUMAN_6M_2012_DISPOSITION`
    - `selected_disposition=NONE_SELECTED`
    - `recommended_default=APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY`
    - `build_execution_allowed_now=false`
    - `broader_modeling_approved=false`
    - `config_promotion_approved=false`
    - `research_use_allowed=false`
- Allowed exact disposition tokens:
  - `KEEP_6M_2012_FAIL_CLOSED_NO_BUILD`
  - `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY`
  - `APPROVE_6M_2012_ACCEPTED_ROLL_MATURITY_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY`
  - `APPROVE_6M_2012_LOCAL_ROLL_MATURITY_CODE_REPAIR_ONLY`
  - `APPROVE_6M_2012_RAW_REBUILD_AFTER_LOCAL_ROLL_METADATA_CODE_REPAIR_ONLY`
- Files changed in this scope:
  - `scripts\validation\diagnose_roll_maturity_blocker.py`
  - `tests\validation\test_diagnose_roll_maturity_blocker.py`
  - `CODEX_HANDOFF.md`
- Generated report artifacts in this scope:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_vs_raw_gap_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_source_vs_raw_gap_diagnosis.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_roll_maturity_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6M_2012_roll_maturity_diagnosis.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2012_roll_maturity_disposition_request.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6M_2012_roll_maturity_disposition_request.md`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\cd230a7e-421c-4bd6-a4bf-c237f60a65f9\pasted-text-1.txt`
  - `Get-Content -Raw AGENTS.md`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Parsed the current 421-row include/readiness JSON artifacts.
  - `python -m scripts.validation.diagnose_6a_2010_source_vs_raw_gaps --market 6M --year 2012 ...`
  - `python -m pytest tests\validation\test_diagnose_roll_maturity_blocker.py`
  - `python -m scripts.validation.diagnose_roll_maturity_blocker --market 6M --year 2012 ...`
  - `python -m pytest tests\validation\test_diagnose_roll_maturity_blocker.py tests\phase2_causal_base\test_build_causal_base_data.py`
  - Parsed the generated source-vs-raw diagnosis, roll-maturity diagnosis, and disposition request.
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
- Validation:
  - Focused roll diagnostic tests passed: `4 passed`.
  - Focused roll diagnostic plus Phase 2 causal-base tests passed: `128 passed`.
  - Final `git diff --name-only -- configs` returned no paths.
  - Final `git diff --name-only -- data` returned no paths.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
- Unresolved blockers:
  - Severe: `6M:2012` roll maturity backstep is confirmed in current raw evidence.
  - Severe: selected disposition remains `NONE_SELECTED`, so no 420-row include, readiness preflight, or broad build is approved.
  - Severe: broad build remains blocked because current readiness-only status is `FAIL`.
- Safety:
  - No provider/network command was run.
  - No DBN source file was mutated.
  - No `data/raw/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No broad build, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, config promotion, or research-use approval was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.

Current blocker:
- 6M:2012 roll maturity backstep is confirmed in raw evidence.
- Disposition request artifact:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_6M_2012_roll_maturity_disposition_request.json
- selected_disposition=NONE_SELECTED
- build_execution_allowed_now=false
- broad build has not run.

Goal:
- Select exactly one 6M:2012 disposition token, or keep the build blocked.

Allowed exact disposition tokens:
- KEEP_6M_2012_FAIL_CLOSED_NO_BUILD
- APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY
- APPROVE_6M_2012_ACCEPTED_ROLL_MATURITY_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY
- APPROVE_6M_2012_LOCAL_ROLL_MATURITY_CODE_REPAIR_ONLY
- APPROVE_6M_2012_RAW_REBUILD_AFTER_LOCAL_ROLL_METADATA_CODE_REPAIR_ONLY

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml or configs/alpha_tiered.yaml.
- Do not run the broad build unless an exact selected disposition approves the next gated path and readiness-only preflight reaches PASS.
- Preserve broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. If no exact token is selected, output only the missing-decision blocker and the exact token choices.
2. If an exact token is selected, output only one final copy-paste GOAL MODE prompt that implements that selected path through the next explicit gate.
```

## Broad Manifest 527 Source-Gap Loop Stopped On 6M 2012 Roll Maturity - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: fix `6A:2014` the same way prior `6A` source-gap blockers were fixed, then continue market-years one by one and fail-closed exclude only rows with the same proven source-vs-raw gap pattern.
- Scope executed:
  - Confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` did not exist.
  - Confirmed the current 425-row readiness-only artifact was blocked on `6J:2012` with a synthetic threshold breach.
  - Added a bounded source-gap fail-closed loop helper and tests.
  - Continued the loop from the 425-row include, excluding only rows where raw timestamps exactly matched local OHLCV DBN timestamps with zero missing timestamps either way.
  - Stopped before build when the next blocker changed class from synthetic threshold source gaps to roll maturity monotonicity.
- Current result:
  - Current include artifact:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_421_source_gap_fail_closed.json`
    - `market_years=421`
    - `excluded_fail_closed_pairs=40`
    - latest source-gap fail-closed exclusion: `6M:2011`
    - `approval_token=APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_421_ROWS_EXCLUDING_SOURCE_GAP_FAIL_CLOSED_ROWS_ONLY`
    - `broader_modeling_approved=false`
    - `config_promotion_approved=false`
    - `research_use_allowed=false`
  - Current readiness-only artifact:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_421_source_gap_fail_closed.json`
    - `status=FAIL`
    - `selected_market_year_count=421`
    - `checked_market_year_count=38`
    - `pending_market_year_count=383`
    - blocker: `6M:2012`
    - reason: `roll maturity sequence not monotonic: backsteps=1`
    - `synthetic_rows_pct=46.563343`
    - `max_synthetic_gap_minutes=116`
    - `status_enrichment_missing_rows=184109`
    - `statistics_enrichment_missing_rows=129`
  - Latest loop summary:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_source_gap_fail_closed_loop_summary.json`
    - `status=STOPPED`
    - `stop_reason=non_synthetic_threshold_blocker 6M:2012 roll maturity sequence not monotonic: backsteps=1`
    - `iterations=4`
    - `build_executed=false`
    - `provider_or_network_call=false`
    - `data_raw_mutated=false`
    - `config_mutated=false`
  - Rows fail-closed by the final bounded batch:
    - `6J:2012`
    - `6J:2014`
    - `6M:2010`
    - `6M:2011`
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Files changed in this scope:
  - `scripts\validation\diagnose_6a_2010_source_vs_raw_gaps.py`
  - `tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py`
  - `scripts\validation\run_broad_manifest_source_gap_fail_closed_loop.py`
  - `tests\validation\test_run_broad_manifest_source_gap_fail_closed_loop.py`
  - `CODEX_HANDOFF.md`
- Generated report artifacts in this scope:
  - Per-market source-vs-raw diagnostics for each fail-closed source-gap row.
  - Per-count include and readiness-only artifacts from `458_source_gap_fail_closed` through `421_source_gap_fail_closed`.
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_source_gap_fail_closed_loop_summary.json`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Parsed 425-row and 421-row include/readiness JSON artifacts.
  - `python -m scripts.validation.diagnose_6a_2010_source_vs_raw_gaps --market 6A --year 2014 ...`
  - `python -m scripts.validation.run_broad_manifest_source_gap_fail_closed_loop --include ... --readiness ... --max-iterations ...`
  - `python -m pytest tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py tests\validation\test_run_broad_manifest_source_gap_fail_closed_loop.py tests\validation\test_diagnose_phase2_readiness_blockers.py tests\validation\test_drilldown_phase2_readiness_blockers.py`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
- Validation:
  - Focused tests passed: `15 passed`.
  - Final parsed loop summary confirms the loop stopped because the blocker changed class to roll maturity monotonicity.
  - Final `git diff --name-only -- configs` returned no paths.
  - Final `git diff --name-only -- data` returned no paths.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
- Unresolved blockers:
  - Severe: 421-row readiness-only preflight failed on `6M:2012`.
  - Severe: the current blocker is not the previously approved source-gap fail-closed pattern: `roll maturity sequence not monotonic: backsteps=1`.
  - Severe: broad build remains blocked because readiness-only preflight is `FAIL`.
  - Severe: no approval exists to exclude, repair, refresh, or accept a readiness exception for `6M:2012`.
- Safety:
  - No provider/network command was run.
  - No DBN source file was mutated.
  - No `data/raw/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No broad build, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, config promotion, or research-use approval was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: diagnose and disposition the new `6M:2012` roll maturity monotonicity blocker. Do not continue source-gap fail-closed exclusions unless row-level evidence proves the blocker has returned to the same source-gap pattern and an exact approval covers it.

Context:
- Repo: C:\Users\donny\Desktop\futures_intraday_model
- The source-gap fail-closed loop has reached its approved stop condition.
- Current include:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_421_source_gap_fail_closed.json
- Current readiness:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_421_source_gap_fail_closed.json
- Current readiness result:
  - status=FAIL
  - selected_market_year_count=421
  - checked_market_year_count=38
  - pending_market_year_count=383
  - blocker=6M:2012
  - reason=roll maturity sequence not monotonic: backsteps=1
  - synthetic_rows_pct=46.563343
  - max_gap_minutes=116
  - status_missing=184109
  - statistics_missing=129
- Latest loop summary:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_source_gap_fail_closed_loop_summary.json
- `data/causal_base_candidates/broad_manifest_527_rebuild_v1` still does not exist.
- Broad build was not run.
- No provider/network command was run.
- No config diff and no `data/**` diff were reported.

Goal:
- Produce a decision-complete implementation plan for the `6M:2012` roll maturity blocker, then continue the broad_manifest_527_rebuild_v1 path only if an explicit gate allows it and readiness-only preflight reaches PASS.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not run the broad build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Output only the final copy-paste GOAL MODE prompt in one fenced text block.
2. The GOAL MODE prompt must cover read-only row-level diagnosis of `6M:2012`, exact disposition options, approval gates, stop conditions, readiness-only verification, and built-not-promoted stopping rules if the path later reaches PASS.
```

## Broad Manifest 527 6A 2014 Disposition Implemented, 458-Row Preflight Blocked On 6A 2015 - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: clear or explicitly disposition the `6A:2014` readiness-only blocker for `broad_manifest_527_rebuild_v1`; continue to broad candidate build only if post-disposition readiness-only preflight reaches PASS.
- Scope executed:
  - Established repo state and confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` did not exist.
  - Confirmed the 459-row include had `market_years=459`, included `6A:2014`, and had fail-closed exclusions for `6A:2010` and `6A:2013`.
  - Confirmed the 459-row readiness-only preflight was `FAIL` with one blocker, `6A:2014`.
  - Ran focused tests for the source-vs-raw diagnostic and one-iteration fail-closed loop helper.
  - Ran exactly one fail-closed loop iteration for `6A:2014`.
  - Verified `6A:2014` has the same source-gap pattern as prior fail-closed `6A` rows: raw timestamp set matches local OHLCV DBN timestamp set, with zero missing timestamps either way.
  - Generated a 458-row include excluding `6A:2010`, `6A:2013`, and `6A:2014`.
  - Ran 458-row readiness-only preflight.
  - Stopped before build because readiness-only preflight failed on the next blocker, `6A:2015`.
- Current result:
  - `6A:2014` DBN-vs-raw diagnostic status: `PASS`.
  - `6A:2014` source-vs-raw call: `raw_timestamp_set_matches_ohlcv_dbn_source_gaps`.
  - `6A:2014` raw rows: `308686`.
  - `6A:2014` DBN rows: `308686`.
  - `6A:2014` timestamp sets match: `true`.
  - `6A:2014` DBN timestamps missing from raw: `0`.
  - `6A:2014` raw timestamps missing from DBN: `0`.
  - `6A:2014` raw Phase 2 session candidate gaps: `23857`.
  - `6A:2014` raw synthetic missing estimate: `32938`.
  - 458-row include artifact:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_458_source_gap_fail_closed.json`
    - `approved_ready_row_count=458`
    - `market_years=458`
    - `excluded_fail_closed_pairs=["6A:2010", "6A:2013", "6A:2014"]`
    - `approval_token=APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_458_ROWS_EXCLUDING_SOURCE_GAP_FAIL_CLOSED_ROWS_ONLY`
    - `broader_modeling_approved=false`
    - `config_promotion_approved=false`
    - `research_use_allowed=false`
  - 458-row readiness-only preflight result:
    - `status=FAIL`
    - `selected_market_year_count=458`
    - `market_year_include_count=458`
    - `checked_market_year_count=3`
    - `pending_market_year_count=455`
    - `blocker_count=1`
    - blocker: `6A:2015`
    - reason: `synthetic threshold breached: rows_pct=5.053376 max_gap_minutes=63`
    - `synthetic_rows_pct=5.053376`
    - `max_synthetic_gap_minutes=63`
    - `status_enrichment_missing_rows=300542`
    - `statistics_enrichment_missing_rows=263`
  - One-iteration loop summary:
    - `status=STOPPED`
    - `stop_reason=max_iterations_reached_1`
    - `iterations=1`
    - `build_executed=false`
    - `provider_or_network_call=false`
    - `data_raw_mutated=false`
    - `config_mutated=false`
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
- Generated report artifacts in this scope:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2014_source_vs_raw_gap_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2014_source_vs_raw_gap_diagnosis.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_458_source_gap_fail_closed.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_458_source_gap_fail_closed.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_458_source_gap_fail_closed.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2014_fail_closed_loop_summary.json`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\af7aca09-d1eb-4b9d-bf98-51eb20347b93\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 180`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Parsed `broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010_6A_2013.json`.
  - Parsed `broad_manifest_527_rebuild_phase2_readiness_459_excluding_6A_2010_6A_2013.json`.
  - `git diff --name-only -- configs data\raw data\dbn`
  - Counted candidate-root parquet files under `data\causal_base_candidates\broad_manifest_527_rebuild_v1`.
  - `python -m pytest tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py tests\validation\test_run_broad_manifest_source_gap_fail_closed_loop.py`
  - `python -m scripts.validation.run_broad_manifest_source_gap_fail_closed_loop --include reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010_6A_2013.json --readiness reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_459_excluding_6A_2010_6A_2013.json --max-iterations 1 --summary-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2014_fail_closed_loop_summary.json`
  - Parsed `6A_2014_source_vs_raw_gap_diagnosis.json`.
  - Parsed `broad_manifest_527_rebuild_ready_only_include_458_source_gap_fail_closed.json`.
  - Parsed `broad_manifest_527_rebuild_phase2_readiness_458_source_gap_fail_closed.json`.
  - Parsed `broad_manifest_527_rebuild_6A_2014_fail_closed_loop_summary.json`.
  - Final `git diff --name-only -- configs data\raw data\dbn`
  - Final `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Final candidate-root parquet count.
  - Final `git status --short`
- Validation:
  - Focused tests passed: `4 passed`.
  - `6A:2014` source-vs-raw diagnostic matched the approved fail-closed pattern.
  - 458-row include parse check passed: `market_years=458`, `has_6A_2014=0`, required fail-closed exclusions present, safety flags false.
  - 458-row readiness-only preflight was `FAIL` on `6A:2015`; build gate remains closed.
  - `git diff --name-only -- configs data\raw data\dbn` returned no paths before and after the fail-closed iteration.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False` before and after the fail-closed iteration.
  - Candidate-root parquet count returned `0`.
- Unresolved blockers:
  - Severe: 458-row readiness-only preflight failed on `6A:2015`.
  - Severe: broad build remains blocked because readiness-only preflight is `FAIL`.
  - Severe: no approval exists to exclude, repair, refresh, or accept a readiness exception for `6A:2015`.
- Safety:
  - No provider/network command was run.
  - No DBN source file was mutated.
  - No `data/raw/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No broad build, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, config promotion, or research-use approval was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: clear the new `6A:2015` readiness-only blocker after `6A:2010`, `6A:2013`, and `6A:2014` were fail-closed and excluded.

Context:
- Repo: C:\Users\donny\Desktop\futures_intraday_model
- `6A:2014` was diagnosed as source-level sparsity:
  - raw timestamp set matches local OHLCV DBN timestamp set
  - raw_rows=308686
  - dbn_rows=308686
  - dbn_timestamps_missing_from_raw=0
  - raw_timestamps_missing_from_dbn=0
  - raw_session_candidate_gaps=23857
  - raw_synthetic_missing_estimate=32938
- 458-row include excluding `6A:2010`, `6A:2013`, and `6A:2014` was generated:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_458_source_gap_fail_closed.json
- 458-row readiness-only preflight failed:
  - status=FAIL
  - selected_market_year_count=458
  - checked_market_year_count=3
  - pending_market_year_count=455
  - blocker_count=1
  - blocker=6A:2015
  - reason=synthetic threshold breached: rows_pct=5.053376 max_gap_minutes=63
  - status_missing=300542
  - statistics_missing=263
- `data/causal_base_candidates/broad_manifest_527_rebuild_v1` still does not exist.
- Broad build was not run.
- No provider/network command was run.
- No config diff and no git-tracked data/raw or data/dbn diff.

Goal:
- Produce an implementation plan to clear or disposition the `6A:2015` blocker under explicit gates, then continue the broad_manifest_527_rebuild_v1 path only if readiness-only preflight reaches PASS.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Brief diagnosis.
2. Required evidence for `6A:2015`.
3. Exact disposition options and approval language.
4. Stop conditions.
5. Verification commands.
6. Final copy-paste GOAL MODE PROMPT.
```

## Desktop Guidance File Consolidation Implemented - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the Desktop guidance file consolidation plan for `RESOURCES.md`, `DATA REBUILD.md`, and `You_are_here_updated_current_FINAL_20260628_post_side_aware_commit.txt`.
- Scope executed:
  - Preserved stable quant research guidance from the deleted root `RESOURCES.md` in `docs\quant_research_playbook.md`.
  - Preserved the reusable data-layout audit prompt from the deleted root `DATA REBUILD.md` as `scripts\dev\audit_prompts\04_data_layout_audit_prompt.md`, clearly marked as a prompt template and not current evidence.
  - Updated `scripts\dev\audit_prompts\README.md` to include the new reusable data-layout audit prompt.
  - Updated `scripts\dev\audit_prompts\02_main_adversarial_audit_prompt.md` so active audit guidance points to `docs\quant_research_playbook.md`, not the deleted root `RESOURCES.md`.
  - Kept current mutable project status in `CODEX_HANDOFF.md`.
  - Did not delete, move, or edit the Desktop originals.
  - Did not restore the deleted repo-root `RESOURCES.md` or `DATA REBUILD.md`.
- Current result:
  - `RESOURCES.md` remains conceptually useful but is no longer the active location for durable research guidance.
  - `DATA REBUILD.md` remains stale as current evidence; its useful content is now a reusable prompt template.
  - The Desktop side-aware checkpoint remains historical/consumed by handoff history, not active current state.
  - Current active project blocker remains the broad manifest rebuild readiness gate blocked on `6A:2014`.
- Files changed in this scope:
  - `docs\quant_research_playbook.md`
  - `scripts\dev\audit_prompts\04_data_layout_audit_prompt.md`
  - `scripts\dev\audit_prompts\README.md`
  - `scripts\dev\audit_prompts\02_main_adversarial_audit_prompt.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 160`
  - `git diff -- docs scripts/dev/audit_prompts`
  - `rg -n "DATA REBUILD|You_are_here|RESOURCES\.md" docs scripts README.md CODEX_HANDOFF.md`
  - `git status --short -- docs scripts\dev\audit_prompts CODEX_HANDOFF.md README.md "DATA REBUILD.md" RESOURCES.md`
  - `git diff --check -- docs scripts/dev/audit_prompts README.md CODEX_HANDOFF.md`
  - `rg -n "DATA REBUILD|You_are_here|RESOURCES\.md" .`
  - `git status --short`
  - `git diff --name-only -- data reports`
  - `git diff --name-only -- docs scripts/dev/audit_prompts CODEX_HANDOFF.md README.md`
  - `rg -n "DATA REBUILD|RESOURCES\.md" docs scripts README.md`
  - Final rerun: `git diff --check -- docs scripts/dev/audit_prompts README.md CODEX_HANDOFF.md`
  - Final rerun: `rg -n "DATA REBUILD|RESOURCES\.md" docs scripts README.md`
  - Final rerun: `git status --short`
- Validation:
  - `git diff --check -- docs scripts/dev/audit_prompts README.md CODEX_HANDOFF.md` passed with line-ending warnings only.
  - Wide stale-reference scan returned only `CODEX_HANDOFF.md` consolidation/history entries; no active docs/scripts references to stale root `RESOURCES.md` or `DATA REBUILD.md` remain.
  - Targeted active-doc/script scan returned no `DATA REBUILD` or `RESOURCES.md` references.
  - `git diff --name-only -- data reports` showed only pre-existing report diffs:
    - `reports/data_manifest/master_data_health_matrix.json`
    - `reports/data_manifest/master_data_health_summary.md`
  - No `data/**` diff was reported.
  - Final rerun after this handoff update passed `git diff --check` with line-ending warnings only, targeted active-doc/script scan returned no matches, and final `git status --short` was recorded.
- Unresolved blockers:
  - Medium: worktree remains dirty with unrelated pre-existing changes outside this documentation consolidation.
  - Severe: the active project workflow remains blocked on `6A:2014`; this documentation consolidation does not change data readiness or build approval.
- Safety:
  - No provider/network command was run.
  - No `data/**`, `reports/**`, configs, pipeline/model code, generated artifacts, staging, commit, cleanup, WFA/modeling, prediction generation, build execution, or Desktop file deletion/move was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: clear the new `6A:2014` readiness-only blocker after `6A:2010` and `6A:2013` were fail-closed and excluded.

Context:
- Repo: C:\Users\donny\Desktop\futures_intraday_model
- Desktop guidance consolidation is complete:
  - durable research guidance now lives in docs/quant_research_playbook.md
  - reusable data-layout audit prompt now lives in scripts/dev/audit_prompts/04_data_layout_audit_prompt.md
  - Desktop originals were not deleted, moved, or edited
  - repo-root RESOURCES.md and DATA REBUILD.md remain deleted
- `6A:2013` was diagnosed as source-level sparsity:
  - raw timestamp set matches local OHLCV DBN timestamp set
  - raw_rows=326807
  - dbn_rows=326807
  - dbn_timestamps_missing_from_raw=0
  - raw_timestamps_missing_from_dbn=0
- 459-row include excluding `6A:2010` and `6A:2013` was generated:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010_6A_2013.json
- 459-row readiness-only preflight failed:
  - status=FAIL
  - selected_market_year_count=459
  - checked_market_year_count=3
  - pending_market_year_count=456
  - blocker_count=1
  - blocker=6A:2014
  - reason=synthetic threshold breached: rows_pct=9.641594 max_gap_minutes=29
  - status_missing=308686
  - statistics_missing=92
- `data/causal_base_candidates/broad_manifest_527_rebuild_v1` still does not exist.
- Broad build was not run.
- No provider/network command was run.
- No config diff and no git-tracked data diff were reported in the prior readiness scope.

Goal:
- Produce an implementation plan to clear or disposition the `6A:2014` blocker under explicit gates, then continue the broad_manifest_527_rebuild_v1 path only if readiness-only preflight reaches PASS.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Brief diagnosis.
2. Required evidence for `6A:2014`.
3. Exact disposition options and approval language.
4. Stop conditions.
5. Verification commands.
6. Final copy-paste GOAL MODE PROMPT.
```

## Broad Manifest 527 6A 2013 Disposition Implemented, 459-Row Preflight Blocked On 6A 2014 - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: fix the `6A:2013` blocker the same way `6A:2010` was fixed.
- Scope executed:
  - Established repo state and confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` did not exist.
  - Generalized the DBN-vs-raw diagnostic report label so it no longer claims `6A:2010` for later market-years.
  - Ran the same report-only source-vs-raw diagnostic for `6A:2013`.
  - Verified local OHLCV DBN timestamp set exactly matches `data/raw/6A/2013.parquet`.
  - Generated a 459-row include artifact excluding exactly `6A:2010` and `6A:2013`.
  - Ran 459-row readiness-only preflight.
  - Stopped before build because readiness-only preflight failed on a new blocker, `6A:2014`.
- Current result:
  - `6A:2013` DBN-vs-raw diagnostic status: `PASS`.
  - `6A:2013` source-vs-raw call: `raw_timestamp_set_matches_ohlcv_dbn_source_gaps`.
  - `6A:2013` raw rows: `326807`.
  - `6A:2013` DBN rows: `326807`.
  - `6A:2013` timestamp sets match: `true`.
  - `6A:2013` DBN timestamps missing from raw: `0`.
  - `6A:2013` raw timestamps missing from DBN: `0`.
  - `6A:2013` raw Phase 2 session candidate gaps: `14500`.
  - `6A:2013` raw synthetic missing estimate: `18795`.
  - 459-row include artifact:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010_6A_2013.json`
    - `approved_ready_row_count=459`
    - `market_years=459`
    - `excluded_fail_closed_pairs=["6A:2010", "6A:2013"]`
    - `excluded_deferred_policy_review_pairs=66`
    - `approval_token=APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_459_ROWS_EXCLUDING_6A_2010_AND_6A_2013_ONLY`
    - `broader_modeling_approved=false`
    - `config_promotion_approved=false`
    - `research_use_allowed=false`
  - 459-row readiness-only preflight result:
    - `status=FAIL`
    - `selected_market_year_count=459`
    - `market_year_include_count=459`
    - `checked_market_year_count=3`
    - `pending_market_year_count=456`
    - `blocker_count=1`
    - blocker: `6A:2014`
    - reason: `synthetic threshold breached: rows_pct=9.641594 max_gap_minutes=29`
    - `synthetic_rows_pct=9.641594`
    - `max_synthetic_gap_minutes=29`
    - `status_enrichment_missing_rows=308686`
    - `statistics_enrichment_missing_rows=92`
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Files changed in this scope:
  - `scripts\validation\diagnose_6a_2010_source_vs_raw_gaps.py`
  - `tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py`
  - `CODEX_HANDOFF.md`
- Generated report artifacts in this scope:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2013_source_vs_raw_gap_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2013_source_vs_raw_gap_diagnosis.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010_6A_2013.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_459_excluding_6A_2010_6A_2013.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_459_excluding_6A_2010_6A_2013.md`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - `python -m pytest tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py`
  - `python -m scripts.validation.diagnose_6a_2010_source_vs_raw_gaps --market 6A --year 2013 --raw-root data\raw --dbn-root data\dbn\ohlcv_1m --readiness-json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6A_2010.json --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2013_source_vs_raw_gap_diagnosis.json --md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2013_source_vs_raw_gap_diagnosis.md`
  - Generated `broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010_6A_2013.json` from the existing 460-row include by excluding exactly `6A:2013`.
  - `python -m scripts.phase2_causal_base.build_causal_base_data --profile all_raw --raw-root data\raw --output-root data\causal_base_candidates\broad_manifest_527_rebuild_v1 --reports-root reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 --raw-alignment-report reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_all_raw_alignment.json --market-year-include-list reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010_6A_2013.json --readiness-only --readiness-json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_459_excluding_6A_2010_6A_2013.json --readiness-md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_459_excluding_6A_2010_6A_2013.md`
  - `python -m pytest tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py tests\validation\test_diagnose_phase2_readiness_blockers.py tests\validation\test_drilldown_phase2_readiness_blockers.py`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `git status --short`
- Validation:
  - `tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py`: `2 passed`.
  - Focused validation suite: `13 passed`.
  - 459-row include parse check passed: `market_years=459`, `has_6A_2010=0`, `has_6A_2013=0`, `deferred_excluded=66`, safety flags false.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Unresolved blockers:
  - Severe: 459-row readiness-only preflight failed on `6A:2014`.
  - Severe: broad build remains blocked because readiness-only preflight is `FAIL`.
  - Severe: no approval exists to exclude, repair, refresh, or accept a readiness exception for `6A:2014`.
- Safety:
  - No provider/network command was run.
  - No DBN source file was mutated.
  - No `data/raw/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No broad build, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, config promotion, or research-use approval was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: clear the new `6A:2014` readiness-only blocker after `6A:2010` and `6A:2013` were fail-closed and excluded.

Context:
- Repo: C:\Users\donny\Desktop\futures_intraday_model
- `6A:2013` was diagnosed as source-level sparsity:
  - raw timestamp set matches local OHLCV DBN timestamp set
  - raw_rows=326807
  - dbn_rows=326807
  - dbn_timestamps_missing_from_raw=0
  - raw_timestamps_missing_from_dbn=0
- 459-row include excluding `6A:2010` and `6A:2013` was generated:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010_6A_2013.json
- 459-row readiness-only preflight failed:
  - status=FAIL
  - selected_market_year_count=459
  - checked_market_year_count=3
  - pending_market_year_count=456
  - blocker_count=1
  - blocker=6A:2014
  - reason=synthetic threshold breached: rows_pct=9.641594 max_gap_minutes=29
  - status_missing=308686
  - statistics_missing=92
- `data/causal_base_candidates/broad_manifest_527_rebuild_v1` still does not exist.
- Broad build was not run.
- No provider/network command was run.
- No config diff and no git-tracked data diff.

Goal:
- Produce an implementation plan to clear or disposition the `6A:2014` blocker under explicit gates, then continue the broad_manifest_527_rebuild_v1 path only if readiness-only preflight reaches PASS.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Brief diagnosis.
2. Required evidence for `6A:2014`.
3. Exact disposition options and approval language.
4. Stop conditions.
5. Verification commands.
6. Final copy-paste GOAL MODE PROMPT.
```

## Broad Manifest 527 6A 2010 Disposition Implemented, 460-Row Preflight Blocked On 6A 2013 - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the 6A:2010 fix-or-disposition plan, defaulting to fail-closed exclusion if no local conversion/readiness bug is proven.
- Scope executed:
  - Established repo state and confirmed `data\causal_base_candidates\broad_manifest_527_rebuild_v1` did not exist.
  - Confirmed post-refresh `6A:2010` readiness remained `FAIL`.
  - Regenerated read-only `6A:2010` root-cause diagnosis/drilldown evidence.
  - Added a focused report-only DBN-vs-raw diagnostic for exact `6A:2010`.
  - Verified local refreshed OHLCV DBN timestamp set exactly matches `data/raw/6A/2010.parquet`.
  - Generated a 460-row include artifact excluding only `6A:2010`.
  - Ran 460-row readiness-only preflight.
  - Stopped before build because readiness-only preflight failed on a new blocker, `6A:2013`.
- Current result:
  - `6A:2010` DBN-vs-raw diagnostic status: `PASS`.
  - `6A:2010` source-vs-raw call: `raw_timestamp_set_matches_ohlcv_dbn_source_gaps`.
  - `6A:2010` raw rows: `193184`.
  - `6A:2010` DBN rows: `193184`.
  - `6A:2010` timestamp sets match: `true`.
  - `6A:2010` DBN timestamps missing from raw: `0`.
  - `6A:2010` raw timestamps missing from DBN: `0`.
  - `6A:2010` raw Phase 2 session candidate gaps: `7685`.
  - `6A:2010` raw synthetic missing estimate: `10926`.
  - 460-row include artifact:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010.json`
    - `approved_ready_row_count=460`
    - `market_years=460`
    - `excluded_fail_closed_pairs=["6A:2010"]`
    - `excluded_deferred_policy_review_pairs=66`
    - `approval_token=APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY`
    - `broader_modeling_approved=false`
    - `config_promotion_approved=false`
    - `research_use_allowed=false`
  - 460-row readiness-only preflight result:
    - `status=FAIL`
    - `selected_market_year_count=460`
    - `market_year_include_count=460`
    - `checked_market_year_count=3`
    - `pending_market_year_count=457`
    - `blocker_count=1`
    - blocker: `6A:2013`
    - reason: `synthetic threshold breached: rows_pct=5.438337 max_gap_minutes=27`
    - `synthetic_rows_pct=5.438337`
    - `max_synthetic_gap_minutes=27`
    - `status_enrichment_missing_rows=243722`
    - `statistics_enrichment_missing_rows=385`
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Files changed in this scope:
  - `scripts\validation\diagnose_6a_2010_source_vs_raw_gaps.py`
  - `tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py`
  - `CODEX_HANDOFF.md`
- Generated report artifacts in this scope:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_post_refresh_root_cause_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_post_refresh_root_cause_drilldown.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_vs_raw_gap_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_vs_raw_gap_diagnosis.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6A_2010.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6A_2010.md`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - Parsed `broad_manifest_527_rebuild_phase2_readiness_after_6A_2010_repair.json`.
  - `python -m scripts.validation.diagnose_phase2_readiness_blockers --checkpoint-jsonl reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl --top-n 1 --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_post_refresh_root_cause_diagnosis.json`
  - `python -m scripts.validation.drilldown_phase2_readiness_blockers --checkpoint-jsonl reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl --raw-root data\raw --profile all_raw --markets 6A --years 2010 --max-selected-market-years 1 --top-n 25 --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_post_refresh_root_cause_drilldown.json`
  - `python -m pytest tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py`
  - `python -m scripts.validation.diagnose_6a_2010_source_vs_raw_gaps --market 6A --year 2010 --raw-root data\raw --dbn-root data\dbn\ohlcv_1m --readiness-json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6A_2010_repair.json --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_vs_raw_gap_diagnosis.json --md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_vs_raw_gap_diagnosis.md`
  - Generated `broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010.json` from the existing 461-row include by excluding exactly `6A:2010`.
  - `python -m scripts.phase2_causal_base.build_causal_base_data --profile all_raw --raw-root data\raw --output-root data\causal_base_candidates\broad_manifest_527_rebuild_v1 --reports-root reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 --raw-alignment-report reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_all_raw_alignment.json --market-year-include-list reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010.json --readiness-only --readiness-json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6A_2010.json --readiness-md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_460_excluding_6A_2010.md`
  - `python -m pytest tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py tests\validation\test_diagnose_phase2_readiness_blockers.py tests\validation\test_drilldown_phase2_readiness_blockers.py`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `git status --short`
- Validation:
  - `tests\validation\test_diagnose_6a_2010_source_vs_raw_gaps.py`: `2 passed`.
  - Focused validation suite: `13 passed`.
  - 460-row include parse check passed: `market_years=460`, `has_6A_2010=0`, `deferred_excluded=66`, safety flags false.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Unresolved blockers:
  - Severe: 460-row readiness-only preflight failed on `6A:2013`.
  - Severe: broad build remains blocked because readiness-only preflight is `FAIL`.
  - Severe: no approval exists to exclude, repair, refresh, or accept a readiness exception for `6A:2013`.
- Safety:
  - No provider/network command was run.
  - No DBN source file was mutated.
  - No `data/raw/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No broad build, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, config promotion, or research-use approval was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: clear the new `6A:2013` readiness-only blocker after `6A:2010` was fail-closed and excluded.

Context:
- Repo: C:\Users\donny\Desktop\futures_intraday_model
- `6A:2010` was diagnosed as source-level sparsity:
  - raw timestamp set matches local OHLCV DBN timestamp set
  - raw_rows=193184
  - dbn_rows=193184
  - dbn_timestamps_missing_from_raw=0
  - raw_timestamps_missing_from_dbn=0
- 460-row include excluding only `6A:2010` was generated:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include_excluding_6A_2010.json
- 460-row readiness-only preflight failed:
  - status=FAIL
  - selected_market_year_count=460
  - checked_market_year_count=3
  - pending_market_year_count=457
  - blocker_count=1
  - blocker=6A:2013
  - reason=synthetic threshold breached: rows_pct=5.438337 max_gap_minutes=27
  - status_missing=243722
  - statistics_missing=385
- `data/causal_base_candidates/broad_manifest_527_rebuild_v1` still does not exist.
- Broad build was not run.
- No provider/network command was run.
- No config diff and no git-tracked data diff.

Goal:
- Produce an implementation plan to clear or disposition the `6A:2013` blocker under explicit gates, then continue the broad_manifest_527_rebuild_v1 path only if readiness-only preflight reaches PASS.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false.

Plan output required:
1. Brief diagnosis.
2. Required evidence for `6A:2013`.
3. Exact disposition options and approval language.
4. Stop conditions.
5. Verification commands.
6. Final copy-paste GOAL MODE PROMPT.
```

## Broad Manifest 527 6A 2010 Source Refresh Completed But Readiness Still Failed - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: proceed with redownloading only the one blocked market-year, not all data.
- Scope executed: refreshed only `6A:2010` Databento DBN source files, rebuilt only `data/raw/6A/2010.parquet`, reran readiness-only preflight, and stopped before broad build because readiness remained `FAIL`.
- Current result:
  - Provider estimates for OHLCV, status, statistics, and definition were all `$0.0000` with `TOTAL_ESTIMATE_ERRORS 0`.
  - Approved provider refresh commands ran only for market `6A`, year `2010`, date range `2010-06-06` to `2011-01-01`.
  - Refreshed DBN targets:
    - `data/dbn/ohlcv_1m/6A/2010/2010-06-06_2011-01-01.dbn.zst`, job `GLBX-20260629-ABREQA856V`, sha256 `82db98f992b74ac56f9e76c199aceac71840a45498eb2296792619a37df94ce5`.
    - `data/dbn/status/6A/2010/2010-06-06_2011-01-01.dbn.zst`, job `GLBX-20260629-PTBJ3X5SR5`, sha256 `ca6a4a7ed7636b2c46e24a8e6a4b3ef2a0b8e01c35d41fd1bc1c513c3c119650`.
    - `data/dbn/statistics/6A/2010/2010-06-06_2011-01-01.dbn.zst`, job `GLBX-20260629-YKVBU4H56N`, sha256 `ae4dfb3e21036958f80551eeb7013015276e307096a15c82cd7748b4599269c5`.
    - `data/dbn/definition/6A/2010/2010-06-06_2011-01-01.dbn.zst`, job `GLBX-20260629-D6EH378CHE`, sha256 `0e5017a1f5e318512875ecd3ccfcfddc19af193cc8f9aa896d09d325d878f837`.
  - Raw conversion rebuilt only `data/raw/6A/2010.parquet`.
  - New raw output hash is `70c8799c620e27124f0a24287914cbd06e7b3fc2bcc7f08c4e0fbc6340750e9d`.
  - Raw row count remains `193184`, first timestamp `2010-06-07T00:00:00+00:00`, last timestamp `2010-12-31T18:14:00+00:00`.
  - Optional schema policy was `require`; optional schema warning count was `0`.
  - Status optional match rate remains `0.224837` with `149749` missing rows.
  - Statistics matched rows remain `193083` with `101` missing rows.
  - Post-repair drilldown still reported `status=FAIL`, top raw gap count `7834`, raw max gap minutes `4381`, session candidate gap count `7685`, and synthetic missing rows estimate `10926`.
  - Post-repair readiness-only preflight still reported `status=FAIL`, `checked_market_year_count=1`, `blocker_count=1`, and blocker `6A:2010`.
  - Remaining blocker reason: `synthetic threshold breached: rows_pct=5.352996 max_gap_minutes=18`.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Broad build execution was not run.
- Report artifacts generated in this scope:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_*_estimate_plan.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_*_download_plan.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_convert\databento_convert_results.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_convert\raw_ingest_manifest.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_post_convert_drilldown.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6A_2010_repair.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6A_2010_repair.md`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 160`
  - Parsed the four approved dry-run artifacts to verify exact market/year/output scope.
  - Parsed `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json`.
  - Ran four Databento `--estimate-cost` commands for exact `6A:2010` OHLCV/status/statistics/definition scopes.
  - Ran four Databento non-dry-run provider refresh commands for exact `6A:2010` OHLCV/status/statistics/definition scopes.
  - `python -m scripts.phase1B_convert.convert_databento_raw --universe custom --markets 6A --start 2010-06-06 --end 2011-01-01 --dbn-root data\dbn\ohlcv_1m --raw-root data\raw --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_convert --include-optional-schemas status,statistics --optional-dbn-root data\dbn --definition-dbn-root data\dbn\definition --optional-schema-policy require --offline-local-conditions --overwrite`
  - `python -m scripts.validation.drilldown_phase2_readiness_blockers --checkpoint-jsonl reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl --raw-root data\raw --profile all_raw --markets 6A --years 2010 --max-selected-market-years 1 --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_post_convert_drilldown.json`
  - `python -m scripts.phase2_causal_base.build_causal_base_data --profile all_raw --raw-root data\raw --output-root data\causal_base_candidates\broad_manifest_527_rebuild_v1 --reports-root reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1 --raw-alignment-report reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_all_raw_alignment.json --market-year-include-list reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include.json --readiness-only --readiness-json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6A_2010_repair.json --readiness-md-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_after_6A_2010_repair.md`
  - `python -m pytest tests\validation\test_diagnose_phase2_readiness_blockers.py tests\validation\test_drilldown_phase2_readiness_blockers.py tests\phase1A_download\test_download_databento_raw.py tests\phase2_causal_base\test_build_causal_base_data.py`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `git status --short`
- Validation:
  - Raw conversion report parsed successfully and recorded `failure_count=0`.
  - Post-repair readiness JSON parsed successfully.
  - Focused tests passed: `232 passed`.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths; note that approved generated/ignored `data/**` artifacts were mutated for `6A:2010`.
- Unresolved blockers:
  - Severe: source refresh did not clear the `6A:2010` Phase 2 readiness blocker.
  - Severe: broad build remains blocked because readiness-only preflight is still `FAIL`.
  - A separate decision is required: keep fail-closed/no build, accept a scoped readiness exception, or build 460 rows excluding `6A:2010`.
- Safety:
  - Only approved `6A:2010` DBN/raw source paths were mutated.
  - No other market/year source refresh was run.
  - No `configs/**` mutation was performed.
  - No broad build, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, config promotion, or research-use approval was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: decide the post-refresh disposition for `6A:2010` after source refresh failed to clear readiness.

Context:
- Repo: C:\Users\donny\Desktop\futures_intraday_model
- `6A:2010` provider refresh completed only for that market-year.
- `data/raw/6A/2010.parquet` was rebuilt from refreshed DBNs.
- Post-repair readiness-only preflight still failed:
  - status=FAIL
  - blocker_count=1
  - blocker=6A:2010
  - reason=synthetic threshold breached: rows_pct=5.352996 max_gap_minutes=18
  - status_missing=149749
  - statistics_missing=101
- `data/causal_base_candidates/broad_manifest_527_rebuild_v1` does not exist.
- Broad build was not run.
- No config diff and no git-tracked data diff.

Goal:
- Produce a plan for the next explicit gate after failed 6A:2010 repair.
- The practical choices are:
  1. keep `6A:2010` fail-closed and no build,
  2. approve a scoped readiness exception for `6A:2010` and rerun readiness-only preflight,
  3. build the 460-row broad scope excluding `6A:2010`.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands.
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not run broad build unless a separate exact disposition is selected and readiness-only preflight reaches PASS.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.

Plan output required:
1. Brief diagnosis.
2. Recommended next disposition.
3. Exact approval language required.
4. Stop conditions.
5. Verification commands.
6. Final copy-paste GOAL MODE PROMPT.
```

## Broad Manifest 527 6A 2010 Source Refresh Dry-Run Stopped Before Provider Mutation - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the proposed `6A:2010` source repair/provider refresh plan.
- Scope executed: established repo state, read repo guidance/current handoff/current disposition evidence, inspected `6A:2010` source/raw evidence, ran read-only blocker diagnosis/drilldown, ran provider-refresh dry-runs for the four proposed schemas, and stopped before provider/network download or data overwrite.
- Current result:
  - The considered disposition is `APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD`.
  - Current disposition artifact still records `selected_option_id=null`, `human_disposition_approved=false`, `build_execution_allowed_now=false`, and `source_repair_approved=false`.
  - The current blocker remains `6A:2010`: `synthetic threshold breached: rows_pct=5.352996 max_gap_minutes=18`.
  - Read-only drilldown status is `FAIL`; top raw gap count is `7834`, raw max gap minutes is `4381`, session candidate gap count is `7685`, and synthetic missing rows estimate is `10926`.
  - Read-only diagnosis status is `FAIL`; reason combo is `synthetic+status_enrichment+statistics_enrichment`.
  - No provider/network command was executed.
  - No DBN source file was overwritten.
  - No raw parquet was overwritten.
  - Readiness-only preflight was not rerun.
  - Broad build execution was not run.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
- Current `6A:2010` source/raw evidence:
  - Raw parquet: `data/raw/6A/2010.parquet`, row count `193184`, sha256 `1feb68734cbf510695fb73f0c7ea389900e8d814a603ddbb9433953f1cfa285d`.
  - OHLCV DBN: `data/dbn/ohlcv_1m/6A/2010/2010-06-06_2011-01-01.dbn.zst`, symbol `6A.v.0`, schema `ohlcv-1m`, `stype_in=continuous`.
  - Status DBN: `data/dbn/status/6A/2010/2010-06-06_2011-01-01.dbn.zst`, symbol `6A.v.0`, schema `status`, `stype_in=continuous`.
  - Statistics DBN: `data/dbn/statistics/6A/2010/2010-06-06_2011-01-01.dbn.zst`, symbol `6A.v.0`, schema `statistics`, `stype_in=continuous`.
  - Definition DBN: `data/dbn/definition/6A/2010/2010-06-06_2011-01-01.dbn.zst`, symbol `6A.FUT`, schema `definition`, `stype_in=parent`.
- Dry-run report artifacts generated:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_diagnosis.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_drilldown.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_ohlcv_1m_plan_dry_run.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_status_corrected_plan_dry_run.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_statistics_corrected_plan_dry_run.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_definition_corrected_plan_dry_run.json`
- Dry-run command-shape findings:
  - Valid OHLCV dry-run command shape used `--schema ohlcv-1m --dbn-root data\dbn\ohlcv_1m` and targets approved output `data/dbn/ohlcv_1m/6A/2010/2010-06-06_2011-01-01.dbn.zst`.
  - Valid status dry-run command shape used `--schema status --dbn-root data\dbn` and targets approved output `data/dbn/status/6A/2010/2010-06-06_2011-01-01.dbn.zst`.
  - Valid statistics dry-run command shape used `--schema statistics --dbn-root data\dbn` and targets approved output `data/dbn/statistics/6A/2010/2010-06-06_2011-01-01.dbn.zst`.
  - Valid definition dry-run command shape used `--schema definition --stype-in parent --dbn-root data\dbn` and targets approved output `data/dbn/definition/6A/2010/2010-06-06_2011-01-01.dbn.zst`.
  - Do not execute the invalid dry-run command shapes that produced nested or wrong targets:
    - `6A_2010_source_refresh_status_plan_dry_run.json` targets `data/dbn/status/status/...`.
    - `6A_2010_source_refresh_statistics_plan_dry_run.json` targets `data/dbn/statistics/statistics/...`.
    - `6A_2010_source_refresh_definition_plan_dry_run.json` targets `data/dbn/definition/definition/...`.
    - `6A_2010_source_refresh_ohlcv_1m_corrected_plan_dry_run.json` targets `data/dbn/6A/...`.
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw C:\Users\donny\Desktop\futures_intraday_model\AGENTS.md`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 120`
  - Parsed `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json`.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - `rg -n "dry_run|estimate_cost|plan_out|download-dbn|convert-parquet|overwrite|mode" scripts\phase1A_download\download_databento_raw.py scripts\phase1B_convert\convert_databento_raw.py`
  - `rg -n "def main|def parse_args|json_out|write|Path\(|argparse" scripts\validation\drilldown_phase2_readiness_blockers.py scripts\validation\diagnose_phase2_readiness_blockers.py scripts\validation\audit_raw_dbn_alignment.py scripts\validation\audit_enriched_raw_optional_schemas.py`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl`
  - `python -m scripts.validation.drilldown_phase2_readiness_blockers --checkpoint-jsonl reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl --raw-root data\raw --profile all_raw --markets 6A --years 2010 --max-selected-market-years 1 --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_drilldown.json`
  - `python -m scripts.validation.diagnose_phase2_readiness_blockers --checkpoint-jsonl reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl --top-n 1 --json-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_diagnosis.json`
  - `python -m scripts.phase1A_download.download_databento_raw --universe custom --markets 6A --schema ohlcv-1m --stype-in continuous --stype-out instrument_id --start 2010-06-06 --end 2011-01-01 --dbn-root data\dbn\ohlcv_1m --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628 --plan-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_ohlcv_1m_plan.json --mode download-dbn --raw-format dbn-zstd --workers 1 --dry-run --overwrite`
  - `python -m scripts.phase1A_download.download_databento_raw --universe custom --markets 6A --schema status --stype-in continuous --stype-out instrument_id --start 2010-06-06 --end 2011-01-01 --dbn-root data\dbn --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628 --plan-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_status_corrected_plan.json --mode download-dbn --raw-format dbn-zstd --workers 1 --dry-run --overwrite`
  - `python -m scripts.phase1A_download.download_databento_raw --universe custom --markets 6A --schema statistics --stype-in continuous --stype-out instrument_id --start 2010-06-06 --end 2011-01-01 --dbn-root data\dbn --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628 --plan-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_statistics_corrected_plan.json --mode download-dbn --raw-format dbn-zstd --workers 1 --dry-run --overwrite`
  - `python -m scripts.phase1A_download.download_databento_raw --universe custom --markets 6A --schema definition --stype-in parent --stype-out instrument_id --start 2010-06-06 --end 2011-01-01 --dbn-root data\dbn --reports-root reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628 --plan-out reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\6A_2010_source_refresh_definition_corrected_plan.json --mode download-dbn --raw-format dbn-zstd --workers 1 --dry-run --overwrite`
  - `python -m pytest tests\validation\test_diagnose_phase2_readiness_blockers.py tests\validation\test_drilldown_phase2_readiness_blockers.py tests\phase1A_download\test_download_databento_raw.py`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `git status --short`
- Validation:
  - Focused tests passed: `108 passed`.
  - Corrected dry-runs produced one planned task per schema for `6A` and `2010-06-06` to `2011-01-01`.
  - Corrected status/statistics/definition dry-runs target approved schema roots under `data\dbn`.
  - Initial OHLCV dry-run targets the approved `data\dbn\ohlcv_1m` path.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Unresolved blockers:
  - Severe: exact provider/network execution and overwrite approval is still required before running non-dry-run provider commands.
  - Severe: current disposition artifact still records `source_repair_approved=false` and `selected_option_id=null`.
  - Severe: raw rebuild and readiness-only preflight cannot proceed until approved source refresh completes or a separate exact raw-only repair approval is provided.
- Safety:
  - No provider/network download was run.
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No DBN source overwrite, raw parquet overwrite, broad build, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, or config promotion was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: either explicitly approve exact non-dry-run provider refresh/overwrite commands for 6A:2010, or keep the repair path blocked.

Context:
- Repo: C:\Users\donny\Desktop\futures_intraday_model
- Current path: broad_manifest_527_rebuild_v1 is stopped at 6A:2010 source repair/provider refresh.
- Current disposition artifact:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_6A_2010_disposition_request.json
- Current source repair status:
  - considered option: APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD
  - selected_option_id=null in the artifact
  - source_repair_approved=false in the artifact
  - no provider command has run
  - no data/** mutation has occurred
  - no configs diff
  - no data diff
- Safe dry-run command shapes have been identified:
  - OHLCV: --schema ohlcv-1m --dbn-root data\dbn\ohlcv_1m -> data/dbn/ohlcv_1m/6A/2010/2010-06-06_2011-01-01.dbn.zst
  - Status: --schema status --dbn-root data\dbn -> data/dbn/status/6A/2010/2010-06-06_2011-01-01.dbn.zst
  - Statistics: --schema statistics --dbn-root data\dbn -> data/dbn/statistics/6A/2010/2010-06-06_2011-01-01.dbn.zst
  - Definition: --schema definition --stype-in parent --dbn-root data\dbn -> data/dbn/definition/6A/2010/2010-06-06_2011-01-01.dbn.zst
- Invalid dry-run command shapes must not be executed:
  - nested status/status
  - nested statistics/statistics
  - nested definition/definition
  - OHLCV data/dbn/6A

Goal:
- Produce an implementation plan for exactly one next gated step:
  1. either run only approved non-dry-run provider refresh commands for the four valid 6A:2010 source targets, or
  2. keep the source repair path blocked if exact provider/network/overwrite approval is not present.

Rules:
- Do not edit files in Plan Mode.
- Do not run provider/network commands in Plan Mode.
- Do not mutate data/** in Plan Mode.
- Do not run raw conversion, readiness-only preflight, or broad build until after provider refresh approval is explicit and source refresh succeeds.
- Do not change configs/data_manifest.yaml.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or research-use approval.

Plan output required:
1. Brief diagnosis.
2. Exact approval language needed for the four non-dry-run provider refresh commands.
3. Exact commands that would run if approved.
4. Stop conditions.
5. Verification commands.
6. Final copy-paste GOAL MODE PROMPT.
```

## Broad Manifest 527 GOAL MODE Stopped At Missing 6A 2010 Disposition - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: clear the explicit `6A:2010` disposition gate and continue the full `broad_manifest_527_rebuild_v1` approval-to-build path only if the selected gate outcome allows it.
- Scope executed: established repo state, read the current handoff and disposition request, parsed the selected option state, ran stopped-path verification, and stopped before readiness-only preflight/build because no exact allowed option was selected.
- Current result:
  - The selected option in the prompt remains the placeholder text, not an allowed option ID.
  - Disposition artifact status remains `AWAITING_HUMAN_6A_2010_DISPOSITION`.
  - `selected_option_id=null`.
  - `human_disposition_approved=false`.
  - `build_execution_allowed_now=false`.
  - Current preflight status remains `FAIL`.
  - Blocked pair remains `6A:2010`.
  - Top blocker reason remains `synthetic threshold breached: rows_pct=5.352996 max_gap_minutes=18`.
  - Current scope remains 461 ready-only rows with 66 `deferred_policy_review_not_checked` rows excluded.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - Build execution was not run.
- Current allowed disposition option IDs:
  - `KEEP_6A_2010_FAIL_CLOSED_NO_BUILD`
  - `APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY`
  - `APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD`
  - `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 80`
  - Parsed `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json` for status, selected option, approval flags, preflight state, blocked pair, and allowed options.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json`
  - `rg -n "BLOCKED_NO_BUILD_APPROVAL|READY_FOR_SEPARATE_BUILD_APPROVAL|AWAITING_HUMAN_6A_2010_DISPOSITION|build_approved|broader_modeling_approved|config_promotion_approved|research_use_allowed|build_execution_allowed_now" CODEX_HANDOFF.md reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.md`
  - `rg -n "KEEP_6A_2010_FAIL_CLOSED_NO_BUILD|APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY|APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD|APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY|APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY" CODEX_HANDOFF.md reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.md`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `python -m pytest tests/validation/test_plan_broad_causal_rebuild.py tests/validation/test_validate_broad_causal_raw_source_readiness.py tests/validation/test_summarize_broad_causal_rebuild_gate.py tests/validation/test_request_broad_causal_source_artifact_policy_decision.py`
- Validation:
  - Disposition JSON parsed successfully.
  - Targeted `rg` checks found the current blocked disposition state, original broad build token, allowed option IDs, and false approval/modeling/promotion/research-use flags.
  - Focused stopped-path validation tests passed: `23 passed`.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Unresolved blockers:
  - Severe: cannot proceed to readiness-only preflight or build execution until the user selects exactly one allowed `6A:2010` disposition option.
  - Broad root remains not built, not validated, not promoted, and not approved for broader modeling.
  - The 66 deferred policy-review rows remain excluded and must not be built.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No DBN source mutation, provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, readiness-only preflight rerun, build execution, or config promotion was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: clear the severe missing `6A:2010` disposition blocker only.

Context:
- Repo: C:\Users\donny\Desktop\futures_intraday_model
- Original broad build approval token remains present: APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY.
- Current disposition artifact:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_6A_2010_disposition_request.json
- Current state:
  - status=AWAITING_HUMAN_6A_2010_DISPOSITION
  - selected_option_id=null
  - human_disposition_approved=false
  - build_execution_allowed_now=false
  - current preflight status=FAIL
  - blocked pair=6A:2010
  - data/causal_base_candidates/broad_manifest_527_rebuild_v1 does not exist
  - no configs diff
  - no data diff

Goal:
- Select exactly one allowed `6A:2010` disposition option, or explicitly keep the rebuild blocked with no build.
- Do not proceed to readiness-only preflight or build execution unless the selected option allows it and any required later readiness gate passes.

Allowed exact option IDs:
- KEEP_6A_2010_FAIL_CLOSED_NO_BUILD
- APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY
- APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD
- APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY

Rules:
- Do not edit files in Plan Mode.
- Do not run the broad build.
- Do not mutate data/**, DBN source, data/raw, configs/data_manifest.yaml, predictions, models, feature matrices, cleanup targets, or unrelated reports.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or broader research-use approval.
- Do not build the 66 deferred_policy_review_not_checked rows.

Plan output required:
1. Brief diagnosis.
2. Exact selected `6A:2010` disposition, or state that it is still missing.
3. What the selected option permits next.
4. Stop conditions.
5. Verification commands.
6. Final copy-paste GOAL MODE PROMPT that includes the exact selected option ID if approved.
```

## Broad Manifest 527 Implementation Attempt Stopped At 6A 2010 Disposition Gate - 2026-06-29

- Updated at UTC date: 2026-06-29.
- User request: implement the full proposed approval-to-build plan.
- Scope executed: established current repo state, read repo guidance/current handoff/current `6A:2010` disposition request, checked for an exact `6A:2010` disposition selection, ran stopped-path verification, and stopped at the explicit unapproved gate.
- Current result:
  - Original broad build approval token remains present: `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY`.
  - No exact `6A:2010` disposition option was selected in the current user message or disposition request artifact.
  - Current disposition request status remains `AWAITING_HUMAN_6A_2010_DISPOSITION`.
  - `selected_option_id=null`.
  - `human_disposition_approved=false`.
  - `build_execution_allowed_now=false`.
  - Blocked pair remains `6A:2010`, `synthetic_rows_pct=5.352996`.
  - Build execution was not run.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Current allowed disposition option IDs:
  - `KEEP_6A_2010_FAIL_CLOSED_NO_BUILD`
  - `APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY`
  - `APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD`
  - `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw C:\Users\donny\Desktop\futures_intraday_model\AGENTS.md`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - Parsed `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json` for status, selected option, approval flags, allowed options, and blocked pair.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json`
  - `rg -n "BLOCKED_NO_BUILD_APPROVAL|READY_FOR_SEPARATE_BUILD_APPROVAL|AWAITING_HUMAN_6A_2010_DISPOSITION|build_approved|broader_modeling_approved|config_promotion_approved|research_use_allowed" CODEX_HANDOFF.md reports scripts tests`
  - `rg -n "APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY|KEEP_6A_2010_FAIL_CLOSED_NO_BUILD|APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY|APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD|APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY" CODEX_HANDOFF.md reports scripts tests`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `python -m pytest tests/validation/test_plan_broad_causal_rebuild.py tests/validation/test_validate_broad_causal_raw_source_readiness.py tests/validation/test_summarize_broad_causal_rebuild_gate.py tests/validation/test_request_broad_causal_source_artifact_policy_decision.py`
- Validation:
  - Verified the repo path is `C:\Users\donny\Desktop\futures_intraday_model`.
  - Verified the disposition request remains unselected and build execution is not allowed.
  - Verified no approved candidate build root exists.
  - Disposition request JSON parsed successfully.
  - Targeted validation tests passed: `23 passed`.
  - Targeted `rg` checks found the blocked status, original approval token, allowed `6A:2010` option IDs, and false approval/modeling/promotion/research-use evidence in current handoff/report/tooling/test artifacts.
  - Verified no config diff and no data diff.
- Unresolved blockers:
  - Severe: cannot proceed to readiness-only preflight rerun or build execution without one exact explicit `6A:2010` disposition option.
  - Broad root remains not built, not validated, not promoted, and not approved for broader modeling.
  - The 66 deferred policy-review rows remain excluded and must not be built.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No DBN source mutation, provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, build execution, or config promotion was performed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: clear the explicit `6A:2010` disposition gate so the full broad_manifest_527_rebuild_v1 approval-to-build path can continue.

Context:
- Original broad build approval token is present: APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY.
- Build remains stopped at a later explicit gate: `6A:2010` Phase 2 readiness-only preflight disposition.
- Current disposition artifact:
  reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_6A_2010_disposition_request.json

Goal:
- Select or record exactly one explicit `6A:2010` disposition option, then continue the full approval-to-build path only if that option and readiness-only preflight allow it.
- If no exact option is selected, keep broad_manifest_527_rebuild_v1 blocked with report-only evidence and no build.

Allowed exact option IDs:
- KEEP_6A_2010_FAIL_CLOSED_NO_BUILD
- APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY
- APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD
- APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY

Rules:
- Do not run the broad build unless one exact `6A:2010` disposition is selected and readiness-only preflight reaches PASS for the resulting approved scope.
- Do not mutate data/**, DBN source, data/raw, configs/data_manifest.yaml, predictions, models, feature matrices, or cleanup targets unless the selected disposition explicitly allows that exact mutation.
- Do not change configs/data_manifest.yaml.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or broader research-use approval.
- Do not build the 66 deferred_policy_review_not_checked rows.

Plan output required:
1. Brief diagnosis.
2. Selected or missing `6A:2010` disposition.
3. Full continuation plan through preflight, build, validation, and built-not-promoted evidence if the selected gate allows it.
4. Stop conditions.
5. Verification commands.
6. Final copy-paste GOAL MODE PROMPT.
```

## Broad Manifest 527 Build Awaiting 6A 2010 Human Disposition - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\d4e170b0-5bf1-47bc-9073-b4fcaefdb4e3\pasted-text-1.txt`
- Original broad build approval token remains present:
  - `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY`
- Current gate state:
  - The original 461-row build approval is insufficient to bypass the later Phase 2 readiness-only preflight blocker.
  - The approved broad build remains blocked until a separate explicit `6A:2010` disposition is selected and applied.
  - No build execution has run.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
- New report-only disposition request artifacts:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.md`
- Disposition request state:
  - `status=AWAITING_HUMAN_6A_2010_DISPOSITION`
  - `selected_option_id=null`
  - `human_disposition_approved=false`
  - `build_execution_allowed_now=false`
  - Blocked pair: `6A:2010`
  - Current blocker: `synthetic threshold breached: rows_pct=5.352996 max_gap_minutes=18`
  - `synthetic_rows=10926`
  - `status_enrichment_missing_rows=149749`
  - `status_enrichment_stale_rows=149749`
  - `statistics_enrichment_missing_rows=101`
  - `statistics_enrichment_stale_rows=101`
- Explicit human choices recorded in the request:
  - `KEEP_6A_2010_FAIL_CLOSED_NO_BUILD`
  - `APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY`
  - `APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD`
  - `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY`
- Safety flags in the request remain false:
  - `broader_modeling_approved=false`
  - `config_promotion_approved=false`
  - `research_use_allowed=false`
  - `data_manifest_change_approved=false`
  - `deferred_rows_build_approved=false`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\d4e170b0-5bf1-47bc-9073-b4fcaefdb4e3\pasted-text-1.txt`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - Parsed current preflight, fail-closed packet, and ready-only include JSON artifacts.
  - Generated the `6A:2010` disposition request JSON/Markdown with a local Python JSON writer.
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json`
  - `rg -n "AWAITING_HUMAN_6A_2010_DISPOSITION|KEEP_6A_2010_FAIL_CLOSED_NO_BUILD|APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY|APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD|APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY|build_execution_allowed_now|broader_modeling_approved|config_promotion_approved|research_use_allowed" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_6A_2010_disposition_request.md`
  - Parsed the disposition request to verify status, selected option, build gate, choice count, blocked pair, and false safety flags.
- Validation:
  - Disposition request JSON parsed successfully.
  - Targeted assertions confirmed all four option IDs, `build_execution_allowed_now=false`, and false broader modeling/config promotion/research-use flags.
  - No disposition option is selected.
- Unresolved blockers:
  - Severe: broad build execution is blocked pending explicit human selection of a `6A:2010` disposition option.
  - A separate explicit human decision is required before any accepted-readiness exception, threshold loosening, source repair, provider command, canonical raw overwrite, 460-row rescope/exclusion, or build execution with the unresolved `6A:2010` preflight blocker.
  - Broad root remains not built, not validated, not promoted, and not approved for broader modeling.
  - The 66 deferred policy-review rows remain excluded and must not be built in this path.
  - Worktree remains dirty with existing tracked/untracked report/tooling state and newly generated report artifacts. No staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed in this scope.
  - No `configs/**` mutation was performed.
  - No DBN source mutation, provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, build execution, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Full goal: solve the broad_manifest_527_rebuild_v1 approval-to-build path end to end under explicit gates, not just the next small decision-recording step.

Current required gate:
- The original broad build approval token is present: APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY.
- The path is now stopped at a later explicit gate: `6A:2010` Phase 2 readiness-only preflight disposition.
- Use this decision request as the current gate artifact:
- reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_6A_2010_disposition_request.json

Goal:
- If no exact `6A:2010` disposition approval is present, keep the full rebuild blocked with report-only evidence and stop.
- If an exact `6A:2010` disposition is present, apply only that disposition, rerun readiness-only preflight, and continue the full approved path through build execution, validation, built-not-promoted evidence, and final handoff.
- Stop only at an explicit unapproved gate, failed validation, scope broadening, or verified completion.

Allowed exact `6A:2010` disposition option IDs:
- `KEEP_6A_2010_FAIL_CLOSED_NO_BUILD`
- `APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY`
- `APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD`
- `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY`

Rules:
- Do not run the broad build unless the current user message or a named approval artifact explicitly selects one `6A:2010` disposition and readiness-only preflight reaches PASS for the resulting approved scope.
- Do not mutate data/**, DBN source, data/raw, configs/data_manifest.yaml, predictions, models, feature matrices, or cleanup targets unless the selected disposition explicitly allows the exact mutation.
- Do not change configs/data_manifest.yaml.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or broader research-use approval.
- Do not build the 66 deferred_policy_review_not_checked rows.
- Do not mark tier2/tier3/all-market rows as modeling-approved.

Task:
- Establish state with Get-Location and git status --short.
- Read CODEX_HANDOFF.md and the referenced approval/disposition/readiness artifacts.
- Detect whether the current user message or named approval artifact explicitly selects one allowed `6A:2010` option ID.
- If no exact disposition is selected, refresh/confirm report-only blocked evidence, update CODEX_HANDOFF.md, and stop with no build.
- If `KEEP_6A_2010_FAIL_CLOSED_NO_BUILD` is selected, record that final blocked disposition and stop with no build.
- If `APPROVE_6A_2010_ACCEPTED_READINESS_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY` is selected, create only the isolated exception evidence/config required for the exact current `6A:2010` warning, rerun readiness-only preflight, and continue only if it reaches PASS.
- If `APPROVE_6A_2010_SOURCE_REPAIR_OR_PROVIDER_REFRESH_BEFORE_BUILD` is selected, perform only the approved `6A:2010` source/raw repair or provider-refresh path, rerun readiness-only preflight, and continue only if it reaches PASS.
- If `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6A_2010_ONLY` is selected, generate a new 460-row include excluding only `6A:2010`, rerun readiness-only preflight for that explicit scope, and continue only if it reaches PASS.
- Once readiness-only preflight reaches PASS for the approved scope, execute only the approved build to data/causal_base_candidates/broad_manifest_527_rebuild_v1.
- Validate manifest, validation report, row/file counts, hashes, selected scope, no deferred rows, no config mutation, no unauthorized data mutation, and generated-artifact hygiene.
- Generate only bounded built-not-promoted evidence if the build validates.
- Keep broader_modeling_approved=false, config_promotion_approved=false, and research_use_allowed=false unless a later explicit gate approves otherwise.
- Update CODEX_HANDOFF.md with status, files changed, commands run, validation results, blockers, remaining work, and the next full-goal prompt.

Stop when:
- The broad build is verified complete and built-not-promoted, or the path is stopped by an explicit unapproved gate, failed validation, or scope broadening.
```

## Broad Manifest 527 Approved Build Remains Blocked By 6A 2010 Fail-Closed Packet - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\d4e170b0-5bf1-47bc-9073-b4fcaefdb4e3\pasted-text-1.txt`
- Explicit human build approval token remains present:
  - `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY`
- Scope executed: continued the approved broad build path from the failed Phase 2 readiness-only preflight and recorded the single preflight blocker as a fail-closed Phase 2 decision packet. No build execution was run.
- New artifacts generated:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl`
  - `reports\phase2_readiness\6A_2010_scope_20260629\6A_2010_decision_packet_20260629.json`
  - `reports\phase2_readiness\6A_2010_scope_20260629\6A_2010_decision_packet_20260629.md`
- Result:
  - The existing repo exception machinery was inspected. `--accepted-readiness-exceptions` is restricted to exact tier-1 candidate rows and does not authorize `6A:2010`; profile-config exceptions can accept exact status-sparse warnings only with explicit configured evidence, but no separate human approval for a `6A:2010` exception was present.
  - The preflight blocker was converted into a one-row checkpoint JSONL for existing decision-packet tooling.
  - `build_phase2_decision_packets` wrote a scoped fail-closed packet for `6A:2010`.
  - Packet status is `ACTION_REQUIRED`.
  - Packet decision status is `BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED`.
  - Blocker class is `synthetic`.
  - Evidence remains: `synthetic_rows=10926`, `synthetic_rows_pct=5.352996`, `max_synthetic_gap_minutes=18`, `status_enrichment_missing_rows=149749`, `status_enrichment_stale_rows=149749`, `statistics_enrichment_missing_rows=101`, and `statistics_enrichment_stale_rows=101`.
  - Policy decision is `keep_fail_closed`.
  - Policy flags remain false: `diagnostic_use_approved=false`, `accepted_readiness_exception_added=false`, `thresholds_loosened=false`, `provider_command_approved=false`, `source_repair_approved=false`, `canonical_raw_overwrite_approved=false`, and `canonical_phase2_rebuild_approved=false`.
  - Build execution remains blocked because the approved 461-row path still lacks a passing readiness-only preflight.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` still does not exist.
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\d4e170b0-5bf1-47bc-9073-b4fcaefdb4e3\pasted-text-1.txt`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `rg -n "synthetic threshold|synthetic_gap_threshold|accepted_readiness|readiness-only|readiness_only|market_year_include|blocker" scripts\phase2_causal_base scripts\validation tests\phase2_causal_base tests\validation`
  - Parsed `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild.json` for the top-level counts and blocker details.
  - `rg -n "def _accepted_readiness_exception_evidence_failures|def _accepted_readiness_exception_for_result|def _accepted_readiness_exception_failures|ACCEPTED_READINESS_EXCEPTION_CATEGORIES|STATUS_SPARSE_EXCEPTION_CATEGORY|TIER1_CANDIDATE_SYNTHETIC_EXCEPTION_ROWS|accepted_readiness_exceptions_path" scripts\phase2_causal_base\build_causal_base_data.py -C 12`
  - `python -m scripts.validation.build_phase2_decision_packets --help`
  - `Get-Content -Raw scripts\validation\build_phase2_decision_packets.py`
  - `Get-Content -Raw tests\validation\test_build_phase2_decision_packets.py`
  - `python -m pytest tests\validation\test_build_phase2_decision_packets.py`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild.json`
  - Generated the one-row blocker JSONL from the preflight report with a local Python JSON writer.
  - `python -m scripts.validation.build_phase2_decision_packets --checkpoint-jsonl reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl --raw-root data\raw --reports-root reports\phase2_readiness --markets 6A --years 2010 --date-tag 20260629`
  - `python -m json.tool reports\phase2_readiness\6A_2010_scope_20260629\6A_2010_decision_packet_20260629.json`
  - Parsed `reports\phase2_readiness\6A_2010_scope_20260629\6A_2010_decision_packet_20260629.json` for status, decision status, blocker class, synthetic metrics, and false policy flags.
  - `rg -n "ACTION_REQUIRED|keep_fail_closed|accepted_readiness_exception_added|canonical_phase2_rebuild_approved|thresholds_loosened|synthetic_rows_pct|6A 2010" reports\phase2_readiness\6A_2010_scope_20260629`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
- Validation:
  - Decision-packet focused tests passed: `4 passed`.
  - Phase 2 preflight JSON parsed successfully.
  - Decision-packet JSON parsed successfully.
  - Targeted packet parse confirmed `status=ACTION_REQUIRED`, `decision_status=BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED`, `blocker_classes=synthetic`, `synthetic_rows_pct=5.352996`, and false policy flags.
  - Targeted `rg` confirmed `ACTION_REQUIRED`, `keep_fail_closed`, false exception/rebuild/threshold flags, and `synthetic_rows_pct` in the packet artifacts.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
- Unresolved blockers:
  - Severe: the approved broad build cannot run because `6A:2010` remains fail-closed after Phase 2 readiness-only preflight.
  - A separate explicit human decision is required before any of these actions: accepted-readiness exception, threshold loosening, provider command, source repair, canonical raw overwrite, 460-row rescope/exclusion, or broad build execution with the `6A:2010` blocker unresolved.
  - Broad root remains not built, not validated, not promoted, and not approved for broader modeling.
  - The 66 deferred policy-review rows remain excluded and must not be built in this path.
  - Worktree remains dirty with existing tracked/untracked report/tooling state and newly generated report artifacts. No staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed in this scope.
  - No `configs/**` mutation was performed.
  - No DBN source mutation, provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, build execution, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: obtain a separate human disposition decision for the `6A:2010` Phase 2 readiness-only preflight blocker before any broad build execution.
Rules:
- Do not run the broad build unless a readiness-only preflight reaches PASS for the approved 461-row ready-only include, or the current user gives a separate explicit human approval for the exact `6A:2010` blocker disposition.
- Do not mutate data/**, DBN source, data/raw, configs/data_manifest.yaml, predictions, models, feature matrices, or cleanup targets.
- Do not change configs/data_manifest.yaml.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or broader research-use approval.
- Do not build the 66 deferred_policy_review_not_checked rows.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Establish state with Get-Location and git status --short.
- Read CODEX_HANDOFF.md.
- Use current artifacts:
  - reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_prebuild.json
  - reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_prebuild_blockers.jsonl
  - reports/phase2_readiness/6A_2010_scope_20260629/6A_2010_decision_packet_20260629.json
- If no new explicit `6A:2010` disposition approval exists, keep the build blocked with report-only evidence and do not build.
- If explicit approval exists, apply only the approved disposition, rerun readiness-only preflight, and run the approved broad build only if preflight reaches PASS for the resulting explicitly approved scope.
Stop when:
- `6A:2010` is either still fail-closed with no build, or explicitly disposed under a separate human gate and the broad build path can continue without widening scope.
```

## Broad Manifest 527 Approved Build Stopped At Phase 2 Preflight - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\d4e170b0-5bf1-47bc-9073-b4fcaefdb4e3\pasted-text-1.txt`
- Explicit human build approval token found in the objective context:
  - `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY`
- Scope executed: followed the approved broad build path through approval recording, 461-row ready-only include generation, raw-alignment preflight repair evidence, and Phase 2 readiness-only preflight. Build execution was not run because the readiness-only preflight failed.
- Approval artifacts generated:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_build_approval.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_build_approval.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include.json`
- Raw alignment artifacts generated:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_all_raw_alignment.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_all_raw_alignment.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_alignment_repair_manifest.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_alignment_repair_manifest.md`
- Phase 2 readiness-only preflight artifacts generated:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_phase2_readiness_prebuild.md`
- Result:
  - Ready-only include verified `ready_rows=461`, `deferred_excluded=66`, and no overlap.
  - All-raw alignment for `data/raw` initially failed on 6 source-hash mismatches: `KE:2019`, `KE:2021`, `KE:2023`, `KE:2024`, `SR1:2020`, `SR3:2020`.
  - The six source files existed and matched the raw parquet provenance hashes, so a scoped repair manifest accepted those alternate source hashes for this approved preflight only.
  - Re-run all-raw alignment passed: `status=PASS expected=530 raw=530 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.
  - Phase 2 readiness-only preflight failed: `status=FAIL selected_market_year_count=461 checked_market_year_count=1 pending_market_year_count=460 blocker_count=1`.
  - Preflight blocker row: `6A:2010` had `status=WARN`, `synthetic_rows=10926`, `synthetic_rows_pct=5.352996`, `max_synthetic_gap_minutes=18`, and `top_blocker_reason="synthetic threshold breached: rows_pct=5.352996 max_gap_minutes=18"`.
  - Build execution was not run.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` does not exist.
  - `configs\data_manifest.yaml` was not changed.
  - No config promotion, modeling, WFA, predictions, metrics, cleanup, staging, or commit was performed.
  - Approval flags for broader use remain false: `broader_modeling_approved=false`, `config_promotion_approved=false`, and `research_use_allowed=false`.
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\d4e170b0-5bf1-47bc-9073-b4fcaefdb4e3\pasted-text-1.txt`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_prebuild_plan.json`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
  - `python -m pytest tests/validation/test_plan_broad_causal_rebuild.py tests/validation/test_validate_broad_causal_raw_source_readiness.py tests/validation/test_summarize_broad_causal_rebuild_gate.py`
  - Generated approval and ready-only include artifacts with a local Python JSON writer.
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_build_approval.json`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_ready_only_include.json`
  - `python -m pytest tests/validation/test_audit_raw_dbn_alignment.py`
  - `python -m scripts.validation.audit_raw_dbn_alignment --profile all_raw --raw-root data/raw --dbn-root data/dbn --json-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_all_raw_alignment.json --md-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_all_raw_alignment.md`
  - Generated the six-row raw-alignment repair manifest with a local Python JSON writer.
  - `python -m scripts.validation.audit_raw_dbn_alignment --profile all_raw --raw-root data/raw --dbn-root data/dbn --repair-manifest reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_raw_alignment_repair_manifest.json --json-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_all_raw_alignment.json --md-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_all_raw_alignment.md`
  - `python -m scripts.phase2_causal_base.build_causal_base_data --profile all_raw --raw-root data/raw --output-root data/causal_base_candidates/broad_manifest_527_rebuild_v1 --reports-root reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1 --raw-alignment-report reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_all_raw_alignment.json --market-year-include-list reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_ready_only_include.json --readiness-only --readiness-json-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_prebuild.json --readiness-md-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_phase2_readiness_prebuild.md`
  - Targeted JSON parse of `broad_manifest_527_rebuild_phase2_readiness_prebuild.json`.
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
- Validation:
  - Focused pre-build tests passed: `17 passed`.
  - Raw alignment tests passed: `28 passed`.
  - Approval JSON and ready-only include JSON parsed successfully.
  - Ready-only include verified `461` ready rows and `66` deferred exclusions.
  - All-raw/data-raw alignment passed after the scoped repair manifest.
  - Phase 2 readiness-only preflight failed before build execution.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths after the failed preflight.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
- Unresolved blockers:
  - Severe: build execution is blocked because Phase 2 readiness-only preflight failed on `6A:2010` synthetic threshold breach.
  - The approved build must not run unless readiness-only preflight reaches `PASS` for the approved 461 ready-only rows or a separate explicit human gate approves a narrowly scoped disposition for the preflight blocker.
  - Broad root remains not built, not validated, not promoted, and not approved for broader modeling.
  - The 66 deferred policy-review rows remain excluded and must not be built in this path.
  - Worktree remains dirty with existing tracked/untracked report/tooling state and newly generated report artifacts. No staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed in this approved build attempt.
  - No `configs/**` mutation was performed.
  - No DBN source mutation, provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commit, build execution, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: clear or explicitly dispose the Phase 2 readiness-only preflight blocker for approved broad_manifest_527_rebuild_v1 before any build execution.
Rules:
- Do not run the broad build unless a readiness-only preflight reaches PASS for the approved 461-row ready-only include, or the current user gives a separate explicit human approval for a narrow disposition of the 6A:2010 synthetic-threshold blocker.
- Do not mutate data/**, DBN source, data/raw, configs/data_manifest.yaml, predictions, models, feature matrices, or cleanup targets.
- Do not change configs/data_manifest.yaml.
- Do not broaden into modeling, WFA, predictions, metrics, cleanup, staging, commits, config promotion, or broader research-use approval.
- Do not build the 66 deferred_policy_review_not_checked rows.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Establish state with Get-Location and git status --short.
- Read CODEX_HANDOFF.md.
- Inspect only the failed preflight report and targeted Phase 2 readiness policy code/tests needed to determine whether `6A:2010` should remain fail-closed, receive a separate explicit exception, or require raw/source repair.
- If no explicit separate approval exists for the blocker disposition, stop with report-only blocked evidence and do not build.
- If a separate explicit approval exists, implement only that approved disposition, rerun readiness-only preflight, and run the approved 461-row build only if preflight passes.
Stop when:
- The 6A:2010 preflight blocker is either left fail-closed with report-only evidence, or explicitly disposed under a separate human gate and the approved build path can continue without widening scope.
```

## Broad Causal Build Approval Gate Still Blocked - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\b71aa000-c47a-4905-8ba2-45d71f2a4cdb\goal-objective.md`
- Scope executed: followed the approval-to-build gate plan until the human build approval gate. No distinct approval token or named approval artifact was present, so the broad build remained blocked and no build was executed.
- Result:
  - No separate build approval was found for exact token `APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY`.
  - Refreshed report-only raw/source readiness for `broad_manifest_527_rebuild_v1`.
  - Refreshed report-only gate summary after readiness refresh.
  - Gate summary status remains `BLOCKED_NO_BUILD_APPROVAL`.
  - Gate decision remains `broad_rebuild_blocked`.
  - Raw/source readiness status remains `READY_FOR_SEPARATE_BUILD_APPROVAL`.
  - Input-only ready rows remain `461`.
  - Deferred policy-review rows remain `66`.
  - Blocked source-artifact rows remain `0`.
  - Blocked pairs remain none.
  - Approval flags remain false: `data_mutation_performed=false`, `build_approved=false`, `restore_approved=false`, `repair_approved=false`, `exclusion_approved=false`, `source_action_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, and `research_use_allowed=false`.
  - `data\causal_base_candidates\broad_manifest_527_rebuild_v1` does not exist.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\b71aa000-c47a-4905-8ba2-45d71f2a4cdb\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw AGENTS.md`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 120`
  - `rg -n "APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY" .`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_prebuild_plan.json`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
  - `python -m pytest tests/validation/test_plan_broad_causal_rebuild.py tests/validation/test_validate_broad_causal_raw_source_readiness.py tests/validation/test_summarize_broad_causal_rebuild_gate.py`
  - `python -m scripts.validation.validate_broad_causal_raw_source_readiness --repo-root .`
  - `python -m scripts.validation.summarize_broad_causal_rebuild_gate --repo-root .`
  - `rg -n "BLOCKED_NO_BUILD_APPROVAL|READY_FOR_SEPARATE_BUILD_APPROVAL|input_only_ready_rows|blocked_source_artifact_rows|build_approved|broader_modeling_approved|config_promotion_approved|research_use_allowed" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1`
- Validation:
  - Focused pre-build tests passed: `17 passed`.
  - Readiness refresh passed and printed `status=READY_FOR_SEPARATE_BUILD_APPROVAL`, `expected_rows=527`, `checked_action_required_rows=461`.
  - Gate summary refresh passed and printed `status=BLOCKED_NO_BUILD_APPROVAL`, `gate_decision=broad_rebuild_blocked`, `ready_for_build_rows=0`, `blocked_source_artifact_rows=0`.
  - Targeted assertions found `BLOCKED_NO_BUILD_APPROVAL`, `READY_FOR_SEPARATE_BUILD_APPROVAL`, `input_only_ready_rows`, `blocked_source_artifact_rows`, and false approval/modeling/promotion flags in the refreshed gate summary JSON/Markdown.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
  - `Test-Path data\causal_base_candidates\broad_manifest_527_rebuild_v1` returned `False`.
- Unresolved blockers:
  - Severe: separate human broad build approval is absent, so no build execution is allowed.
  - Broad root remains not built, not validated, not promoted, and not approved for broader modeling.
  - `READY_FOR_SEPARATE_BUILD_APPROVAL` is input readiness only; it is not broad build approval.
  - `66` deferred policy-review rows remain non-research and must not be built in the 461-row approved path.
  - Worktree remains dirty with pre-existing tracked/untracked report/tooling state. No staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed in this scope.
  - No `configs/**` mutation was performed.
  - No provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commits, build execution, or config promotion were performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: obtain or record the separate human build approval decision for broad_manifest_527_rebuild_v1.
Rules:
- Do not mutate data/** unless the current user message or a named approval artifact contains exactly: APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_461_READY_ROWS_ONLY.
- Do not change configs/data_manifest.yaml.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, source repair, exclusion execution, build execution, or config promotion without the explicit gate approval above.
- Do not build the 66 deferred_policy_review_not_checked rows.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use the refreshed current evidence:
  - reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_raw_source_readiness.json
  - reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_gate_summary.json
- If exact approval is absent, keep broad_manifest_527_rebuild_v1 blocked with report-only evidence.
- If exact approval is present, plan the approved 461-row ready-only build path, including generation of a ready-only include file, preflight readiness-only build check, scoped build execution to data/causal_base_candidates/broad_manifest_527_rebuild_v1, post-build validation, and a separate stop before config promotion or modeling.
Stop when:
- The exact human build approval decision is recorded, or broad_manifest_527_rebuild_v1 remains explicitly blocked with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
```

## Broad Causal Rebuild Gate Summary Post-Resolution - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\62bc9876-fdff-4b20-ade1-731cb4aca61a\goal-objective.md`
- Scope executed: updated the report-only `broad_manifest_527_rebuild_v1` gate summary after `SR1:2020` and `SR3:2020` source-hash resolution.
- Result:
  - Updated `scripts\validation\summarize_broad_causal_rebuild_gate.py` to validate the post-resolution readiness state.
  - Updated `tests\validation\test_summarize_broad_causal_rebuild_gate.py` for zero source-reference failures, two resolved source-hash rows, and fail-closed source-resolution checks.
  - Regenerated:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md`
  - Gate summary status remains `BLOCKED_NO_BUILD_APPROVAL`.
  - Gate decision remains `broad_rebuild_blocked`.
  - Block reason is now `raw_source_hash_readiness_passed_but_separate_broad_build_approval_missing`.
  - Raw/source readiness status is `READY_FOR_SEPARATE_BUILD_APPROVAL`.
  - Input-only ready rows: `461`.
  - Blocked source-artifact rows: `0`.
  - Blocked pairs: none.
  - Resolved source-hash pairs: `SR1:2020`, `SR3:2020`.
  - Approval flags remain false: `data_mutation_performed=false`, `build_approved=false`, `restore_approved=false`, `repair_approved=false`, `exclusion_approved=false`, `source_action_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, and `research_use_allowed=false`.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - `scripts\validation\summarize_broad_causal_rebuild_gate.py`
  - `tests\validation\test_summarize_broad_causal_rebuild_gate.py`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\62bc9876-fdff-4b20-ade1-731cb4aca61a\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Get-Content -Raw scripts\validation\summarize_broad_causal_rebuild_gate.py`
  - `Get-Content -Raw tests\validation\test_summarize_broad_causal_rebuild_gate.py`
  - Parsed summaries from:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\source_hash_mismatch_resolution.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy_selection.json`
  - `python -m pytest tests/validation/test_summarize_broad_causal_rebuild_gate.py`
  - `python -m scripts.validation.summarize_broad_causal_rebuild_gate --repo-root .`
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json`
  - `rg -n "BLOCKED_NO_BUILD_APPROVAL|READY_FOR_SEPARATE_BUILD_APPROVAL|blocked_source_artifact_rows|input_only_ready_rows|source_hash_mismatch_resolution|build_approved|broader_modeling_approved|config_promotion_approved|research_use_allowed" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `git status --short`
- Validation:
  - Focused gate summary tests passed: `8 passed`.
  - Gate summary generation passed and printed `status=BLOCKED_NO_BUILD_APPROVAL`, `ready_for_build_rows=0`, `blocked_source_artifact_rows=0`.
  - Gate summary JSON parsed successfully.
  - Targeted report assertions found `BLOCKED_NO_BUILD_APPROVAL`, `READY_FOR_SEPARATE_BUILD_APPROVAL`, `blocked_source_artifact_rows`, `input_only_ready_rows`, `source_hash_mismatch_resolution`, and false approval flags.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
- Unresolved blockers:
  - No source-reference failures remain in the current raw/source/hash readiness gate.
  - Broad root remains not built, not validated, not promoted, and not approved for broader modeling.
  - `READY_FOR_SEPARATE_BUILD_APPROVAL` is input readiness only; it is not broad build approval.
  - Current configured canonical causal coverage remains `8/527` unless `configs/data_manifest.yaml` is changed by a separate approved policy decision.
  - `66` deferred policy-review rows remain non-research and not checked.
  - Worktree remains dirty with pre-existing tracked/untracked report/tooling state. No staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed in this scope.
  - No `configs/**` mutation was performed.
  - No provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, staging, commits, build execution, or config promotion were performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: request or record the separate human broad build approval decision for broad_manifest_527_rebuild_v1 after input readiness passed.
Rules:
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, source repair, exclusion execution, build execution, or config promotion.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use the current post-resolution gate summary as input evidence:
  - `reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_gate_summary.json`
  - `reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_gate_summary.md`
- Produce a plan for exactly one small report-only step that records whether a human approves broad build execution for `data/causal_base_candidates/broad_manifest_527_rebuild_v1` or keeps broad build explicitly blocked.
Stop when:
- The separate build-approval decision is recorded in report-only evidence, or broad_manifest_527_rebuild_v1 remains explicitly blocked with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
```

## SR Parent 2020 Source Hash Resolution - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Scope executed: resolved the `SR1:2020` and `SR3:2020` source-hash blocker for broad_manifest_527_rebuild_v1 readiness by verifying current local parent DBNs rebuild to the existing raw parquet core OHLCV/front-contract identity rows, then updating only the raw parquet `source_sha256` provenance values to the current local DBN hashes.
- Result:
  - Missing-file blocker was already cleared.
  - `SR1:2020` current source file: `data/dbn_sr_parent_candidate/SR1/2020/2020-01-01_2021-01-01.dbn.zst`.
  - `SR1:2020` source hash updated in raw provenance from `8b42a88a15d5115d86488909caf4f103c99c19fb999e5777ef4e090b47c6e79c` to `4ef063289d591e6aeeb4ee646afd7f6153a747ccdda6ddfd8841690fe127dd91`.
  - `SR3:2020` current source file: `data/dbn_sr_parent_candidate/SR3/2020/2020-01-01_2021-01-01.dbn.zst`.
  - `SR3:2020` source hash updated in raw provenance from `41a55dc79af7bad6b1f666b0fd6838cabca019c01b8b2c104bc7beab7e986265` to `74ab12437e9a0b781bc09a2dca892ff63be3d3007eef0e15fef0916152ef2f80`.
  - In-memory deterministic front-contract candidate rebuild from the current parent DBNs returned `CORE_MATCH` against existing raw core columns for both rows:
    - `SR1:2020`: `8566` rows.
    - `SR3:2020`: `3461` rows.
  - New raw parquet hashes after provenance-only repair:
    - `data/raw/SR1/2020.parquet`: `bde36b5172fe55e66535fc4d79f7ec71760c9c0cbc38ddaaa33d1bbd593a205c`.
    - `data/raw/SR3/2020.parquet`: `f6cc8cebd1cdca1a03f732e299296b608a2c96730cd78fc6d939944b6b78b6cf`.
  - Raw/source/hash readiness now reports `READY_FOR_SEPARATE_BUILD_APPROVAL`.
  - Readiness status counts now include `ready_for_build_input_only=461`, `action_required_source_reference_failure=0`, and `deferred_policy_review_not_checked=66`.
  - `SR1:2020` and `SR3:2020` now both report `ready_for_build_input_only`.
  - Approval flags remain false: `build_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, `research_use_allowed=false`.
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - `data/raw/SR1/2020.parquet`
  - `data/raw/SR3/2020.parquet`
  - `reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_raw_source_readiness.json`
  - `reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_raw_source_readiness.md`
  - `reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/post_download_raw_source_readiness.json`
  - `reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/post_download_raw_source_readiness.md`
  - `reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/source_hash_mismatch_resolution.json`
  - `reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/source_hash_mismatch_resolution.md`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Get-Content -Raw scripts/validation/validate_broad_causal_raw_source_readiness.py`
  - `rg -n "source_sha256|SR1|SR3|dbn_sr_parent_candidate|build_front_contract_candidate|convert_dbn_archive_to_raw" scripts tests reports configs CODEX_HANDOFF.md`
  - `Test-Path data/dbn/definition/SR1/2020/2020-01-01_2021-01-01.dbn.zst`
  - `Test-Path data/dbn/definition/SR3/2020/2020-01-01_2021-01-01.dbn.zst`
  - `Test-Path data/dbn/status/SR1/2020/2020-01-01_2021-01-01.dbn.zst`
  - `Test-Path data/dbn/status/SR3/2020/2020-01-01_2021-01-01.dbn.zst`
  - `Test-Path data/dbn/statistics/SR1/2020/2020-01-01_2021-01-01.dbn.zst`
  - `Test-Path data/dbn/statistics/SR3/2020/2020-01-01_2021-01-01.dbn.zst`
  - In-memory Python comparison using existing deterministic front-contract candidate logic.
  - Metadata-only Python provenance repair for `source_sha256` in `data/raw/SR1/2020.parquet` and `data/raw/SR3/2020.parquet`.
  - `python -m scripts.validation.validate_broad_causal_raw_source_readiness --repo-root .`
  - `python -m scripts.validation.validate_broad_causal_raw_source_readiness --repo-root . --json-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/post_download_raw_source_readiness.json --markdown-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/post_download_raw_source_readiness.md`
  - `python -m json.tool reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/source_hash_mismatch_resolution.json`
  - `python -m pytest tests/validation/test_validate_broad_causal_raw_source_readiness.py`
- Validation:
  - Current local parent DBNs rebuilt in memory to the same core OHLCV/front-contract identity rows as existing raw parquet for both `SR1:2020` and `SR3:2020`.
  - `source_hash_mismatch_resolution.json` parsed successfully.
  - Focused readiness tests passed: `python -m pytest tests/validation/test_validate_broad_causal_raw_source_readiness.py` returned `5 passed`.
  - Post-repair readiness command returned `READY_FOR_SEPARATE_BUILD_APPROVAL`.
  - JSON/Markdown assertions verified `RESOLVED_FOR_SOURCE_READINESS`, `CORE_MATCH`, `READY_FOR_SEPARATE_BUILD_APPROVAL`, `action_required_source_reference_failure=0`, and false approval flags.
- Unresolved blockers:
  - Source-hash blocker is resolved for raw/source/hash readiness.
  - `READY_FOR_SEPARATE_BUILD_APPROVAL` is not build approval.
  - The broad root remains not built, not validated, not promoted, and not approved for broader modeling.
  - Current configured canonical causal coverage remains `8/527` unless `configs/data_manifest.yaml` is changed by a separate approved policy decision.
  - `66` deferred policy-review rows remain non-research and not checked.
  - `scripts/validation/summarize_broad_causal_rebuild_gate.py` still contains stale expected counts from the pre-resolution blocker state and should be updated or regenerated before using it as current gate evidence.
  - No config promotion, broad build execution, WFA/modeling, predictions, metrics, cleanup, staging, or commit was performed.
- Safety:
  - No `configs/**` mutation was performed.
  - Data mutation in this scope was limited to the `source_sha256` provenance values in `data/raw/SR1/2020.parquet` and `data/raw/SR3/2020.parquet`.
  - No provider/network command was run in this resolution scope.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: update the report-only broad_manifest_527_rebuild_v1 gate summary after the SR1:2020 and SR3:2020 source-hash resolution.
Rules:
- Do not mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, source repair, exclusion execution, build execution, or config promotion.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Treat the current raw/source/hash readiness report as `READY_FOR_SEPARATE_BUILD_APPROVAL` with `ready_for_build_input_only=461`, `action_required_source_reference_failure=0`, and `deferred_policy_review_not_checked=66`.
- Update only the report-only gate summary logic/artifact needed to remove the stale two-source-failure assumption and preserve false approval flags.
Stop when:
- The post-resolution broad rebuild gate summary is recorded and tested, or broad_manifest_527_rebuild_v1 remains explicitly blocked with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
```

## SR Parent 2020 Source Download Hash Gate - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\3977411a-cf24-42fa-8095-05ab4272d3df\goal-objective.md`
- Scope executed: downloaded only the two requested Databento parent OHLCV DBN source artifacts for `SR1:2020` and `SR3:2020` to the exact requested `data\dbn_sr_parent_candidate` paths, after dry-run and zero-cost gates passed.
- Result:
  - Dry-run planned exactly `2` tasks.
  - Dry-run output paths were exactly:
    - `data/dbn_sr_parent_candidate/SR1/2020/2020-01-01_2021-01-01.dbn.zst`
    - `data/dbn_sr_parent_candidate/SR3/2020/2020-01-01_2021-01-01.dbn.zst`
  - Zero-cost estimate passed: `TOTAL_ESTIMATED_COST_USD 0.0000`, `TOTAL_ESTIMATE_ERRORS 0`, `ZERO_COST_GATE status=PASS downloadable=2`.
  - Download wrote:
    - `data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst`
    - `data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
    - `data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst`
    - `data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
  - Bounded report folder written:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\`
  - Download manifests record expected request spec: `GLBX.MDP3`, `ohlcv-1m`, `parent`, `instrument_id`, `dbn`, `zstd`, `SR1.FUT`/`SR3.FUT`, `request_status=ok`.
  - Hash gate failed:
    - `SR1` expected `8b42a88a15d5115d86488909caf4f103c99c19fb999e5777ef4e090b47c6e79c`, actual `4ef063289d591e6aeeb4ee646afd7f6153a747ccdda6ddfd8841690fe127dd91`.
    - `SR3` expected `41a55dc79af7bad6b1f666b0fd6838cabca019c01b8b2c104bc7beab7e986265`, actual `74ab12437e9a0b781bc09a2dca892ff63be3d3007eef0e15fef0916152ef2f80`.
  - Post-download raw/source readiness validation was then run as bounded report-only evidence, and it remained `ACTION_REQUIRED`.
  - Post-download readiness status counts: `ready_for_build_input_only=459`, `action_required_source_reference_failure=2`, `deferred_policy_review_not_checked=66`.
  - The two remaining source-reference failures are now hash mismatches, not missing files:
    - `SR1:2020` has `source_present=true`, `hash_matches=false`, `readiness_status=action_required_source_reference_failure`.
    - `SR3:2020` has `source_present=true`, `hash_matches=false`, `readiness_status=action_required_source_reference_failure`.
  - The readiness report records `build_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, and `research_use_allowed=false`.
  - Added report-only hash-mismatch disposition:
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\source_hash_mismatch_disposition.json`
    - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\source_hash_mismatch_disposition.md`
  - Disposition status: `ACTION_REQUIRED`.
  - Disposition decision: `hash_mismatch_blocked`.
  - The disposition records that the missing-source-artifact blocker is cleared, but the source-hash blocker is not cleared.
  - Required human policy decision options now recorded:
    - `continue_block_no_action`
    - `approve_accept_current_provider_hashes_via_separate_manifest_policy`
    - `approve_restore_historical_artifacts_after_validation`
    - `approve_new_provider_download_attempt_with_overwrite_and_hash_policy`
- Files changed in this scope:
  - `CODEX_HANDOFF.md`
  - `data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst`
  - `data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
  - `data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst`
  - `data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\databento_download_plan_dry_run.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\databento_cost_estimate.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\databento_download_plan.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\databento_download_results.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\databento_zero_cost_gate.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\dbn_chunk_manifest.csv`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\dbn_download_manifest.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\post_download_raw_source_readiness.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\post_download_raw_source_readiness.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\source_hash_mismatch_disposition.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\source_hash_mismatch_disposition.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\3977411a-cf24-42fa-8095-05ab4272d3df\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Test-Path data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst`
  - `Test-Path data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst`
  - `Test-Path data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
  - `Test-Path data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
  - `git diff --name-only -- configs`
  - `git diff --name-only -- data`
  - `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --raw-format dbn-zstd --symbols SR1,SR3 --dataset GLBX.MDP3 --schema ohlcv-1m --stype-in parent --stype-out instrument_id --start 2020-01-01 --end 2021-01-01 --chunk year --dbn-root data/dbn_sr_parent_candidate --reports-root reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download --plan-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/databento_download_plan.json --workers 1 --dry-run`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\databento_download_plan_dry_run.json`
  - `rg -n "total_tasks|tasks|SR1.FUT|SR3.FUT|data/dbn_sr_parent_candidate/SR1/2020/2020-01-01_2021-01-01.dbn.zst|data/dbn_sr_parent_candidate/SR3/2020/2020-01-01_2021-01-01.dbn.zst|GLBX.MDP3|ohlcv-1m|parent|instrument_id|dbn-zstd" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\databento_download_plan_dry_run.json`
  - `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --raw-format dbn-zstd --symbols SR1,SR3 --dataset GLBX.MDP3 --schema ohlcv-1m --stype-in parent --stype-out instrument_id --start 2020-01-01 --end 2021-01-01 --chunk year --dbn-root data/dbn_sr_parent_candidate --reports-root reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download --plan-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/databento_download_plan.json --workers 1 --estimate-cost --zero-cost-only`
  - Same estimate command rerun with scoped network approval after the sandbox proxy blocked the first attempt.
  - `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --raw-format dbn-zstd --symbols SR1,SR3 --dataset GLBX.MDP3 --schema ohlcv-1m --stype-in parent --stype-out instrument_id --start 2020-01-01 --end 2021-01-01 --chunk year --dbn-root data/dbn_sr_parent_candidate --reports-root reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download --plan-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/databento_download_plan.json --workers 1 --zero-cost-only`
  - `Get-FileHash -Algorithm SHA256 data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst`
  - `Get-FileHash -Algorithm SHA256 data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst`
  - `rg -n "GLBX.MDP3|ohlcv-1m|SR1.FUT|SR3.FUT|parent|instrument_id|dbn|zstd|request_status|file_sha256" data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
  - `Get-ChildItem -Force data\dbn_sr_parent_candidate\SR1\2020`
  - `Get-ChildItem -Force data\dbn_sr_parent_candidate\SR3\2020`
  - `Get-ChildItem -Force reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download`
  - `python -m scripts.validation.validate_broad_causal_raw_source_readiness --repo-root . --json-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/post_download_raw_source_readiness.json --markdown-out reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/post_download_raw_source_readiness.md`
  - `rg -n -C 8 "SR1|SR3|source_sha256_mismatch|source_reference_failure|READY_FOR_SEPARATE_BUILD_APPROVAL|ACTION_REQUIRED|build_approved|broader_modeling_approved|config_promotion_approved|4ef063289d591e6aeeb4ee646afd7f6153a747ccdda6ddfd8841690fe127dd91|74ab12437e9a0b781bc09a2dca892ff63be3d3007eef0e15fef0916152ef2f80" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\post_download_raw_source_readiness.json`
  - `rg -n "ACTION_REQUIRED|SR1:2020|SR3:2020|source_sha256_mismatch|ready_for_build_input_only|build_approved|broader_modeling_approved|config_promotion_approved" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\post_download_raw_source_readiness.md`
  - `Get-Content -Raw data\dbn_sr_parent_candidate\SR1\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
  - `Get-Content -Raw data\dbn_sr_parent_candidate\SR3\2020\2020-01-01_2021-01-01.dbn.zst.manifest.json`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\dbn_download_manifest.json`
  - `rg -n "8b42a88a15d5115d86488909caf4f103c99c19fb999e5777ef4e090b47c6e79c|41a55dc79af7bad6b1f666b0fd6838cabca019c01b8b2c104bc7beab7e986265|4ef063289d591e6aeeb4ee646afd7f6153a747ccdda6ddfd8841690fe127dd91|74ab12437e9a0b781bc09a2dca892ff63be3d3007eef0e15fef0916152ef2f80" reports configs scripts tests CODEX_HANDOFF.md`
  - `python -c "import hashlib, pathlib; import zstandard as zstd; ..."` to compute compressed and decompressed SHA256 evidence without writing data.
  - `python -m json.tool reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\source_hash_mismatch_disposition.json`
  - `rg -n "ACTION_REQUIRED|hash_mismatch_blocked|blocked_hash_mismatch|SR1:2020|SR3:2020|4ef063289d591e6aeeb4ee646afd7f6153a747ccdda6ddfd8841690fe127dd91|74ab12437e9a0b781bc09a2dca892ff63be3d3007eef0e15fef0916152ef2f80|build_approved|broader_modeling_approved|config_promotion_approved|approve_accept_current_provider_hashes" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\source_hash_mismatch_disposition.json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\source_hash_mismatch_disposition.md`
- Validation:
  - Dry-run task/path gate passed exactly.
  - Zero-cost estimate gate passed after scoped network approval.
  - File and sidecar existence checks passed.
  - Manifest spec checks passed.
  - Hash gate failed for both downloaded DBN files.
  - Post-download readiness validation passed as a command but returned report status `ACTION_REQUIRED`, with both blocked rows now failing on source hash mismatch.
  - Report-only hash-mismatch disposition JSON parsed successfully and Markdown/JSON assertions verified `ACTION_REQUIRED`, `hash_mismatch_blocked`, both pairs, actual hashes, and false approval flags.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --name-only -- data` returned no paths.
  - `git status --short` remains dirty with pre-existing tracked/untracked report/tooling state; generated `data/**` and bounded report artifacts are not shown as tracked changes.
- Unresolved blockers:
  - Severe: downloaded `SR1:2020` and `SR3:2020` source artifacts do not match the expected hashes recorded by the objective/prebuild evidence, so they cannot be treated as validated canonical broad source artifacts.
  - Broad root remains not built, not promoted, and not approved for modeling.
  - Current configured canonical causal coverage remains `8/527`.
  - No config promotion, source hash update, build execution, WFA/modeling, metrics, staging, or commit was performed.
- Safety:
  - No `configs/**` mutation was performed.
  - `data/**` mutation was limited to the two exact DBN files and their two exact manifest sidecars.
  - Report writes were limited to `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\sr_parent_2020_source_download\`.
  - No provider command beyond dry-run, estimate, and the two bounded Databento downloads was run.
  - No WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, restore, source repair beyond the requested download, exclusion execution, build execution, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: plan a report-only hash-mismatch disposition for the freshly downloaded SR1:2020 and SR3:2020 Databento parent OHLCV source artifacts.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not change configs/data_manifest.yaml.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, exclusion execution, build execution, or config promotion.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use only current local evidence:
  - data/dbn_sr_parent_candidate/SR1/2020/2020-01-01_2021-01-01.dbn.zst.manifest.json
  - data/dbn_sr_parent_candidate/SR3/2020/2020-01-01_2021-01-01.dbn.zst.manifest.json
  - reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/sr_parent_2020_source_download/**
  - reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_raw_source_readiness.json
- Produce a plan for exactly one small report-only validator/disposition artifact that records the expected-vs-actual hash mismatch and keeps broad_manifest_527_rebuild_v1 blocked unless a separate human policy decision approves accepting current provider hashes or rerunning with a different source.
Stop when:
- A decision-complete plan exists for report-only hash-mismatch disposition, or the broad rebuild remains explicitly blocked with no build, config promotion, data mutation, source restore/exclusion action, or broader modeling approval.
```

## Broad Causal Rebuild Gate Summary - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\4a2cdbd9-c427-4aa4-a49e-76ce2cddc5a8\goal-objective.md`
- Scope executed: added and ran one report-only `broad_manifest_527_rebuild_v1` gate summary after the selected `continue_block_no_action` policy option for `SR1:2020` and `SR3:2020`.
- Result:
  - Added `scripts\validation\summarize_broad_causal_rebuild_gate.py`.
  - Added `tests\validation\test_summarize_broad_causal_rebuild_gate.py`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md`.
  - Gate summary status: `BLOCKED_NO_BUILD_APPROVAL`.
  - Gate decision: `broad_rebuild_blocked`.
  - Future root: `data/causal_base_candidates/broad_manifest_527_rebuild_v1`.
  - Expected rows: `527`.
  - Ready-for-build rows: `0`.
  - Input-only ready rows: `459`.
  - Blocked source-artifact rows: `2`.
  - Blocked pairs: `SR1:2020`, `SR3:2020`.
  - Selected decision option: `continue_block_no_action`.
  - Approved action: `none`.
  - The report explicitly records `data_mutation_performed=false`, `build_approved=false`, `restore_approved=false`, `repair_approved=false`, `exclusion_approved=false`, `source_action_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, and `research_use_allowed=false`.
- Files changed in this scope:
  - `scripts\validation\summarize_broad_causal_rebuild_gate.py`
  - `tests\validation\test_summarize_broad_causal_rebuild_gate.py`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\4a2cdbd9-c427-4aa4-a49e-76ce2cddc5a8\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Get-Content -Raw scripts\validation\record_broad_causal_source_artifact_policy_selection.py`
  - `Get-Content -Raw tests\validation\test_record_broad_causal_source_artifact_policy_selection.py`
  - `rg -n "OUTPUT_STAGE|EXPECTED_|FALSE_FLAGS|future_root|expected_rows|ready_for_build|ACTION_REQUIRED|deferred_policy_review|source_reference_failure|source_action_approved|broader_modeling_approved|config_promotion_approved" scripts\validation\plan_broad_causal_rebuild.py scripts\validation\validate_broad_causal_raw_source_readiness.py`
  - `rg -n "summary|rows|ready_for_build|source_reference_failure|SR1:2020|SR3:2020|future_root|expected_rows" tests\validation\test_plan_broad_causal_rebuild.py tests\validation\test_validate_broad_causal_raw_source_readiness.py`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_prebuild_plan.json`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy_selection.json`
  - `rg -n -C 6 "SR1|SR3|dbn_sr_parent_candidate|action_required_source_reference_failure" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
  - `Get-Content -Raw scripts\validation\validate_broad_causal_raw_source_readiness.py`
  - `Get-Content -Raw scripts\validation\plan_broad_causal_rebuild.py`
  - `python -m pytest tests/validation/test_summarize_broad_causal_rebuild_gate.py`
  - `python -m scripts.validation.summarize_broad_causal_rebuild_gate --repo-root .`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md -TotalCount 90`
  - `rg -n "BLOCKED_NO_BUILD_APPROVAL|broad_rebuild_blocked|ready_for_build_rows|input_only_ready_rows|blocked_source_artifact_rows|SR1:2020|SR3:2020|build_approved|config_promotion_approved|broader_modeling_approved|source_action_approved" reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_gate_summary.md`
  - `git diff --name-only -- data`
  - `git diff --name-only -- configs`
  - `git diff --check -- CODEX_HANDOFF.md scripts\validation\summarize_broad_causal_rebuild_gate.py tests\validation\test_summarize_broad_causal_rebuild_gate.py`
  - `git status --short`
- Validation:
  - Focused test passed: `python -m pytest tests/validation/test_summarize_broad_causal_rebuild_gate.py` -> `6 passed`.
  - Real report-only command passed and wrote JSON/Markdown outputs: `broad_causal_rebuild_gate_summary status=BLOCKED_NO_BUILD_APPROVAL gate_decision=broad_rebuild_blocked ready_for_build_rows=0 blocked_source_artifact_rows=2`.
  - Targeted Markdown read verified `BLOCKED_NO_BUILD_APPROVAL`, `broad_rebuild_blocked`, future root, expected rows `527`, ready-for-build rows `0`, input-only ready rows `459`, blocked source-artifact rows `2`, both blocked pairs, selected option `continue_block_no_action`, approved action `none`, and false approval flags.
  - Targeted `rg` verified blocked status, gate decision, row counts, both pairs, and false build/config/modeling/source-action flags in JSON/Markdown.
  - `git diff --name-only -- data` returned no paths.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --check` passed with only the existing `CODEX_HANDOFF.md` LF-to-CRLF warning.
- Unresolved blockers:
  - `SR1:2020` and `SR3:2020` remain blocked by absent current referenced source files under `data/dbn_sr_parent_candidate`.
  - The selected policy option explicitly approves no source repair, restore, exclusion, build execution, config promotion, broader modeling, production/live use, or model promotion.
  - `broad_manifest_527_rebuild_v1` has not been built, validated, promoted, or approved for modeling.
  - Current configured canonical causal coverage remains `8/527`.
  - Worktree remains dirty with pre-existing tracked report/handoff state and new report-only tooling; no staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, archive/quarantine execution, restore, source repair, exclusion execution, build execution, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: plan the next human project-direction decision after the broad_manifest_527_rebuild_v1 gate summary.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, source repair, exclusion execution, build execution, or config promotion.
- Treat current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved config decision after a validated broad root exists.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_gate_summary.json as the evidence source.
- Choose the next report-only policy direction only: keep broad_manifest_527_rebuild_v1 paused/blocked, reopen a separate source repair/restore policy plan for SR1:2020 and SR3:2020, or reopen a separate policy exclusion/deferment plan for those two rows.
- Produce a decision-complete plan for recording only that project-direction decision, with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
Stop when:
- A decision-complete plan exists for recording the next project-direction decision, or broad_manifest_527_rebuild_v1 remains explicitly blocked with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
```

## Broad Causal Source Artifact Policy Selection - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\3aacb342-d4b6-40a4-990c-9c3a185490d3\goal-objective.md`
- Scope executed: recorded the selected human policy option `continue_block_no_action` for the two blocked broad source artifacts; report-only with no source/data/build/config/modeling approval.
- Result:
  - Added `scripts\validation\record_broad_causal_source_artifact_policy_selection.py`.
  - Added `tests\validation\test_record_broad_causal_source_artifact_policy_selection.py`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy_selection.json`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy_selection.md`.
  - Input request evidence was `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_next_policy_request.json`.
  - Policy selection status: `ACTION_REQUIRED`.
  - Selected decision option: `continue_block_no_action`.
  - Human decision recorded: `true`.
  - Approved action: `none`.
  - Pair count: `2`.
  - Pairs: `SR1:2020`, `SR3:2020`.
  - Both rows remain blocked by absent current source artifacts.
  - The report explicitly records `data_mutation_performed=false`, `build_approved=false`, `restore_approved=false`, `repair_approved=false`, `exclusion_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, `research_use_allowed=false`, and `source_action_approved=false`.
- Files changed in this scope:
  - `scripts\validation\record_broad_causal_source_artifact_policy_selection.py`
  - `tests\validation\test_record_broad_causal_source_artifact_policy_selection.py`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy_selection.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy_selection.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\3aacb342-d4b6-40a4-990c-9c3a185490d3\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 130`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_next_policy_request.md -TotalCount 90`
  - `Get-Content scripts\validation\request_broad_causal_source_artifact_policy_decision.py`
  - `Get-Content tests\validation\test_request_broad_causal_source_artifact_policy_decision.py`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_next_policy_request.json -TotalCount 140`
  - `python -m pytest tests/validation/test_record_broad_causal_source_artifact_policy_selection.py`
  - `python -m scripts.validation.record_broad_causal_source_artifact_policy_selection --repo-root .`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy_selection.md -TotalCount 90`
  - `rg -n "continue_block_no_action|human_decision_recorded|SR1:2020|SR3:2020|approved_action|source_action_approved|restore_approved|repair_approved|exclusion_approved|broader_modeling_approved|config_promotion_approved|ACTION_REQUIRED" reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_policy_selection.json reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_policy_selection.md`
  - `git diff --name-only -- data`
  - `git diff --name-only -- configs`
  - `git diff --check -- CODEX_HANDOFF.md scripts/validation/record_broad_causal_source_artifact_policy_selection.py tests/validation/test_record_broad_causal_source_artifact_policy_selection.py`
  - `git status --short`
- Validation:
  - Focused test passed: `python -m pytest tests/validation/test_record_broad_causal_source_artifact_policy_selection.py` -> `7 passed`.
  - Real report-only command passed and wrote JSON/Markdown outputs: `broad_causal_source_artifact_policy_selection status=ACTION_REQUIRED selected_decision_option=continue_block_no_action pair_count=2`.
  - Targeted Markdown read verified `ACTION_REQUIRED`, selected option `continue_block_no_action`, human decision recorded, both pairs, approved action `none`, and false approval flags.
  - Targeted `rg` verified both rows, selected option, human decision, approved action `none`, action-required status, and false restore/repair/exclusion/modeling/config/source-action flags in JSON/Markdown.
  - `git diff --name-only -- data` returned no paths.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --check` passed with only the existing `CODEX_HANDOFF.md` LF-to-CRLF warning.
- Unresolved blockers:
  - `SR1:2020` and `SR3:2020` remain blocked by absent current referenced source files under `data/dbn_sr_parent_candidate`.
  - The selected policy option explicitly approves no source repair, restore, exclusion, build execution, config promotion, broader modeling, production/live use, or model promotion.
  - The broad root has not been built, validated, promoted, or approved for modeling.
  - Current configured canonical causal coverage remains `8/527`.
  - Worktree remains dirty with pre-existing tracked report/handoff state and new report-only tooling; no staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, archive/quarantine execution, restore, source repair, exclusion execution, build execution, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: plan a report-only broad_manifest_527_rebuild_v1 gate summary after the continue_block_no_action policy selection.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, source repair, exclusion execution, build execution, or config promotion.
- Treat current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved config decision after a validated broad root exists.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_policy_selection.json as the evidence source.
- Focus only on summarizing the gate result: SR1:2020 and SR3:2020 remain blocked, no source action is approved, and broad_manifest_527_rebuild_v1 remains not build-approved.
- Define exact report-only outputs, required evidence fields, validation commands, and stop conditions.
Stop when:
- A decision-complete plan exists for recording the broad rebuild gate summary, or the broad rebuild remains explicitly blocked with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
```

## Broad Causal Source Artifact Next Policy Request - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\0d30f456-e04b-4016-b2b0-826618250b86\goal-objective.md`
- Scope executed: added and ran one report-only next-policy-decision request for the two blocked broad source artifacts; no source repair/restore/exclusion/build/config/modeling approval.
- Result:
  - Added `scripts\validation\request_broad_causal_source_artifact_policy_decision.py`.
  - Added `tests\validation\test_request_broad_causal_source_artifact_policy_decision.py`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_next_policy_request.json`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_next_policy_request.md`.
  - Input policy evidence was `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy.json`.
  - Request status: `HUMAN_DECISION_REQUIRED`.
  - Current decision: `continued_block_no_source_action_approved`.
  - Requested decision options: `approve_separate_source_repair_restore_plan`, `approve_policy_exclusion_deferment_plan`, `continue_block_no_action`.
  - Selected decision option: `None`.
  - Approved action: `none`.
  - Pair count: `2`.
  - Pairs: `SR1:2020`, `SR3:2020`.
  - The report explicitly records `data_mutation_performed=false`, `build_approved=false`, `restore_approved=false`, `repair_approved=false`, `exclusion_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, `research_use_allowed=false`, and `source_action_approved=false`.
- Files changed in this scope:
  - `scripts\validation\request_broad_causal_source_artifact_policy_decision.py`
  - `tests\validation\test_request_broad_causal_source_artifact_policy_decision.py`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_next_policy_request.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_next_policy_request.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\0d30f456-e04b-4016-b2b0-826618250b86\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 120`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy.md -TotalCount 90`
  - `Get-Content scripts\validation\record_broad_causal_source_artifact_policy.py`
  - `Get-Content tests\validation\test_record_broad_causal_source_artifact_policy.py`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy.json -TotalCount 130`
  - `python -m pytest tests/validation/test_request_broad_causal_source_artifact_policy_decision.py`
  - `python -m scripts.validation.request_broad_causal_source_artifact_policy_decision --repo-root .`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_next_policy_request.md -TotalCount 90`
  - `rg -n "HUMAN_DECISION_REQUIRED|approve_separate_source_repair_restore_plan|approve_policy_exclusion_deferment_plan|continue_block_no_action|SR1:2020|SR3:2020|source_action_approved|restore_approved|repair_approved|exclusion_approved|broader_modeling_approved|config_promotion_approved" reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_next_policy_request.json reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_next_policy_request.md`
  - `git diff --name-only -- data`
  - `git diff --name-only -- configs`
  - `git diff --check -- CODEX_HANDOFF.md scripts/validation/request_broad_causal_source_artifact_policy_decision.py tests/validation/test_request_broad_causal_source_artifact_policy_decision.py`
  - `git status --short`
- Validation:
  - Focused test passed: `python -m pytest tests/validation/test_request_broad_causal_source_artifact_policy_decision.py` -> `6 passed`.
  - Real report-only command passed and wrote JSON/Markdown outputs: `broad_causal_source_artifact_next_policy_request status=HUMAN_DECISION_REQUIRED current_decision=continued_block_no_source_action_approved pair_count=2`.
  - Targeted Markdown read verified `HUMAN_DECISION_REQUIRED`, the current continued-block decision, both pairs, all three requested decision options, selected option `None`, approved action `none`, and false approval flags.
  - Targeted `rg` verified both rows, all three decision options, human-decision-required status, and false restore/repair/exclusion/modeling/config/source-action flags in JSON/Markdown.
  - `git diff --name-only -- data` returned no paths.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --check` passed with only the existing `CODEX_HANDOFF.md` LF-to-CRLF warning.
- Unresolved blockers:
  - A human decision is still required to select one of `approve_separate_source_repair_restore_plan`, `approve_policy_exclusion_deferment_plan`, or `continue_block_no_action`.
  - `SR1:2020` and `SR3:2020` remain blocked by absent current referenced source files under `data/dbn_sr_parent_candidate`.
  - The request explicitly approves no source repair, restore, exclusion, build execution, config promotion, broader modeling, production/live use, or model promotion.
  - The broad root has not been built, validated, promoted, or approved for modeling.
  - Current configured canonical causal coverage remains `8/527`.
  - Worktree remains dirty with pre-existing tracked report/handoff state and new report-only tooling; no staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, archive/quarantine execution, restore, source repair, exclusion execution, build execution, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: make the human policy decision requested by broad_manifest_527_rebuild_source_artifact_next_policy_request.json for SR1:2020 and SR3:2020.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, source repair, exclusion execution, build execution, or config promotion.
- Treat current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved config decision after a validated broad root exists.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_next_policy_request.json as the evidence source.
- Choose exactly one policy option for SR1:2020 and SR3:2020: approve_separate_source_repair_restore_plan, approve_policy_exclusion_deferment_plan, or continue_block_no_action.
- Produce a plan for recording only that human decision in a report-only artifact with required false action/approval flags unless a future separate implementation plan is explicitly approved.
Stop when:
- A decision-complete plan exists for recording the selected human policy option, or the two rows remain explicitly blocked with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
```

## Broad Causal Source Artifact Policy Decision - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\bea4c2df-a4a9-415f-8b0f-0099f4ede2f7\pasted-text-1.txt`
- Scope executed: added and ran one report-only policy decision recorder for the two blocked broad source artifacts; no data/config/source action/build execution.
- Result:
  - Added `scripts\validation\record_broad_causal_source_artifact_policy.py`.
  - Added `tests\validation\test_record_broad_causal_source_artifact_policy.py`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy.json`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy.md`.
  - Input disposition evidence was `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.json`.
  - Policy status: `ACTION_REQUIRED`.
  - Policy decision: `continued_block_no_source_action_approved`.
  - Pair count: `2`.
  - Pairs: `SR1:2020`, `SR3:2020`.
  - Both rows remain `blocked_missing_current_source_artifact`.
  - Approved action: `none`.
  - The report explicitly records `data_mutation_performed=false`, `build_approved=false`, `restore_approved=false`, `repair_approved=false`, `exclusion_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, `research_use_allowed=false`, and `source_action_approved=false`.
- Files changed in this scope:
  - `scripts\validation\record_broad_causal_source_artifact_policy.py`
  - `tests\validation\test_record_broad_causal_source_artifact_policy.py`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\bea4c2df-a4a9-415f-8b0f-0099f4ede2f7\pasted-text-1.txt`
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 120`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.md -TotalCount 80`
  - `Get-Content scripts\validation\dispose_broad_causal_source_reference_failures.py`
  - `Get-Content tests\validation\test_dispose_broad_causal_source_reference_failures.py`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.json -TotalCount 150`
  - `python -m pytest tests/validation/test_record_broad_causal_source_artifact_policy.py`
  - `python -m scripts.validation.record_broad_causal_source_artifact_policy --repo-root .`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_artifact_policy.md -TotalCount 80`
  - `rg -n "continued_block_no_source_action_approved|SR1:2020|SR3:2020|blocked_missing_current_source_artifact|restore_approved|repair_approved|exclusion_approved|broader_modeling_approved|config_promotion_approved|research_use_allowed" reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_policy.json reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_policy.md`
  - `git diff --name-only -- data`
  - `git diff --name-only -- configs`
  - `git diff --check -- CODEX_HANDOFF.md scripts/validation/record_broad_causal_source_artifact_policy.py tests/validation/test_record_broad_causal_source_artifact_policy.py`
  - `git status --short`
- Validation:
  - Focused test passed: `python -m pytest tests/validation/test_record_broad_causal_source_artifact_policy.py` -> `6 passed`.
  - Real report-only command passed and wrote JSON/Markdown outputs: `broad_causal_source_artifact_policy status=ACTION_REQUIRED decision=continued_block_no_source_action_approved pair_count=2`.
  - Targeted Markdown read verified `ACTION_REQUIRED`, the continued-block decision, both pairs, false approval flags, and approved action `none`.
  - Targeted `rg` verified both rows, `blocked_missing_current_source_artifact`, continued-block decision, and false restore/repair/exclusion/modeling/config/research flags in JSON/Markdown.
  - `git diff --name-only -- data` returned no paths.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --check` passed with only the existing `CODEX_HANDOFF.md` LF-to-CRLF warning.
- Unresolved blockers:
  - `SR1:2020` and `SR3:2020` remain blocked by absent current referenced source files under `data/dbn_sr_parent_candidate`.
  - The policy decision explicitly approves no source repair, restore, exclusion, build execution, config promotion, broader modeling, production/live use, or model promotion.
  - The broad root has not been built, validated, promoted, or approved for modeling.
  - Current configured canonical causal coverage remains `8/527`.
  - Worktree remains dirty with pre-existing tracked report/handoff state and new report-only tooling; no staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, archive/quarantine execution, restore, source repair, exclusion execution, build execution, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: request or plan the next human policy decision for the two blocked broad source artifacts; no implementation action is approved while the continued-block policy remains active.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, source repair, exclusion execution, build execution, or config promotion.
- Treat current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved config decision after a validated broad root exists.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_artifact_policy.json as the evidence source.
- Focus only on SR1:2020 and SR3:2020, both continued_block_no_source_action_approved with approved action none.
- Decide whether the next step should remain blocked, request a separate human approval for a source repair/restore plan, or request a separate human approval for policy exclusion/deferment.
- Define exact report-only outputs, required evidence fields, validation commands, and stop conditions if a new policy decision is selected.
Stop when:
- A decision-complete plan exists for the next human policy decision, or the two rows remain explicitly blocked with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
```

## Broad Causal Source-Reference Disposition - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\986fc02b-c6c8-4e71-a6af-c66a64328b81\goal-objective.md`
- Scope executed: added and ran one report-only source-reference disposition for the two broad raw/source/hash readiness failures; no data/config/build execution.
- Result:
  - Added `scripts\validation\dispose_broad_causal_source_reference_failures.py`.
  - Added `tests\validation\test_dispose_broad_causal_source_reference_failures.py`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.json`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.md`.
  - Input readiness evidence was `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`.
  - Disposition status: `ACTION_REQUIRED`.
  - Failed pair count: `2`.
  - Failed pairs: `SR1:2020`, `SR3:2020`.
  - Disposition status counts: `blocked_missing_current_source_artifact=2`, `blocked_current_source_hash_mismatch=0`, `current_source_recovered_rerun_readiness_required=0`, `invalid_unexpected_readiness_state=0`.
  - `SR1:2020`: raw rows `8566`; current source file absent at `data/dbn_sr_parent_candidate/SR1/2020/2020-01-01_2021-01-01.dbn.zst`.
  - `SR3:2020`: raw rows `3461`; current source file absent at `data/dbn_sr_parent_candidate/SR3/2020/2020-01-01_2021-01-01.dbn.zst`.
  - Historical references were recorded as `historical_evidence_only=true`; they are not canonical source, repair, restore, build, exclusion, modeling, or config-promotion approval.
  - The report explicitly records `data_mutation_performed=false`, `build_approved=false`, `restore_approved=false`, `repair_approved=false`, `exclusion_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, and `research_use_allowed=false`.
- Files changed in this scope:
  - `scripts\validation\dispose_broad_causal_source_reference_failures.py`
  - `tests\validation\test_dispose_broad_causal_source_reference_failures.py`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\986fc02b-c6c8-4e71-a6af-c66a64328b81\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content CODEX_HANDOFF.md -TotalCount 140`
  - `Get-Content -Raw scripts\validation\validate_broad_causal_raw_source_readiness.py`
  - `Get-Content -Raw tests\validation\test_validate_broad_causal_raw_source_readiness.py`
  - `rg -n 'action_required_source_reference_failure|SR3|SR1|source_file|source_sha256' reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
  - `python -m pytest tests/validation/test_dispose_broad_causal_source_reference_failures.py`
  - `python -m scripts.validation.dispose_broad_causal_source_reference_failures --repo-root .`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.md -TotalCount 45`
  - `rg -n "blocked_missing_current_source_artifact|SR3:2020|SR1:2020|historical_evidence_only|does not approve broader modeling|config promotion|data_mutation_performed" reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_reference_disposition.md reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_reference_disposition.json`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.json | ConvertFrom-Json | Select-Object -ExpandProperty summary | Format-List status,failed_pair_count,data_mutation_performed,build_approved,restore_approved,repair_approved,exclusion_approved,broader_modeling_approved,config_promotion_approved,research_use_allowed,historical_evidence_only`
  - `git diff --name-only -- data`
  - `git diff --name-only -- configs`
  - `Test-Path reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.json`
  - `Test-Path reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_source_reference_disposition.md`
  - `git diff --check -- CODEX_HANDOFF.md scripts/validation/dispose_broad_causal_source_reference_failures.py tests/validation/test_dispose_broad_causal_source_reference_failures.py`
  - `git status --short`
- Validation:
  - Focused test passed: `python -m pytest tests/validation/test_dispose_broad_causal_source_reference_failures.py` -> `6 passed`.
  - Real report-only command passed and wrote JSON/Markdown outputs: `broad_causal_source_reference_disposition status=ACTION_REQUIRED failed_pair_count=2`.
  - Targeted Markdown read verified `ACTION_REQUIRED`, `failed pairs`, `blocked_missing_current_source_artifact=2`, non-approval text, and per-row missing current source artifacts.
  - Targeted `rg` verified both failed pairs, missing-artifact disposition, historical-evidence-only markers, non-approval text, config-promotion text, and false data-mutation flag in JSON/Markdown.
  - Structured JSON assertion verified `status=ACTION_REQUIRED`, `failed_pair_count=2`, all approval flags false, and `historical_evidence_only=true`.
  - `git diff --name-only -- data` returned no paths.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --check` passed with only the existing `CODEX_HANDOFF.md` LF-to-CRLF warning.
- Unresolved blockers:
  - `SR1:2020` and `SR3:2020` remain blocked by absent current referenced source files under `data/dbn_sr_parent_candidate`.
  - The disposition does not approve source restore, source repair, policy exclusion, build execution, config promotion, broader modeling, production/live use, or model promotion.
  - The broad root has not been built, validated, promoted, or approved for modeling.
  - Current configured canonical causal coverage remains `8/527`.
  - Worktree remains dirty with pre-existing tracked report/handoff state and new report-only tooling; no staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, archive/quarantine execution, restore, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: plan the separate report-only policy decision for the two blocked broad source artifacts before any source repair, restore, exclusion, build, or modeling work.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, source repair, exclusion execution, build execution, or config promotion.
- Treat current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved config decision after a validated broad root exists.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_source_reference_disposition.json as the evidence source.
- Focus only on SR1:2020 and SR3:2020, both currently blocked_missing_current_source_artifact.
- Produce a plan for recording the next human policy choice: separately approved source repair/restore plan, policy exclusion/deferment, or continued block.
- Define exact report-only outputs, required evidence fields, validation commands, and stop conditions with no data/** mutation.
Stop when:
- A decision-complete plan exists for the source-artifact policy decision, or the two rows remain explicitly blocked with no build, config promotion, data mutation, source repair/restore/exclusion action, or broader modeling approval.
```

## Broad Causal Raw/Source/Hash Readiness Validator - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\6fb42489-9469-4e73-b1ef-753f8c37f6e9\goal-objective.md`
- Scope executed: added and ran one report-only raw/source/hash readiness validator for `broad_manifest_527_rebuild_v1`; no data/config/build execution.
- Result:
  - Added `scripts\validation\validate_broad_causal_raw_source_readiness.py`.
  - Added `tests\validation\test_validate_broad_causal_raw_source_readiness.py`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.md`.
  - Input scope remained exactly `527` rows from `broad_manifest_527_rebuild_prebuild_plan.json`.
  - Checked action-required rows: `461`.
  - Deferred policy-review rows: `66`.
  - Overall readiness status: `ACTION_REQUIRED`.
  - Readiness status counts: `ready_for_build_input_only=459`, `action_required_source_reference_failure=2`, `deferred_policy_review_not_checked=66`, `action_required_missing_raw=0`, `action_required_unreadable_raw=0`, `action_required_schema_or_metadata_failure=0`, `excluded_from_phase2_not_checked=0`.
  - Remaining source-reference failures:
    - `SR3:2020`: raw rows `3461`; missing source file `data/dbn_sr_parent_candidate/SR3/2020/2020-01-01_2021-01-01.dbn.zst`.
    - `SR1:2020`: raw rows `8566`; missing source file `data/dbn_sr_parent_candidate/SR1/2020/2020-01-01_2021-01-01.dbn.zst`.
  - The report explicitly records `data_mutation_performed=false`, `build_approved=false`, `broader_modeling_approved=false`, `config_promotion_approved=false`, and `research_use_allowed=false`.
- Files changed in this scope:
  - `scripts\validation\validate_broad_causal_raw_source_readiness.py`
  - `tests\validation\test_validate_broad_causal_raw_source_readiness.py`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\6fb42489-9469-4e73-b1ef-753f8c37f6e9\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Get-Content -Raw scripts\validation\plan_broad_causal_rebuild.py`
  - `Get-Content -Raw tests\validation\test_plan_broad_causal_rebuild.py`
  - `rg -n 'stage|future_root|expected_rows|status_counts|broader_modeling_approved|config_promotion_approved|legacy_restore_approved|research_use_allowed' reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_prebuild_plan.json`
  - `Test-Path scripts\validation\validate_broad_causal_raw_source_readiness.py`
  - `Test-Path tests\validation\test_validate_broad_causal_raw_source_readiness.py`
  - `python -m pytest tests/validation/test_validate_broad_causal_raw_source_readiness.py`
  - `python -m scripts.validation.validate_broad_causal_raw_source_readiness --repo-root .`
  - `Get-Content reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.md -TotalCount 80`
  - `rg -n '\"status\"|\"expected_rows\"|\"checked_action_required_rows\"|\"deferred_policy_review_rows\"|\"readiness_status_counts\"|ready_for_build_input_only|action_required_source_reference_failure|action_required_schema_or_metadata_failure|action_required_missing_raw' reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json`
  - `rg -n -C 8 'action_required_source_reference_failure|source hash mismatch|source file missing|source_file/source_sha256 references absent' reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.json reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_raw_source_readiness.md`
  - `rg -n "broad_causal_raw_source_readiness|ready_for_build_input_only|ACTION_REQUIRED|READY_FOR_SEPARATE_BUILD_APPROVAL|does not approve broader modeling|config promotion" reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628`
  - `git diff --name-only -- data`
  - `git diff --name-only -- configs`
  - `git diff --check -- CODEX_HANDOFF.md scripts/validation/validate_broad_causal_raw_source_readiness.py tests/validation/test_validate_broad_causal_raw_source_readiness.py`
  - `git status --short`
  - Structured PowerShell JSON assertion of readiness summary counts and approval flags.
- Validation:
  - Focused test passed: `python -m pytest tests/validation/test_validate_broad_causal_raw_source_readiness.py` -> `5 passed`.
  - Real report-only scan passed as a command and wrote JSON/Markdown outputs: `broad_causal_raw_source_readiness status=ACTION_REQUIRED expected_rows=527 checked_action_required_rows=461`.
  - The report preserved fail-closed status because `2` source-reference failures remain.
  - Structured JSON assertion verified `status=ACTION_REQUIRED`, `expected_rows=527`, `checked_action_required_rows=461`, `ready_for_build_input_only=459`, `source_reference_failures=2`, `deferred_policy_review_not_checked=66`, and all approval flags false.
  - Targeted `rg` found the readiness stage, fail-closed status, input-only ready status, non-approval text, and config-promotion text in the review artifacts.
  - `git diff --name-only -- data` returned no paths.
  - `git diff --name-only -- configs` returned no paths.
  - `git diff --check` passed with only the existing `CODEX_HANDOFF.md` LF-to-CRLF warning.
  - Initial targeted `rg` during exploration used an invalid escaped regex and failed before project code ran; it was replaced by a simpler literal search.
- Unresolved blockers:
  - `SR3:2020` and `SR1:2020` remain blocked by missing raw-provenance source files under `data/dbn_sr_parent_candidate`.
  - The broad root has not been built, validated, promoted, or approved for modeling.
  - Current configured canonical causal coverage remains `8/527`.
  - Worktree remains dirty with pre-existing tracked report/handoff state and new report-only tooling; no staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, archive/quarantine execution, restore, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: plan a report-only source-reference disposition for the two remaining broad raw readiness failures before any build.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, or config promotion.
- Treat current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved config decision after a validated broad root exists.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_raw_source_readiness.json as the evidence source.
- Focus only on SR3:2020 and SR1:2020 source-reference failures for missing data/dbn_sr_parent_candidate source files.
- Decide whether the next step should be report-only provenance disposition, explicit policy exclusion/deferment, or a separately approved source repair plan.
- Define exact report outputs, validation commands, and stop conditions with no data/** mutation.
Stop when:
- A decision-complete plan exists for disposing the two source-reference failures, with no build, config promotion, data mutation, or broader modeling approval.
```

## Broad Causal Rebuild Prebuild Plan - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\df7b44fb-0935-4916-b5fe-b8f1f5676d21\goal-objective.md`
- Scope executed: added report-only tooling to design and validate the future broad causal rebuild plan for `broad_manifest_527_rebuild_v1`; no data/config/build execution.
- Result:
  - Added `scripts\validation\plan_broad_causal_rebuild.py`.
  - Added `tests\validation\test_plan_broad_causal_rebuild.py`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_prebuild_plan.json`.
  - Generated `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_prebuild_plan.md`.
  - The generated plan expands `configs\data_manifest.yaml` to exactly `527` planned market/year rows.
  - Future output pattern remains `data/causal_base_candidates/broad_manifest_527_rebuild_v1/{market}/{year}.parquet`.
  - Status counts are fail-closed by design: `action_required=461`, `deferred_policy_review=66`, `ready_for_build=0`, `excluded_from_phase2=0`.
  - `2025` holdout and `2026` forward rows are marked non-research until separately approved.
  - The prebuild plan records required root manifest fields, required per-row manifest fields, fail-closed statuses, validation gates, and explicit non-approval for broader modeling, cleanup, metrics, predictions, config promotion, legacy restore, labels, features, WFA, production/live use, and model promotion.
- Files changed in this scope:
  - `scripts\validation\plan_broad_causal_rebuild.py`
  - `tests\validation\test_plan_broad_causal_rebuild.py`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_prebuild_plan.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_manifest_527_rebuild_prebuild_plan.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\df7b44fb-0935-4916-b5fe-b8f1f5676d21\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Get-Content -Raw configs\data_manifest.yaml`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_causal_root_policy.md`
  - `Test-Path scripts\validation\plan_broad_causal_rebuild.py`
  - `Test-Path tests\validation\test_plan_broad_causal_rebuild.py`
  - `python -m pytest tests/validation/test_plan_broad_causal_rebuild.py`
  - `python -m scripts.validation.plan_broad_causal_rebuild --repo-root .`
  - `rg -n "broad_manifest_527_rebuild_v1|expected_rows.*527|does not approve broader modeling|config promotion" reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628`
  - `git diff --name-only -- data`
  - `git diff --name-only -- configs`
  - `git status --short`
- Validation:
  - Initial focused pytest failed on a local expected-field naming mismatch (`config_hash` versus `config_sha256`); tooling was corrected to match existing causal manifest convention.
  - Final `python -m pytest tests/validation/test_plan_broad_causal_rebuild.py` passed: `4 passed`.
  - `python -m scripts.validation.plan_broad_causal_rebuild --repo-root .` passed and printed `expected_rows=527`.
  - Targeted `rg` found required broad-root, row-count, non-approval, and config-promotion text in the policy/prebuild artifacts.
  - `git diff --name-only -- data` returned no paths.
  - `git diff --name-only -- configs` returned no paths.
- Unresolved blockers:
  - This is a report-only prebuild plan; no broad causal parquet was built.
  - The broad root is still not validated, promoted, or approved for modeling.
  - Current configured canonical causal coverage remains `8/527`.
  - Worktree remains dirty with pre-existing tracked report/handoff state and new report-only tooling; no staging or commit was performed.
- Safety:
  - No `data/**` mutation was performed.
  - No `configs/**` mutation was performed.
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, archive/quarantine execution, restore, or config promotion was performed.
  - No tier2/tier3/all-market rows were marked modeling-approved.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: plan a report-only raw/source/hash readiness validator for broad_manifest_527_rebuild_v1 before any build.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, or config promotion.
- Treat the current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved config decision after a validated broad root exists.
- Do not mark tier2/tier3/all-market rows as modeling-approved.
Task:
- Use reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_manifest_527_rebuild_prebuild_plan.json as the input scope.
- Design one small report-only validator that can check planned raw/source/hash/readiness prerequisites for the 461 action_required research rows without writing data/**.
- Define exact outputs, fail-closed row statuses, validation commands, and stop conditions.
Stop when:
- A decision-complete implementation plan exists for the raw/source/hash readiness validator, with no data/** mutation and no broader modeling approval.
```

## Broad Causal Root Policy Recorded - 2026-06-29

- Updated at UTC date: 2026-06-29.
- Scope executed: recorded the human policy decision for the canonical broad causal root; report-only/documentation-only, with no data/config/build execution.
- Decision:
  - Policy decision: `rebuild_new_broad_root`.
  - Future candidate root: `data/causal_base_candidates/broad_manifest_527_rebuild_v1`.
  - Future parquet pattern: `data/causal_base_candidates/broad_manifest_527_rebuild_v1/{market}/{year}.parquet`.
  - Scope source: `configs/data_manifest.yaml`.
  - Scope inventory: `527` expected market/year rows, default start year `2010`, end year `2026`, and start-year overrides for `KE`, `RTY`, `SR1`, `SR3`, `TN`, `ZL`, and `ZM`.
  - `2025` holdout rows and `2026` forward rows remain non-research until separately approved.
- Current configured canonical state:
  - `configs/data_manifest.yaml` was not changed.
  - Current configured canonical causal pattern remains `data/causal_base_candidates/tier1_rebuild_v1/{market}/{year}.parquet`.
  - Current configured canonical causal coverage remains `8/527` until the new broad root is built, validated, and separately approved for config promotion.
- Legacy root disposition:
  - Legacy `data/causally_gated_normalized*` roots are evidence only.
  - Legacy roots are not canonical restore targets under this policy.
  - Legacy roots must not be used as canonical broad causal input without a separate validation and policy decision.
- Future rebuild requirements recorded:
  - Root-level manifest with expected row count, produced/deferred/excluded counts, build command, UTC timestamp, config path/hash, code revision, and warnings.
  - Per-row manifest records with market, year, input raw path/hash/row count, output path/hash/row count, timestamp bounds, schema/version, and status.
  - Rows with unresolved source/raw/policy evidence must fail closed as deferred, excluded, or action-required.
- Unresolved blockers:
  - The broad root `data/causal_base_candidates/broad_manifest_527_rebuild_v1` has not been built, validated, or promoted.
  - Current configured canonical causal coverage remains `8/527`; tier2/tier3/all-market modeling remains blocked.
  - Worktree remains dirty with pre-existing `AGENTS.md`, required `CODEX_HANDOFF.md`, and refreshed tracked report outputs; this report-only policy artifact was added under `reports/`.
- Files changed:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_causal_root_policy.md`
  - `CODEX_HANDOFF.md`
- Commands run in this scope:
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Test-Path reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_causal_root_policy.md`
  - `git diff --check -- CODEX_HANDOFF.md reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_causal_root_policy.md`
  - `rg -n "broad_manifest_527_rebuild_v1|527|rebuild_new_broad_root|separate.*config|does not approve broader modeling" CODEX_HANDOFF.md reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_causal_root_policy.md`
  - `git diff --name-only -- data`
  - `git diff --name-only -- configs`
  - `git status --short`
- Validation:
  - `git diff --check -- CODEX_HANDOFF.md reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broad_causal_root_policy.md` passed; output contained the existing `CODEX_HANDOFF.md` LF-to-CRLF warning only.
  - Targeted `rg` found `broad_manifest_527_rebuild_v1`, `527`, `rebuild_new_broad_root`, separate config approval language, and `does not approve broader modeling` in the policy/handoff artifacts.
  - `git diff --name-only -- data` returned no paths.
  - `git diff --name-only -- configs` returned no paths.
  - `git status --short` reported the pre-existing modified `AGENTS.md`, modified `CODEX_HANDOFF.md`, and modified tracked master data health report outputs.
- Safety:
  - No `data/**` mutation was performed.
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commit, archive/quarantine execution, restore, or config promotion was performed.
  - This policy does not approve broader modeling, cleanup, production/live use, model promotion, labels, features, WFA, predictions, metrics, or config promotion.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: plan the prebuild validation/build design for broad_manifest_527_rebuild_v1 before any broad causal build or config promotion.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, commits, restore, or config promotion.
- Treat the current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved config decision after a validated broad root exists.
- Do not mark tier2/tier3/all-market rows as modeling-approved from old data/causally_gated_normalized evidence.
Task:
- Design the prebuild validation and build plan for data/causal_base_candidates/broad_manifest_527_rebuild_v1/{market}/{year}.parquet using the 527-row configs/data_manifest.yaml scope.
- Specify the root-level manifest schema, per-row manifest schema, hash checks, fail-closed statuses, validation commands, and stop conditions.
- Decide whether the next implementation should be report-only prebuild validation tooling or an explicitly approved build runner.
Stop when:
- A decision-complete implementation plan exists for prebuild validation/build design, with no data/** mutation and no broader modeling approval.
```

## Broad Causal Source Matrix Reconciliation - 2026-06-28

- Updated at local date: 2026-06-28.
- Scope executed: refreshed the report-only master data health matrix from current configured canonical filesystem evidence and reconciled stale broad causal counts.
- Result:
  - Old matrix count preserved as stale evidence: `461/527`.
  - Older handoff correction preserved as stale evidence: `107/527`.
  - Current configured canonical causal count: `8/527`.
  - Current canonical causal pattern: `data/causal_base_candidates/tier1_rebuild_v1/{market}/{year}.parquet`.
  - Current present rows: `ES:2023`, `ES:2024`, `CL:2023`, `CL:2024`, `ZN:2023`, `ZN:2024`, `6E:2023`, `6E:2024`.
- Report artifacts updated or added:
  - `reports\data_manifest\master_data_health_matrix.json`
  - `reports\data_manifest\master_data_health_summary.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broad_causal_source_matrix_reconciliation.md`
- Validation:
  - `python -m pytest tests/validation/test_refresh_master_data_health_matrix.py` -> `3 passed`.
  - `python -m scripts.validation.refresh_master_data_health_matrix --repo-root .` -> `master_data_health_refresh expected_rows=527 causal_parquet_present=8 approved_pass=11 fail_closed=28 unresolved=0`.
  - Post-refresh structural audit verified `summary.expected_rows == 527`, `summary.schema_presence_counts.causal_parquet_present == 8`, `summary.current_canonical_causal.present_count == 8`, and exact present rows.
  - `git diff --name-only -- data` returned no paths.
- Safety:
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, archive, move, delete, restore, quarantine execution, `data/**` mutation, staging, or commit was performed.
  - This reconciliation does not approve tier2/tier3/all-market modeling, cleanup, production/live use, or model promotion.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: make a human policy decision on the canonical broad causal root before any tier2/tier3 modeling work.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, or commits.
- Treat the current configured canonical causal coverage as 8/527 unless configs/data_manifest.yaml is explicitly changed by a separate approved policy decision.
- Do not mark tier2/tier3/all-market rows as modeling-approved from old data/causally_gated_normalized evidence.
Task:
- Decide whether broad causal should be rebuilt into data/causal_base_candidates/<approved_broad_root>, restored from an existing historical root after validation, or remain blocked.
- If a broad root is selected, define the exact market/year scope, manifest requirements, hash checks, and validation gates before any build or restore action.
Stop when:
- A canonical broad causal-root policy is recorded, or broader lineage remains explicitly blocked with no modeling approval.
```

## Broader Tier2/Tier3 Source-Of-Truth Lineage Review - 2026-06-28

- Updated at local time: 2026-06-28T16:59:00-07:00.
- Scope executed: report-only broader lineage review for tier2/tier3 market-year rows.
- Objective file read first:
  - `C:\Users\donny\.codex\attachments\4c9b5ca9-5604-4e3d-a9a5-1e34427cbaaf\goal-objective.md`
- Generated report-only artifacts:
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broader_source_of_truth_lineage.md`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broader_source_of_truth_lineage.json`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broader_market_year_lineage.csv`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broader_phase_status_summary.csv`
  - `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628\broader_conflicts_and_gaps.md`
- Current classification result:
  - `tier_2_research`: 105 profile rows.
  - `tier_3_research`: 495 profile rows.
  - Total profile rows: 600.
  - Configured tier3 rows absent from current master data health matrix: 34; these are explicitly marked `no_current_matrix_row`.
  - No tier2/tier3 row is approved as broader-profile modeling input.
  - Overlapping tier1 rows are marked `yes_for_tier1_only; no_for_this_broader_profile_modeling`.
- Preserved conflicts:
  - The verified active modeling chain remains tier1 only: `data/dbn` -> `data/raw/{market}/{year}.parquet` -> `data/causal_base_candidates/tier1_rebuild_v1` -> `data/labeled/tier1_rebuild_v1` -> `data/feature_matrices/baseline_tier1_rebuild_v1` -> `reports/data_audit/wfa_research/tier1_rebuild_v1`.
  - `configs\data_manifest.yaml` points causal parquet at `data/causal_base_candidates/tier1_rebuild_v1/{market}/{year}.parquet`, while the master matrix still reports broad causal parquet presence. This report records that as conflict evidence, not approval.
  - `reports\data_manifest\master_data_health_matrix.json` reports `causal_parquet_present=461/527`, while this handoff previously recorded a later correction to `107/527`; this remains a blocker to broader modeling use until the matrix is refreshed or the broad causal policy is settled.
  - Cleanup remains blocked: `cleanup_eligible_now=false`, `dry_run_cleanup_safe_next=false`, and `actual_cleanup_safe_now=false`.
- Validation performed:
  - JSON parsed.
  - Both CSV files parsed.
  - Required row fields are present.
  - No duplicate profile/market/year rows.
  - Every configured tier2/tier3 profile row is represented.
  - Every current matrix row applicable to tier2/tier3 profiles is represented.
  - Report text explicitly states no broader modeling, cleanup, production/live trading, or model-promotion approval.
  - `git diff --name-only -- data` returned no paths.
- Commands run in this scope:
  - `Get-Content -Raw C:\Users\donny\.codex\attachments\4c9b5ca9-5604-4e3d-a9a5-1e34427cbaaf\goal-objective.md`
  - `Get-Location`
  - `git status --short`
  - `Get-Content -Raw CODEX_HANDOFF.md`
  - `Get-Content -Raw configs\alpha_tiered.yaml`
  - `Get-Content -Raw configs\data_manifest.yaml`
  - `Get-Content -Raw reports\data_manifest\master_data_health_matrix.json`
  - `Get-Content -Raw reports\data_audit\final\final_cleanup_blockers.json`
  - `Get-Content -Raw reports\data_audit\source_of_truth_lineage\source_of_truth_lineage.json`
  - `Get-ChildItem -Force data\labeled`
  - `Get-ChildItem -Force data\feature_matrices`
  - `Get-ChildItem -Force reports\data_audit\wfa_research`
  - `Get-ChildItem -Force data\causal_base_candidates`
  - `Test-Path reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628`
  - `git diff --name-only -- data`
  - Local Python report generator for `reports\data_audit\source_of_truth_lineage\broader_lineage_review_20260628`
  - Local Python structural validator for the generated JSON/CSV/Markdown artifacts
- Safety:
  - No provider/network download, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, archive, move, delete, restore, quarantine execution, `data/**` mutation, staging, or commit was performed.
  - `AGENTS.md` remains a pre-existing uncommitted local change and was not touched.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: refresh or reconcile the broad causal/source matrix before any tier2/tier3 modeling decision.
Rules:
- Do not delete, move, rename, archive, quarantine, restore, or mutate data/**.
- Do not run provider/network downloads, WFA/modeling, prediction generation, metrics execution, cleanup, dry-run cleanup, staging, or commits.
- Treat reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/ as report evidence only.
- Do not mark tier2/tier3/all-market rows as modeling-approved unless current causal, label, feature, WFA, prediction, and metrics evidence all exist for the selected scope.
Task:
- Read reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/broader_conflicts_and_gaps.md.
- Decide whether to refresh the master data health matrix from current canonical filesystem evidence or first make a human policy decision on the canonical broad causal root.
- If refreshing, generate report-only matrix outputs and explicitly reconcile the 461/527 versus 107/527 causal-count conflict.
Stop when:
- The broad causal/source count conflict is resolved into a current report-only artifact, or a human decision is recorded that broader lineage remains blocked.
```

## Local Documentation Preservation Finalized - 2026-06-28

- Updated at local time: 2026-06-28T16:16:17-07:00.
- Scope executed: chose to preserve the remaining local documentation/guidance changes rather than revert or commit them.
- Final disposition:
  - `AGENTS.md`: intentionally left local and uncommitted. It remains a separate repo-guidance change candidate and must not be staged, committed, or reverted unless the user explicitly approves touching `AGENTS.md`.
  - `CODEX_HANDOFF.md`: intentionally left local and uncommitted as cross-run handoff documentation. It should not be staged, committed, or reverted unless the user explicitly approves a documentation-only action.
- Rationale:
  - Reverting either file would mutate tracked source/docs state and was not explicitly approved.
  - Committing either file would require explicit approval of the exact file scope.
  - Leaving both files local satisfies the selected stop condition without touching `data/**`, report evidence roots, quarantine, staging, commits, or production/model claims.
- Verified evidence before this final disposition:
  - `git status --short --branch` -> `## main...origin/main` with `M AGENTS.md` and `M CODEX_HANDOFF.md`.
  - `git diff --name-only -- data` returned no paths.
  - `Test-Path data\_quarantine\actual_cleanup_v1_20260628_130232` returned `True`.
  - No staged files were present.
- Safety:
  - No `data/**` mutation, cleanup, archive, quarantine deletion, report overwrite, staging, commit, revert, production/live readiness claim, model promotion claim, cleanup/archive approval, or historical model-result approval occurred.

### Exact Next Recommended Step

```text
None.
```

## Worktree Documentation Disposition - 2026-06-28

- Updated at local time: 2026-06-28T16:13:22-07:00.
- Scope executed: decided the remaining documentation/worktree disposition after side-aware commit `209f48f` was pushed.
- Current verified state at start of this scope:
  - `git status --short --branch` -> `## main...origin/main` with `M AGENTS.md` and `M CODEX_HANDOFF.md`.
  - `git diff --name-only -- data` returned no paths.
  - `Test-Path data\_quarantine\actual_cleanup_v1_20260628_130232` returned `True`.
  - No staged files were present.
- `AGENTS.md` disposition:
  - Final disposition for now: leave local and uncommitted; do not stage, commit, or revert without explicit user approval.
  - Classification: separate repo-guidance change candidate, not side-aware implementation work and not required for the pushed `209f48f` side-aware contract.
  - Diff evidence reviewed: the only shown change removes the required `Metrics` final section and removes `Metrics` from the allowed final top-level sections.
  - Recommended future choice: if the user wants this repo-local final-output contract changed, handle it as a separate AGENTS-only approval/commit path; otherwise revert only after explicit user approval.
- `CODEX_HANDOFF.md` disposition:
  - Final disposition for now: keep as an uncommitted local cross-run handoff note.
  - Reason: the file now documents post-push status, the `AGENTS.md` disposition, and the validation gate needed before relying on side-aware behavior; no user approval was given to stage or commit this documentation note.
  - Recommended future choice: if the user wants a durable repo history entry for this handoff documentation, prepare a separate documentation-only commit that excludes `AGENTS.md`, `data/**`, generated artifacts, report roots, and model/data outputs.
- Required validation gate remains unchanged:
  - Before any pipeline, model result, archive decision, cleanup decision, closeout claim, promotion claim, or live-readiness claim relies on side-aware behavior, run the fresh intended-scope validation documented in `Post-Side-Aware Push and Validation Gate - 2026-06-28`.
- Safety:
  - No `data/**` files, quarantine folders, smoke report roots, staging, commits, or `AGENTS.md` edits were performed in this scope.
  - No production/live readiness, model promotion, cleanup/archive approval, or historical model-result approval was claimed.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: choose whether to clean or preserve the remaining local documentation changes.
Rules:
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Preserve data/_quarantine/actual_cleanup_v1_20260628_130232 for rollback.
- Do not delete or overwrite reports/side_aware_trend_smoke_v1, reports/side_aware_trend_smoke_v2_tier1_core, or reports/side_aware_trend_smoke_v3_tier1_core.
- Do not claim production/live readiness, model promotion, cleanup/archive approval, or approval of historical model results.
Task:
- Decide whether AGENTS.md should remain local, be reverted, or be committed as a separate AGENTS-only repo-guidance change.
- Decide whether CODEX_HANDOFF.md should remain local, be reverted to the committed version, or be committed as a separate documentation-only handoff note.
- If choosing revert or commit, explicitly approve the exact files to touch before any staging, commit, or revert.
Stop when:
- The chosen disposition is executed or the files are intentionally left local, with no data/** mutation.
```

## Post-Side-Aware Push and Validation Gate - 2026-06-28

- Updated at local time: 2026-06-28T16:10:51-07:00.
- Scope executed: implemented the safe post-side-aware-commit plan from `C:\Users\donny\Desktop\You_are_here_updated_current_FINAL_20260628_post_side_aware_commit.txt`.
- Push result:
  - Preconditions passed before push:
    - `git status --short --branch` -> `## main...origin/main [ahead 1]` with only `M AGENTS.md`.
    - `git log -1 --oneline` -> `209f48f Add side-aware trend risk contract`.
    - `git diff --name-only -- data` returned no paths.
    - `Test-Path data\_quarantine\actual_cleanup_v1_20260628_130232` returned `True`.
  - `git push origin main` succeeded and advanced `origin/main` from `798f7fd` to `209f48f`.
  - Post-push `git status --short --branch` -> `## main...origin/main` with only `M AGENTS.md` before this handoff update.
  - No staged files remained after the push.
- `AGENTS.md` disposition:
  - Classified as a separate repo-guidance change candidate, not side-aware implementation work.
  - Diff evidence: it removes the required `Metrics` final section and removes `Metrics` from the allowed final top-level sections.
  - It was not staged, committed, reverted, or otherwise modified in this scope.
- Required validation gate before any pipeline, model result, archive decision, cleanup decision, closeout claim, promotion claim, or live-readiness claim relies on side-aware behavior:
  1. Re-run static/source checks on the exact worktree intended for reliance: `git diff --check -- configs scripts tests CODEX_HANDOFF.md` and `python -m scripts.validation.model_registry --config configs\models.yaml`.
  2. Re-run focused tests covering side-aware labels, Phase 4 target registry/leakage guard, Phase 7 target-specific prediction routing, Phase 8 policy/audit behavior, model registry, and live-shadow bundle/gating.
  3. Run the fresh intended pipeline scope from current inputs, not historical prediction artifacts, and verify manifests, row counts, prediction schemas, warnings/failures, cost assumptions, purge/embargo, and promotion/closeout gates.
  4. Preserve `reports\side_aware_trend_smoke_v1`, `reports\side_aware_trend_smoke_v2_tier1_core`, and `reports\side_aware_trend_smoke_v3_tier1_core`; do not reuse them as approval for broader claims.
  5. Verify `git diff --name-only -- data` remains empty unless a later user-approved task explicitly allows data mutation.
- Safety:
  - No `data/**` files were mutated.
  - `data\_quarantine\actual_cleanup_v1_20260628_130232` remains the preserved rollback quarantine.
  - Smoke report roots were not deleted or overwritten.
  - No production/live readiness, model promotion, cleanup/archive approval, or historical model-result approval was claimed.
- Files changed in this scope:
  - `CODEX_HANDOFF.md` only, to document the push, `AGENTS.md` disposition, and validation gate.

### Exact Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: decide the remaining documentation/worktree disposition after pushing side-aware commit 209f48f.
Rules:
- Do not delete, move, rename, archive, quarantine, or mutate data/**.
- Preserve data/_quarantine/actual_cleanup_v1_20260628_130232 for rollback.
- Do not delete or overwrite reports/side_aware_trend_smoke_v1, reports/side_aware_trend_smoke_v2_tier1_core, or reports/side_aware_trend_smoke_v3_tier1_core.
- Do not stage, commit, or revert AGENTS.md unless explicitly approved after inspection.
- Do not claim production/live readiness, model promotion, cleanup/archive approval, or approval of historical model results.
Task:
- Verify git status --short --branch.
- Review the documented AGENTS.md disposition in CODEX_HANDOFF.md and the current AGENTS.md diff only.
- Decide whether AGENTS.md should remain local, be reverted by explicit approval, or be prepared as a separate AGENTS-only commit.
- Decide whether CODEX_HANDOFF.md should remain as an uncommitted local handoff note or be prepared for a separate documentation-only commit.
Stop when:
- AGENTS.md and CODEX_HANDOFF.md each have an explicit disposition, with no data/** mutation and no staging/commit/revert unless explicitly approved.
```

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
