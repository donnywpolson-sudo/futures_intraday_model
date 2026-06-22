# ZM 2025 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T14:05:35Z

## Scope

- Selected pair: ZM 2025.
- Selection reason: first remaining raw missing pair after ZL 2026 evidence was committed and pushed.
- Phase: Phase 1B raw repair only.
- No Phase 2, Phase 3+, cleanup, merge, quarantine, move, delete, DBN redownload, full rebuild, or DBN source modification was run.

## Inputs

- OHLCV DBN: `data/dbn/ohlcv_1m/ZM/2025/2025-01-01_2026-01-01.dbn.zst`
  - SHA256 before/after: `924523691AAAF157E9D350CADABF347C00384A888281E1954CA87911532C5808`
- Definition DBN: `data/dbn/definition/ZM/2025/2025-01-01_2026-01-01.dbn.zst`
  - SHA256 before/after: `4378512E62C3D19C2CEB44B2608F7091A8CFC7F6608B3B42A46194283E585BD6`

## Output

- Raw parquet: `data/raw/ZM/2025.parquet`
- Rows: 193088
- Row groups: 1
- Columns: 25
- Size bytes: 4378100
- SHA256: `9117B0C18F433EB34C4D07167521EED6373FE41A7C780111512CBAE0F9B9510A`

## Commands Run

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols ZM --start 2025-01-01 --end 2026-01-01 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/zm_2025_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/zm_2025_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/zm_2025_phase1c_raw_repair_alignment.md
```

```powershell
python scripts\audit_data_manifest.py
```

## Validation

- Phase 1B conversion: PASS, `CONVERT_OK market=ZM year=2025 inputs=1 output=data/raw/ZM/2025.parquet rows=193088`.
- Phase 1C alignment: PASS, `expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.
- Manifest audit: PASS, `manifest_check issues=170 failures=0`.
- Raw missing pairs decreased exactly 2 -> 1.
- `ZM:2025` no longer appears as missing raw.
- No new manifest UNKNOWN rows were introduced.
- `git status --short -- data` was empty after the repair and audit.

## Remaining Blockers

- Phase 1B raw repairs remaining: 1 (`ZM:2026`).
- Phase 2 causal repair rows still require later user decision: 66.
- Cleanup remains disabled and blocked until raw repairs are validated, Phase 2 causal rows are decided or explicitly deferred, blockers are zero, and cleanup is explicitly approved.
