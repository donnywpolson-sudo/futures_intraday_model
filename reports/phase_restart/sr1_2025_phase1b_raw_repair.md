# SR1 2025 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T11:24:48Z

## Scope

- Market/year: SR1 2025.
- Reason selected: `SR1:2025` was the first remaining raw missing pair in `reports/data_manifest/manifest_coverage_check.csv` after the KE repairs.
- Approved repair class: `APPROVE_BOUNDED_REPAIR_LATER`.
- Output repaired: `data/raw/SR1/2025.parquet`.
- No Phase 2, Phase 3+, cleanup, quarantine, merge, move, delete, DBN redownload, or DBN source modification was run.

## Commands

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols SR1 --start 2025-01-01 --end 2026-01-01 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

Result: `CONVERT_OK market=SR1 year=2025 inputs=1 output=data/raw/SR1/2025.parquet rows=74742 elapsed_s=2.203`; `CONVERT_PARQUET total=1 failed=0`.

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/sr1_2025_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/sr1_2025_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/sr1_2025_phase1c_raw_repair_alignment.md
```

Result: `status=PASS expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.

```powershell
python scripts\audit_data_manifest.py
```

Result: `manifest_check issues=176 failures=0`.

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2025/2025-01-01_2026-01-01.dbn.zst`.
- Input definition DBN: `data/dbn/definition/SR1/2025/2025-01-01_2026-01-01.dbn.zst`.
- Output exists: `data/raw/SR1/2025.parquet`.
- Output metadata: 74742 rows, 1 row group, 25 columns, 1610364 bytes.
- Output SHA256: `77C0C3AE98E0EDBB60E891CC803D22BAEDC58E72AB12736E5167F0878250A7FC`.
- Phase 1C report: `reports/phase_restart/sr1_2025_phase1c_raw_repair_alignment.md`.
- Bounded profile: `reports/phase_restart/sr1_2025_raw_repair_alpha_tiered.yaml`.
- Manifest summary: `reports/data_manifest/manifest_coverage_summary.md`.

## Source Integrity

- `data/dbn/ohlcv_1m/SR1/2025/2025-01-01_2026-01-01.dbn.zst` SHA256 before/after: `8DEA52C4EA94FDC164762130AB021657B7D0E70D89658FF8C052CCE7F8AB88C5`.
- `data/dbn/definition/SR1/2025/2025-01-01_2026-01-01.dbn.zst` SHA256 before/after: `6A71651D426ACAE27CE6E60E92C2B5A2102BB7D4B0F0C90F4A78B835641C0883`.

## Manifest Delta

- Raw missing pairs before this repair: 8.
- Raw missing pairs after this repair: 7.
- `SR1:2025` no longer appears as a missing raw pair.
- Causal missing pairs remain 66.
- Cleanup remains disabled and blocked.
