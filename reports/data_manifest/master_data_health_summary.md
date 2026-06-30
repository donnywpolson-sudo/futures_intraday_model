# Master Data Health Matrix

- Generated at UTC: 2026-06-30T14:57:23Z
- Scope: report-only master data health refresh from existing local evidence.
- Safety: no repair, Phase 2 build, cleanup, redownload, move, merge, quarantine, delete, or DBN/source modification was run by this refresh.

## Raw/Source Completeness

- Expected market/year rows: 527.
- `OK_SOURCE_PRESENT`: 45.
- `POLICY_REVIEW_REQUIRED`: 473.
- `EXCLUDED_FROM_PHASE2`: 9.
- `UNKNOWN_REVIEW_REQUIRED`: 0.
- `raw_parquet_present`: 527/527.
- `ohlcv_1m_dbn_present`: 527/527.
- `definition_dbn_present`: 527/527.
- `statistics_dbn_present`: 527/527.
- `status_dbn_present`: 460/527; missing 67 rows.

## Current Canonical Phase 2 Causal Coverage

- `causal_parquet_present`: 460/527.
- Missing canonical causal parquet rows: 67.
- Current build plan accepted rows: 57; deferred rows: 9.
- Accepted rows still requiring pre-build raw evidence: 0.

## Approved Phase 1-2 Scope

- Approved PASS rows: 11.
- Approved PASS rows with current canonical causal parquet: 11/11.
- Fail-closed rows with decision packet: 28.
- Unresolved rows: 0.
- PASS rows: SR1:2020, SR3:2020, KE:2019, KE:2021, KE:2023, KE:2024, HE:2016, HE:2019, HE:2020, LE:2016, LE:2020.
- Fail-closed rows: ZC:2019, ZC:2020, ZC:2021, ZC:2022, ZC:2023, ZC:2024, ZL:2019, ZL:2020, ZL:2021, ZL:2022, ZL:2023, ZM:2019, ZM:2020, ZM:2021, ZM:2022, ZM:2023, ZM:2024, ZS:2019, ZS:2020, ZS:2021, ZS:2022, ZS:2023, ZS:2024, ZW:2019, ZW:2020, ZW:2022, ZW:2023, ZW:2024.
- Unresolved rows: None.

## Raw Optional-Schema Audit

- Status: `PASS` from `reports/raw_readiness/raw_enriched_optional_schema_audit.json`.
- Files checked: 530; rows checked: 130086009.
- `duplicate_key_row_count`: 0.
- `file_failure_count`: 0.
- `missing_source_file_count`: 0.
- `missing_statistics_archive_market_year_count`: 0.
- `missing_status_archive_market_year_count`: 0.
- `required_schema_exception_failure_count`: 0.
- `row_count`: 130086009.
- `schema_failure_count`: 0.
- `source_hash_mismatch_count`: 0.
- `statistics_archive_market_year_count`: 530.
- `statistics_failure_count`: 0.
- `status_archive_market_year_count`: 529.
- `status_failure_count`: 0.
- `status_required_schema_exception_count`: 1.

## Stale/Conflicting Prior Matrix Evidence

- Prior matrix generated at UTC: 2026-06-23T02:42:17Z.
- Prior `causal_parquet_present`: 461/527.
- Current canonical `causal_parquet_present`: 460/527.
- Correction: -1 rows versus the prior matrix count.
- Matrix row-level `status_dbn_present`: 460/527; current raw optional audit `status_archive_market_year_count`: 529 and `missing_status_archive_market_year_count`: 0.
- Status DBN counts are separate evidence scopes and are preserved rather than merged.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No data file was moved, deleted, merged, quarantined, rebuilt, or redownloaded.
- DBN source files were not modified by this refresh.
