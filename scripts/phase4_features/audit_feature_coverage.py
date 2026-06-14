#!/usr/bin/env python3
"""Audit Phase 4 feature coverage against available Phase 3 labeled data."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from scripts.phase4_features.build_baseline_features import (
    DEFAULT_INPUT_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_PROFILE_CONFIG,
    relative_path,
    resolve_profile_inputs,
    resolve_profile_name,
)
from scripts.validation.check_tier_2_coverage import PRODUCT_AVAILABLE_START_YEAR


DEFAULT_REPORTS_ROOT = Path("reports/phase4")
DEFAULT_PROFILE = "tier_3"


@dataclass(frozen=True)
class CoverageRow:
    market: str
    year: int
    labeled_path: str
    feature_path: str
    labeled_exists: bool
    feature_exists: bool
    eligible: bool
    status: str
    skipped_reason: str
    labeled_rows: int | None = None
    feature_rows: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "market": self.market,
            "year": self.year,
            "labeled_path": self.labeled_path,
            "feature_path": self.feature_path,
            "labeled_exists": self.labeled_exists,
            "feature_exists": self.feature_exists,
            "eligible": self.eligible,
            "status": self.status,
            "skipped_reason": self.skipped_reason,
            "labeled_rows": self.labeled_rows,
            "feature_rows": self.feature_rows,
        }


def _read_yaml(path: Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return payload if isinstance(payload, Mapping) else {}


def _configured_root(
    profile_config: Path,
    key: str,
    default: Path,
) -> Path:
    config = _read_yaml(profile_config)
    paths = config.get("paths", {})
    if isinstance(paths, Mapping) and paths.get(key):
        return Path(str(paths[key]))
    return default


def _resolved_profile(profile: str, profile_config: Path) -> str:
    config = _read_yaml(profile_config)
    aliases = config.get("aliases", {})
    alias_map = {str(key): str(value) for key, value in aliases.items()} if isinstance(aliases, Mapping) else {}
    return resolve_profile_name(profile, alias_map)


def _parquet_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq

        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:
        return None


def _coverage_row(
    market: str,
    year: int,
    labeled_path: Path,
    feature_path: Path,
    *,
    collect_row_counts: bool,
) -> CoverageRow:
    start_year = PRODUCT_AVAILABLE_START_YEAR.get(market)
    if start_year is not None and year < start_year:
        return CoverageRow(
            market=market,
            year=year,
            labeled_path=relative_path(labeled_path),
            feature_path=relative_path(feature_path),
            labeled_exists=labeled_path.exists(),
            feature_exists=feature_path.exists(),
            eligible=False,
            status="skipped",
            skipped_reason=f"product_unavailable_before_{start_year}",
        )

    labeled_exists = labeled_path.exists()
    feature_exists = feature_path.exists()
    if not labeled_exists:
        status = "missing_labeled"
        skipped_reason = "missing_labeled"
    elif feature_exists:
        status = "covered"
        skipped_reason = "existing_feature"
    else:
        status = "missing_feature"
        skipped_reason = ""

    return CoverageRow(
        market=market,
        year=year,
        labeled_path=relative_path(labeled_path),
        feature_path=relative_path(feature_path),
        labeled_exists=labeled_exists,
        feature_exists=feature_exists,
        eligible=labeled_exists,
        status=status,
        skipped_reason=skipped_reason,
        labeled_rows=_parquet_row_count(labeled_path) if collect_row_counts else None,
        feature_rows=_parquet_row_count(feature_path) if collect_row_counts else None,
    )


def build_coverage_audit(
    *,
    profile: str = DEFAULT_PROFILE,
    input_root: Path | None = None,
    output_root: Path | None = None,
    profile_config: Path = DEFAULT_PROFILE_CONFIG,
    collect_row_counts: bool = False,
) -> dict[str, Any]:
    resolved_input_root = input_root or _configured_root(
        profile_config,
        "labeled_root",
        DEFAULT_INPUT_ROOT,
    )
    resolved_output_root = output_root or _configured_root(
        profile_config,
        "feature_matrix_root",
        DEFAULT_OUTPUT_ROOT,
    )
    profile_inputs = resolve_profile_inputs(profile, resolved_input_root, profile_config)
    rows = [
        _coverage_row(
            market,
            year,
            labeled_path,
            resolved_output_root / market / f"{year}.parquet",
            collect_row_counts=collect_row_counts,
        )
        for market, year, labeled_path in profile_inputs
    ]

    available_labeled = [row for row in rows if row.eligible and row.labeled_exists]
    existing_features = [row for row in available_labeled if row.feature_exists]
    missing_features = [row for row in available_labeled if not row.feature_exists]
    missing_labeled = [row for row in rows if row.status == "missing_labeled"]
    skipped = [row for row in rows if row.status == "skipped"]
    by_market: dict[str, dict[str, int]] = {}
    for row in rows:
        market_summary = by_market.setdefault(
            row.market,
            {
                "available_labeled": 0,
                "existing_features": 0,
                "missing_features": 0,
                "missing_labeled": 0,
                "skipped": 0,
            },
        )
        if row.status in market_summary:
            market_summary[row.status] += 1
        if row.eligible and row.labeled_exists:
            market_summary["available_labeled"] += 1
            if row.feature_exists:
                market_summary["existing_features"] += 1
            else:
                market_summary["missing_features"] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "resolved_profile": _resolved_profile(profile, profile_config),
        "input_root": relative_path(resolved_input_root),
        "output_root": relative_path(resolved_output_root),
        "available_labeled": len(available_labeled),
        "existing_features": len(existing_features),
        "missing_features": len(missing_features),
        "missing_tier3_count": len(missing_features),
        "missing_labeled_count": len(missing_labeled),
        "skipped_count": len(skipped),
        "skipped_reasons": sorted({row.skipped_reason for row in skipped if row.skipped_reason}),
        "status_counts": {
            "covered": sum(row.status == "covered" for row in rows),
            "missing_feature": sum(row.status == "missing_feature" for row in rows),
            "missing_labeled": len(missing_labeled),
            "skipped": len(skipped),
        },
        "by_market": by_market,
        "rows": [row.to_dict() for row in rows],
    }


def missing_feature_inputs(audit: Mapping[str, Any]) -> list[tuple[str, int, Path]]:
    rows = audit.get("rows", [])
    if not isinstance(rows, list):
        return []
    missing: list[tuple[str, int, Path]] = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("status") != "missing_feature":
            continue
        market = str(row["market"])
        year = int(row["year"])
        missing.append((market, year, Path(str(row["labeled_path"]))))
    return missing


def _write_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "market",
        "year",
        "status",
        "skipped_reason",
        "eligible",
        "labeled_exists",
        "feature_exists",
        "labeled_rows",
        "feature_rows",
        "labeled_path",
        "feature_path",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def write_coverage_audit(audit: Mapping[str, Any], reports_root: Path) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / "feature_coverage_audit.json"
    csv_path = reports_root / "feature_coverage_audit.csv"
    json_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    rows = audit.get("rows", [])
    _write_csv(csv_path, rows if isinstance(rows, list) else [])
    return json_path, csv_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--input-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--row-counts", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    audit = build_coverage_audit(
        profile=args.profile,
        input_root=Path(args.input_root) if args.input_root else None,
        output_root=Path(args.output_root) if args.output_root else None,
        profile_config=Path(args.profile_config),
        collect_row_counts=args.row_counts,
    )
    json_path, csv_path = write_coverage_audit(audit, Path(args.reports_root))
    print(
        "PASS Phase 4 coverage audit:"
        f" available_labeled={audit['available_labeled']}"
        f" existing_features={audit['existing_features']}"
        f" missing_features={audit['missing_features']}"
        f" report={relative_path(json_path)} csv={relative_path(csv_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
