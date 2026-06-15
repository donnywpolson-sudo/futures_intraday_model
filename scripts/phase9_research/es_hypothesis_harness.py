#!/usr/bin/env python3
"""Run a compact ES-only Ridge harness for one feature hypothesis."""

from __future__ import annotations

import argparse
import json
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts.phase4_features.build_baseline_features import FEATURE_FAMILIES
from scripts.phase7_wfa.run_wfa import (
    DEFAULT_INPUT_ROOT,
    DEFAULT_SPLIT_PLAN,
    _file_hash_map,
    _fold_masks,
    _git_commit,
    _load_market_frame,
    _read_json,
    _relative_path,
    _validate_fold_fields,
    _write_json,
    load_feature_cols,
)


DEFAULT_RUN = "tier1_es_hypothesis"
DEFAULT_REPORTS_ROOT = Path("reports/pipeline_audit")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_DISCOVERY_FOLDS = tuple(f"ES_research_{idx:04d}" for idx in range(1, 5))
DEFAULT_CONFIRMATION_FOLDS = tuple(f"ES_research_{idx:04d}" for idx in range(5, 9))
TARGET_COLUMN = "target_net_dollars_after_est_cost"
GROSS_COLUMN = "target_gross_dollars_15m"
COST_COLUMN = "round_turn_cost_dollars"
MARKET = "ES"


def _parse_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _correlation(prediction: pd.Series, target: pd.Series, method: str) -> float | None:
    aligned = pd.DataFrame({"prediction": prediction, "target": target}).replace(
        [np.inf, -np.inf], np.nan
    )
    aligned = aligned.dropna()
    if len(aligned) < 2:
        return None
    if aligned["prediction"].nunique(dropna=True) < 2 or aligned["target"].nunique(dropna=True) < 2:
        return None
    return _float_or_none(aligned["prediction"].corr(aligned["target"], method=method))


def _resolve_features(
    *,
    feature_family: str | None,
    features: Sequence[str],
    registered_features: Sequence[str],
) -> tuple[str, list[str]]:
    if feature_family and features:
        raise SystemExit("provide either --feature-family or --features, not both")
    if not feature_family and not features:
        raise SystemExit("provide --feature-family or --features")

    if feature_family:
        if feature_family not in FEATURE_FAMILIES:
            raise SystemExit(f"unknown feature family: {feature_family}")
        selected = list(FEATURE_FAMILIES[feature_family])
        hypothesis_id = feature_family
    else:
        selected = list(dict.fromkeys(features))
        hypothesis_id = "custom"

    registry = set(registered_features)
    missing = [feature for feature in selected if feature not in registry]
    if missing:
        raise SystemExit(f"selected features missing from registry: {missing}")
    if not selected:
        raise SystemExit("selected feature set is empty")
    return hypothesis_id, selected


def _source_columns(features: Sequence[str]) -> list[str]:
    return sorted(
        set(features)
        | {
            "ts",
            "market",
            "year",
            "session_id",
            "session_segment_id",
            "causal_valid",
            "target_valid",
            "feature_input_valid",
            "training_row_valid",
            TARGET_COLUMN,
            GROSS_COLUMN,
            COST_COLUMN,
        }
    )


