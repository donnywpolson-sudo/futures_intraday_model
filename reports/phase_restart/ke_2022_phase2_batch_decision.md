# KE 2022 Phase 2 Batch Readiness Decision

- Reviewed at UTC: 2026-06-22T15:19:27Z
- Scope: automated bounded Phase 2 readiness-only review and explicit blocker-plan record.
- Decision state: EXPLICIT_BLOCKER_PLAN_APPROVED_BATCH

## Evidence

- Readiness report: `reports/phase_restart/ke_2022_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Raw alignment report: `reports/phase_restart/ke_2022_phase2_raw_alignment.json`

## Row Findings

- Top blocker reason: `roll maturity sequence not monotonic: backsteps=4`
- Warnings: roll maturity sequence not monotonic: backsteps=4; synthetic threshold breached: rows_pct=49.142266 max_gap_minutes=97
- Synthetic rows: 134381 of 273453, 49.142266%.
- Max synthetic gap minutes: 97
- Roll maturity backsteps: 4
- Status missing/stale rows: 0/0
- Statistics missing/stale rows: 1/1
- Roll maturity examples:
  - 2022-03-09T01:00:00+00:00: previous `KEN2` maturity 24271, current `KEK2` maturity 24269.
  - 2022-03-24T00:00:00+00:00: previous `KEN2` maturity 24271, current `KEK2` maturity 24269.
  - 2022-03-30T00:00:00+00:00: previous `KEN2` maturity 24271, current `KEK2` maturity 24269.
  - 2022-04-01T00:00:00+00:00: previous `KEN2` maturity 24271, current `KEK2` maturity 24269.

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
- No canonical causal parquet was written for KE 2022.
- No policy threshold was changed.
