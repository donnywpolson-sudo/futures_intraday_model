# Batch Phase 2 Synthetic-Threshold Policy

- Updated at UTC: 2026-06-22T17:17:31Z
- Scope: report-only batch policy for the 31 Phase 2 readiness rows whose top blocker is `synthetic threshold breached`.
- Decision state: SYNTHETIC_THRESHOLD_REVIEWABLE_BATCH

## Summary

- Starting synthetic-threshold blockers: 31.
- Rows made source/status reviewable: 21.
- Rows made policy-exception reviewable: 10.
- Rows explicitly deferred in this batch policy: 0.
- Rows approved for Phase 2 build: 0.
- Rows approved for cleanup: 0.

This packet makes the 31 synthetic-threshold blockers explicit without approving Phase 2 build execution. Each row remains stopped before Phase 2 build until a separate bounded source/status review, source acquisition/reconstruction plan, policy-exception decision, or explicit deferral is approved and recorded.

## Policy Classes

- `SOURCE_STATUS_REVIEWABLE`: readiness also shows missing or stale status/statistics enrichment. Next allowed step is a bounded source/status/statistics review or acquisition/reconstruction plan. Stop before Phase 2 build.
- `POLICY_EXCEPTION_REVIEWABLE`: readiness shows no missing status/statistics rows, but synthetic coverage still breaches the configured threshold. Next allowed step is a market/year policy-exception review or explicit deferral. Stop before Phase 2 build.

## Synthetic-Threshold Rows

