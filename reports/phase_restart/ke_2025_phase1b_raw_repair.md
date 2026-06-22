# KE 2025 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T11:11:45Z

## Scope

- Market/year: KE 2025.
- Approved repair class: `APPROVE_BOUNDED_REPAIR_LATER`.
- Output repaired: `data/raw/KE/2025.parquet`.
- Evidence accepted: yes, based on bounded Phase 1B command, canonical raw output, unchanged DBN source hashes, and Phase 1C PASS evidence.
- No Phase 2, Phase 3+, cleanup, quarantine, merge, move, delete, DBN redownload, or DBN source modification was run.

## Commands

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols KE --start 2025-01-01 --end 2026-01-01 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

Result: `CONVERT_OK market=KE year=2025 inputs=1 output=data/raw/KE/2025.parquet rows=157299 elapsed_s=2.640`; `CONVERT_PARQUET total=1 failed=0`.

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/ke_2025_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/ke_2025_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/ke_2025_phase1c_raw_repair_alignment.md
```

Result: `status=PASS expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.

```powershell
python scripts\audit_data_manifest.py
```

Result: `manifest_check issues=178 failures=0`.

## Evidence

- Output exists: `data/raw/KE/2025.parquet`.
- Output metadata: 157299 rows, 1 row group, 25 columns, 3653095 bytes.
- Output SHA256: `10A2C36BB91C8803388281FC09FA4FE43995726548A2DE4E96A4FADD5144BD8B`.
- Phase 1C report: `reports/phase_restart/ke_2025_phase1c_raw_repair_alignment.md`.
- Bounded profile: `reports/phase_restart/ke_2025_raw_repair_alpha_tiered.yaml`.
- Manifest summary: `reports/data_manifest/manifest_coverage_summary.md`.

## Source Integrity

- `data/dbn/ohlcv_1m/KE/2025/2025-01-01_2026-01-01.dbn.zst` SHA256 before/after: `311E1D8F21D7CE05E73CEFDA38B590C6E8003A66CC09560B0C9F3E17B653403F`.
- `data/dbn/definition/KE/2025/2025-01-01_2026-01-01.dbn.zst` SHA256 before/after: `2BAF0BC1818075EF71ABA5DA4E794A3F457ACE77CC1F416C13E9834487567C52`.

## Remaining Blockers

- Raw missing pairs: 9.
- Causal missing pairs: 66.
- Cleanup remains disabled and blocked.
