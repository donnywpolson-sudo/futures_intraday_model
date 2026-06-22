# Phase 1B Smoke

Status: PASS

Scope: manifest-bounded ZN 2023 conversion check using existing canonical-path files with `--resume` and offline local quality conditions.

Command:
```powershell
python -m scripts.phase1B_convert.convert_databento_raw --schema ohlcv-1m --markets ZN --start 2023-01-01 --end 2024-01-01 --chunk year --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/phase_restart/manifest_phase_1b_smoke --workers 1 --resume --offline-local-conditions --include-optional-schemas status,statistics
```

Result:
- Converter status: `ok_existing`.
- Input OHLCV DBN: `data/dbn/ohlcv_1m/ZN/2023/2023-01-01_2024-01-01.dbn.zst`.
- Input definition DBN: `data/dbn/definition/ZN/2023/2023-01-01_2024-01-01.dbn.zst`.
- Canonical raw parquet output: `data/raw/ZN/2023.parquet`.
- Existing raw rows: 335711.
- Failed conversions: 0.
- Required schema/value validation: PASS.
- Evidence: `reports/phase_restart/manifest_phase_1b_smoke/databento_convert_results.json`.
- Additional manifests: `reports/phase_restart/manifest_phase_1b_smoke/raw_ingest_manifest.json`, `reports/phase_restart/manifest_phase_1b_smoke/raw_parquet_manifest.json`.

Safety checks:
- DBN source files modified: no evidence; command reported existing output reuse.
- Deprecated top-level data folders created: no evidence.
- Data mutation check after run: `git status --short -- data` returned no output.
