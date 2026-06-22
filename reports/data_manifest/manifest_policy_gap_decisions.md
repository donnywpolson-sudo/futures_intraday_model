# Manifest Policy Gap Decisions

Generated at UTC: 2026-06-22T10:01:44+00:00

## Decision

- Cleanup gate: BLOCKED.
- Cleanup/quarantine/move/delete was not run.
- Data files were not moved, deleted, redownloaded, generated, or modified by this classification pass.
- Canonical contract: `configs/data_manifest.yaml`.

## Previous Blocker Counts

- REPAIR_REQUIRED_BEFORE_CLEANUP: 144
- DUPLICATE_POLICY_DEFERRED: 12
- STALE_OR_UNKNOWN_REVIEW_REQUIRED: 2

## Updated Counts By Final Decision

- DUPLICATE_MERGE_APPROVAL_REQUIRED: 12
- EXPLICITLY_DEFERRED_POLICY_GAP: 23
- MANIFEST_POLICY_FIX_REQUIRED: 68
- REPAIR_APPROVAL_REQUIRED: 76
- SAFE_TO_DEFER_DO_NOT_TOUCH: 2

## Missing Expected Data Decisions

- `data/causally_gated_normalized/{market}/{year}.parquet` -> REPAIR_APPROVAL_REQUIRED: 66 pairs. KE: 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026; SR1: 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026; TN: 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026; ZL: 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026; ZM: 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026.
- `data/dbn/status` -> MANIFEST_POLICY_FIX_REQUIRED: 68 pairs. 6A: 2014; 6B: 2014; 6C: 2010, 2011, 2014; 6E: 2012, 2013, 2014; 6J: 2010, 2014; 6M: 2013, 2014; ES: 2014; GC: 2010, 2014; HE: 2013; HG: 2011, 2014; HO: 2010, 2011, 2012, 2013; KE: 2013, 2014; LE: 2010, 2011, 2012, 2013; NQ: 2012, 2014; RB: 2010, 2011, 2012, 2013, 2014; SI: 2014; UB: 2010, 2011, 2012; YM: 2011, 2012, 2013, 2014; ZB: 2010, 2011, 2012; ZC: 2010, 2014; ZF: 2010, 2011, 2012; ZL: 2012, 2013; ZM: 2011, 2012, 2013, 2014; ZN: 2010, 2011, 2012; ZS: 2011, 2013; ZT: 2010, 2011, 2012, 2013, 2014; ZW: 2013.
- `data/raw/{market}/{year}.parquet` -> REPAIR_APPROVAL_REQUIRED: 10 pairs. KE: 2025, 2026; SR1: 2025, 2026; TN: 2025, 2026; ZL: 2025, 2026; ZM: 2025, 2026.

## Duplicate Decisions

- `data/dbn/definition` -> DUPLICATE_MERGE_APPROVAL_REQUIRED: 1 pairs (6M:2026). Evidence paths: `data/dbn/definition/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/definition/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/ohlcv_1d` -> DUPLICATE_MERGE_APPROVAL_REQUIRED: 1 pairs (6M:2026). Evidence paths: `data/dbn/ohlcv_1d/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1d/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/ohlcv_1h` -> DUPLICATE_MERGE_APPROVAL_REQUIRED: 1 pairs (6M:2026). Evidence paths: `data/dbn/ohlcv_1h/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1h/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/ohlcv_1m` -> DUPLICATE_MERGE_APPROVAL_REQUIRED: 1 pairs (6M:2026). Evidence paths: `data/dbn/ohlcv_1m/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1m/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/ohlcv_1s` -> DUPLICATE_MERGE_APPROVAL_REQUIRED: 1 pairs (6M:2026). Evidence paths: `data/dbn/ohlcv_1s/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1s/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/statistics` -> DUPLICATE_MERGE_APPROVAL_REQUIRED: 3 pairs (6M:2026, RTY:2017, SR3:2018). Evidence paths: `data/dbn/statistics/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/statistics/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/status` -> DUPLICATE_MERGE_APPROVAL_REQUIRED: 3 pairs (6M:2026, RTY:2017, SR3:2018). Evidence paths: `data/dbn/status/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/status/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/trades` -> DUPLICATE_MERGE_APPROVAL_REQUIRED: 1 pairs (6M:2026). Evidence paths: `data/dbn/trades/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/trades/6M/2026/2026-06-12_2026-06-13.dbn.zst`.

## Repair-Candidate Decisions

- `data/raw/_repair_candidates` -> SAFE_TO_DEFER_DO_NOT_TOUCH: exists=True; files=24; dirs=3; bytes=48287054; no-underscore path data/raw_repair_candidates exists=False; Lineage classifies as STALE_OR_UNKNOWN, not canonical top-level data/raw; text references are reports/handoff/manifest only, with no scripts/tests references found.
- `data/causally_gated_normalized/_repair_candidates` -> SAFE_TO_DEFER_DO_NOT_TOUCH: exists=True; files=2; dirs=1; bytes=14492021; no-underscore path data/causally_gated_normalized_repair_candidates exists=False; Lineage classifies as STALE_OR_UNKNOWN, not canonical top-level data/causally_gated_normalized; text references are reports/handoff/manifest only, with no scripts/tests references found.

## Cleanup Gate

- REPAIR_REQUIRED_BEFORE_CLEANUP count is now 0: true.
- DUPLICATE_POLICY_DEFERRED count is now 0: true.
- STALE_OR_UNKNOWN_REVIEW_REQUIRED count is now 0: true.
- UNKNOWN_BLOCKING_CLEANUP remains: false (0).
- Approval-required actions remain: true (156).
- Cleanup remains blocked: true.

## Next Gate

1. Approve bounded repair/generation or explicit deferral for `REPAIR_APPROVAL_REQUIRED` rows.
2. Approve a manifest policy change or status repair plan for `MANIFEST_POLICY_FIX_REQUIRED` rows.
3. Approve duplicate content review plus merge/quarantine/keep policy for `DUPLICATE_MERGE_APPROVAL_REQUIRED` rows.
