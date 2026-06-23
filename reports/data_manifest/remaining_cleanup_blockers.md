# Remaining Cleanup Blockers

Generated at UTC: 2026-06-22T14:22:47Z

## Summary

- Status manifest-policy rows are resolved by commit `c2f9998 Apply status manifest policy`.
- User decision recorded: keep both for all 12 duplicate rows; no duplicate merge/quarantine/move/delete is approved.
- Ten bounded Phase 1B raw repairs have been run and validated: `data/raw/KE/2025.parquet`, `data/raw/KE/2026.parquet`, `data/raw/SR1/2025.parquet`, `data/raw/SR1/2026.parquet`, `data/raw/TN/2025.parquet`, `data/raw/TN/2026.parquet`, `data/raw/ZL/2025.parquet`, `data/raw/ZL/2026.parquet`, `data/raw/ZM/2025.parquet`, and `data/raw/ZM/2026.parquet`.
- Remaining approved Phase 1B raw parquet repairs: 0.
- User decision recorded: the 66 Phase 2 causal repair rows are approved for later bounded one-market/year repair runs; stop before Phase 2 execution.
- Cleanup remains disabled in `configs/data_manifest.yaml`.
- No cleanup, merge, quarantine, data move, data delete, rebuild, phase 2 build, phase 3+ command, or unapproved DBN source modification was run. Bounded user-approved KE 2014 status-only API and exact-contract lookback requests were run as evidence.

## Final Decision Packet

- Packet: `reports/data_manifest/final_repair_duplicate_decision_packet.md`.
- Matrix: `reports/data_manifest/final_repair_duplicate_decision_matrix.csv`.
- Current manifest audit: `manifest_check issues=169 failures=0`.
- Decision/evidence counts: 10 raw repairs completed and validated; `APPROVE_BOUNDED_REPAIR_LATER` causal rows 66; `KEEP_BOTH_DO_NOT_TOUCH` duplicate rows 12; `USER_DECISION_REQUIRED` rows 0; `UNKNOWN_BLOCKING_CLEANUP` 0.
- Explicitly deferred rows: 0.
- Duplicate rows still requiring user decision: 0.
- Phase 2 causal rows still requiring later user decision: 0.

## Repair Decisions

| Group | Rows | Final class | Scope | Required before cleanup |
|---|---:|---|---|---|
| Raw parquet repair completed | 10 | validated evidence | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026 | no raw repair rows remain |
| Raw parquet repair remaining | 0 | complete | none | no |
| Causal parquet repair with raw present | 66 | `APPROVE_BOUNDED_REPAIR_LATER` | KE 2013-2026; SR1 2018-2026; TN 2016-2026; ZL 2011-2026; ZM 2011-2026 | yes; approved for later bounded one-market/year repair only |
| Causal parquet repair dependent on raw repair | 0 | complete | none | no |

## Duplicate Decisions

| Final class | Rows | Scope | Policy |
|---|---:|---|---|
| `KEEP_BOTH_DO_NOT_TOUCH` | 12 | all duplicate DBN rows | preserve both files in place; no mutation |

## Cleanup Gate

- Cleanup remains disabled.
- Cleanup remains blocked until approved Phase 2 causal rows are executed or explicitly deferred, blockers are zero, and cleanup is separately approved.
- `UNKNOWN_BLOCKING_CLEANUP`: 0.

## Latest Raw Repair Evidence

- Evidence reports: `reports/phase_restart/ke_2025_phase1b_raw_repair.md`, `reports/phase_restart/ke_2026_phase1b_raw_repair.md`, `reports/phase_restart/sr1_2025_phase1b_raw_repair.md`, `reports/phase_restart/sr1_2026_phase1b_raw_repair.md`, `reports/phase_restart/tn_2025_phase1b_raw_repair.md`, `reports/phase_restart/tn_2026_phase1b_raw_repair.md`, `reports/phase_restart/zl_2025_phase1b_raw_repair.md`, `reports/phase_restart/zl_2026_phase1b_raw_repair.md`, `reports/phase_restart/zm_2025_phase1b_raw_repair.md`, and `reports/phase_restart/zm_2026_phase1b_raw_repair.md`.
- Progress report: `reports/phase_restart/phase1b_raw_repair_progress.md`.
- Phase 1C alignment: PASS for KE 2025, KE 2026, SR1 2025, SR1 2026, TN 2025, TN 2026, ZL 2025, ZL 2026, ZM 2025, and ZM 2026.
- Manifest raw missing pairs after latest repair: 0.

