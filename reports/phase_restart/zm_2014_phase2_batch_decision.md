# ZM 2014 Phase 2 Batch Readiness Decision

- Reviewed at UTC: 2026-06-22T16:25:12Z
- Scope: automated bounded Phase 2 readiness-only review and explicit blocker-plan record.
- Decision state: EXPLICIT_BLOCKER_PLAN_APPROVED_BATCH

## Evidence

- Readiness report: `reports/phase_restart/zm_2014_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Raw alignment report: `reports/phase_restart/zm_2014_phase2_raw_alignment.json`

## Row Findings

- Top blocker reason: `synthetic threshold breached: rows_pct=33.824621 max_gap_minutes=71`
- Warnings: synthetic threshold breached: rows_pct=33.824621 max_gap_minutes=71
- Synthetic rows: 91156 of 269496, 33.824621%.
- Max synthetic gap minutes: 71
- Roll maturity backsteps: 0
- Status missing/stale rows: 178340/178340
- Statistics missing/stale rows: 2/2

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
- No canonical causal parquet was written for ZM 2014.
- No policy threshold was changed.
