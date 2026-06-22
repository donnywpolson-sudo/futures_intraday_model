# Phase Restart Summary

Generated at UTC: 2026-06-22T10:24:23Z

## Scope

- Contract: `configs/data_manifest.yaml`.
- Smoke subset: ZN 2023, selected because it is present in canonical DBN/raw/causal roots and was not avoided despite synthetic rows around 5%.
- Report-local smoke profile: `reports/phase_restart/manifest_smoke_alpha_tiered.yaml`.
- Phases run: 1A dry-run and 1B existing-output conversion check from prior committed evidence; 1C expected-only alignment audit and phase 2 readiness-only preflight refreshed at 2026-06-22T10:24:23Z.
- Phases after phase 2: not run.
- Cleanup/quarantine/redownload/full rebuild: not run.

## Results

| Phase | Status | Evidence |
|---|---|---|
| 1A | PASS | `reports/phase_restart/manifest_phase_1a_smoke/databento_download_plan_dry_run.json` |
| 1B | PASS | `reports/phase_restart/manifest_phase_1b_smoke/databento_convert_results.json` |
| 1C | PASS | `reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.json` |
| 2 | PASS | `reports/phase_restart/manifest_phase_2_readiness_summary.json` |

## Targeted Tests

- `python -m pytest tests\validation\test_audit_raw_dbn_alignment.py -q`: PASS, 25 passed in 3.44s.
- `python -m pytest tests\phase2_causal_base\test_build_causal_base_data.py -q`: PASS, 65 passed in 11.98s.

## Change Classification

- `scripts\phase1C_validate\audit_raw_dbn_alignment.py`: smoke flag/path validation. Current committed change adds default-off `--expected-only`; production default remains all-root audit.
- `scripts\phase2_causal_base\build_causal_base_data.py`: smoke flag/path validation. Current committed change adds default-off `--readiness-only`; production default still writes causal outputs only after readiness passes.
- `tests\validation\test_audit_raw_dbn_alignment.py`: test coverage for expected-only filtering.
- `tests\phase2_causal_base\test_build_causal_base_data.py`: test coverage for readiness-only reports and no causal output writes.
- Unsafe or ambiguous current code change: none found in the clean worktree review.

## Refreshed Smoke Commands

Phase 1C:
```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/manifest_smoke_alpha_tiered.yaml --profile manifest_smoke --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.json --md-out reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.md
```

Phase 2:
```powershell
python -m scripts.phase2_causal_base.build_causal_base_data --profile manifest_smoke --raw-root data/raw --output-root reports/phase_restart/manifest_phase_2_output --reports-root reports/phase_restart/manifest_phase_2_smoke --profile-config reports/phase_restart/manifest_smoke_alpha_tiered.yaml --raw-alignment-report reports/phase_restart/manifest_phase_1c_raw_dbn_alignment.json --readiness-only --readiness-json-out reports/phase_restart/manifest_phase_2_readiness_summary.json --readiness-md-out reports/phase_restart/manifest_phase_2_readiness_summary.md
```

Rerun results:
- Phase 1C: PASS, `expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.
- Phase 2: PASS, `checked=1 blockers=0`.

## Canonical Path Resolution

- Phase 1A planned DBN archive output: `data/dbn/ohlcv_1m/ZN/2023/2023-01-01_2024-01-01.dbn.zst`.
- Phase 1B consumed canonical DBN input: `data/dbn/ohlcv_1m/ZN/2023/2023-01-01_2024-01-01.dbn.zst`.
- Phase 1B reused canonical raw output: `data/raw/ZN/2023.parquet`.
- Phase 1C validated canonical DBN root `data/dbn` against canonical raw root `data/raw`.
- Phase 2 readiness consumed canonical raw root `data/raw` and did not write causal outputs.
- Canonical paths are present in `configs/data_manifest.yaml`: `dbn_root: data/dbn`, `raw_parquet_pattern: data/raw/{market}/{year}.parquet`, and `causal_parquet_pattern: data/causally_gated_normalized/{market}/{year}.parquet`.

## Safety

- `data/` status after smoke commands: `git status --short -- data` returned no output.
- DBN source modification: no recent DBN source file writes were found by the scoped 10-minute probe.
- Deprecated top-level data folders created: none found for `data/raw_repair_candidates`, `data/causally_gated_normalized_repair_candidates`, `data/raw_repair`, `data/causal_repair`, or `data/phase2_smoke_output`.
- Generated smoke evidence stayed under `reports/phase_restart`.
- Generated data artifacts staged: none.
- Cleanup/quarantine/move actions: not run.

## Manifest Policy Gaps

- Repair required before cleanup: 144 unexpected missing pairs in `reports/data_manifest/manifest_coverage_check.csv` (10 raw parquet pairs, 66 causal parquet pairs, 68 DBN status pairs).
- Explicitly deferred policy gap: 23 allowed extra DBN pairs are encoded in `configs/data_manifest.yaml` with cleanup disabled.
- Duplicate/deprecated path deferred: 12 known duplicate DBN market-year pairs are policy-deferred review-before-cleanup.
- UNKNOWN requiring review: `data/raw/_repair_candidates` and `data/causally_gated_normalized/_repair_candidates` remain `STALE_OR_UNKNOWN` in `reports/data_manifest/manifest_coverage_summary.md`.
- Cleanup gate decision: cleanup remains blocked and cannot be evaluated for approval until missing-pair repairs or deferrals, duplicate review, and `STALE_OR_UNKNOWN` review are resolved.

## Notes

- Synthetic rows remain diagnostic for this bounded smoke. Existing ZN 2023 causal parquet has 17838 synthetic rows, all with zero volume, none causal-valid, and none marked raw-row-present.
- Phase 2 currently uses `raw_row_present & ~is_synthetic` for observed causal eligibility semantics; no separate `observed_row` output column exists.
