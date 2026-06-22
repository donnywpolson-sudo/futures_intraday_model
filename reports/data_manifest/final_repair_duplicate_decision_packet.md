# Final Repair/Duplicate Decision Packet

Generated at UTC: 2026-06-22T14:22:47Z

## Summary

- User decision recorded: `KEEP_BOTH_DO_NOT_TOUCH` for all 12 duplicate rows.
- User decision recorded: all 10 bounded Phase 1B raw parquet repairs have evidence; raw missing pairs are now 0.
- User decision recorded: approve the 66 Phase 2 causal repairs for later bounded one-market/year repair runs; stop before Phase 2 execution.
- Starting blocker counts: 76 repair approval rows and 12 duplicate policy rows.
- Final decision classes: `APPROVE_BOUNDED_REPAIR_LATER` 76; `KEEP_BOTH_DO_NOT_TOUCH` 12; `USER_DECISION_REQUIRED` 0; `UNKNOWN_BLOCKING_CLEANUP` 0.
- Rows approved for later bounded repair classification: 76.
- Rows explicitly deferred: 0.
- Rows requiring a later user repair decision: 0.
- Duplicate rows still requiring user decision: 0.
- No Phase 2 execution, cleanup, move, quarantine, merge, delete, rebuild, redownload, phase 3+ command, or DBN source modification occurred in this decision step.
- Cleanup remains disabled in `configs/data_manifest.yaml` and remains blocked until approved Phase 2 causal repairs are executed or explicitly deferred, blockers are zero, and cleanup is explicitly approved.

## Counts By Final Decision Class

| Final decision class | Repair rows | Duplicate rows | Total rows |
|---|---:|---:|---:|
| `APPROVE_BOUNDED_REPAIR_LATER` | 76 | 0 | 76 |
| `EXPLICITLY_DEFER_REPAIR` | 0 | 0 | 0 |
| `KEEP_BLOCKED_UNTIL_SOURCE_DATA_REVIEW` | 0 | 0 | 0 |
| `KEEP_BOTH_DO_NOT_TOUCH` | 0 | 12 | 12 |
| `APPROVE_MERGE_LATER` | 0 | 0 | 0 |
| `APPROVE_QUARANTINE_LATER` | 0 | 0 | 0 |
| `EXPLICITLY_DEFER_DUPLICATE_POLICY` | 0 | 0 | 0 |
| `USER_DECISION_REQUIRED` | 0 | 0 | 0 |
| `UNKNOWN_BLOCKING_CLEANUP` | 0 | 0 | 0 |

## Repair Decision Groups

| Group | Rows | Final class | Phase/script likely responsible | Schema | Market/year scope | Canonical output path | Decision status | Why bounded | Later command pattern | Validation command | Stop condition |
|---|---:|---|---|---|---|---|---|---|---|---|---|
| Raw parquet repair | 10 | `APPROVE_BOUNDED_REPAIR_LATER` | `scripts/phase1B_convert/convert_databento_raw.py` | `phase1b_raw_parquet` | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026 | `data/raw/{market}/{year}.parquet` | Completed and validated by bounded Phase 1B plus Phase 1C evidence; raw missing pairs are 0. | One market/year and one-year local DBN input window; no redownload, phase 3+, or cleanup. | complete | `python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config <bounded-profile> --profile <bounded-profile> --dbn-root data/dbn --raw-root data/raw --expected-only` | Completed evidence exists for all 10 raw rows; stop if DBN source changes or raw missing reappears. |
| Causal parquet repair with raw present | 66 | `APPROVE_BOUNDED_REPAIR_LATER` | `scripts/phase2_causal_base/build_causal_base_data.py` | `phase2_causal_base_parquet` | KE 2013-2026; SR1 2018-2026; TN 2016-2026; ZL 2011-2026; ZM 2011-2026 | `data/causally_gated_normalized/{market}/{year}.parquet` | User approved this group for later bounded Phase 2 repair; no Phase 2 execution in this step. | One market/year through a bounded profile using existing canonical raw parquet; no phase 3+, cleanup, rebuild, or redownload. | `python -m scripts.phase2_causal_base.build_causal_base_data --profile <bounded-profile> --profile-config <bounded-profile.yaml> --raw-root data/raw --output-root data/causally_gated_normalized --reports-root reports/phase_restart --readiness-only` first; after readiness PASS and separate execution approval, rerun same bounded profile without `--readiness-only`. | Readiness-only command before build; after approved build run `python scripts\audit_data_manifest.py` and `git status --short -- data`. | Stop now before Phase 2 execution; future bounded run stops when one approved causal parquet exists, manifest audit passes, and no unexpected data status appears. |

