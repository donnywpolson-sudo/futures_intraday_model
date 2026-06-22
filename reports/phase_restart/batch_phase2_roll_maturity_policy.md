# Batch Phase 2 Roll-Maturity Policy

- Updated at UTC: 2026-06-22T17:22:50Z
- Scope: report-only batch policy for the 35 Phase 2 readiness rows whose top blocker is `roll maturity sequence not monotonic`.
- Decision state: ROLL_MATURITY_REVIEWABLE_BATCH

## Summary

- Starting roll-maturity blockers: 35.
- Pure roll-maturity reviewable rows: 9.
- Roll plus source/status reviewable rows: 13.
- Roll plus policy-exception reviewable rows: 13.
- Rows explicitly deferred in this batch policy: 0.
- Rows approved for Phase 2 build: 0.
- Rows approved for cleanup: 0.

This packet makes the 35 roll-maturity blockers explicit without approving Phase 2 build execution. Each row remains stopped before Phase 2 build until a separate bounded roll-rule review, source/status/statistics review, policy-exception decision, or explicit deferral is approved and recorded.

## Policy Classes

- `PURE_ROLL_MATURITY_REVIEWABLE`: readiness top blocker is roll maturity, with no synthetic rows and no missing status/statistics rows. Next allowed step is bounded roll-rule review or explicit deferral. Stop before Phase 2 build.
- `ROLL_SOURCE_STATUS_REVIEWABLE`: readiness top blocker is roll maturity and also shows missing/stale status or statistics enrichment. Next allowed step is bounded source/status/statistics review plus roll-rule review. Stop before Phase 2 build.
- `ROLL_POLICY_EXCEPTION_REVIEWABLE`: readiness top blocker is roll maturity, status/statistics rows are complete, but synthetic coverage is nonzero. Next allowed step is bounded roll-rule plus synthetic policy-exception review or explicit deferral. Stop before Phase 2 build.

## Roll-Maturity Rows

