# SR1 2020 Phase 1B Canonical Raw Repair Evidence

- Generated at UTC: 2026-06-22T16:12:42Z
- Scope: bounded Phase 1B raw repair from canonical DBN after source-hash alignment mismatch.
- Decision state: CANONICAL_RAW_REPAIRED_PHASE2_READINESS_PENDING

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2020/2020-01-01_2021-01-01.dbn.zst`
- Input OHLCV DBN SHA256: `3ea62d9e4a384ef70d812c7d0c7d97d1d1aa88924c45c98f8ea92bfb05aa3607`
- Input definition DBN: `data/dbn/definition/SR1/2020/2020-01-01_2021-01-01.dbn.zst`
- Input definition DBN SHA256: `9d56e4e5b4adfde0e8c963769d5c802612ff67e30e4469ccd70a39dc08728030`
- Previous raw SHA256: `1803cb3e2864cce1795b13547ff0557a6e75a925883899babbb3f90df7726a6c`
- Repaired raw SHA256: `9d57a7f37b4baad118eeffec2206b3eba9098ed61ee014c56d13f3a96f8571fc`
- Phase 1C repair alignment: `reports/phase_restart/sr1_2020_phase1c_raw_repair_alignment.json`

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written.
- No generated data artifacts were staged.
