# Phase 1C Smoke

Status: PASS

Scope: manifest-bounded ZN 2023 raw/DBN alignment audit against canonical DBN and raw parquet roots. The smoke profile is report-local and resolves to `manifest_smoke_zn_2023`.

Command:
```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/manifest_smoke_alpha_tiered.yaml --profile manifest_smoke --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.json --md-out reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.md
```

Result:
- Alignment status: PASS.
- Expected market-years: 1.
- Raw market-years: 1.
- OHLCV DBN market-years: 1.
- Definition DBN market-years: 1.
- Needs Phase 1B conversion: 0.
- Raw-only market-years: 0.
- Invalid manifests: 0.
- Source hash mismatches: 0.
- Definition join status: checked.
- Definition join mismatches: 0.
- Evidence: `reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.json`.
- Summary: `reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.md`.

Safety checks:
- `--expected-only` bounded the audit to the profile/discovery expected market-years instead of all files under the roots.
- Phase 1C did not generate synthetic rows; synthetic-row diagnostics are checked in the phase 2 smoke report.
- Data mutation check after run: `git status --short -- data` returned no output.
