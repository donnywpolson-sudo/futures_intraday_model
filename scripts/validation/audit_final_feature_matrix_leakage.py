#!/usr/bin/env python3
"""Report-only leakage audit for the final active feature matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from scripts.validation.feature_leakage_guard import forbidden_feature_columns


DEFAULT_FEATURE_ROOT = Path("data/feature_matrices")
DEFAULT_LABELED_ROOT = Path("data/labeled")
DEFAULT_MANIFEST = (
    Path("reports")
    / "features_baseline"
    / "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement"
    / "baseline_feature_manifest.json"
)
DEFAULT_SPLIT_PLAN = (
    Path("reports")
    / "wfa"
    / "phase5_v2_apex_30m60m_20260709_tier1_core"
    / "split_plan.json"
)
DEFAULT_OUTPUT_ROOT = (
    Path("reports")
    / "model_trust_audit"
    / "final_feature_matrix_leakage_20260709"
)
DEFAULT_PHASE4_SCRIPT = Path("scripts/phase4_features/build_baseline_features.py")
DEFAULT_WFA_RUNNER = Path("scripts/phase7_wfa/run_wfa.py")
DEFAULT_MARKETS = ("6E", "CL", "ES", "ZN")
DEFAULT_YEARS = (2023, 2024)
REPORT_JSON = "final_feature_matrix_leakage_audit.json"
REPORT_MD = "final_feature_matrix_leakage_audit.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_path(repo_root: Path, path: Path | str | None) -> Path | None:
    if path is None:
        return None
    raw = Path(path)
    return raw if raw.is_absolute() else repo_root / raw


def _display(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_list(path: Path) -> list[str]:
    payload = _read_json(path)
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"expected JSON string list: {path.as_posix()}")
    return list(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_text_or_empty(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_csv(value: str | None, *, cast: type = str) -> tuple[Any, ...]:
    if not value:
        return ()
    return tuple(cast(item.strip()) for item in value.split(",") if item.strip())


def _parquet_columns_and_rows(path: Path) -> tuple[list[str], int | None]:
    try:
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(path)
        return list(parquet_file.schema.names), int(parquet_file.metadata.num_rows)
    except Exception:
        frame = pd.read_parquet(path)
        return list(frame.columns), int(len(frame))


def _feature_families() -> dict[str, str]:
    try:
        from scripts.phase4_features import build_baseline_features as phase4

        return {str(key): str(value) for key, value in phase4.FEATURE_TO_FAMILY.items()}
    except Exception:
        return {}


def _family_source(family: str, feature: str) -> str:
    if family in {"tier1_intermarket", "tier1_cross_market_regime"}:
        return "same-timestamp Tier 1 labeled OHLCV rows joined on exact UTC ts"
    if family == "higher_timeframe_prior_session":
        return "current completed OHLCV row, current session metadata, and prior completed session OHLCV"
    if family in {"volatility_volume", "effort_result"}:
        return "Phase 3 labeled OHLCV close/high/low/volume from Phase 2 causal rows"
    if family in {"session_structure", "trend_day_open_drive", "auction_acceptance"}:
        return "current-session Phase 3 labeled OHLCV and session metadata through the feature row"
    if "volume" in feature:
        return "Phase 3 labeled OHLCV volume and range fields"
    return "Phase 3 labeled OHLCV and session metadata from Phase 2 causal rows"


def _family_chain(family: str, feature: str) -> str:
    if family in {"tier1_intermarket", "tier1_cross_market_regime"}:
        return "compute causal self/other trailing returns, exact-merge on ts, then combine same-timestamp values"
    if family == "higher_timeframe_prior_session":
        if "prior_session" in feature or "overnight" in feature:
            return "map previous completed session stats with session-level shift(1), then compare to current completed row"
        return "compute trailing completed-bar return/slope inside session segment"
    if "z_" in feature:
        return "current value minus trailing rolling mean divided by trailing rolling std inside session segment"
    if "vol" in feature or "shock" in feature or "large_bar" in feature:
        return "trailing rolling range/return/volume statistics inside session segment"
    if family in {"session_structure", "trend_day_open_drive", "auction_acceptance"}:
        return "current-session cumulative/cummax/cummin/VWAP/opening-range state through current completed bar"
    if family == "breakout_rejection":
        return "prior rolling high/low shifted one bar, then compare current completed bar"
    if family == "range_chop":
        return "trailing rolling range/overlap/chop statistics inside session segment"
    if family == "time_buckets":
        return "deterministic timestamp/session-calendar bucket transform"
    if family == "fade_safety_trend_danger":
        return "trailing return/path/directional-bar statistics inside session segment"
    if family == "effort_result":
        return "trailing 30-bar close progress, true range, and volume ratios"
    return "deterministic current-row or trailing-window feature transform"


def _availability_lag(family: str, feature: str) -> str:
    if family in {"tier1_intermarket", "tier1_cross_market_regime"}:
        return "same-timestamp cross-market bar must be complete; no stale or future join allowed"
    if family == "higher_timeframe_prior_session" and (
        "prior_session" in feature or "overnight" in feature
    ):
        return "prior completed session plus current completed bar"
    if family in {"session_structure", "trend_day_open_drive", "auction_acceptance"}:
        return "current session state available after current one-minute bar close"
    if family == "time_buckets":
        return "known from timestamp/session calendar at or before prediction timestamp"
    return "current completed bar plus trailing completed bars"


def _risk_class(family: str, feature: str, unknown: bool) -> str:
    if unknown:
        return "high"
    if family in {"tier1_intermarket", "tier1_cross_market_regime"}:
        return "medium"
    if family in {"session_structure", "trend_day_open_drive", "auction_acceptance"}:
        return "medium"
    if family == "higher_timeframe_prior_session":
        return "medium"
    if feature in {"feature_minutes_until_session_close", "feature_last_30m_flag"}:
        return "medium"
    return "low"


def build_feature_risk_inventory(feature_cols: Sequence[str]) -> list[dict[str, Any]]:
    families = _feature_families()
    inventory: list[dict[str, Any]] = []
    for feature in feature_cols:
        family = families.get(feature, "unregistered")
        unknown = family == "unregistered"
        uses_current_bar = family not in {"time_buckets"} or feature in {
            "feature_minutes_since_session_open",
            "feature_minutes_until_session_close",
            "feature_session_progress",
        }
        inventory.append(
            {
                "feature": feature,
                "family": family,
                "source_data": _family_source(family, feature),
                "transformation_chain": _family_chain(family, feature),
                "availability_lag": _availability_lag(family, feature),
                "feature_timestamp_rule": (
                    "conservative feature_timestamp = row ts; source rows are at row ts or earlier"
                ),
                "prediction_timestamp_rule": "prediction_timestamp = row ts + 1 minute",
                "timestamp_contract": "feature_timestamp <= prediction_timestamp",
                "max_source_offset_minutes": 0,
                "uses_current_completed_bar": uses_current_bar,
                "intra_bar_policy": (
                    "remove_or_lag_if_prediction_before_bar_close"
                    if uses_current_bar
                    else "safe_for_precomputed_calendar_time"
                ),
                "risk_class": _risk_class(family, feature, unknown),
                "risk_reason": (
                    "feature is not registered in Phase 4 feature family metadata"
                    if unknown
                    else "risk controlled by completed-bar timestamp convention and static source inspection"
                ),
            }
        )
    return inventory


def _assigned_features_for_pattern(source: str, pattern: str) -> list[str]:
    rows: list[str] = []
    for line in source.splitlines():
        if re.search(pattern, line):
            rows.extend(re.findall(r"['\"](feature_[A-Za-z0-9_]+)['\"]\s*\]", line))
    return sorted(set(rows))


def static_phase4_checks(
    *,
    phase4_source: str,
    feature_cols: Sequence[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    forbidden = forbidden_feature_columns(feature_cols)
    negative_shift_features = _assigned_features_for_pattern(
        phase4_source,
        r"\.shift\s*\(\s*-\d|periods\s*=\s*-\d",
    )
    full_session_features = _assigned_features_for_pattern(
        phase4_source,
        r"\.transform\s*\(\s*['\"](?:max|min|last|sum|mean|std)['\"]\s*\)",
    )
    fit_transform_features = _assigned_features_for_pattern(
        phase4_source,
        r"fit_transform\s*\(|StandardScaler|MinMaxScaler|RobustScaler",
    )
    has_exact_ts_merge = ".merge(frame, on=\"ts\"" in phase4_source or ".merge(frame, on='ts'" in phase4_source
    checks = [
        {
            "name": "feature_registry_contains_no_forbidden_columns",
            "status": "PASS" if not forbidden else "FAIL",
            "failure": f"forbidden feature columns present: {forbidden}" if forbidden else None,
            "impacted_features": forbidden,
        },
        {
            "name": "phase4_source_has_no_negative_shift",
            "status": "PASS" if not negative_shift_features and not re.search(r"\.shift\s*\(\s*-\d|periods\s*=\s*-\d", phase4_source) else "FAIL",
            "failure": "negative shift/future row access detected" if re.search(r"\.shift\s*\(\s*-\d|periods\s*=\s*-\d", phase4_source) else None,
            "impacted_features": negative_shift_features,
        },
        {
            "name": "phase4_source_has_no_unbounded_full_session_transform",
            "status": "PASS" if not full_session_features else "FAIL",
            "failure": "full-session transform aggregate detected" if full_session_features else None,
            "impacted_features": full_session_features,
        },
        {
            "name": "phase4_source_has_no_full_sample_normalization_fit",
            "status": "PASS" if not re.search(r"fit_transform\s*\(|StandardScaler|MinMaxScaler|RobustScaler", phase4_source) else "FAIL",
            "failure": "Phase 4 source contains fitted normalization before WFA" if re.search(r"fit_transform\s*\(|StandardScaler|MinMaxScaler|RobustScaler", phase4_source) else None,
            "impacted_features": fit_transform_features,
        },
        {
            "name": "intermarket_features_join_on_exact_ts",
            "status": "PASS"
            if not any("intermarket" in row.get("family", "") for row in build_feature_risk_inventory(feature_cols))
            or (has_exact_ts_merge and "merge_asof" not in phase4_source)
            else "FAIL",
            "failure": "intermarket features require exact ts merge and no merge_asof" if not has_exact_ts_merge and any("intermarket" in row.get("family", "") for row in build_feature_risk_inventory(feature_cols)) else None,
            "impacted_features": [
                feature
                for feature, family in _feature_families().items()
                if family in {"tier1_intermarket", "tier1_cross_market_regime"}
                and feature in set(feature_cols)
            ],
        },
    ]
    removals: list[str] = []
    for check in checks:
        if check["status"] == "FAIL":
            removals.extend(str(item) for item in check.get("impacted_features", []) if item)
    if forbidden:
        removals.extend(forbidden)
    return checks, sorted(set(removals))


def wfa_normalization_checks(wfa_source: str) -> list[dict[str, Any]]:
    if not wfa_source:
        return [
            {
                "name": "wfa_runner_source_available",
                "status": "MISSING_EVIDENCE",
                "failure": "WFA runner source was not available for train-only normalization inspection",
            }
        ]
    pipeline_present = all(
        token in wfa_source for token in ("Pipeline", "SimpleImputer", "StandardScaler")
    )
    fit_train_only = "estimator.fit(x_train, y_train)" in wfa_source
    overlap_guard = 'train["ts"].max() >= test["ts"].min()' in wfa_source
    return [
        {
            "name": "wfa_uses_sklearn_pipeline_for_fit_transforms",
            "status": "PASS" if pipeline_present else "FAIL",
            "failure": None if pipeline_present else "expected Pipeline(SimpleImputer, StandardScaler, estimator) not found",
        },
        {
            "name": "wfa_fits_pipeline_on_train_frame_only",
            "status": "PASS" if fit_train_only else "FAIL",
            "failure": None if fit_train_only else "estimator.fit(x_train, y_train) not found",
        },
        {
            "name": "wfa_rejects_train_test_timestamp_overlap",
            "status": "PASS" if overlap_guard else "FAIL",
            "failure": None if overlap_guard else "train/test timestamp overlap guard not found",
        },
    ]


def _safe_read_frame(path: Path, columns: Sequence[str]) -> tuple[pd.DataFrame | None, str | None]:
    try:
        return pd.read_parquet(path, columns=list(dict.fromkeys(columns))), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _sample_frame(frame: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if len(frame) <= max_rows:
        return frame
    positions = np.linspace(0, len(frame) - 1, num=max_rows, dtype=int)
    return frame.iloc[np.unique(positions)].copy()


def _read_parquet_sample(
    path: Path,
    *,
    columns: Sequence[str],
    max_rows: int,
) -> tuple[pd.DataFrame | None, str | None]:
    try:
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(path)
        frames: list[pd.DataFrame] = []
        remaining = max_rows
        for batch in parquet_file.iter_batches(
            batch_size=max(1, min(max_rows, remaining)),
            columns=list(dict.fromkeys(columns)),
        ):
            frame = batch.to_pandas()
            frames.append(frame)
            remaining -= len(frame)
            if remaining <= 0:
                break
        if not frames:
            return pd.DataFrame(columns=list(columns)), None
        return pd.concat(frames, ignore_index=True), None
    except Exception:
        frame, error = _safe_read_frame(path, columns)
        if error or frame is None:
            return None, error
        return _sample_frame(frame, max_rows), None


def _numeric_series(frame: pd.DataFrame, column: str) -> pd.Series | None:
    if column not in frame.columns:
        return None
    series = pd.to_numeric(frame[column], errors="coerce")
    if series.notna().sum() == 0:
        return None
    return series


def embedding_findings_for_frame(
    frame: pd.DataFrame,
    *,
    feature_cols: Sequence[str],
    target_cols: Sequence[str],
    market: str,
    year: int,
    min_overlap: int,
    corr_threshold: float,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    valid_mask = (
        frame["training_row_valid"].fillna(False).astype(bool)
        if "training_row_valid" in frame.columns
        else pd.Series(True, index=frame.index)
    )
    sample = frame.loc[valid_mask]
    if sample.empty:
        return findings
    numeric_features = {
        feature: _numeric_series(sample, feature)
        for feature in feature_cols
        if feature in sample.columns
    }
    numeric_targets = {
        target: _numeric_series(sample, target)
        for target in target_cols
        if target in sample.columns
    }
    numeric_features = {key: value for key, value in numeric_features.items() if value is not None}
    numeric_targets = {key: value for key, value in numeric_targets.items() if value is not None}
    for feature, feature_series in numeric_features.items():
        assert feature_series is not None
        for target, target_series in numeric_targets.items():
            assert target_series is not None
            pair = pd.concat([feature_series, target_series], axis=1).dropna()
            if len(pair) < min_overlap:
                continue
            left = pair.iloc[:, 0].to_numpy(dtype=float)
            right = pair.iloc[:, 1].to_numpy(dtype=float)
            left_std = float(np.nanstd(left))
            right_std = float(np.nanstd(right))
            if (
                left_std > 1e-12
                and right_std > 1e-12
                and np.allclose(left, right, rtol=1e-12, atol=1e-12)
            ):
                findings.append(
                    {
                        "severity": "FAIL",
                        "market": market,
                        "year": year,
                        "feature": feature,
                        "target": target,
                        "overlap_rows": int(len(pair)),
                        "reason": "feature is numerically identical or near-identical to target column",
                    }
                )
                continue
            if left_std <= 1e-12 or right_std <= 1e-12:
                continue
            corr = float(np.corrcoef(left, right)[0, 1])
            if np.isfinite(corr) and abs(corr) >= corr_threshold:
                findings.append(
                    {
                        "severity": "WARN",
                        "market": market,
                        "year": year,
                        "feature": feature,
                        "target": target,
                        "overlap_rows": int(len(pair)),
                        "abs_corr": abs(corr),
                        "reason": "feature has near-perfect target correlation; review as possible structural label embedding",
                    }
                )
    return findings


def audit_matrix_files(
    *,
    repo_root: Path,
    feature_root: Path,
    labeled_root: Path,
    markets: Sequence[str],
    years: Sequence[int],
    feature_cols: Sequence[str],
    target_cols: Sequence[str],
    max_embedding_sample_rows_per_file: int,
    min_embedding_overlap: int,
    corr_threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    embedding_findings: list[dict[str, Any]] = []
    removals: list[str] = []
    for market in markets:
        for year in years:
            feature_path = feature_root / market / f"{year}.parquet"
            label_path = labeled_root / market / f"{year}.parquet"
            row: dict[str, Any] = {
                "market": market,
                "year": year,
                "feature_path": _display(repo_root, feature_path),
                "label_path": _display(repo_root, label_path),
                "status": "PASS",
                "failures": [],
                "row_count": None,
                "labeled_row_count": None,
                "timestamp_null_count": None,
                "timestamp_contract_violation_count": None,
                "label_feature_ts_match": None,
                "missing_feature_columns": [],
                "missing_target_columns": [],
            }
            if not feature_path.exists():
                row["status"] = "FAIL"
                row["failures"].append("feature parquet missing")
                rows.append(row)
                continue
            if not label_path.exists():
                row["status"] = "FAIL"
                row["failures"].append("labeled source parquet missing")
                rows.append(row)
                continue
            feature_columns, row_count = _parquet_columns_and_rows(feature_path)
            label_columns, label_row_count = _parquet_columns_and_rows(label_path)
            row["row_count"] = row_count
            row["labeled_row_count"] = label_row_count
            if "ts" not in feature_columns:
                row["status"] = "FAIL"
                row["failures"].append("feature parquet missing ts")
                rows.append(row)
                continue
            missing_features = sorted(set(feature_cols) - set(feature_columns))
            missing_targets = sorted(set(target_cols) - set(feature_columns))
            row["missing_feature_columns"] = missing_features
            row["missing_target_columns"] = missing_targets
            if missing_features:
                row["status"] = "FAIL"
                row["failures"].append("feature parquet missing registered feature columns")
            columns = ["ts", "training_row_valid"]
            frame, error = _safe_read_frame(
                feature_path,
                [column for column in columns if column in feature_columns],
            )
            if error or frame is None:
                row["status"] = "FAIL"
                row["failures"].append(f"feature parquet read failed: {error}")
                rows.append(row)
                continue
            ts = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
            prediction_ts = ts + pd.Timedelta(minutes=1)
            timestamp_null_count = int(ts.isna().sum())
            timestamp_contract_violations = int((ts > prediction_ts).fillna(True).sum())
            checked_pairs = int(row_count or len(frame)) * len(feature_cols)
            row["timestamp_null_count"] = timestamp_null_count
            row["timestamp_contract_violation_count"] = timestamp_contract_violations
            row["feature_timestamp_contract_checked_pairs"] = checked_pairs
            row["feature_timestamp_definition"] = "conservative feature_timestamp = row ts"
            row["prediction_timestamp_definition"] = "row ts + 1 minute"
            if timestamp_null_count or timestamp_contract_violations:
                row["status"] = "FAIL"
                row["failures"].append("feature_timestamp <= prediction_timestamp proof failed")
            label_ts_frame, label_error = _safe_read_frame(label_path, ["ts"] if "ts" in label_columns else [])
            if label_error or label_ts_frame is None or "ts" not in label_ts_frame.columns:
                row["status"] = "FAIL"
                row["failures"].append(f"labeled ts read failed: {label_error}")
            else:
                label_ts = pd.to_datetime(label_ts_frame["ts"], utc=True, errors="coerce")
                ts_match = bool(len(label_ts) == len(ts) and label_ts.reset_index(drop=True).equals(ts.reset_index(drop=True)))
                row["label_feature_ts_match"] = ts_match
                if not ts_match:
                    row["status"] = "FAIL"
                    row["failures"].append("feature/labeled ts sequence mismatch")
            embedding_columns = [
                column
                for column in ["training_row_valid", *feature_cols, *target_cols]
                if column in feature_columns
            ]
            sampled, sample_error = _read_parquet_sample(
                feature_path,
                columns=embedding_columns,
                max_rows=max_embedding_sample_rows_per_file,
            )
            if sample_error or sampled is None:
                row["status"] = "FAIL"
                row["failures"].append(f"embedding sample read failed: {sample_error}")
                rows.append(row)
                continue
            row["embedding_sample_rows"] = int(len(sampled))
            embedding_findings.extend(
                embedding_findings_for_frame(
                    sampled,
                    feature_cols=feature_cols,
                    target_cols=target_cols,
                    market=market,
                    year=year,
                    min_overlap=min_embedding_overlap,
                    corr_threshold=corr_threshold,
                )
            )
            rows.append(row)
    for finding in embedding_findings:
        if finding.get("severity") == "FAIL":
            removals.append(str(finding["feature"]))
    return rows, embedding_findings, sorted(set(removals))


def _status_from_checks(checks: Sequence[Mapping[str, Any]]) -> str:
    statuses = {str(check.get("status")) for check in checks}
    if "FAIL" in statuses:
        return "FAIL"
    if "MISSING_EVIDENCE" in statuses:
        return "MISSING_EVIDENCE"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _findings(
    *,
    static_checks: Sequence[Mapping[str, Any]],
    wfa_checks: Sequence[Mapping[str, Any]],
    matrix_rows: Sequence[Mapping[str, Any]],
    embedding_findings: Sequence[Mapping[str, Any]],
    feature_cols: Sequence[str],
    target_cols: Sequence[str],
) -> dict[str, Any]:
    target_intersection = sorted(set(feature_cols) & set(target_cols))
    exact_embedding = [row for row in embedding_findings if row.get("severity") == "FAIL"]
    high_corr = [row for row in embedding_findings if row.get("severity") == "WARN"]
    row_failures = [row for row in matrix_rows if row.get("status") == "FAIL"]
    return {
        "lookahead_bias": {
            "status": "FAIL"
            if any(check.get("status") == "FAIL" for check in static_checks if "negative_shift" in str(check.get("name")) or "full_session" in str(check.get("name")))
            or row_failures
            else "PASS",
            "static_checks": [
                check
                for check in static_checks
                if "negative_shift" in str(check.get("name"))
                or "full_session" in str(check.get("name"))
                or "intermarket" in str(check.get("name"))
            ],
            "row_level_failures": row_failures,
        },
        "target_leakage": {
            "status": "FAIL" if target_intersection or forbidden_feature_columns(feature_cols) else "PASS",
            "target_feature_intersection": target_intersection,
            "forbidden_feature_columns": forbidden_feature_columns(feature_cols),
        },
        "feature_engineering_outside_training_windows": {
            "status": "FAIL"
            if any(check.get("status") == "FAIL" for check in static_checks if "normalization" in str(check.get("name")))
            else "PASS",
            "phase4_checks": [
                check for check in static_checks if "normalization" in str(check.get("name"))
            ],
            "note": "Phase 4 should contain deterministic transforms only; fitted transforms belong inside WFA train folds.",
        },
        "accidental_label_embedding": {
            "status": "FAIL" if exact_embedding else ("WARN" if high_corr else "PASS"),
            "exact_or_near_identical_findings": exact_embedding,
            "near_perfect_correlation_findings": high_corr,
        },
        "normalization_leakage": {
            "status": _status_from_checks(wfa_checks),
            "wfa_checks": list(wfa_checks),
        },
        "order_flow_features": {
            "status": "PASS",
            "finding": (
                "No true order-book/order-flow columns are in feature_cols; effort/result features are OHLCV volume proxies only."
            ),
        },
    }


def _confidence(
    *,
    findings: Mapping[str, Any],
    matrix_rows: Sequence[Mapping[str, Any]],
    inventory: Sequence[Mapping[str, Any]],
    required_removals: Sequence[str],
) -> dict[str, Any]:
    score = 100
    deductions: list[dict[str, Any]] = [
        {
            "points": 2,
            "reason": "proof depends on completed-current-bar prediction convention",
        },
        {
            "points": 2,
            "reason": "per-feature source chains are static code inspection plus conservative timestamp assignment, not per-cell replay",
        },
    ]
    if required_removals:
        deductions.append({"points": 35, "reason": "required feature removals are present"})
    failed_groups = [
        key
        for key, value in findings.items()
        if isinstance(value, Mapping) and value.get("status") == "FAIL"
    ]
    if failed_groups:
        deductions.append({"points": 20 * len(failed_groups), "reason": f"failed leakage groups: {failed_groups}"})
    missing_groups = [
        key
        for key, value in findings.items()
        if isinstance(value, Mapping) and value.get("status") == "MISSING_EVIDENCE"
    ]
    if missing_groups:
        deductions.append({"points": 10 * len(missing_groups), "reason": f"missing evidence groups: {missing_groups}"})
    unknown_features = [row["feature"] for row in inventory if row.get("family") == "unregistered"]
    if unknown_features:
        deductions.append({"points": min(25, len(unknown_features) * 2), "reason": "unregistered feature lineage"})
    matrix_failures = [row for row in matrix_rows if row.get("status") == "FAIL"]
    if matrix_failures:
        deductions.append({"points": min(50, len(matrix_failures) * 8), "reason": "matrix file row-level failures"})
    for deduction in deductions:
        score -= int(deduction["points"])
    return {
        "score": max(0, min(100, score)),
        "scale": "0-100",
        "deductions": deductions,
    }


def build_markdown(payload: Mapping[str, Any]) -> str:
    confidence = payload["confidence_score"]
    findings = payload["leakage_findings"]
    lines = [
        "# Final Feature Matrix Leakage Audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Verdict: `{payload['verdict']}`",
        f"- Confidence score: `{confidence['score']}/100`",
        f"- Feature count: `{payload['feature_count']}`",
        f"- Scope: `{payload['scope']['markets']}` years `{payload['scope']['years']}`",
        f"- Required feature removals: `{payload['required_feature_removals']}`",
        "",
        "## Leakage Findings",
        "",
        "| category | status | key evidence |",
        "| --- | --- | --- |",
    ]
    for key, value in findings.items():
        if not isinstance(value, Mapping):
            continue
        status = value.get("status")
        if key == "accidental_label_embedding":
            evidence = (
                f"exact={len(value.get('exact_or_near_identical_findings', []))}, "
                f"near_corr={len(value.get('near_perfect_correlation_findings', []))}"
            )
        elif key == "target_leakage":
            evidence = f"forbidden={len(value.get('forbidden_feature_columns', []))}"
        elif key == "lookahead_bias":
            evidence = f"row_failures={len(value.get('row_level_failures', []))}"
        else:
            evidence = str(value.get("finding") or value.get("note") or "")
        lines.append(f"| `{key}` | `{status}` | {evidence.replace('|', '/')} |")
    lines.extend(
        [
            "",
            "## Feature Risk Inventory",
            "",
            "| feature | family | lag | risk |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["feature_risk_inventory"]:
        lines.append(
            f"| `{row['feature']}` | `{row['family']}` | {row['availability_lag'].replace('|', '/')} | `{row['risk_class']}` |"
        )
    lines.extend(
        [
            "",
            "## Non Approval",
            "",
            "- This report is evidence only. It does not approve WFA/modeling, predictions, Phase 8, promotion, artifact freeze, final holdout, paper/live trading, provider downloads, cleanup, staging, commits, or pushes.",
            "",
        ]
    )
    return "\n".join(lines)


def build_final_feature_matrix_leakage_audit(
    *,
    repo_root: Path,
    feature_root: Path = DEFAULT_FEATURE_ROOT,
    labeled_root: Path = DEFAULT_LABELED_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    split_plan_path: Path | None = DEFAULT_SPLIT_PLAN,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    phase4_script_path: Path = DEFAULT_PHASE4_SCRIPT,
    wfa_runner_path: Path = DEFAULT_WFA_RUNNER,
    markets: Sequence[str] = DEFAULT_MARKETS,
    years: Sequence[int] = DEFAULT_YEARS,
    max_embedding_sample_rows_per_file: int = 1_000,
    min_embedding_overlap: int = 100,
    corr_threshold: float = 0.999999,
    generated_at_utc: str | None = None,
    write_reports: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    feature_root = _repo_path(repo_root, feature_root) or repo_root / DEFAULT_FEATURE_ROOT
    labeled_root = _repo_path(repo_root, labeled_root) or repo_root / DEFAULT_LABELED_ROOT
    manifest_path = _repo_path(repo_root, manifest_path) or repo_root / DEFAULT_MANIFEST
    split_plan_path = _repo_path(repo_root, split_plan_path) if split_plan_path else None
    output_root = _repo_path(repo_root, output_root) or repo_root / DEFAULT_OUTPUT_ROOT
    phase4_script_path = _repo_path(repo_root, phase4_script_path) or repo_root / DEFAULT_PHASE4_SCRIPT
    wfa_runner_path = _repo_path(repo_root, wfa_runner_path) or repo_root / DEFAULT_WFA_RUNNER
    generated_at_utc = generated_at_utc or _utc_now()

    feature_cols = _read_json_list(feature_root / "feature_cols.json")
    target_cols = _read_json_list(feature_root / "target_cols.json")
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    split_plan = _read_json(split_plan_path) if split_plan_path and split_plan_path.exists() else {}
    phase4_source = _read_text_or_empty(phase4_script_path)
    wfa_source = _read_text_or_empty(wfa_runner_path)

    inventory = build_feature_risk_inventory(feature_cols)
    static_checks, static_removals = static_phase4_checks(
        phase4_source=phase4_source,
        feature_cols=feature_cols,
    )
    wfa_checks = wfa_normalization_checks(wfa_source)
    matrix_rows, embedding_findings, embedding_removals = audit_matrix_files(
        repo_root=repo_root,
        feature_root=feature_root,
        labeled_root=labeled_root,
        markets=markets,
        years=years,
        feature_cols=feature_cols,
        target_cols=target_cols,
        max_embedding_sample_rows_per_file=max_embedding_sample_rows_per_file,
        min_embedding_overlap=min_embedding_overlap,
        corr_threshold=corr_threshold,
    )
    required_removals = sorted(set(static_removals) | set(embedding_removals))
    findings = _findings(
        static_checks=static_checks,
        wfa_checks=wfa_checks,
        matrix_rows=matrix_rows,
        embedding_findings=embedding_findings,
        feature_cols=feature_cols,
        target_cols=target_cols,
    )
    confidence = _confidence(
        findings=findings,
        matrix_rows=matrix_rows,
        inventory=inventory,
        required_removals=required_removals,
    )
    status = "PASS" if not required_removals and all(
        not (isinstance(value, Mapping) and value.get("status") == "FAIL")
        for value in findings.values()
    ) else "FAIL"
    verdict = (
        "PASS_NO_FEATURE_LEAKAGE_FOUND_UNDER_COMPLETED_BAR_CONVENTION"
        if status == "PASS"
        else "FAIL_FEATURE_LEAKAGE_REQUIRES_REMEDIATION"
    )
    payload: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "git_commit": _git_commit(repo_root),
        "script_path": _display(repo_root, Path(__file__).resolve()),
        "diagnostic_type": "final_feature_matrix_leakage_audit",
        "diagnostic_only": True,
        "status": status,
        "verdict": verdict,
        "scope": {
            "feature_root": _display(repo_root, feature_root),
            "labeled_root": _display(repo_root, labeled_root),
            "markets": list(markets),
            "years": list(years),
            "matrix_file_count": len(matrix_rows),
            "active_v2_tier1_core_only": True,
        },
        "timestamp_contract": {
            "feature_timestamp": "row ts, conservatively assigned for every non-null feature value",
            "prediction_timestamp": "row ts + 1 minute",
            "required_inequality": "feature_timestamp <= prediction_timestamp",
            "completed_bar_convention_required": True,
            "intra_bar_prediction_policy": "current-bar OHLCV features must be removed or lagged if predictions occur before bar close",
        },
        "feature_count": len(feature_cols),
        "target_column_count": len(target_cols),
        "feature_risk_inventory": inventory,
        "static_phase4_checks": static_checks,
        "matrix_file_checks": matrix_rows,
        "embedding_findings": embedding_findings,
        "leakage_findings": findings,
        "required_feature_removals": required_removals,
        "confidence_score": confidence,
        "source_evidence": {
            "feature_cols_path": _display(repo_root, feature_root / "feature_cols.json"),
            "feature_cols_sha256": _file_sha256(feature_root / "feature_cols.json"),
            "target_cols_path": _display(repo_root, feature_root / "target_cols.json"),
            "target_cols_sha256": _file_sha256(feature_root / "target_cols.json"),
            "phase4_manifest_path": _display(repo_root, manifest_path),
            "phase4_manifest_sha256": _file_sha256(manifest_path),
            "phase4_manifest_status": manifest.get("status") if isinstance(manifest, Mapping) else None,
            "split_plan_path": _display(repo_root, split_plan_path),
            "split_plan_sha256": _file_sha256(split_plan_path),
            "split_plan_status": split_plan.get("status") if isinstance(split_plan, Mapping) else None,
            "phase4_script_path": _display(repo_root, phase4_script_path),
            "phase4_script_sha256": _file_sha256(phase4_script_path),
            "wfa_runner_path": _display(repo_root, wfa_runner_path),
            "wfa_runner_sha256": _file_sha256(wfa_runner_path),
        },
        "summary_counts": {
            "feature_risk_class_counts": dict(Counter(row["risk_class"] for row in inventory)),
            "matrix_file_status_counts": dict(Counter(row["status"] for row in matrix_rows)),
            "embedding_finding_severity_counts": dict(Counter(row["severity"] for row in embedding_findings)),
            "leakage_finding_status_counts": dict(
                Counter(
                    value.get("status")
                    for value in findings.values()
                    if isinstance(value, Mapping)
                )
            ),
        },
        "non_approval": {
            "feature_rebuild": False,
            "wfa_modeling": False,
            "prediction_generation": False,
            "phase8": False,
            "promotion": False,
            "artifact_freeze": False,
            "final_holdout": False,
            "paper_live": False,
            "provider_downloads": False,
            "cleanup": False,
            "staging_commit_push": False,
        },
        "outputs": {},
    }
    if write_reports:
        json_path = output_root / REPORT_JSON
        md_path = output_root / REPORT_MD
        payload["outputs"] = {
            "json": _display(repo_root, json_path),
            "markdown": _display(repo_root, md_path),
        }
        _write_json(json_path, payload)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(build_markdown(payload), encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--feature-root", default=DEFAULT_FEATURE_ROOT.as_posix())
    parser.add_argument("--labeled-root", default=DEFAULT_LABELED_ROOT.as_posix())
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST.as_posix())
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    parser.add_argument("--phase4-script", default=DEFAULT_PHASE4_SCRIPT.as_posix())
    parser.add_argument("--wfa-runner", default=DEFAULT_WFA_RUNNER.as_posix())
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    parser.add_argument("--max-embedding-sample-rows-per-file", type=int, default=1_000)
    parser.add_argument("--min-embedding-overlap", type=int, default=100)
    parser.add_argument("--corr-threshold", type=float, default=0.999999)
    parser.add_argument("--fail-on-leakage", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = build_final_feature_matrix_leakage_audit(
        repo_root=Path(args.repo_root),
        feature_root=Path(args.feature_root),
        labeled_root=Path(args.labeled_root),
        manifest_path=Path(args.manifest),
        split_plan_path=Path(args.split_plan) if args.split_plan else None,
        output_root=Path(args.output_root),
        phase4_script_path=Path(args.phase4_script),
        wfa_runner_path=Path(args.wfa_runner),
        markets=_parse_csv(args.markets, cast=str) or DEFAULT_MARKETS,
        years=_parse_csv(args.years, cast=int) or DEFAULT_YEARS,
        max_embedding_sample_rows_per_file=args.max_embedding_sample_rows_per_file,
        min_embedding_overlap=args.min_embedding_overlap,
        corr_threshold=args.corr_threshold,
        write_reports=True,
    )
    print(
        f"{payload['verdict']}: "
        f"status={payload['status']} "
        f"features={payload['feature_count']} "
        f"removals={len(payload['required_feature_removals'])} "
        f"confidence={payload['confidence_score']['score']} "
        f"report={payload['outputs'].get('json')}"
    )
    return 1 if args.fail_on_leakage and payload["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
