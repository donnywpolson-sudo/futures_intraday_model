# TN 2026 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T13:28:32Z

## Scope

- Selected pair: TN 2026.
- Selection reason: first remaining raw missing pair after TN 2025 evidence was committed and pushed.
- Phase: Phase 1B raw repair only.
- No Phase 2, Phase 3+, cleanup, merge, quarantine, move, delete, DBN redownload, full rebuild, or DBN source modification was run.

## Inputs

- OHLCV DBN: `data/dbn/ohlcv_1m/TN/2026/2026-01-01_2026-06-13.dbn.zst`
  - SHA256 before/after: `EBD02E1D94873D0A00C1DCDFDDA5F149A065041319DB40E21D88A83461107166`
- Definition DBN: `data/dbn/definition/TN/2026/2026-01-01_2026-06-13.dbn.zst`
  - SHA256 before/after: `A76AB85A81B865F37B40900F6543E737B68005030C057604134202E0F718B618`

## Output

- Raw parquet: `data/raw/TN/2026.parquet`
- Rows: 131674
- Row groups: 1
- Columns: 25
- Size bytes: 3062842
- SHA256: `7C4AEB049C8AA9183B5DEE1CDC4474A36E62261AD03B82DDB3EA9B1438348C86`

## Commands Run

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols TN --start 2026-01-01 --end 2026-06-13 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/tn_2026_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/tn_2026_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/tn_2026_phase1c_raw_repair_alignment.md
```

```powershell
python scripts\audit_data_manifest.py
```

## Validation

- Phase 1B conversion: PASS, `CONVERT_OK market=TN year=2026 inputs=1 output=data/raw/TN/2026.parquet rows=131674`.
- Phase 1C alignment: PASS, `expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.
- Manifest audit: PASS, `manifest_check issues=173 failures=0`.
- Raw missing pairs decreased exactly 5 -> 4.
- `TN:2026` no longer appears as missing raw.
- No new manifest UNKNOWN rows were introduced.
- `git status --short -- data` was empty after the repair and audit.

## Remaining Blockers

- Phase 1B raw repairs remaining: 4 (`ZL:2025`, `ZL:2026`, `ZM:2025`, `ZM:2026`).
- Phase 2 causal repair rows still require later user decision: 66.
- Cleanup remains disabled and blocked until raw repairs are validated, Phase 2 causal rows are decided or explicitly deferred, blockers are zero, and cleanup is explicitly approved.
