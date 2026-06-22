# Manifest Cleanup Gate Decision

Generated at UTC: 2026-06-22T10:01:44+00:00

## Summary

- Cleanup gate decision: BLOCKED.
- No cleanup, move, quarantine, delete, redownload, rebuild, data generation, or DBN source modification was performed.
- Cleanup cannot proceed until approval-required repair, manifest-policy, and duplicate decisions are resolved.

## Previous Blocker Counts

- REPAIR_REQUIRED_BEFORE_CLEANUP: 144
- DUPLICATE_POLICY_DEFERRED: 12
- STALE_OR_UNKNOWN_REVIEW_REQUIRED: 2

## Updated Final Decision Counts

- DUPLICATE_MERGE_APPROVAL_REQUIRED: 12
- EXPLICITLY_DEFERRED_POLICY_GAP: 23
- MANIFEST_POLICY_FIX_REQUIRED: 68
- REPAIR_APPROVAL_REQUIRED: 76
- SAFE_TO_DEFER_DO_NOT_TOUCH: 2

## Required Count Checks

- REPAIR_REQUIRED_BEFORE_CLEANUP count is now 0: true.
- DUPLICATE_POLICY_DEFERRED count is now 0: true.
- STALE_OR_UNKNOWN_REVIEW_REQUIRED count is now 0: true.
- UNKNOWN_BLOCKING_CLEANUP remains: false (0).
- Cleanup remains blocked: true.
- Explicit approval needed: true (156 rows).

## Approval-Required Actions

- REPAIR_APPROVAL_REQUIRED: 76 rows require approved bounded conversion/build/download/repair or explicit deferral before cleanup evaluation.
- MANIFEST_POLICY_FIX_REQUIRED: 68 rows require approval to change `configs/data_manifest.yaml` status-coverage policy or approve status repair.
- DUPLICATE_MERGE_APPROVAL_REQUIRED: 12 rows require approved duplicate content review and merge/quarantine/keep policy.

## Duplicate Paths

- `data/dbn/ohlcv_1m` 6M:2026: `data/dbn/ohlcv_1m/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1m/6M/2026/2026-06-12_2026-06-13.dbn.zst`
- `data/dbn/ohlcv_1s` 6M:2026: `data/dbn/ohlcv_1s/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1s/6M/2026/2026-06-12_2026-06-13.dbn.zst`
- `data/dbn/ohlcv_1h` 6M:2026: `data/dbn/ohlcv_1h/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1h/6M/2026/2026-06-12_2026-06-13.dbn.zst`
- `data/dbn/ohlcv_1d` 6M:2026: `data/dbn/ohlcv_1d/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1d/6M/2026/2026-06-12_2026-06-13.dbn.zst`
- `data/dbn/statistics` 6M:2026: `data/dbn/statistics/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/statistics/6M/2026/2026-06-12_2026-06-13.dbn.zst`
- `data/dbn/statistics` RTY:2017: `data/dbn/statistics/RTY/2017/2017-01-01_2018-01-01.dbn.zst;data/dbn/statistics/RTY/2017/2017-06-05_2018-01-01.dbn.zst`
- `data/dbn/statistics` SR3:2018: `data/dbn/statistics/SR3/2018/2018-01-01_2019-01-01.dbn.zst;data/dbn/statistics/SR3/2018/2018-04-23_2019-01-01.dbn.zst`
- `data/dbn/status` 6M:2026: `data/dbn/status/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/status/6M/2026/2026-06-12_2026-06-13.dbn.zst`
- `data/dbn/status` RTY:2017: `data/dbn/status/RTY/2017/2017-01-01_2018-01-01.dbn.zst;data/dbn/status/RTY/2017/2017-06-05_2018-01-01.dbn.zst`
- `data/dbn/status` SR3:2018: `data/dbn/status/SR3/2018/2018-01-01_2019-01-01.dbn.zst;data/dbn/status/SR3/2018/2018-04-23_2019-01-01.dbn.zst`
- `data/dbn/definition` 6M:2026: `data/dbn/definition/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/definition/6M/2026/2026-06-12_2026-06-13.dbn.zst`
- `data/dbn/trades` 6M:2026: `data/dbn/trades/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/trades/6M/2026/2026-06-12_2026-06-13.dbn.zst`

## Repair-Candidate Paths

- `data/raw/_repair_candidates` -> SAFE_TO_DEFER_DO_NOT_TOUCH: exists=True; files=24; dirs=3; bytes=48287054; no-underscore path data/raw_repair_candidates exists=False; Lineage classifies as STALE_OR_UNKNOWN, not canonical top-level data/raw; text references are reports/handoff/manifest only, with no scripts/tests references found.
- `data/causally_gated_normalized/_repair_candidates` -> SAFE_TO_DEFER_DO_NOT_TOUCH: exists=True; files=2; dirs=1; bytes=14492021; no-underscore path data/causally_gated_normalized_repair_candidates exists=False; Lineage classifies as STALE_OR_UNKNOWN, not canonical top-level data/causally_gated_normalized; text references are reports/handoff/manifest only, with no scripts/tests references found.

## Proposed Manifest Policy Work

- Do not edit `configs/data_manifest.yaml` without explicit approval.
- Proposed policy decision needing approval: decide whether `data/dbn/status` should remain complete required coverage or become optional/deferred for the Phase 1A/1B/1C/2 restart cleanup gate.
