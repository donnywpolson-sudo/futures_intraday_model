# SR1 2018 Phase 2 Batch Readiness Decision

- Reviewed at UTC: 2026-06-22T16:12:22Z
- Scope: automated bounded Phase 2 readiness-only review and explicit blocker-plan record.
- Decision state: EXPLICIT_BLOCKER_PLAN_APPROVED_BATCH

## Evidence

- Readiness report: `reports/phase_restart/sr1_2018_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Raw alignment report: `reports/phase_restart/sr1_2018_phase2_raw_alignment.json`

## Row Findings

- Top blocker reason: `roll maturity sequence not monotonic: backsteps=36`
- Warnings: roll maturity sequence not monotonic: backsteps=36; roll exclusion threshold breached: rows_pct=7.426376 rows=116
- Synthetic rows: 0 of 1562, 0.0%.
- Max synthetic gap minutes: 0
- Roll maturity backsteps: 36
- Status missing/stale rows: 0/0
- Statistics missing/stale rows: 0/0
- Roll maturity examples:
  - 2018-05-10T12:46:00+00:00: previous `SR1M8` maturity 24222, current `SR1K8` maturity 24221.
  - 2018-05-23T11:59:00+00:00: previous `SR1M8` maturity 24222, current `SR1K8` maturity 24221.
  - 2018-06-01T07:52:00+00:00: previous `SR1Q8` maturity 24224, current `SR1N8` maturity 24223.
  - 2018-06-13T18:28:00+00:00: previous `SR1Q8` maturity 24224, current `SR1M8` maturity 24222.
  - 2018-06-19T12:58:00+00:00: previous `SR1V8` maturity 24226, current `SR1M8` maturity 24222.

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
- No canonical causal parquet was written for SR1 2018.
- No policy threshold was changed.
