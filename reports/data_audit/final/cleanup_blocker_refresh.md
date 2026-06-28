# Cleanup Blocker Refresh

- Generated at UTC: 2026-06-28T12:50:26Z
- Cleanup eligible now: true.
- Dry-run cleanup safe next: true.
- Actual cleanup safe now: false.
- Active reference blockers remaining: none.
- Manual-review blockers remaining: none.
- Dry-run cleanup was not run.
- Actual cleanup was not run.

## Candidate Cleanup/Quarantine Paths

- `data/causally_gated_normalized`
- `data/raw/_repair_candidates`
- `data/feature_matrices/baseline`
- `data/predictions`
- `data/dbn_sr_parent_candidate`

## Protected/Unsafe Paths

- `data/dbn`
- `data/raw`
- `data/raw/ES`
- `data/raw/RTY`
- `data/raw/ZS`
- `reports/data_audit/**`

## Reason

The legacy causal root is no longer an active approved causal base. The active tier1 causal policy now points to `data/causal_base_candidates/tier1_rebuild_v1`; remaining old-root references are non-blocking scanner/guard/test/doc/report history. A dry-run is the next safe step only after explicit user approval.
