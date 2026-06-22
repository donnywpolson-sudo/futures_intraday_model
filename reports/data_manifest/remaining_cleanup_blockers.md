# Remaining Cleanup Blockers

Generated at UTC: 2026-06-22T10:56:58Z

## Summary

- Status manifest-policy rows are resolved by commit `c2f9998 Apply status manifest policy`.
- `reports/data_manifest/manifest_coverage_check.csv` classifies the 68 missing `data/dbn/status` pairs as `expected_missing`, not `unexpected_missing`.
- Cleanup remains disabled in `configs/data_manifest.yaml`.
- Cleanup gate remains blocked by 76 repair approval rows and 12 duplicate policy rows until the user accepts or changes the final decisions.
- No cleanup, repair, merge, quarantine, data move, data delete, redownload, rebuild, conversion, phase 3+ command, or DBN source modification was run.

## Final Decision Packet

- Packet: `reports/data_manifest/final_repair_duplicate_decision_packet.md`.
- Matrix: `reports/data_manifest/final_repair_duplicate_decision_matrix.csv`.
- Decision class counts: `APPROVE_BOUNDED_REPAIR_LATER` 76; `KEEP_BOTH_DO_NOT_TOUCH` 8; `USER_DECISION_REQUIRED` 4; `UNKNOWN_BLOCKING_CLEANUP` 0.
- Explicitly deferred rows: 0.
- Future execution approval required before repair or duplicate mutation: 80 rows.

## Repair Decisions

| Group | Rows | Final class | Scope | Required before cleanup |
|---|---:|---|---|---|
| Raw parquet repair | 10 | `APPROVE_BOUNDED_REPAIR_LATER` | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026 | yes |
| Causal parquet repair with raw present | 56 | `APPROVE_BOUNDED_REPAIR_LATER` | KE 2013-2024; SR1 2018-2024; TN 2016-2024; ZL 2011-2024; ZM 2011-2024 | yes |
| Causal parquet repair dependent on raw repair | 10 | `APPROVE_BOUNDED_REPAIR_LATER` | KE 2025-2026; SR1 2025-2026; TN 2025-2026; ZL 2025-2026; ZM 2025-2026 | yes, after raw repair |

## Duplicate Decisions

| Final class | Rows | Scope | Policy |
|---|---:|---|---|
| `KEEP_BOTH_DO_NOT_TOUCH` | 8 | 6M:2026 across ohlcv/status/statistics/definition/trades DBN roots | preserve both files in place; no mutation |
| `USER_DECISION_REQUIRED` | 4 | RTY:2017 and SR3:2018 statistics/status DBN rows | choose keep-both, later merge, later quarantine, or explicit deferral |

## Cleanup Gate

- Cleanup remains disabled.
- Cleanup remains blocked until the repair approvals and duplicate policy decisions are accepted or explicitly deferred, blockers are zero, and cleanup is separately approved.
- `UNKNOWN_BLOCKING_CLEANUP`: 0.