Explicit approval to execute is still required before running any Phase 2 command. This packet records the Phase 2 causal approval decision and stops before Phase 2 execution.

## Duplicate Decision Rows

| Schema | Pair | Final class | Canonical path | Duplicate path | Likely data type | Overwrite/conflict risk | Validation needed before any future action |
|---|---|---|---|---|---|---|---|
| `ohlcv-1m` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/ohlcv_1m/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/ohlcv_1m/6M/2026/2026-06-12_2026-06-13.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `ohlcv-1s` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/ohlcv_1s/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/ohlcv_1s/6M/2026/2026-06-12_2026-06-13.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `ohlcv-1h` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/ohlcv_1h/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/ohlcv_1h/6M/2026/2026-06-12_2026-06-13.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `ohlcv-1d` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/ohlcv_1d/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/ohlcv_1d/6M/2026/2026-06-12_2026-06-13.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `statistics` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/statistics/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/statistics/6M/2026/2026-06-12_2026-06-13.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `statistics` | RTY:2017 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/statistics/RTY/2017/2017-01-01_2018-01-01.dbn.zst` | `data/dbn/statistics/RTY/2017/2017-06-05_2018-01-01.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `statistics` | SR3:2018 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/statistics/SR3/2018/2018-01-01_2019-01-01.dbn.zst` | `data/dbn/statistics/SR3/2018/2018-04-23_2019-01-01.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `status` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/status/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/status/6M/2026/2026-06-12_2026-06-13.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `status` | RTY:2017 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/status/RTY/2017/2017-01-01_2018-01-01.dbn.zst` | `data/dbn/status/RTY/2017/2017-06-05_2018-01-01.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `status` | SR3:2018 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/status/SR3/2018/2018-01-01_2019-01-01.dbn.zst` | `data/dbn/status/SR3/2018/2018-04-23_2019-01-01.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `definition` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/definition/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/definition/6M/2026/2026-06-12_2026-06-13.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |
| `trades` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` | `data/dbn/trades/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/trades/6M/2026/2026-06-12_2026-06-13.dbn.zst` | DBN/raw source archive | none for keep-both; high for any later merge/quarantine unless separately approved | no future duplicate action approved; if policy changes later, run approved content/provenance comparison first |

All duplicate rows are now explicit no-mutation decisions: preserve both files in place. No merge, quarantine, move, delete, overwrite, or content scan is approved by this packet.

## Recommended Next User Decision

1. Execute a separate bounded Phase 2 repair goal for one approved causal market/year at a time, readiness-only first, then stop before broader execution.
2. Continue to keep duplicate files in place; no duplicate merge, quarantine, move, or delete is approved.
3. Keep cleanup disabled until the 66 Phase 2 causal rows are executed or explicitly deferred, blockers are zero, and cleanup is explicitly approved.

## Smallest Safe Executable Next Step After Approval

The smallest safe executable next step is one approved bounded Phase 2 causal readiness-only check for one market/year, likely the first causal missing row `KE:2013`. Stop before Phase 2 build execution unless a separate execution goal explicitly approves it, and always stop before duplicate action or cleanup.

## Evidence

- `reports/data_manifest/final_repair_duplicate_decision_matrix.csv` contains all 88 row-level decisions.
- `reports/data_manifest/manifest_repair_plan.csv` contains the 76 source repair approval rows.
- `reports/data_manifest/manifest_duplicate_policy_proposal.csv` contains the 12 duplicate policy rows and cheap metadata evidence.
- `reports/data_manifest/manifest_cleanup_approval_packet.md` records the starting blocker counts.
- `configs/data_manifest.yaml` records `artifact_policy.cleanup_allowed: false`.
