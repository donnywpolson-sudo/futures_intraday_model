# Final Repair/Duplicate Decision Packet

Generated at UTC: 2026-06-22T11:04:54Z

## Summary

- User decision recorded: `KEEP_BOTH_DO_NOT_TOUCH` for all 12 duplicate rows.
- User decision recorded: approve only the 10 bounded Phase 1B raw parquet repairs for a later repair run; stop before running repair.
- User decision recorded: decide the 66 Phase 2 causal repairs only after raw repair evidence exists; no Phase 2 repair is approved now.
- Starting blocker counts: 76 repair approval rows and 12 duplicate policy rows.
- Final decision classes: `APPROVE_BOUNDED_REPAIR_LATER` 10; `KEEP_BOTH_DO_NOT_TOUCH` 12; `USER_DECISION_REQUIRED` 66; `UNKNOWN_BLOCKING_CLEANUP` 0.
- Rows approved for later bounded repair classification: 10.
- Rows explicitly deferred: 0.
- Rows requiring a later user repair decision: 66.
- Duplicate rows still requiring user decision: 0.
- No repair, cleanup, move, quarantine, merge, delete, rebuild, redownload, conversion, phase 3+ command, or DBN source modification occurred in this step.
- Cleanup remains disabled in `configs/data_manifest.yaml` and remains blocked until repair blockers are zero and cleanup is explicitly approved.

## Counts By Final Decision Class

| Final decision class | Repair rows | Duplicate rows | Total rows |
|---|---:|---:|---:|
| `APPROVE_BOUNDED_REPAIR_LATER` | 10 | 0 | 10 |
| `EXPLICITLY_DEFER_REPAIR` | 0 | 0 | 0 |
| `KEEP_BLOCKED_UNTIL_SOURCE_DATA_REVIEW` | 0 | 0 | 0 |
| `KEEP_BOTH_DO_NOT_TOUCH` | 0 | 12 | 12 |
| `APPROVE_MERGE_LATER` | 0 | 0 | 0 |
| `APPROVE_QUARANTINE_LATER` | 0 | 0 | 0 |
| `EXPLICITLY_DEFER_DUPLICATE_POLICY` | 0 | 0 | 0 |
| `USER_DECISION_REQUIRED` | 66 | 0 | 66 |
| `UNKNOWN_BLOCKING_CLEANUP` | 0 | 0 | 0 |

## Repair Decision Groups

| Group | Rows | Final class | Phase/script likely responsible | Schema | Market/year scope | Canonical output path | Decision status | Why bounded | Later command pattern | Validation command | Stop condition |
|---|---:|---|---|---|---|---|---|---|---|---|---|
| Raw parquet repair | 10 | `APPROVE_BOUNDED_REPAIR_LATER` | `scripts/phase1B_convert/convert_databento_raw.py` | `phase1b_raw_parquet` | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026 | `data/raw/{market}/{year}.parquet` | User approved this group for a later bounded repair run; no execution in this step. | One market/year and one-year local DBN input window; no redownload, phase 3+, or cleanup. | `python -m scripts.phase1B_convert.convert_databento_raw --symbols <MARKET> --start <YEAR>-01-01 --end <YEAR+1>-01-01 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions` | `python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config <bounded-profile> --profile <bounded-profile> --dbn-root data/dbn --raw-root data/raw --expected-only` | Stop when the approved `data/raw/<MARKET>/<YEAR>.parquet` exists and bounded Phase 1C alignment passes; stop if output already exists unexpectedly or any DBN source changes. |
| Causal parquet repair with raw present | 56 | `USER_DECISION_REQUIRED` | `scripts/phase2_causal_base/build_causal_base_data.py` | `phase2_causal_base_parquet` | KE 2013-2024; SR1 2018-2024; TN 2016-2024; ZL 2011-2024; ZM 2011-2024 | `data/causally_gated_normalized/{market}/{year}.parquet` | User deferred the Phase 2 causal decision until raw repair evidence exists. | Not executable yet; if later approved, one market/year through a bounded profile with no phase 3+. | not approved yet | future readiness-only before any build | Stop before Phase 2 repair until user decides after raw repair evidence. |
| Causal parquet repair dependent on raw repair | 10 | `USER_DECISION_REQUIRED` | `scripts/phase2_causal_base/build_causal_base_data.py` | `phase2_causal_base_parquet` | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026 | `data/causally_gated_normalized/{market}/{year}.parquet` | Matching raw parquet must exist first; user deferred Phase 2 causal decision. | Not executable yet; if later approved, one market/year after raw repair evidence with no phase 3+. | not approved yet | future readiness-only before any build | Stop before Phase 2 repair until raw repair output and alignment evidence exist and user decides. |

Explicit approval to execute is still required before running any repair command. This packet records the chosen order and blocks Phase 2 causal repair until raw repair evidence is available and reviewed.

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

1. Execute a separate bounded repair goal for one approved Phase 1B raw market/year at a time, then validate with Phase 1C alignment.
2. After all 10 raw repairs have evidence, review the 66 Phase 2 causal rows and approve bounded repair or explicit deferral.
3. Keep duplicate files in place and keep cleanup disabled until repair blockers are zero and cleanup is explicitly approved.

## Smallest Safe Executable Next Step After Approval

The smallest safe executable next step is one approved Phase 1B raw parquet repair for one market/year from the 10 raw rows, followed by bounded Phase 1C alignment validation for that same pair. Stop before any causal repair, duplicate action, or cleanup.

## Evidence

- `reports/data_manifest/final_repair_duplicate_decision_matrix.csv` contains all 88 row-level decisions.
- `reports/data_manifest/manifest_repair_plan.csv` contains the 76 source repair approval rows.
- `reports/data_manifest/manifest_duplicate_policy_proposal.csv` contains the 12 duplicate policy rows and cheap metadata evidence.
- `reports/data_manifest/manifest_cleanup_approval_packet.md` records the starting blocker counts.
- `configs/data_manifest.yaml` records `artifact_policy.cleanup_allowed: false`.
