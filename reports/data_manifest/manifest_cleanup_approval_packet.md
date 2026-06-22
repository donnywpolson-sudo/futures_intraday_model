# Manifest Cleanup Approval Packet

Generated at UTC: 2026-06-22T10:39:26+00:00

## Summary

- Cleanup gate remains blocked.
- No cleanup, move, quarantine, merge, delete, rebuild, redownload, conversion, or data generation was performed.
- Approved `data/dbn/status` manifest policy was applied in `configs/data_manifest.yaml`; cleanup remains disabled.
- This packet converts remaining blocker rows into approval-ready repair and duplicate-handling decisions.

## Current Blocker Counts

- REPAIR_APPROVAL_REQUIRED: 76
- MANIFEST_POLICY_FIX_REQUIRED: 0
- DUPLICATE_MERGE_APPROVAL_REQUIRED: 12

Before approved status policy:

- REPAIR_APPROVAL_REQUIRED: 76
- MANIFEST_POLICY_FIX_REQUIRED: 68
- DUPLICATE_MERGE_APPROVAL_REQUIRED: 12

## Proposed Decision Counts

- APPROVE_REPAIR_PLAN_REQUIRED: 76
- KEEP_BOTH_DO_NOT_TOUCH: 8
- MANIFEST_FIX_RECOMMENDED: 0
- USER_DECISION_REQUIRED: 4
- UNKNOWN_BLOCKING_CLEANUP: 0

## Repair Packet

- `data/causally_gated_normalized/{market}/{year}.parquet`: 66 rows -> APPROVE_REPAIR_PLAN_REQUIRED. See `reports/data_manifest/manifest_repair_plan.csv`.
- `data/raw/{market}/{year}.parquet`: 10 rows -> APPROVE_REPAIR_PLAN_REQUIRED. See `reports/data_manifest/manifest_repair_plan.csv`.

Recommended repair sequencing:

1. Repair the 10 missing canonical raw parquet rows first because phase 2 causal repairs depend on raw inputs for those market-years.
2. Run phase 2 causal repairs only after raw inputs exist and readiness-only checks pass.
3. Keep each repair bounded by market/year and validate with phase-specific checks before broader cleanup evaluation.

## Manifest Policy Packet

- Approved status policy applied: 68 missing `data/dbn/status` rows are now allowed missing pairs under `coverage_policy.missing_pairs.allowed_missing_pairs`.
- Manifest audit command: `python scripts\audit_data_manifest.py`.
- Manifest audit result: `manifest_check issues=179 failures=0`.
- Status missing classification after audit: 68 expected missing, 0 unexpected missing.
- No status DBN repair or redownload was run.

## Duplicate Packet

- 8 duplicate rows -> KEEP_BOTH_DO_NOT_TOUCH. See `reports/data_manifest/manifest_duplicate_policy_proposal.csv`.
- 4 duplicate rows -> USER_DECISION_REQUIRED because cheap metadata found matching file sizes but no checksum/content equivalence proof.
- Cheap metadata did not prove a safe discard/merge path; keeping both avoids data mutation until a user-approved content/provenance review exists.

## Recommended Next Approval Choice

Review the remaining repair approval rows first, then duplicate policy rows. Do not run repair or mutate duplicate data without separate explicit approval.

## Cleanup Gate

- Cleanup remains blocked: true.
- Exact rows still requiring user decision: 4.
- Exact UNKNOWN_BLOCKING_CLEANUP rows: 0.
- Later repair requires approved bounded rebuild/conversion for raw/causal rows: true.
- Later manifest policy edit required for status optional/deferred policy: false.
- Later duplicate data mutation is not recommended in this packet; keep-both policy can be approved without moving data.
