# SR1 2026 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T11:32:24Z

## Scope

- Market/year: SR1 2026.
- Reason selected: `SR1:2026` was the first remaining raw missing pair in `reports/data_manifest/manifest_coverage_check.csv` after SR1 2025.
- Approved repair class: `APPROVE_BOUNDED_REPAIR_LATER`.
- Output repaired: `data/raw/SR1/2026.parquet`.
- No Phase 2, Phase 3+, cleanup, quarantine, merge, move, delete, DBN redownload, or DBN source modification was run.

## Commands

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols SR1 --start 2026-01-01 --end 2026-06-13 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

Result: `CONVERT_OK market=SR1 year=2026 inputs=1 output=data/raw/SR1/2026.parquet rows=28558 elapsed_s=1.703`; `CONVERT_PARQUET total=1 failed=0`.

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/sr1_2026_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/sr1_2026_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/sr1_2026_phase1c_raw_repair_alignment.md
```

Result: `status=PASS expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.

```powershell
python scripts\audit_data_manifest.py
```

Result: `manifest_check issues=175 failures=0`.

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2026/2026-01-01_2026-06-13.dbn.zst`.
- Input definition DBN: `data/dbn/definition/SR1/2026/2026-01-01_2026-06-13.dbn.zst`.
- Output exists: `data/raw/SR1/2026.parquet`.
- Output metadata: 28558 rows, 1 row group, 25 columns, 616906 bytes.
- Output SHA256: `41CE25B4372C58B17D64CCE4CD798C63E4AB86F0824B1B892DC30CCBD8AFA40B`.
- Phase 1C report: `reports/phase_restart/sr1_2026_phase1c_raw_repair_alignment.md`.
- Bounded profile: `reports/phase_restart/sr1_2026_raw_repair_alpha_tiered.yaml`.
- Manifest summary: `reports/data_manifest/manifest_coverage_summary.md`.

## Source Integrity

- `data/dbn/ohlcv_1m/SR1/2026/2026-01-01_2026-06-13.dbn.zst` SHA256 before/after: `BA0B0B03D48DBDCA1318D0F30045BF196F03359094DC4A5224FB0B3A0FB7C929`.
- `data/dbn/definition/SR1/2026/2026-01-01_2026-06-13.dbn.zst` SHA256 before/after: `46CD0730E3B93E9C47CAAB7AAA4D9C7793CDAE0E7A222FFA0329335DD5C44552`.

## Manifest Delta

- Raw missing pairs before this repair: 7.
- Raw missing pairs after this repair: 6.
- `SR1:2026` no longer appears as a missing raw pair.
- Causal missing pairs remain 66.
- Cleanup remains disabled and blocked.
