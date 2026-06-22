# SR1 2021 Phase 2 Batch Readiness Decision

- Reviewed at UTC: 2026-06-22T16:12:59Z
- Scope: automated bounded Phase 2 readiness-only review and explicit blocker-plan record.
- Decision state: EXPLICIT_BLOCKER_PLAN_APPROVED_BATCH

## Evidence

- Readiness report: `reports/phase_restart/sr1_2021_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Raw alignment report: `reports/phase_restart/sr1_2021_phase2_raw_alignment.json`

## Row Findings

- Top blocker reason: `roll maturity sequence not monotonic: backsteps=76`
- Warnings: roll maturity sequence not monotonic: backsteps=76; roll exclusion threshold breached: rows_pct=3.796572 rows=268
- Synthetic rows: 0 of 7059, 0.0%.
- Max synthetic gap minutes: 0
- Roll maturity backsteps: 76
- Status missing/stale rows: 0/0
- Statistics missing/stale rows: 0/0
- Roll maturity examples:
  - 2021-01-06T01:32:00+00:00: previous `SR1G1` maturity 24254, current `SR1F1` maturity 24253.
  - 2021-01-08T01:42:00+00:00: previous `SR1J1` maturity 24256, current `SR1F1` maturity 24253.
  - 2021-01-14T02:27:00+00:00: previous `SR1N1` maturity 24259, current `SR1J1` maturity 24256.
  - 2021-01-18T06:13:00+00:00: previous `SR1K1` maturity 24257, current `SR1J1` maturity 24256.
  - 2021-01-21T11:54:00+00:00: previous `SR1J1` maturity 24256, current `SR1G1` maturity 24254.

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
- No canonical causal parquet was written for SR1 2021.
- No policy threshold was changed.