## Latest Phase 2 Causal Decision

- All 66 Phase 2 causal rows are now `APPROVE_BOUNDED_REPAIR_LATER`.
- No Phase 2 command was run in this decision step.
- Smallest later execution unit: one market/year readiness-only check, then one separately approved bounded Phase 2 build for that same market/year.
- KE-specific decision update: KE 2013-2015 are excluded from canonical Phase 2 unless explicitly policy-excepted; KE 2016-2026 are policy-reviewable, not automatically clean.

## Latest Status-Source Recovery Execution

- Evidence packet: `reports/phase_restart/batch_phase2_status_source_recovery_execution.md`.
- KE 2014 local canonicalization completed by copying the equivalent status DBN from `data/dbn/status_parent/status/KE/2014/2014-01-01_2015-01-01.dbn.zst` to `data/dbn/status/KE/2014/2014-01-01_2015-01-01.dbn.zst`; source SHA256 remained `6b972a329f87a6870d5465a7a432de1c1c2b1b31be237f4691cd52b702abccef`.
- KE 2014 bounded Phase 1B raw/status re-enrichment completed and Phase 1C alignment passed.
- KE 2014 Phase 2 readiness-only still failed: blocker `roll maturity sequence not monotonic: backsteps=4`; synthetic threshold still breached at `61.854098%`; status DBN loaded but matched 0 of 101536 raw rows.
- The other 7 status-source rows were attempted with `--zero-cost-only --resume` and remain unrecovered: KE 2013, ZL 2012, ZL 2013, ZM 2011, ZM 2012, ZM 2013, and ZM 2014.
- Current manifest audit after recovery: `manifest_check issues=168 failures=0`.
- No Phase 2 build, cleanup, phase 3+, move, merge, quarantine, delete, full rebuild, or data artifact staging occurred.

## KE 2014 Final Recovery Decision

- Diagnostic: `reports/phase_restart/ke_2014_status_mismatch_diagnostic.md`.
- Final decision: `EXCLUDED_STATUS_SOURCE_NOT_JOINABLE`.
- Reason: the canonical status DBN decodes and partially overlaps raw instrument IDs, but every status event for overlapping raw instruments occurs after the corresponding observed raw rows ended; `KEH5` has no status event. Therefore the existing backward as-of status join cannot enrich observed KE 2014 rows without changing status semantics or inventing prior state.
- KE 2014 remains excluded from Phase 2 build unless a future separate explicit policy exception accepts missing status enrichment, roll maturity backsteps, and synthetic coverage, or a new trusted status source with prior joinable events is supplied.
- Latest KE 2014 readiness-only: FAIL, blockers=1, failures=0; top blocker `roll maturity sequence not monotonic: backsteps=4`; synthetic threshold `rows_pct=61.854098 max_gap_minutes=119`; status matched rows 0 of 101536.

## KE 2014 Status API Redownload

- Redownload evidence: `reports/phase_restart/ke_2014_status_api_redownload.md`.
- User-approved status-only API redownload completed for KE 2014 with Databento job `GLBX-20260622-Y6UBTB3UE7`.
- Zero-cost gate: PASS; cost `0.0`; record count 476.
- Canonical status file changed from SHA256 `6b972a329f87a6870d5465a7a432de1c1c2b1b31be237f4691cd52b702abccef` to `1efee9634d7817f28c693661de86d4bfed928f54ebe00ca08150fa1b6368f388`.
- Joinability still failed: raw/status instrument overlap 5 of 6, possible backward as-of raw matches 0, `KEH5` still has no status event.
- No Phase 1B re-enrichment, Phase 2 build, cleanup, phase 3+, or data artifact staging occurred.

## KE 2014 Exact-Contract Status Lookback

- Exact-contract evidence: `reports/phase_restart/ke_2014_exact_contract_status_lookback.md`.
- Scratch status-only Databento request completed for `KEH4,KEK4,KEN4,KEU4,KEZ4,KEH5` with Databento job `GLBX-20260622-Y3XLQQ4JBC`.
- Zero-cost gate: PASS; cost `0.0`; record count 17.
- Scratch output only: `reports/status_source_recovery/ke_2014_exact_contract_lookback/dbn/KE_EXACT/2014/2013-01-01_2015-01-01.dbn.zst`.
- Joinability still failed: raw/status instrument overlap 5 of 6, possible backward as-of raw matches 0, `KEH5` still has no status event.
- No canonical status overwrite, Phase 1B re-enrichment, Phase 2 build, cleanup, phase 3+, or data artifact staging occurred.
- KE 2014 remains excluded from Phase 2 build unless a separate explicit policy exception accepts missing status enrichment, roll maturity backsteps, and synthetic coverage.

