# Phase Restart Summary

Generated at UTC: 2026-06-22T09:32:47Z

## Scope

- Contract: `configs/data_manifest.yaml`.
- Smoke subset: ZN 2023, selected because it is present in canonical DBN/raw/causal roots and was not avoided despite synthetic rows around 5%.
- Report-local smoke profile: `reports/phase_restart/manifest_smoke_alpha_tiered.yaml`.
- Phases run: 1A dry-run, 1B existing-output conversion check, 1C expected-only alignment audit, phase 2 readiness-only preflight.
- Phases after phase 2: not run.
- Cleanup/quarantine/redownload/full rebuild: not run.

## Results

| Phase | Status | Evidence |
|---|---|---|
| 1A | PASS | `reports/phase_restart/manifest_phase_1a_smoke/databento_download_plan_dry_run.json` |
| 1B | PASS | `reports/phase_restart/manifest_phase_1b_smoke/databento_convert_results.json` |
| 1C | PASS | `reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.json` |
| 2 | PASS | `reports/phase_restart/manifest_phase_2_readiness_summary.json` |

## Canonical Path Resolution

- Phase 1A planned DBN archive output: `data/dbn/ohlcv_1m/ZN/2023/2023-01-01_2024-01-01.dbn.zst`.
- Phase 1B consumed canonical DBN input: `data/dbn/ohlcv_1m/ZN/2023/2023-01-01_2024-01-01.dbn.zst`.
- Phase 1B reused canonical raw output: `data/raw/ZN/2023.parquet`.
- Phase 1C validated canonical DBN root `data/dbn` against canonical raw root `data/raw`.
- Phase 2 readiness consumed canonical raw root `data/raw` and did not write causal outputs.

## Safety

- `data/` status after smoke commands: `git status --short -- data` returned no output.
- DBN source modification: no evidence.
- Deprecated top-level data folders created: no evidence.
- Generated smoke evidence stayed under `reports/phase_restart`.
- Cleanup gate remains blocked by manifest policy gaps from the prior manifest check; this smoke run did not attempt cleanup.

## Notes

- Synthetic rows remain diagnostic for this bounded smoke. Existing ZN 2023 causal parquet has 17838 synthetic rows, all with zero volume, none causal-valid, and none marked raw-row-present.
- Phase 2 currently uses `raw_row_present & ~is_synthetic` for observed causal eligibility semantics; no separate `observed_row` output column exists.
