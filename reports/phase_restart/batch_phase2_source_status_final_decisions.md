# Batch Phase 2 Source/Status Final Decisions

- Updated at UTC: 2026-06-22T18:38:32Z
- Scope: report-only final batch decisions for the 34 Phase 2 source/status rows.
- Decision state: SOURCE_STATUS_FINAL_BATCH_DECISIONS_RECORDED

## Summary

- Starting source/status rows: 34.
- Explicitly deferred because canonical status source is absent: 8.
- Accepted for status/statistics exception handling: 12.
- Accepted for statistics-edge exception handling: 14.
- Total accepted for exception handling: 26.
- Rows approved for Phase 2 build: 0.
- Rows approved for cleanup: 0.
- Rows approved for redownload/source acquisition: 0.

## Batch Decision

The conservative batch decision is:

1. Defer rows where readiness has missing status rows and cheap metadata found no canonical `data/dbn/status/<market>/<year>/*.dbn.zst` or `data/dbn/status_parent/<market>/<year>/*.dbn.zst`.
2. Accept exception handling for rows where canonical status/statistics sources exist but readiness still reports status/statistics gaps.
3. Accept exception handling for rows with only statistics-edge gaps where canonical statistics sources exist.

This records decisions only. It does not approve Phase 2 build execution, cleanup, data repair, source acquisition, redownload, threshold changes, or any data movement.

## Explicitly Deferred Rows

| Row | Decision | Reason |
| --- | --- | --- |
| KE:2013 | EXPLICITLY_DEFER_STATUS_SOURCE_ABSENT | Missing status rows and no canonical status/status_parent DBN source found. |
| KE:2014 | EXPLICITLY_DEFER_STATUS_SOURCE_ABSENT | Missing status rows and no canonical status/status_parent DBN source found. |
| ZL:2012 | EXPLICITLY_DEFER_STATUS_SOURCE_ABSENT | Missing status rows and no canonical status/status_parent DBN source found. |
| ZL:2013 | EXPLICITLY_DEFER_STATUS_SOURCE_ABSENT | Missing status rows and no canonical status/status_parent DBN source found. |
| ZM:2011 | EXPLICITLY_DEFER_STATUS_SOURCE_ABSENT | Missing status rows and no canonical status/status_parent DBN source found. |
| ZM:2012 | EXPLICITLY_DEFER_STATUS_SOURCE_ABSENT | Missing status rows and no canonical status/status_parent DBN source found. |
| ZM:2013 | EXPLICITLY_DEFER_STATUS_SOURCE_ABSENT | Missing status rows and no canonical status/status_parent DBN source found. |
| ZM:2014 | EXPLICITLY_DEFER_STATUS_SOURCE_ABSENT | Missing status rows and no canonical status/status_parent DBN source found. |

## Accepted Status/Statistics Exception Rows

| Row | Decision | Reason |
| --- | --- | --- |
| KE:2015 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| TN:2017 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| TN:2018 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| TN:2019 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| TN:2020 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| TN:2022 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| TN:2023 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| TN:2024 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| ZL:2011 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| ZL:2014 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| ZL:2015 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |
| ZM:2015 | ACCEPT_STATUS_STATISTICS_EXCEPTION | Canonical status/statistics files exist; readiness gaps are handled as explicit exception evidence. |

## Accepted Statistics-Edge Exception Rows

| Row | Decision | Reason |
| --- | --- | --- |
| KE:2016 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| KE:2017 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| KE:2018 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| KE:2020 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| KE:2022 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| TN:2016 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| TN:2021 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| ZL:2016 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| ZL:2017 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| ZL:2018 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| ZL:2024 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| ZM:2016 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| ZM:2017 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |
| ZM:2018 | ACCEPT_STATISTICS_EDGE_EXCEPTION | Canonical statistics file exists; readiness statistics gap is handled as explicit exception evidence. |

## Remaining Gate

- All 66 Phase 2 rows now have explicit report-only decisions.
- Rows accepted for exception handling are not approved for Phase 2 build until a separate bounded Phase 2 build command is approved.
- Deferred rows should be excluded from any future bounded Phase 2 build unless separately approved for source recovery or explicit override.
- Cleanup remains disabled until Phase 2 execution state is settled and cleanup is explicitly approved.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No phase 3+ command was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No source/status acquisition or reconstruction was run.
- No policy threshold was changed.
- No canonical causal parquet was written.
- No data artifact was staged.
- Cleanup remains disabled.
