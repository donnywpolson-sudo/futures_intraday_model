# Canonical Path Summary

Generated at UTC: 2026-06-22T09:08:15.207901+00:00

## Direct Answers

The raw `.dbn.zst` files currently used by the pipeline appear to be:
- `data/dbn/ohlcv_1m`: 533 files, 1.5 GB, coverage 2010-2026; market_year_pairs=532; duplicate_pairs=1.
- `data/dbn/ohlcv_1s` (`ohlcv-1s`): 533 files, 12.3 GB, coverage 2010-2026; market_year_pairs=532; duplicate_pairs=1.
- `data/dbn/ohlcv_1h` (`ohlcv-1h`): 528 files, 65.6 MB, coverage 2010-2026; market_year_pairs=527; duplicate_pairs=1.
- `data/dbn/ohlcv_1d` (`ohlcv-1d`): 528 files, 9.5 MB, coverage 2010-2026; market_year_pairs=527; duplicate_pairs=1.
- `data/dbn/statistics`: 535 files, 668.3 MB, coverage 2010-2026; market_year_pairs=532; duplicate_pairs=3.
- `data/dbn/status`: 465 files, 15.4 MB, coverage 2010-2026; market_year_pairs=462; duplicate_pairs=3.
- `data/dbn/definition`: 533 files, 1.4 GB, coverage 2010-2026; market_year_pairs=532; duplicate_pairs=1.
- `data/dbn/trades`: 67 files, 7.2 GB, coverage 2025-2026; market_year_pairs=66; duplicate_pairs=1.

The intended raw DBN path `data\dbn` is confirmed because Phase 1C defaults to `data/dbn`, Phase 2 consumes the Phase 1C alignment report, `scripts/phase1_raw_contract.py` maps expected schemas to subfolders under that root, and current reports/raw_ingest evidence records `dbn_root=data/dbn` or `data/dbn/ohlcv_1m` for conversion.

The parquet files currently produced by phase 1B appear to be:
- `data/raw/<market>/<year>.parquet`: 517 top-level files, 33 markets, years 2010-2026.
- `reports/raw_ingest/raw_parquet_manifest.json` records `dbn_root=data/dbn/ohlcv_1m` and `raw_root=data/raw`.

The intended converted parquet path `data\raw` is confirmed because Phase 1B defaults `raw_root` to `data/raw`, Phase 1C defaults `--raw-root data/raw`, Phase 2 defaults `--raw-root data/raw`, and top-level `data/raw/<market>/<year>.parquet` exists.

The parquet files currently validated by phase 1C appear to be:
- Top-level `data/raw/<market>/<year>.parquet` files, cross-checked against `data/dbn/ohlcv_1m` and `data/dbn/definition` by `reports/raw_ingest/raw_dbn_alignment.json`.
- Current alignment report status is PASS with `raw_root=data/raw`, `dbn_root=data/dbn`, `expected_market_year_count=461`, `raw_market_year_count=517`, `missing_ohlcv_dbn_count=0`, `missing_definition_dbn_count=0`, and `invalid_manifest_count=0`.

The parquet files currently consumed/produced by phase 2 appear to be:
- Consumed: `data/raw/<market>/<year>.parquet` selected by profile/config and guarded by `reports/raw_ingest/raw_dbn_alignment.json`.
- Produced: `data/causally_gated_normalized/<market>/<year>.parquet`: 461 top-level files, 28 markets, years 2010-2026.
- Current `reports/causal_base/causal_base_manifest.json` exists but is a tier_1/WARN manifest, not a complete tier_3 manifest.

The intended causal normalized path `data\causally_gated_normalized` is confirmed because Phase 2 defaults `--output-root` to that path, `configs/alpha_tiered.yaml` defines `causal_base_root: data/causally_gated_normalized`, and top-level market/year parquet exists there.

