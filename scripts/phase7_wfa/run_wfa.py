#!/usr/bin/env python3
"""Run simple train-only baseline models on existing WFA split plans."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
import yaml
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts.validation.data_audit_universe_guard import (
    data_audit_evidence_matches,
    load_data_audit_universe,
)
from scripts.validation.feature_leakage_guard import forbidden_feature_columns
from scripts.profile_scope import (
    DEFAULT_PROFILE_CONFIG,
    ProfileScope,
    load_profile_scope,
    profile_config_hash,
)


DEFAULT_PROFILE = "tier_1"
DEFAULT_MATRIX = "baseline"
DEFAULT_RUN = "baseline"
DEFAULT_INPUT_ROOT = Path("data") / "feature_matrices"
DEFAULT_SPLIT_PLAN = Path("reports/wfa/split_plan.json")
DEFAULT_REPORTS_ROOT = Path("reports/wfa")
DEFAULT_MODELS_CONFIG = Path("configs/models.yaml")
NO_CALIBRATION_ID = "no_calibration"
PHASE_7A_STAGE = "phase_7a_linear_controls"
CLASSIFIER_COLLAPSE_STD_EPS = 1e-9
PREDICTION_COLUMNS = [
    "market",
    "year",
    "fold_id",
    "timestamp",
    "session_id",
    "session_segment_id",
    "split_group",
    "model_id",
    "model_family",
    "target_name",
    "prediction_type",
    "y_true",
    "y_pred_raw",
    "y_pred_calibrated",
    "p_long",
    "p_short",
    "p_flat",
    "p_fade_success",
    "p_trend_adverse_long_30m",
    "p_trend_favorable_long_30m",
    "p_trend_adverse_short_30m",
    "p_trend_favorable_short_30m",
    "p_trend_danger",
    "calibration_id",
    "model_config_hash",
    "feature_config_hash",
    "execution_open",
    "execution_close",
    "target_valid",
    "causal_valid",
    "close",
    "target_entry_ts",
    "target_exit_ts",
    "minutes_until_session_close",
]
PROBABILITY_COLUMNS = [
    "p_long",
    "p_short",
    "p_flat",
    "p_fade_success",
    "p_trend_adverse_long_30m",
    "p_trend_favorable_long_30m",
    "p_trend_adverse_short_30m",
    "p_trend_favorable_short_30m",
    "p_trend_danger",
]
TARGET_PROBABILITY_COLUMNS = {
    "target_fade_success_15m": "p_fade_success",
    "target_trend_adverse_long_30m": "p_trend_adverse_long_30m",
    "target_trend_favorable_long_30m": "p_trend_favorable_long_30m",
    "target_trend_adverse_short_30m": "p_trend_adverse_short_30m",
    "target_trend_favorable_short_30m": "p_trend_favorable_short_30m",
    "target_trend_danger_30m": "p_trend_danger",
}


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    stage: str
    family: str
    task: str
    target: str
    config_hash: str


@dataclass(frozen=True)
class FeatureSetSpec:
    feature_cols: list[str]
    config_path: Path
    config_hash: str
    manifest: dict[str, Any] | None = None


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hash_or_missing(path: Path) -> str:
    return _file_sha256(path) if path.exists() else "MISSING"


def _file_hash_map(paths: Iterable[Path]) -> dict[str, str]:
    return {_relative_path(path): _file_hash_or_missing(path) for path in paths}


def _is_stale_default_feature_root(path: Path) -> bool:
    normalized = path.as_posix().replace("\\", "/").rstrip("/")
    stale_root = "data/feature_matrices/baseline"
    return normalized == stale_root or normalized.endswith(f"/{stale_root}")


def _stale_prediction_output_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "stale_output_path_exists": False,
            "stale_output_path": None,
            "stale_output_file_hash": None,
            "stale_output_mtime_utc": None,
            "stale_output_row_count": None,
            "stale_output_split_groups": [],
        }

    info: dict[str, Any] = {
        "stale_output_path_exists": True,
        "stale_output_path": _relative_path(path),
        "stale_output_file_hash": _file_sha256(path),
        "stale_output_mtime_utc": datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
        "stale_output_row_count": None,
        "stale_output_split_groups": [],
    }
    try:
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(path)
        info["stale_output_row_count"] = int(parquet_file.metadata.num_rows)
        if "split_group" in parquet_file.schema.names:
            table = pq.read_table(path, columns=["split_group"])
            groups = table.column("split_group").to_pylist()
            info["stale_output_split_groups"] = sorted(
                {str(value) for value in groups if value is not None}
            )
    except Exception as exc:
        info["stale_output_read_error"] = str(exc)
    return info


def prediction_artifact_evidence_failures(manifest: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if int(manifest.get("failure_count") or 0) > 0:
        failures.append("manifest failure_count is nonzero")
    if int(manifest.get("prediction_count") or 0) <= 0:
        failures.append("manifest prediction_count is zero")
    output_hashes = manifest.get("output_file_hashes", {})
    if isinstance(output_hashes, Mapping) and any(value == "NOT_WRITTEN" for value in output_hashes.values()):
        failures.append("manifest output hash is NOT_WRITTEN")
    if manifest.get("stale_output_path_exists") is True:
        failures.append("stale prediction output exists from a previous run")
    return failures


def build_model_risk_gate(
    model_config: Mapping[str, Any],
    model_specs: list[ModelSpec],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    policy = model_config.get("policy", {})
    policy = policy if isinstance(policy, Mapping) else {}
    calibration = model_config.get("calibration", {})
    calibration = calibration if isinstance(calibration, Mapping) else {}
    dummy_fallback_count = sum(1 for item in diagnostics if item.get("dummy_fallback_used") is True)
    convergence_warning_count = sum(
        1
        for item in diagnostics
        if any("convergence" in str(warning).lower() for warning in item.get("warnings", []))
    )
    failures: list[str] = []
    if policy.get("hyperparameter_tuning_allowed_initially") is not False:
        failures.append("hyperparameter_tuning_allowed_initially must be false")
    if policy.get("random_splits_allowed") is not False:
        failures.append("random_splits_allowed must be false")
    if policy.get("final_holdout_tuning_allowed") is not False:
        failures.append("final_holdout_tuning_allowed must be false")
    if convergence_warning_count:
        failures.append("model convergence warnings must be zero")
    trust_blockers = [
        "feature-importance stability is registered for pre-promotion review and is not standalone trust evidence"
    ]
    return {
        "gate_name": "model_risk_gate",
        "status": "PASS_METADATA_READY" if not failures else "FAIL",
        "model_risk_metadata_ready": not failures,
        "model_trust_ready": False,
        "model_trust_blockers": trust_blockers if not failures else [*failures, *trust_blockers],
        "failure_count": len(failures),
        "failures": failures,
        "hyperparameter_budget": {
            "hyperparameter_tuning_allowed_initially": policy.get(
                "hyperparameter_tuning_allowed_initially"
            ),
            "budget": "fixed Phase 7A baseline controls only; no search in this runner",
        },
        "seed_policy": {
            "random_splits_allowed": policy.get("random_splits_allowed"),
            "determinism_source": "chronological split_plan plus deterministic sklearn baseline estimators",
        },
        "calibration": {
            "calibration_id": NO_CALIBRATION_ID,
            "test_fold_fit_allowed": calibration.get("test_fold_fit_allowed", False),
            "final_holdout_fit_allowed": calibration.get("final_holdout_fit_allowed", False),
            "method": "no calibration fit in Phase 6; scores carry no_calibration marker",
        },
        "class_imbalance_handling": {
            "class_counts_recorded_per_fold": True,
            "dummy_fallback_count": dummy_fallback_count,
            "dummy_fallback_policy": "diagnostic only; class-prior-only predictions fail promotion review",
        },
        "regularization": {
            "ridge_regression": "Ridge(alpha=1.0)",
            "logistic_regression": "LogisticRegression(max_iter=1000)",
        },
        "feature_importance_stability": {
            "status": "registered_for_pre_promotion_review",
            "evidence": "fold diagnostics and fixed feature set recorded; promotion requires stability review",
        },
        "model_families": sorted({spec.family for spec in model_specs}),
        "model_ids": [spec.model_id for spec in model_specs],
    }


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _resolved_profile_config(profile_config: Path | None, models_config: Path) -> Path:
    if profile_config is not None:
        return profile_config
    sibling = models_config.parent / DEFAULT_PROFILE_CONFIG.name
    return sibling if sibling.exists() else DEFAULT_PROFILE_CONFIG


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return sorted(str(item) for item in value)


def _int_list(value: object) -> list[int] | None:
    if not isinstance(value, list):
        return None
    try:
        return sorted(int(item) for item in value)
    except (TypeError, ValueError):
        return None


def _split_scope_context(
    *,
    plan: ProfileScope,
    split_profile: object,
    split_resolved_profile: object,
    expected_markets: list[str],
    expected_years: list[int],
    actual_markets: object,
    actual_years: object,
    reason: str,
) -> str:
    return (
        "split plan scope/provenance mismatch: "
        f"reason={reason}; "
        f"requested_profile={plan.requested_profile!r}; "
        f"requested_resolved_profile={plan.resolved_profile!r}; "
        f"split_plan_profile={split_profile!r}; "
        f"split_plan_resolved_profile={split_resolved_profile!r}; "
        f"expected_markets={expected_markets}; expected_years={expected_years}; "
        f"actual_markets={actual_markets}; actual_years={actual_years}"
    )


def _validate_split_plan_scope(
    *,
    split_manifest: Mapping[str, Any],
    plan: ProfileScope,
    profile_config: Path,
    models_config: Path,
) -> None:
    split_profile = split_manifest.get("profile")
    split_resolved_profile = split_manifest.get("resolved_profile")
    expected_markets = sorted(plan.markets)
    expected_years = sorted(plan.years)
    actual_markets = _string_list(split_manifest.get("markets"))
    actual_years = _int_list(split_manifest.get("years"))
    failures: list[str] = []

    def add(reason: str) -> None:
        failures.append(
            _split_scope_context(
                plan=plan,
                split_profile=split_profile,
                split_resolved_profile=split_resolved_profile,
                expected_markets=expected_markets,
                expected_years=expected_years,
                actual_markets=actual_markets if actual_markets is not None else split_manifest.get("markets"),
                actual_years=actual_years if actual_years is not None else split_manifest.get("years"),
                reason=reason,
            )
        )

    if split_profile != plan.requested_profile:
        add("profile mismatch")
    if split_resolved_profile != plan.resolved_profile:
        add("resolved_profile mismatch")
    if actual_markets is None:
        add("markets missing or invalid")
    elif actual_markets != expected_markets:
        add("markets mismatch")
    if actual_years is None:
        add("years missing or invalid")
    elif actual_years != expected_years:
        add("years mismatch")

    required_provenance = ("config_hash", "script_hash", "input_file_hashes")
    for field in required_provenance:
        if field not in split_manifest:
            add(f"missing provenance field {field}")
    expected_config_hash = profile_config_hash([profile_config, models_config])
    if split_manifest.get("config_hash") not in (None, expected_config_hash):
        add("config_hash mismatch")

    if failures:
        raise SystemExit("; ".join(failures))


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _utc(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def load_feature_cols(input_root: Path, feature_cols_path: Path | None = None) -> tuple[list[str], Path]:
    path = feature_cols_path or (input_root / "feature_cols.json")
    if not path.exists():
        raise SystemExit(f"feature column registry missing: {_relative_path(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise SystemExit(f"invalid feature column registry: {_relative_path(path)}")
    forbidden = forbidden_feature_columns(payload)
    if forbidden:
        raise SystemExit(f"feature column registry contains forbidden columns: {forbidden}")
    return list(payload), path


def _validate_feature_list(features: object, context: str) -> list[str]:
    if not isinstance(features, list) or not all(isinstance(item, str) for item in features):
        raise SystemExit(f"invalid feature column registry: {context}")
    if not features:
        raise SystemExit(f"feature column registry is empty: {context}")
    duplicates = sorted({item for item in features if features.count(item) > 1})
    if duplicates:
        raise SystemExit(f"feature column registry contains duplicates: {duplicates}")
    forbidden = forbidden_feature_columns(features)
    if forbidden:
        raise SystemExit(f"feature column registry contains forbidden columns: {forbidden}")
    return list(features)


def _resolve_manifest_relative_path(manifest_path: Path, raw_path: object) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return manifest_path.parent / path


def load_feature_set(feature_set_path: Path) -> FeatureSetSpec:
    if not feature_set_path.exists():
        raise SystemExit(f"feature-set manifest missing: {_relative_path(feature_set_path)}")
    payload = _read_json(feature_set_path)
    feature_set_id = payload.get("feature_set_id")
    if not isinstance(feature_set_id, str) or not feature_set_id:
        raise SystemExit(f"feature-set manifest missing feature_set_id: {_relative_path(feature_set_path)}")
    if payload.get("status") != "FROZEN":
        raise SystemExit(f"feature-set {feature_set_id!r} is not FROZEN")
    if payload.get("allowed_for_wfa") is not True:
        raise SystemExit(f"feature-set {feature_set_id!r} is not allowed for WFA")

    features_source: Path | None = None
    if "features" in payload:
        feature_cols = _validate_feature_list(
            payload.get("features"),
            f"feature-set {feature_set_id!r}",
        )
    elif "features_path" in payload:
        features_source = _resolve_manifest_relative_path(feature_set_path, payload["features_path"])
        if not features_source.exists():
            raise SystemExit(f"feature-set features file missing: {_relative_path(features_source)}")
        feature_cols = _validate_feature_list(
            [
                line.strip()
                for line in features_source.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ],
            _relative_path(features_source),
        )
    else:
        raise SystemExit(f"feature-set {feature_set_id!r} has no features or features_path")

    expected_count = payload.get("feature_count")
    if expected_count is not None and int(expected_count) != len(feature_cols):
        raise SystemExit(
            f"feature-set {feature_set_id!r} feature_count mismatch: "
            f"manifest={expected_count} actual={len(feature_cols)}"
        )

    registry_path: Path | None = None
    if "feature_cols_path" in payload:
        registry_path = _resolve_manifest_relative_path(feature_set_path, payload["feature_cols_path"])
        registry_features, _ = load_feature_cols(registry_path.parent, registry_path)
        if registry_features != feature_cols:
            raise SystemExit(
                f"feature-set {feature_set_id!r} does not match feature_cols_path "
                f"{_relative_path(registry_path)}"
            )

    manifest = {
        "feature_set_id": feature_set_id,
        "status": payload.get("status"),
        "allowed_for_wfa": payload.get("allowed_for_wfa"),
        "feature_count": len(feature_cols),
        "feature_set_path": _relative_path(feature_set_path),
        "features_path": _relative_path(features_source) if features_source is not None else None,
        "feature_cols_path": _relative_path(registry_path) if registry_path is not None else None,
    }
    return FeatureSetSpec(
        feature_cols=feature_cols,
        config_path=feature_set_path,
        config_hash=_file_hash_or_missing(feature_set_path),
        manifest=manifest,
    )


def resolve_feature_set(
    input_root: Path,
    feature_cols_path: Path | None = None,
    feature_set_path: Path | None = None,
) -> FeatureSetSpec:
    if feature_cols_path is not None and feature_set_path is not None:
        raise SystemExit("provide either --feature-cols or --feature-set, not both")
    if feature_set_path is not None:
        return load_feature_set(feature_set_path)
    feature_cols, resolved_path = load_feature_cols(input_root, feature_cols_path)
    return FeatureSetSpec(
        feature_cols=feature_cols,
        config_path=resolved_path,
        config_hash=_file_hash_or_missing(resolved_path),
    )


def load_model_specs(models_config: Path) -> tuple[list[ModelSpec], dict[str, Any]]:
    config = _read_yaml(models_config)
    policy = config.get("policy", {})
    if not isinstance(policy, Mapping):
        raise SystemExit("models policy mapping missing")
    if policy.get("random_splits_allowed") is not False:
        raise SystemExit("random train/test splits must be disabled")
    if policy.get("hyperparameter_tuning_allowed_initially") is not False:
        raise SystemExit("initial hyperparameter tuning must be disabled")
    if policy.get("final_holdout_tuning_allowed") is not False:
        raise SystemExit("final holdout tuning must be disabled")

    models = config.get("models", {})
    if not isinstance(models, Mapping):
        raise SystemExit("models mapping missing")
    specs: list[ModelSpec] = []
    for model_id, raw_model in models.items():
        if not isinstance(model_id, str) or not isinstance(raw_model, Mapping):
            continue
        if raw_model.get("enabled") is not True:
            continue
        if raw_model.get("requires_optional_dependency") is True:
            continue
        if raw_model.get("stage") != PHASE_7A_STAGE:
            continue
        family = str(raw_model.get("family", ""))
        task = str(raw_model.get("task", ""))
        if family not in {"ridge_regression", "logistic_regression"}:
            raise SystemExit(f"unsupported initial model family for {model_id}: {family}")
        if task not in {"regression", "classification"}:
            raise SystemExit(f"unsupported task for {model_id}: {task}")
        target = str(raw_model.get("target", ""))
        if not target:
            raise SystemExit(f"missing target for {model_id}")
        specs.append(
            ModelSpec(
                model_id=model_id,
                stage=str(raw_model["stage"]),
                family=family,
                task=task,
                target=target,
                config_hash=_stable_hash({"model_id": model_id, **dict(raw_model)}),
            )
        )
    if not specs:
        raise SystemExit("no enabled Phase 7A baseline models found")
    return specs, config


def _required_source_columns(feature_cols: list[str], model_specs: list[ModelSpec]) -> list[str]:
    columns = set(feature_cols)
    columns.update(
        {
            "ts",
            "market",
            "year",
            "session_id",
            "session_segment_id",
            "causal_valid",
            "target_valid",
            "feature_input_valid",
            "training_row_valid",
            "close",
            "target_entry_ts",
            "target_exit_ts",
            "target_entry_price",
            "target_exit_price",
            "minutes_until_session_close",
        }
    )
    for spec in model_specs:
        columns.add(spec.target)
    return sorted(columns)


def _read_schema(path: Path) -> set[str]:
    import pyarrow.parquet as pq

    return set(pq.read_schema(path).names)


def _load_market_frame(
    market: str,
    years: Iterable[int],
    input_root: Path,
    columns: list[str],
) -> tuple[pd.DataFrame | None, list[str], list[Path]]:
    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    paths: list[Path] = []
    for year in sorted(set(int(item) for item in years)):
        path = input_root / market / f"{year}.parquet"
        paths.append(path)
        if not path.exists():
            failures.append(f"missing feature matrix: {_relative_path(path)}")
            continue
        available = _read_schema(path)
        missing = [column for column in columns if column not in available]
        required_missing = [
            column
            for column in missing
            if column in {"ts", "market", "year", "session_segment_id", "target_valid", "causal_valid"}
            or column.startswith("target_")
        ]
        if required_missing:
            failures.append(
                f"feature matrix missing required columns {required_missing}: {_relative_path(path)}"
            )
            continue
        read_columns = [column for column in columns if column in available]
        frame = pd.read_parquet(path, columns=read_columns)
        for column in missing:
            frame[column] = np.nan
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
        frames.append(frame)
    if not frames:
        return None, failures, paths
    out = pd.concat(frames, ignore_index=True).sort_values("ts", kind="mergesort")
    return out.reset_index(drop=True), failures, paths


def _valid_bool(df: pd.DataFrame, column: str, default: bool) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=bool)
    return df[column].fillna(default).astype(bool)


def _parse_csv_filter(value: str | None) -> set[str] | None:
    if value is None:
        return None
    selected = {item.strip() for item in value.split(",") if item.strip()}
    return selected or None


def _target_series(df: pd.DataFrame, spec: ModelSpec) -> pd.Series:
    if spec.target not in df.columns:
        return pd.Series(np.nan, index=df.index)
    series = df[spec.target]
    if spec.task == "classification":
        if series.dtype == bool:
            return series.astype(int)
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def _build_estimator(spec: ModelSpec, y_train: pd.Series) -> tuple[Any, str]:
    if spec.task == "regression":
        return (
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                    ("scaler", StandardScaler()),
                    ("model", Ridge(alpha=1.0)),
                ]
            ),
            "ridge_regression",
        )

    unique = pd.Series(y_train).dropna().unique()
    if len(unique) < 2:
        return DummyClassifier(strategy="prior"), "dummy_class_prior"
    return (
        Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000)),
            ]
        ),
        "logistic_regression",
    )


def _positive_probability(classes: np.ndarray, probabilities: np.ndarray, positive: object) -> np.ndarray:
    out = np.full(len(probabilities), np.nan)
    for idx, value in enumerate(classes):
        if value == positive:
            out = probabilities[:, idx]
            break
    return out


def _classification_predictions(
    estimator: Any,
    spec: ModelSpec,
    x_test: pd.DataFrame,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    probabilities = estimator.predict_proba(x_test)
    classes = np.asarray(estimator.classes_)
    p_long = _positive_probability(classes, probabilities, 1)
    p_short = _positive_probability(classes, probabilities, -1)
    p_flat = _positive_probability(classes, probabilities, 0)
    p_true = _positive_probability(classes, probabilities, 1)

    columns = {column: np.full(len(x_test), np.nan) for column in PROBABILITY_COLUMNS}
    if spec.target == "target_sign_with_deadzone":
        columns["p_long"] = p_long
        columns["p_short"] = p_short
        columns["p_flat"] = p_flat
        raw = np.nan_to_num(p_long, nan=0.0) - np.nan_to_num(p_short, nan=0.0)
    elif spec.target in TARGET_PROBABILITY_COLUMNS:
        columns[TARGET_PROBABILITY_COLUMNS[spec.target]] = p_true
        raw = p_true
    else:
        raw = p_true
    return raw, columns


def _finite_std(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return 0.0
    return float(np.std(finite))


def classifier_collapse_failure(
    *,
    spec: ModelSpec,
    actual_estimator: str,
    raw_pred: np.ndarray,
    probability_cols: dict[str, np.ndarray],
) -> str | None:
    if spec.task != "classification" or actual_estimator == "dummy_class_prior":
        return None
    relevant = raw_pred
    if spec.target == "target_sign_with_deadzone":
        relevant = np.nan_to_num(probability_cols["p_long"], nan=0.0) - np.nan_to_num(
            probability_cols["p_short"], nan=0.0
        )
    elif spec.target in TARGET_PROBABILITY_COLUMNS:
        relevant = probability_cols[TARGET_PROBABILITY_COLUMNS[spec.target]]
    if _finite_std(np.asarray(relevant, dtype=float)) <= CLASSIFIER_COLLAPSE_STD_EPS:
        return f"{spec.model_id}: classifier probabilities collapsed to near-constant class-prior values"
    return None


def _prediction_frame(
    test: pd.DataFrame,
    spec: ModelSpec,
    fold: Mapping[str, Any],
    y_true: pd.Series,
    raw_pred: np.ndarray,
    probability_cols: dict[str, np.ndarray] | None,
    feature_config_hash: str,
) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "market": test["market"].astype(str).to_numpy(),
            "year": pd.to_numeric(test["year"], errors="coerce").astype("Int64").to_numpy(),
            "fold_id": str(fold["fold_id"]),
            "timestamp": test["ts"].to_numpy(),
            "session_id": test.get("session_id", pd.Series(pd.NA, index=test.index)).to_numpy(),
            "session_segment_id": test["session_segment_id"].astype(str).to_numpy(),
            "split_group": str(fold.get("split_group", "")),
            "model_id": spec.model_id,
            "model_family": spec.family,
            "target_name": spec.target,
            "prediction_type": "regression" if spec.task == "regression" else "classification_probability",
            "y_true": y_true.to_numpy(),
            "y_pred_raw": raw_pred,
            "y_pred_calibrated": raw_pred,
            "calibration_id": NO_CALIBRATION_ID,
            "model_config_hash": spec.config_hash,
            "feature_config_hash": feature_config_hash,
            "execution_open": pd.to_numeric(test["target_entry_price"], errors="coerce").to_numpy(),
            "execution_close": pd.to_numeric(test["target_exit_price"], errors="coerce").to_numpy(),
            "target_valid": _valid_bool(test, "target_valid", False).to_numpy(),
            "causal_valid": _valid_bool(test, "causal_valid", False).to_numpy(),
            "close": pd.to_numeric(test["close"], errors="coerce").to_numpy(),
            "target_entry_ts": pd.to_datetime(
                test["target_entry_ts"], utc=True, errors="coerce"
            ).to_numpy(),
            "target_exit_ts": pd.to_datetime(
                test["target_exit_ts"], utc=True, errors="coerce"
            ).to_numpy(),
            "minutes_until_session_close": pd.to_numeric(
                test["minutes_until_session_close"], errors="coerce"
            ).to_numpy(),
        }
    )
    for column in PROBABILITY_COLUMNS:
        if probability_cols is None:
            out[column] = np.nan
        else:
            out[column] = probability_cols[column]
    return out[PREDICTION_COLUMNS]


def _fold_masks(frame: pd.DataFrame, fold: Mapping[str, Any], y: pd.Series) -> tuple[pd.Series, pd.Series]:
    ts = frame["ts"]
    train_start = _utc(fold["train_start"])
    purged_train_end = _utc(fold["purged_train_end"])
    test_start = _utc(fold["test_start"])
    test_end = _utc(fold["test_end"])

    train_valid = (
        _valid_bool(frame, "training_row_valid", False)
        & _valid_bool(frame, "causal_valid", False)
        & _valid_bool(frame, "target_valid", False)
        & y.notna()
    )
    test_valid = (
        _valid_bool(frame, "feature_input_valid", True)
        & _valid_bool(frame, "causal_valid", False)
        & _valid_bool(frame, "target_valid", False)
        & y.notna()
    )
    train_mask = (ts >= train_start) & (ts <= purged_train_end) & train_valid
    test_mask = (ts >= test_start) & (ts <= test_end) & test_valid
    return train_mask, test_mask


def _validate_fold_fields(fold: Mapping[str, Any]) -> list[str]:
    fold_id = str(fold.get("fold_id", "<unknown>"))
    failures: list[str] = []
    required = [
        "market",
        "fold_id",
        "split_group",
        "selection_allowed",
        "train_start",
        "purged_train_end",
        "test_start",
        "test_end",
    ]
    missing = [field for field in required if field not in fold]
    if missing:
        if "selection_allowed" in missing:
            failures.append(f"{fold_id}: missing selection_allowed")
        failures.append(f"{fold_id}: missing required fold fields: {missing}")
        return failures
    if "is_final_holdout" not in fold and "final_holdout" not in fold:
        failures.append(f"{fold_id}: missing final_holdout flag")
    if not str(fold.get("market", "")).strip():
        failures.append(f"{fold_id}: market is empty")
    split_group = str(fold.get("split_group", ""))
    if split_group not in {"research", "restricted", "forward", "final_holdout"}:
        failures.append(f"{fold_id}: invalid split_group {split_group!r}")
    if not isinstance(fold.get("selection_allowed"), bool):
        failures.append(f"{fold_id}: selection_allowed must be boolean")

    final_holdout = bool(fold.get("is_final_holdout", fold.get("final_holdout", False)))
    if split_group == "final_holdout" and not final_holdout:
        failures.append(f"{fold_id}: final_holdout split must have final_holdout flag true")
    if split_group != "final_holdout" and final_holdout:
        failures.append(f"{fold_id}: non-final split cannot have final_holdout flag true")

    try:
        train_start = _utc(fold["train_start"])
        purged_train_end = _utc(fold["purged_train_end"])
        test_start = _utc(fold["test_start"])
        test_end = _utc(fold["test_end"])
    except Exception as exc:
        failures.append(f"{fold_id}: invalid fold timestamp fields: {exc}")
        return failures
    if train_start > purged_train_end:
        failures.append(f"{fold_id}: train_start after purged_train_end")
    if purged_train_end >= test_start:
        failures.append(f"{fold_id}: purged_train_end must be before test_start")
    if test_start > test_end:
        failures.append(f"{fold_id}: test_start after test_end")
    return failures


def _fold_test_years(fold: Mapping[str, Any]) -> list[int]:
    test_start = _utc(fold["test_start"])
    test_end = _utc(fold["test_end"])
    return list(range(int(test_start.year), int(test_end.year) + 1))


def run_wfa(
    *,
    profile: str,
    matrix: str,
    run: str,
    input_root: Path,
    split_plan: Path,
    predictions_root: Path | None,
    reports_root: Path,
    models_config: Path,
    profile_config: Path | None = None,
    feature_cols_path: Path | None = None,
    feature_set_path: Path | None = None,
    max_folds: int | None = None,
    markets: set[str] | None = None,
    fold_shard_count: int | None = None,
    fold_shard_index: int | None = None,
    data_audit_universe_json: Path | None = None,
    write_predictions: bool = False,
) -> dict[str, Any]:
    if matrix != "baseline":
        raise SystemExit("only baseline matrix is supported in the initial WFA runner")
    if write_predictions and predictions_root is None:
        raise SystemExit("prediction writes require an explicit predictions_root")
    if not write_predictions and _is_stale_default_feature_root(input_root):
        raise SystemExit(
            "report-only/no-predictions WFA requires an explicit non-stale feature input root; "
            "refused data/feature_matrices/baseline"
        )
    if (fold_shard_count is None) != (fold_shard_index is None):
        raise SystemExit("--fold-shard-count and --fold-shard-index must be provided together")
    if fold_shard_count is not None and fold_shard_index is not None:
        if fold_shard_count <= 0:
            raise SystemExit("--fold-shard-count must be positive")
        if fold_shard_index < 1 or fold_shard_index > fold_shard_count:
            raise SystemExit("--fold-shard-index must be between 1 and --fold-shard-count")
    resolved_profile_config = _resolved_profile_config(profile_config, models_config)
    profile_scope = load_profile_scope(profile, resolved_profile_config)
    if (
        feature_set_path is None
        and (
            profile_scope.requested_profile == "tier_1"
            or profile_scope.resolved_profile == "tier_1_research"
        )
    ):
        raise SystemExit(
            "Tier 1 WFA execution requires --feature-set with a FROZEN allowed_for_wfa manifest"
        )
    feature_set = resolve_feature_set(input_root, feature_cols_path, feature_set_path)
    feature_cols = feature_set.feature_cols
    resolved_feature_config_path = feature_set.config_path
    model_specs, model_config = load_model_specs(models_config)
    split_manifest = _read_json(split_plan)
    _validate_split_plan_scope(
        split_manifest=split_manifest,
        plan=profile_scope,
        profile_config=resolved_profile_config,
        models_config=models_config,
    )
    if (
        data_audit_universe_json is None
        and (
            profile_scope.requested_profile == "tier_1"
            or profile_scope.resolved_profile == "tier_1_research"
        )
    ):
        raise SystemExit("Tier 1 WFA execution requires --data-audit-universe-json")
    data_audit_universe = (
        load_data_audit_universe(data_audit_universe_json)
        if data_audit_universe_json is not None
        else None
    )
    data_audit_evidence = (
        data_audit_universe.evidence() if data_audit_universe is not None else None
    )
    folds = split_manifest.get("folds", [])
    if not isinstance(folds, list) or not folds:
        raise SystemExit(f"split plan has no folds: {_relative_path(split_plan)}")
    failures: list[str] = []
    data_audit_plan_failure: str | None = None
    if data_audit_universe is not None and not data_audit_evidence_matches(
        split_manifest.get("data_audit_universe"),
        data_audit_universe,
    ):
        data_audit_plan_failure = "split plan missing or stale data-audit universe evidence"
        failures.append(data_audit_plan_failure)
    selectable_folds: list[Mapping[str, Any]] = []
    skipped_folds: list[dict[str, Any]] = []
    for fold in folds:
        if not isinstance(fold, Mapping):
            failures.append("invalid fold entry")
            continue
        fold_failures = _validate_fold_fields(fold)
        if fold_failures:
            failures.extend(fold_failures)
            continue
        split_group = str(fold.get("split_group", ""))
        if fold.get("selection_allowed") is True and split_group == "research":
            if data_audit_plan_failure is not None:
                skipped_folds.append(
                    {
                        "fold_id": str(fold.get("fold_id", "<unknown>")),
                        "market": str(fold.get("market", "")),
                        "split_group": split_group,
                        "reason": data_audit_plan_failure,
                    }
                )
                continue
            if data_audit_universe is not None:
                fold_guard_failures = [
                    data_audit_universe.require_usable(
                        str(fold["market"]),
                        year,
                        context=f"WFA fold {fold.get('fold_id', '<unknown>')}",
                    )
                    for year in _fold_test_years(fold)
                ]
                fold_guard_failures = [failure for failure in fold_guard_failures if failure]
                if fold_guard_failures:
                    failures.extend(fold_guard_failures)
                    skipped_folds.append(
                        {
                            "fold_id": str(fold.get("fold_id", "<unknown>")),
                            "market": str(fold.get("market", "")),
                            "split_group": split_group,
                            "reason": "data_audit_universe_not_usable",
                        }
                    )
                    continue
            selectable_folds.append(fold)
        elif fold.get("selection_allowed") is True:
            failures.append(
                f"{fold.get('fold_id', '<unknown>')}: non-research split_group {split_group!r} "
                "cannot be selection_allowed"
            )
            skipped_folds.append(
                {
                    "fold_id": str(fold.get("fold_id", "<unknown>")),
                    "market": str(fold.get("market", "")),
                    "split_group": split_group,
                    "reason": "selection_allowed true on non-research split",
                }
            )
        else:
            skipped_folds.append(
                {
                    "fold_id": str(fold.get("fold_id", "<unknown>")),
                    "market": str(fold.get("market", "")),
                    "split_group": split_group,
                    "reason": "selection_allowed is false",
                }
            )
    if not selectable_folds:
        failures.append("no selectable research folds in split plan")
    unfiltered_selectable_count = len(selectable_folds)
    if markets is not None:
        selectable_folds = [fold for fold in selectable_folds if str(fold.get("market")) in markets]
    if fold_shard_count is not None and fold_shard_index is not None:
        selectable_folds = [
            fold
            for index, fold in enumerate(selectable_folds)
            if index % fold_shard_count == fold_shard_index - 1
        ]
    if (markets is not None or fold_shard_count is not None) and not selectable_folds:
        failures.append("no selectable research folds after explicit WFA filters")
    manifest_markets = split_manifest.get("markets", [])
    if selectable_folds and isinstance(manifest_markets, list) and markets is None:
        selected_markets = {str(fold.get("market")) for fold in selectable_folds}
        missing_markets = sorted(str(market) for market in manifest_markets if str(market) not in selected_markets)
        if missing_markets:
            failures.append(f"selectable research folds missing for markets: {missing_markets}")
    if max_folds is not None:
        selectable_folds = selectable_folds[:max_folds]

    skipped_years_by_market: dict[str, set[int]] = {}
    skipped_inputs = split_manifest.get("skipped_inputs", [])
    if isinstance(skipped_inputs, list):
        for item in skipped_inputs:
            if not isinstance(item, Mapping):
                continue
            try:
                skipped_years_by_market.setdefault(str(item["market"]), set()).add(int(item["year"]))
            except (KeyError, TypeError, ValueError):
                continue
    manifest_years = [int(year) for year in split_manifest["years"]]
    years_by_market: dict[str, set[int]] = {}
    for fold in selectable_folds:
        market = str(fold["market"])
        years_by_market.setdefault(market, set()).update(
            year for year in manifest_years if year not in skipped_years_by_market.get(market, set())
        )

    source_columns = _required_source_columns(feature_cols, model_specs)
    frames: dict[str, pd.DataFrame] = {}
    input_paths: list[Path] = [split_plan, resolved_feature_config_path, models_config]
    for market, years in years_by_market.items():
        frame, market_failures, paths = _load_market_frame(market, years, input_root, source_columns)
        input_paths.extend(paths)
        failures.extend(market_failures)
        if frame is not None:
            frames[market] = frame

    predictions: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []
    for fold in selectable_folds:
        market = str(fold["market"])
        frame = frames.get(market)
        if frame is None:
            continue
        for spec in model_specs:
            target = _target_series(frame, spec)
            train_mask, test_mask = _fold_masks(frame, fold, target)
            train = frame.loc[train_mask]
            test = frame.loc[test_mask]
            detail: dict[str, Any] = {
                "fold_id": str(fold["fold_id"]),
                "market": market,
                "split_group": str(fold.get("split_group", "")),
                "model_id": spec.model_id,
                "model_family": spec.family,
                "target_name": spec.target,
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "fit_ts_min": train["ts"].min().isoformat() if not train.empty else None,
                "fit_ts_max": train["ts"].max().isoformat() if not train.empty else None,
                "score_ts_min": test["ts"].min().isoformat() if not test.empty else None,
                "score_ts_max": test["ts"].max().isoformat() if not test.empty else None,
                "fit_estimator": None,
                "status": "PASS",
                "warnings": [],
            }
            if train.empty or test.empty:
                detail["status"] = "SKIP"
                detail["warnings"].append("empty train or test rows")
                diagnostics.append(detail)
                continue
            if train["ts"].max() >= test["ts"].min():
                detail["status"] = "FAIL"
                failures.append(f"{detail['fold_id']} {spec.model_id}: train/test timestamp overlap")
                diagnostics.append(detail)
                continue

            x_train = train[feature_cols]
            x_test = test[feature_cols]
            y_train = _target_series(train, spec)
            y_test = _target_series(test, spec)
            y_train_non_null = pd.Series(y_train).dropna()
            detail["y_train_unique"] = int(y_train_non_null.nunique())
            if spec.task == "classification":
                detail["y_train_class_counts"] = {
                    str(key): int(value)
                    for key, value in y_train_non_null.value_counts().sort_index().items()
                }
            estimator, actual_estimator = _build_estimator(spec, y_train)
            detail["fit_estimator"] = actual_estimator
            detail["dummy_fallback_used"] = actual_estimator == "dummy_class_prior"
            with warnings.catch_warnings(record=True) as caught_warnings:
                warnings.simplefilter("always", ConvergenceWarning)
                estimator.fit(x_train, y_train)
            detail["warnings"].extend(str(item.message).splitlines()[0] for item in caught_warnings)
            if caught_warnings:
                detail["status"] = "FAIL"
                failures.append(
                    f"{detail['fold_id']} {spec.model_id}: estimator emitted convergence warning"
                )
                diagnostics.append(detail)
                continue
            detail["train_feature_means_sample"] = {
                column: float(pd.to_numeric(x_train[column], errors="coerce").mean())
                for column in feature_cols[:5]
            }

            if spec.task == "regression":
                raw_pred = estimator.predict(x_test)
                probability_cols = None
                detail["prediction_std"] = _finite_std(np.asarray(raw_pred, dtype=float))
            else:
                raw_pred, probability_cols = _classification_predictions(estimator, spec, x_test)
                collapse_failure = classifier_collapse_failure(
                    spec=spec,
                    actual_estimator=actual_estimator,
                    raw_pred=np.asarray(raw_pred, dtype=float),
                    probability_cols=probability_cols,
                )
                detail["prediction_std"] = _finite_std(np.asarray(raw_pred, dtype=float))
                detail["probability_std_by_column"] = {
                    column: _finite_std(np.asarray(values, dtype=float))
                    for column, values in probability_cols.items()
                }
                if collapse_failure is not None:
                    detail["status"] = "FAIL"
                    detail["warnings"].append(collapse_failure)
                    failures.append(f"{detail['fold_id']} {collapse_failure}")
                    diagnostics.append(detail)
                    continue
            predictions.append(
                _prediction_frame(
                    test,
                    spec,
                    fold,
                    y_test,
                    np.asarray(raw_pred, dtype=float),
                    probability_cols,
                    feature_set.config_hash,
                )
            )
            detail["prediction_rows"] = int(len(test))
            diagnostics.append(detail)

    output_path = (
        predictions_root / run / "oos_predictions.parquet"
        if predictions_root is not None
        else None
    )
    prediction_count = 0
    duplicate_count = 0
    prediction_markets: list[str] = []
    prediction_years: list[int] = []
    prediction_artifact_written = False
    if predictions:
        output = pd.concat(predictions, ignore_index=True)
        duplicate_count = int(
            output.duplicated(
                subset=["market", "timestamp", "fold_id", "model_id", "target_name"]
            ).sum()
        )
        if duplicate_count:
            failures.append(f"duplicate prediction rows: {duplicate_count}")
        prediction_markets = sorted(output["market"].dropna().astype(str).unique().tolist())
        prediction_years = sorted(int(year) for year in output["year"].dropna().unique())
        prediction_count = int(len(output))
        if write_predictions:
            if output_path is None:
                raise SystemExit("prediction writes require an explicit predictions_root")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = output_path.with_name(f"{output_path.name}.tmp")
            output.to_parquet(tmp_path, index=False)
            tmp_path.replace(output_path)
            prediction_artifact_written = True
    else:
        failures.append("no prediction rows generated")
    output_hashes = {}
    if write_predictions:
        if output_path is None:
            raise SystemExit("prediction writes require an explicit predictions_root")
        output_hashes = (
            _file_hash_map([output_path])
            if prediction_artifact_written
            else {_relative_path(output_path): "NOT_WRITTEN"}
        )
    stale_output = (
        _stale_prediction_output_info(output_path)
        if write_predictions and not prediction_artifact_written and output_path is not None
        else {
        "stale_output_path_exists": False,
        "stale_output_path": None,
        "stale_output_file_hash": None,
        "stale_output_mtime_utc": None,
        "stale_output_row_count": None,
        "stale_output_split_groups": [],
        }
    )
    if stale_output["stale_output_path_exists"]:
        failures.append(
            f"stale prediction output exists from a previous run: {stale_output['stale_output_path']}"
        )

    model_risk_gate = build_model_risk_gate(model_config, model_specs, diagnostics)
    failures.extend(str(item) for item in model_risk_gate["failures"])

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "profile": profile,
        "resolved_profile": profile_scope.resolved_profile,
        "matrix": matrix,
        "run": run,
        "markets": profile_scope.markets,
        "years": profile_scope.years,
        "models": [spec.__dict__ for spec in model_specs],
        "feature_count": len(feature_cols),
        "feature_set": feature_set.manifest,
        "model_risk_gate": model_risk_gate,
        "fold_count": len(selectable_folds),
        "unfiltered_selectable_fold_count": unfiltered_selectable_count,
        "fold_selection": {
            "markets": sorted(markets) if markets is not None else None,
            "fold_shard_count": fold_shard_count,
            "fold_shard_index": fold_shard_index,
            "max_folds": max_folds,
        },
        "data_audit_universe": data_audit_evidence,
        "skipped_fold_count": len(skipped_folds),
        "skipped_folds": skipped_folds,
        "prediction_count": prediction_count,
        "prediction_markets": prediction_markets,
        "prediction_years": prediction_years,
        "duplicate_prediction_count": duplicate_count,
        "prediction_writes_enabled": write_predictions,
        "prediction_artifact_written": prediction_artifact_written,
        "prediction_artifact_write_skipped": not write_predictions,
        "warning_count": sum(len(item["warnings"]) for item in diagnostics),
        "failure_count": len(failures),
        "failures": failures,
        "diagnostics": diagnostics,
        **stale_output,
    }
    manifest = {
        **{key: report[key] for key in ("generated_at", "git_commit", "script_path", "script_hash")},
        "profile": profile,
        "resolved_profile": profile_scope.resolved_profile,
        "matrix": matrix,
        "run": run,
        "markets": profile_scope.markets,
        "years": profile_scope.years,
        "model_config_hash": _stable_hash(model_config),
        "feature_config_hash": feature_set.config_hash,
        "feature_set": feature_set.manifest,
        "profile_config_path": _relative_path(resolved_profile_config),
        "profile_config_hash": _file_hash_or_missing(resolved_profile_config),
        "split_plan_path": _relative_path(split_plan),
        "split_plan_hash": _file_hash_or_missing(split_plan),
        "split_plan_profile": split_manifest.get("profile"),
        "split_plan_resolved_profile": split_manifest.get("resolved_profile"),
        "split_plan_config_hash": split_manifest.get("config_hash"),
        "input_root": _relative_path(input_root),
        "output_root": _relative_path(predictions_root) if write_predictions else None,
        "predictions_root": _relative_path(predictions_root) if write_predictions else None,
        "reports_root": _relative_path(reports_root),
        "prediction_path": _relative_path(output_path) if write_predictions else None,
        "input_file_hashes": _file_hash_map(input_paths),
        "output_file_hashes": output_hashes,
        "required_columns": PREDICTION_COLUMNS,
        "model_ids": [spec.model_id for spec in model_specs],
        "target_names": [spec.target for spec in model_specs],
        "feature_count": len(feature_cols),
        "model_risk_gate": model_risk_gate,
        "fold_count": len(selectable_folds),
        "unfiltered_selectable_fold_count": unfiltered_selectable_count,
        "fold_selection": {
            "markets": sorted(markets) if markets is not None else None,
            "fold_shard_count": fold_shard_count,
            "fold_shard_index": fold_shard_index,
            "max_folds": max_folds,
        },
        "data_audit_universe": data_audit_evidence,
        "skipped_fold_count": len(skipped_folds),
        "skipped_folds": skipped_folds,
        "prediction_count": prediction_count,
        "prediction_markets": prediction_markets,
        "prediction_years": prediction_years,
        "duplicate_prediction_count": duplicate_count,
        "prediction_writes_enabled": write_predictions,
        "prediction_artifact_written": prediction_artifact_written,
        "prediction_artifact_write_skipped": not write_predictions,
        "warning_count": report["warning_count"],
        "failure_count": len(failures),
        "failures": failures,
        **stale_output,
    }
    artifact_evidence_failures = prediction_artifact_evidence_failures(manifest)
    manifest["artifact_evidence_ready"] = not artifact_evidence_failures
    manifest["artifact_evidence_failures"] = artifact_evidence_failures
    report["artifact_evidence_ready"] = manifest["artifact_evidence_ready"]
    report["artifact_evidence_failures"] = artifact_evidence_failures
    _write_json(reports_root / f"{run}_wfa_report.json", report)
    _write_json(reports_root / f"{run}_predictions_manifest.json", manifest)
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--matrix", default=DEFAULT_MATRIX)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--input-root", default=None)
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--predictions-root", default=None)
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--feature-cols", default=None)
    parser.add_argument("--feature-set", default=None)
    parser.add_argument("--max-folds", type=int, default=None)
    parser.add_argument("--markets", default=None)
    parser.add_argument("--fold-shard-count", type=int, default=None)
    parser.add_argument("--fold-shard-index", type=int, default=None)
    parser.add_argument("--data-audit-universe-json", default=None)
    parser.add_argument(
        "--write-predictions",
        action="store_true",
        dest="write_predictions",
        help="Write OOS prediction parquet artifacts. Requires --predictions-root.",
    )
    parser.add_argument(
        "--no-predictions",
        action="store_false",
        dest="write_predictions",
        help="Run WFA diagnostics without writing OOS prediction parquet artifacts.",
    )
    parser.add_argument(
        "--report-only",
        action="store_false",
        dest="write_predictions",
        help="Alias for --no-predictions.",
    )
    parser.set_defaults(write_predictions=False)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.write_predictions and not args.predictions_root:
        parser.error("--predictions-root is required when --write-predictions is set")
    if not args.input_root:
        parser.error("--input-root is required; pass an explicit feature root")
    manifest = run_wfa(
        profile=args.profile,
        matrix=args.matrix,
        run=args.run,
        input_root=Path(args.input_root),
        split_plan=Path(args.split_plan),
        predictions_root=Path(args.predictions_root) if args.predictions_root else None,
        reports_root=Path(args.reports_root),
        models_config=Path(args.models_config),
        profile_config=Path(args.profile_config),
        feature_cols_path=Path(args.feature_cols) if args.feature_cols else None,
        feature_set_path=Path(args.feature_set) if args.feature_set else None,
        max_folds=args.max_folds,
        markets=_parse_csv_filter(args.markets),
        fold_shard_count=args.fold_shard_count,
        fold_shard_index=args.fold_shard_index,
        data_audit_universe_json=(
            Path(args.data_audit_universe_json) if args.data_audit_universe_json else None
        ),
        write_predictions=args.write_predictions,
    )
    status = "FAIL" if manifest["failure_count"] else "PASS"
    print(
        f"{status} WFA baseline: predictions={manifest['prediction_count']} "
        f"models={len(manifest['model_ids'])} folds={manifest['fold_count']} "
        f"failures={manifest['failure_count']}"
    )
    return 1 if manifest["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