| Row | Policy class | Backsteps | Roll-window rows | Roll-window % | Synthetic % | Status missing rows | Statistics missing rows | Evidence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| KE:2014 | ROLL_SOURCE_STATUS_REVIEWABLE | 4 | 403 | 0.151402 | 61.854098 | 101536 | 3 | `reports/phase_restart/ke_2014_phase2_readiness.json` |
| KE:2016 | ROLL_SOURCE_STATUS_REVIEWABLE | 2 | 279 | 0.102043 | 60.763897 | 0 | 2 | `reports/phase_restart/ke_2016_phase2_readiness.json` |
| KE:2017 | ROLL_SOURCE_STATUS_REVIEWABLE | 2 | 279 | 0.102290 | 59.111657 | 0 | 3 | `reports/phase_restart/ke_2017_phase2_readiness.json` |
| KE:2018 | ROLL_SOURCE_STATUS_REVIEWABLE | 2 | 279 | 0.102049 | 55.154554 | 0 | 2 | `reports/phase_restart/ke_2018_phase2_readiness.json` |
| KE:2019 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 1 | 217 | 0.079396 | 53.604083 | 0 | 0 | `reports/phase_restart/ke_2019_phase2_readiness.json` |
| KE:2021 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 1 | 217 | 0.078764 | 46.208236 | 0 | 0 | `reports/phase_restart/ke_2021_phase2_readiness.json` |
| KE:2022 | ROLL_SOURCE_STATUS_REVIEWABLE | 4 | 403 | 0.147375 | 49.142266 | 0 | 1 | `reports/phase_restart/ke_2022_phase2_readiness.json` |
| KE:2024 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 3 | 341 | 0.124539 | 44.213667 | 0 | 0 | `reports/phase_restart/ke_2024_phase2_readiness.json` |
| KE:2026 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 1 | 124 | 0.101315 | 32.053272 | 0 | 0 | `reports/phase_restart/ke_2026_phase2_readiness.json` |
| SR1:2018 | PURE_ROLL_MATURITY_REVIEWABLE | 36 | 116 | 7.426376 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2018_phase2_readiness.json` |
| SR1:2019 | PURE_ROLL_MATURITY_REVIEWABLE | 50 | 198 | 1.931330 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2019_phase2_readiness.json` |
| SR1:2020 | PURE_ROLL_MATURITY_REVIEWABLE | 72 | 255 | 2.674358 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2020_phase2_readiness.json` |
| SR1:2021 | PURE_ROLL_MATURITY_REVIEWABLE | 76 | 268 | 3.796572 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2021_phase2_readiness.json` |
| SR1:2022 | PURE_ROLL_MATURITY_REVIEWABLE | 44 | 214 | 0.329494 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2022_phase2_readiness.json` |
| SR1:2023 | PURE_ROLL_MATURITY_REVIEWABLE | 54 | 269 | 0.325938 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2023_phase2_readiness.json` |
| SR1:2024 | PURE_ROLL_MATURITY_REVIEWABLE | 62 | 390 | 0.527476 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2024_phase2_readiness.json` |
| SR1:2025 | PURE_ROLL_MATURITY_REVIEWABLE | 64 | 399 | 0.533836 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2025_phase2_readiness.json` |
| SR1:2026 | PURE_ROLL_MATURITY_REVIEWABLE | 27 | 186 | 0.651306 | 0.000000 | 0 | 0 | `reports/phase_restart/sr1_2026_phase2_readiness.json` |
| ZL:2011 | ROLL_SOURCE_STATUS_REVIEWABLE | 1 | 186 | 0.072611 | 34.808849 | 151862 | 2 | `reports/phase_restart/zl_2011_phase2_readiness.json` |
| ZL:2013 | ROLL_SOURCE_STATUS_REVIEWABLE | 1 | 217 | 0.076738 | 29.084949 | 200535 | 6 | `reports/phase_restart/zl_2013_phase2_readiness.json` |
| ZL:2014 | ROLL_SOURCE_STATUS_REVIEWABLE | 1 | 217 | 0.080522 | 30.415745 | 142399 | 2 | `reports/phase_restart/zl_2014_phase2_readiness.json` |
| ZL:2018 | ROLL_SOURCE_STATUS_REVIEWABLE | 1 | 217 | 0.079302 | 29.474923 | 0 | 2 | `reports/phase_restart/zl_2018_phase2_readiness.json` |
| ZL:2019 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 1 | 217 | 0.079444 | 27.634570 | 0 | 0 | `reports/phase_restart/zl_2019_phase2_readiness.json` |
| ZL:2021 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 3 | 341 | 0.123773 | 13.842580 | 0 | 0 | `reports/phase_restart/zl_2021_phase2_readiness.json` |
| ZL:2022 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 1 | 217 | 0.079314 | 19.429083 | 0 | 0 | `reports/phase_restart/zl_2022_phase2_readiness.json` |
| ZL:2024 | ROLL_SOURCE_STATUS_REVIEWABLE | 2 | 279 | 0.101895 | 16.969066 | 0 | 1 | `reports/phase_restart/zl_2024_phase2_readiness.json` |
| ZM:2013 | ROLL_SOURCE_STATUS_REVIEWABLE | 2 | 279 | 0.098664 | 32.633965 | 190497 | 4 | `reports/phase_restart/zm_2013_phase2_readiness.json` |
| ZM:2015 | ROLL_SOURCE_STATUS_REVIEWABLE | 2 | 279 | 0.101566 | 34.317812 | 163558 | 2 | `reports/phase_restart/zm_2015_phase2_readiness.json` |
| ZM:2018 | ROLL_SOURCE_STATUS_REVIEWABLE | 1 | 186 | 0.067941 | 31.000815 | 0 | 2 | `reports/phase_restart/zm_2018_phase2_readiness.json` |
| ZM:2019 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 2 | 310 | 0.113627 | 36.214088 | 0 | 0 | `reports/phase_restart/zm_2019_phase2_readiness.json` |
| ZM:2020 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 4 | 434 | 0.158002 | 28.469856 | 0 | 0 | `reports/phase_restart/zm_2020_phase2_readiness.json` |
| ZM:2021 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 1 | 217 | 0.078764 | 22.103047 | 0 | 0 | `reports/phase_restart/zm_2021_phase2_readiness.json` |
| ZM:2022 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 2 | 279 | 0.102023 | 24.793304 | 0 | 0 | `reports/phase_restart/zm_2022_phase2_readiness.json` |
| ZM:2024 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 2 | 279 | 0.101895 | 23.339907 | 0 | 0 | `reports/phase_restart/zm_2024_phase2_readiness.json` |
| ZM:2025 | ROLL_POLICY_EXCEPTION_REVIEWABLE | 2 | 310 | 0.113364 | 29.389479 | 0 | 0 | `reports/phase_restart/zm_2025_phase2_readiness.json` |

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

User decision needed: approve bounded roll-rule review for the 9 `PURE_ROLL_MATURITY_REVIEWABLE` rows, approve bounded source/status plus roll review for the 13 `ROLL_SOURCE_STATUS_REVIEWABLE` rows, approve bounded roll plus policy-exception review for the 13 `ROLL_POLICY_EXCEPTION_REVIEWABLE` rows, or explicitly defer selected rows. Stop before Phase 2 build execution.
