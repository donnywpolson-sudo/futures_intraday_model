# Data Workflow Readiness Plan

- Generated at UTC: 2026-06-23T01:28:25Z
- Scope: report-only workflow definition for the Databento futures data pipeline.
- Safety: no download, repair, Phase 2 build, cleanup, move, merge, quarantine, delete, rebuild, redownload, or data mutation was run for this document.
- Contract sources: `configs/data_manifest.yaml`, `configs/alpha_tiered.yaml`, `reports/data_lineage/pipeline_phase_io_map.md`, `reports/data_manifest/manifest_coverage_summary.md`, `reports/data_manifest/master_data_health_summary.md`, and `reports/data_reorg/l0_trades_ohlcv_overlap_summary.md`.

## Readiness Terms

`source-ready` means the canonical DBN source inputs for a market/year/schema are present under `data/dbn`, match the manifest path contract, have stable provenance evidence, and any missing optional source is explicitly accepted, deferred, or excluded. Source-ready is not the same as raw-ready or model-ready.

`raw-ready` means the market/year has a canonical raw parquet file at `data/raw/{market}/{year}.parquet`, produced from canonical DBN sources, with one consistent raw parquet schema per market-year. It also requires source-reference/hash evidence, required columns, no duplicate raw keys, and accepted handling for optional status/statistics gaps.

`Phase2-ready` means the raw-ready market/year can be causally normalized into `data/causally_gated_normalized/{market}/{year}.parquet` without unresolved readiness blockers. Excluded/deferred rows are not Phase2-ready unless a later explicit policy exception accepts them.

`model-ready` means the row is safe to feed downstream modeling. A row is not fully model-ready until source-ready, raw-ready, and Phase2-ready gates are satisfied or every remaining caveat is explicitly accepted. The full dataset is not model-ready until optional-schema failures, excluded/deferred rows, duplicates, and Phase 2 blockers are resolved or explicitly accepted.

## Workflow

1. Download L0 DBN sources.
   - Inputs: Databento Historical API, dataset/profile defined by the repo configs.
   - Schemas: `ohlcv-1m`, `statistics`, `definition`, and `status`.
   - Universe: 33 tier-3 research futures markets from `configs/data_manifest.yaml`, years 2010-2026, with configured later starts for markets such as `KE`, `RTY`, `SR1`, `SR3`, `TN`, `ZL`, and `ZM`.
   - Output: `data/dbn/<schema_path>/<market>/<year>/<start>_<end>.dbn.zst`.
   - Gate after DBN download: mark source-ready only when expected DBN paths exist, schema/market/year windows match the manifest, sidecar/provenance evidence exists where required, duplicates are identified, missing optional sources are policy-accounted, and DBN source files remain immutable.

2. Download L1 trade DBN sources for local OHLCV overlap validation.
   - Schema: `trades`.
   - Universe: 33 tier-3 research markets for the locally downloaded validation window.
   - Output: `data/dbn/trades/<market>/<year>/<start>_<end>.dbn.zst`.
   - Current local trade-validation window: `2025-06-18` to `2026-06-13` using the existing DBN chunk convention.
   - Gate after trade DBN download: trade DBNs are source-ready only for the downloaded window; they do not prove full-history OHLCV correctness outside that window.

3. Convert DBN to raw parquet.
   - Phase/script: Phase 1B, `scripts/phase1B_convert/convert_databento_raw.py`.
   - Inputs: canonical `ohlcv-1m` DBN plus `definition`; optional enrichment from `status` and `statistics` when present and joinable.
   - Output: `data/raw/{market}/{year}.parquet`.
   - Important schema rule: do not create "one giant schema" or one giant physical file. The target is one consistent raw parquet schema per market-year, with comparable columns and provenance fields across rows.
   - Gate after raw parquet conversion: require a readable parquet file, expected raw schema, stable row keys, source file references, source hashes where available, and explicit handling for missing/non-joinable optional status/statistics.

4. Validate raw alignment.
   - Phase/script: Phase 1C, `scripts/phase1C_validate/audit_raw_dbn_alignment.py`.
   - Inputs: `data/dbn/<ohlcv_1m|definition>/<market>/<year>/*.dbn.zst` and `data/raw/{market}/{year}.parquet`.
   - Output evidence: raw/DBN alignment reports under `reports/raw_ingest`.
   - Gate after raw alignment: raw row counts, timestamps, instrument IDs/symbols, source paths, and synthetic/missing-row flags must be explainable and causal. Synthetic rows are acceptable only when flagged, distinguishable from observed rows, and accepted by policy.

5. Validate trade/OHLCV overlap where local trades exist.
   - Project policy treats Databento OHLCV as vendor-trusted for the full history.
   - Local trade-vs-OHLCV validation only directly covers the downloaded trades window: `2025-06-18` to `2026-06-13`.
   - Gate after trade/OHLCV overlap validation: inside the trade window, missing OHLCV minutes must be supported by no-trade evidence or a documented timestamp-basis explanation. Outside the trade window, do not claim local trade proof; rely on vendor-trusted OHLCV policy plus DBN/raw alignment evidence.

6. Build causally gated normalized parquet.
   - Phase/script: Phase 2, `scripts/phase2_causal_base/build_causal_base_data.py`.
   - Inputs: raw-ready `data/raw/{market}/{year}.parquet`, profile settings, and raw-alignment guard evidence.
   - Output: `data/causally_gated_normalized/{market}/{year}.parquet`.
   - Gate after Phase 2 causal normalization: require no future-looking joins, accepted roll maturity behavior, accepted synthetic-row rates/gaps, observed-row eligibility where required, validation manifest output, and no unresolved Phase 2 readiness blocker for included rows.

7. Promote to model-ready.
   - Inputs: only rows that passed or were explicitly accepted through source-ready, raw-ready, and Phase2-ready gates.
   - Required before full-dataset model use: optional-schema failures resolved or accepted, excluded/deferred rows resolved or excluded by policy, duplicates explicitly kept/merged/quarantined/deferred by approved policy, and Phase 2 blockers cleared or explicitly accepted.
   - Cleanup remains disabled until blockers are zero and cleanup is separately approved.

## Current Caveats To Preserve

- `reports/data_manifest/manifest_coverage_summary.md` is the source for current manifest coverage counts.
- `reports/data_manifest/master_data_health_summary.md` and `reports/data_manifest/master_data_health_matrix.csv` are the source for source/raw health classes.
- `reports/phase_restart/batch_phase2_build_exclusion_plan.md` is the source for current Phase 2 inclusion/exclusion decisions.
- `reports/data_reorg/l0_trades_ohlcv_overlap_summary.md` is the source for the local trade/OHLCV overlap caveat.
- This workflow plan does not make the dataset model-ready by itself; it only defines the gates needed to call data source-ready, raw-ready, Phase2-ready, and model-ready.

## Explicit Non-Actions

- No Databento download or redownload.
- No raw repair or re-enrichment.
- No Phase 2 build.
- No cleanup.
- No duplicate merge, move, quarantine, delete, or overwrite.
- No DBN source modification.
