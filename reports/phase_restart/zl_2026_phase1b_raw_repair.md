# ZL 2026 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T13:55:37Z

## Scope

- Selected pair: ZL 2026.
- Selection reason: first remaining raw missing pair after ZL 2025 evidence was committed and pushed.
- Phase: Phase 1B raw repair only.
- No Phase 2, Phase 3+, cleanup, merge, quarantine, move, delete, DBN redownload, full rebuild, or DBN source modification was run.

## Inputs

- OHLCV DBN: `data/dbn/ohlcv_1m/ZL/2026/2026-01-01_2026-06-13.dbn.zst`
  - SHA256 before/after: `36663221B44ED65B5CA70B2AB379F200180E4A6AA6ED814C44D0F999230C3487`
- Definition DBN: `data/dbn/definition/ZL/2026/2026-01-01_2026-06-13.dbn.zst`
  - SHA256 before/after: `8D78FD2324CA87E3B0E13FC3D7DB52E24B210BB323B05F2FC5C6B9EE94A1EFCA`

## Output

- Raw parquet: `data/raw/ZL/2026.parquet`
- Rows: 107919
- Row groups: 1
- Columns: 25
- Size bytes: 2791968
- SHA256: `B068D7CAE71ED1F0573BCDF2510725F54112049404A72678A072F66DEE2C087F`

## Commands Run

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols ZL --start 2026-01-01 --end 2026-06-13 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/zl_2026_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/zl_2026_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/zl_2026_phase1c_raw_repair_alignment.md
```

```powershell
python scripts\audit_data_manifest.py
```

## Validation

- Phase 1B conversion: PASS, `CONVERT_OK market=ZL year=2026 inputs=1 output=data/raw/ZL/2026.parquet rows=107919`.
- Phase 1C alignment: PASS, `expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.
- Manifest audit: PASS, `manifest_check issues=171 failures=0`.
- Raw missing pairs decreased exactly 3 -> 2.
- `ZL:2026` no longer appears as missing raw.
- No new manifest UNKNOWN rows were introduced.
- `git status --short -- data` was empty after the repair and audit.

## Remaining Blockers

- Phase 1B raw repairs remaining: 2 (`ZM:2025`, `ZM:2026`).
- Phase 2 causal repair rows still require later user decision: 66.
- Cleanup remains disabled and blocked until raw repairs are validated, Phase 2 causal rows are decided or explicitly deferred, blockers are zero, and cleanup is explicitly approved.
