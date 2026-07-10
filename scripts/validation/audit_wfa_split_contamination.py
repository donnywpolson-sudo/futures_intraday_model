#!/usr/bin/env python3
"""Report-only WFA split-contamination guard for active v2 Tier 1 core."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from scripts.validation.feature_leakage_guard import forbidden_feature_columns
from scripts.validation.model_registry import resolve_purge_bars, validate_purge_policy


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "wfa_split_contamination_guard"
PASS_STATUS = "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD"
FAIL_STATUS = "FAIL_WFA_SPLIT_CONTAMINATION_GUARD"

DEFAULT_SPLIT_PLAN = Path("reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.json")
DEFAULT_FEATURE_ROOT = Path("data/feature_matrices")
DEFAULT_FEATURE_MANIFEST = Path(
    "reports/features_baseline/"
    "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "baseline_feature_manifest.json"
)
DEFAULT_MODELS_CONFIG = Path("configs/models.yaml")
DEFAULT_WFA_RUNNER = Path("scripts/phase7_wfa/run_wfa.py")
DEFAULT_REPORTS_ROOT = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_contamination_audit"
)
DEFAULT_MARKETS = ("6E", "CL", "ES", "ZN")
DEFAULT_YEARS = (2023, 2024)
DEFAULT_EXPECTED_FEATURE_COUNT = 114
DEFAULT_EXPECTED_FOLD_COUNT = 48

REPORT_JSON = "wfa_split_contamination_audit.json"
REPORT_MD = "wfa_split_contamination_audit.md"
REQUIRED_SCHEMA_COLUMNS = (
    "ts",
    "training_row_valid",
    "target_30m_valid",
    "target_60m_valid",
    "target_exit_ts_30m",
    "target_exit_ts_60m",
)
VALIDATION_KEYS = (
    "validation_start",
    "validation_end",
    "inner_validation_start",
    "inner_validation_end",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path.as_posix()}")
    return payload


def read_json_list(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"expected JSON string list: {path.as_posix()}")
    return list(payload)


def read_yaml_object(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"expected YAML object: {path.as_posix()}")
    return payload


def parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def expected_pairs(markets: Sequence[str], years: Sequence[int]) -> list[tuple[str, int]]:
    return [(market, int(year)) for market in markets for year in years]


def parse_ts(value: Any) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts)


def add_check(
    checks: list[dict[str, Any]],
    failures: list[str],
    warnings: list[str],
    *,
    name: str,
    passed: bool,
    evidence: Mapping[str, Any],
    failure: str,
    warning: str | None = None,
) -> None:
    status = "PASS" if passed else "FAIL"
    checks.append(
        {
            "name": name,
            "status": status,
            "evidence": dict(evidence),
            "failure": None if passed else failure,
            "warning": warning if passed else None,
        }
    )
    if passed and warning:
        warnings.append(f"{name}: {warning}")
    if not passed:
        failures.append(f"{name}: {failure}")


def load_feature_frames(
    *,
    feature_root: Path,
    markets: Sequence[str],
    years: Sequence[int],
) -> tuple[dict[str, pd.DataFrame], list[str], list[dict[str, Any]]]:
    frames: dict[str, list[pd.DataFrame]] = defaultdict(list)
    failures: list[str] = []
    summaries: list[dict[str, Any]] = []
    columns = ["ts", "target_exit_ts_30m", "target_exit_ts_60m", "training_row_valid"]
    for market, year in expected_pairs(markets, years):
        path = feature_root / market / f"{year}.parquet"
        if not path.is_file():
            failures.append(f"missing feature matrix: {path.as_posix()}")
            continue
        try:
            import pyarrow.parquet as pq

            schema = pq.read_schema(path)
            available = set(schema.names)
            metadata = pq.ParquetFile(path).metadata
        except Exception as exc:
            failures.append(f"unreadable feature schema {path.as_posix()}: {exc}")
            continue
        missing_required = sorted(set(REQUIRED_SCHEMA_COLUMNS) - available)
        summaries.append(
            {
                "path": path.as_posix(),
                "rows": int(metadata.num_rows),
                "columns": len(schema.names),
                "missing_required_columns": missing_required,
            }
        )
        if missing_required:
            failures.append(f"{path.as_posix()}: missing required columns {missing_required}")
            continue
        frame = pd.read_parquet(path, columns=columns)
        for column in ("ts", "target_exit_ts_30m", "target_exit_ts_60m"):
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
        frame["market"] = market
        frame["year"] = int(year)
        frames[market].append(frame)
    return (
        {
            market: pd.concat(parts, ignore_index=True).sort_values("ts").reset_index(drop=True)
            for market, parts in frames.items()
            if parts
        },
        failures,
        summaries,
    )


def split_scope_check(
    split_plan: Mapping[str, Any],
    *,
    markets: Sequence[str],
    years: Sequence[int],
    expected_fold_count: int,
) -> tuple[bool, dict[str, Any], list[str]]:
    failures: list[str] = []
    folds = split_plan.get("folds")
    if not isinstance(folds, list):
        folds = []
        failures.append("split plan folds is not a list")
    observed_markets = sorted(str(item) for item in split_plan.get("markets", []))
    observed_years = sorted(int(item) for item in split_plan.get("years", []))
    if observed_markets != sorted(markets):
        failures.append(f"markets mismatch: {observed_markets}")
    if observed_years != sorted(int(year) for year in years):
        failures.append(f"years mismatch: {observed_years}")
    if split_plan.get("profile") != "tier_1":
        failures.append(f"profile mismatch: {split_plan.get('profile')}")
    if split_plan.get("resolved_profile") != "tier_1_research":
        failures.append(f"resolved_profile mismatch: {split_plan.get('resolved_profile')}")
    if split_plan.get("input_root") != "data/feature_matrices":
        failures.append(f"input_root mismatch: {split_plan.get('input_root')}")
    if int(split_plan.get("fold_count") or -1) != expected_fold_count:
        failures.append(f"fold_count must be {expected_fold_count}")
    if int(split_plan.get("failure_count") or 0) != 0:
        failures.append("split plan failure_count is not zero")
    return (
        not failures,
        {
            "profile": split_plan.get("profile"),
            "resolved_profile": split_plan.get("resolved_profile"),
            "input_root": split_plan.get("input_root"),
            "markets": observed_markets,
            "years": observed_years,
            "fold_count": split_plan.get("fold_count"),
            "failure_count": split_plan.get("failure_count"),
        },
        failures,
    )


def feature_registry_check(
    *,
    feature_root: Path,
    feature_manifest: Mapping[str, Any],
    markets: Sequence[str],
    years: Sequence[int],
    expected_feature_count: int,
) -> tuple[bool, dict[str, Any], list[str]]:
    failures: list[str] = []
    feature_cols = read_json_list(feature_root / "feature_cols.json")
    target_cols = read_json_list(feature_root / "target_cols.json")
    forbidden = forbidden_feature_columns(feature_cols)
    target_intersection = sorted(set(feature_cols) & set(target_cols))
    duplicate_features = sorted(
        column for column, count in Counter(feature_cols).items() if count > 1
    )
    if forbidden:
        failures.append(f"forbidden feature columns: {forbidden}")
    if target_intersection:
        failures.append(f"feature/target registry intersection: {target_intersection}")
    if duplicate_features:
        failures.append(f"duplicate feature columns: {duplicate_features}")
    if feature_manifest.get("status") != "PASS":
        failures.append(f"feature manifest status is {feature_manifest.get('status')}")
    if int(feature_manifest.get("failure_count") or 0) != 0:
        failures.append("feature manifest failure_count is not zero")
    if feature_manifest.get("profile") != "tier_1":
        failures.append(f"feature manifest profile mismatch: {feature_manifest.get('profile')}")
    if feature_manifest.get("resolved_profile") != "tier_1_research":
        failures.append(
            f"feature manifest resolved_profile mismatch: {feature_manifest.get('resolved_profile')}"
        )
    if feature_manifest.get("output_root") != "data/feature_matrices":
        failures.append(f"feature manifest output_root mismatch: {feature_manifest.get('output_root')}")
    if int(feature_manifest.get("feature_count") or -1) != expected_feature_count:
        failures.append(f"feature manifest feature_count must be {expected_feature_count}")
    if len(feature_cols) != expected_feature_count:
        failures.append(f"feature_cols.json count must be {expected_feature_count}")
    if sorted(str(item) for item in feature_manifest.get("markets", [])) != sorted(markets):
        failures.append("feature manifest markets mismatch")
    if sorted(int(item) for item in feature_manifest.get("years", [])) != sorted(years):
        failures.append("feature manifest years mismatch")
    schema_failures: list[str] = []
    for market, year in expected_pairs(markets, years):
        path = feature_root / market / f"{year}.parquet"
        try:
            import pyarrow.parquet as pq

            names = set(pq.read_schema(path).names)
        except Exception as exc:
            schema_failures.append(f"{path.as_posix()}: unreadable schema {exc}")
            continue
        missing_features = sorted(set(feature_cols) - names)
        missing_targets = sorted(set(target_cols) - names)
        if missing_features:
            schema_failures.append(f"{path.as_posix()}: missing features {missing_features[:10]}")
        if missing_targets:
            schema_failures.append(f"{path.as_posix()}: missing targets {missing_targets[:10]}")
    failures.extend(schema_failures)
    return (
        not failures,
        {
            "feature_count": len(feature_cols),
            "target_count": len(target_cols),
            "forbidden_feature_columns": forbidden,
            "target_intersection": target_intersection,
            "duplicate_features": duplicate_features,
            "schema_failure_count": len(schema_failures),
        },
        failures,
    )


def purge_policy_check(
    *,
    models_config: Mapping[str, Any],
    split_plan: Mapping[str, Any],
    expected_dependency_bars: int,
) -> tuple[bool, dict[str, Any], list[str]]:
    failures = validate_purge_policy(dict(models_config))
    purge = models_config.get("purge", {})
    if not isinstance(purge, Mapping):
        purge = {}
        failures.append("models.yaml purge mapping missing")
    try:
        resolved = resolve_purge_bars(dict(purge))
    except Exception as exc:
        resolved = None
        failures.append(f"cannot resolve purge bars: {exc}")
    embargo_config = int(purge.get("embargo_bars", resolved or -1))
    if resolved != expected_dependency_bars:
        failures.append(f"resolved purge must be {expected_dependency_bars}, got {resolved}")
    if embargo_config < expected_dependency_bars:
        failures.append(
            f"configured embargo must be at least {expected_dependency_bars}, got {embargo_config}"
        )
    split_policy = split_plan.get("purge_policy")
    split_policy = split_policy if isinstance(split_policy, Mapping) else {}
    for key in ("purge_bars", "resolved_purge_bars", "embargo_bars"):
        if int(split_policy.get(key) or -1) < expected_dependency_bars:
            failures.append(f"split purge_policy {key} is below {expected_dependency_bars}")
    policy = models_config.get("policy", {})
    if not isinstance(policy, Mapping) or policy.get("random_splits_allowed") is not False:
        failures.append("random_splits_allowed must be false")
    if not isinstance(policy, Mapping) or policy.get("final_holdout_tuning_allowed") is not False:
        failures.append("final_holdout_tuning_allowed must be false")
    return (
        not failures,
        {
            "models_purge": dict(purge),
            "resolved_purge_bars": resolved,
            "configured_embargo_bars": embargo_config,
            "split_purge_policy": dict(split_policy),
            "policy": dict(policy) if isinstance(policy, Mapping) else policy,
        },
        failures,
    )


def same_fold_checks(
    *,
    folds: Sequence[Mapping[str, Any]],
    feature_frames: Mapping[str, pd.DataFrame],
    expected_dependency_bars: int,
) -> tuple[bool, dict[str, Any], list[str]]:
    failures: list[str] = []
    max_exit_by_fold: dict[str, str | None] = {}
    min_gap_minutes: float | None = None
    purged_train_rows_below_dependency: list[str] = []
    for fold in folds:
        fold_id = str(fold.get("fold_id", "<unknown>"))
        market = str(fold.get("market", ""))
        train_start = parse_ts(fold.get("train_start"))
        purged_train_end = parse_ts(fold.get("purged_train_end"))
        test_start = parse_ts(fold.get("test_start"))
        test_end = parse_ts(fold.get("test_end"))
        if any(value is None for value in (train_start, purged_train_end, test_start, test_end)):
            failures.append(f"{fold_id}: missing fold timestamps")
            continue
        if not (train_start <= purged_train_end < test_start <= test_end):
            failures.append(f"{fold_id}: train/test chronology violation")
        if int(fold.get("train_rows_after_purge") or 0) <= 0:
            failures.append(f"{fold_id}: non-positive train_rows_after_purge")
        if int(fold.get("test_rows") or 0) <= 0:
            failures.append(f"{fold_id}: non-positive test_rows")
        if int(fold.get("purge_bars") or -1) < expected_dependency_bars:
            failures.append(f"{fold_id}: purge_bars below {expected_dependency_bars}")
        if int(fold.get("resolved_purge_bars") or -1) < expected_dependency_bars:
            failures.append(f"{fold_id}: resolved_purge_bars below {expected_dependency_bars}")
        if int(fold.get("purged_train_rows") or -1) < expected_dependency_bars:
            purged_train_rows_below_dependency.append(fold_id)
        gap = (test_start - purged_train_end).total_seconds() / 60.0
        min_gap_minutes = gap if min_gap_minutes is None else min(min_gap_minutes, gap)
        frame = feature_frames.get(market)
        if frame is None:
            failures.append(f"{fold_id}: missing loaded feature frame for {market}")
            continue
        mask = frame["ts"].ge(train_start) & frame["ts"].le(purged_train_end)
        train_rows = frame.loc[mask]
        if train_rows.empty:
            failures.append(f"{fold_id}: no rows found in purged train interval")
            continue
        max_exit = train_rows[["target_exit_ts_30m", "target_exit_ts_60m"]].max().max()
        max_exit_by_fold[fold_id] = None if pd.isna(max_exit) else pd.Timestamp(max_exit).isoformat()
        if pd.notna(max_exit) and pd.Timestamp(max_exit) >= test_start:
            failures.append(f"{fold_id}: train target horizon reaches test_start")
    purged_counts = [
        int(fold.get("purged_train_rows") or -1)
        for fold in folds
        if fold.get("purged_train_rows") is not None
    ]
    return (
        not failures,
        {
            "fold_count": len(folds),
            "min_gap_minutes": min_gap_minutes,
            "min_purged_train_rows_metadata": min(purged_counts) if purged_counts else None,
            "purged_train_rows_metadata_below_dependency_count": len(
                purged_train_rows_below_dependency
            ),
            "purged_train_rows_metadata_below_dependency_sample": (
                purged_train_rows_below_dependency[:8]
            ),
            "max_train_target_exit_ts_by_fold_sample": dict(list(max_exit_by_fold.items())[:8]),
        },
        failures,
    )


def embargo_and_reuse_checks(
    *,
    folds: Sequence[Mapping[str, Any]],
    expected_dependency_bars: int,
) -> tuple[bool, dict[str, Any], list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    reuse_pairs: list[dict[str, str]] = []
    embargo_intrusions: list[dict[str, str]] = []
    by_market: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for fold in folds:
        by_market[str(fold.get("market", ""))].append(fold)
        if int(fold.get("embargo_bars") or -1) < expected_dependency_bars:
            failures.append(f"{fold.get('fold_id', '<unknown>')}: embargo_bars below {expected_dependency_bars}")
    for market, market_folds in by_market.items():
        ordered = sorted(market_folds, key=lambda item: int(item.get("fold_number") or 0))
        for index, current in enumerate(ordered):
            current_train_start = parse_ts(current.get("train_start"))
            current_train_end = parse_ts(current.get("purged_train_end"))
            if current_train_start is None or current_train_end is None:
                continue
            for previous in ordered[:index]:
                previous_test_start = parse_ts(previous.get("test_start"))
                previous_test_end = parse_ts(previous.get("test_end"))
                previous_embargo_end = parse_ts(previous.get("embargo_end"))
                if previous_test_start is None or previous_test_end is None:
                    continue
                if current_train_start <= previous_test_end and current_train_end >= previous_test_start:
                    reuse_pairs.append(
                        {
                            "market": market,
                            "current_fold": str(current.get("fold_id")),
                            "prior_oos_fold": str(previous.get("fold_id")),
                        }
                    )
                if (
                    previous_embargo_end is not None
                    and current_train_start <= previous_embargo_end
                    and current_train_end > previous_test_end
                ):
                    embargo_intrusions.append(
                        {
                            "market": market,
                            "current_fold": str(current.get("fold_id")),
                            "prior_oos_fold": str(previous.get("fold_id")),
                        }
                    )
    if reuse_pairs:
        warnings.append(
            "WARN_EXPECTED_ROLLING_RETRAINING_REUSE: later folds train on earlier OOS windows; "
            "metrics are rolling-retraining research evidence, not independent holdout evidence"
        )
    if embargo_intrusions:
        warnings.append(
            "WARN_ROLLING_RETRAINING_PRIOR_EMBARGO_REUSE: later folds train on earlier fold "
            "embargo windows; metrics are not independent holdout evidence"
        )
    return (
        not failures,
        {
            "prior_oos_reuse_pair_count": len(reuse_pairs),
            "prior_oos_reuse_sample": reuse_pairs[:8],
            "prior_embargo_intrusion_count": len(embargo_intrusions),
            "prior_embargo_intrusion_sample": embargo_intrusions[:8],
        },
        failures,
        warnings,
    )


def validation_window_check(folds: Sequence[Mapping[str, Any]]) -> tuple[bool, dict[str, Any], str | None]:
    folds_with_validation = [
        str(fold.get("fold_id"))
        for fold in folds
        if any(key in fold and fold.get(key) not in (None, "") for key in VALIDATION_KEYS)
    ]
    if not folds_with_validation:
        return (
            True,
            {"folds_with_validation_window": 0, "validation_keys": list(VALIDATION_KEYS)},
            "WARN_NO_INNER_VALIDATION_WINDOW: model/threshold/calibration selection remains blocked",
        )
    return (
        True,
        {
            "folds_with_validation_window": len(folds_with_validation),
            "fold_sample": folds_with_validation[:8],
        },
        None,
    )


def runner_static_check(wfa_runner: Path) -> tuple[bool, dict[str, Any], list[str]]:
    source = wfa_runner.read_text(encoding="utf-8")
    required_patterns = {
        "train_test_timestamp_guard": r'train\["ts"\]\.max\(\)\s*>=\s*test\["ts"\]\.min\(\)',
        "x_train_from_train_frame": r"x_train\s*=\s*train\[feature_cols\]",
        "x_test_from_test_frame": r"x_test\s*=\s*test\[feature_cols\]",
        "estimator_fit_on_train_only": r"estimator\.fit\(x_train,\s*y_train\)",
    }
    missing = [
        name for name, pattern in required_patterns.items() if re.search(pattern, source) is None
    ]
    suspicious_patterns = {
        "full_frame_fit_feature_cols": r"\.fit\(\s*frame\[feature_cols\]",
        "full_frame_fit_transform": r"fit_transform\(\s*frame",
        "full_output_fit": r"\.fit\(\s*output",
    }
    suspicious = [
        name for name, pattern in suspicious_patterns.items() if re.search(pattern, source) is not None
    ]
    failures: list[str] = []
    if missing:
        failures.append(f"missing required runner train-only patterns: {missing}")
    if suspicious:
        failures.append(f"suspicious full-sample fit patterns found: {suspicious}")
    return (
        not failures,
        {
            "runner": wfa_runner.as_posix(),
            "required_patterns_present": sorted(set(required_patterns) - set(missing)),
            "missing_required_patterns": missing,
            "suspicious_patterns": suspicious,
            "parameter_reuse_detected": False,
            "classification": "per-fold refit expected from runner source" if not failures else "blocked",
        },
        failures,
    )


def build_report(
    *,
    repo_root: Path,
    split_plan_path: Path,
    feature_root: Path,
    feature_manifest_path: Path,
    models_config_path: Path,
    wfa_runner_path: Path,
    reports_root: Path,
    markets: Sequence[str],
    years: Sequence[int],
    expected_feature_count: int = DEFAULT_EXPECTED_FEATURE_COUNT,
    expected_fold_count: int = DEFAULT_EXPECTED_FOLD_COUNT,
    write_reports: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []

    split_plan = read_json_object(split_plan_path)
    feature_manifest = read_json_object(feature_manifest_path)
    models_config = read_yaml_object(models_config_path)
    folds = split_plan.get("folds", [])
    folds = folds if isinstance(folds, list) else []
    purge = models_config.get("purge", {})
    try:
        expected_dependency_bars = resolve_purge_bars(dict(purge)) if isinstance(purge, Mapping) else 61
    except Exception:
        expected_dependency_bars = 61

    passed, evidence, check_failures = split_scope_check(
        split_plan,
        markets=markets,
        years=years,
        expected_fold_count=expected_fold_count,
    )
    add_check(
        checks,
        failures,
        warnings,
        name="scope_and_split_plan_evidence",
        passed=passed,
        evidence=evidence,
        failure="; ".join(check_failures),
    )

    passed, evidence, check_failures = feature_registry_check(
        feature_root=feature_root,
        feature_manifest=feature_manifest,
        markets=markets,
        years=years,
        expected_feature_count=expected_feature_count,
    )
    add_check(
        checks,
        failures,
        warnings,
        name="feature_manifest_registry_and_schema_guard",
        passed=passed,
        evidence=evidence,
        failure="; ".join(check_failures),
    )

    passed, evidence, check_failures = purge_policy_check(
        models_config=models_config,
        split_plan=split_plan,
        expected_dependency_bars=expected_dependency_bars,
    )
    add_check(
        checks,
        failures,
        warnings,
        name="purge_embargo_policy_covers_30m60m_dependency",
        passed=passed,
        evidence=evidence,
        failure="; ".join(check_failures),
    )

    frames, frame_failures, schema_summary = load_feature_frames(
        feature_root=feature_root,
        markets=markets,
        years=years,
    )
    add_check(
        checks,
        failures,
        warnings,
        name="feature_matrix_timestamp_schema_loadable",
        passed=not frame_failures and len(schema_summary) == len(expected_pairs(markets, years)),
        evidence={"schema_summary": schema_summary, "load_failures": frame_failures},
        failure="; ".join(frame_failures) or "unexpected feature file count",
    )

    passed, evidence, check_failures = same_fold_checks(
        folds=folds,
        feature_frames=frames,
        expected_dependency_bars=expected_dependency_bars,
    )
    add_check(
        checks,
        failures,
        warnings,
        name="same_fold_train_test_and_target_horizon_separation",
        passed=passed,
        evidence=evidence,
        failure="; ".join(check_failures),
    )

    passed, evidence, check_failures, check_warnings = embargo_and_reuse_checks(
        folds=folds,
        expected_dependency_bars=expected_dependency_bars,
    )
    add_check(
        checks,
        failures,
        warnings,
        name="embargo_and_later_fold_oos_reuse_classification",
        passed=passed,
        evidence=evidence,
        failure="; ".join(check_failures),
        warning="; ".join(check_warnings) if check_warnings else None,
    )

    passed, evidence, warning = validation_window_check(folds)
    add_check(
        checks,
        failures,
        warnings,
        name="validation_window_presence",
        passed=passed,
        evidence=evidence,
        failure="validation window check failed",
        warning=warning,
    )

    passed, evidence, check_failures = runner_static_check(wfa_runner_path)
    add_check(
        checks,
        failures,
        warnings,
        name="wfa_runner_train_only_transform_and_parameter_reuse_guard",
        passed=passed,
        evidence=evidence,
        failure="; ".join(check_failures),
    )

    status = FAIL_STATUS if failures else PASS_STATUS
    outputs = {
        "json": rel(reports_root / REPORT_JSON, repo_root),
        "markdown": rel(reports_root / REPORT_MD, repo_root),
    }
    report = {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": utc_now(),
        "scope": {
            "markets": list(markets),
            "years": [int(year) for year in years],
            "expected_fold_count": expected_fold_count,
            "expected_feature_count": expected_feature_count,
        },
        "summary": {
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "fold_count": len(folds),
            "market_year_count": len(expected_pairs(markets, years)),
            "model_trust_ready": False,
            "valid_for_independent_holdout_claims": False,
            "valid_for_same_fold_rolling_retraining_research_evidence": not failures,
            "classification": (
                "same_fold_rolling_retraining_research_only" if not failures else "blocked"
            ),
        },
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "input_evidence": {
            "split_plan": rel(split_plan_path, repo_root),
            "feature_root": rel(feature_root, repo_root),
            "feature_manifest": rel(feature_manifest_path, repo_root),
            "models_config": rel(models_config_path, repo_root),
            "wfa_runner": rel(wfa_runner_path, repo_root),
        },
        "outputs": outputs,
        "non_approval": {
            "wfa_modeling": False,
            "prediction_generation": False,
            "phase8_refresh": False,
            "promotion_or_artifact_freeze": False,
            "final_holdout": False,
            "paper_or_live": False,
            "provider_or_network": False,
            "data_mutation": False,
            "git_staging_commit_push": False,
        },
    }
    if write_reports:
        write_report(report, reports_root)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# WFA Split Contamination Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Classification: `{summary['classification']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Warnings: `{summary['warning_count']}`",
        f"- Valid for independent holdout claims: `{summary['valid_for_independent_holdout_claims']}`",
        f"- Valid for same-fold rolling-retraining research evidence: `{summary['valid_for_same_fold_rolling_retraining_research_evidence']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Failure | Warning |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        failure = str(check.get("failure") or "").replace("|", "\\|")
        warning = str(check.get("warning") or "").replace("|", "\\|")
        lines.append(f"| `{check['name']}` | `{check['status']}` | {failure} | {warning} |")
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in report["failures"]] or ["- None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in report["warnings"]] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Approval",
            "",
            "- This report does not approve WFA/modeling, predictions, Phase 8, promotion, artifact freeze, final holdout, paper/live work, provider calls, cleanup, staging, commit, or push.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    (reports_root / REPORT_JSON).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (reports_root / REPORT_MD).write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--split-plan", default=str(DEFAULT_SPLIT_PLAN))
    parser.add_argument("--feature-root", default=str(DEFAULT_FEATURE_ROOT))
    parser.add_argument("--feature-manifest", default=str(DEFAULT_FEATURE_MANIFEST))
    parser.add_argument("--models-config", default=str(DEFAULT_MODELS_CONFIG))
    parser.add_argument("--wfa-runner", default=str(DEFAULT_WFA_RUNNER))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    parser.add_argument("--expected-feature-count", type=int, default=DEFAULT_EXPECTED_FEATURE_COUNT)
    parser.add_argument("--expected-fold-count", type=int, default=DEFAULT_EXPECTED_FOLD_COUNT)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    report = build_report(
        repo_root=repo_root,
        split_plan_path=resolve_path(repo_root, args.split_plan),
        feature_root=resolve_path(repo_root, args.feature_root),
        feature_manifest_path=resolve_path(repo_root, args.feature_manifest),
        models_config_path=resolve_path(repo_root, args.models_config),
        wfa_runner_path=resolve_path(repo_root, args.wfa_runner),
        reports_root=resolve_path(repo_root, args.reports_root),
        markets=parse_csv_strings(args.markets),
        years=parse_csv_ints(args.years),
        expected_feature_count=int(args.expected_feature_count),
        expected_fold_count=int(args.expected_fold_count),
        write_reports=True,
    )
    print(
        f"{report['status']} failures={report['summary']['failure_count']} "
        f"warnings={report['summary']['warning_count']} "
        f"classification={report['summary']['classification']} "
        f"json={report['outputs']['json']} md={report['outputs']['markdown']}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
