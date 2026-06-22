# Batch Phase 2 Source/Status Review

- Updated at UTC: 2026-06-22T17:31:31Z
- Scope: bounded report-only source/status review for the 34 Phase 2 rows previously classified as source/status reviewable.
- Decision state: SOURCE_STATUS_DECISIONS_RECORDED_BATCH

## Summary

- Starting source/status-reviewable rows: 34.
- `RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT`: 8 rows.
- `STATUS_STATISTICS_RECONCILE_OR_EXCEPTION`: 12 rows.
- `STATISTICS_EDGE_RECONCILE_OR_EXCEPTION`: 14 rows.
- Rows approved for Phase 2 build: 0.
- Rows approved for cleanup: 0.
- Rows approved for redownload/source acquisition: 0.
- Rows explicitly deferred in this batch: 0.

This packet turns the 34 source/status-reviewable rows into explicit recovery, reconciliation, exception, or deferral decision paths. It does not approve Phase 2 build execution, source acquisition, redownload, repair, threshold changes, or cleanup.

## Decision Classes

- `RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT`: readiness has missing status rows, and cheap metadata found no canonical `data/dbn/status/<market>/<year>/*.dbn.zst` or `data/dbn/status_parent/<market>/<year>/*.dbn.zst`. Next decision is bounded status source recovery/acquisition/reconstruction or explicit deferral.
- `STATUS_STATISTICS_RECONCILE_OR_EXCEPTION`: readiness has missing status rows, but canonical status and statistics DBN files exist. Next decision is bounded enrichment reconciliation or explicit policy exception/deferral.
- `STATISTICS_EDGE_RECONCILE_OR_EXCEPTION`: readiness has no missing status rows but has missing statistics rows. Canonical statistics DBN files exist. Next decision is bounded statistics edge reconciliation or explicit policy exception/deferral.

## Reviewed Rows

| Row | Prior policy | Final decision | Status missing | Statistics missing | Status files | Status parent files | Statistics files |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| KE:2013 | SOURCE_STATUS_REVIEWABLE | RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT | 4071 | 0 | 0 | 0 | 1 |
| KE:2014 | ROLL_SOURCE_STATUS_REVIEWABLE | RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT | 101536 | 3 | 0 | 0 | 1 |
| KE:2015 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 98117 | 2 | 1 | 0 | 1 |
| KE:2016 | ROLL_SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 2 | 1 | 0 | 1 |
| KE:2017 | ROLL_SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 3 | 1 | 0 | 1 |
| KE:2018 | ROLL_SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 2 | 1 | 0 | 1 |
| KE:2020 | SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 1 | 1 | 0 | 1 |
| KE:2022 | ROLL_SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 1 | 1 | 0 | 1 |
| TN:2016 | SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 11 | 1 | 0 | 1 |
| TN:2017 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 2504 | 51 | 1 | 0 | 1 |
| TN:2018 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 2112 | 136 | 1 | 0 | 1 |
| TN:2019 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 883 | 20 | 1 | 0 | 1 |
| TN:2020 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 3496 | 95 | 1 | 0 | 1 |
| TN:2021 | SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 6 | 1 | 0 | 1 |
| TN:2022 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 4564 | 150 | 1 | 0 | 1 |
| TN:2023 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 4721 | 49 | 1 | 0 | 1 |
| TN:2024 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 2277 | 300 | 1 | 0 | 1 |
| ZL:2011 | ROLL_SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 151862 | 2 | 1 | 0 | 1 |
| ZL:2012 | SOURCE_STATUS_REVIEWABLE | RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT | 216029 | 314 | 0 | 0 | 1 |
| ZL:2013 | ROLL_SOURCE_STATUS_REVIEWABLE | RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT | 200535 | 6 | 0 | 0 | 1 |
| ZL:2014 | ROLL_SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 142399 | 2 | 1 | 0 | 1 |
| ZL:2015 | SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 174466 | 2 | 1 | 0 | 1 |
| ZL:2016 | SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 1 | 1 | 0 | 1 |
| ZL:2017 | SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 4 | 1 | 0 | 1 |
| ZL:2018 | ROLL_SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 2 | 1 | 0 | 1 |
| ZL:2024 | ROLL_SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 1 | 1 | 0 | 1 |
| ZM:2011 | SOURCE_STATUS_REVIEWABLE | RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT | 136632 | 21 | 0 | 0 | 1 |
| ZM:2012 | SOURCE_STATUS_REVIEWABLE | RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT | 189710 | 32 | 0 | 0 | 1 |
| ZM:2013 | ROLL_SOURCE_STATUS_REVIEWABLE | RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT | 190497 | 4 | 0 | 0 | 1 |
| ZM:2014 | SOURCE_STATUS_REVIEWABLE | RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT | 178340 | 2 | 0 | 0 | 1 |
| ZM:2015 | ROLL_SOURCE_STATUS_REVIEWABLE | STATUS_STATISTICS_RECONCILE_OR_EXCEPTION | 163558 | 2 | 1 | 0 | 1 |
| ZM:2016 | SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 2 | 1 | 0 | 1 |
| ZM:2017 | SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 3 | 1 | 0 | 1 |
| ZM:2018 | ROLL_SOURCE_STATUS_REVIEWABLE | STATISTICS_EDGE_RECONCILE_OR_EXCEPTION | 0 | 2 | 1 | 0 | 1 |

## Smallest Safe Next Steps

1. For `RECOVERY_OR_DEFER_STATUS_SOURCE_ABSENT`, approve a bounded source/status recovery plan or explicitly defer those rows. Stop before data acquisition, reconstruction, Phase 2 build, or cleanup.
2. For `STATUS_STATISTICS_RECONCILE_OR_EXCEPTION`, approve a bounded enrichment reconciliation review or explicitly accept/defer a policy exception. Stop before Phase 2 build.
3. For `STATISTICS_EDGE_RECONCILE_OR_EXCEPTION`, approve a bounded statistics edge reconciliation review or explicitly accept/defer a policy exception. Stop before Phase 2 build.

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
