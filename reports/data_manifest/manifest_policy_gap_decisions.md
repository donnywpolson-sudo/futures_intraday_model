# Manifest Policy Gap Decisions

Generated at UTC: 2026-06-22T09:55:38+00:00

## Decision

- Cleanup gate: BLOCKED.
- Cleanup/quarantine was not run.
- Data files were not moved, deleted, redownloaded, or modified by this classification pass.
- Canonical contract: `configs/data_manifest.yaml`.

## Counts By Classification

- REPAIR_REQUIRED_BEFORE_CLEANUP: 144
- EXPLICITLY_DEFERRED_POLICY_GAP: 23
- DUPLICATE_POLICY_DEFERRED: 12
- STALE_OR_UNKNOWN_REVIEW_REQUIRED: 2
- UNKNOWN_BLOCKING_CLEANUP: 0

## Missing Expected Data

- `data/causally_gated_normalized/{market}/{year}.parquet` (phase2_output, phase2_causal_base_parquet): 66 pairs. KE: 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026; SR1: 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026; TN: 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026; ZL: 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026; ZM: 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026.
- `data/dbn/status` (phase1A_source_optional_enrichment, status): 68 pairs. 6A: 2014; 6B: 2014; 6C: 2010, 2011, 2014; 6E: 2012, 2013, 2014; 6J: 2010, 2014; 6M: 2013, 2014; ES: 2014; GC: 2010, 2014; HE: 2013; HG: 2011, 2014; HO: 2010, 2011, 2012, 2013; KE: 2013, 2014; LE: 2010, 2011, 2012, 2013; NQ: 2012, 2014; RB: 2010, 2011, 2012, 2013, 2014; SI: 2014; UB: 2010, 2011, 2012; YM: 2011, 2012, 2013, 2014; ZB: 2010, 2011, 2012; ZC: 2010, 2014; ZF: 2010, 2011, 2012; ZL: 2012, 2013; ZM: 2011, 2012, 2013, 2014; ZN: 2010, 2011, 2012; ZS: 2011, 2013; ZT: 2010, 2011, 2012, 2013, 2014; ZW: 2013.
- `data/raw/{market}/{year}.parquet` (phase1B_output_phase2_input, phase1b_raw_parquet): 10 pairs. KE: 2025, 2026; SR1: 2025, 2026; TN: 2025, 2026; ZL: 2025, 2026; ZM: 2025, 2026.

## Explicitly Deferred Policy Gaps

- `data/dbn/definition`: 5 allowed extra pairs. TN:2010, TN:2011, TN:2012, ZL:2010, ZM:2010.
- `data/dbn/ohlcv_1m`: 5 allowed extra pairs. TN:2010, TN:2011, TN:2012, ZL:2010, ZM:2010.
- `data/dbn/ohlcv_1s`: 5 allowed extra pairs. TN:2010, TN:2011, TN:2012, ZL:2010, ZM:2010.
- `data/dbn/statistics`: 5 allowed extra pairs. TN:2010, TN:2011, TN:2012, ZL:2010, ZM:2010.
- `data/dbn/status`: 3 allowed extra pairs. TN:2010, TN:2011, TN:2012.

## Duplicate Policy Deferred

- `data/dbn/definition`: 1 known duplicate pairs. 6M:2026. Evidence paths: `data/dbn/definition/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/definition/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/ohlcv_1d`: 1 known duplicate pairs. 6M:2026. Evidence paths: `data/dbn/ohlcv_1d/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1d/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/ohlcv_1h`: 1 known duplicate pairs. 6M:2026. Evidence paths: `data/dbn/ohlcv_1h/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1h/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/ohlcv_1m`: 1 known duplicate pairs. 6M:2026. Evidence paths: `data/dbn/ohlcv_1m/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1m/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/ohlcv_1s`: 1 known duplicate pairs. 6M:2026. Evidence paths: `data/dbn/ohlcv_1s/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/ohlcv_1s/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/statistics`: 3 known duplicate pairs. 6M:2026, RTY:2017, SR3:2018. Evidence paths: `data/dbn/statistics/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/statistics/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/status`: 3 known duplicate pairs. 6M:2026, RTY:2017, SR3:2018. Evidence paths: `data/dbn/status/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/status/6M/2026/2026-06-12_2026-06-13.dbn.zst`.
- `data/dbn/trades`: 1 known duplicate pairs. 6M:2026. Evidence paths: `data/dbn/trades/6M/2026/2026-01-01_2026-06-13.dbn.zst;data/dbn/trades/6M/2026/2026-06-12_2026-06-13.dbn.zst`.

## Stale Or Unknown Repair-Candidate Paths

- `data/raw/_repair_candidates`: cleanup_blocked_unknown_review_required. Referenced by manifest exclusion, lineage reports, handoff, and phase_restart repair-candidate reports; targeted search found no scripts/tests references.
- `data/causally_gated_normalized/_repair_candidates`: cleanup_blocked_unknown_review_required. Referenced by manifest exclusion, lineage reports, handoff, and phase_restart repair-candidate reports; targeted search found no scripts/tests references.

## Next Gate

1. Repair or explicitly defer the 144 missing expected pairs under the manifest contract.
2. Review the 12 known duplicate DBN market-year groups before any duplicate cleanup policy is considered.
3. Review the 2 `STALE_OR_UNKNOWN` repair-candidate roots and document whether they are safe to defer, repair-required, or still unknown.
