$ErrorActionPreference = "Stop"
$auditRoot = Join-Path $env:TEMP ("quant_project_phase1b_tier2_audit_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
$auditReports = Join-Path $env:TEMP ("quant_project_phase1b_tier2_reports_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
$env:PHASE1B_AUDIT_ROOT = $auditRoot

python -m scripts.phase1B_convert.convert_databento_raw --dbn-root data\raw --raw-root $auditRoot --reports-root $auditReports --symbols CL,ES,ZN --overwrite
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

@'
import os, sys, yaml
from pathlib import Path
from scripts.phase1A_download.download_databento_raw import validate_download, validate_raw_file_manifest, raw_file_manifest_path

cfg = yaml.safe_load(Path("configs/alpha_tiered.yaml").read_text(encoding="utf-8"))
profile = cfg["profiles"]["tier_2"]
markets = profile["markets"]
years = profile["years"]
audit_root = Path(os.environ["PHASE1B_AUDIT_ROOT"])

failures = []
for market in markets:
    for year in years:
        for schema, path in [
            ("ohlcv-1m", Path("data/raw") / market / f"{year}.dbn.zst"),
            ("definition", Path("data/raw/definition") / market / f"{year}.dbn.zst"),
        ]:
            if not path.exists():
                failures.append(f"missing {path}")
                continue
            if not raw_file_manifest_path(path).exists():
                failures.append(f"missing manifest {raw_file_manifest_path(path)}")
                continue
            errors = validate_raw_file_manifest(path, expected_schema=schema, expected_market=market, expected_year=year)
            if errors:
                failures.append(f"{path}: {errors}")

        parquet = audit_root / market / f"{year}.parquet"
        if not parquet.exists():
            failures.append(f"missing converted parquet {parquet}")
            continue
        check = validate_download(parquet)
        if not check["valid"]:
            failures.append(f"{parquet}: {check['errors']}")

if failures:
    print("FAIL")
    print("\n".join(failures[:100]))
    sys.exit(1)

print(f"PASS tier_2 archives and Phase 1B conversion stable: markets={markets} years={years} audit_root={audit_root}")
'@ | python -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git status --short