## KE 2014 Alternate-Source Review

- Alternate-source review: `reports/phase_restart/ke_2014_alternate_source_review.md`.
- Existing definition DBN overlaps all 6 raw instruments and has causal contract metadata coverage.
- Existing statistics DBN overlaps all 6 raw instruments and has causal statistics coverage.
- Neither definition nor statistics contains status semantics such as `status_action`, `status_trading_event`, `status_is_trading`, or `status_is_quoting`; they cannot replace the status source without changing semantics.
- Final decision: `NO_CAUSAL_ALTERNATE_SOURCE_KEEP_EXCLUDED`.
- KE 2014 remains excluded from Phase 2 build unless a separate explicit policy exception accepts missing status enrichment, roll maturity backsteps, and synthetic coverage.
- No canonical data modification, Phase 1B re-enrichment, Phase 2 build, cleanup, redownload, or data artifact staging occurred.

## KE Phase 2 Exclusion and Policy Review

- Decision packet: `reports/phase_restart/ke_phase2_exclusion_policy_review.md`.
- KE 2013-2015 are excluded from canonical Phase 2 unless a future explicit policy exception approves them.
- KE 2014 remains specifically excluded as `KE_2014_EXCLUDED_NO_CAUSAL_STATUS_SOURCE`.
- KE 2016-2026 are `KE_2016_2026_POLICY_REVIEWABLE`: status missing rows are 0, but readiness still fails on roll and/or synthetic blockers.
- Automatically clean KE Phase 2 rows: 0.
- No Phase 2 build, cleanup, repair, redownload, move, merge, quarantine, delete, canonical data mutation, or data artifact staging occurred.

## Master Data Health Matrix
- Updated at UTC: 2026-06-22T23:25:02Z.
- Report-only matrix written to `reports/data_manifest/master_data_health_summary.md`, `reports/data_manifest/master_data_health_matrix.csv`, and `reports/data_manifest/master_data_health_matrix.json`.
- Expected market/year rows reviewed: 527.
- Health class counts: OK_SOURCE_PRESENT=45, POLICY_REVIEW_REQUIRED=450, EXCLUDED_FROM_PHASE2=9, UNKNOWN_REVIEW_REQUIRED=23.
- Drilldown required before Phase 2/model trust: 23 unknown rows and 9 excluded rows.
- Raw optional-schema audit status: `FAIL` with 23 file failures.
- Phase 2 build/exclusion evidence must be refreshed before Phase 2 build because latest KE policy excludes `KE:2015` while the older build plan accepted it.
- Validation result: `git status --short -- data` was empty; `git diff --check` was clean; the matrix report files are ignored and not staged.
- No repair, Phase 2 build, cleanup, redownload, move, merge, quarantine, delete, or DBN source modification was run by the matrix generation.
- Cleanup remains disabled.

## Unknown Review Decision Packet
- Updated at UTC: 2026-06-22T23:36:26Z.
- Decision packet: `reports/data_manifest/unknown_review_decision_packet.md` and `reports/data_manifest/unknown_review_decision_packet.json`.
- Starting `UNKNOWN_REVIEW_REQUIRED` rows: 23.
- `APPROVE_SOURCE_REFERENCE_CORRECTION_LATER`: 6 rows, SR3 2019-2024.
- `APPROVE_BOUNDED_RAW_REENRICHMENT_LATER`: 17 rows, SR1 2018-2026; TN/ZL/ZM/KE 2025-2026.
- `USER_DECISION_REQUIRED`: 0 rows.
- Phase 2 build/exclusion plan refreshed: accepted rows 57, deferred/excluded rows 9, accepted rows with pre-build raw evidence prerequisites 17.
- `KE:2015` is now excluded from future Phase 2 build batches unless separately policy-excepted.
- No repair, raw re-enrichment, source-reference correction, Phase 2 build, cleanup, redownload, move, merge, quarantine, delete, or DBN source modification was run.
- Cleanup remains disabled.

