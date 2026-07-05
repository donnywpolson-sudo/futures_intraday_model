# Futures Intraday Model

A local research workspace for testing intraday futures ideas with Databento
continuous-contract 1-minute OHLCV data.

This repo is for research and walk-forward validation only. It is not a
live-trading bot, broker connection, or production trading system.

## If You Use Codex Or ChatGPT

Start by asking Codex:

```text
Read AGENTS.md, PROJECT_OUTLINE.md, and the current section of CODEX_HANDOFF.md.
Tell me the current project status and the safest next step. Do not run broad
data builds, model runs, downloads, commits, pushes, paper trading, or live
trading unless I explicitly approve the exact bounded command.
```

Use `PROJECT_OUTLINE.md` for the authoritative project outline. `PIPELINE.md`
is only a compatibility pointer.
Use `PROJECT_OUTLINE.md` for the real workflow and runnable pipeline commands.
This README is only for setup and orientation.

## What Is In This Repo

- `AGENTS.md`: rules Codex should follow in this repo.
- `PROJECT_OUTLINE.md`: project workflow, phase order, checks, and commands.
- `CODEX_HANDOFF.md`: latest working state and continuation notes.
- `configs/`: local settings, markets, years, sessions, costs, and profiles.
- `scripts/`: research, data, validation, and reporting code.
- `tests/`: checks Codex can run after code changes.

Local data, reports, secrets, logs, model outputs, and cache files are not meant
to be stored in GitHub.

## New Computer Setup

These steps assume you are on Windows PowerShell.

### 1. Install basics

Install:

```text
Git
Python 3.11
```

Check that PowerShell can see them:

```powershell
git --version
python --version
```

### 2. Download the repo

```powershell
git clone https://github.com/donnywpolson-sudo/futures_intraday_model.git futures_intraday_model
cd futures_intraday_model
```

### 3. Create the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Each time you come back to the project, reactivate the environment first:

```powershell
.\.venv\Scripts\activate
```

### 4. Add your Databento API key

Create the ignored local secrets file:

```powershell
New-Item -ItemType Directory -Force .\secrets
Set-Content -Path .\secrets\databento.env -Value 'DATABENTO_API_KEY="YOUR_KEY_HERE"' -Encoding utf8
```

Replace `YOUR_KEY_HERE` with your real key. Do not commit or paste real API keys
into chat.

### 5. Check the install

```powershell
python -m pytest -q
```

If this fails, ask Codex to inspect the error and suggest the narrowest fix.

## Daily Use

Before asking Codex to work on the project:

```powershell
.\.venv\Scripts\activate
git pull --ff-only
```

Before pushing reviewed code or docs:

```powershell
git status --short --untracked-files=all
python scripts/check_git_hygiene.py
git diff --check
```

Only push changes you reviewed:

```powershell
git push
```

## Local Files GitHub Should Ignore

These are local outputs and should normally stay off GitHub:

```text
data/
reports/
models/
outputs/
logs/
cache/
secrets/
```

Profile definitions live in `configs/alpha_tiered.yaml`.
