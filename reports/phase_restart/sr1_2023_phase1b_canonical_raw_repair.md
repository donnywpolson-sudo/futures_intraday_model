# SR1 2023 Phase 1B Canonical Raw Repair Evidence

- Generated at UTC: 2026-06-22T16:13:22Z
- Scope: bounded Phase 1B raw repair from canonical DBN after source-hash alignment mismatch.
- Decision state: CANONICAL_RAW_REPAIRED_PHASE2_READINESS_PENDING

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2023/2023-01-01_2024-01-01.dbn.zst`
- Input OHLCV DBN SHA256: `6239cb3b582376570f8ca45622bad6f3f327f42174a587203ea21442094d8ac6`
- Input definition DBN: `data/dbn/definition/SR1/2023/2023-01-01_2024-01-01.dbn.zst`
- Input definition DBN SHA256: `e6c82f8595176b5647e9b6b16723a6bd2c66579b9194166efda44633004326e8`
- Previous raw SHA256: `749330f86067148427edfaf9763a2367ab66725b05b1ab87e6ddcd488945ece6`
- Repaired raw SHA256: `6499b9a979c89de4bbbf0c932c5695010d5f7f6a7f2d658d8a593826cec92248`
- Phase 1C repair alignment: `reports/phase_restart/sr1_2023_phase1c_raw_repair_alignment.json`

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written.
- No generated data artifacts were staged.