def _round_turn_cost(costs_config: Path, market: str) -> float | None:
    if not costs_config.exists():
        return None
    payload = yaml.safe_load(costs_config.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        return None
    markets = payload.get("markets", {})
    if not isinstance(markets, Mapping):
        return None
    market_costs = markets.get(market)
    if not isinstance(market_costs, Mapping):
        return None
    return _float_or_none(market_costs.get("round_turn_cost_dollars"))


def _selected_folds(
    split_manifest: Mapping[str, Any],
    discovery_fold_ids: Sequence[str],
    confirmation_fold_ids: Sequence[str],
) -> tuple[list[tuple[str, Mapping[str, Any]]], list[str]]:
    folds = split_manifest.get("folds", [])
    if not isinstance(folds, list) or not folds:
        raise SystemExit("split plan has no folds")

    by_id: dict[str, Mapping[str, Any]] = {}
    for fold in folds:
        if isinstance(fold, Mapping) and "fold_id" in fold:
            by_id[str(fold["fold_id"])] = fold

    requested = [*discovery_fold_ids, *confirmation_fold_ids]
    missing = [fold_id for fold_id in requested if fold_id not in by_id]
    if missing:
        raise SystemExit(f"requested folds missing from split plan: {missing}")

    failures: list[str] = []
    selected: list[tuple[str, Mapping[str, Any]]] = []
    for stage, fold_ids in (("discovery", discovery_fold_ids), ("confirmation", confirmation_fold_ids)):
        for fold_id in fold_ids:
            fold = by_id[fold_id]
            failures.extend(_validate_fold_fields(fold))
            if str(fold.get("market", "")) != MARKET:
                failures.append(f"{fold_id}: harness only supports ES folds")
            if str(fold.get("split_group", "")) != "research":
                failures.append(f"{fold_id}: harness only supports research folds")
            if fold.get("selection_allowed") is not True:
                failures.append(f"{fold_id}: selection_allowed must be true")
            selected.append((stage, fold))

    if failures:
        raise SystemExit("; ".join(failures))
    return selected, requested


def _feature_quality(frame: pd.DataFrame, mask: pd.Series, features: Sequence[str]) -> dict[str, Any]:
    sample = frame.loc[mask, list(features)]
    if sample.empty:
        return {
            "rows": 0,
            "all_null_features": list(features),
            "mean_missing_rate": None,
            "max_missing_rate": None,
        }
    missing_rates = sample.isna().mean()
    return {
        "rows": int(len(sample)),
        "all_null_features": sorted(missing_rates[missing_rates >= 1.0].index.tolist()),
        "mean_missing_rate": _float_or_none(missing_rates.mean()),
        "max_missing_rate": _float_or_none(missing_rates.max()),
    }


def _fit_estimator() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0)),
        ]
    )


def _fold_metrics(
    *,
    fold: Mapping[str, Any],
    stage: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: Sequence[str],
    y_train: pd.Series,
    y_test: pd.Series,
    prediction: np.ndarray,
    top_fraction: float,
) -> dict[str, Any]:
    pred = pd.Series(prediction, index=test.index, dtype="float64")
    gross = pd.to_numeric(test[GROSS_COLUMN], errors="coerce")
    cost = pd.to_numeric(test[COST_COLUMN], errors="coerce").fillna(0.0)
    position = pd.Series(np.sign(pred.to_numpy()), index=test.index, dtype="float64")
    realized_gross = position * gross
    realized_net = realized_gross - np.where(position.ne(0), cost, 0.0)

    scored = pd.DataFrame(
        {
            "prediction": pred,
            "target": y_test,
            "position": position,
            "gross_dollars": realized_gross,
            "net_dollars": realized_net,
        }
    ).replace([np.inf, -np.inf], np.nan)
    scored = scored.dropna(subset=["prediction", "target", "gross_dollars", "net_dollars"])
    top_rows = int(math.ceil(len(scored) * top_fraction)) if len(scored) else 0
    if top_rows:
        top = scored.assign(abs_prediction=scored["prediction"].abs()).nlargest(
            top_rows, "abs_prediction"
        )
    else:
        top = scored.iloc[0:0]

    actual_side = pd.Series(np.sign(scored["target"].to_numpy()), index=scored.index)
    signable = scored["position"].ne(0) & actual_side.ne(0)
    if signable.any():
        sign_accuracy = float(scored.loc[signable, "position"].eq(actual_side.loc[signable]).mean())
    else:
        sign_accuracy = None

    return {
        "fold_id": str(fold["fold_id"]),
        "stage": stage,
        "market": str(fold.get("market", "")),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "scored_rows": int(len(scored)),
        "fit_ts_min": train["ts"].min().isoformat() if not train.empty else None,
        "fit_ts_max": train["ts"].max().isoformat() if not train.empty else None,
        "score_ts_min": test["ts"].min().isoformat() if not test.empty else None,
        "score_ts_max": test["ts"].max().isoformat() if not test.empty else None,
        "prediction_std": _float_or_none(np.nanstd(prediction)),
        "pearson_prediction_target": _correlation(pred, y_test, "pearson"),
        "spearman_prediction_target": _correlation(pred, y_test, "spearman"),
        "signed_target_accuracy": sign_accuracy,
        "all_rows_total_gross_dollars": _float_or_none(scored["gross_dollars"].sum()),
        "all_rows_total_net_dollars": _float_or_none(scored["net_dollars"].sum()),
        "top_fraction": top_fraction,
        "top_rows": int(len(top)),
        "top_total_gross_dollars": _float_or_none(top["gross_dollars"].sum()),
        "top_total_net_dollars": _float_or_none(top["net_dollars"].sum()),
        "top_avg_net_dollars": _float_or_none(top["net_dollars"].mean()),
        "train_feature_quality": _feature_quality(train, pd.Series(True, index=train.index), features),
        "test_feature_quality": _feature_quality(test, pd.Series(True, index=test.index), features),
    }


