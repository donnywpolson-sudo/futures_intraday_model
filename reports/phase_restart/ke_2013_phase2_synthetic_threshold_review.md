# KE 2013 Phase 2 Synthetic Threshold Review

- Reviewed at UTC: 2026-06-22T15:00:51Z
- Scope: bounded review of the existing KE 2013 Phase 2 readiness-only blocker, including source/status availability and raw timestamp metadata.
- Decision state: EXPLICIT_BLOCKER_POLICY_EXCEPTION_OR_SOURCE_STATUS_PLAN_APPROVED

## Evidence

- Readiness report: `reports/phase_restart/ke_2013_phase2_readiness.json`
- Readiness status: `FAIL`
- Checked market-years: 1
- Blockers: 1
- Failures: 0
- Blocker reason: `synthetic threshold breached: rows_pct=59.633118 max_gap_minutes=105`
- Synthetic rows: 6014 of 10085 output rows, 59.633118%.
- Max synthetic gap: 105 minutes.
- Status enrichment available: true.
- Status enrichment missing rows: 4071.
- Status enrichment stale rows: 4071.
- Statistics enrichment available: true.
- Statistics enrichment missing rows: 0.
- Statistics enrichment stale rows: 0.

## Source/status review

- Canonical OHLCV DBN exists: `data/dbn/ohlcv_1m/KE/2013/2013-01-01_2014-01-01.dbn.zst`, 44772 bytes.
- Canonical definition DBN exists: `data/dbn/definition/KE/2013/2013-01-01_2014-01-01.dbn.zst`, 137560 bytes.
- Canonical statistics DBN exists: `data/dbn/statistics/KE/2013/2013-01-01_2014-01-01.dbn.zst`, 13892 bytes.
- Canonical status folder exists but has no DBN files: `data/dbn/status/KE/2013`.
- Parent status folder is absent for KE 2013: `data/dbn/status_parent/KE/2013`.
- Raw parquet rows: 4071.
- Raw timestamp range: 2013-12-16 01:00:00+00:00 through 2013-12-31 19:14:00+00:00.
- Raw duplicate timestamps: 0.
- Raw observed timestamp gaps greater than 1 minute: 696.
- Raw observed timestamp gaps from 2 to 120 minutes: 680.
- Raw observed timestamp gaps greater than 120 minutes: 16.
- Max observed raw timestamp gap: 3226 minutes.
- Raw status enrichment columns are present, but `status_missing=true` and `status_stale=true` for all 4071 observed raw rows.
- Raw statistics enrichment columns are present and complete for the observed raw rows.

## Conclusion

KE 2013 is not ready for Phase 2 build execution under the current bounded readiness policy. The source/status review supports the readiness blocker: the raw file has sparse observed coverage, the readiness command filled 6014 synthetic rows, and no canonical status DBN file is available to confirm status enrichment for the observed rows.

The user approved making this blocker explicit through a bounded policy-exception/source-status acquisition plan. This approval records the decision path only; it does not approve data acquisition, redownload, threshold changes, source reconstruction, Phase 2 build execution, or cleanup.

Approved bounded plan:

1. Keep KE 2013 blocked for Phase 2 build under the current readiness policy.
2. If KE 2013 must be recovered, first pursue a separate explicitly approved source/status acquisition or reconstruction step limited to `data/dbn/status/KE/2013` or equivalent status enrichment evidence.
3. If source/status evidence cannot be recovered, require a separate explicitly approved KE 2013-only policy exception documenting why sparse observed coverage and 59.633118% synthetic rows are acceptable.
4. After either path, rerun KE 2013 readiness-only before any Phase 2 build.

Stop condition: KE 2013 remains blocked until a separate approved acquisition/reconstruction step or policy exception is completed and a follow-up readiness-only check passes or is explicitly accepted.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written for KE 2013.
- No policy threshold was changed.