These folders appear to be audit/reorg artifacts, not canonical pipeline inputs:
- `data/raw/_full_rebuild_20260621`: 532 parquet files, classification AUDIT_ARTIFACT.
- `data/raw/_repair_candidates`: 24 parquet files, classification STALE_OR_UNKNOWN.
- `data/raw/_smoke_phase_restart_20260621_nooverwrite`: 17 parquet files, classification AUDIT_ARTIFACT.
- `data/raw/_smoke_phase_restart_20260621_tier1refs`: 68 parquet files, classification AUDIT_ARTIFACT.
- `data/raw/_smoke_phase_restart_20260621_tier1refs_2022only`: 4 parquet files, classification AUDIT_ARTIFACT.
- `data/raw/_smoke_phase_restart_20260621_tier1refs_2023only`: 4 parquet files, classification AUDIT_ARTIFACT.
- `data/raw/_smoke_step6_blockerfix_20260621`: 68 parquet files, classification AUDIT_ARTIFACT.
- `data/raw/_smoke_step6_blockerfix_bounded_20260621`: 4 parquet files, classification AUDIT_ARTIFACT.
- `data/raw/_smoke_step6_post_cleanup_20260621`: 4 parquet files, classification AUDIT_ARTIFACT.
- `data/causally_gated_normalized/_diagnostic_zn_synthetic_gaps_20260621`: 3 parquet files, classification AUDIT_ARTIFACT.
- `data/causally_gated_normalized/_repair_candidates`: 2 parquet files, classification STALE_OR_UNKNOWN.
- `data/causally_gated_normalized/_smoke_phase_restart_20260621_gatefix`: 1 parquet files, classification AUDIT_ARTIFACT.
- `data/causally_gated_normalized/_smoke_phase_restart_20260621_no_zn`: 3 parquet files, classification AUDIT_ARTIFACT.
- `data/causally_gated_normalized/_smoke_phase_restart_20260621_nooverwrite`: 1 parquet files, classification AUDIT_ARTIFACT.
- `data/causally_gated_normalized/_smoke_phase_restart_20260621_vendor_trusted_zn2024`: 4 parquet files, classification AUDIT_ARTIFACT.
- `data/causally_gated_normalized/_smoke_step6_blockerfix_bounded_20260621`: 4 parquet files, classification AUDIT_ARTIFACT.
- `data/causally_gated_normalized/_smoke_step6_post_cleanup_20260621`: 4 parquet files, classification AUDIT_ARTIFACT.
- `reports/data_reorg/*` and `reports/phase_restart/*`: report evidence only, not canonical data inputs.

These paths remain ambiguous and require review:
- `data/dbn/ohlcv_1m_parent`: 42 DBN files, classification DO_NOT_TOUCH; source-like parent folder but not active default schema path.
- `data/dbn/statistics_parent`: 41 DBN files, classification DO_NOT_TOUCH; source-like parent folder but not active default schema path.
- `data/dbn/status_parent`: 41 DBN files, classification DO_NOT_TOUCH; source-like parent folder but not active default schema path.
- `data/raw/_repair_candidates`: 24 parquet files, classification STALE_OR_UNKNOWN.
- `data/causally_gated_normalized/_repair_candidates`: 2 parquet files, classification STALE_OR_UNKNOWN.

Expected vs actual market/schema/year coverage summary:
- Expected market universe from `configs/alpha_tiered.yaml` / Phase 2 constants: 33 markets.
- Expected market-year pairs after Phase 1A product starts through 2026: 527; trades expected pairs for 2025-2026 only: 66.
- `data/dbn/ohlcv_1m`: actual 532/527 pairs, missing 0, extra 5, duplicates 1.
- `data/dbn/ohlcv_1s` (`ohlcv-1s`): actual 532/527 pairs, missing 0, extra 5, duplicates 1.
- `data/dbn/ohlcv_1h` (`ohlcv-1h`): actual 527/527 pairs, missing 0, extra 0, duplicates 1.
- `data/dbn/ohlcv_1d` (`ohlcv-1d`): actual 527/527 pairs, missing 0, extra 0, duplicates 1.
- `data/dbn/statistics`: actual 532/527 pairs, missing 0, extra 5, duplicates 3.
- `data/dbn/status`: actual 462/527 pairs, missing 68, extra 3, duplicates 3.
- `data/dbn/definition`: actual 532/527 pairs, missing 0, extra 5, duplicates 1.
- `data/dbn/trades`: actual 66/66 pairs, missing 0, extra 0, duplicates 1.
- `data/raw/<market>/<year>.parquet`: actual 517/527 pairs, missing 10, extra 0, duplicates 0.
- `data/causally_gated_normalized/<market>/<year>.parquet`: actual 461/527 pairs, missing 66, extra 0, duplicates 0.

See `raw_dbn_candidates.csv`, `parquet_candidates.csv`, and `expected_vs_actual_coverage.csv` for structured details.
