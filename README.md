# Quant Project

Intraday futures research pipeline using Databento continuous-contract 1-minute OHLCV data.

## Environment

Use Python 3.11.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Databento API Key

Put the Databento API key in `databento.env` at the project root:

```powershell
Set-Content -Path .\databento.env -Value 'DATABENTO_API_KEY="YOUR_KEY"' -Encoding utf8
```

The raw downloader only reads `DATABENTO_API_KEY` from that file. `databento.env` is git-ignored.
It also accepts a raw key as the only non-comment line in `databento.env`.

## Raw Data Download

Raw files are written as:

```text
data/raw/{market}/{year}.parquet
```

Smoke test:

```powershell
python scripts\download_databento_raw.py --symbols ES --start-year 2026 --end-year 2026 --end-date 2026-01-03 --out data\raw_api_test --overwrite
```

Full L0/OHLCV archive:

```powershell
python scripts\download_databento_raw.py --universe extended_cme_vix --start-year 2010 --end-year 2026 --end-date 2026-06-10
```

The downloader does not replace existing files unless `--overwrite` is passed.

## Causal Base

Build the normalized causal base from every raw market/year file:

```powershell
python scripts\build_causal_base_data.py --profile all_raw
```

Output:

```text
data/causally_gated_normalized/{market}/{year}.parquet
reports/causal_base/
```

## Tests

```powershell
python -m pytest -q
```

## Simple GitHub Sync

Stage, commit, rebase, and push all non-risky local changes from this computer to GitHub:

```powershell
python push_github.py
```

Pull GitHub changes onto this computer before working:

```powershell
python pull_github.py
```

`push_github.py` prints changed files, blocks risky data/secret/output paths, runs tests, creates backup branches, stages with `git add -A`, commits, pulls with `--rebase`, and pushes. Raw data and generated reports stay out of GitHub.
