#!/usr/bin/env python3
"""Build missing canonical Phase 4 baseline feature matrices."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.phase4_features.audit_feature_coverage import (
    DEFAULT_REPORTS_ROOT,
    build_coverage_audit,
    missing_feature_inputs,
    write_coverage_audit,
)
from scripts.phase4_features.build_baseline_features import (
    DEFAULT_COSTS_CONFIG,
    DEFAULT_INPUT_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_PROFILE_CONFIG,
    FeatureResult,
    process_file,
    relative_path,
    write_reports,
)


DEFAULT_PROFILE = "tier_3"


def _process_missing_file(task: tuple[str, int, str, str, str, str, str]) -> FeatureResult:
    market, year, input_path, output_root, profile, costs_config, input_root = task
    return process_file(
        Path(input_path),
        Path(output_root) / market / f"{year}.parquet",
        profile=profile,
        costs_config=Path(costs_config),
        input_root=Path(input_root),
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_missing_features(
    *,
    profile: str = DEFAULT_PROFILE,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    reports_root: Path = DEFAULT_REPORTS_ROOT,
    profile_config: Path = DEFAULT_PROFILE_CONFIG,
    costs_config: Path = DEFAULT_COSTS_CONFIG,
    max_files: int | None = None,
    workers: int = 1,
    dry_run: bool = False,
) -> dict[str, Any]:
    pre_audit = build_coverage_audit(
        profile=profile,
        input_root=input_root,
        output_root=output_root,
        profile_config=profile_config,
        collect_row_counts=False,
    )
    missing_inputs = missing_feature_inputs(pre_audit)
    if max_files is not None:
        missing_inputs = missing_inputs[:max_files]

    results: list[FeatureResult] = []
    if not dry_run:
        tasks = [
            (
                market,
                year,
                input_path.as_posix(),
                output_root.as_posix(),
                profile,
                costs_config.as_posix(),
                input_root.as_posix(),
            )
            for market, year, input_path in missing_inputs
        ]
        if workers <= 1:
            for task in tasks:
                result = _process_missing_file(task)
                results.append(result)
                print(
                    f"{result.status} {result.market} {result.year}: rows={result.output_rows} "
                    f"features={result.feature_count} warnings={len(result.warnings)} "
                    f"failures={len(result.failures)}",
                    flush=True,
                )
        else:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                future_to_task = {executor.submit(_process_missing_file, task): task for task in tasks}
                for future in as_completed(future_to_task):
                    result = future.result()
                    results.append(result)
                    print(
                        f"{result.status} {result.market} {result.year}: rows={result.output_rows} "
                        f"features={result.feature_count} warnings={len(result.warnings)} "
                        f"failures={len(result.failures)}",
                        flush=True,
                    )
            results.sort(key=lambda item: (item.market, item.year))

        if results:
            write_reports(
                results,
                profile=profile,
                input_root=input_root,
                output_root=output_root,
                reports_root=reports_root,
                profile_config=profile_config,
                costs_config=costs_config,
                input_selection={
                    "mode": "missing_only",
                    "pre_build_missing_features": pre_audit["missing_features"],
                    "selected_input_count": len(results),
                    "max_files": max_files,
                    "workers": workers,
                },
            )

    post_audit = build_coverage_audit(
        profile=profile,
        input_root=input_root,
        output_root=output_root,
        profile_config=profile_config,
        collect_row_counts=False,
    )
    write_coverage_audit(post_audit, reports_root)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "input_root": relative_path(input_root),
        "output_root": relative_path(output_root),
        "reports_root": relative_path(reports_root),
        "mode": "missing_only",
        "dry_run": dry_run,
        "max_files": max_files,
        "workers": workers,
        "pre_build": {
            "available_labeled": pre_audit["available_labeled"],
            "existing_features": pre_audit["existing_features"],
            "missing_features": pre_audit["missing_features"],
            "missing_tier3_count": pre_audit["missing_tier3_count"],
            "skipped_count": pre_audit["skipped_count"],
            "skipped_reasons": pre_audit["skipped_reasons"],
        },
        "post_build": {
            "available_labeled": post_audit["available_labeled"],
            "existing_features": post_audit["existing_features"],
            "missing_features": post_audit["missing_features"],
            "missing_tier3_count": post_audit["missing_tier3_count"],
            "skipped_count": post_audit["skipped_count"],
            "skipped_reasons": post_audit["skipped_reasons"],
        },
        "selected_missing_count": len(missing_inputs),
        "built_count": sum(result.status != "FAIL" for result in results),
        "failure_count": sum(result.status == "FAIL" for result in results),
        "warning_count": sum(len(result.warnings) for result in results),
        "failures": [failure for result in results for failure in result.failures],
        "warnings": [warning for result in results for warning in result.warnings],
        "outputs": [result.to_dict() for result in results],
    }
    _write_json(reports_root / "missing_baseline_feature_build_manifest.json", manifest)
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    manifest = build_missing_features(
        profile=args.profile,
        input_root=Path(args.input_root),
        output_root=Path(args.output_root),
        reports_root=Path(args.reports_root),
        profile_config=Path(args.profile_config),
        costs_config=Path(args.costs_config),
        max_files=args.max_files,
        workers=args.workers,
        dry_run=args.dry_run,
    )
    status = "FAIL" if manifest["failure_count"] else "PASS"
    print(
        f"{status} missing Phase 4 build:"
        f" pre_missing={manifest['pre_build']['missing_features']}"
        f" built={manifest['built_count']}"
        f" post_missing={manifest['post_build']['missing_features']}"
        f" failures={manifest['failure_count']}"
    )
    return 1 if manifest["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
