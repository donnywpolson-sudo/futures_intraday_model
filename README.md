# Futures Intraday Model

Intraday futures research pipeline using Databento continuous-contract 1-minute OHLCV data.

## New Machine Setup

These steps assume the new machine only has the files cloned from GitHub. Local data, reports, virtual environments, and secrets are intentionally not stored in GitHub.

### 1. Install prerequisites

Install:

```text
Git
Python 3.11
```

Confirm PowerShell can see them:

```powershell
git --version
python --version
```

### 2. Clone the repo

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

When returning to the project later, reactivate the environment before running scripts:

```powershell
.\.venv\Scripts\activate
```

### 4. Add the Databento API key

Create the ignored local secrets folder and key file:

```powershell
New-Item -ItemType Directory -Force .\secrets
Set-Content -Path .\secrets\databento.env -Value 'DATABENTO_API_KEY="YOUR_KEY_HERE"' -Encoding utf8
```

Do not commit `secrets/`, `.env`, API keys, raw data, reports, or model outputs.

### 5. Verify the checkout

```powershell
python -m pytest -q
```

### 6. Pipeline and data rebuilds

Use `PROJECT_OUTLINE.md` for the authoritative project outline, phase order,
runnable phase commands, acceptance checks, and stop conditions. `PIPELINE.md`
is only a compatibility pointer for older references. Keep runnable pipeline
commands out of setup docs so they do not drift.

Generated local outputs are ignored by Git:

```text
data/
reports/
models/
outputs/
logs/
cache/
```

Profile definitions live in `configs/alpha_tiered.yaml`.

### 7. Sync with GitHub

Pull latest code before working:

```powershell
git pull --ff-only
```

Before pushing code or docs, review the worktree and run the hygiene checks:

```powershell
git status --short --untracked-files=all
python scripts/check_git_hygiene.py
git diff --check
```

Push only reviewed code/docs changes:

```powershell
git push
```
