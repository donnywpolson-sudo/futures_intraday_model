# Remaining Cleanup Blockers

Generated at UTC: 2026-06-22T11:04:54Z

## Summary

- Status manifest-policy rows are resolved by commit `c2f9998 Apply status manifest policy`.
- User decision recorded: keep both for all 12 duplicate rows; no duplicate merge/quarantine/move/delete is approved.
- User decision recorded: only the 10 Phase 1B raw parquet repairs are approved for later bounded repair; no repair was run.
- User decision recorded: the 66 Phase 2 causal repair rows remain `USER_DECISION_REQUIRED` until raw repair evidence exists.
- Cleanup remains disabled in `configs/data_manifest.yaml`.
- No cleanup, repair, merge, quarantine, data move, data delete, redownload, rebuild, conversion, phase 3+ command, or DBN source modification was run.

## Final Decision Packet

- Packet: `reports/data_manifest/final_repair_duplicate_decision_packet.md`.
- Matrix: `reports/data_manifest/final_repair_duplicate_decision_matrix.csv`.
- Decision class counts: `APPROVE_BOUNDED_REPAIR_LATER` 10; `KEEP_BOTH_DO_NOT_TOUCH` 12; `USER_DECISION_REQUIRED` 66; `UNKNOWN_BLOCKING_CLEANUP` 0.
- Explicitly deferred rows: 0.
- Duplicate rows still requiring user decision: 0.
- Phase 2 causal rows still requiring later user decision: 66.

## Repair Decisions

| Group | Rows | Final class | Scope | Required before cleanup |
|---|---:|---|---|---|
| Raw parquet repair | 10 | `APPROVE_BOUNDED_REPAIR_LATER` | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026 | yes; approved for later bounded repair only |
| Causal parquet repair with raw present | 56 | `USER_DECISION_REQUIRED` | KE 2013-2024; SR1 2018-2024; TN 2016-2024; ZL 2011-2024; ZM 2011-2024 | yes; decide after raw repair evidence |
| Causal parquet repair dependent on raw repair | 10 | `USER_DECISION_REQUIRED` | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026 | yes; raw repair evidence required first |

## Duplicate Decisions

| Final class | Rows | Scope | Policy |
|---|---:|---|---|
| `KEEP_BOTH_DO_NOT_TOUCH` | 12 | all duplicate DBN rows | preserve both files in place; no mutation |

## Cleanup Gate

- Cleanup remains disabled.
- Cleanup remains blocked until raw repairs are executed and validated, Phase 2 causal rows are decided/executed/deferred, blockers are zero, and cleanup is separately approved.
- `UNKNOWN_BLOCKING_CLEANUP`: 0.
