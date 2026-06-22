# Phase 2 Smoke

Status: PASS

Refreshed at UTC: 2026-06-22T10:24:23Z

Scope: manifest-bounded ZN 2023 phase 2 readiness-only preflight. No causal parquet output was written.

Command:
```powershell
python -m scripts.phase2_causal_base.build_causal_base_data --profile manifest_smoke --raw-root data/raw --output-root reports/phase_restart/manifest_phase_2_output --reports-root reports/phase_restart/manifest_phase_2_smoke --profile-config reports/phase_restart/manifest_smoke_alpha_tiered.yaml --raw-alignment-report reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.json --readiness-only --readiness-json-out reports/phase_restart/manifest_phase_2_readiness_summary.json --readiness-md-out reports/phase_restart/manifest_phase_2_readiness_summary.md
```

Result:
- Readiness status: PASS.
- Rerun output: `phase2_readiness_only status=PASS checked=1 blockers=0 json=reports/phase_restart/manifest_phase_2_readiness_summary.json`.
- Expected market-years: 1.
- Selected market-years: 1.
- Checked market-years: 1.
- Pending market-years: 0.
- Blockers: 0.
- Failures: 0.
- Evidence: `reports/phase_restart/manifest_phase_2_readiness_summary.json`.
- Summary: `reports/phase_restart/manifest_phase_2_readiness_summary.md`.

Targeted test:
- `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q`: PASS, 65 passed in 11.98s.

Canonical path resolution:
- Raw input root: `data/raw`.
- Raw alignment evidence: `reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.json`.
- Requested smoke output root: `reports/phase_restart/manifest_phase_2_output`.
- Output root state after readiness-only run: absent; no parquet output was written.

Synthetic-row and eligibility checks:
- Existing canonical causal parquet inspected: `data/causally_gated_normalized/ZN/2023.parquet`.
- Rows: 353549.
- Synthetic rows: 17838 (5.045411%).
- Synthetic rows with nonzero volume: 0.
- Synthetic rows with `causal_valid=true`: 0.
- Synthetic rows with `raw_row_present=true`: 0.
- Current phase 2 implementation gates causal eligibility with `raw_row_present & ~is_synthetic`; there is no separate `observed_row` or `trade_entry_eligible` column in phase 2 output.

Safety checks:
- Phase after phase 2: not run.
- Generated phase 2 outputs: readiness JSON/Markdown only.
- Data mutation check after run: `git status --short -- data` returned no output.
- Requested smoke output root remained absent after readiness-only run: `reports/phase_restart/manifest_phase_2_output`.
