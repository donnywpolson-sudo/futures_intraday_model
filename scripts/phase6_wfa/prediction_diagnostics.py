#!/usr/bin/env python3
"""Build report-only Phase 6 OOS prediction diagnostics."""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from scripts.phase8_model_selection.evaluate_predictions import (
    _direction_accuracy,
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _prediction_manifest_failures,
    _read_json,
    _relative_path,
    _score_column_for_target,
    _safe_float,
    _safe_int,
    _write_json,
)


DEFAULT_OUTPUT_ROOT = Path("reports") / "prediction_diagnostics"
DEFAULT_RUN = "baseline"
DIAGNOSTIC_STATUS = "PREDICTION_DIAGNOSTICS_READY"


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _pearson(left: pd.Series, right: pd.Series) -> float | None:
    aligned = pd.DataFrame({"left": left, "right": right}).dropna()
    if len(aligned) < 2:
        return None
    if aligned["left"].nunique(dropna=True) < 2 or aligned["right"].nunique(dropna=True) < 2:
        return None
    return _safe_float(aligned["left"].corr(aligned["right"], method="pearson"))


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    aligned = pd.DataFrame({"left": left, "right": right}).dropna()
    if len(aligned) < 2:
        return None
    if aligned["left"].nunique(dropna=True) < 2 or aligned["right"].nunique(dropna=True) < 2:
        return None
    return _safe_float(aligned["left"].corr(aligned["right"], method="spearman"))


def _safe_std(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return None
    return _safe_float(numeric.std(ddof=0))


def _log_loss(y_true: pd.Series, probability: pd.Series) -> float | None:
    aligned = pd.DataFrame({"y_true": y_true, "probability": probability}).dropna()
    if aligned.empty:
        return None
    y = aligned["y_true"].clip(lower=0, upper=1).astype(float)
    p = aligned["probability"].clip(lower=1e-12, upper=1.0 - 1e-12).astype(float)
    return _safe_float(float(-(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)).mean()))


def _brier(y_true: pd.Series, probability: pd.Series) -> float | None:
    aligned = pd.DataFrame({"y_true": y_true, "probability": probability}).dropna()
    if aligned.empty:
        return None
    y = aligned["y_true"].clip(lower=0, upper=1).astype(float)
    p = aligned["probability"].clip(lower=0, upper=1).astype(float)
    return _safe_float(float(((p - y) ** 2).mean()))


