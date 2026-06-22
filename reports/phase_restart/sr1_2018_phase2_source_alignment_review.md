# SR1 2018 Phase 2 Source Alignment Review

- Reviewed at UTC: 2026-06-22T15:33:00Z
- Scope: bounded source-alignment review for SR1 2018 after Phase 1C precheck blocked Phase 2 readiness-only.
- Decision state: CANONICAL_DBN_TRUSTED_RAW_REQUIRES_REPAIR_OR_EXCEPTION

## Alignment Failure

- Alignment report: `reports/phase_restart/sr1_2018_phase2_raw_alignment.json`
- Alignment status: `FAIL`
- Failure: `source hash mismatches: 1`
- Raw path: `data/raw/SR1/2018.parquet`
- Raw rows: 1357
- Raw duplicate timestamps: 0
- Raw timestamp range: 2018-05-06 22:09:00+00:00 through 2018-12-31 17:21:00+00:00
- Raw instrument IDs observed: 8
- Raw status missing/stale rows: 0 / 0
- Raw statistics missing/stale rows: 0 / 0

## Raw Recorded Source

- Raw recorded source file: `data/dbn_sr_parent_candidate/SR1/2018/2018-04-23_2019-01-01.dbn.zst`
- Raw recorded source SHA256: `42d2be31d9151f09d6cf84d2a8a30aa10f6d1fe5fe6a8d1188dd5d9ab5ca6e9b`
- The original `data/dbn_sr_parent_candidate` path is no longer under `data/`.
- Prior cleanup evidence records `data/dbn_sr_parent_candidate` moved to `_data_reorg_quarantine20260621T222448Z/dbn_sr_parent_candidate`.
- Quarantined candidate file exists and matches the raw recorded hash:
  - path: `_data_reorg_quarantine20260621T222448Z/dbn_sr_parent_candidate/SR1/2018/2018-04-23_2019-01-01.dbn.zst`
  - size: 81994 bytes
  - SHA256: `42d2be31d9151f09d6cf84d2a8a30aa10f6d1fe5fe6a8d1188dd5d9ab5ca6e9b`
- Quarantined candidate manifest:
  - dataset: `GLBX.MDP3`
  - schema: `ohlcv-1m`
  - symbols requested: `SR1.FUT`
  - `stype_in`: `parent`
  - `stype_out`: `instrument_id`
  - downloaded at: `2026-06-20T18:04:29.479366+00:00`

## Current Canonical Source

- Canonical DBN path: `data/dbn/ohlcv_1m/SR1/2018/2018-04-23_2019-01-01.dbn.zst`
- Canonical DBN exists.
- Canonical DBN size: 23514 bytes.
- Canonical DBN SHA256: `7830e41d9da6a7753d309a38d09bea12deaa08bda72ef18b3f5ee379adf0d2d7`
- Canonical manifest:
  - dataset: `GLBX.MDP3`
  - schema: `ohlcv-1m`
  - symbols requested: `SR1.v.0`
  - `stype_in`: `continuous`
  - `stype_out`: `instrument_id`
  - downloaded at: `2026-06-18T03:07:58.764098+00:00`
- Data reorg evidence classifies `data/dbn` as canonical and `data/dbn_sr_parent_candidate` as noncanonical/quarantined.

## Trust Decision

For the current canonical pipeline contract, the trusted source is the canonical DBN under `data/dbn/ohlcv_1m/SR1/2018`, not the existing raw parquet.

The existing raw parquet is internally traceable to the quarantined parent-candidate DBN, so it is not arbitrary or unexplained. However, it is not aligned to the current canonical DBN contract because it was built from a different source file, symbol request, and `stype_in`.

## Approved Plan

SR1 2018 remains blocked before Phase 2 readiness/build until the user separately approves one of:

1. Bounded Phase 1B raw repair for SR1 2018 from the current canonical DBN, followed by Phase 1C alignment.
2. Explicit SR1 2018 exception accepting the parent-candidate raw source for readiness-only despite the canonical mismatch.
3. Explicit deferral of SR1 2018 so the Phase 2 readiness batch can continue with later rows.

## Safety

- No Phase 2 readiness-only command was run for SR1 2018 after the failed alignment precheck.
- No Phase 2 build was run.
- No cleanup was run.
- No repair was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written for SR1 2018.
- No generated data artifacts were staged.
