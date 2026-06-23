# Master Data Health Matrix

- Generated at UTC: 2026-06-23T02:42:17Z
- Scope: report-only refreshed evidence matrix for every expected market/year from `configs/data_manifest.yaml`.
- Sources used: current manifest coverage, latest raw optional-schema audit, Phase 2 build/exclusion decisions, and existing matrix metadata.
- Safety: no repair, Phase 2 build, cleanup, redownload, move, merge, quarantine, delete, or DBN source modification was run by this refresh.
- Cleanup remains disabled and should stay disabled until blockers are zero and cleanup is explicitly approved.

## Counts

- Expected market/year rows: 527.
- `OK_SOURCE_PRESENT`: 45.
- `POLICY_REVIEW_REQUIRED`: 473.
- `EXCLUDED_FROM_PHASE2`: 9.
- `UNKNOWN_REVIEW_REQUIRED`: 0.
- Rows needing drilldown before trust/build: 0 unknown + 9 excluded.
- Phase 2 decision rows: 66.
- Current build plan accepted rows: 57; deferred rows: 9.
- Accepted rows still requiring pre-build raw evidence: 0.

## Schema Presence

- `raw_parquet_present`: 527/527.
- `causal_parquet_present`: 461/527.
- `ohlcv_1m_dbn_present`: 527/527.
- `definition_dbn_present`: 527/527.
- `statistics_dbn_present`: 527/527.
- `status_dbn_present`: 460/527.

## Raw Optional-Schema Audit

- Status: `PASS` from `reports/raw_readiness/raw_enriched_optional_schema_audit.json`.
- Files checked: 527; rows checked: 130074125.
- `duplicate_key_row_count`: 0.
- `file_failure_count`: 0.
- `missing_source_file_count`: 0.
- `missing_statistics_archive_market_year_count`: 0.
- `missing_status_archive_market_year_count`: 67.
- `row_count`: 130074125.
- `schema_failure_count`: 0.
- `source_hash_mismatch_count`: 0.
- `statistics_archive_market_year_count`: 527.
- `statistics_failure_count`: 0.
- `status_archive_market_year_count`: 460.
- `status_failure_count`: 0.

## Unknown Drilldown

- Current unknown rows: 0.
- raw optional-schema audit failed: 0.

| pair | primary_blocker | raw_audit_status | raw_failure_summary | latest_phase2_decision |
| --- | --- | --- | --- | --- |
| None |  |  |  |  |

## Cleared Since Prior Snapshot

- `SR3:2019`, `SR3:2020`, `SR3:2021`, `SR3:2022`, `SR3:2023`, `SR3:2024`, `SR1:2018`, `SR1:2019`, `SR1:2020`, `SR1:2021`, `SR1:2022`, `SR1:2023`, `SR1:2024`, `SR1:2025`, `SR1:2026`, `TN:2025`, `TN:2026`, `ZL:2025`, `ZL:2026`, `ZM:2025`, `ZM:2026`, `KE:2025`, and `KE:2026` now pass the latest raw optional-schema audit and are no longer `UNKNOWN_REVIEW_REQUIRED`.
- These rows are still not automatically model-ready; rows with missing/stale optional enrichment, missing causal outputs, or Phase 2 decisions remain `POLICY_REVIEW_REQUIRED`.

## Excluded Drilldown

| pair | latest_phase2_decision | primary_blocker | phase2_top_blocker | decision_conflict |
| --- | --- | --- | --- | --- |
| ZL:2012 | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | synthetic threshold breached: rows_pct=25.533946 max_gap_minutes=41 | False |
| ZL:2013 | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | roll maturity sequence not monotonic: backsteps=1 | False |
| ZM:2011 | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | synthetic threshold breached: rows_pct=46.647299 max_gap_minutes=80 | False |
| ZM:2012 | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | synthetic threshold breached: rows_pct=34.603054 max_gap_minutes=53 | False |
| ZM:2013 | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | roll maturity sequence not monotonic: backsteps=2 | False |
| ZM:2014 | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | DEFERRED_EXCLUDED_FROM_PHASE2_BUILD | synthetic threshold breached: rows_pct=33.824621 max_gap_minutes=71 | False |
| KE:2013 | KE_2013_EXCLUDED_STATUS_SOURCE_PARTIAL_STUB | KE_2013_EXCLUDED_STATUS_SOURCE_PARTIAL_STUB | synthetic threshold breached: rows_pct=59.633118 max_gap_minutes=105 | False |
| KE:2014 | KE_2014_EXCLUDED_NO_CAUSAL_STATUS_SOURCE | KE_2014_EXCLUDED_NO_CAUSAL_STATUS_SOURCE | roll maturity sequence not monotonic: backsteps=4 | False |
| KE:2015 | KE_2015_EXCLUDED_STATUS_SOURCE_INCOMPLETE | KE_2015_EXCLUDED_STATUS_SOURCE_INCOMPLETE | synthetic threshold breached: rows_pct=60.032591 max_gap_minutes=120 | True |

## Policy Review Summary

Rows in this class have enough source/raw evidence to avoid unknown classification, but still have optional status/statistics gaps, Phase 2 readiness/build decisions, missing causal outputs, accepted exceptions, or duplicate/extra manifest policy rows. They are not automatically clean for modeling or cleanup.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No data file was moved, deleted, merged, quarantined, rebuilt, or redownloaded.
- DBN source files were not modified by this refresh.