def _stage_summary(fold_metrics: Sequence[Mapping[str, Any]], stage: str) -> dict[str, Any]:
    rows = [item for item in fold_metrics if item["stage"] == stage]
    top_rows = sum(int(item.get("top_rows") or 0) for item in rows)
    top_total_net = sum(float(item.get("top_total_net_dollars") or 0.0) for item in rows)
    top_total_gross = sum(float(item.get("top_total_gross_dollars") or 0.0) for item in rows)
    return {
        "stage": stage,
        "fold_count": len(rows),
        "train_rows": sum(int(item.get("train_rows") or 0) for item in rows),
        "test_rows": sum(int(item.get("test_rows") or 0) for item in rows),
        "scored_rows": sum(int(item.get("scored_rows") or 0) for item in rows),
        "top_rows": top_rows,
        "top_total_gross_dollars": _float_or_none(top_total_gross),
        "top_total_net_dollars": _float_or_none(top_total_net),
        "top_avg_net_dollars": _float_or_none(top_total_net / top_rows) if top_rows else None,
        "positive_top_net_fold_count": sum(
            1 for item in rows if float(item.get("top_total_net_dollars") or 0.0) > 0.0
        ),
        "positive": bool(top_total_net > 0.0 and top_rows > 0),
    }


def _markdown_report(report: Mapping[str, Any]) -> str:
    discovery = report["stage_summaries"]["discovery"]
    confirmation = report["stage_summaries"]["confirmation"]
    lines = [
        "# Tier 1 ES Hypothesis Harness",
        "",
        f"- run: {report['run']}",
        f"- hypothesis: {report['hypothesis_id']}",
        f"- features: {len(report['features'])}",
        f"- target: {TARGET_COLUMN}",
        f"- model: Ridge(alpha=1.0)",
        f"- top_fraction: {report['top_fraction']}",
        f"- decision: {report['decision']}",
        f"- graduation_allowed: {report['graduation_allowed']}",
        "",
        "## Stage Summary",
        "",
        "| stage | folds | test_rows | top_rows | top_net | avg_top_net | positive_folds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in (discovery, confirmation):
        lines.append(
            "| {stage} | {folds} | {test_rows} | {top_rows} | {top_net:.2f} | {avg_top_net} | {positive_folds} |".format(
                stage=summary["stage"],
                folds=summary["fold_count"],
                test_rows=summary["test_rows"],
                top_rows=summary["top_rows"],
                top_net=float(summary["top_total_net_dollars"] or 0.0),
                avg_top_net=(
                    f"{float(summary['top_avg_net_dollars']):.2f}"
                    if summary["top_avg_net_dollars"] is not None
                    else "NA"
                ),
                positive_folds=summary["positive_top_net_fold_count"],
            )
        )
    lines.extend(["", "## Fold Summary", ""])
    lines.append(
        "| fold | stage | train_rows | test_rows | top_rows | top_net | pred_std | spearman |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in report["fold_metrics"]:
        lines.append(
            "| {fold} | {stage} | {train_rows} | {test_rows} | {top_rows} | {top_net:.2f} | {pred_std} | {spearman} |".format(
                fold=item["fold_id"],
                stage=item["stage"],
                train_rows=item["train_rows"],
                test_rows=item["test_rows"],
                top_rows=item["top_rows"],
                top_net=float(item["top_total_net_dollars"] or 0.0),
                pred_std=(
                    f"{float(item['prediction_std']):.6f}"
                    if item["prediction_std"] is not None
                    else "NA"
                ),
                spearman=(
                    f"{float(item['spearman_prediction_target']):.6f}"
                    if item["spearman_prediction_target"] is not None
                    else "NA"
                ),
            )
        )
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
            "- stop if discovery top net is not positive.",
            "- stop if confirmation top net is not positive.",
            "- graduate only when both discovery and confirmation are positive without fold failures.",
            "",
        ]
    )
    return "\n".join(lines)


