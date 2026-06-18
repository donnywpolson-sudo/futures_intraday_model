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
    iter_range_tasks,
)
from scripts.validation.check_tier_2_coverage import (  # noqa: E402
    load_yaml,
    resolve_profile_name,
)


DEFAULT_SCHEMAS = (SCHEMA, "definition")


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
) -> list[dict[str, Any]]:
    start = f"{min(years)}-01-01"
    end = f"{max(years) + 1}-01-01"
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


def _count_by_market(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if row[field]:
            continue
        market = str(row["market"])
        counts[market] = counts.get(market, 0) + 1
    return dict(sorted(counts.items()))


def build_report(
    *,
    config_path: Path,
    profile: str,
    dbn_root: Path,
    schemas: tuple[str, ...] = DEFAULT_SCHEMAS,
    require_manifests: bool = True,
) -> dict[str, Any]:
    resolved, markets, years = _profile_markets_and_years(config_path, profile)
    rows = _expected_archive_rows(
        markets=markets,
        years=years,
        dbn_root=dbn_root,
        schemas=schemas,
    )
    missing_archives = [row for row in rows if not row["archive_present"]]
    missing_manifests = [row for row in rows if not row["manifest_present"]]
    failures: list[str] = []
    if missing_archives:
        failures.append(f"missing DBN archives: {len(missing_archives)}")
    if require_manifests and missing_manifests:
        failures.append(f"missing DBN archive manifests: {len(missing_manifests)}")

    return {
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "profile": profile,
        "resolved_profile": resolved,
        "dataset": CME_DATASET,
        "dbn_root": dbn_root.as_posix(),
        "schemas": list(schemas),
        "markets": markets,
        "years": years,
        "expected_archive_count": len(rows),
        "missing_archive_count": len(missing_archives),
        "missing_manifest_count": len(missing_manifests),
        "missing_archives_by_market": _count_by_market(rows, "archive_present"),
        "missing_manifests_by_market": _count_by_market(rows, "manifest_present"),
        "missing_archives": missing_archives,
        "missing_manifests": missing_manifests,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/alpha_tiered.yaml")
    parser.add_argument("--profile", default="tier_3_research")
    parser.add_argument("--dbn-root", default=DEFAULT_DBN_OUT)
    parser.add_argument(
        "--schema",
        action="append",
        choices=DEFAULT_SCHEMAS,
        dest="schemas",
        help="Schema to check; defaults to ohlcv-1m and definition.",
    )
    parser.add_argument("--allow-missing-manifests", action="store_true")
    parser.add_argument("--report-out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        config_path=Path(args.config),
        profile=str(args.profile),
        dbn_root=Path(args.dbn_root),
        schemas=tuple(args.schemas or DEFAULT_SCHEMAS),
        require_manifests=not args.allow_missing_manifests,
    )
    if args.report_out:
        out = Path(args.report_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "status={status} expected_archives={expected_archive_count} "
        "missing_archives={missing_archive_count} missing_manifests={missing_manifest_count}".format(**report)
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
