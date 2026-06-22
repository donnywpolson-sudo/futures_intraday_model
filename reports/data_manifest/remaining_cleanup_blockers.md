# Remaining Cleanup Blockers

Generated at UTC: 2026-06-22T13:55:37Z

## Summary

- Status manifest-policy rows are resolved by commit `c2f9998 Apply status manifest policy`.
- User decision recorded: keep both for all 12 duplicate rows; no duplicate merge/quarantine/move/delete is approved.
- Eight bounded Phase 1B raw repairs have been run and validated: `data/raw/KE/2025.parquet`, `data/raw/KE/2026.parquet`, `data/raw/SR1/2025.parquet`, `data/raw/SR1/2026.parquet`, `data/raw/TN/2025.parquet`, `data/raw/TN/2026.parquet`, `data/raw/ZL/2025.parquet`, and `data/raw/ZL/2026.parquet`.
- Remaining approved Phase 1B raw parquet repairs: 2.
- User decision recorded: the 66 Phase 2 causal repair rows remain `USER_DECISION_REQUIRED` until raw repair evidence exists.
- Cleanup remains disabled in `configs/data_manifest.yaml`.
- No cleanup, merge, quarantine, data move, data delete, redownload, rebuild, phase 2, phase 3+ command, or DBN source modification was run.

## Final Decision Packet

- Packet: `reports/data_manifest/final_repair_duplicate_decision_packet.md`.
- Matrix: `reports/data_manifest/final_repair_duplicate_decision_matrix.csv`.
- Current manifest audit: `manifest_check issues=171 failures=0`.
- Decision/evidence counts: 8 raw repairs completed and validated; `APPROVE_BOUNDED_REPAIR_LATER` raw rows remaining 2; `KEEP_BOTH_DO_NOT_TOUCH` duplicate rows 12; `USER_DECISION_REQUIRED` causal rows 66; `UNKNOWN_BLOCKING_CLEANUP` 0.
- Explicitly deferred rows: 0.
- Duplicate rows still requiring user decision: 0.
- Phase 2 causal rows still requiring later user decision: 66.

## Repair Decisions

| Group | Rows | Final class | Scope | Required before cleanup |
|---|---:|---|---|---|
| Raw parquet repair completed | 8 | validated evidence | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026 | still blocks cleanup until Phase 2 decision is made |
| Raw parquet repair remaining | 2 | `APPROVE_BOUNDED_REPAIR_LATER` | ZM 2025-2026 | yes; approved for later bounded repair only |
| Causal parquet repair with raw present | 64 | `USER_DECISION_REQUIRED` | KE 2013-2026; SR1 2018-2026; TN 2016-2026; ZL 2011-2026; ZM 2011-2024 | yes; decide after raw repair evidence |
| Causal parquet repair dependent on raw repair | 2 | `USER_DECISION_REQUIRED` | ZM 2025-2026 | yes; raw repair evidence required first |

## Duplicate Decisions

| Final class | Rows | Scope | Policy |
|---|---:|---|---|
| `KEEP_BOTH_DO_NOT_TOUCH` | 12 | all duplicate DBN rows | preserve both files in place; no mutation |

## Cleanup Gate

- Cleanup remains disabled.
- Cleanup remains blocked until raw repairs are executed and validated, Phase 2 causal rows are decided/executed/deferred, blockers are zero, and cleanup is separately approved.
- `UNKNOWN_BLOCKING_CLEANUP`: 0.

## Latest Raw Repair Evidence

- Evidence reports: `reports/phase_restart/ke_2025_phase1b_raw_repair.md`, `reports/phase_restart/ke_2026_phase1b_raw_repair.md`, `reports/phase_restart/sr1_2025_phase1b_raw_repair.md`, `reports/phase_restart/sr1_2026_phase1b_raw_repair.md`, `reports/phase_restart/tn_2025_phase1b_raw_repair.md`, `reports/phase_restart/tn_2026_phase1b_raw_repair.md`, `reports/phase_restart/zl_2025_phase1b_raw_repair.md`, and `reports/phase_restart/zl_2026_phase1b_raw_repair.md`.
- Progress report: `reports/phase_restart/phase1b_raw_repair_progress.md`.
- Phase 1C alignment: PASS for KE 2025, KE 2026, SR1 2025, SR1 2026, TN 2025, TN 2026, ZL 2025, and ZL 2026.
- Manifest raw missing pairs after latest repair: 2.