def run_harness(
    *,
    run: str,
    input_root: Path,
    split_plan: Path,
    reports_root: Path,
    feature_family: str | None,
    features: Sequence[str],
    costs_config: Path = DEFAULT_COSTS_CONFIG,
    feature_cols_path: Path | None = None,
    discovery_fold_ids: Sequence[str] = DEFAULT_DISCOVERY_FOLDS,
    confirmation_fold_ids: Sequence[str] = DEFAULT_CONFIRMATION_FOLDS,
    top_fraction: float = 0.05,
) -> dict[str, Any]:
    if not 0.0 < top_fraction <= 1.0:
        raise SystemExit("--top-fraction must be in (0, 1]")

    registered_features, resolved_feature_cols_path = load_feature_cols(input_root, feature_cols_path)
    hypothesis_id, selected_features = _resolve_features(
        feature_family=feature_family,
        features=features,
        registered_features=registered_features,
    )
    split_manifest = _read_json(split_plan)
    selected_folds, requested_fold_ids = _selected_folds(
        split_manifest, discovery_fold_ids, confirmation_fold_ids
    )
    years = [int(year) for year in split_manifest.get("years", [])]
    if not years:
        raise SystemExit("split plan years are missing")

    frame, load_failures, matrix_paths = _load_market_frame(
        MARKET,
        years,
        input_root,
        _source_columns(selected_features),
    )
    if frame is None:
        raise SystemExit("; ".join(load_failures) if load_failures else "no ES feature frame loaded")
    if load_failures:
        raise SystemExit("; ".join(load_failures))
    target = pd.to_numeric(frame[TARGET_COLUMN], errors="coerce")
    fold_metrics: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings_seen: list[str] = []
    round_turn = _round_turn_cost(costs_config, MARKET)
    cost = pd.to_numeric(frame.get(COST_COLUMN), errors="coerce")
    if cost.isna().any():
        if round_turn is None:
            raise SystemExit(f"{COST_COLUMN} missing/null and no usable ES cost in {_relative_path(costs_config)}")
        frame[COST_COLUMN] = cost.fillna(round_turn)
        warnings_seen.append(
            f"{COST_COLUMN} missing/null in feature matrix; filled ES cost from {_relative_path(costs_config)}"
        )

    for stage, fold in selected_folds:
        train_mask, test_mask = _fold_masks(frame, fold, target)
        train = frame.loc[train_mask].copy()
        test = frame.loc[test_mask].copy()
        if train.empty or test.empty:
            failures.append(f"{fold['fold_id']}: empty train or test rows")
            continue
        if train["ts"].max() >= test["ts"].min():
            failures.append(f"{fold['fold_id']}: train/test timestamp overlap")
            continue

        y_train = target.loc[train.index]
        y_test = target.loc[test.index]
        estimator = _fit_estimator()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            estimator.fit(train[list(selected_features)], y_train)
        if caught:
            warning_text = [str(item.message).splitlines()[0] for item in caught]
            warnings_seen.extend(f"{fold['fold_id']}: {item}" for item in warning_text)
        prediction = estimator.predict(test[list(selected_features)])
        fold_metrics.append(
            _fold_metrics(
                fold=fold,
                stage=stage,
                train=train,
                test=test,
                features=selected_features,
                y_train=y_train,
                y_test=y_test,
                prediction=np.asarray(prediction, dtype=float),
                top_fraction=top_fraction,
            )
        )

    discovery = _stage_summary(fold_metrics, "discovery")
    confirmation = _stage_summary(fold_metrics, "confirmation")
    graduation_allowed = bool(
        not failures
        and discovery["positive"]
        and confirmation["positive"]
        and discovery["fold_count"] == len(discovery_fold_ids)
        and confirmation["fold_count"] == len(confirmation_fold_ids)
    )
    decision = "GRADUATE_TO_LOCKED_OOS_RECHECK" if graduation_allowed else "STOP_REWORK_HYPOTHESIS"

    json_path = reports_root / f"{run}_hypothesis_harness.json"
    markdown_path = reports_root / f"{run}_hypothesis_harness.md"
    report: dict[str, Any] = {
        "run": run,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "market": MARKET,
        "hypothesis_id": hypothesis_id,
        "feature_family": feature_family,
        "features": list(selected_features),
        "target": TARGET_COLUMN,
        "model": {"family": "ridge_regression", "alpha": 1.0},
        "top_fraction": top_fraction,
        "discovery_fold_ids": list(discovery_fold_ids),
        "confirmation_fold_ids": list(confirmation_fold_ids),
        "requested_fold_ids": requested_fold_ids,
        "input_root": _relative_path(input_root),
        "split_plan": _relative_path(split_plan),
        "costs_config": _relative_path(costs_config),
        "feature_cols_path": _relative_path(resolved_feature_cols_path),
        "input_file_hashes": _file_hash_map(
            [split_plan, costs_config, resolved_feature_cols_path, *matrix_paths]
        ),
        "fold_metrics": fold_metrics,
        "stage_summaries": {"discovery": discovery, "confirmation": confirmation},
        "failure_count": len(failures),
        "failures": failures,
        "warning_count": len(warnings_seen),
        "warnings": warnings_seen,
        "graduation_allowed": graduation_allowed,
        "decision": decision,
        "report_paths": {
            "json": _relative_path(json_path),
            "markdown": _relative_path(markdown_path),
        },
    }
    _write_json(json_path, report)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--feature-cols", default=None)
    parser.add_argument("--feature-family", default=None)
    parser.add_argument("--features", default=None)
    parser.add_argument("--discovery-folds", default=",".join(DEFAULT_DISCOVERY_FOLDS))
    parser.add_argument("--confirmation-folds", default=",".join(DEFAULT_CONFIRMATION_FOLDS))
    parser.add_argument("--top-fraction", type=float, default=0.05)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    report = run_harness(
        run=args.run,
        input_root=Path(args.input_root),
        split_plan=Path(args.split_plan),
        reports_root=Path(args.reports_root),
        costs_config=Path(args.costs_config),
        feature_cols_path=Path(args.feature_cols) if args.feature_cols else None,
        feature_family=args.feature_family,
        features=_parse_csv(args.features),
        discovery_fold_ids=_parse_csv(args.discovery_folds),
        confirmation_fold_ids=_parse_csv(args.confirmation_folds),
        top_fraction=args.top_fraction,
    )
    discovery = report["stage_summaries"]["discovery"]
    confirmation = report["stage_summaries"]["confirmation"]
    status = "PASS" if report["graduation_allowed"] else "STOP"
    print(
        f"{status} ES hypothesis harness: decision={report['decision']} "
        f"discovery_top_net={float(discovery['top_total_net_dollars'] or 0.0):.2f} "
        f"confirmation_top_net={float(confirmation['top_total_net_dollars'] or 0.0):.2f} "
        f"failures={report['failure_count']}"
    )
    return 0 if report["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
