# SR1 2021 Phase 1B Canonical Raw Repair Evidence

- Generated at UTC: 2026-06-22T16:12:55Z
- Scope: bounded Phase 1B raw repair from canonical DBN after source-hash alignment mismatch.
- Decision state: CANONICAL_RAW_REPAIRED_PHASE2_READINESS_PENDING

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2021/2021-01-01_2022-01-01.dbn.zst`
- Input OHLCV DBN SHA256: `40cb36228e8ed989b54d00da715247a1d736d6ff6983f33ee8cb6e977db61b2f`
- Input definition DBN: `data/dbn/definition/SR1/2021/2021-01-01_2022-01-01.dbn.zst`
- Input definition DBN SHA256: `511aa1f16595feba0e2ed49ee43c7de65702db6d3e9401de22cf187c6fa94de9`
- Previous raw SHA256: `88db91c027fab6d5a104f4f030328a644eec63326b8747aa3f3498e6a0e4cb6a`
- Repaired raw SHA256: `3cb9d8e3e44d8ed1d1a811571824c30efc2a7ac4ce82148ff48770d5032779ba`
- Phase 1C repair alignment: `reports/phase_restart/sr1_2021_phase1c_raw_repair_alignment.json`

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written.
- No generated data artifacts were staged.
