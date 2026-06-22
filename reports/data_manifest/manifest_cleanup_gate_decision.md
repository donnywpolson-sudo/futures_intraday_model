# Manifest Cleanup Gate Decision

Generated at UTC: 2026-06-22T10:39:26+00:00

## Summary

- Cleanup gate decision: BLOCKED.
- Approved `data/dbn/status` manifest policy was applied in `configs/data_manifest.yaml`.
- No cleanup, move, quarantine, merge, delete, redownload, rebuild, conversion, data generation, or DBN source modification was performed.
- Cleanup cannot proceed until approval-required repair decisions are resolved and duplicate keep-both/user-decision policy is explicitly accepted or replaced.

## Current Blocker Counts

- REPAIR_APPROVAL_REQUIRED: 76
- MANIFEST_POLICY_FIX_REQUIRED: 0
- DUPLICATE_MERGE_APPROVAL_REQUIRED: 12

Before this approved policy change:

- REPAIR_APPROVAL_REQUIRED: 76
- MANIFEST_POLICY_FIX_REQUIRED: 68
- DUPLICATE_MERGE_APPROVAL_REQUIRED: 12

## Approval Packet Outputs

- `reports/data_manifest/manifest_cleanup_approval_packet.md`
- `reports/data_manifest/manifest_repair_plan.csv`
- `reports/data_manifest/manifest_policy_fix_proposal.csv`
- `reports/data_manifest/manifest_duplicate_policy_proposal.csv`

## Proposed Decision Counts

- APPROVE_REPAIR_PLAN_REQUIRED: 76
- KEEP_BOTH_DO_NOT_TOUCH: 8
- MANIFEST_FIX_RECOMMENDED: 0
- USER_DECISION_REQUIRED: 4
- UNKNOWN_BLOCKING_CLEANUP: 0

## Required Count Checks

- Manifest audit command: `python scripts\audit_data_manifest.py`.
- Manifest audit result: `manifest_check issues=179 failures=0`.
- `data/dbn/status` missing rows changed from 68 unexpected missing to 68 expected missing.
- Unexpected missing rows now remain only for 10 raw parquet pairs and 66 causal parquet pairs.
- REPAIR_REQUIRED_BEFORE_CLEANUP count is now 0: true.
- DUPLICATE_POLICY_DEFERRED count is now 0: true.
- STALE_OR_UNKNOWN_REVIEW_REQUIRED count is now 0: true.
- UNKNOWN_BLOCKING_CLEANUP remains: false (0).
- Exact rows still requiring user decision: 4.
- Cleanup remains blocked: true.
- Explicit approval needed before repair or duplicate policy mutation: true.

## Recommended Next Approval Choice

Review the remaining 76 repair approval rows and 12 duplicate policy rows. Do not run repair, cleanup, merge, quarantine, or delete without separate explicit approval.

## Explicit No-Action Statement

No cleanup/move/quarantine/merge/delete/rebuild/redownload/conversion/data generation was performed in this packet. No DBN source files were modified.
