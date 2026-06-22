# KE 2014 Phase 2 Roll Maturity And Synthetic Review

- Reviewed at UTC: 2026-06-22T15:10:28Z
- Scope: bounded review of the existing KE 2014 Phase 2 readiness-only blocker, including roll maturity examples, synthetic coverage, source/status availability, and raw timestamp metadata.
- Decision state: EXPLICIT_BLOCKER_POLICY_EXCEPTION_SOURCE_STATUS_ROLL_MATURITY_PLAN_APPROVED

## Evidence

- Readiness report: `reports/phase_restart/ke_2014_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Top blocker reason: `roll maturity sequence not monotonic: backsteps=4`
- Warnings:
  - `roll maturity sequence not monotonic: backsteps=4`
  - `synthetic threshold breached: rows_pct=61.854098 max_gap_minutes=119`
- Synthetic rows: 164642 of 266178 output rows, 61.854098%.
- Max synthetic gap: 119 minutes.
- Status enrichment missing rows: 101536.
- Status enrichment stale rows: 101536.
- Statistics enrichment missing rows: 3.
- Statistics enrichment stale rows: 3.

## Roll maturity review

Readiness reported four roll maturity backsteps:

- 2014-03-26T00:00:00+00:00: previous `KEN4` maturity 24175, current `KEK4` maturity 24173.
- 2014-03-28T00:00:00+00:00: previous `KEN4` maturity 24175, current `KEK4` maturity 24173.
- 2014-04-14T00:00:00+00:00: previous `KEN4` maturity 24175, current `KEK4` maturity 24173.
- 2014-08-20T00:00:00+00:00: previous `KEZ4` maturity 24180, current `KEU4` maturity 24177.

Bounded raw metadata check:

- Raw parquet rows: 101536.
- Raw symbols observed: 6.
- Instrument IDs observed: 6.
- Top raw-symbol row counts: `KEZ4` 25461, `KEN4` 21265, `KEU4` 14425, `KEK4` 14138, `KEH5` 13364, `KEH4` 12883.
- Backstep example dates are present in raw data with the current reported symbols and instrument IDs.

## Source/status review

- Canonical OHLCV DBN exists: `data/dbn/ohlcv_1m/KE/2014/2014-01-01_2015-01-01.dbn.zst`, 1238508 bytes.
- Canonical definition DBN exists: `data/dbn/definition/KE/2014/2014-01-01_2015-01-01.dbn.zst`, 2961749 bytes.
- Canonical statistics DBN exists: `data/dbn/statistics/KE/2014/2014-01-01_2015-01-01.dbn.zst`, 484344 bytes.
- Canonical status folder exists but has no DBN files: `data/dbn/status/KE/2014`.
- Parent status folder is absent for KE 2014: `data/dbn/status_parent/KE/2014`.
- Raw timestamp range: 2014-01-02 14:30:00+00:00 through 2014-12-31 19:14:00+00:00.
- Raw duplicate timestamps: 0.
- Raw observed timestamp gaps greater than 1 minute: 22369.
- Raw observed timestamp gaps from 2 to 120 minutes: 22096.
- Raw observed timestamp gaps greater than 120 minutes: 273.
- Max observed raw timestamp gap: 5551 minutes.
- Raw status enrichment columns are present, but `status_missing=true` and `status_stale=true` for all 101536 observed raw rows.
- Raw statistics enrichment has 3 missing/stale observed rows.

## Conclusion

KE 2014 is reviewable but not ready for Phase 2 build execution under the current bounded readiness policy. The readiness blocker is supported by two independent signals:

- roll maturity sequence backsteps that need a separate keep/defer/exception decision;
- sparse observed raw coverage plus missing/stale status enrichment for every observed row, which drove 61.854098% synthetic rows.

Approved bounded review completed. The user approved making this blocker explicit through a bounded policy exception/source-status/roll-maturity plan. This approval records the decision path only; it does not approve Phase 2 build execution, source acquisition, redownload, threshold changes, data repair, merge, move, quarantine, delete, or cleanup.

Approved bounded plan:

1. Keep KE 2014 blocked for Phase 2 build under the current readiness policy.
2. If KE 2014 must be recovered, first pursue a separate explicitly approved source/status acquisition or reconstruction step limited to `data/dbn/status/KE/2014` or equivalent status enrichment evidence.
3. Separately review the four roll maturity backsteps and approve keep/defer/exception handling for the `KEN4 -> KEK4` and `KEZ4 -> KEU4` examples before any build.
4. If source/status evidence cannot be recovered, require a separate explicitly approved KE 2014-only policy exception documenting why sparse observed coverage, 61.854098% synthetic rows, and the four roll maturity backsteps are acceptable.
5. After any acquisition, reconstruction, or exception path, rerun KE 2014 readiness-only before any Phase 2 build.

Stop condition: KE 2014 remains blocked until the bounded source/status and roll-maturity plan is completed and a follow-up readiness-only check passes or is explicitly accepted.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written for KE 2014.
- No policy threshold was changed.
