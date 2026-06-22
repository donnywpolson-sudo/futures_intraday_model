# TN 2025 Phase 1B Raw Repair Evidence

Generated at UTC: 2026-06-22T11:40:23Z

## Scope

- Selected pair: TN 2025.
- Selection reason: first remaining raw missing pair after SR1 2026 evidence was committed.
- Phase: Phase 1B raw repair only.
- No Phase 2, Phase 3+, cleanup, merge, quarantine, move, delete, DBN redownload, full rebuild, or DBN source modification was run.

## Inputs

- OHLCV DBN: `data/dbn/ohlcv_1m/TN/2025/2025-01-01_2026-01-01.dbn.zst`
  - SHA256 before/after: `7AAABEE6669F6CD61F38D0BE665E0C7ABCC4B0AA3C4414E2399F33FDA0AF1855`
- Definition DBN: `data/dbn/definition/TN/2025/2025-01-01_2026-01-01.dbn.zst`
  - SHA256 before/after: `C4C7D3E54690DDF32D1A7F31F91A62BE07E91C6751424F26A03C55B871413C9C`

## Output

- Raw parquet: `data/raw/TN/2025.parquet`
- Rows: 293412
- Row groups: 1
- Columns: 25
- Size bytes: 6193870
- SHA256: `67EFF207A842E2C14C9C36FE674144B6E0EAFA0435854C64444081C49DC52A31`

## Commands Run

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols TN --start 2025-01-01 --end 2026-01-01 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions
```

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/tn_2025_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/tn_2025_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/tn_2025_phase1c_raw_repair_alignment.md
```

```powershell
python scripts\audit_data_manifest.py
```

## Validation

- Phase 1B conversion: PASS, `CONVERT_OK market=TN year=2025 inputs=1 output=data/raw/TN/2025.parquet rows=293412`.
- Phase 1C alignment: PASS, `expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.
- Manifest audit: PASS, `manifest_check issues=174 failures=0`.
- Raw missing pairs decreased exactly 6 -> 5.
- `TN:2025` no longer appears as missing raw.
- No new manifest UNKNOWN rows were introduced.
- `git status --short -- data` was empty after the repair and audit.

## Remaining Blockers

- Phase 1B raw repairs remaining: 5 (`TN:2026`, `ZL:2025`, `ZL:2026`, `ZM:2025`, `ZM:2026`).
- Phase 2 causal repair rows still require later user decision: 66.
- Cleanup remains disabled and blocked until raw repairs are validated, Phase 2 causal rows are decided or explicitly deferred, blockers are zero, and cleanup is explicitly approved.
