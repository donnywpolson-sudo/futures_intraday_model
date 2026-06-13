Refactor raw-ingest data layout only.

Repo:
C:\Users\donny\Desktop\futures_intraday_model

Use only this active repo. Do not read, write, or run commands outside this
repo. If expected raw-ingest files/scripts are not present here, stop and
report the missing paths instead of switching repos.

Goal:
Make the Databento archive/raw layout professional, simple, and unambiguous.

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

Preconditions:
- Before edits, inspect repo path and git status.
- Before edits, run this Phase 1A/1B stability check:
  python -m pytest tests/phase1A_download/test_download_databento_raw.py -q
- If that pre-edit check fails, stop and report the failures.
- Do not stage, commit, move, rename, delete, or preserve generated data/report artifacts.
- Do not manually move existing DBN/parquet files.
- Do not modify Phase 2/3/4 logic or configs.
- Do not edit generated data files.
- Do not move large local data automatically unless implementing a dry-run migration helper.

Allowed files:
- scripts/phase1A_download/download_databento_raw.py
- scripts/phase1B_convert/convert_databento_raw.py only if the conversion CLI wrapper needs a path/default update
- tests/phase1A_download/test_download_databento_raw.py
- README.md
- project_layout.md
- .gitignore only if needed

If required raw-ingest logic is outside these files, stop and report the exact
file needed before editing it.

Required changes:
1. Update raw-ingest defaults:
   - dbn_root = data/dbn/ohlcv_1m
   - definition_root = data/dbn/definition
   - raw_root = data/raw
   - reports_root = reports/raw_ingest

   The CLI may keep a single public --dbn-root if that matches the current
   implementation, but the default definition path must still resolve to
   data/dbn/definition.

2. Preserve legacy path discovery only:
   - data/raw/{market}/{year}.dbn.zst
   - data/raw/definition/{market}/{year}.dbn.zst
   New DBN outputs must use data/dbn paths.

3. DBN archive filenames must be based on the actual task date range:
   - {chunk_start}_{chunk_end}.dbn.zst
   - chunk_start and chunk_end are ISO dates, for example 2024-01-01_2025-01-01.dbn.zst
   - for year chunks, keep the year as the directory, not the filename

4. Conversion target remains:
   - data/raw/{market}/{year}.parquet

5. Phase 1B conversion discovery must:
   - discover canonical OHLCV DBN chunks under data/dbn/ohlcv_1m/{market}/{year}/
   - group one or more OHLCV chunk files into data/raw/{market}/{year}.parquet
   - discover matching definition DBN chunks under data/dbn/definition/{market}/{year}/
   - keep legacy data/raw/{market}/{year}.dbn.zst and data/raw/definition/{market}/{year}.dbn.zst readable for conversion
   - skip definition DBN files as OHLCV conversion inputs

6. Definitions must never be converted into raw OHLCV parquet.

7. Aggregate reports:
   - reports/raw_ingest/dbn_download_manifest.json
   - reports/raw_ingest/dbn_chunk_manifest.csv
   - reports/raw_ingest/raw_parquet_manifest.json
   - reports/raw_ingest/definition_download_manifest.json if definitions are supported

Tests:
- default OHLCV DBN path is data/dbn/ohlcv_1m/{market}/{year}/{chunk}.dbn.zst
- default definition path is data/dbn/definition/{market}/{year}/{chunk}.dbn.zst
- converted parquet path is data/raw/{market}/{year}.parquet
- multiple canonical OHLCV chunks for the same market/year are grouped into one parquet output
- legacy data/raw/*.dbn.zst can be discovered for conversion but is not the new output path
- definitions are not converted as OHLCV parquet
- manifests contain expected fields
- generated data/report artifacts remain ignored/untracked

Validation:
python -m pytest tests/phase1A_download/test_download_databento_raw.py -q
python -m pytest -q
python -m scripts.phase1A_download.download_databento_raw --help
python -m scripts.phase1B_convert.convert_databento_raw --help
git ls-files data reports
git status --short

Stop after reporting:
- files changed
- commands run
- validation results
- generated artifacts
- final git status
- unresolved migration risks or blockers
