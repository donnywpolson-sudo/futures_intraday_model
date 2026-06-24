#!/usr/bin/env python3
"""Validate local DBN archive coverage for a configured research profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1A_download.download_databento_raw import (  # noqa: E402
    CME_DATASET,
    DEFAULT_DBN_OUT,
    SCHEMA,
    dbn_schema_root,
    iter_range_tasks,
    resolve_requested_schemas,
    validate_raw_file_manifest,
)
from scripts.phase1_raw_contract import REQUIRED_SCHEMAS, SCHEMA_ALIASES, SCHEMA_PATHS, SUPPORTED_SCHEMAS  # noqa: E402
from scripts.validation.check_tier_2_coverage import (  # noqa: E402
    load_yaml,
    resolve_profile_name,
)


DEFAULT_SCHEMAS = REQUIRED_SCHEMAS
_SCHEMA_ROOT_NAMES = set(SCHEMA_PATHS.values())


def _non_empty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _profile_markets_and_years(config_path: Path, profile_name: str) -> tuple[str, list[str], list[int]]:
    config = load_yaml(config_path)
    profiles = config.get("profiles", {})
    aliases = config.get("aliases", {})
    if not isinstance(profiles, dict):
        raise ValueError("alpha_tiered profiles mapping missing")
    if not isinstance(aliases, dict):
        aliases = {}

    resolved = resolve_profile_name(profile_name, {str(key): str(value) for key, value in aliases.items()})
    profile = profiles.get(resolved)
    if not isinstance(profile, dict):
        raise ValueError(f"profile {profile_name!r} resolved to {resolved!r} but was not found")

    markets = [str(item) for item in profile.get("markets", [])]
    years = [int(item) for item in profile.get("years", [])]
    if not markets:
        raise ValueError(f"profile {resolved!r} has no markets")
    if not years:
        raise ValueError(f"profile {resolved!r} has no years")
    return resolved, markets, years


def _expected_archive_rows(
    *,
    markets: list[str],
    years: list[int],
    dbn_root: Path,
    schemas: tuple[str, ...],
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    start = f"{min(years)}-01-01"
    end = end_date or f"{max(years) + 1}-01-01"
    selected_years = set(years)
    rows: list[dict[str, Any]] = []

    for schema in schemas:
        tasks = iter_range_tasks(
            markets,
            start=start,
            end=end,
            output_root=dbn_root,
            chunk="year",
            mode="download-dbn",
            raw_format="dbn-zstd",
            dataset=CME_DATASET,
            schema=schema,
        )
        for task in tasks:
            if task.year not in selected_years:
                continue
            archive_path = Path(task.output_path)
            manifest_path = archive_path.with_name(f"{archive_path.name}.manifest.json")
            rows.append(
                {
                    "schema": schema,
                    "market": task.product,
                    "year": task.year,
                    "start": task.start,
                    "end": task.end,
                    "path": archive_path.as_posix(),
                    "manifest_path": manifest_path.as_posix(),
                    "archive_present": _non_empty_file(archive_path),
                    "manifest_present": _non_empty_file(manifest_path),
                }
            )
    return rows


def _count_rows_by_market(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        market = str(row["market"])
        counts[market] = counts.get(market, 0) + 1
    return dict(sorted(counts.items()))


def _count_rows_by_schema(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        schema = str(row["schema"])
        counts[schema] = counts.get(schema, 0) + 1
    return dict(sorted(counts.items()))


def resolve_schema_args(schemas: tuple[str, ...] | None) -> tuple[str, ...]:
    resolved: list[str] = []
    for schema in schemas or DEFAULT_SCHEMAS:
        for item in resolve_requested_schemas(schema):
            if item not in resolved:
                resolved.append(item)
    return tuple(resolved)


def resolve_optional_schema_args(schemas: tuple[str, ...] | None) -> tuple[str, ...]:
    resolved: list[str] = []
    for schema in schemas or ():
        if schema in SCHEMA_ALIASES:
            raise ValueError(f"optional schema must be concrete, got alias {schema!r}")
        for item in resolve_requested_schemas(schema):
            if item not in resolved:
                resolved.append(item)
    return tuple(resolved)


def _normalize_dbn_root(dbn_root: Path) -> Path:
    root = Path(dbn_root)
    ohlcv_root_name = SCHEMA_PATHS[SCHEMA]
    if root.name == ohlcv_root_name:
        return root
    if root.name in _SCHEMA_ROOT_NAMES:
        return root.parent / ohlcv_root_name
    if root.name == "dbn" or (root / ohlcv_root_name).exists():
        return root / ohlcv_root_name
    return root


def _extra_market_dirs_by_schema(
    *,
    dbn_root: Path,
    schemas: tuple[str, ...],
    markets: list[str],
) -> dict[str, list[str]]:
    allowed = set(markets)
    extras: dict[str, list[str]] = {}
    for schema in schemas:
        root = dbn_schema_root(dbn_root, schema)
        if not root.is_dir():
            continue
        extra_dirs = sorted(
            child.name
            for child in root.iterdir()
            if child.is_dir() and child.name not in allowed
        )
        if extra_dirs:
            extras[schema] = extra_dirs
    return extras


def _invalid_manifests(rows: list[dict[str, Any]], *, require_manifests: bool) -> list[dict[str, Any]]:
    if not require_manifests:
        return []
    invalid: list[dict[str, Any]] = []
    for row in rows:
        if not row["manifest_present"]:
            continue
        failures = validate_raw_file_manifest(
            Path(str(row["path"])),
            expected_schema=str(row["schema"]),
            expected_market=str(row["market"]),
            expected_year=int(row["year"]),
        )
        if failures:
            invalid.append({**row, "manifest_failures": failures})
    return invalid


def build_report(
    *,
    config_path: Path,
    profile: str,
    dbn_root: Path,
    schemas: tuple[str, ...] = DEFAULT_SCHEMAS,
    require_manifests: bool = True,
    optional_schemas: tuple[str, ...] = (),
    end_date: str | None = None,
) -> dict[str, Any]:
    resolved, markets, years = _profile_markets_and_years(config_path, profile)
    schemas = resolve_schema_args(schemas)
    optional_schemas = resolve_optional_schema_args(optional_schemas)
    required_marked_optional = sorted(set(optional_schemas) & set(DEFAULT_SCHEMAS))
    if required_marked_optional:
        raise ValueError(
            "Phase 1A downstream readiness schemas cannot be optional: "
            + ",".join(required_marked_optional)
        )
    optional_schema_set = set(optional_schemas)
    effective_dbn_root = _normalize_dbn_root(dbn_root)
    rows = _expected_archive_rows(
        markets=markets,
        years=years,
        dbn_root=effective_dbn_root,
        schemas=schemas,
        end_date=end_date,
    )
    required_rows = [row for row in rows if str(row["schema"]) not in optional_schema_set]
    optional_rows = [row for row in rows if str(row["schema"]) in optional_schema_set]
    missing_archives = [row for row in required_rows if not row["archive_present"]]
    missing_optional_archives = [row for row in optional_rows if not row["archive_present"]]
    missing_manifests = [row for row in required_rows if not row["manifest_present"]]
    missing_optional_manifests = [row for row in optional_rows if not row["manifest_present"]]
    invalid_manifests = _invalid_manifests(rows, require_manifests=require_manifests)
    extra_market_dirs = _extra_market_dirs_by_schema(
        dbn_root=effective_dbn_root,
        schemas=schemas,
        markets=markets,
    )
    extra_market_dir_count = sum(len(items) for items in extra_market_dirs.values())
    failures: list[str] = []
    if missing_archives:
        failures.append(f"missing DBN archives: {len(missing_archives)}")
    if require_manifests and missing_manifests:
        failures.append(f"missing DBN archive manifests: {len(missing_manifests)}")
    if invalid_manifests:
        failures.append(f"invalid DBN archive manifests: {len(invalid_manifests)}")
    if extra_market_dirs:
        failures.append(f"extra DBN market directories: {extra_market_dir_count}")

    return {
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "profile": profile,
        "resolved_profile": resolved,
        "dataset": CME_DATASET,
        "dbn_root": dbn_root.as_posix(),
        "effective_dbn_root": effective_dbn_root.as_posix(),
        "schemas": list(schemas),
        "optional_schemas": list(optional_schemas),
        "markets": markets,
        "years": years,
        "audit_start": f"{min(years)}-01-01",
        "audit_end": end_date or f"{max(years) + 1}-01-01",
        "expected_archive_count": len(rows),
        "missing_archive_count": len(missing_archives),
        "missing_optional_archive_count": len(missing_optional_archives),
        "missing_manifest_count": len(missing_manifests),
        "missing_optional_manifest_count": len(missing_optional_manifests),
        "invalid_manifest_count": len(invalid_manifests),
        "extra_market_dir_count": extra_market_dir_count,
        "missing_archives_by_market": _count_rows_by_market(missing_archives),
        "missing_optional_archives_by_market": _count_rows_by_market(missing_optional_archives),
        "missing_archives_by_schema": _count_rows_by_schema(missing_archives),
        "missing_optional_archives_by_schema": _count_rows_by_schema(missing_optional_archives),
        "missing_manifests_by_market": _count_rows_by_market(missing_manifests),
        "missing_optional_manifests_by_market": _count_rows_by_market(missing_optional_manifests),
        "missing_manifests_by_schema": _count_rows_by_schema(missing_manifests),
        "missing_optional_manifests_by_schema": _count_rows_by_schema(missing_optional_manifests),
        "extra_market_dirs_by_schema": extra_market_dirs,
        "missing_archives": missing_archives,
        "missing_optional_archives": missing_optional_archives,
        "missing_manifests": missing_manifests,
        "missing_optional_manifests": missing_optional_manifests,
        "invalid_manifests": invalid_manifests,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/alpha_tiered.yaml")
    parser.add_argument("--profile", default="tier_3_research")
    parser.add_argument("--dbn-root", default=DEFAULT_DBN_OUT)
    parser.add_argument(
        "--schema",
        action="append",
        choices=[*SUPPORTED_SCHEMAS, *SCHEMA_ALIASES],
        dest="schemas",
        help="Schema to check; defaults to Phase 1A required schemas: ohlcv-1m, definition, statistics, status.",
    )
    parser.add_argument(
        "--optional-schema",
        action="append",
        choices=SUPPORTED_SCHEMAS,
        dest="optional_schemas",
        help="Schema whose missing archives/manifests should be reported as optional gaps.",
    )
    parser.add_argument("--end-date", help="Exclusive end date for partial current-year audits, YYYY-MM-DD.")
    parser.add_argument("--allow-missing-manifests", action="store_true")
    parser.add_argument("--report-out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        config_path=Path(args.config),
        profile=str(args.profile),
        dbn_root=Path(args.dbn_root),
        schemas=resolve_schema_args(tuple(args.schemas or DEFAULT_SCHEMAS)),
        require_manifests=not args.allow_missing_manifests,
        optional_schemas=resolve_optional_schema_args(tuple(args.optional_schemas or ())),
        end_date=args.end_date,
    )
    if args.report_out:
        out = Path(args.report_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "status={status} expected_archives={expected_archive_count} "
        "missing_archives={missing_archive_count} missing_manifests={missing_manifest_count} "
        "missing_optional_archives={missing_optional_archive_count} "
        "missing_optional_manifests={missing_optional_manifest_count} "
        "invalid_manifests={invalid_manifest_count} extra_market_dirs={extra_market_dir_count}".format(**report)
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
