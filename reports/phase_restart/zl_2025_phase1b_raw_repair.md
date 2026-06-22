# ZL 2025 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T13:42:19Z

## Scope

- Selected pair: ZL 2025.
- Selection reason: first remaining raw missing pair after TN 2026 evidence was committed and pushed.
- Phase: Phase 1B raw repair only.
- No Phase 2, Phase 3+, cleanup, merge, quarantine, move, delete, DBN redownload, full rebuild, or DBN source modification was run.

## Inputs

- OHLCV DBN: `data/dbn/ohlcv_1m/ZL/2025/2025-01-01_2026-01-01.dbn.zst`
  - SHA256 before/after: `6D33512DCBFA85F6760C46C0091FD434ECF045FB81C595E111D65D4657681CAB`
- Definition DBN: `data/dbn/definition/ZL/2025/2025-01-01_2026-01-01.dbn.zst`
  - SHA256 before/after: `827D54C0CFDFC511CD3F0DDF9D2F6B96CE4BC75B75D5BE5050465681E2071566`

## Output

- Raw parquet: `data/raw/ZL/2025.parquet`
- Rows: 227587
- Row groups: 1
- Columns: 25
- Size bytes: 5338424
- SHA256: `68C231A19C334A4A84E89E45F70CFFD203091F67E854DBED0EB37D2325450F19`

## Commands Run

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols ZL --start 2025-01-01 --end 2026-01-01 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/zl_2025_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/zl_2025_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/zl_2025_phase1c_raw_repair_alignment.md
```

```powershell
python scripts\audit_data_manifest.py
```

## Validation

- Phase 1B conversion: PASS, `CONVERT_OK market=ZL year=2025 inputs=1 output=data/raw/ZL/2025.parquet rows=227587`.
- Phase 1C alignment: PASS, `expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.
- Manifest audit: PASS, `manifest_check issues=172 failures=0`.
- Raw missing pairs decreased exactly 4 -> 3.
- `ZL:2025` no longer appears as missing raw.
- No new manifest UNKNOWN rows were introduced.
- `git status --short -- data` was empty after the repair and audit.

## Remaining Blockers

- Phase 1B raw repairs remaining: 3 (`ZL:2026`, `ZM:2025`, `ZM:2026`).
- Phase 2 causal repair rows still require later user decision: 66.
- Cleanup remains disabled and blocked until raw repairs are validated, Phase 2 causal rows are decided or explicitly deferred, blockers are zero, and cleanup is explicitly approved.