def _target_scope_records(predictions: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    group_cols = ["model_id", "model_family", "target_name", "market", "year", "fold_id"]
    for keys, group in predictions.groupby(group_cols, dropna=False):
        model_id, model_family, target_name, market, year, fold_id = keys
        score = _score_column_for_target(group, str(target_name))
        actual = pd.to_numeric(group["y_true"], errors="coerce")
        record: dict[str, Any] = {
            "model_id": model_id,
            "model_family": model_family,
            "target_name": target_name,
            "market": market,
            "year": _safe_int(year) if _safe_int(year) is not None else year,
            "fold_id": fold_id,
            "row_count": int(len(group)),
            "prediction_type": str(group["prediction_type"].dropna().iloc[0])
            if group["prediction_type"].notna().any()
            else None,
            "prediction_mean": _safe_float(score.mean()),
            "prediction_std": _safe_std(score),
            "target_mean": _safe_float(actual.mean()),
            "target_std": _safe_std(actual),
            "ic_pearson": _pearson(score, actual),
            "rank_ic_spearman": _spearman(score, actual),
            "direction_accuracy": _direction_accuracy(group)
            if str(target_name) == "target_sign_with_deadzone"
            else None,
        }
        if actual.dropna().isin([0, 1]).all():
            record["brier_score"] = _brier(actual, score)
            record["log_loss"] = _log_loss(actual, score)
        else:
            record["brier_score"] = None
            record["log_loss"] = None
        records.append(record)
    return records


def _target_summary(target_scope: pd.DataFrame) -> pd.DataFrame:
    if target_scope.empty:
        return pd.DataFrame()
    records: list[dict[str, Any]] = []
    for keys, group in target_scope.groupby(["model_id", "model_family", "target_name"], dropna=False):
        model_id, model_family, target_name = keys
        records.append(
            {
                "model_id": model_id,
                "model_family": model_family,
                "target_name": target_name,
                "row_count": int(group["row_count"].sum()),
                "market_count": int(group["market"].nunique(dropna=True)),
                "year_count": int(group["year"].nunique(dropna=True)),
                "fold_count": int(group["fold_id"].nunique(dropna=True)),
                "mean_ic_pearson": _safe_float(group["ic_pearson"].mean()),
                "mean_rank_ic_spearman": _safe_float(group["rank_ic_spearman"].mean()),
                "min_fold_ic_pearson": _safe_float(group["ic_pearson"].min()),
                "max_fold_ic_pearson": _safe_float(group["ic_pearson"].max()),
                "ic_dispersion": _safe_std(group["ic_pearson"]),
                "mean_direction_accuracy": _safe_float(group["direction_accuracy"].mean()),
                "mean_brier_score": _safe_float(group["brier_score"].mean()),
                "mean_log_loss": _safe_float(group["log_loss"].mean()),
            }
        )
    return pd.DataFrame(records).sort_values(["model_id", "target_name"]).reset_index(drop=True)


def _decile_records(predictions: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for keys, group in predictions.groupby(["model_id", "target_name"], dropna=False):
        model_id, target_name = keys
        score = _score_column_for_target(group, str(target_name))
        actual = pd.to_numeric(group["y_true"], errors="coerce")
        aligned = group[["market", "year", "fold_id"]].copy()
        aligned["score"] = score
        aligned["actual"] = actual
        aligned = aligned.dropna(subset=["score", "actual"])
        if len(aligned) < 10 or aligned["score"].nunique(dropna=True) < 2:
            continue
        try:
            aligned["prediction_decile"] = pd.qcut(
                aligned["score"],
                q=10,
                labels=False,
                duplicates="drop",
            )
        except ValueError:
            continue
        for decile, decile_group in aligned.groupby("prediction_decile", dropna=False):
            records.append(
                {
                    "model_id": model_id,
                    "target_name": target_name,
                    "prediction_decile": _safe_int(decile),
                    "row_count": int(len(decile_group)),
                    "prediction_mean": _safe_float(decile_group["score"].mean()),
                    "target_mean": _safe_float(decile_group["actual"].mean()),
                    "target_positive_rate": _safe_float(decile_group["actual"].gt(0).mean()),
                }
            )
    return records


def _calibration_records(predictions: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for keys, group in predictions.groupby(["model_id", "target_name"], dropna=False):
        model_id, target_name = keys
        actual = pd.to_numeric(group["y_true"], errors="coerce")
        if not actual.dropna().isin([0, 1]).all():
            continue
        score = _score_column_for_target(group, str(target_name)).clip(lower=0.0, upper=1.0)
        aligned = pd.DataFrame({"score": score, "actual": actual}).dropna()
        if aligned.empty:
            continue
        aligned["probability_bin"] = pd.cut(
            aligned["score"],
            bins=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            labels=["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"],
            include_lowest=True,
        ).astype(str)
        for bin_id, bin_group in aligned.groupby("probability_bin", dropna=False):
            records.append(
                {
                    "model_id": model_id,
                    "target_name": target_name,
                    "probability_bin": bin_id,
                    "row_count": int(len(bin_group)),
                    "avg_probability": _safe_float(bin_group["score"].mean()),
                    "empirical_positive_rate": _safe_float(bin_group["actual"].mean()),
                    "calibration_error": _safe_float(
                        abs(bin_group["score"].mean() - bin_group["actual"].mean())
                    ),
                }
            )
    return records


def _failure_labels(target_summary: pd.DataFrame) -> list[str]:
    labels: set[str] = set()
    if target_summary.empty:
        return ["prediction_diagnostics_missing"]
    for _, row in target_summary.iterrows():
        mean_ic = _safe_float(row.get("mean_ic_pearson"))
        mean_rank_ic = _safe_float(row.get("mean_rank_ic_spearman"))
        dispersion = _safe_float(row.get("ic_dispersion"))
        mean_brier = _safe_float(row.get("mean_brier_score"))
        if (mean_ic is None or abs(mean_ic) < 0.01) and (
            mean_rank_ic is None or abs(mean_rank_ic) < 0.01
        ):
            labels.add("weak_signal")
        if dispersion is not None and dispersion > 0.20:
            labels.add("unstable_by_fold")
        if mean_brier is not None and mean_brier > 0.30:
            labels.add("miscalibrated_probabilities")
    return sorted(labels)


def _manifest_scope(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "profile": manifest.get("profile"),
        "resolved_profile": manifest.get("resolved_profile"),
        "markets": manifest.get("markets"),
        "years": manifest.get("years"),
        "prediction_markets": manifest.get("prediction_markets"),
        "prediction_years": manifest.get("prediction_years"),
        "fold_count": manifest.get("fold_count"),
        "prediction_count": manifest.get("prediction_count"),
    }


def build_prediction_diagnostics(
    *,
    predictions_path: Path,
    predictions_manifest: Path,
    output_root: Path,
    run: str,
) -> dict[str, Any]:
    failures: list[str] = []
    manifest = _read_json(predictions_manifest)
    if not predictions_path.exists():
        predictions = pd.DataFrame()
        failures.append(f"prediction parquet missing: {_relative_path(predictions_path)}")
    else:
        predictions = pd.read_parquet(predictions_path)
    failures.extend(
        _prediction_manifest_failures(
            manifest,
            predictions_path=predictions_path,
            predictions=predictions,
            run=run,
        )
        if predictions_manifest
        else ["prediction manifest required"]
    )

    target_scope = pd.DataFrame(_target_scope_records(predictions)) if not predictions.empty else pd.DataFrame()
    target_summary = _target_summary(target_scope)
    deciles = pd.DataFrame(_decile_records(predictions)) if not predictions.empty else pd.DataFrame()
    calibration = (
        pd.DataFrame(_calibration_records(predictions)) if not predictions.empty else pd.DataFrame()
    )
    labels = _failure_labels(target_summary)
    prediction_diagnostics_ready = not failures
    status = DIAGNOSTIC_STATUS if prediction_diagnostics_ready else "FAIL"

    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "prediction_diagnostics_summary.json"
    target_scope_path = output_root / "prediction_target_scope.csv"
    target_summary_path = output_root / "prediction_target_summary.csv"
    deciles_path = output_root / "prediction_deciles.csv"
    calibration_path = output_root / "prediction_calibration_bins.csv"
    readme_path = output_root / "prediction_diagnostics.md"
    outputs = {
        "summary": _relative_path(summary_path),
        "target_scope": _relative_path(target_scope_path),
        "target_summary": _relative_path(target_summary_path),
        "deciles": _relative_path(deciles_path),
        "calibration": _relative_path(calibration_path),
        "readme": _relative_path(readme_path),
    }
    _write_csv(target_scope_path, target_scope)
    _write_csv(target_summary_path, target_summary)
    _write_csv(deciles_path, deciles)
    _write_csv(calibration_path, calibration)

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "diagnostic_type": "phase6_prediction_diagnostics",
        "diagnostic_only": True,
        "status": status,
        "prediction_diagnostics_ready": prediction_diagnostics_ready,
        "run": run,
        "prediction_path": _relative_path(predictions_path),
        "predictions_manifest_path": _relative_path(predictions_manifest),
        "prediction_count": int(len(predictions)),
        "failure_count": len(failures),
        "failures": failures,
        "failure_labels": labels,
        "scope": _manifest_scope(manifest),
        "target_count": int(predictions["target_name"].nunique(dropna=True))
        if "target_name" in predictions
        else 0,
        "target_summaries": target_summary.to_dict(orient="records"),
        "input_file_hashes": _file_hash_map([predictions_path, predictions_manifest]),
        "outputs": outputs,
        "research_only": True,
        "model_promotion_allowed": False,
    }
    _write_json(summary_path, payload)
    readme_path.write_text(
        "\n".join(
            [
                "# Phase 6 Prediction Diagnostics",
                "",
                f"Run: `{run}`",
                "",
                "This report audits saved OOS predictions only. It does not train, tune, select, promote, or trade a model.",
                "",
                f"Status: `{status}`",
                f"Failure labels: `{', '.join(labels) if labels else 'none'}`",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--predictions-manifest", required=True)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = build_prediction_diagnostics(
        predictions_path=Path(args.predictions),
        predictions_manifest=Path(args.predictions_manifest),
        output_root=Path(args.output_root),
        run=args.run,
    )
    print(
        "PASS" if not result["failure_count"] else "FAIL",
        "prediction diagnostics:",
        f"predictions={result['prediction_count']}",
        f"targets={result['target_count']}",
        f"failures={result['failure_count']}",
        f"summary={result['outputs']['summary']}",
    )
    return 1 if result["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