## SR3 2019 Source-Reference Correction
- Updated at UTC: 2026-06-23T00:13:05Z.
- Evidence report: `reports/phase_restart/sr3_2019_source_reference_correction.md`.
- Pushed `75b5453` to `origin/main`.
- Ran exactly one bounded local Phase 1B conversion/source-reference correction for `SR3:2019` from existing canonical DBNs.
- Output raw parquet: `data/raw/SR3/2019.parquet`, 4608 rows.
- Validation: `SR3:2019` now passes `reports/raw_readiness/raw_enriched_optional_schema_audit.json`; source reference failures are 0 and source hash mismatches are 0.
- Overall optional-schema audit remains `FAIL` because 22 unrelated rows still fail.
- Remaining source-reference correction rows: 5, SR3 2020-2024.
- Remaining bounded raw re-enrichment rows: 17, SR1 2018-2026; TN/ZL/ZM/KE 2025-2026.
- No Phase 2 build, cleanup, redownload, move, merge, quarantine, delete, or DBN source modification was run.
- Cleanup remains disabled.

## SR3 2020 Source-Reference Correction
- Updated at UTC: 2026-06-23T00:24:36Z.
- Evidence report: `reports/phase_restart/sr3_2020_source_reference_correction.md`.
- Ran exactly one bounded local Phase 1B conversion/source-reference correction for `SR3:2020` from existing canonical DBNs.
- Output raw parquet: `data/raw/SR3/2020.parquet`, 10630 rows.
- Validation: `SR3:2020` now passes `reports/raw_readiness/raw_enriched_optional_schema_audit.json`; source reference failures are 0 and source hash mismatches are 0.
- Overall optional-schema audit remains `FAIL` because 21 unrelated rows still fail.
- Remaining source-reference correction rows: 4, SR3 2021-2024.
- Remaining bounded raw re-enrichment rows: 17, SR1 2018-2026; TN/ZL/ZM/KE 2025-2026.
- No Phase 2 build, cleanup, redownload, move, merge, quarantine, delete, or DBN source modification was run.
- Cleanup remains disabled.


## Refreshed Health Matrix And Phase 2 Prerequisites
- Updated at UTC: 2026-06-23T01:49:59Z.
- This section supersedes older count snapshots above for current health-matrix and Phase 2 pre-build prerequisite counts.
- Latest raw optional-schema audit: `FAIL` with 9 file failures, 0 missing source-file references, and 0 source-hash mismatches.
- Refreshed health class counts: OK_SOURCE_PRESENT=45, POLICY_REVIEW_REQUIRED=464, EXCLUDED_FROM_PHASE2=9, UNKNOWN_REVIEW_REQUIRED=9.
- Rows still requiring raw/source prerequisite before Phase 2 build: 9 rows: KE:2025, KE:2026, SR1:2026, TN:2025, TN:2026, ZL:2025, ZL:2026, ZM:2025, ZM:2026.
- Rows cleared from stale unknown/pre-build prerequisite status by latest raw audit: SR3:2019, SR3:2020, SR3:2021, SR3:2022, SR3:2023, SR3:2024, SR1:2018, SR1:2019, SR1:2020, SR1:2021, SR1:2022, SR1:2023, SR1:2024.
- Phase 2 build commands run in this refresh: 0.
- Cleanup commands run in this refresh: 0.
- Cleanup remains disabled until blockers are zero and cleanup is separately approved.

## Raw Source Corrections Completion
- Updated at UTC: 2026-06-23T02:42:17Z.
- This section supersedes older raw/source prerequisite counts above.
- Evidence report: `reports/phase_restart/raw_source_corrections_completion.md`.
- Final raw optional-schema audit: `PASS` with `file_failure_count=0`, `missing_source_file_count=0`, `schema_failure_count=0`, `statistics_failure_count=0`, `status_failure_count=0`, and `source_hash_mismatch_count=0`.
- Rows corrected in this run: SR3 2021-2024; SR1 2018-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026; KE 2025-2026.
- Previously corrected rows preserved: SR3 2019-2020.
- Remaining source-reference correction rows: 0.
- Remaining bounded raw re-enrichment rows: 0.
- Accepted Phase 2 rows with unresolved raw/source pre-build prerequisites: 0.
- Phase 2 build commands run in this completion step: 0.
- Cleanup commands run in this completion step: 0.
- No redownload, DBN source modification, move, merge, quarantine, delete, or data artifact staging occurred.
- Cleanup remains disabled until Phase 2 execution/defer state is settled and cleanup is separately approved.
