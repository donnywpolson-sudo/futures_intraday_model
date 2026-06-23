# SR3 2020 Source-Reference Correction

- Updated at UTC: 2026-06-23T00:24:36Z.
- Scope: one bounded Phase 1B local conversion/source-reference correction for `SR3:2020`.
- Selected row: `SR3:2020`.
- Reason selected: next `APPROVE_SOURCE_REFERENCE_CORRECTION_LATER` row after `SR3:2019` in `reports/data_manifest/unknown_review_decision_packet.md`.
- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR3/2020/2020-01-01_2021-01-01.dbn.zst`.
- Optional status DBN: `data/dbn/status/SR3/2020/2020-01-01_2021-01-01.dbn.zst`.
- Optional statistics DBN: `data/dbn/statistics/SR3/2020/2020-01-01_2021-01-01.dbn.zst`.
- Output raw parquet: `data/raw/SR3/2020.parquet`.

## Commands Run

```powershell
python -m scripts.phase1B_convert.convert_databento_raw --mode convert-parquet --schema ohlcv-1m --markets SR3 --start 2020-01-01 --end 2021-01-01 --chunk year --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/phase_restart/sr3_2020_source_reference_correction --include-optional-schemas status,statistics --optional-dbn-root data/dbn --optional-schema-policy warn --offline-local-conditions --workers 1 --overwrite
python -m scripts.validation.audit_enriched_raw_optional_schemas --raw-root data/raw --dbn-root data/dbn --json-out reports/raw_readiness/raw_enriched_optional_schema_audit.json --md-out reports/raw_readiness/raw_enriched_optional_schema_audit.md
git status --short -- data
```

## Results

- Conversion result: `CONVERT_OK market=SR3 year=2020 inputs=1 output=data/raw/SR3/2020.parquet rows=10630`.
- Optional-schema audit overall status: `FAIL`, because 21 unrelated rows still fail.
- `SR3:2020` audit status: `PASS`.
- `SR3:2020` source reference failures after correction: 0.
- `SR3:2020` source hash mismatch count after correction: 0.
- `SR3:2020` remaining optional caveats: status enrichment has 168 missing/stale rows; statistics enrichment has 25 missing/stale rows. These are not source-reference failures.
- File failure count changed from 22 to 21.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No phase 3+ command was run.
- No redownload was run.
- DBN source files were not modified.
- No data files were deleted, moved, merged, quarantined, or staged.
- `git status --short -- data` was empty after the correction.
