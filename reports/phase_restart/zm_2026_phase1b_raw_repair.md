# ZM 2026 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T14:12:07Z

## Scope

- Selected pair: ZM 2026.
- Selection reason: final remaining raw missing pair after ZM 2025 evidence was committed and pushed.
- Phase: Phase 1B raw repair only.
- No Phase 2, Phase 3+, cleanup, merge, quarantine, move, delete, DBN redownload, full rebuild, or DBN source modification was run.

## Inputs

- OHLCV DBN: `data/dbn/ohlcv_1m/ZM/2026/2026-01-01_2026-06-13.dbn.zst`
  - SHA256 before/after: `DC9BB62851491755DBCC5B695C57EE44FA800CA5EEE79EB83DC047B4AB30E6CE`
- Definition DBN: `data/dbn/definition/ZM/2026/2026-01-01_2026-06-13.dbn.zst`
  - SHA256 before/after: `A9B9890B8E9A094478F20354B45728887CB396FA6CCFA23D4A584AE21C4FFBB1`

## Output

- Raw parquet: `data/raw/ZM/2026.parquet`
- Rows: 93278
- Row groups: 1
- Columns: 25
- Size bytes: 2230453
- SHA256: `A66252DC985E46A4D1876F444623DA69A4B4AD980394819CCA49D16A5A1FAE6D`

## Commands Run

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols ZM --start 2026-01-01 --end 2026-06-13 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/zm_2026_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/zm_2026_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/zm_2026_phase1c_raw_repair_alignment.md
```

```powershell
python scripts\audit_data_manifest.py
```

## Validation

- Phase 1B conversion: PASS, `CONVERT_OK market=ZM year=2026 inputs=1 output=data/raw/ZM/2026.parquet rows=93278`.
- Phase 1C alignment: PASS, `expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.
- Manifest audit: PASS, `manifest_check issues=169 failures=0`.
- Raw missing pairs decreased exactly 1 -> 0.
- `ZM:2026` no longer appears as missing raw.
- No new manifest UNKNOWN rows were introduced.
- `git status --short -- data` was empty after the repair and audit.

## Remaining Blockers

- Phase 1B raw repairs remaining: 0.
- Phase 2 causal repair rows still require later user decision: 66.
- Cleanup remains disabled and blocked until Phase 2 causal rows are decided or explicitly deferred, blockers are zero, and cleanup is explicitly approved.
