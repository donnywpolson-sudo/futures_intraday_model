#!/usr/bin/env python3
"""Report-only target timing audit for active v2 Tier 1 core labels/features."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.pipeline_gates import file_sha256


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "target_timing_v2_tier1_core"
PASS_STATUS = "PASS_TARGET_TIMING_AUDIT"
FAIL_STATUS = "FAIL_TARGET_TIMING_AUDIT"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_FILE_COUNT = len(EXPECTED_MARKETS) * len(EXPECTED_YEARS)
LABEL_SEMANTICS_ID = "phase3_labels_v2_next_1m_open_30m_primary_60m_confirm_apex_aware"
FEATURE_PLACEMENT_STATUS = "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM"
LABEL_PLACEMENT_STATUS = "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM"

ENTRY_OFFSET_BARS = 1
PRIMARY_EXIT_OFFSET_BARS = 31
ROBUSTNESS_EXIT_OFFSET_BARS = 61

DEFAULT_LABEL_ROOT = Path("data/labeled")
DEFAULT_FEATURE_ROOT = Path("data/feature_matrices")
DEFAULT_FEATURE_MANIFEST = Path(
    "reports/features_baseline/"
    "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "baseline_feature_manifest.json"
)
DEFAULT_FEATURE_PLACEMENT_HASHES = Path(
    "reports/features_baseline/"
    "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "post_active_feature_hashes.json"
)
DEFAULT_LABEL_PLACEMENT_HASHES = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_active_replacement_decision/"
    "post_replacement_hashes.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/model_trust_audit/target_timing_v2_tier1_core_20260709")

REQUIRED_LABEL_COLUMNS = (
    "ts",
    "market",
    "year",
    "session_segment_id",
    "label_semantics",
    "target_30m_valid",
    "target_60m_valid",
    "target_entry_ts_30m",
    "target_exit_ts_30m",
    "target_entry_ts_60m",
    "target_exit_ts_60m",
)
REQUIRED_FEATURE_COLUMNS = ("ts", "market", "year", "session_segment_id")
LEAKAGE_FEATURE_PREFIXES = (
    "target_",
    "diagnostic_",
    "future_",
    "path_",
    "cost_",
    "execution_",
    "entry_",
    "exit_",
    "label_",
    "feature_target_",
    "feature_diagnostic_",
    "feature_future_",
    "feature_path_",
    "feature_cost_",
    "feature_execution_",
    "feature_entry_",
    "feature_exit_",
    "feature_label_",
)
FORBIDDEN_NOW = (
    "provider_or_download",
    "label_or_feature_rebuild",
    "wfa_or_modeling",
    "prediction_generation",
    "phase8_refresh",
    "promotion_or_artifact_freeze",
    "final_holdout",
    "paper_or_live",
    "cleanup",
    "git_staging_commit_push",
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


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"missing JSON input: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON input {path.as_posix()}: {exc}"
    if not isinstance(payload, dict):
        return None, f"JSON input is not an object: {path.as_posix()}"
    return payload, None


def read_json_list(path: Path) -> tuple[list[Any] | None, str | None]:
    if not path.is_file():
        return None, f"missing JSON input: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON input {path.as_posix()}: {exc}"
    if not isinstance(payload, list):
        return None, f"JSON input is not a list: {path.as_posix()}"
    return payload, None


def parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def expected_pairs(markets: Sequence[str], years: Sequence[int]) -> list[tuple[str, int]]:
    return [(market, year) for market in markets for year in years]


def scope_failures(markets: Sequence[str], years: Sequence[int]) -> list[str]:
    failures: list[str] = []
    if sorted(markets) != sorted(EXPECTED_MARKETS):
        failures.append(f"scope markets must be exactly {list(EXPECTED_MARKETS)}, got {list(markets)}")
    if sorted(years) != sorted(EXPECTED_YEARS):
        failures.append(f"scope years must be exactly {list(EXPECTED_YEARS)}, got {list(years)}")
    if len(expected_pairs(markets, years)) != EXPECTED_FILE_COUNT:
        failures.append(f"scope file count must be {EXPECTED_FILE_COUNT}")
    return failures


def validate_payload_scope(
    payload: Mapping[str, Any] | None,
    *,
    label: str,
    file_count_key: str,
) -> list[str]:
    if payload is None:
        return [f"{label} payload missing"]
    scope = payload.get("scope")
    if not isinstance(scope, Mapping):
        return [f"{label} scope missing"]
    failures: list[str] = []
    markets = sorted(str(item) for item in scope.get("markets", []))
    years = sorted(int(item) for item in scope.get("years", []))
    if markets != sorted(EXPECTED_MARKETS):
        failures.append(f"{label} scope markets mismatch: {markets}")
    if years != list(EXPECTED_YEARS):
        failures.append(f"{label} scope years mismatch: {years}")
    if int(scope.get(file_count_key) or 0) != EXPECTED_FILE_COUNT:
        failures.append(f"{label} scope {file_count_key} is not {EXPECTED_FILE_COUNT}")
    return failures


def hash_if_present(path: Path) -> str | None:
    return file_sha256(path) if path.is_file() else None


def label_record_map(payload: Mapping[str, Any] | None) -> dict[tuple[str, int], Mapping[str, Any]]:
    records = payload.get("records", []) if isinstance(payload, Mapping) else []
    by_pair: dict[tuple[str, int], Mapping[str, Any]] = {}
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, Mapping):
                continue
            try:
                key = (str(record["market"]), int(record["year"]))
            except (KeyError, TypeError, ValueError):
                continue
            by_pair[key] = record
    return by_pair


def feature_record_map(payload: Mapping[str, Any] | None) -> dict[tuple[str, int], Mapping[str, Any]]:
    records = payload.get("records", []) if isinstance(payload, Mapping) else []
    by_pair: dict[tuple[str, int], Mapping[str, Any]] = {}
    if not isinstance(records, list):
        return by_pair
    for record in records:
        if not isinstance(record, Mapping):
            continue
        raw_path = record.get("path")
        if not isinstance(raw_path, str) or not raw_path.endswith(".parquet"):
            continue
        parts = Path(raw_path).parts
        if len(parts) < 2:
            continue
        try:
            key = (parts[-2], int(Path(parts[-1]).stem))
        except ValueError:
            continue
        by_pair[key] = record
    return by_pair


def expected_hash_from_mapping(mapping: object, path: Path, repo_root: Path) -> str | None:
    if not isinstance(mapping, Mapping):
        return None
    rel_path = rel(path, repo_root)
    raw = mapping.get(rel_path)
    return str(raw) if raw is not None else None


def validate_hash(
    *,
    path: Path,
    expected_hashes: Iterable[str | None],
    repo_root: Path,
    input_hashes: dict[str, str],
    failures: list[str],
    label: str,
) -> str | None:
    rel_path = rel(path, repo_root)
    if not path.is_file():
        failures.append(f"{label} missing: {rel_path}")
        return None
    actual = file_sha256(path)
    input_hashes[rel_path] = actual
    for expected in expected_hashes:
        if expected is not None and expected != actual:
            failures.append(f"{label} hash mismatch for {rel_path}")
    return actual


def normalize_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def bool_col(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].fillna(False).astype(bool)


def compare_keys(label_df: pd.DataFrame, feature_df: pd.DataFrame) -> int:
    if len(label_df) != len(feature_df):
        return max(len(label_df), len(feature_df))
    mismatched = np.zeros(len(label_df), dtype=bool)
    left_ts = normalize_ts(label_df["ts"]).reset_index(drop=True)
    right_ts = normalize_ts(feature_df["ts"]).reset_index(drop=True)
    mismatched |= ~(left_ts.eq(right_ts) | (left_ts.isna() & right_ts.isna())).to_numpy(
        dtype=bool
    )
    for column in ("market", "session_segment_id"):
        left = (
            label_df[column]
            .astype("string")
            .reset_index(drop=True)
            .fillna("<missing>")
            .to_numpy(dtype=object)
        )
        right = (
            feature_df[column]
            .astype("string")
            .reset_index(drop=True)
            .fillna("<missing>")
            .to_numpy(dtype=object)
        )
        mismatched |= left != right
    left_year = pd.to_numeric(label_df["year"], errors="coerce").reset_index(drop=True)
    right_year = pd.to_numeric(feature_df["year"], errors="coerce").reset_index(drop=True)
    mismatched |= ~(left_year.eq(right_year) | (left_year.isna() & right_year.isna())).to_numpy(
        dtype=bool
    )
    return int(mismatched.sum())


def consecutive_run_end_positions(segment: pd.Series) -> np.ndarray:
    segment_text = segment.astype("string").fillna("<missing>")
    run_start = segment_text.ne(segment_text.shift()).fillna(True)
    run_id = run_start.astype(bool).cumsum()
    positions = pd.Series(np.arange(len(segment_text)), index=segment_text.index)
    return positions.groupby(run_id, sort=False).transform("max").to_numpy(dtype=int)


def mismatch_count(mask: pd.Series, left: pd.Series, right: pd.Series) -> int:
    selected = mask.fillna(False).astype(bool)
    return int((selected & left.ne(right)).fillna(False).sum())


def audit_pair(
    *,
    market: str,
    year: int,
    label_path: Path,
    feature_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    pair_name = f"{market}:{year}"
    failures: list[str] = []
    try:
        label_df = pd.read_parquet(label_path, columns=list(REQUIRED_LABEL_COLUMNS))
    except Exception as exc:
        return (
            {
                "market": market,
                "year": year,
                "label_path": label_path.as_posix(),
                "feature_path": feature_path.as_posix(),
                "status": "FAIL",
                "failures": [f"label parquet unreadable: {exc}"],
            },
            [f"{pair_name} label parquet unreadable: {exc}"],
        )
    try:
        feature_df = pd.read_parquet(feature_path, columns=list(REQUIRED_FEATURE_COLUMNS))
    except Exception as exc:
        return (
            {
                "market": market,
                "year": year,
                "label_path": label_path.as_posix(),
                "feature_path": feature_path.as_posix(),
                "status": "FAIL",
                "failures": [f"feature parquet unreadable: {exc}"],
            },
            [f"{pair_name} feature parquet unreadable: {exc}"],
        )

    label_df = label_df.sort_values("ts", kind="mergesort").reset_index(drop=True)
    feature_df = feature_df.sort_values("ts", kind="mergesort").reset_index(drop=True)
    ts = normalize_ts(label_df["ts"])
    entry_30m = normalize_ts(label_df["target_entry_ts_30m"])
    exit_30m = normalize_ts(label_df["target_exit_ts_30m"])
    entry_60m = normalize_ts(label_df["target_entry_ts_60m"])
    exit_60m = normalize_ts(label_df["target_exit_ts_60m"])
    valid_30m = bool_col(label_df, "target_30m_valid")
    valid_60m = bool_col(label_df, "target_60m_valid")
    both_valid = valid_30m & valid_60m

    row_key_mismatches = compare_keys(label_df, feature_df)
    if row_key_mismatches:
        failures.append(f"{pair_name} label/feature row key mismatches: {row_key_mismatches}")

    label_semantics_mismatches = int(
        label_df["label_semantics"].astype("string").ne(LABEL_SEMANTICS_ID).fillna(True).sum()
    )
    if label_semantics_mismatches:
        failures.append(f"{pair_name} label_semantics mismatches: {label_semantics_mismatches}")

    expected_entry = ts.shift(-ENTRY_OFFSET_BARS)
    expected_exit_30m = ts.shift(-PRIMARY_EXIT_OFFSET_BARS)
    expected_exit_60m = ts.shift(-ROBUSTNESS_EXIT_OFFSET_BARS)

    entry_30m_not_after_ts = int((valid_30m & entry_30m.le(ts)).fillna(False).sum())
    entry_60m_not_after_ts = int((valid_60m & entry_60m.le(ts)).fillna(False).sum())
    exit_30m_not_after_entry = int((valid_30m & exit_30m.le(entry_30m)).fillna(False).sum())
    exit_60m_not_after_entry = int((valid_60m & exit_60m.le(entry_60m)).fillna(False).sum())
    entry_30m_offset_mismatches = mismatch_count(valid_30m, entry_30m, expected_entry)
    entry_60m_offset_mismatches = mismatch_count(valid_60m, entry_60m, expected_entry)
    exit_30m_offset_mismatches = mismatch_count(valid_30m, exit_30m, expected_exit_30m)
    exit_60m_offset_mismatches = mismatch_count(valid_60m, exit_60m, expected_exit_60m)
    entry_30m_60m_mismatches = mismatch_count(both_valid, entry_30m, entry_60m)

    run_end = consecutive_run_end_positions(label_df["session_segment_id"])
    positions = np.arange(len(label_df))
    same_session_30m = pd.Series(positions + PRIMARY_EXIT_OFFSET_BARS <= run_end, index=label_df.index)
    same_session_60m = pd.Series(positions + ROBUSTNESS_EXIT_OFFSET_BARS <= run_end, index=label_df.index)
    same_session_30m_violations = int((valid_30m & ~same_session_30m).sum())
    same_session_60m_violations = int((valid_60m & ~same_session_60m).sum())

    metric_failures = {
        "entry_30m_not_after_ts": entry_30m_not_after_ts,
        "entry_60m_not_after_ts": entry_60m_not_after_ts,
        "exit_30m_not_after_entry": exit_30m_not_after_entry,
        "exit_60m_not_after_entry": exit_60m_not_after_entry,
        "entry_30m_offset_mismatches": entry_30m_offset_mismatches,
        "entry_60m_offset_mismatches": entry_60m_offset_mismatches,
        "exit_30m_offset_mismatches": exit_30m_offset_mismatches,
        "exit_60m_offset_mismatches": exit_60m_offset_mismatches,
        "entry_30m_60m_mismatches": entry_30m_60m_mismatches,
        "same_session_30m_violations": same_session_30m_violations,
        "same_session_60m_violations": same_session_60m_violations,
    }
    for name, count in metric_failures.items():
        if count:
            failures.append(f"{pair_name} {name}: {count}")

    record = {
        "market": market,
        "year": year,
        "label_path": label_path.as_posix(),
        "feature_path": feature_path.as_posix(),
        "row_count": int(len(label_df)),
        "feature_row_count": int(len(feature_df)),
        "valid_30m_rows": int(valid_30m.sum()),
        "valid_60m_rows": int(valid_60m.sum()),
        "label_semantics_mismatches": label_semantics_mismatches,
        "row_key_mismatches": row_key_mismatches,
        **metric_failures,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    return record, failures


def feature_name_failures(
    *,
    feature_root: Path,
    feature_manifest: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    feature_cols_path = feature_root / "feature_cols.json"
    feature_cols_payload, feature_cols_error = read_json_list(feature_cols_path)
    if feature_cols_error:
        return {"status": "FAIL", "failures": [feature_cols_error]}, [feature_cols_error]
    feature_cols = [str(item) for item in feature_cols_payload or []]
    manifest_feature_cols = feature_manifest.get("feature_cols", []) if isinstance(feature_manifest, Mapping) else []
    if not isinstance(manifest_feature_cols, list):
        failures.append("feature manifest feature_cols is not a list")
        manifest_feature_cols = []
    manifest_feature_cols = [str(item) for item in manifest_feature_cols]
    if manifest_feature_cols and manifest_feature_cols != feature_cols:
        failures.append("feature manifest feature_cols does not match feature_cols.json")

    checked = sorted(set(feature_cols) | set(manifest_feature_cols))
    forbidden = [
        column
        for column in checked
        if any(column.startswith(prefix) for prefix in LEAKAGE_FEATURE_PREFIXES)
    ]
    if forbidden:
        failures.append(f"forbidden feature names: {forbidden}")
    gate_failures = feature_manifest.get("forbidden_feature_leakage_failures", []) if isinstance(feature_manifest, Mapping) else []
    if gate_failures:
        failures.append(f"feature manifest forbidden_feature_leakage_failures is non-empty: {gate_failures}")
    return (
        {
            "status": "PASS" if not failures else "FAIL",
            "feature_cols_path": feature_cols_path.as_posix(),
            "feature_count": len(feature_cols),
            "manifest_feature_count": len(manifest_feature_cols),
            "forbidden_feature_count": len(forbidden),
            "forbidden_features": forbidden,
            "failures": failures,
        },
        failures,
    )


def build_report(
    *,
    repo_root: Path,
    label_root: Path,
    feature_root: Path,
    feature_manifest_path: Path,
    feature_placement_hashes_path: Path,
    label_placement_hashes_path: Path,
    reports_root: Path,
    markets: Sequence[str],
    years: Sequence[int],
) -> dict[str, Any]:
    failures: list[str] = []
    warnings = [
        "WARN_COMPLETED_BAR_CONVENTION_ASSUMED: audit proves timing only if feature row ts "
        "means completed one-minute bar availability, not bar-open availability."
    ]
    input_hashes: dict[str, str] = {}
    for path in (feature_manifest_path, feature_placement_hashes_path, label_placement_hashes_path):
        digest = hash_if_present(path)
        if digest is not None:
            input_hashes[rel(path, repo_root)] = digest

    failures.extend(scope_failures(markets, years))
    feature_manifest, feature_manifest_error = read_json_object(feature_manifest_path)
    feature_placement, feature_placement_error = read_json_object(feature_placement_hashes_path)
    label_placement, label_placement_error = read_json_object(label_placement_hashes_path)
    failures.extend(
        error
        for error in (feature_manifest_error, feature_placement_error, label_placement_error)
        if error
    )

    if feature_manifest is not None:
        if feature_manifest.get("status") != "PASS":
            failures.append(f"feature manifest status is {feature_manifest.get('status')!r}")
        if int(feature_manifest.get("failure_count") or 0) != 0:
            failures.append("feature manifest failure_count is not 0")
        audit_gate = feature_manifest.get("feature_audit_gate", {})
        if not isinstance(audit_gate, Mapping) or audit_gate.get("status") != "PASS":
            failures.append("feature manifest feature_audit_gate is not PASS")
    if feature_placement is not None:
        if feature_placement.get("status") != FEATURE_PLACEMENT_STATUS:
            failures.append(f"feature placement status is {feature_placement.get('status')!r}")
        failures.extend(validate_payload_scope(feature_placement, label="feature placement", file_count_key="parquet_count"))
    if label_placement is not None:
        if label_placement.get("status") != LABEL_PLACEMENT_STATUS:
            failures.append(f"label placement status is {label_placement.get('status')!r}")
        if label_placement.get("label_semantics_id") != LABEL_SEMANTICS_ID:
            failures.append(f"label placement semantics is {label_placement.get('label_semantics_id')!r}")
        failures.extend(validate_payload_scope(label_placement, label="label placement", file_count_key="file_count"))

    feature_name_gate, feature_name_gate_failures = feature_name_failures(
        feature_root=feature_root,
        feature_manifest=feature_manifest,
    )
    failures.extend(feature_name_gate_failures)
    feature_cols_hash = hash_if_present(feature_root / "feature_cols.json")
    if feature_cols_hash is not None:
        input_hashes[rel(feature_root / "feature_cols.json", repo_root)] = feature_cols_hash
    target_cols_hash = hash_if_present(feature_root / "target_cols.json")
    if target_cols_hash is not None:
        input_hashes[rel(feature_root / "target_cols.json", repo_root)] = target_cols_hash

    label_records = label_record_map(label_placement)
    feature_records = feature_record_map(feature_placement)
    feature_tree_hashes = feature_placement.get("active_tree_hashes_after", {}) if isinstance(feature_placement, Mapping) else {}
    manifest_input_hashes = feature_manifest.get("input_file_hashes", {}) if isinstance(feature_manifest, Mapping) else {}
    manifest_output_hashes = feature_manifest.get("output_file_hashes", {}) if isinstance(feature_manifest, Mapping) else {}

    pair_records: list[dict[str, Any]] = []
    for market, year in expected_pairs(markets, years):
        pair = (market, year)
        label_path = label_root / market / f"{year}.parquet"
        feature_path = feature_root / market / f"{year}.parquet"
        label_record = label_records.get(pair)
        feature_record = feature_records.get(pair)
        if label_record is None:
            failures.append(f"label placement record missing for {market}:{year}")
        if feature_record is None:
            failures.append(f"feature placement record missing for {market}:{year}")
        validate_hash(
            path=label_path,
            expected_hashes=[
                str(label_record.get("active_sha256")) if label_record else None,
                str(label_record.get("staged_sha256")) if label_record else None,
                expected_hash_from_mapping(manifest_input_hashes, label_path, repo_root),
            ],
            repo_root=repo_root,
            input_hashes=input_hashes,
            failures=failures,
            label="label parquet",
        )
        validate_hash(
            path=feature_path,
            expected_hashes=[
                str(feature_record.get("sha256")) if feature_record else None,
                str(feature_record.get("staged_sha256")) if feature_record else None,
                expected_hash_from_mapping(feature_tree_hashes, feature_path, repo_root),
                expected_hash_from_mapping(manifest_output_hashes, feature_path, repo_root),
            ],
            repo_root=repo_root,
            input_hashes=input_hashes,
            failures=failures,
            label="feature parquet",
        )
        if label_path.is_file() and feature_path.is_file():
            pair_record, pair_failures = audit_pair(
                market=market,
                year=year,
                label_path=label_path,
                feature_path=feature_path,
            )
            pair_record["label_path"] = rel(label_path, repo_root)
            pair_record["feature_path"] = rel(feature_path, repo_root)
            pair_records.append(pair_record)
            failures.extend(pair_failures)

    aggregate = {
        "pair_count": len(pair_records),
        "row_count": int(sum(record.get("row_count", 0) for record in pair_records)),
        "valid_30m_rows": int(sum(record.get("valid_30m_rows", 0) for record in pair_records)),
        "valid_60m_rows": int(sum(record.get("valid_60m_rows", 0) for record in pair_records)),
        "row_key_mismatches": int(sum(record.get("row_key_mismatches", 0) for record in pair_records)),
        "entry_30m_not_after_ts": int(sum(record.get("entry_30m_not_after_ts", 0) for record in pair_records)),
        "entry_60m_not_after_ts": int(sum(record.get("entry_60m_not_after_ts", 0) for record in pair_records)),
        "exit_30m_offset_mismatches": int(sum(record.get("exit_30m_offset_mismatches", 0) for record in pair_records)),
        "exit_60m_offset_mismatches": int(sum(record.get("exit_60m_offset_mismatches", 0) for record in pair_records)),
        "same_session_30m_violations": int(sum(record.get("same_session_30m_violations", 0) for record in pair_records)),
        "same_session_60m_violations": int(sum(record.get("same_session_60m_violations", 0) for record in pair_records)),
    }
    status = PASS_STATUS if not failures else FAIL_STATUS
    return {
        "stage": STAGE,
        "status": status,
        "generated_at": utc_now(),
        "reports_root": rel(reports_root, repo_root),
        "scope": {
            "markets": list(markets),
            "years": list(years),
            "file_count": len(expected_pairs(markets, years)),
            "label_root": rel(label_root, repo_root),
            "feature_root": rel(feature_root, repo_root),
        },
        "summary": {
            "status": status,
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "commands_executed": 0,
            "data_model_or_prediction_mutation": False,
            "completed_bar_convention_assumed": True,
            **aggregate,
        },
        "feature_name_gate": feature_name_gate,
        "pair_records": pair_records,
        "input_file_hashes": dict(sorted(input_hashes.items())),
        "failures": failures,
        "warnings": warnings,
        "forbidden_actions": list(FORBIDDEN_NOW),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Target Timing Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Scope: `{report['scope']['markets']}` years `{report['scope']['years']}`",
        f"- Pairs: `{summary['pair_count']}`",
        f"- Rows: `{summary['row_count']}`",
        f"- Valid 30m rows: `{summary['valid_30m_rows']}`",
        f"- Valid 60m rows: `{summary['valid_60m_rows']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Warnings: `{summary['warning_count']}`",
        "",
        "## Timing Checks",
        "",
        f"- Row key mismatches: `{summary['row_key_mismatches']}`",
        f"- 30m entries not after feature timestamp: `{summary['entry_30m_not_after_ts']}`",
        f"- 60m entries not after feature timestamp: `{summary['entry_60m_not_after_ts']}`",
        f"- 30m exit offset mismatches: `{summary['exit_30m_offset_mismatches']}`",
        f"- 60m exit offset mismatches: `{summary['exit_60m_offset_mismatches']}`",
        f"- 30m same-session violations: `{summary['same_session_30m_violations']}`",
        f"- 60m same-session violations: `{summary['same_session_60m_violations']}`",
        "",
        "## Feature Leakage Names",
        "",
        f"- Feature name gate: `{report['feature_name_gate']['status']}`",
        f"- Forbidden feature count: `{report['feature_name_gate']['forbidden_feature_count']}`",
        "",
        "## Assumption",
        "",
        "- This audit proves causality only under the completed one-minute bar convention: "
        "feature row `ts` is treated as completed-bar availability, not bar-open availability.",
    ]
    failures = list(report.get("failures", []))
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    warnings = list(report.get("warnings", []))
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This report is read-only evidence. It did not rebuild labels/features, run WFA/modeling, "
            "write predictions, refresh Phase 8, call providers, stage, commit, push, paper trade, or live trade.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / "target_timing_audit.json"
    md_path = reports_root / "target_timing_audit.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--label-root", default=DEFAULT_LABEL_ROOT.as_posix())
    parser.add_argument("--feature-root", default=DEFAULT_FEATURE_ROOT.as_posix())
    parser.add_argument("--feature-manifest", default=DEFAULT_FEATURE_MANIFEST.as_posix())
    parser.add_argument("--feature-placement-hashes", default=DEFAULT_FEATURE_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--label-placement-hashes", default=DEFAULT_LABEL_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--markets", default=",".join(EXPECTED_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in EXPECTED_YEARS))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    report = build_report(
        repo_root=repo_root,
        label_root=resolve_path(repo_root, args.label_root),
        feature_root=resolve_path(repo_root, args.feature_root),
        feature_manifest_path=resolve_path(repo_root, args.feature_manifest),
        feature_placement_hashes_path=resolve_path(repo_root, args.feature_placement_hashes),
        label_placement_hashes_path=resolve_path(repo_root, args.label_placement_hashes),
        reports_root=resolve_path(repo_root, args.reports_root),
        markets=parse_csv_strings(args.markets),
        years=parse_csv_ints(args.years),
    )
    json_path, md_path = write_report(report, resolve_path(repo_root, args.reports_root))
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"warnings={report['summary']['warning_count']} json={rel(json_path, repo_root)} "
        f"md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
