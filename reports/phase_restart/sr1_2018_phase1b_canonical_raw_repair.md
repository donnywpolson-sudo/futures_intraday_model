# SR1 2018 Phase 1B Canonical Raw Repair Evidence

- Generated at UTC: 2026-06-22T16:00:46Z
- Scope: bounded Phase 1B raw repair for SR1 2018 from the canonical DBN source.
- Decision state: CANONICAL_RAW_REPAIRED_PHASE2_READINESS_NOT_RUN

## Reason

SR1 2018 Phase 2 batch automation stopped because the existing raw parquet was traceable to a quarantined parent-candidate DBN, not the current canonical DBN contract.

Approved action: repair only `data/raw/SR1/2018.parquet` from `data/dbn/ohlcv_1m/SR1/2018/2018-04-23_2019-01-01.dbn.zst`, then stop before Phase 2 readiness/build.

## Commands

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --symbols SR1 --start 2018-04-23 --end 2019-01-01 --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/raw_ingest --workers 1 --resume --offline-local-conditions --overwrite
```

Result: `CONVERT_OK market=SR1 year=2018 inputs=1 output=data/raw/SR1/2018.parquet rows=1562`; `CONVERT_PARQUET total=1 failed=0`.

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/sr1_2018_raw_repair_alpha_tiered.yaml --profile raw_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/sr1_2018_phase1c_raw_repair_alignment.json --md-out reports/phase_restart/sr1_2018_phase1c_raw_repair_alignment.md
```

Result: `status=PASS expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports/phase_restart/sr1_2018_phase2_causal_repair.yaml --profile phase2_repair --dbn-root data/dbn --raw-root data/raw --expected-only --json-out reports/phase_restart/sr1_2018_phase2_raw_alignment.json --md-out reports/phase_restart/sr1_2018_phase2_raw_alignment.md
```

Result: `status=PASS expected=1 raw=1 needs_phase1b=0 raw_only=0 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=checked definition_join_mismatches=0`.

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2018/2018-04-23_2019-01-01.dbn.zst`.
- Input OHLCV DBN SHA256: `7830e41d9da6a7753d309a38d09bea12deaa08bda72ef18b3f5ee379adf0d2d7`.
- Input definition DBN: `data/dbn/definition/SR1/2018/2018-04-23_2019-01-01.dbn.zst`.
- Input definition DBN SHA256: `73621e11d540ffe9f8a8a08e7f2415cc226bafadf117a7761d7b5b21e0484c58`.
- Previous raw parquet SHA256: `b21e7bce76fba22c3a11330ff387e706232d3ee91837306976c1ca8291e27fb8`.
- Repaired raw parquet SHA256: `a521c825963887c0e0649002de57e0775dd92ae908bd9a51d2722537f5e867a5`.
- Repaired raw parquet rows: 1562.
- Repaired raw parquet columns: 25.
- Repaired raw source file: `data/dbn/ohlcv_1m/SR1/2018/2018-04-23_2019-01-01.dbn.zst`.
- Repaired raw source SHA256: `7830e41d9da6a7753d309a38d09bea12deaa08bda72ef18b3f5ee379adf0d2d7`.
- Repaired raw timestamp range: 2018-05-06 22:09:00+00:00 through 2018-12-31 18:36:00+00:00.
- Repaired raw duplicate timestamps: 0.
- Canonical causal output exists: false.

## Safety

- No Phase 2 readiness-only command was run after this repair.
- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written for SR1 2018.
- No generated data artifacts were staged.
