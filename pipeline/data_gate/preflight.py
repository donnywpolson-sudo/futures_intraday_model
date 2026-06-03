from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pipeline.common.io_safe import atomic_write_json


REMEDIATION = (
    "python scripts/validate_databento_continuous.py "
    "--write-validated --clean-policy drop-invalid"
)


class DatasetPreflightError(RuntimeError):
    pass


def _cfg_get(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def _manifest_paths(root: Path) -> list[Path]:
    return [p for p in [root / "manifest.json", root / "_manifest.csv"] if p.exists()]


def _manifest_records(path: Path) -> list[str]:
    if path.suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("files") if isinstance(raw, dict) else raw
        out = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    out.append(str(row.get("path") or row.get("file") or row.get("filepath") or ""))
                else:
                    out.append(str(row))
        return [x for x in out if x]
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [
                str(row.get("path") or row.get("file") or row.get("filepath") or "")
                for row in reader
                if row
            ]
    return []


def validate_research_data_preflight(config: Any, report_path: str | Path = "reports/validation/research_data_preflight.json") -> dict:
    data = config.data
    root = Path(_cfg_get(data, "root", "data/validated"))
    validated_root = Path(_cfg_get(data, "validated_root", "data/validated"))
    symbols = list(_cfg_get(config, "symbols", []))
    years = range(int(_cfg_get(config, "start_year", 0)), int(_cfg_get(config, "end_year", 9999)) + 1)

    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    if _cfg_get(data, "forbid_raw_fallback_after_validation", True) and root == Path(_cfg_get(data, "raw_root", "data/raw")):
        failures.append(f"raw fallback rejected: data.root={root}; run: {REMEDIATION}")

    manifests = _manifest_paths(root)
    if _cfg_get(data, "manifest_required", True) and not manifests:
        failures.append(f"missing manifest under {root}: expected manifest.json or _manifest.csv")

    expected = [root / sym / f"{year}.parquet" for sym in symbols for year in years]
    existing = [p for p in expected if p.exists()]
    only_manifests = bool(manifests) and not list(root.glob("*/*.parquet"))

    if root == validated_root and _cfg_get(data, "require_validated_files", True):
        if not existing:
            failures.append(
                f"missing validated parquet files under {root}/{{market}}/{{year}}.parquet "
                f"for symbols={symbols} years={list(years)}; run: {REMEDIATION}"
            )
        if only_manifests:
            failures.append(f"validated root has only manifests and no parquet files: {root}; run: {REMEDIATION}")

    manifest_missing = []
    if manifests:
        records = set()
        for mp in manifests:
            records.update(_manifest_records(mp))
        if records:
            for p in existing:
                rel = str(p.as_posix())
                if rel not in records and str(p) not in records and p.name not in records:
                    manifest_missing.append(rel)
    if manifest_missing:
        checks.append({"name": "manifest_records_match_files", "status": "WARN", "missing_records": manifest_missing[:20]})

    status = "FAIL" if failures else "PASS"
    report = {
        "status": status,
        "data_root": str(root),
        "symbols": symbols,
        "years": list(years),
        "manifest_paths": [str(p) for p in manifests],
        "existing_parquet_files": [str(p) for p in existing],
        "failures": failures,
        "checks": checks,
        "remediation": REMEDIATION,
    }
    atomic_write_json(report_path, report)
    if failures:
        raise DatasetPreflightError("; ".join(failures))
    return report
