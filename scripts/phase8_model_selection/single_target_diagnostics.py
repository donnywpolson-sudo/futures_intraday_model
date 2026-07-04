#!/usr/bin/env python3
"""Diagnostic-only Phase 8 compatibility checks for a single prediction target."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.phase8_model_selection.evaluate_predictions import (
    NO_CALIBRATION_ID,
    PREDICTION_KEY_CANDIDATES,
    PREDICTION_REQUIRED_COLUMNS,
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _mean_float,
    _prediction_manifest_failures,
    _read_json,
    _read_yaml,
    _relative_path,
    _score_column_for_target,
    _std_float,
    _write_json,
    build_calibration_report,
    build_model_comparison,
)


DEFAULT_TARGET_NAME = "target_sign_with_deadzone"
DEFAULT_MIN_CLASS_RATE = 0.01
EXTRA_REQUIRED_COLUMNS = {
    "target_entry_ts",
    "target_exit_ts",
}
REQUIRED_COLUMNS = PREDICTION_REQUIRED_COLUMNS | EXTRA_REQUIRED_COLUMNS


def _output_paths(reports_root: Path, run: str) -> dict[str, Path]:
    return {
        "diagnostics": reports_root / f"{run}_single_target_diagnostics.json",
        "model_comparison": reports_root / f"{run}_single_target_model_comparison.csv",
    }


def _coverage(predictions: pd.DataFrame) -> dict[str, Any]:
    if predictions.empty:
        return {
            "row_count": 0,
            "markets": [],
            "years": [],
            "fold_ids": [],
            "model_ids": [],
            "target_names": [],
            "split_groups": [],
            "first_timestamp": None,
            "last_timestamp": None,
        }
    timestamps = pd.to_datetime(predictions["timestamp"], errors="coerce", utc=True)
    valid_timestamps = timestamps.dropna()
    return {
        "row_count": int(len(predictions)),
        "markets": sorted(predictions["market"].dropna().astype(str).unique().tolist()),
        "years": sorted(int(year) for year in predictions["year"].dropna().unique()),
        "fold_ids": sorted(predictions["fold_id"].dropna().astype(str).unique().tolist()),
        "model_ids": sorted(predictions["model_id"].dropna().astype(str).unique().tolist()),
        "target_names": sorted(predictions["target_name"].dropna().astype(str).unique().tolist()),
        "split_groups": sorted(predictions["split_group"].dropna().astype(str).unique().tolist()),
        "first_timestamp": valid_timestamps.min().isoformat() if not valid_timestamps.empty else None,
        "last_timestamp": valid_timestamps.max().isoformat() if not valid_timestamps.empty else None,
    }


def _class_balance(frame: pd.DataFrame, *, min_class_rate: float) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    if frame.empty or "y_true" not in frame.columns:
        return {
            "class_count": 0,
            "class_counts": {},
            "class_rates": {},
            "min_class_rate": min_class_rate,
        }, ["single-target diagnostics require y_true values"]

    y_true = pd.to_numeric(frame["y_true"], errors="coerce").dropna()
    counts = y_true.value_counts().sort_index()
    total = int(counts.sum())
    class_counts = {str(key): int(value) for key, value in counts.items()}
    class_rates = {
        str(key): float(value / total) if total else 0.0
        for key, value in counts.items()
    }
    if total <= 0:
        failures.append("single-target diagnostics require y_true values")
    if len(counts) < 2:
        failures.append("single-target diagnostics require at least two observed classes")
    elif min(class_rates.values()) < min_class_rate:
        failures.append(
            "single-target diagnostics class balance below minimum: "
            f"min_rate={min(class_rates.values())} threshold={min_class_rate}"
        )
    return {
        "class_count": int(len(counts)),
        "class_counts": class_counts,
        "class_rates": class_rates,
        "min_class_rate": min_class_rate,
    }, failures


def _score_summary(frame: pd.DataFrame, target_name: str) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    if frame.empty:
        return {
            "non_null_count": 0,
            "prediction_mean": None,
            "prediction_std": None,
            "prediction_min": None,
            "prediction_max": None,
        }, ["single-target diagnostics require prediction rows"]
    try:
        scores = _score_column_for_target(frame, target_name)
    except KeyError as exc:
        return {
            "non_null_count": 0,
            "prediction_mean": None,
            "prediction_std": None,
            "prediction_min": None,
            "prediction_max": None,
        }, [f"single-target diagnostics missing score column: {exc.args[0]}"]
    scores = pd.to_numeric(scores, errors="coerce")
    finite_scores = scores.dropna()
    prediction_std = _std_float(finite_scores)
    if finite_scores.empty:
        failures.append("single-target diagnostics require non-null prediction scores")
    elif prediction_std is None or prediction_std <= 0.0:
        failures.append("single-target diagnostics require nonconstant prediction scores")
    return {
        "non_null_count": int(len(finite_scores)),
        "prediction_mean": _mean_float(finite_scores),
        "prediction_std": prediction_std,
        "prediction_min": float(finite_scores.min()) if not finite_scores.empty else None,
        "prediction_max": float(finite_scores.max()) if not finite_scores.empty else None,
    }, failures


def _duplicate_prediction_count(frame: pd.DataFrame) -> tuple[int, list[str]]:
    key_cols = [
        column
        for column in [*PREDICTION_KEY_CANDIDATES, "target_name", "model_id"]
        if column in frame.columns
    ]
    if not key_cols or frame.empty:
        return 0, []
    duplicate_count = int(frame.duplicated(key_cols).sum())
    failures = [f"duplicate prediction keys: {duplicate_count}"] if duplicate_count else []
    return duplicate_count, failures


def evaluate_single_target_predictions(
    *,
    predictions_path: Path,
    predictions_manifest: Path,
    models_config: Path,
    reports_root: Path,
    run: str,
    target_name: str = DEFAULT_TARGET_NAME,
    min_class_rate: float = DEFAULT_MIN_CLASS_RATE,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    warnings: list[str] = []
    manifest_failures: list[str] = []
    required_column_failures: list[str] = []

    if not predictions_path.exists():
        predictions = pd.DataFrame()
        failures.append(f"prediction parquet missing: {_relative_path(predictions_path)}")
    else:
        predictions = pd.read_parquet(predictions_path)
        missing_columns = sorted(REQUIRED_COLUMNS - set(predictions.columns))
        if missing_columns:
            required_column_failures.append(
                f"prediction parquet missing required columns: {missing_columns}"
            )
            failures.extend(required_column_failures)

    manifest = _read_json(predictions_manifest)
    manifest_failures = _prediction_manifest_failures(
        manifest,
        predictions_path=predictions_path,
        predictions=predictions,
        run=run,
    )
    failures.extend(manifest_failures)

    models = _read_yaml(models_config)
    if not models_config.exists():
        failures.append(f"models config missing: {_relative_path(models_config)}")

    target_names = (
        sorted(predictions["target_name"].dropna().astype(str).unique().tolist())
        if "target_name" in predictions.columns
        else []
    )
    if len(target_names) != 1:
        failures.append(f"single-target diagnostics require exactly one target, found {target_names}")
    elif target_names[0] != target_name:
        failures.append(
            f"single-target diagnostics target mismatch: observed={target_names[0]!r} expected={target_name!r}"
        )

    target_frame = (
        predictions[predictions["target_name"].astype(str).eq(target_name)].copy()
        if "target_name" in predictions.columns
        else pd.DataFrame()
    )
    if "split_group" in target_frame.columns and target_frame["split_group"].astype(str).eq("final_holdout").any():
        failures.append("final_holdout predictions cannot be used for single-target diagnostics")

    duplicate_count, duplicate_failures = _duplicate_prediction_count(target_frame)
    failures.extend(duplicate_failures)
    class_balance, class_failures = _class_balance(target_frame, min_class_rate=min_class_rate)
    failures.extend(class_failures)
    score_summary, score_failures = _score_summary(target_frame, target_name)
    failures.extend(score_failures)

    comparison_ready = not required_column_failures and not target_frame.empty
    model_comparison = (
        build_model_comparison(target_frame) if comparison_ready else pd.DataFrame()
    )
    calibration_report = (
        build_calibration_report(target_frame, models) if comparison_ready else {}
    )
    output_paths = _output_paths(reports_root, run)
    reports_root.mkdir(parents=True, exist_ok=True)
    model_comparison.to_csv(output_paths["model_comparison"], index=False)

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "run": run,
        "target_name": target_name,
        "diagnostic_type": "single_target_phase8_compatibility",
        "diagnostic_only": True,
        "canonical_phase8_policy_applicable": False,
        "canonical_phase8_policy_reason": (
            "canonical Phase 8 policy evaluation requires expected-return, fade, and "
            "side-aware trend target prediction families; this adapter validates one target only"
        ),
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "promotion_allowed": False,
        "live_execution_ready": False,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "prediction_manifest_artifact_evidence_ready": not manifest_failures,
        "prediction_path": _relative_path(predictions_path),
        "prediction_manifest_path": _relative_path(predictions_manifest),
        "models_config": _relative_path(models_config),
        "output_root": _relative_path(reports_root),
        "input_file_hashes": _file_hash_map([predictions_path, predictions_manifest, models_config]),
        "coverage": _coverage(target_frame),
        "duplicate_prediction_count": duplicate_count,
        "class_balance": class_balance,
        "score_summary": score_summary,
        "model_comparison_row_count": int(len(model_comparison)),
        "diagnostics_path": _relative_path(output_paths["diagnostics"]),
        "model_comparison_path": _relative_path(output_paths["model_comparison"]),
        "model_comparison_output_path": _relative_path(output_paths["model_comparison"]),
        "model_comparison": model_comparison.to_dict(orient="records"),
        "calibration_report": calibration_report,
        "acceptance_scope": (
            "model-quality and artifact-compatibility diagnostics only; not costed policy PnL, "
            "not model promotion, and not live/paper readiness"
        ),
    }
    _write_json(output_paths["diagnostics"], payload)
    payload["diagnostics_path"] = output_paths["diagnostics"]
    payload["model_comparison_output_path"] = output_paths["model_comparison"]
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--predictions-manifest", required=True)
    parser.add_argument("--models-config", required=True)
    parser.add_argument("--reports-root", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--target-name", default=DEFAULT_TARGET_NAME)
    parser.add_argument("--min-class-rate", type=float, default=DEFAULT_MIN_CLASS_RATE)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = evaluate_single_target_predictions(
        predictions_path=Path(args.predictions),
        predictions_manifest=Path(args.predictions_manifest),
        models_config=Path(args.models_config),
        reports_root=Path(args.reports_root),
        run=args.run,
        target_name=args.target_name,
        min_class_rate=args.min_class_rate,
    )
    coverage = result["coverage"]
    score_summary = result["score_summary"]
    print(
        "FAIL" if result["failure_count"] else "PASS",
        "single-target diagnostics:",
        f"rows={coverage.get('row_count', 0)}",
        f"target={result['target_name']}",
        f"prediction_std={score_summary.get('prediction_std')}",
        f"promotion_allowed={result['promotion_allowed']}",
        f"failures={result['failure_count']}",
    )
    return 1 if result["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
