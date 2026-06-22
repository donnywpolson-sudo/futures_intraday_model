# SR1 2022 Phase 1B Canonical Raw Repair Evidence

- Generated at UTC: 2026-06-22T16:13:07Z
- Scope: bounded Phase 1B raw repair from canonical DBN after source-hash alignment mismatch.
- Decision state: CANONICAL_RAW_REPAIRED_PHASE2_READINESS_PENDING

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2022/2022-01-01_2023-01-01.dbn.zst`
- Input OHLCV DBN SHA256: `1971166098d84a83bcacea35f2c125e4c7090aa8f1fb7910fe07455724bc8f91`
- Input definition DBN: `data/dbn/definition/SR1/2022/2022-01-01_2023-01-01.dbn.zst`
- Input definition DBN SHA256: `f4163c6e09058fed181022fcc392654062b72165ae43f6d347b8231b4693c5be`
- Previous raw SHA256: `557a9ed1007a50974458ef96e879e3ae3acce4c21c59eace0de1acf6e7e81350`
- Repaired raw SHA256: `db101c054bd736ffaf5d574c40c08ec60225f3f78d594b113b170d938750b875`
- Phase 1C repair alignment: `reports/phase_restart/sr1_2022_phase1c_raw_repair_alignment.json`

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written.
- No generated data artifacts were staged.
