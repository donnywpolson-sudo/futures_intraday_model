#!/usr/bin/env python3
"""Fail-closed audit for Phase 2 causal candidate outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

import pyarrow.parquet as pq


DEFAULT_PROFILE = "tier_3"
DEFAULT_RESOLVED_PROFILE = "tier_3_research"
DEFAULT_EXPECTED_COUNT = 461
DEFAULT_REQUIRED_COLUMNS = (
    "status_missing",
    "status_stale",
    "statistics_missing",
    "statistics_stale",
)


def _read_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON root is not an object: {path.as_posix()}")
    return payload


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_path(raw_path: object) -> Path:
    return Path(str(raw_path)).expanduser().resolve()


def _paths_match(left: object, right: Path) -> bool:
    try:
        return _resolve_path(left) == right.expanduser().resolve()
    except (OSError, TypeError, ValueError):
        return False


def _hash_lookup(hash_map: object, path: Path) -> str | None:
    if not isinstance(hash_map, Mapping):
        return None
    expected_path = path.expanduser().resolve()
    for raw_path, raw_hash in hash_map.items():
        try:
            if _resolve_path(raw_path) == expected_path:
                return str(raw_hash)
        except (OSError, TypeError, ValueError):
            continue
    return None


def _pre_availability_exemptions(raw_alignment: Mapping[str, Any]) -> set[tuple[str, int]]:
    exemptions: set[tuple[str, int]] = set()
    for item in raw_alignment.get("pre_availability_exemptions", []):
        try:
            if isinstance(item, Mapping):
                exemptions.add((str(item["market"]), int(item["year"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                exemptions.add((str(item[0]), int(item[1])))
        except (KeyError, TypeError, ValueError):
            continue
    return exemptions


def expected_market_years(raw_alignment: Mapping[str, Any]) -> set[tuple[str, int]]:
    markets = [str(market) for market in raw_alignment.get("markets", [])]
    years = [int(year) for year in raw_alignment.get("years", [])]
    return {
        (market, year)
        for market in markets
        for year in years
    } - _pre_availability_exemptions(raw_alignment)


def _actual_market_years(root: Path) -> set[tuple[str, int]]:
    actual: set[tuple[str, int]] = set()
    if not root.exists():
        return actual
    for path in root.glob("*/*.parquet"):
        try:
            actual.add((path.parent.name, int(path.stem)))
        except ValueError:
            continue
    return actual


def _manifest_output_pairs(manifest: Mapping[str, Any]) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    outputs = manifest.get("outputs", [])
    if not isinstance(outputs, list):
        return pairs
    for row in outputs:
        if not isinstance(row, Mapping):
            continue
        try:
            pairs.add((str(row["market"]), int(row["year"])))
        except (KeyError, TypeError, ValueError):
            continue
    return pairs


def audit_phase2_candidate(
    *,
    causal_root: Path,
    manifest_path: Path,
    raw_alignment_path: Path,
    expected_profile: str = DEFAULT_PROFILE,
    expected_resolved_profile: str = DEFAULT_RESOLVED_PROFILE,
    expected_count: int = DEFAULT_EXPECTED_COUNT,
    required_columns: Iterable[str] = DEFAULT_REQUIRED_COLUMNS,
) -> dict[str, Any]:
    failures: list[str] = []
    if not raw_alignment_path.exists():
        failures.append(f"raw alignment report missing: {_relative_path(raw_alignment_path)}")
        raw_alignment: Mapping[str, Any] = {}
    else:
        raw_alignment = _read_json(raw_alignment_path)
    if not manifest_path.exists():
        failures.append(f"Phase 2 manifest missing: {_relative_path(manifest_path)}")
        manifest: Mapping[str, Any] = {}
    else:
        manifest = _read_json(manifest_path)

    if raw_alignment:
        if raw_alignment.get("status") != "PASS":
            failures.append(f"raw alignment status is {raw_alignment.get('status')!r}, not PASS")
        if raw_alignment.get("profile") != expected_profile:
            failures.append(
                f"raw alignment profile is {raw_alignment.get('profile')!r}, not {expected_profile!r}"
            )
        if raw_alignment.get("resolved_profile") != expected_resolved_profile:
            failures.append(
                "raw alignment resolved_profile is "
                f"{raw_alignment.get('resolved_profile')!r}, not {expected_resolved_profile!r}"
            )
        for field in (
            "missing_raw_count",
            "needs_phase1b_conversion_count",
            "missing_ohlcv_dbn_count",
            "missing_definition_dbn_count",
            "invalid_manifest_count",
            "raw_schema_failure_count",
            "source_hash_mismatch_count",
            "definition_join_mismatch_count",
        ):
            if raw_alignment.get(field) != 0:
                failures.append(f"raw alignment {field} is {raw_alignment.get(field)!r}, not 0")

    expected_pairs = expected_market_years(raw_alignment) if raw_alignment else set()
    if len(expected_pairs) != expected_count:
        failures.append(f"expected market-year count is {len(expected_pairs)}, not {expected_count}")

    if manifest:
        if manifest.get("stage") != "causal_base":
            failures.append(f"manifest stage is {manifest.get('stage')!r}, not 'causal_base'")
        if manifest.get("status") != "PASS":
            failures.append(f"manifest status is {manifest.get('status')!r}, not PASS")
        if manifest.get("profile") != expected_profile:
            failures.append(f"manifest profile is {manifest.get('profile')!r}, not {expected_profile!r}")
        if manifest.get("resolved_profile") != expected_resolved_profile:
            failures.append(
                "manifest resolved_profile is "
                f"{manifest.get('resolved_profile')!r}, not {expected_resolved_profile!r}"
            )
        if not _paths_match(manifest.get("output_root"), causal_root):
            failures.append(
                "manifest output_root does not match causal_root: "
                f"{manifest.get('output_root')!r} != {_relative_path(causal_root)}"
            )
        if int(manifest.get("failure_count") or 0) != 0:
            failures.append(f"manifest failure_count is {manifest.get('failure_count')!r}, not 0")
        if int(manifest.get("warning_count") or 0) != 0:
            failures.append(f"manifest warning_count is {manifest.get('warning_count')!r}, not 0")
        summary = manifest.get("summary", {})
        if isinstance(summary, Mapping):
            if int(summary.get("fail_count") or 0) != 0:
                failures.append(f"manifest summary.fail_count is {summary.get('fail_count')!r}, not 0")
            if int(summary.get("warn_count") or 0) != 0:
                failures.append(f"manifest summary.warn_count is {summary.get('warn_count')!r}, not 0")

    actual_pairs = _actual_market_years(causal_root)
    missing_pairs = sorted(expected_pairs - actual_pairs)
    extra_pairs = sorted(actual_pairs - expected_pairs)
    if missing_pairs:
        failures.append(f"missing candidate outputs: {len(missing_pairs)}")
    if extra_pairs:
        failures.append(f"extra candidate outputs outside eligible scope: {len(extra_pairs)}")
    if len(actual_pairs & expected_pairs) != expected_count:
        failures.append(
            "eligible candidate output count is "
            f"{len(actual_pairs & expected_pairs)}, not {expected_count}"
        )

    manifest_pairs = _manifest_output_pairs(manifest)
    missing_manifest_pairs = sorted(expected_pairs - manifest_pairs)
    if missing_manifest_pairs:
        failures.append(f"manifest missing eligible outputs: {len(missing_manifest_pairs)}")

    output_hashes = manifest.get("output_file_hashes", {}) if manifest else {}
    missing_required_columns: list[dict[str, Any]] = []
    missing_prefix_columns: list[dict[str, Any]] = []
    stale_hashes: list[str] = []
    required_column_set = set(required_columns)
    for market, year in sorted(expected_pairs):
        path = causal_root / market / f"{year}.parquet"
        if not path.exists():
            continue
        expected_hash = _hash_lookup(output_hashes, path)
        if expected_hash is None:
            stale_hashes.append(f"{_relative_path(path)}: missing manifest hash")
        elif expected_hash != _file_sha256(path):
            stale_hashes.append(f"{_relative_path(path)}: stale manifest hash")
        columns = set(pq.read_schema(path).names)
        missing_columns = sorted(required_column_set - columns)
        if missing_columns:
            missing_required_columns.append(
                {"market": market, "year": year, "missing_columns": missing_columns}
            )
        has_status = any(column.startswith("status_") for column in columns)
        has_statistics = any(
            column.startswith("stat_") or column.startswith("statistics_")
            for column in columns
        )
        if not has_status or not has_statistics:
            missing_prefix_columns.append(
                {"market": market, "year": year, "has_status": has_status, "has_statistics": has_statistics}
            )

    if stale_hashes:
        failures.append(f"output hash failures: {len(stale_hashes)}")
    if missing_required_columns:
        failures.append(f"outputs missing required enrichment columns: {len(missing_required_columns)}")
    if missing_prefix_columns:
        failures.append(f"outputs missing enrichment prefix columns: {len(missing_prefix_columns)}")

    return {
        "stage": "phase2_candidate_audit",
        "status": "PASS" if not failures else "FAIL",
        "profile": expected_profile,
        "resolved_profile": expected_resolved_profile,
        "causal_root": _relative_path(causal_root),
        "manifest_path": _relative_path(manifest_path),
        "raw_alignment_path": _relative_path(raw_alignment_path),
        "expected_count": expected_count,
        "expected_market_year_count": len(expected_pairs),
        "candidate_output_count": len(actual_pairs),
        "eligible_candidate_output_count": len(actual_pairs & expected_pairs),
        "missing_output_count": len(missing_pairs),
        "extra_output_count": len(extra_pairs),
        "manifest_output_count": len(manifest_pairs),
        "manifest_missing_output_count": len(missing_manifest_pairs),
        "hash_failure_count": len(stale_hashes),
        "missing_required_column_count": len(missing_required_columns),
        "missing_prefix_column_count": len(missing_prefix_columns),
        "missing_outputs": [{"market": market, "year": year} for market, year in missing_pairs[:50]],
        "extra_outputs": [{"market": market, "year": year} for market, year in extra_pairs[:50]],
        "hash_failures": stale_hashes[:50],
        "missing_required_columns": missing_required_columns[:50],
        "missing_prefix_columns": missing_prefix_columns[:50],
        "failures": failures,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--causal-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--raw-alignment-report", required=True)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--resolved-profile", default=DEFAULT_RESOLVED_PROFILE)
    parser.add_argument("--expected-count", type=int, default=DEFAULT_EXPECTED_COUNT)
    parser.add_argument(
        "--required-column",
        action="append",
        default=list(DEFAULT_REQUIRED_COLUMNS),
        help="Required enrichment column; may be provided multiple times.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = audit_phase2_candidate(
        causal_root=Path(args.causal_root),
        manifest_path=Path(args.manifest),
        raw_alignment_path=Path(args.raw_alignment_report),
        expected_profile=args.profile,
        expected_resolved_profile=args.resolved_profile,
        expected_count=args.expected_count,
        required_columns=args.required_column,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
