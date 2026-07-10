#!/usr/bin/env python3
"""Validate hardened Phase 5 WFA split plans without running models."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PASS_STATUS = "PASS_HARDENED_PHASE5_SPLIT_PLAN_ACCEPTED_NO_MODELING"
FAIL_STATUS = "FAIL_HARDENED_PHASE5_SPLIT_PLAN_REJECTED_NO_MODELING"
REPORT_JSON = "hardened_split_acceptance_report.json"
REPORT_MD = "hardened_split_acceptance_report.md"
DEFAULT_MARKETS = ("6E", "CL", "ES", "ZN")
DEFAULT_YEARS = (2023, 2024)
DEFAULT_MIN_TRAIN_ROWS = 100_000
DEFAULT_MIN_VALIDATION_ROWS = 50_000
DEFAULT_MIN_TEST_ROWS = 50_000
DEFAULT_MIN_REQUIRED_BARS = 61

REQUIRED_FOLD_FIELDS = (
    "market",
    "fold_id",
    "fold_number",
    "year",
    "split_group",
    "train_start",
    "train_end",
    "purged_train_end",
    "validation_start",
    "validation_end",
    "validation_embargo_end",
    "test_start",
    "test_end",
    "test_embargo_end",
    "train_rows_before_purge",
    "train_rows_after_purge",
    "purged_train_rows",
    "validation_rows",
    "validation_embargo_rows",
    "test_rows",
    "test_embargo_rows",
    "purge_bars",
    "resolved_purge_bars",
    "embargo_bars",
    "hardened_split_type",
    "independent_test_claim_allowed",
    "selection_source",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, repo_root: Path | None = None) -> str:
    root = repo_root or Path.cwd()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def expected_feature_paths(markets: Sequence[str], years: Sequence[int]) -> list[str]:
    return [
        f"data/feature_matrices/{market}/{int(year)}.parquet"
        for market in markets
        for year in years
    ]


def ts(value: Any) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def int_field(mapping: Mapping[str, Any], key: str, *, default: int = -1) -> int:
    value = mapping.get(key, default)
    if value is None:
        return default
    return int(value)


def add_check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    observed: Mapping[str, Any],
    expected: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": dict(observed),
            "expected": expected,
        }
    )
    if not passed:
        failures.append(f"{name}: {observed}")


def scope_failures(split_plan: Mapping[str, Any], markets: Sequence[str], years: Sequence[int]) -> list[str]:
    failures: list[str] = []
    observed_markets = sorted(str(market) for market in split_plan.get("markets", []))
    observed_years = sorted(int(year) for year in split_plan.get("years", []))
    if observed_markets != sorted(markets):
        failures.append(f"markets mismatch: {observed_markets}")
    if observed_years != sorted(int(year) for year in years):
        failures.append(f"years mismatch: {observed_years}")
    if any(year in {2025, 2026} for year in observed_years):
        failures.append(f"forbidden forward/final-holdout year present: {observed_years}")
    if split_plan.get("profile") != "tier_1":
        failures.append(f"profile mismatch: {split_plan.get('profile')}")
    if split_plan.get("resolved_profile") != "tier_1_research":
        failures.append(f"resolved_profile mismatch: {split_plan.get('resolved_profile')}")
    if split_plan.get("input_root") != "data/feature_matrices":
        failures.append(f"input_root mismatch: {split_plan.get('input_root')}")
    return failures


def fold_schema_failures(folds: Sequence[Mapping[str, Any]], markets: Sequence[str]) -> list[str]:
    failures: list[str] = []
    if len(folds) != len(markets):
        failures.append(f"fold_count must be {len(markets)}, got {len(folds)}")
    counts = Counter(str(fold.get("market")) for fold in folds)
    if counts != Counter(str(market) for market in markets):
        failures.append(f"fold markets must be one per market: {dict(counts)}")
    for fold in folds:
        missing = [field for field in REQUIRED_FOLD_FIELDS if field not in fold]
        if missing:
            failures.append(f"{fold.get('fold_id', '<missing_fold_id>')}: missing fields {missing}")
        if fold.get("hardened_split_type") != "fixed_train_validation_test":
            failures.append(f"{fold.get('fold_id')}: hardened_split_type mismatch")
        if fold.get("independent_test_claim_allowed") is not True:
            failures.append(f"{fold.get('fold_id')}: independent_test_claim_allowed must be true")
        if fold.get("selection_source") != "validation_only":
            failures.append(f"{fold.get('fold_id')}: selection_source must be validation_only")
        if fold.get("final_holdout") is True or fold.get("is_final_holdout") is True:
            failures.append(f"{fold.get('fold_id')}: final holdout is not allowed")
    return failures


def row_threshold_failures(
    folds: Sequence[Mapping[str, Any]],
    *,
    min_train_rows: int,
    min_validation_rows: int,
    min_test_rows: int,
) -> list[str]:
    failures: list[str] = []
    for fold in folds:
        fold_id = fold.get("fold_id")
        if int_field(fold, "train_rows_after_purge") < min_train_rows:
            failures.append(f"{fold_id}: train_rows_after_purge below {min_train_rows}")
        if int_field(fold, "validation_rows") < min_validation_rows:
            failures.append(f"{fold_id}: validation_rows below {min_validation_rows}")
        if int_field(fold, "test_rows") < min_test_rows:
            failures.append(f"{fold_id}: test_rows below {min_test_rows}")
    return failures


def timing_failures(folds: Sequence[Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    for fold in folds:
        fold_id = str(fold.get("fold_id"))
        values = {
            key: ts(fold.get(key))
            for key in (
                "train_start",
                "purged_train_end",
                "validation_start",
                "validation_end",
                "validation_embargo_end",
                "test_start",
                "test_end",
                "test_embargo_end",
            )
        }
        missing = [key for key, value in values.items() if value is None]
        if missing:
            failures.append(f"{fold_id}: invalid timestamps {missing}")
            continue
        assert all(value is not None for value in values.values())
        ordered = (
            values["train_start"]
            <= values["purged_train_end"]
            < values["validation_start"]
            <= values["validation_end"]
            < values["validation_embargo_end"]
            < values["test_start"]
            <= values["test_end"]
            < values["test_embargo_end"]
        )
        if not ordered:
            failures.append(f"{fold_id}: train/validation/test boundaries overlap or are unordered")
    return failures


def purge_embargo_failures(
    split_plan: Mapping[str, Any],
    folds: Sequence[Mapping[str, Any]],
    *,
    minimum_required_bars: int,
) -> list[str]:
    failures: list[str] = []
    policy = split_plan.get("purge_policy")
    policy = policy if isinstance(policy, Mapping) else {}
    for key in ("purge_bars", "resolved_purge_bars", "embargo_bars"):
        if int_field(policy, key) < minimum_required_bars:
            failures.append(f"purge_policy {key} below {minimum_required_bars}")
    for fold in folds:
        fold_id = fold.get("fold_id")
        for key in ("purge_bars", "resolved_purge_bars", "embargo_bars"):
            if int_field(fold, key) < minimum_required_bars:
                failures.append(f"{fold_id}: {key} below {minimum_required_bars}")
        if int_field(fold, "purged_train_rows") < minimum_required_bars:
            failures.append(f"{fold_id}: purged_train_rows below {minimum_required_bars}")
        if int_field(fold, "validation_embargo_rows") < minimum_required_bars:
            failures.append(f"{fold_id}: validation_embargo_rows below {minimum_required_bars}")
        if int_field(fold, "test_embargo_rows") < minimum_required_bars:
            failures.append(f"{fold_id}: test_embargo_rows below {minimum_required_bars}")
    return failures


def hash_scope_failures(split_plan: Mapping[str, Any], markets: Sequence[str], years: Sequence[int]) -> list[str]:
    input_hashes = split_plan.get("input_file_hashes")
    input_hashes = input_hashes if isinstance(input_hashes, Mapping) else {}
    expected = sorted(expected_feature_paths(markets, years))
    observed = sorted(str(path) for path in input_hashes)
    if observed != expected:
        return [f"input_file_hashes paths mismatch: {observed}"]
    missing_hashes = [path for path, value in input_hashes.items() if not value or value == "MISSING"]
    if missing_hashes:
        return [f"input_file_hashes missing values: {missing_hashes}"]
    return []


def later_fold_reuse_failures(folds: Sequence[Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    by_market: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for fold in folds:
        by_market[str(fold.get("market"))].append(fold)
    for market, market_folds in by_market.items():
        ordered = sorted(market_folds, key=lambda fold: ts(fold.get("test_start")) or pd.Timestamp.min.tz_localize("UTC"))
        prior_block_ends: list[tuple[str, pd.Timestamp]] = []
        for fold in ordered:
            fold_id = str(fold.get("fold_id"))
            train_end = ts(fold.get("purged_train_end"))
            for prior_id, block_end in prior_block_ends:
                if train_end is not None and train_end >= block_end:
                    failures.append(
                        f"{market}: {fold_id} trains through prior OOS/embargo block from {prior_id}"
                    )
            validation_embargo_end = ts(fold.get("validation_embargo_end"))
            test_embargo_end = ts(fold.get("test_embargo_end"))
            if validation_embargo_end is not None:
                prior_block_ends.append((fold_id, validation_embargo_end))
            if test_embargo_end is not None:
                prior_block_ends.append((fold_id, test_embargo_end))
    return failures


def build_acceptance_report(
    *,
    split_plan: Mapping[str, Any],
    split_plan_path: Path,
    reports_root: Path,
    markets: Sequence[str] = DEFAULT_MARKETS,
    years: Sequence[int] = DEFAULT_YEARS,
    min_train_rows: int = DEFAULT_MIN_TRAIN_ROWS,
    min_validation_rows: int = DEFAULT_MIN_VALIDATION_ROWS,
    min_test_rows: int = DEFAULT_MIN_TEST_ROWS,
    minimum_required_bars: int = DEFAULT_MIN_REQUIRED_BARS,
    generated_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    folds = split_plan.get("folds")
    folds = folds if isinstance(folds, list) else []

    scope = scope_failures(split_plan, markets, years)
    add_check(
        checks,
        failures,
        name="exact_hardened_scope",
        passed=not scope,
        observed={"failures": scope, "markets": split_plan.get("markets"), "years": split_plan.get("years")},
        expected="tier_1/tier_1_research 6E,CL,ES,ZN years 2023,2024 only",
    )

    schema = fold_schema_failures(folds, markets)
    add_check(
        checks,
        failures,
        name="fold_schema_one_per_market",
        passed=not schema,
        observed={"failures": schema, "fold_count": len(folds)},
        expected="4 hardened folds, one per market, with validation/test fields",
    )

    thresholds = row_threshold_failures(
        folds,
        min_train_rows=min_train_rows,
        min_validation_rows=min_validation_rows,
        min_test_rows=min_test_rows,
    )
    add_check(
        checks,
        failures,
        name="minimum_train_validation_test_rows",
        passed=not thresholds,
        observed={
            "failures": thresholds,
            "min_train_rows": min_train_rows,
            "min_validation_rows": min_validation_rows,
            "min_test_rows": min_test_rows,
        },
        expected="all folds meet predeclared minimum row thresholds",
    )

    timing = timing_failures(folds)
    add_check(
        checks,
        failures,
        name="non_overlapping_train_validation_test_timing",
        passed=not timing,
        observed={"failures": timing},
        expected="train < validation < validation embargo < test < test embargo",
    )

    purge = purge_embargo_failures(
        split_plan,
        folds,
        minimum_required_bars=minimum_required_bars,
    )
    add_check(
        checks,
        failures,
        name="purge_embargo_minimums",
        passed=not purge,
        observed={"failures": purge, "minimum_required_bars": minimum_required_bars},
        expected="purge and embargo fields meet the required bar count",
    )

    hashes = hash_scope_failures(split_plan, markets, years)
    add_check(
        checks,
        failures,
        name="input_hash_scope",
        passed=not hashes,
        observed={"failures": hashes},
        expected="input hashes cover exactly the 8 active v2 feature matrices",
    )

    reuse = later_fold_reuse_failures(folds)
    add_check(
        checks,
        failures,
        name="no_later_fold_oos_or_embargo_reuse",
        passed=not reuse,
        observed={"failures": reuse},
        expected="later folds must not train through prior validation/test/embargo blocks",
    )

    status = PASS_STATUS if not failures else FAIL_STATUS
    return {
        "stage": "phase5_hardened_split_acceptance",
        "status": status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "fold_count": len(folds),
            "market_count": len(markets),
            "independent_test_claim_allowed": status == PASS_STATUS,
            "modeling_allowed": False,
            "prediction_materialization_allowed": False,
            "phase8_refresh_allowed": False,
        },
        "checks": checks,
        "failures": failures,
        "input_evidence": {"split_plan": rel(split_plan_path, repo_root)},
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Hardened Phase 5 Split Acceptance",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Fold count: `{summary['fold_count']}`",
        f"- Independent test claim allowed: `{summary['independent_test_claim_allowed']}`",
        f"- Modeling allowed: `{summary['modeling_allowed']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['name']}` | `{check['status']}` |")
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in report["failures"]:
            lines.append(f"- {failure}")
    lines.extend(
        [
            "",
            "## Non-Approval",
            "",
            "- This report does not run WFA modeling, materialize predictions, refresh Phase 8, approve promotion, touch final holdout, write prop-account reports, run provider/download commands, mutate data, clean up files, stage, commit, or push.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    (reports_root / REPORT_JSON).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (reports_root / REPORT_MD).write_text(render_markdown(report), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-plan", required=True)
    parser.add_argument("--reports-root", required=True)
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    parser.add_argument("--min-train-rows", type=int, default=DEFAULT_MIN_TRAIN_ROWS)
    parser.add_argument("--min-validation-rows", type=int, default=DEFAULT_MIN_VALIDATION_ROWS)
    parser.add_argument("--min-test-rows", type=int, default=DEFAULT_MIN_TEST_ROWS)
    parser.add_argument("--minimum-required-bars", type=int, default=DEFAULT_MIN_REQUIRED_BARS)
    args = parser.parse_args(argv)

    split_plan_path = Path(args.split_plan)
    reports_root = Path(args.reports_root)
    split_plan = json.loads(split_plan_path.read_text(encoding="utf-8"))
    if not isinstance(split_plan, Mapping):
        raise SystemExit("split plan must be a JSON object")
    report = build_acceptance_report(
        split_plan=split_plan,
        split_plan_path=split_plan_path,
        reports_root=reports_root,
        markets=parse_csv_strings(args.markets),
        years=parse_csv_ints(args.years),
        min_train_rows=args.min_train_rows,
        min_validation_rows=args.min_validation_rows,
        min_test_rows=args.min_test_rows,
        minimum_required_bars=args.minimum_required_bars,
    )
    write_report(report, reports_root)
    print(
        f"{report['stage']} status={report['status']} "
        f"failures={report['summary']['failure_count']} json={reports_root / REPORT_JSON}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
