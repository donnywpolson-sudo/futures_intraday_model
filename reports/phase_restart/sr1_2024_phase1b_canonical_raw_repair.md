# SR1 2024 Phase 1B Canonical Raw Repair Evidence

- Generated at UTC: 2026-06-22T16:13:38Z
- Scope: bounded Phase 1B raw repair from canonical DBN after source-hash alignment mismatch.
- Decision state: CANONICAL_RAW_REPAIRED_PHASE2_READINESS_PENDING

## Evidence

- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR1/2024/2024-01-01_2025-01-01.dbn.zst`
- Input OHLCV DBN SHA256: `646f5c5cb6885874ddc689bed0348fc340c2a7d0f7bb589cebd39742aadea430`
- Input definition DBN: `data/dbn/definition/SR1/2024/2024-01-01_2025-01-01.dbn.zst`
- Input definition DBN SHA256: `0d5ee931b9ea0ea054b6d87459448d53856049639e7da9bcf222719bf9eda0df`
- Previous raw SHA256: `25873fcb0e27ce5c349c8ade58f246fafdca0f4035936ce380b868b2a9c748d4`
- Repaired raw SHA256: `e69463810771f9a07755e4db5549903d0f2cbdb77266314bcc7b1d8384126189`
- Phase 1C repair alignment: `reports/phase_restart/sr1_2024_phase1c_raw_repair_alignment.json`

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No canonical causal parquet was written.
- No generated data artifacts were staged.
