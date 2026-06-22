# Master Data Health Matrix

- Generated at UTC: 2026-06-22T23:25:02Z
- Scope: report-only evidence matrix for every expected market/year from `configs/data_manifest.yaml`.
- Sources used: `configs/data_manifest.yaml`, manifest coverage, raw optional-schema audit, Phase 2 readiness/decision reports, and cheap file-presence checks only.
- Safety: no repair, Phase 2 build, cleanup, redownload, move, merge, quarantine, delete, or DBN source modification was run by this report generation.
- Cleanup remains disabled and should stay disabled until blockers are zero and cleanup is explicitly approved.

## Counts

- Expected market/year rows: 527.
- `OK_SOURCE_PRESENT`: 45.
- `POLICY_REVIEW_REQUIRED`: 450.
- `EXCLUDED_FROM_PHASE2`: 9.
- `UNKNOWN_REVIEW_REQUIRED`: 23.
- Rows needing drilldown before trust/build: 23 unknown + 9 excluded.
- Phase 2 readiness evidence rows: 66.
- Current build plan accepted rows: 58; deferred rows: 8.
- Decision evidence requiring refresh before Phase 2 build: 1 row(s): KE:2015.

## Schema Presence

- `raw_parquet_present`: 527/527.
- `causal_parquet_present`: 461/527.
- `ohlcv_1m_dbn_present`: 527/527.
- `definition_dbn_present`: 527/527.
- `statistics_dbn_present`: 527/527.
- `status_dbn_present`: 460/527.

## Raw Optional-Schema Audit

- Status: `FAIL` from `reports\raw_readiness\raw_enriched_optional_schema_audit.json`.
- Files checked: 527; rows checked: 129656421.
- `duplicate_key_row_count`: 0.
- `file_failure_count`: 23.
- `missing_source_file_count`: 48.
- `missing_statistics_archive_market_year_count`: 0.
- `missing_status_archive_market_year_count`: 67.
- `row_count`: 129656421.
- `schema_failure_count`: 17.
- `source_hash_mismatch_count`: 0.
- `statistics_archive_market_year_count`: 527.
- `statistics_failure_count`: 17.
- `status_archive_market_year_count`: 460.
- `status_failure_count`: 17.

## Unknown Drilldown

- raw audit failed: missing enriched columns/schema: 17.
- raw audit failed: missing source reference paths: 6.

| pair | primary_blocker | raw_audit_status | raw_failure_summary | latest_phase2_decision |
| --- | --- | --- | --- | --- |
| SR3:2019 | raw optional-schema audit failed; source reference path missing | FAIL | source_file path does not exist / status_source_file path does not exist / stat_opening_price_source_file path does not exist / stat_sett... |  |
| SR3:2020 | raw optional-schema audit failed; source reference path missing | FAIL | source_file path does not exist / status_source_file path does not exist / stat_opening_price_source_file path does not exist / stat_sett... |  |
| SR3:2021 | raw optional-schema audit failed; source reference path missing | FAIL | source_file path does not exist / status_source_file path does not exist / stat_opening_price_source_file path does not exist / stat_sett... |  |
| SR3:2022 | raw optional-schema audit failed; source reference path missing | FAIL | source_file path does not exist / status_source_file path does not exist / stat_opening_price_source_file path does not exist / stat_sett... |  |
| SR3:2023 | raw optional-schema audit failed; source reference path missing | FAIL | source_file path does not exist / status_source_file path does not exist / stat_opening_price_source_file path does not exist / stat_sett... |  |
| SR3:2024 | raw optional-schema audit failed; source reference path missing | FAIL | source_file path does not exist / status_source_file path does not exist / stat_opening_price_source_file path does not exist / stat_sett... |  |
| SR1:2018 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| SR1:2019 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| SR1:2020 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| SR1:2021 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| SR1:2022 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| SR1:2023 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| SR1:2024 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| SR1:2025 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| SR1:2026 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| TN:2025 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| TN:2026 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| ZL:2025 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| ZL:2026 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| ZM:2025 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| ZM:2026 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | ACCEPTED_FOR_FUTURE_BOUNDED_PHASE2_BUILD |
| KE:2025 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | KE_2016_2026_POLICY_REVIEWABLE |
| KE:2026 | raw optional-schema audit failed | FAIL | missing enriched raw columns: stat_cleared_volume,stat_cleared_volume_missing,stat_cleared_volume_source_file,stat_cleared_volume_source_... | KE_2016_2026_POLICY_REVIEWABLE |

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

Rows in this class have source evidence present enough to avoid immediate exclusion/unknown classification, but still have optional status/statistics gaps, Phase 2 readiness blockers, accepted exceptions, missing causal outputs, or duplicate/extra manifest policy rows. They are not automatically clean for modeling or cleanup.

| pair | primary_blocker | latest_phase2_decision | phase2_top_blocker |
| --- | --- | --- | --- |
| ES:2010 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| ES:2011 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| ES:2012 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| ES:2013 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| ES:2014 | canonical status DBN absent or optional; raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| ES:2015 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| ES:2016 | raw statistics enrichment missing/stale rows |  |  |
| ES:2017 | raw statistics enrichment missing/stale rows |  |  |
| ES:2018 | raw statistics enrichment missing/stale rows |  |  |
| ES:2019 | raw statistics enrichment missing/stale rows |  |  |
| ES:2020 | raw statistics enrichment missing/stale rows |  |  |
| ES:2021 | raw statistics enrichment missing/stale rows |  |  |
| ES:2022 | raw statistics enrichment missing/stale rows |  |  |
| ES:2023 | raw statistics enrichment missing/stale rows |  |  |
| ES:2024 | raw statistics enrichment missing/stale rows |  |  |
| ES:2025 | raw statistics enrichment missing/stale rows |  |  |
| ES:2026 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2010 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| NQ:2011 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| NQ:2012 | canonical status DBN absent or optional; raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| NQ:2013 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| NQ:2014 | canonical status DBN absent or optional; raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| NQ:2015 | raw status enrichment missing/stale rows; raw statistics enrichment missing/stale rows |  |  |
| NQ:2016 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2017 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2018 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2019 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2020 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2021 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2022 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2023 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2024 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2025 | raw statistics enrichment missing/stale rows |  |  |
| NQ:2026 | raw statistics enrichment missing/stale rows |  |  |
| RTY:2017 | raw statistics enrichment missing/stale rows; manifest duplicate/extra policy row |  |  |
| RTY:2018 | raw statistics enrichment missing/stale rows |  |  |
| RTY:2019 | raw statistics enrichment missing/stale rows |  |  |
| RTY:2020 | raw statistics enrichment missing/stale rows |  |  |
| RTY:2021 | raw statistics enrichment missing/stale rows |  |  |
| RTY:2022 | raw statistics enrichment missing/stale rows |  |  |

## Recommended Next Decision

1. Do not run Phase 2 or cleanup from this matrix alone.
2. Resolve the 23 `UNKNOWN_REVIEW_REQUIRED` raw/source rows first with bounded one-row re-enrichment, source-reference correction, explicit deferral, or exclusion decisions.
3. Refresh the Phase 2 build/exclusion plan before any Phase 2 build, because the later KE policy excludes `KE:2015` while the older build plan still lists it as accepted.
