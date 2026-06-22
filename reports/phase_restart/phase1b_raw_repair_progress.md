# Phase 1B Raw Repair Progress

Generated at UTC: 2026-06-22T13:42:19Z

## Summary

- Completed and validated raw repairs: 7.
- Remaining raw missing pairs: 3.
- Phase 2 causal rows still undecided: 66.
- Duplicate policy: 12 rows are `KEEP_BOTH_DO_NOT_TOUCH`.
- Cleanup remains disabled and blocked.

## Completed Repairs

| Pair | Output | Phase 1C | Evidence |
|---|---|---|---|
| KE:2025 | `data/raw/KE/2025.parquet` | PASS | `reports/phase_restart/ke_2025_phase1b_raw_repair.md` |
| KE:2026 | `data/raw/KE/2026.parquet` | PASS | `reports/phase_restart/ke_2026_phase1b_raw_repair.md` |
| SR1:2025 | `data/raw/SR1/2025.parquet` | PASS | `reports/phase_restart/sr1_2025_phase1b_raw_repair.md` |
| SR1:2026 | `data/raw/SR1/2026.parquet` | PASS | `reports/phase_restart/sr1_2026_phase1b_raw_repair.md` |
| TN:2025 | `data/raw/TN/2025.parquet` | PASS | `reports/phase_restart/tn_2025_phase1b_raw_repair.md` |
| TN:2026 | `data/raw/TN/2026.parquet` | PASS | `reports/phase_restart/tn_2026_phase1b_raw_repair.md` |
| ZL:2025 | `data/raw/ZL/2025.parquet` | PASS | `reports/phase_restart/zl_2025_phase1b_raw_repair.md` |

## Remaining Raw Repairs

| Pair | Status |
|---|---|
| ZL:2026 | approved for later bounded Phase 1B raw repair |
| ZM:2025 | approved for later bounded Phase 1B raw repair |
| ZM:2026 | approved for later bounded Phase 1B raw repair |

## Safety

- No Phase 2 command was run.
- No cleanup command was run.
- No DBN source files were modified.
- No data files were deleted.
