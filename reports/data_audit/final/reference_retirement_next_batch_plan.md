# Reference Retirement Next Batch Plan

- Generated at UTC: 2026-06-28T12:50:26Z
- Reference-retirement blockers remaining: none.
- Recommended next action: dry-run cleanup approval plan.
- Do not run dry-run cleanup without separate explicit user approval.
- Do not run actual cleanup without separate explicit user approval after dry-run review.

## Dry-Run Candidate Scope

- `data/causally_gated_normalized`
- `data/raw/_repair_candidates`
- `data/feature_matrices/baseline`
- `data/predictions`
- `data/dbn_sr_parent_candidate`

## Excluded Protected Scope

- `data/dbn`
- `data/raw`
- `data/raw/ES`
- `data/raw/RTY`
- `data/raw/ZS`
- `data/causal_base_candidates/tier1_rebuild_v1`
- `data/labeled/tier1_rebuild_v1`
- `data/feature_matrices/baseline_tier1_rebuild_v1`
- `reports/data_audit/**`

## Required Before Any Dry-Run

- Confirm the committed worktree is clean.
- Confirm candidate paths still exclude protected keep paths.
- Confirm the dry-run command is review-only and writes no data mutations.
- Obtain explicit user approval for dry-run cleanup.