| Row | Policy class | Synthetic % | Max gap minutes | Status missing rows | Statistics missing rows | Evidence |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| KE:2013 | SOURCE_STATUS_REVIEWABLE | 59.633118 | 105 | 4071 | 0 | `reports/phase_restart/ke_2013_phase2_readiness.json` |
| KE:2015 | SOURCE_STATUS_REVIEWABLE | 60.032591 | 120 | 98117 | 2 | `reports/phase_restart/ke_2015_phase2_readiness.json` |
| KE:2020 | SOURCE_STATUS_REVIEWABLE | 50.132170 | 108 | 0 | 1 | `reports/phase_restart/ke_2020_phase2_readiness.json` |
| KE:2023 | POLICY_EXCEPTION_REVIEWABLE | 47.828151 | 120 | 0 | 0 | `reports/phase_restart/ke_2023_phase2_readiness.json` |
| KE:2025 | POLICY_EXCEPTION_REVIEWABLE | 42.477190 | 67 | 0 | 0 | `reports/phase_restart/ke_2025_phase2_readiness.json` |
| TN:2016 | SOURCE_STATUS_REVIEWABLE | 36.631235 | 116 | 0 | 11 | `reports/phase_restart/tn_2016_phase2_readiness.json` |
| TN:2017 | SOURCE_STATUS_REVIEWABLE | 36.008144 | 81 | 2504 | 51 | `reports/phase_restart/tn_2017_phase2_readiness.json` |
| TN:2018 | SOURCE_STATUS_REVIEWABLE | 31.388361 | 95 | 2112 | 136 | `reports/phase_restart/tn_2018_phase2_readiness.json` |
| TN:2019 | SOURCE_STATUS_REVIEWABLE | 24.484669 | 109 | 883 | 20 | `reports/phase_restart/tn_2019_phase2_readiness.json` |
| TN:2020 | SOURCE_STATUS_REVIEWABLE | 16.563056 | 98 | 3496 | 95 | `reports/phase_restart/tn_2020_phase2_readiness.json` |
| TN:2021 | SOURCE_STATUS_REVIEWABLE | 15.308577 | 45 | 0 | 6 | `reports/phase_restart/tn_2021_phase2_readiness.json` |
| TN:2022 | SOURCE_STATUS_REVIEWABLE | 7.703368 | 52 | 4564 | 150 | `reports/phase_restart/tn_2022_phase2_readiness.json` |
| TN:2023 | SOURCE_STATUS_REVIEWABLE | 11.775790 | 78 | 4721 | 49 | `reports/phase_restart/tn_2023_phase2_readiness.json` |
| TN:2024 | SOURCE_STATUS_REVIEWABLE | 13.402213 | 103 | 2277 | 300 | `reports/phase_restart/tn_2024_phase2_readiness.json` |
| TN:2025 | POLICY_EXCEPTION_REVIEWABLE | 16.861847 | 51 | 0 | 0 | `reports/phase_restart/tn_2025_phase2_readiness.json` |
| TN:2026 | POLICY_EXCEPTION_REVIEWABLE | 16.626671 | 36 | 0 | 0 | `reports/phase_restart/tn_2026_phase2_readiness.json` |
| ZL:2012 | SOURCE_STATUS_REVIEWABLE | 25.533946 | 41 | 216029 | 314 | `reports/phase_restart/zl_2012_phase2_readiness.json` |
| ZL:2015 | SOURCE_STATUS_REVIEWABLE | 29.447784 | 46 | 174466 | 2 | `reports/phase_restart/zl_2015_phase2_readiness.json` |
| ZL:2016 | SOURCE_STATUS_REVIEWABLE | 25.843309 | 46 | 0 | 1 | `reports/phase_restart/zl_2016_phase2_readiness.json` |
| ZL:2017 | SOURCE_STATUS_REVIEWABLE | 25.000183 | 99 | 0 | 4 | `reports/phase_restart/zl_2017_phase2_readiness.json` |
| ZL:2020 | POLICY_EXCEPTION_REVIEWABLE | 13.174231 | 109 | 0 | 0 | `reports/phase_restart/zl_2020_phase2_readiness.json` |
| ZL:2023 | POLICY_EXCEPTION_REVIEWABLE | 19.136132 | 46 | 0 | 0 | `reports/phase_restart/zl_2023_phase2_readiness.json` |
| ZL:2025 | POLICY_EXCEPTION_REVIEWABLE | 16.773509 | 46 | 0 | 0 | `reports/phase_restart/zl_2025_phase2_readiness.json` |
| ZL:2026 | POLICY_EXCEPTION_REVIEWABLE | 11.823678 | 46 | 0 | 0 | `reports/phase_restart/zl_2026_phase2_readiness.json` |
| ZM:2011 | SOURCE_STATUS_REVIEWABLE | 46.647299 | 80 | 136632 | 21 | `reports/phase_restart/zm_2011_phase2_readiness.json` |
| ZM:2012 | SOURCE_STATUS_REVIEWABLE | 34.603054 | 53 | 189710 | 32 | `reports/phase_restart/zm_2012_phase2_readiness.json` |
| ZM:2014 | SOURCE_STATUS_REVIEWABLE | 33.824621 | 71 | 178340 | 2 | `reports/phase_restart/zm_2014_phase2_readiness.json` |
| ZM:2016 | SOURCE_STATUS_REVIEWABLE | 33.018313 | 75 | 0 | 2 | `reports/phase_restart/zm_2016_phase2_readiness.json` |
| ZM:2017 | SOURCE_STATUS_REVIEWABLE | 32.373895 | 115 | 0 | 3 | `reports/phase_restart/zm_2017_phase2_readiness.json` |
| ZM:2023 | POLICY_EXCEPTION_REVIEWABLE | 23.455840 | 46 | 0 | 0 | `reports/phase_restart/zm_2023_phase2_readiness.json` |
| ZM:2026 | POLICY_EXCEPTION_REVIEWABLE | 23.786257 | 47 | 0 | 0 | `reports/phase_restart/zm_2026_phase2_readiness.json` |

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No phase 3+ command was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written.
- No data artifact was staged.
- Cleanup remains disabled.

## Next Decision

User decision needed: approve a bounded batch source/status review plan for the 21 `SOURCE_STATUS_REVIEWABLE` rows, approve market/year policy-exception review for the 10 `POLICY_EXCEPTION_REVIEWABLE` rows, or explicitly defer selected rows. Stop before Phase 2 build execution.
