# KE 2026 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T11:17:07Z

## Scope

- Market/year: KE 2026.
- Reason selected: `KE:2026` was the first remaining raw missing pair in `reports/data_manifest/manifest_coverage_check.csv` after accepting KE 2025 evidence.
- Approved repair class: `APPROVE_BOUNDED_REPAIR_LATER`.
- Output repaired: `data/raw/KE/2026.parquet`.
- No Phase 2, Phase 3+, cleanup, quarantine, merge, move, delete, DBN redownload, or DBN source modification was run.

## Commands

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols KE --start 2026-01-01 --end 2026-06-13 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

Result: `CONVERT_OK market=KE year=2026 inputs=1 output=data/raw/KE/2026.parquet rows=83160 elapsed_s=1.547`; `CONVERT_PARQUET total=1 failed=0`.

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/ke_2026_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/ke_2026_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/ke_2026_phase1c_raw_repair_alignment.md
```

Result: `status=PASS expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.

```powershell
python scripts\audit_data_manifest.py
```

Result: `manifest_check issues=177 failures=0`.

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/KE/2026/2026-01-01_2026-06-13.dbn.zst`.
- Input definition DBN: `data/dbn/definition/KE/2026/2026-01-01_2026-06-13.dbn.zst`.
- Output exists: `data/raw/KE/2026.parquet`.
- Output metadata: 83160 rows, 1 row group, 25 columns, 2008762 bytes.
- Output SHA256: `BD044B4A31801A91B6FC4E6D418AE34E1A119BCCA542814DB01D9D6B7331DFF6`.
- Phase 1C report: `reports/phase_restart/ke_2026_phase1c_raw_repair_alignment.md`.
- Bounded profile: `reports/phase_restart/ke_2026_raw_repair_alpha_tiered.yaml`.
- Manifest summary: `reports/data_manifest/manifest_coverage_summary.md`.

## Source Integrity

- `data/dbn/ohlcv_1m/KE/2026/2026-01-01_2026-06-13.dbn.zst` SHA256 before/after: `8CA4F0215BAB6CCD44DA1ED4362680D4AE5A1FC7058B77D439124E75F6E2D7B6`.
- `data/dbn/definition/KE/2026/2026-01-01_2026-06-13.dbn.zst` SHA256 before/after: `52AD5E32131C41D9B473B7A95578CDAFEBFFDC7D9EDDD7AD76CB29D54F8798C0`.

## Manifest Delta

- Raw missing pairs before this repair: 9.
- Raw missing pairs after this repair: 8.
- `KE:2026` no longer appears as a missing raw pair.
- Causal missing pairs remain 66.
- Cleanup remains disabled and blocked.
