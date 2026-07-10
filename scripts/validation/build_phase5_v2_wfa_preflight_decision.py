#!/usr/bin/env python3
"""Report-only Phase 5/WFA preflight decision for active v2 Tier 1 core data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from scripts.phase5_wfa import build_wfa_splits
from scripts.validation.data_audit_universe_guard import load_data_audit_universe


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "phase5_v2_wfa_preflight_decision"
PASS_STATUS = "PASS_PHASE5_V2_WFA_PREFLIGHT_READY_NO_SPLIT_BUILD"
FAIL_STATUS = "FAIL_PHASE5_V2_WFA_PREFLIGHT_BLOCKED_NO_SPLIT_BUILD"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_MARKET_YEAR_COUNT = len(EXPECTED_MARKETS) * len(EXPECTED_YEARS)
EXPECTED_FEATURE_COUNT = 114
EXPECTED_FEATURE_PARQUET_COLUMNS = 342
EXPECTED_LABEL_PARQUET_COLUMNS = 217
EXPECTED_RESOLVED_PURGE_BARS = 61
EXPECTED_TARGET_HORIZON_BARS = 30
EXPECTED_TREND_HORIZON_BARS = 60

DEFAULT_FEATURE_ROOT = Path("data/feature_matrices")
DEFAULT_LABEL_ROOT = Path("data/labeled")
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
DEFAULT_DATA_AUDIT_UNIVERSE = Path(
    "reports/data_audit/wfa_research/tier1_rebuild_v1/preflight/"
    "data_audit_universe_tier1_rebuild_v1.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/wfa_preflight/phase5_v2_apex_30m60m_20260709_tier1_core")
DEFAULT_FUTURE_WFA_REPORTS_ROOT = Path("reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core")
DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")
DEFAULT_MODELS_CONFIG = Path("configs/models.yaml")

REQUIRED_FEATURE_MATRIX_COLUMNS = (
    "ts",
    "market",
    "year",
    "training_row_valid",
    "target_valid",
    "feature_input_valid",
)
REQUIRED_V2_TARGET_COLUMNS = (
    "target_ret_30m",
    "target_ret_ticks_30m",
    "target_favorable_after_cost_30m",
    "target_net_ticks_after_est_cost_30m",
    "target_net_dollars_after_est_cost_30m",
    "target_mfe_long_ticks_30m",
    "target_mae_long_ticks_30m",
    "target_mfe_short_ticks_30m",
    "target_mae_short_ticks_30m",
    "target_ret_60m",
    "target_ret_ticks_60m",
    "target_favorable_after_cost_60m",
    "target_net_ticks_after_est_cost_60m",
    "target_net_dollars_after_est_cost_60m",
    "target_mfe_long_ticks_60m",
    "target_mae_long_ticks_60m",
    "target_mfe_short_ticks_60m",
    "target_mae_short_ticks_60m",
    "target_apex_dll_eod_threat_30m",
    "target_apex_dll_eod_threat_60m",
    "target_no_hold_into_close_30m",
    "target_no_hold_into_close_60m",
    "target_fillable_after_slippage_30m",
    "target_fillable_after_slippage_60m",
    "target_accept_any_30m",
    "target_accept_any_60m",
    "target_apex_confirmed_any_30m_60m",
)

FORBIDDEN_NOW = (
    "scripts.phase5_wfa.build_wfa_splits",
    "phase6_wfa_training",
    "phase8_refresh",
    "provider_or_download",
    "promotion_or_artifact_freeze",
    "final_holdout",
    "paper_or_live",
    "cleanup",
    "git_staging_commit_push",
    "rescue_tuning",
    "label_or_feature_rebuild",
    "prop_account_reports",
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"missing JSON file: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - fail closed with evidence.
        return None, f"unreadable JSON file {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"JSON file is not an object: {path.as_posix()}"
    return payload, None


def read_json_list(path: Path) -> tuple[list[Any] | None, str | None]:
    if not path.is_file():
        return None, f"missing JSON list file: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, f"unreadable JSON list file {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, list):
        return None, f"JSON file is not a list: {path.as_posix()}"
    return payload, None


def read_yaml_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"missing YAML file: {path.as_posix()}"
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return None, f"unreadable YAML file {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"YAML file is not a mapping: {path.as_posix()}"
    return payload, None


def parse_csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_csv_ints(value: str) -> list[int]:
    result: list[int] = []
    for item in parse_csv_strings(value):
        try:
            result.append(int(item))
        except ValueError as exc:
            raise SystemExit(f"invalid --years value: {value}") from exc
    return result


def expected_pairs(markets: Iterable[str], years: Iterable[int]) -> list[tuple[str, int]]:
    return [(str(market), int(year)) for market in markets for year in years]


def expected_feature_paths(feature_root: Path, pairs: Iterable[tuple[str, int]]) -> list[Path]:
    return [feature_root / market / f"{year}.parquet" for market, year in pairs]


def expected_label_paths(label_root: Path, pairs: Iterable[tuple[str, int]]) -> list[Path]:
    return [label_root / market / f"{year}.parquet" for market, year in pairs]


def sidecar_paths(feature_root: Path) -> list[Path]:
    return [
        feature_root / "feature_cols.json",
        feature_root / "target_cols.json",
        feature_root / "metadata_cols.json",
        feature_root / "excluded_cols.json",
    ]


def record_check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _path_record_map(records: object, *, path_key: str, alt_path_key: str | None = None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(records, list):
        return {}
    by_path: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        raw_path = record.get(path_key)
        if raw_path is None and alt_path_key is not None:
            raw_path = record.get(alt_path_key)
        if raw_path is not None:
            by_path[str(raw_path).replace("\\", "/")] = record
    return by_path


def _parquet_metadata(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"missing parquet: {path.as_posix()}"
    try:
        parquet_file = pq.ParquetFile(path)
    except Exception as exc:  # noqa: BLE001
        return None, f"unreadable parquet {path.as_posix()}: {type(exc).__name__}: {exc}"
    return {
        "rows": int(parquet_file.metadata.num_rows),
        "columns": list(parquet_file.schema_arrow.names),
    }, None


def _hash_record_evidence(
    *,
    repo_root: Path,
    records: Mapping[str, Mapping[str, Any]],
    expected_path: Path,
    sha_key: str,
    expected_rows: int | None = None,
    expected_columns: int | None = None,
) -> dict[str, Any]:
    rel_path = rel(expected_path, repo_root)
    record = records.get(rel_path)
    exists = expected_path.is_file()
    actual_sha = file_sha256(expected_path) if exists else None
    expected_sha = str(record.get(sha_key) or "") if record is not None else ""
    metadata, metadata_error = _parquet_metadata(expected_path) if expected_path.suffix == ".parquet" else (None, None)
    row_count = metadata.get("rows") if metadata is not None else None
    column_count = len(metadata.get("columns") or []) if metadata is not None else None
    failures: list[str] = []
    if record is None:
        failures.append("missing hash record")
    if not exists:
        failures.append("active file missing")
    if metadata_error is not None:
        failures.append(metadata_error)
    if expected_sha and actual_sha != expected_sha:
        failures.append("sha256 mismatch")
    if record is not None and record.get("active_matches_staged") is not True:
        failures.append("active_matches_staged is not true")
    if record is not None and record.get("backup_matches_pre_active") is not True:
        failures.append("backup_matches_pre_active is not true")
    if expected_rows is not None and row_count != expected_rows:
        failures.append(f"row count {row_count} != {expected_rows}")
    if expected_columns is not None and column_count != expected_columns:
        failures.append(f"column count {column_count} != {expected_columns}")
    return {
        "path": rel_path,
        "exists": exists,
        "record_present": record is not None,
        "expected_sha256": expected_sha,
        "actual_sha256": actual_sha,
        "hash_match": bool(expected_sha and actual_sha == expected_sha),
        "record_rows": record.get("rows") if record is not None else None,
        "actual_rows": row_count,
        "record_columns": record.get("columns") if record is not None else None,
        "actual_columns": column_count,
        "active_matches_staged": record.get("active_matches_staged") if record is not None else None,
        "backup_matches_pre_active": record.get("backup_matches_pre_active") if record is not None else None,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }


def validate_scope(markets: list[str], years: list[int]) -> dict[str, Any]:
    expected_market_set = set(EXPECTED_MARKETS)
    expected_year_set = set(EXPECTED_YEARS)
    failures: list[str] = []
    if set(markets) != expected_market_set:
        failures.append(f"markets must be exactly {sorted(expected_market_set)}")
    if set(years) != expected_year_set:
        failures.append(f"years must be exactly {sorted(expected_year_set)}")
    if len(expected_pairs(markets, years)) != EXPECTED_MARKET_YEAR_COUNT:
        failures.append("market-year scope does not contain exactly 8 pairs")
    return {
        "status": "PASS" if not failures else "FAIL",
        "markets": markets,
        "years": years,
        "expected_markets": list(EXPECTED_MARKETS),
        "expected_years": list(EXPECTED_YEARS),
        "expected_market_year_count": EXPECTED_MARKET_YEAR_COUNT,
        "failures": failures,
    }


def validate_feature_manifest(
    *,
    repo_root: Path,
    feature_manifest: Mapping[str, Any] | None,
    feature_root: Path,
    label_root: Path,
    pairs: list[tuple[str, int]],
) -> dict[str, Any]:
    failures: list[str] = []
    outputs = feature_manifest.get("outputs") if isinstance(feature_manifest, Mapping) else None
    if not isinstance(feature_manifest, Mapping):
        failures.append("feature manifest missing or unreadable")
        outputs = []
    if not isinstance(outputs, list):
        failures.append("feature manifest outputs is not a list")
        outputs = []

    feature_audit_gate = feature_manifest.get("feature_audit_gate") if isinstance(feature_manifest, Mapping) else {}
    if not isinstance(feature_audit_gate, Mapping):
        feature_audit_gate = {}
    output_file_hashes = feature_manifest.get("output_file_hashes") if isinstance(feature_manifest, Mapping) else {}
    if not isinstance(output_file_hashes, Mapping):
        output_file_hashes = {}

    by_pair: dict[tuple[str, int], Mapping[str, Any]] = {}
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        try:
            by_pair[(str(output["market"]), int(output["year"]))] = output
        except (KeyError, TypeError, ValueError):
            failures.append(f"invalid feature manifest output row: {output!r}")

    expected_pair_set = set(pairs)
    if set(by_pair) != expected_pair_set:
        failures.append(f"feature manifest output scope mismatch: {sorted(by_pair)}")
    if feature_manifest is not None:
        if feature_manifest.get("status") != "PASS":
            failures.append(f"feature manifest status is {feature_manifest.get('status')!r}")
        if feature_manifest.get("profile") != "tier_1":
            failures.append(f"feature manifest profile is {feature_manifest.get('profile')!r}")
        if feature_manifest.get("resolved_profile") != "tier_1_research":
            failures.append(
                f"feature manifest resolved_profile is {feature_manifest.get('resolved_profile')!r}"
            )
        if rel(resolve_path(repo_root, str(feature_manifest.get("output_root"))), repo_root) != rel(feature_root, repo_root):
            failures.append(f"feature manifest output_root mismatch: {feature_manifest.get('output_root')!r}")
        if int(feature_manifest.get("feature_count") or 0) != EXPECTED_FEATURE_COUNT:
            failures.append(f"feature manifest feature_count is {feature_manifest.get('feature_count')!r}")
        if int(feature_manifest.get("failure_count") or 0) != 0:
            failures.append("feature manifest failure_count is not 0")
        if feature_manifest.get("failures"):
            failures.append("feature manifest failures is non-empty")
        if feature_audit_gate.get("status") != "PASS":
            failures.append(f"feature audit gate status is {feature_audit_gate.get('status')!r}")
        if int(feature_audit_gate.get("failure_count") or 0) != 0:
            failures.append("feature audit gate failure_count is not 0")
        if feature_manifest.get("forbidden_feature_leakage_failures"):
            failures.append("feature manifest has forbidden feature leakage failures")

    output_evidence: list[dict[str, Any]] = []
    for market, year in pairs:
        output = by_pair.get((market, year), {})
        feature_path = feature_root / market / f"{year}.parquet"
        label_path = label_root / market / f"{year}.parquet"
        feature_meta, feature_error = _parquet_metadata(feature_path)
        label_meta, label_error = _parquet_metadata(label_path)
        feature_rows = feature_meta.get("rows") if feature_meta is not None else None
        label_rows = label_meta.get("rows") if label_meta is not None else None
        row_failures: list[str] = []
        if feature_error:
            row_failures.append(feature_error)
        if label_error:
            row_failures.append(label_error)
        if output.get("output_path") != rel(feature_path, repo_root):
            row_failures.append(f"output_path mismatch: {output.get('output_path')!r}")
        if output.get("input_path") != rel(label_path, repo_root):
            row_failures.append(f"input_path mismatch: {output.get('input_path')!r}")
        if int(output.get("output_rows") or -1) != feature_rows:
            row_failures.append("output_rows mismatch")
        if int(output.get("input_rows") or -1) != label_rows:
            row_failures.append("input_rows mismatch")
        if feature_rows != label_rows:
            row_failures.append(f"feature rows {feature_rows} != label rows {label_rows}")
        expected_hash = output_file_hashes.get(rel(feature_path, repo_root))
        actual_hash = file_sha256(feature_path) if feature_path.is_file() else None
        if expected_hash and actual_hash != expected_hash:
            row_failures.append("feature manifest output hash mismatch")
        output_evidence.append(
            {
                "market": market,
                "year": year,
                "feature_path": rel(feature_path, repo_root),
                "label_path": rel(label_path, repo_root),
                "feature_rows": feature_rows,
                "label_rows": label_rows,
                "feature_manifest_hash_match": bool(expected_hash and actual_hash == expected_hash),
                "failures": row_failures,
                "status": "PASS" if not row_failures else "FAIL",
            }
        )
        failures.extend(f"{market}:{year}: {failure}" for failure in row_failures)

    return {
        "status": "PASS" if not failures else "FAIL",
        "manifest_status": feature_manifest.get("status") if isinstance(feature_manifest, Mapping) else None,
        "profile": feature_manifest.get("profile") if isinstance(feature_manifest, Mapping) else None,
        "resolved_profile": feature_manifest.get("resolved_profile") if isinstance(feature_manifest, Mapping) else None,
        "output_root": feature_manifest.get("output_root") if isinstance(feature_manifest, Mapping) else None,
        "output_count": len(outputs),
        "feature_count": feature_manifest.get("feature_count") if isinstance(feature_manifest, Mapping) else None,
        "feature_audit_gate": dict(feature_audit_gate),
        "outputs": output_evidence,
        "failures": failures,
    }


def validate_sidecars_and_schemas(
    *,
    repo_root: Path,
    feature_root: Path,
    label_root: Path,
    pairs: list[tuple[str, int]],
) -> dict[str, Any]:
    failures: list[str] = []
    feature_cols, feature_cols_error = read_json_list(feature_root / "feature_cols.json")
    target_cols, target_cols_error = read_json_list(feature_root / "target_cols.json")
    metadata_cols, metadata_cols_error = read_json_list(feature_root / "metadata_cols.json")
    excluded_cols, excluded_cols_error = read_json_list(feature_root / "excluded_cols.json")
    for error in (feature_cols_error, target_cols_error, metadata_cols_error, excluded_cols_error):
        if error is not None:
            failures.append(error)

    feature_col_names = [str(item) for item in (feature_cols or [])]
    target_col_names = [str(item) for item in (target_cols or [])]
    metadata_col_names = [str(item) for item in (metadata_cols or [])]
    if len(feature_col_names) != EXPECTED_FEATURE_COUNT:
        failures.append(f"feature_cols count {len(feature_col_names)} != {EXPECTED_FEATURE_COUNT}")
    if any(column.startswith("target_") or column.startswith("diagnostic_") for column in feature_col_names):
        failures.append("feature_cols contains target/diagnostic columns")
    missing_metadata = sorted(set(REQUIRED_FEATURE_MATRIX_COLUMNS) - set(metadata_col_names))
    if missing_metadata:
        failures.append("metadata_cols missing required columns: " + ",".join(missing_metadata))
    missing_target_sidecars = sorted(set(REQUIRED_V2_TARGET_COLUMNS) - set(target_col_names))
    if missing_target_sidecars:
        failures.append("target_cols missing required v2 targets: " + ",".join(missing_target_sidecars))

    file_evidence: list[dict[str, Any]] = []
    for market, year in pairs:
        feature_path = feature_root / market / f"{year}.parquet"
        label_path = label_root / market / f"{year}.parquet"
        feature_meta, feature_error = _parquet_metadata(feature_path)
        label_meta, label_error = _parquet_metadata(label_path)
        feature_schema = set(feature_meta.get("columns") or []) if feature_meta else set()
        label_schema = set(label_meta.get("columns") or []) if label_meta else set()
        row_failures: list[str] = []
        if feature_error:
            row_failures.append(feature_error)
        if label_error:
            row_failures.append(label_error)
        missing_feature_matrix_columns = sorted(set(REQUIRED_FEATURE_MATRIX_COLUMNS) - feature_schema)
        if missing_feature_matrix_columns:
            row_failures.append(
                "feature schema missing WFA columns: " + ",".join(missing_feature_matrix_columns)
            )
        missing_feature_targets = sorted(set(REQUIRED_V2_TARGET_COLUMNS) - feature_schema)
        if missing_feature_targets:
            row_failures.append("feature schema missing v2 targets: " + ",".join(missing_feature_targets))
        missing_label_targets = sorted(set(REQUIRED_V2_TARGET_COLUMNS) - label_schema)
        if missing_label_targets:
            row_failures.append("label schema missing v2 targets: " + ",".join(missing_label_targets))
        file_evidence.append(
            {
                "market": market,
                "year": year,
                "feature_path": rel(feature_path, repo_root),
                "label_path": rel(label_path, repo_root),
                "feature_columns": len(feature_schema),
                "label_columns": len(label_schema),
                "required_target_columns_present": not missing_feature_targets and not missing_label_targets,
                "failures": row_failures,
                "status": "PASS" if not row_failures else "FAIL",
            }
        )
        failures.extend(f"{market}:{year}: {failure}" for failure in row_failures)

    return {
        "status": "PASS" if not failures else "FAIL",
        "feature_cols_count": len(feature_col_names),
        "target_cols_count": len(target_col_names),
        "metadata_cols_count": len(metadata_col_names),
        "excluded_cols_count": len(excluded_cols or []),
        "required_v2_target_columns": list(REQUIRED_V2_TARGET_COLUMNS),
        "files": file_evidence,
        "failures": failures,
    }


def validate_hash_reports(
    *,
    repo_root: Path,
    feature_root: Path,
    label_root: Path,
    feature_hash_report: Mapping[str, Any] | None,
    label_hash_report: Mapping[str, Any] | None,
    pairs: list[tuple[str, int]],
) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(feature_hash_report, Mapping):
        feature_hash_report = {}
        failures.append("feature placement hash report missing or unreadable")
    if not isinstance(label_hash_report, Mapping):
        label_hash_report = {}
        failures.append("label placement hash report missing or unreadable")
    if feature_hash_report.get("status") != "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM":
        failures.append(f"feature placement status is {feature_hash_report.get('status')!r}")
    if label_hash_report.get("status") != "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM":
        failures.append(f"label replacement status is {label_hash_report.get('status')!r}")

    expected_feature_files = expected_feature_paths(feature_root, pairs)
    expected_sidecars = sidecar_paths(feature_root)
    expected_label_files = expected_label_paths(label_root, pairs)
    feature_records = _path_record_map(feature_hash_report.get("records"), path_key="path")
    label_records = _path_record_map(label_hash_report.get("records"), path_key="active_path")

    expected_feature_record_paths = {rel(path, repo_root) for path in expected_feature_files + expected_sidecars}
    expected_label_record_paths = {rel(path, repo_root) for path in expected_label_files}
    feature_extra = sorted(set(feature_records) - expected_feature_record_paths)
    label_extra = sorted(set(label_records) - expected_label_record_paths)
    if feature_extra:
        failures.append("feature placement hash report has extra paths: " + ",".join(feature_extra))
    if label_extra:
        failures.append("label replacement hash report has extra paths: " + ",".join(label_extra))

    feature_evidence: list[dict[str, Any]] = []
    for path in expected_feature_files:
        row = _hash_record_evidence(
            repo_root=repo_root,
            records=feature_records,
            expected_path=path,
            sha_key="sha256",
            expected_columns=EXPECTED_FEATURE_PARQUET_COLUMNS,
        )
        feature_evidence.append(row)
        failures.extend(f"{row['path']}: {failure}" for failure in row["failures"])
    for path in expected_sidecars:
        row = _hash_record_evidence(
            repo_root=repo_root,
            records=feature_records,
            expected_path=path,
            sha_key="sha256",
        )
        feature_evidence.append(row)
        failures.extend(f"{row['path']}: {failure}" for failure in row["failures"])

    label_evidence: list[dict[str, Any]] = []
    for path in expected_label_files:
        row = _hash_record_evidence(
            repo_root=repo_root,
            records=label_records,
            expected_path=path,
            sha_key="active_sha256",
            expected_columns=EXPECTED_LABEL_PARQUET_COLUMNS,
        )
        label_evidence.append(row)
        failures.extend(f"{row['path']}: {failure}" for failure in row["failures"])

    return {
        "status": "PASS" if not failures else "FAIL",
        "feature_record_count": len(feature_records),
        "label_record_count": len(label_records),
        "feature_files": feature_evidence,
        "label_files": label_evidence,
        "failures": failures,
    }


def validate_configs(
    *,
    profile_config_path: Path,
    models_config_path: Path,
    markets: list[str],
    years: list[int],
) -> dict[str, Any]:
    failures: list[str] = []
    profile_evidence: dict[str, Any] = {"status": "FAIL"}
    policy_evidence: dict[str, Any] = {"status": "FAIL"}
    models_config, models_config_error = read_yaml_object(models_config_path)
    if models_config_error is not None:
        failures.append(models_config_error)
        models_config = {}

    try:
        profile_plan = build_wfa_splits.load_profile_plan("tier_1", profile_config_path)
        profile_plan = build_wfa_splits.filter_profile_plan(
            profile_plan,
            markets=markets,
            years=years,
        )
        profile_evidence = {
            "status": "PASS",
            "profile": profile_plan.requested_profile,
            "resolved_profile": profile_plan.resolved_profile,
            "markets": profile_plan.markets,
            "years": profile_plan.years,
            "settings_profile": profile_plan.settings_profile,
            "train_days": profile_plan.train_days,
            "test_days": profile_plan.test_days,
            "step_days": profile_plan.step_days,
            "final_holdout_years": profile_plan.final_holdout_years,
            "forbid_research_use": profile_plan.forbid_research_use,
        }
        if profile_plan.resolved_profile != "tier_1_research":
            failures.append(f"tier_1 resolves to {profile_plan.resolved_profile!r}")
        if set(profile_plan.markets) != set(EXPECTED_MARKETS):
            failures.append("tier_1 filtered markets do not match exact expected scope")
        if set(profile_plan.years) != set(EXPECTED_YEARS):
            failures.append("tier_1 filtered years do not match exact expected scope")
        if profile_plan.forbid_research_use:
            failures.append("tier_1 research profile unexpectedly forbids research use")
    except SystemExit as exc:
        failures.append(f"profile config failed: {exc}")
        profile_evidence = {"status": "FAIL", "failures": [str(exc)]}

    try:
        policy = build_wfa_splits.load_wfa_policy(models_config_path)
        policy_evidence = {
            "status": "PASS",
            "purge_bars": policy.purge_bars,
            "resolved_purge_bars": policy.resolved_purge_bars,
            "embargo_bars": policy.embargo_bars,
            "final_holdout_tuning_allowed": policy.final_holdout_tuning_allowed,
            "final_holdout_excluded_from_selection": policy.final_holdout_excluded_from_selection,
        }
        if policy.resolved_purge_bars != EXPECTED_RESOLVED_PURGE_BARS:
            failures.append(f"resolved purge bars {policy.resolved_purge_bars} != 61")
    except SystemExit as exc:
        failures.append(f"models config WFA policy failed: {exc}")
        policy_evidence = {"status": "FAIL", "failures": [str(exc)]}

    purge = models_config.get("purge") if isinstance(models_config, Mapping) else {}
    if not isinstance(purge, Mapping):
        purge = {}
    target_horizon = int(purge.get("target_horizon_bars") or 0)
    trend_horizon = int(purge.get("trend_horizon_bars") or 0)
    if target_horizon != EXPECTED_TARGET_HORIZON_BARS:
        failures.append(f"target_horizon_bars {target_horizon} != 30")
    if trend_horizon != EXPECTED_TREND_HORIZON_BARS:
        failures.append(f"trend_horizon_bars {trend_horizon} != 60")

    return {
        "status": "PASS" if not failures else "FAIL",
        "profile": profile_evidence,
        "wfa_policy": policy_evidence,
        "target_horizon_bars": target_horizon,
        "trend_horizon_bars": trend_horizon,
        "failures": failures,
    }


def validate_data_audit_universe(path: Path, pairs: list[tuple[str, int]]) -> dict[str, Any]:
    failures: list[str] = []
    try:
        universe = load_data_audit_universe(path)
    except SystemExit as exc:
        return {"status": "FAIL", "failures": [str(exc)], "path": path.as_posix()}
    expected_pair_set = set(pairs)
    actual_pair_set = set(universe.market_years)
    extra = sorted(actual_pair_set - expected_pair_set)
    missing = sorted(expected_pair_set - actual_pair_set)
    if extra:
        failures.append(f"data-audit universe has extra market-years: {extra}")
    if missing:
        failures.append(f"data-audit universe missing market-years: {missing}")
    row_evidence: list[dict[str, Any]] = []
    for market, year in pairs:
        row = universe.market_years.get((market, year), {})
        failure = universe.require_usable(market, year, context="Phase 5 v2 WFA preflight")
        if failure is not None:
            failures.append(failure)
        row_evidence.append(
            {
                "market": market,
                "year": year,
                "audit_status": row.get("audit_status"),
                "final_decision": row.get("final_decision"),
                "usable_for_wfa": row.get("usable_for_wfa"),
                "status": "PASS" if failure is None else "FAIL",
                "failure": failure,
            }
        )
    return {
        "status": "PASS" if not failures else "FAIL",
        "path": path.as_posix(),
        "file_hash": universe.file_hash,
        "status_counts": universe.status_counts,
        "market_year_count": len(universe.market_years),
        "rows": row_evidence,
        "failures": failures,
    }


def future_phase5_command(
    *,
    feature_root: Path,
    future_wfa_reports_root: Path,
    profile_config: Path,
    models_config: Path,
    feature_manifest: Path,
    data_audit_universe_json: Path,
    markets: list[str],
    years: list[int],
    repo_root: Path,
) -> str:
    return (
        "python -m scripts.phase5_wfa.build_wfa_splits "
        "--profile tier_1 "
        f"--input-root {rel(feature_root, repo_root)} "
        f"--reports-root {rel(future_wfa_reports_root, repo_root)} "
        f"--profile-config {rel(profile_config, repo_root)} "
        f"--models-config {rel(models_config, repo_root)} "
        f"--feature-manifest {rel(feature_manifest, repo_root)} "
        f"--data-audit-universe-json {rel(data_audit_universe_json, repo_root)} "
        f"--markets {','.join(markets)} "
        f"--years {','.join(str(year) for year in years)}"
    )


def validate_no_split_artifacts(*, repo_root: Path, future_wfa_reports_root: Path) -> dict[str, Any]:
    expected_artifacts = [
        future_wfa_reports_root / "split_plan.json",
        future_wfa_reports_root / "split_plan.csv",
    ]
    existing = [rel(path, repo_root) for path in expected_artifacts if path.exists()]
    failures = [f"future Phase 5 split artifact already exists: {path}" for path in existing]
    return {
        "status": "PASS" if not failures else "FAIL",
        "future_wfa_reports_root": rel(future_wfa_reports_root, repo_root),
        "expected_future_artifacts": [rel(path, repo_root) for path in expected_artifacts],
        "existing_future_artifacts": existing,
        "generated_split_artifacts": [],
        "commands_executed": 0,
        "failures": failures,
    }


def build_report(
    *,
    repo_root: Path,
    feature_root: Path,
    label_root: Path,
    feature_manifest_path: Path,
    feature_placement_hashes_path: Path,
    label_placement_hashes_path: Path,
    data_audit_universe_path: Path,
    reports_root: Path,
    future_wfa_reports_root: Path,
    profile_config_path: Path,
    models_config_path: Path,
    markets: list[str],
    years: list[int],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    scope = validate_scope(markets, years)
    pairs = expected_pairs(markets, years)
    record_check(
        checks,
        name="exact_8_market_year_scope",
        passed=scope["status"] == "PASS",
        observed={"markets": markets, "years": years, "market_year_count": len(pairs)},
        expected={"markets": list(EXPECTED_MARKETS), "years": list(EXPECTED_YEARS), "market_year_count": 8},
        detail="The preflight may only inspect the active v2 Tier 1 core scope.",
    )

    feature_manifest, feature_manifest_error = read_json_object(feature_manifest_path)
    feature_hash_report, feature_hash_error = read_json_object(feature_placement_hashes_path)
    label_hash_report, label_hash_error = read_json_object(label_placement_hashes_path)
    read_failures = [error for error in (feature_manifest_error, feature_hash_error, label_hash_error) if error]
    record_check(
        checks,
        name="required_evidence_files_readable",
        passed=not read_failures,
        observed=read_failures,
        expected=[],
        detail="Feature manifest and Phase 3/4 active placement hash evidence must be readable JSON.",
    )

    feature_manifest_check = validate_feature_manifest(
        repo_root=repo_root,
        feature_manifest=feature_manifest,
        feature_root=feature_root,
        label_root=label_root,
        pairs=pairs,
    )
    record_check(
        checks,
        name="active_feature_manifest_v2_scope_pass",
        passed=feature_manifest_check["status"] == "PASS",
        observed=feature_manifest_check["failures"],
        expected="PASS tier_1/tier_1_research manifest with 8 outputs and 114 features",
        detail="Phase 5 must consume the active v2 Tier 1 feature manifest, not stale broad evidence.",
    )

    hash_check = validate_hash_reports(
        repo_root=repo_root,
        feature_root=feature_root,
        label_root=label_root,
        feature_hash_report=feature_hash_report,
        label_hash_report=label_hash_report,
        pairs=pairs,
    )
    record_check(
        checks,
        name="active_label_feature_hash_evidence_matches",
        passed=hash_check["status"] == "PASS",
        observed=hash_check["failures"],
        expected="active hashes equal recorded Phase 3/4 placement hashes",
        detail="Stop if the active label or feature files drift from recorded replacement evidence.",
    )

    schema_check = validate_sidecars_and_schemas(
        repo_root=repo_root,
        feature_root=feature_root,
        label_root=label_root,
        pairs=pairs,
    )
    record_check(
        checks,
        name="required_v2_targets_and_wfa_columns_present",
        passed=schema_check["status"] == "PASS",
        observed=schema_check["failures"],
        expected="30m primary, 60m robustness, Apex risk, close, fillability, and WFA columns present",
        detail="The v2 labels and active feature matrices must expose the target fields Phase 5/6 will need.",
    )

    config_check = validate_configs(
        profile_config_path=profile_config_path,
        models_config_path=models_config_path,
        markets=markets,
        years=years,
    )
    record_check(
        checks,
        name="phase5_profile_and_purge_policy_compatible",
        passed=config_check["status"] == "PASS",
        observed=config_check["failures"],
        expected="tier_1 exact scope, 61-bar purge, 30m primary horizon, 60m robustness",
        detail="Phase 5 compatibility requires config scope and purge/embargo policy to match v2 labels.",
    )

    universe_check = validate_data_audit_universe(data_audit_universe_path, pairs)
    record_check(
        checks,
        name="data_audit_universe_exact_usable_scope",
        passed=universe_check["status"] == "PASS",
        observed=universe_check["failures"],
        expected="exact 8 usable market-years with no blocked WFA decisions",
        detail="Tier 1 Phase 5 split generation requires usable data-audit universe evidence.",
    )

    split_artifact_check = validate_no_split_artifacts(
        repo_root=repo_root,
        future_wfa_reports_root=future_wfa_reports_root,
    )
    record_check(
        checks,
        name="no_phase5_split_artifacts_written_or_overwritten",
        passed=split_artifact_check["status"] == "PASS",
        observed=split_artifact_check["existing_future_artifacts"],
        expected=[],
        detail="This command is report-only and must not create or overwrite reports/wfa split plans.",
    )

    failing_checks = [check for check in checks if check["status"] == "FAIL"]
    status = FAIL_STATUS if failing_checks else PASS_STATUS
    future_command = future_phase5_command(
        feature_root=feature_root,
        future_wfa_reports_root=future_wfa_reports_root,
        profile_config=profile_config_path,
        models_config=models_config_path,
        feature_manifest=feature_manifest_path,
        data_audit_universe_json=data_audit_universe_path,
        markets=markets,
        years=years,
        repo_root=repo_root,
    )
    report = {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": scope,
        "summary": {
            "failure_count": len(failing_checks),
            "check_count": len(checks),
            "market_year_count": len(pairs),
            "feature_count": feature_manifest_check.get("feature_count"),
            "commands_executed": 0,
            "split_plan_generated": False,
            "future_phase5_command_exposed": status == PASS_STATUS,
        },
        "checks": checks,
        "evidence": {
            "feature_manifest": {
                "path": rel(feature_manifest_path, repo_root),
                "sha256": file_sha256(feature_manifest_path) if feature_manifest_path.is_file() else None,
                "check": feature_manifest_check,
            },
            "feature_placement_hashes": {
                "path": rel(feature_placement_hashes_path, repo_root),
                "sha256": file_sha256(feature_placement_hashes_path)
                if feature_placement_hashes_path.is_file()
                else None,
            },
            "label_placement_hashes": {
                "path": rel(label_placement_hashes_path, repo_root),
                "sha256": file_sha256(label_placement_hashes_path)
                if label_placement_hashes_path.is_file()
                else None,
            },
            "hash_check": hash_check,
            "schema_check": schema_check,
            "config_check": config_check,
            "data_audit_universe": universe_check,
            "split_artifact_check": split_artifact_check,
        },
        "future_phase5_split_command": future_command if status == PASS_STATUS else None,
        "future_phase5_split_command_evidence_only": True,
        "future_phase5_split_command_not_executed": True,
        "forbidden_patterns": list(FORBIDDEN_NOW),
        "stop_conditions": [
            "Stop if any active hash differs from the recorded active-placement evidence.",
            "Stop if scope expands beyond 6E,CL,ES,ZN years 2023,2024.",
            "Stop if universe evidence is missing, stale, blocked, or not exact 8 usable rows.",
            "Stop if feature/label row counts diverge.",
            "Stop if any required v2 target column is missing.",
            "Stop if reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.* already exists.",
            "Do not run Phase 5, WFA/modeling, Phase 8, provider/download, promotion, paper/live, cleanup, git staging/commit/push, rescue tuning, label/feature rebuilds, or prop-account reports from this command.",
        ],
        "generated_artifact_hygiene": {
            "reports_root": rel(reports_root, repo_root),
            "expected_report_files": [
                rel(reports_root / "phase5_preflight_decision.json", repo_root),
                rel(reports_root / "phase5_preflight_decision.md", repo_root),
            ],
            "future_wfa_reports_root": rel(future_wfa_reports_root, repo_root),
            "expected_future_split_files_not_written": split_artifact_check["expected_future_artifacts"],
        },
        "rollback_hash_evidence": {
            "preflight_is_report_only": True,
            "rollback_for_this_command": "delete generated ignored preflight report root only if separately approved",
            "active_label_feature_backups_remain_external": [
                "data/labeled_active_backup/phase3_v2_apex_30m60m_20260709_tier1_core_pre_replace",
                "data/feature_matrices_active_backup/phase4_v2_apex_30m60m_20260709_tier1_core_pre_replace",
            ],
        },
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Phase 5 v2 WFA Preflight Decision",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated at UTC: `{report['generated_at_utc']}`",
        f"- Scope: `{','.join(report['scope']['markets'])}` `{','.join(str(year) for year in report['scope']['years'])}`",
        f"- Checks: `{summary['check_count']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Commands executed: `{summary['commands_executed']}`",
        f"- Split plan generated: `{summary['split_plan_generated']}`",
        "",
        "## Checks",
        "",
        "| check | status |",
        "| --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['name']}` | `{check['status']}` |")
    lines.extend(["", "## Future Phase 5 Command", ""])
    command = report.get("future_phase5_split_command")
    if command:
        lines.extend(["```powershell", str(command), "```"])
    else:
        lines.append("- Not exposed because the preflight failed closed.")
    failures = [
        f"{check['name']}: {check['observed']}"
        for check in report["checks"]
        if check["status"] == "FAIL"
    ]
    lines.extend(["", "## Failures", ""])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Non-Approval",
            "",
            "- This is report-only evidence. It did not run Phase 5, create split plans, train models, refresh Phase 8, write prop-account reports, or approve trading readiness.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / "phase5_preflight_decision.json"
    md_path = reports_root / "phase5_preflight_decision.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--feature-root", default=DEFAULT_FEATURE_ROOT.as_posix())
    parser.add_argument("--label-root", default=DEFAULT_LABEL_ROOT.as_posix())
    parser.add_argument("--feature-manifest", default=DEFAULT_FEATURE_MANIFEST.as_posix())
    parser.add_argument("--feature-placement-hashes", default=DEFAULT_FEATURE_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--label-placement-hashes", default=DEFAULT_LABEL_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--data-audit-universe-json", default=DEFAULT_DATA_AUDIT_UNIVERSE.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--future-wfa-reports-root", default=DEFAULT_FUTURE_WFA_REPORTS_ROOT.as_posix())
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--markets", default=",".join(EXPECTED_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in EXPECTED_YEARS))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    report = build_report(
        repo_root=repo_root,
        feature_root=resolve_path(repo_root, args.feature_root),
        label_root=resolve_path(repo_root, args.label_root),
        feature_manifest_path=resolve_path(repo_root, args.feature_manifest),
        feature_placement_hashes_path=resolve_path(repo_root, args.feature_placement_hashes),
        label_placement_hashes_path=resolve_path(repo_root, args.label_placement_hashes),
        data_audit_universe_path=resolve_path(repo_root, args.data_audit_universe_json),
        reports_root=resolve_path(repo_root, args.reports_root),
        future_wfa_reports_root=resolve_path(repo_root, args.future_wfa_reports_root),
        profile_config_path=resolve_path(repo_root, args.profile_config),
        models_config_path=resolve_path(repo_root, args.models_config),
        markets=parse_csv_strings(args.markets),
        years=parse_csv_ints(args.years),
    )
    json_path, md_path = write_report(report, resolve_path(repo_root, args.reports_root))
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"commands_executed={report['summary']['commands_executed']} "
        f"split_plan_generated={report['summary']['split_plan_generated']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
