# SR3 2019 Source-Reference Correction

- Updated at UTC: 2026-06-23T00:13:05Z.
- Scope: one bounded Phase 1B local conversion/source-reference correction for `SR3:2019`.
- Selected row: `SR3:2019`.
- Reason selected: first `APPROVE_SOURCE_REFERENCE_CORRECTION_LATER` row in `reports/data_manifest/unknown_review_decision_packet.md`.
- Input OHLCV DBN: `data/dbn/ohlcv_1m/SR3/2019/2019-01-01_2020-01-01.dbn.zst`.
- Optional status DBN: `data/dbn/status/SR3/2019/2019-01-01_2020-01-01.dbn.zst`.
- Optional statistics DBN: `data/dbn/statistics/SR3/2019/2019-01-01_2020-01-01.dbn.zst`.
- Output raw parquet: `data/raw/SR3/2019.parquet`.

## Commands Run

```powershell
git push origin main
python -m scripts.phase1B_convert.convert_databento_raw --mode convert-parquet --schema ohlcv-1m --markets SR3 --start 2019-01-01 --end 2020-01-01 --chunk year --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/phase_restart/sr3_2019_source_reference_correction --include-optional-schemas status,statistics --optional-dbn-root data/dbn --optional-schema-policy warn --offline-local-conditions --workers 1 --overwrite
python -m scripts.validation.audit_enriched_raw_optional_schemas --raw-root data/raw --dbn-root data/dbn --json-out reports/raw_readiness/raw_enriched_optional_schema_audit.json --md-out reports/raw_readiness/raw_enriched_optional_schema_audit.md
git status --short -- data
```

## Results

- Push result: `75b5453` pushed to `origin/main`.
- Conversion result: `CONVERT_OK market=SR3 year=2019 inputs=1 output=data/raw/SR3/2019.parquet rows=4608`.
- Optional-schema audit overall status: `FAIL`, because 22 unrelated rows still fail.
- `SR3:2019` audit status: `PASS`.
- `SR3:2019` source reference failures after correction: 0.
- `SR3:2019` source hash mismatch count after correction: 0.
- `SR3:2019` remaining optional caveat: status enrichment has 17 missing/stale rows, but this is not a source-reference failure.
- File failure count changed from 23 to 22.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No phase 3+ command was run.
- No redownload was run.
- DBN source files were not modified.
- No data files were deleted, moved, merged, quarantined, or staged.
- `git status --short -- data` was empty after the correction.
