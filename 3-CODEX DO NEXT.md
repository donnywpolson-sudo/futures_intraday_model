Refactor raw-ingest data layout only.

Repo:
C:\Users\donny\Desktop\quant_project

Goal:
Make Databento archive/raw layout professional, simple, and unambiguous.

Canonical layout:
- data/dbn/ohlcv_1m/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst
- data/dbn/ohlcv_1m/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst.manifest.json
- data/dbn/definition/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst
- data/dbn/definition/{market}/{year}/{chunk_start}_{chunk_end}.dbn.zst.manifest.json
- data/raw/{market}/{year}.parquet

Meaning:
- data/dbn = immutable Databento vendor archives
- data/dbn/ohlcv_1m = OHLCV-1m DBN archives
- data/dbn/definition = Databento definition/reference DBN archives
- data/raw = immutable converted raw parquet consumed by Phase 2
- reports/raw_ingest = aggregate manifests/reports

Allowed files:
- scripts/raw_ingest/download_databento_raw.py
- tests/raw_ingest/test_download_databento_raw.py
- README.md
- build/project_layout.md
- .gitignore only if needed

Do not modify Phase 2/3/4 logic.
Do not edit or commit generated data files.
Do not move large local data automatically unless implementing a dry-run migration helper.

Required changes:
1. Update raw-ingest defaults:
   - dbn_root = data/dbn/ohlcv_1m
   - definition_root = data/dbn/definition
   - raw_root = data/raw
   - reports_root = reports/raw_ingest

2. Preserve legacy path discovery only:
   - data/raw/{market}/{year}.dbn.zst
   - data/raw/definition/{market}/{year}.dbn.zst
   New DBN outputs must use data/dbn paths.

3. Conversion target remains:
   - data/raw/{market}/{year}.parquet

4. Definitions must never be converted into raw OHLCV parquet.

5. Aggregate reports:
   - reports/raw_ingest/dbn_download_manifest.json
   - reports/raw_ingest/dbn_chunk_manifest.csv
   - reports/raw_ingest/raw_parquet_manifest.json
   - reports/raw_ingest/definition_download_manifest.json if definitions are supported

Tests:
- default OHLCV DBN path is data/dbn/ohlcv_1m/{market}/{year}/{chunk}.dbn.zst
- default definition path is data/dbn/definition/{market}/{year}/{chunk}.dbn.zst
- converted parquet path is data/raw/{market}/{year}.parquet
- legacy data/raw/*.dbn.zst can be discovered for conversion but is not the new output path
- definitions are not converted as OHLCV parquet
- manifests contain expected fields
- generated data/report artifacts remain ignored/untracked

Validation:
python -m pytest tests/raw_ingest -q
python -m pytest -q
python -m scripts.raw_ingest.download_databento_raw --help
git ls-files data reports
git status --short

Stop after reporting changed files, validation results, and final git status.