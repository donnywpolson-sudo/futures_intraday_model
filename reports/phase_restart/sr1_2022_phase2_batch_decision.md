# SR1 2022 Phase 2 Batch Readiness Decision

- Reviewed at UTC: 2026-06-22T16:13:14Z
- Scope: automated bounded Phase 2 readiness-only review and explicit blocker-plan record.
- Decision state: EXPLICIT_BLOCKER_PLAN_APPROVED_BATCH

## Evidence

- Readiness report: `reports/phase_restart/sr1_2022_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Raw alignment report: `reports/phase_restart/sr1_2022_phase2_raw_alignment.json`

## Row Findings

- Top blocker reason: `roll maturity sequence not monotonic: backsteps=44`
- Warnings: roll maturity sequence not monotonic: backsteps=44
- Synthetic rows: 0 of 64948, 0.0%.
- Max synthetic gap minutes: 0
- Roll maturity backsteps: 44
- Status missing/stale rows: 0/0
- Statistics missing/stale rows: 0/0
- Roll maturity examples:
  - 2022-01-07T02:04:00+00:00: previous `SR1K2` maturity 24269, current `SR1J2` maturity 24268.
  - 2022-01-09T23:00:00+00:00: previous `SR1J2` maturity 24268, current `SR1G2` maturity 24266.
  - 2022-01-24T09:06:00+00:00: previous `SR1J2` maturity 24268, current `SR1F2` maturity 24265.
  - 2022-01-27T07:15:00+00:00: previous `SR1K2` maturity 24269, current `SR1F2` maturity 24265.
  - 2022-02-06T23:10:00+00:00: previous `SR1K2` maturity 24269, current `SR1J2` maturity 24268.

## Approved Batch Plan

- This report records an explicit review/plan decision only.
- Phase 2 build execution remains blocked unless separately approved.
- If readiness failed because of synthetic coverage, status enrichment, statistics enrichment, or roll maturity warnings, handle by separate bounded defer/acquire/reconstruct/policy-exception decision before any build.
- After any source/status acquisition, reconstruction, or exception path, rerun readiness-only before any Phase 2 build.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written for SR1 2022.
- No policy threshold was changed.
