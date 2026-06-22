# Data Manifest Coverage Summary

Generated at UTC: 2026-06-22T23:10:21.385561+00:00

## Verdict

- Manifest market cross-check: PASS
- Cleanup/quarantine allowed: false
- Cleanup gate: No cleanup/quarantine until UNKNOWN and policy-deferred paths are reviewed.
- Coverage CSV rows read: 10
- Issue rows written: 168

## Missing Pairs

- `data/raw/{market}/{year}.parquet`: expected missing 0; unexpected missing 0.
- `data/causally_gated_normalized/{market}/{year}.parquet`: expected missing 0; unexpected missing 66.
- `data/dbn/status`: expected missing 67; unexpected missing 0.

## Extras And Duplicates

- `data/dbn/definition`: allowed extras 5; unexpected extras 0; known policy-deferred duplicates 1; unexpected duplicates 0.
- `data/dbn/ohlcv_1d`: allowed extras 0; unexpected extras 0; known policy-deferred duplicates 1; unexpected duplicates 0.
- `data/dbn/ohlcv_1h`: allowed extras 0; unexpected extras 0; known policy-deferred duplicates 1; unexpected duplicates 0.
- `data/dbn/ohlcv_1m`: allowed extras 5; unexpected extras 0; known policy-deferred duplicates 1; unexpected duplicates 0.
- `data/dbn/ohlcv_1s`: allowed extras 5; unexpected extras 0; known policy-deferred duplicates 1; unexpected duplicates 0.
- `data/dbn/statistics`: allowed extras 5; unexpected extras 0; known policy-deferred duplicates 3; unexpected duplicates 0.
- `data/dbn/status`: allowed extras 3; unexpected extras 0; known policy-deferred duplicates 3; unexpected duplicates 0.
- `data/dbn/trades`: allowed extras 0; unexpected extras 0; known policy-deferred duplicates 1; unexpected duplicates 0.

## Cleanup Exclusions

- `data/dbn/ohlcv_1m_parent`: DO_NOT_TOUCH - Source-like parent DBN folder; redundancy not proven.
- `data/dbn/statistics_parent`: DO_NOT_TOUCH - Source-like parent DBN folder; redundancy not proven.
- `data/dbn/status_parent`: DO_NOT_TOUCH - Source-like parent DBN folder; redundancy not proven.
- `data/raw/_repair_candidates`: STALE_OR_UNKNOWN - Repair candidate parquet folder needs explicit review.
- `data/causally_gated_normalized/_repair_candidates`: STALE_OR_UNKNOWN - Repair candidate parquet folder needs explicit review.

## UNKNOWN / Policy-Deferred Paths

- `data/raw/_repair_candidates`: STALE_OR_UNKNOWN
- `data/causally_gated_normalized/_repair_candidates`: STALE_OR_UNKNOWN

Exact pair-level issues are in `reports/data_manifest/manifest_coverage_check.csv`.
