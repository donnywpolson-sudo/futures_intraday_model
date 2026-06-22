# SR1 2019 Phase 1B Canonical Raw Repair Evidence

- Generated at UTC: 2026-06-22T16:12:30Z
- Scope: bounded Phase 1B raw repair from canonical DBN after source-hash alignment mismatch.
- Decision state: CANONICAL_RAW_REPAIRED_PHASE2_READINESS_PENDING

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2019/2019-01-01_2020-01-01.dbn.zst`
- Input OHLCV DBN SHA256: `3883ae30e71a17d1273ea103280eedd2af8eceb89415aae3caabd919667f610f`
- Input definition DBN: `data/dbn/definition/SR1/2019/2019-01-01_2020-01-01.dbn.zst`
- Input definition DBN SHA256: `3831f2eebaa6dd868cdd372bc3bf9a758a4297fb657d696b466456fddc5dc05e`
- Previous raw SHA256: `1940c048947bcd218fe1a1b9c636aea8820272fc7bb2a2ab0401578f430a7594`
- Repaired raw SHA256: `be201f9d217a828d6968857df15c7f6e72e434511182b8019ccd5757a9cb14d4`
- Phase 1C repair alignment: `reports/phase_restart/sr1_2019_phase1c_raw_repair_alignment.json`

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written.
- No generated data artifacts were staged.
