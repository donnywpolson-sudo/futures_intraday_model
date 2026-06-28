# Manual Review Classification Refresh

- Generated at UTC: 2026-06-28T12:50:26Z
- Cleanup eligible now: true.
- Dry-run cleanup safe next: true.
- Actual cleanup safe now: false.
- Active blockers remaining: none.
- Manual-review blockers remaining: none.
- Legacy `data/causally_gated_normalized` active approved-base policy has been retired in favor of `data/causal_base_candidates/tier1_rebuild_v1`.
- Remaining legacy causal references are scanner/classifier strings, hygiene guards, test fixtures, docs/help, or report history.

## Protected Keep Paths

- `data/dbn`
- `data/raw`
- `data/raw/ES`
- `data/raw/RTY`
- `data/raw/ZS`
- `data/causal_base_candidates/tier1_rebuild_v1`
- `data/labeled/tier1_rebuild_v1`
- `data/feature_matrices/baseline_tier1_rebuild_v1`
- `reports/data_audit/**`

## Candidate Future Quarantine Plan Only

- `data/causally_gated_normalized`
- `data/raw/_repair_candidates`
- `data/feature_matrices/baseline`
- `data/predictions`
- `data/dbn_sr_parent_candidate`

## Retired Or Reclassified References

- configs/data_manifest.yaml:11 canonical causal pattern -> data/causal_base_candidates/tier1_rebuild_v1/{market}/{year}.parquet
- configs/data_manifest.yaml artifact_policy removed data/causally_gated_normalized/_ active audit prefix
- scripts/audit_data_manifest.py causal coverage artifact label now follows manifest canonical pattern
- scripts/audit_databento_phase5.py approved causal base -> data/causal_base_candidates/tier1_rebuild_v1
- tests/validation/test_refresh_master_data_health_matrix.py fixture canonical causal pattern aligned to rebuilt root
- scripts/audit_databento_phase0.py legacy causal strings -> audit scanner/classification strings
- scripts/audit_databento_phase4.py legacy causal strings -> audit scanner/modeling-root historical classifier strings
- scripts/check_git_hygiene.py data/causally_gated_normalized -> protective hygiene guard
- tests/* data/causally_gated_normalized references -> test fixtures
- reports/data_audit/** data/causally_gated_normalized references -> report/history evidence

## Safety

- No cleanup or dry-run cleanup was run.
- No `data/**` files were modified.
- Actual cleanup remains unsafe without separate explicit approval.
