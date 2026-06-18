# Futures Intraday Model Runbook

This repo is the GitHub source of truth for code, configs, tests, docs, and
small rebuild metadata for an intraday futures research pipeline. It is not a
byte-for-byte backup of the local 20.7 GB working tree.

## What GitHub Tracks

- `configs/`: market sessions, costs, model registry, and alpha tier profiles.
- `scripts/`: phase entrypoints and utility scripts.
- `tests/`: focused pytest coverage for pipeline phases and validation.
- `docs/` and `manifests/`: backup policy, runbooks, inventories, and small
  summaries needed to rebuild or audit the project.
- Root project files such as `README.md`, `README_RUNBOOK.md`,
  `requirements.txt`, `.gitignore`, and `.pre-commit-config.yaml`.

## What GitHub Excludes

The repo intentionally excludes local secrets, virtual environments, raw market
data, generated parquet/DBN/ZST files, model binaries, caches, logs, and
temporary reports. Important generated findings should be reduced to a small
summary or manifest under `docs/` or `manifests/`.

Full byte-for-byte restore of ignored data and artifacts requires an
external SSD, NAS, or cloud backup in addition to GitHub.

## Disaster Recovery Checklist

1. Clone the GitHub repo.
2. Create and activate a Python 3.11 virtual environment.
3. Install dependencies from `requirements.txt`.
4. Restore local secrets such as the Databento API key into `secrets/`.
5. Restore ignored data/artifacts from external/cloud backup, or redownload raw
   data and rebuild generated stages.
6. Run smoke checks before long data or model jobs.
7. Regenerate inventories/manifests after restore.

## Fresh Clone Setup: Windows PowerShell

```powershell
git clone <YOUR_PRIVATE_REPO_URL> futures_intraday_model
cd .\futures_intraday_model
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Use Python 3.11 unless the project is explicitly updated.

## Secrets

Create `secrets/databento.env` locally. This path is ignored by Git.

```powershell
New-Item -ItemType Directory -Force -Path .\secrets
Set-Content -Path .\secrets\databento.env -Value 'DATABENTO_API_KEY="YOUR_KEY"' -Encoding utf8
```

Do not commit API keys, credentials, `.env` files, `.key` files, or `.pem`
files.

## Optional Databento Live Smoke

Live smoke support is additive research/paper observation only. It does not
place orders, connect to brokers, perform live inference, or change the
historical research/backtest pipeline.

The script requires `DATABENTO_API_KEY` only when run. Imports, tests, and
normal historical commands do not require a live key or network access.

```powershell
powershell -NoProfile -Command '$env:DATABENTO_API_KEY=""; python scripts\live_smoke_databento.py --max-records 1 --timeout-seconds 30'
$env:DATABENTO_API_KEY=""
python scripts\live_smoke_databento.py --max-records 1 --timeout-seconds 30
python scripts\live_smoke_databento.py --max-records 5 --timeout-seconds 30
python scripts\live_smoke_databento.py --start 0 --max-records 5 --timeout-seconds 30 --save-dbn
```

When `--save-dbn` is used, raw live DBN is written to a timestamped ignored
file under `data/live_raw/`.

## Restore Or Redownload Raw Data

If external/cloud backup exists, restore ignored directories such as `data/`,
`reports/`, and `models/` before rebuilding.

If raw data must be redownloaded, use `PIPELINE.md` for the authoritative
dry-run, bounded archive job, DBN layout, conversion command, acceptance checks,
and stop conditions.

## Pipeline Rebuild Order

Use `PIPELINE.md` for the authoritative pipeline rebuild order, validation
coverage command, phase commands, acceptance checks, and current stop rules.

## Smoke Tests

```powershell
python -m py_compile scripts/write_project_inventory.py scripts/check_git_hygiene.py
python scripts/check_git_hygiene.py
python -m pytest -q tests\phase1A_download\test_download_databento_raw.py tests\validation\test_model_registry.py
```

## Full Tests

```powershell
python -m pytest -q
```

## Manifests And Inventories

Create a code/config/test inventory without hashing the whole working tree:

```powershell
python scripts/write_project_inventory.py
```

Include ignored data/artifact directories only when intentionally auditing local
storage:

```powershell
python scripts/write_project_inventory.py --include-data
```

Compute SHA256 hashes only for small, targeted inventory runs:

```powershell
python scripts/write_project_inventory.py --hash
```

Before committing, review what Git would add and run the hygiene check:

```powershell
git add --dry-run .
python scripts/check_git_hygiene.py
```
