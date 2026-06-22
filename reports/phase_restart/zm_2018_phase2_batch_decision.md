# ZM 2018 Phase 2 Batch Readiness Decision

- Reviewed at UTC: 2026-06-22T16:26:45Z
- Scope: automated bounded Phase 2 readiness-only review and explicit blocker-plan record.
- Decision state: EXPLICIT_BLOCKER_PLAN_APPROVED_BATCH

## Evidence

- Readiness report: `reports/phase_restart/zm_2018_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Raw alignment report: `reports/phase_restart/zm_2018_phase2_raw_alignment.json`

## Row Findings

- Top blocker reason: `roll maturity sequence not monotonic: backsteps=1`
- Warnings: roll maturity sequence not monotonic: backsteps=1; synthetic threshold breached: rows_pct=31.000815 max_gap_minutes=47
- Synthetic rows: 84870 of 273767, 31.000815%.
- Max synthetic gap minutes: 47
- Roll maturity backsteps: 1
- Status missing/stale rows: 0/0
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
- No canonical causal parquet was written for ZM 2018.
- No policy threshold was changed.
