# SR1 2020 Phase 2 Batch Readiness Decision

- Reviewed at UTC: 2026-06-22T16:12:47Z
- Scope: automated bounded Phase 2 readiness-only review and explicit blocker-plan record.
- Decision state: EXPLICIT_BLOCKER_PLAN_APPROVED_BATCH

## Evidence

- Readiness report: `reports/phase_restart/sr1_2020_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Raw alignment report: `reports/phase_restart/sr1_2020_phase2_raw_alignment.json`

## Row Findings

- Top blocker reason: `roll maturity sequence not monotonic: backsteps=72`
- Warnings: roll maturity sequence not monotonic: backsteps=72; roll exclusion threshold breached: rows_pct=2.674358 rows=255
- Synthetic rows: 0 of 9535, 0.0%.
- Max synthetic gap minutes: 0
- Roll maturity backsteps: 72
- Status missing/stale rows: 0/0
- Statistics missing/stale rows: 0/0
- Roll maturity examples:
  - 2020-01-15T08:39:00+00:00: previous `SR1G0` maturity 24242, current `SR1F0` maturity 24241.
  - 2020-01-27T09:48:00+00:00: previous `SR1K0` maturity 24245, current `SR1F0` maturity 24241.
  - 2020-01-31T00:00:00+00:00: previous `SR1K0` maturity 24245, current `SR1J0` maturity 24244.
  - 2020-02-03T00:15:00+00:00: previous `SR1J0` maturity 24244, current `SR1G0` maturity 24242.
  - 2020-02-09T23:08:00+00:00: previous `SR1M0` maturity 24246, current `SR1K0` maturity 24245.

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
- No canonical causal parquet was written for SR1 2020.
- No policy threshold was changed.
