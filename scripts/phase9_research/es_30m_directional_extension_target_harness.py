#!/usr/bin/env python3
"""ES-only Phase 9 smoke for a 30-minute directional-extension target.

This harness is target-construction feasibility only. It reads existing feature
matrices, writes a bounded smoke report, and does not run WFA, Phase 8,
promotion, downloads, label/feature rebuilds, or saved-prediction evaluation.
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

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


HYPOTHESIS_ID = "es_30m_directional_extension_target_v1"
DEFAULT_RUN = HYPOTHESIS_ID
DEFAULT_REPORTS_ROOT = Path("reports/pipeline_audit")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_TARGET_REGISTRY = Path("manifests/target_hypotheses/registry.json")
DEFAULT_DISCOVERY_FOLDS = tuple(f"ES_research_{idx:04d}" for idx in range(1, 5))
DEFAULT_CONFIRMATION_FOLDS = tuple(f"ES_research_{idx:04d}" for idx in range(5, 9))
DEFAULT_LOCKED_FOLDS = tuple(f"ES_research_{idx:04d}" for idx in range(9, 13))
DEFAULT_TOP_FRACTION = 0.05
MARKET = "ES"
ENTRY_OFFSET_BARS = 1
EXIT_OFFSET_BARS = 31
HORIZON_BARS = EXIT_OFFSET_BARS - ENTRY_OFFSET_BARS

TARGET_VALID_COLUMN = "target_valid_30m_extension"
TARGET_DIRECTION_COLUMN = "target_direction_30m_extension"
TARGET_GROSS_COLUMN = "target_gross_dollars_30m_extension"
TARGET_COST_COLUMN = "target_cost_dollars_30m_extension"
TARGET_NET_COLUMN = "target_net_dollars_30m_extension"
TARGET_NONFLAT_COLUMN = "target_nonflat_30m_extension"
TARGET_ENTRY_TS_COLUMN = "target_entry_ts_30m_extension"
TARGET_EXIT_TS_COLUMN = "target_exit_ts_30m_extension"

REQUIRED_COLUMNS = (
    "ts",
    "market",
    "year",
    "session_segment_id",
    "open",
    "high",
    "low",
    "close",
    "causal_valid",
    "valid_ohlcv",
    "inside_session",
    "feature_input_valid",
    "feature_row_valid",
    "training_row_valid",
    "target_valid",
    "target_sign_with_deadzone",
    "is_synthetic",
    "roll_window_flag",
    "boundary_session_flag",
)
LEAKAGE_PREFIXES = ("target", "label", "future", "entry", "exit")
LEAKAGE_SUBSTRINGS = ("forward", "gross", "net", "pnl", "profit", "cost", "mfe", "mae")


def _parse_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _float_or_none(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _bool_col(df: pd.DataFrame, column: str, default: bool) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=bool)
    values = df[column].replace(
        {
            "True": True,
            "true": True,
            "1": True,
            "False": False,
            "false": False,
            "0": False,
        }
    )
    return values.fillna(default).astype(bool)


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").astype(float)


def validate_target_hypothesis_registered(
    registry_path: Path = DEFAULT_TARGET_REGISTRY,
) -> list[str]:
    if not registry_path.exists():
        return [f"target registry missing: {_relative_path(registry_path)}"]
    try:
        payload = _read_json(registry_path)
    except Exception as exc:
        return [f"target registry invalid JSON: {exc}"]
    rows = payload.get("hypotheses", [])
    if not isinstance(rows, list):
        return ["target registry hypotheses must be a list"]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("target_hypothesis_id") != HYPOTHESIS_ID:
            continue
        failures: list[str] = []
        if row.get("status") != "CANDIDATE":
            failures.append(f"{HYPOTHESIS_ID}: expected CANDIDATE status before smoke run")
        if row.get("wfa_allowed") is not False:
            failures.append(f"{HYPOTHESIS_ID}: wfa_allowed must be false before freeze")
        scope = row.get("scope", {})
        if not isinstance(scope, Mapping):
            failures.append(f"{HYPOTHESIS_ID}: scope must be an object")
        else:
            if scope.get("markets") != [MARKET]:
                failures.append(f"{HYPOTHESIS_ID}: scope.markets must be ['ES']")
            if scope.get("years") != [2023, 2024]:
                failures.append(f"{HYPOTHESIS_ID}: scope.years must be [2023, 2024]")
        return failures
    return [f"{HYPOTHESIS_ID}: missing from target hypothesis registry"]


def load_es_cost_config(costs_config: Path) -> dict[str, float]:
    payload = yaml.safe_load(costs_config.read_text(encoding="utf-8")) or {}
    markets = payload.get("markets", {}) if isinstance(payload, Mapping) else {}
    raw = markets.get(MARKET) if isinstance(markets, Mapping) else None
    if not isinstance(raw, Mapping):
        raise SystemExit(f"missing cost config for {MARKET}")
    required = ("tick_size", "tick_value", "round_turn_cost_dollars", "min_profit_ticks")
    out: dict[str, float] = {}
    for key in required:
        value = _float_or_none(raw.get(key))
        if value is None or value <= 0:
            raise SystemExit(f"invalid {key} for {MARKET}")
        out[key] = value
    out["cost_ticks"] = out["round_turn_cost_dollars"] / out["tick_value"]
    return out


def is_leakage_feature(column: str) -> bool:
    value = column.lower()
    if any(value.startswith(prefix) for prefix in LEAKAGE_PREFIXES):
        return True
    return any(item in value for item in LEAKAGE_SUBSTRINGS)


def select_model_features(feature_cols: Sequence[str]) -> list[str]:
    return [column for column in feature_cols if column.startswith("feature_") and not is_leakage_feature(column)]


def _source_columns(features: Sequence[str]) -> list[str]:
    return sorted(set(features) | set(REQUIRED_COLUMNS))


def _path_valid_mask(frame: pd.DataFrame) -> pd.Series:
    valid = (
        _bool_col(frame, "causal_valid", False)
        & _bool_col(frame, "valid_ohlcv", True)
        & _bool_col(frame, "inside_session", True)
        & _bool_col(frame, "feature_input_valid", False)
        & _bool_col(frame, "feature_row_valid", True)
        & _bool_col(frame, "training_row_valid", False)
        & _bool_col(frame, "target_valid", False)
        & ~_bool_col(frame, "is_synthetic", False)
        & ~_bool_col(frame, "roll_window_flag", False)
        & ~_bool_col(frame, "boundary_session_flag", False)
        & (_numeric(frame, "open") > 0)
        & (_numeric(frame, "high") > 0)
        & (_numeric(frame, "low") > 0)
        & (_numeric(frame, "close") > 0)
    )
    session = frame["session_segment_id"].astype("string")
    same_session = pd.Series(True, index=frame.index, dtype=bool)
    full_path_valid = pd.Series(True, index=frame.index, dtype=bool)
    for offset in range(0, EXIT_OFFSET_BARS + 1):
        same_session &= session.shift(-offset).eq(session).fillna(False)
        full_path_valid &= valid.shift(-offset).fillna(False)
    return same_session & full_path_valid


def apply_30m_directional_extension_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    exit_price = _numeric(out, "open").shift(-EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    valid = _path_valid_mask(out) & entry_price.notna() & exit_price.notna()

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])
    cost_ticks = float(cost_config["cost_ticks"])
    min_profit_ticks = float(cost_config["min_profit_ticks"])
    threshold_ticks = cost_ticks + min_profit_ticks

    gross_ticks = (exit_price - entry_price) / tick_size
    gross_dollars = gross_ticks * tick_value
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & (gross_ticks > threshold_ticks), 1)
    direction = direction.mask(valid & (gross_ticks < -threshold_ticks), -1)
    nonflat = direction.ne(0) & valid
    net_ticks = np.sign(gross_ticks) * (gross_ticks.abs() - cost_ticks).clip(lower=0.0)
    net_dollars = net_ticks * tick_value

    out[TARGET_VALID_COLUMN] = valid.astype(bool)
    out[TARGET_DIRECTION_COLUMN] = direction
    out[TARGET_NONFLAT_COLUMN] = nonflat.astype(bool)
    out[TARGET_GROSS_COLUMN] = gross_dollars.where(valid)
    out[TARGET_COST_COLUMN] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[TARGET_NET_COLUMN] = net_dollars.where(valid)
    out[TARGET_ENTRY_TS_COLUMN] = entry_ts.where(valid)
    out[TARGET_EXIT_TS_COLUMN] = exit_ts.where(valid)
    return out


def non_overlapping_events(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    valid = frame.loc[frame[TARGET_VALID_COLUMN].astype(bool)].copy()
    selected_indices: list[int] = []
    skipped = 0
    for _, group in valid.groupby(["market", "year", "session_segment_id"], dropna=False, sort=False):
        group = group.sort_values(TARGET_ENTRY_TS_COLUMN, kind="mergesort")
        last_exit: pd.Timestamp | None = None
        for row in group.itertuples():
            entry_ts = getattr(row, TARGET_ENTRY_TS_COLUMN)
            exit_ts = getattr(row, TARGET_EXIT_TS_COLUMN)
            if pd.isna(entry_ts) or pd.isna(exit_ts) or exit_ts <= entry_ts:
                skipped += 1
                continue
            if last_exit is not None and entry_ts <= last_exit:
                skipped += 1
                continue
            selected_indices.append(int(row.Index))
            last_exit = exit_ts
    events = frame.loc[selected_indices].sort_values(
        ["market", "year", TARGET_ENTRY_TS_COLUMN],
        kind="mergesort",
    )
    return events.reset_index(drop=True), skipped


def duplicate_target_overlap(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty:
        return {"available": False, "overlap_with_current_15m_deadzone": None}
    new_nonflat = events[TARGET_NONFLAT_COLUMN].astype(bool)
    current_nonflat = pd.to_numeric(events["target_sign_with_deadzone"], errors="coerce").fillna(0).ne(0)
    denominator = int(new_nonflat.sum())
    overlap = int((new_nonflat & current_nonflat).sum())
    return {
        "available": True,
        "new_nonflat_count": denominator,
        "current_15m_nonflat_count": int(current_nonflat.sum()),
        "overlap_count": overlap,
        "overlap_with_current_15m_deadzone": float(overlap / denominator) if denominator else None,
        "max_allowed_overlap": 0.80,
    }


def class_balance(events: pd.DataFrame) -> dict[str, Any]:
    total = int(len(events))
    direction = pd.to_numeric(events[TARGET_DIRECTION_COLUMN], errors="coerce").fillna(0)
    counts = {
        "long": int((direction > 0).sum()),
        "short": int((direction < 0).sum()),
        "flat": int((direction == 0).sum()),
    }
    rates = {key: float(value / total) if total else None for key, value in counts.items()}
    return {"event_count": total, "counts": counts, "rates": rates}


def _fit_estimator() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0)),
        ]
    )


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


def _fold_metrics(
    *,
    fold: Mapping[str, Any],
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: Sequence[str],
    top_fraction: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    y_train = pd.to_numeric(train[TARGET_NET_COLUMN], errors="coerce")
    y_test = pd.to_numeric(test[TARGET_NET_COLUMN], errors="coerce")
    estimator = _fit_estimator()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        estimator.fit(train[list(features)], y_train)
    prediction = pd.Series(
        estimator.predict(test[list(features)]),
        index=test.index,
        dtype="float64",
    )
    position = np.sign(prediction).astype(float)
    gross = pd.to_numeric(test[TARGET_GROSS_COLUMN], errors="coerce")
    cost = pd.to_numeric(test[TARGET_COST_COLUMN], errors="coerce").fillna(0.0)
    realized_gross = position * gross
    realized_net = realized_gross - np.where(position.ne(0), cost, 0.0)
    scored = test.copy()
    scored["prediction"] = prediction
    scored["position"] = position
    scored["realized_gross_dollars"] = realized_gross
    scored["realized_net_dollars"] = realized_net
    scored = scored.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["prediction", TARGET_NET_COLUMN, "realized_net_dollars"]
    )
    top_count = int(math.ceil(len(scored) * top_fraction)) if len(scored) else 0
    top = (
        scored.assign(abs_prediction=scored["prediction"].abs()).nlargest(top_count, "abs_prediction")
        if top_count
        else scored.iloc[0:0].copy()
    )
    actual_direction = pd.to_numeric(scored[TARGET_DIRECTION_COLUMN], errors="coerce").fillna(0)
    signable = scored["position"].ne(0) & actual_direction.ne(0)
    signed_accuracy = (
        float(scored.loc[signable, "position"].eq(actual_direction.loc[signable]).mean())
        if signable.any()
        else None
    )
    warning_text = [str(item.message).splitlines()[0] for item in caught]
    metric = {
        "fold_id": str(fold["fold_id"]),
        "market": str(fold.get("market", "")),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "scored_rows": int(len(scored)),
        "top_fraction": float(top_fraction),
        "top_rows": int(len(top)),
        "prediction_std": _float_or_none(prediction.std()),
        "spearman_prediction_target": _correlation(prediction, y_test, "spearman"),
        "signed_nonflat_accuracy": signed_accuracy,
        "top_total_gross_dollars": _float_or_none(top["realized_gross_dollars"].sum()),
        "top_total_net_dollars": _float_or_none(top["realized_net_dollars"].sum()),
        "top_avg_net_dollars": _float_or_none(top["realized_net_dollars"].mean()),
        "top_long_count": int((top["position"] > 0).sum()),
        "top_short_count": int((top["position"] < 0).sum()),
        "warning_count": len(warning_text),
        "warnings": warning_text,
    }
    return metric, top


def stage_folds(stage: str, fold_ids: Sequence[str] | None = None) -> list[str]:
    if fold_ids:
        return list(fold_ids)
    if stage == "discovery":
        return list(DEFAULT_DISCOVERY_FOLDS)
    if stage == "confirmation":
        return list(DEFAULT_CONFIRMATION_FOLDS)
    if stage == "locked":
        return list(DEFAULT_LOCKED_FOLDS)
    raise SystemExit(f"unknown stage: {stage}")


def _selected_folds(split_manifest: Mapping[str, Any], fold_ids: Sequence[str]) -> list[Mapping[str, Any]]:
    raw_folds = split_manifest.get("folds", [])
    if not isinstance(raw_folds, list):
        raise SystemExit("split plan folds must be a list")
    by_id = {str(fold.get("fold_id")): fold for fold in raw_folds if isinstance(fold, Mapping)}
    missing = [fold_id for fold_id in fold_ids if fold_id not in by_id]
    if missing:
        raise SystemExit(f"requested folds missing from split plan: {missing}")
    failures: list[str] = []
    selected: list[Mapping[str, Any]] = []
    for fold_id in fold_ids:
        fold = by_id[fold_id]
        failures.extend(_validate_fold_fields(fold))
        if str(fold.get("market")) != MARKET:
            failures.append(f"{fold_id}: expected ES market")
        if str(fold.get("split_group")) != "research":
            failures.append(f"{fold_id}: expected research split_group")
        if fold.get("selection_allowed") is not True:
            failures.append(f"{fold_id}: selection_allowed must be true")
        if fold.get("final_holdout") is True or fold.get("is_final_holdout") is True:
            failures.append(f"{fold_id}: final holdout folds are forbidden")
        selected.append(fold)
    if failures:
        raise SystemExit("; ".join(failures))
    return selected


def stage_summary(fold_metrics: Sequence[Mapping[str, Any]], expected_fold_count: int) -> dict[str, Any]:
    top_rows = sum(int(item.get("top_rows") or 0) for item in fold_metrics)
    top_net = sum(float(item.get("top_total_net_dollars") or 0.0) for item in fold_metrics)
    pred_stds = [float(item["prediction_std"]) for item in fold_metrics if item.get("prediction_std") is not None]
    return {
        "expected_fold_count": int(expected_fold_count),
        "fold_count": int(len(fold_metrics)),
        "test_rows": sum(int(item.get("test_rows") or 0) for item in fold_metrics),
        "scored_rows": sum(int(item.get("scored_rows") or 0) for item in fold_metrics),
        "top_rows": int(top_rows),
        "top_total_net_dollars": float(top_net),
        "top_avg_net_dollars": float(top_net / top_rows) if top_rows else None,
        "positive_top_net_fold_count": sum(
            1 for item in fold_metrics if float(item.get("top_total_net_dollars") or 0.0) > 0.0
        ),
        "min_prediction_std": min(pred_stds) if pred_stds else None,
    }


def evaluate_stage_gates(report: Mapping[str, Any]) -> dict[str, Any]:
    failures = list(report.get("failures", []))
    gates: list[dict[str, Any]] = [
        {
            "gate": "registry_inputs_and_schema",
            "pass": not failures,
            "failure_decision": "STOP_INPUT_FAILURE",
            "failures": failures,
        }
    ]
    balance = report["class_balance"]
    counts = balance["counts"]
    rates = balance["rates"]
    class_failures = [
        name
        for name in ("long", "short", "flat")
        if int(counts.get(name, 0)) < 1000 or float(rates.get(name) or 0.0) < 0.01
    ]
    gates.append(
        {
            "gate": "no_class_collapse",
            "pass": not class_failures,
            "failure_decision": "STOP_CLASS_COLLAPSE",
            "failures": class_failures,
            "min_count": 1000,
            "min_rate": 0.01,
        }
    )
    overlap = report["duplicate_target_overlap"].get("overlap_with_current_15m_deadzone")
    gates.append(
        {
            "gate": "not_duplicate_of_current_15m_deadzone",
            "pass": overlap is not None and float(overlap) <= 0.80,
            "failure_decision": "STOP_DUPLICATE_TARGET",
            "overlap": overlap,
            "max_allowed_overlap": 0.80,
        }
    )
    summary = report["stage_summary"]
    unstable = []
    if summary["fold_count"] != summary["expected_fold_count"]:
        unstable.append("missing_fold_metrics")
    if summary["top_rows"] <= 0:
        unstable.append("no_top_rows")
    if summary["min_prediction_std"] is None or float(summary["min_prediction_std"]) <= 0.0:
        unstable.append("constant_predictions")
    if int(summary["positive_top_net_fold_count"]) < max(1, math.ceil(summary["expected_fold_count"] / 2)):
        unstable.append("too_few_positive_folds")
    gates.append(
        {
            "gate": "stable_stage_folds",
            "pass": not unstable,
            "failure_decision": "STOP_UNSTABLE_FOLDS",
            "failures": unstable,
        }
    )
    gates.append(
        {
            "gate": "positive_stage_net",
            "pass": float(summary["top_total_net_dollars"]) > 0.0,
            "failure_decision": f"STOP_{str(report['stage']).upper()}_NEGATIVE_NET",
            "top_total_net_dollars": summary["top_total_net_dollars"],
        }
    )
    decision = f"{str(report['stage']).upper()}_PASS"
    for gate in gates:
        if not gate["pass"]:
            decision = str(gate["failure_decision"])
            break
    return {"decision": decision, "gates": gates}


def _markdown_report(report: Mapping[str, Any]) -> str:
    summary = report["stage_summary"]
    lines = [
        "# ES 30m Directional Extension Target Smoke",
        "",
        f"- run: {report['run']}",
        f"- hypothesis_id: {report['hypothesis_id']}",
        f"- stage: {report['stage']}",
        f"- decision: {report['decision']}",
        "- output_type: target-construction smoke only",
        "- executable_pnl: false",
        "- wfa: false",
        "",
        "## Gates",
        "",
        "| gate | pass |",
        "| --- | --- |",
    ]
    for gate in report["gates"]:
        lines.append(f"| {gate['gate']} | {gate['pass']} |")
    lines.extend(
        [
            "",
            "## Stage Summary",
            "",
            f"- folds: {summary['fold_count']} / {summary['expected_fold_count']}",
            f"- top_rows: {summary['top_rows']}",
            f"- top_total_net_dollars: {summary['top_total_net_dollars']:.2f}",
            f"- positive_top_net_fold_count: {summary['positive_top_net_fold_count']}",
            "",
            "## Class Balance",
            "",
            f"- counts: {report['class_balance']['counts']}",
            f"- rates: {report['class_balance']['rates']}",
            "",
            "## Duplicate Target Overlap",
            "",
            f"- overlap_with_current_15m_deadzone: {report['duplicate_target_overlap'].get('overlap_with_current_15m_deadzone')}",
            "",
            "## Fold Metrics",
            "",
            "| fold | top_rows | top_net | pred_std | spearman |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report["fold_metrics"]:
        pred_std = row["prediction_std"]
        spearman = row["spearman_prediction_target"]
        lines.append(
            "| {fold} | {top_rows} | {top_net:.2f} | {pred_std} | {spearman} |".format(
                fold=row["fold_id"],
                top_rows=row["top_rows"],
                top_net=float(row["top_total_net_dollars"] or 0.0),
                pred_std="NA" if pred_std is None else f"{float(pred_std):.6f}",
                spearman="NA" if spearman is None else f"{float(spearman):.6f}",
            )
        )
    lines.extend(
        [
            "",
            "## Do Not Do",
            "",
            "- Do not run confirmation unless discovery decision is DISCOVERY_PASS.",
            "- Do not run locked unless confirmation decision is CONFIRMATION_PASS.",
            "- Do not run WFA, Phase 8, promotion, downloads, or artifact freeze from this result.",
            "- Do not tune thresholds, features, costs, or fold selection after seeing this report.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_paths(reports_root: Path, run: str, stage: str) -> tuple[Path, Path]:
    return (
        reports_root / f"{run}_{stage}_smoke.md",
        reports_root / f"{run}_{stage}_smoke.json",
    )


def run_harness(
    *,
    run: str = DEFAULT_RUN,
    stage: str = "discovery",
    input_root: Path = DEFAULT_INPUT_ROOT,
    split_plan: Path = DEFAULT_SPLIT_PLAN,
    reports_root: Path = DEFAULT_REPORTS_ROOT,
    costs_config: Path = DEFAULT_COSTS_CONFIG,
    target_registry: Path = DEFAULT_TARGET_REGISTRY,
    feature_cols_path: Path | None = None,
    fold_ids: Sequence[str] | None = None,
    top_fraction: float = DEFAULT_TOP_FRACTION,
    write_reports: bool = True,
) -> dict[str, Any]:
    if not 0.0 < top_fraction <= 1.0:
        raise SystemExit("--top-fraction must be in (0, 1]")
    selected_fold_ids = stage_folds(stage, fold_ids)
    registry_failures = validate_target_hypothesis_registered(target_registry)
    cost_config = load_es_cost_config(costs_config)
    feature_cols, resolved_feature_cols = load_feature_cols(input_root, feature_cols_path)
    model_features = select_model_features(feature_cols)
    if not model_features:
        raise SystemExit("no non-leaking feature columns available")
    split_manifest = _read_json(split_plan)
    folds = _selected_folds(split_manifest, selected_fold_ids)
    years = [2023, 2024]
    frame, load_failures, matrix_paths = _load_market_frame(
        MARKET,
        years,
        input_root,
        _source_columns(model_features),
    )
    failures = [*registry_failures, *load_failures]
    if frame is None:
        raise SystemExit("; ".join(failures) if failures else "no ES feature frame loaded")
    labeled = apply_30m_directional_extension_target(frame, cost_config)
    events, skipped_overlap_count = non_overlapping_events(labeled)
    fold_metrics: list[dict[str, Any]] = []
    top_rows: list[pd.DataFrame] = []
    if not events.empty:
        target = pd.to_numeric(events[TARGET_NET_COLUMN], errors="coerce")
        for fold in folds:
            train_mask, test_mask = _fold_masks(events, fold, target)
            train = events.loc[train_mask].copy()
            test = events.loc[test_mask].copy()
            if train.empty or test.empty:
                failures.append(f"{fold['fold_id']}: empty train or test rows")
                continue
            if train["ts"].max() >= test["ts"].min():
                failures.append(f"{fold['fold_id']}: train/test timestamp overlap")
                continue
            metric, selected_top = _fold_metrics(
                fold=fold,
                train=train,
                test=test,
                features=model_features,
                top_fraction=top_fraction,
            )
            fold_metrics.append(metric)
            top_rows.append(selected_top)

    selected = pd.concat(top_rows, ignore_index=True) if top_rows else pd.DataFrame()
    md_path, json_path = _report_paths(reports_root, run, stage)
    hash_paths = [target_registry, split_plan, costs_config, resolved_feature_cols, *matrix_paths]
    report: dict[str, Any] = {
        "run": run,
        "hypothesis_id": HYPOTHESIS_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "stage": stage,
        "harness_type": "phase9_target_construction_smoke_only",
        "not_wfa": True,
        "not_phase8": True,
        "uses_saved_predictions": False,
        "scope": {
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "markets": [MARKET],
            "years": years,
            "fold_ids": selected_fold_ids,
        },
        "input_paths": {
            "target_registry": _relative_path(target_registry),
            "input_root": _relative_path(input_root),
            "split_plan": _relative_path(split_plan),
            "costs_config": _relative_path(costs_config),
            "feature_cols": _relative_path(resolved_feature_cols),
        },
        "input_hashes": _file_hash_map(hash_paths),
        "label_definition": {
            "entry": "next 1-minute open",
            "exit": "open 31 bars ahead, giving a 30-minute entry-to-exit horizon",
            "long": "gross ticks > round-turn cost ticks + min_profit_ticks",
            "short": "gross ticks < -(round-turn cost ticks + min_profit_ticks)",
            "flat": "all valid rows inside the deadzone",
            "validity": "same session segment, no synthetic/invalid/boundary/roll path, existing target/feature validity true",
        },
        "target_columns": [
            TARGET_VALID_COLUMN,
            TARGET_DIRECTION_COLUMN,
            TARGET_GROSS_COLUMN,
            TARGET_COST_COLUMN,
            TARGET_NET_COLUMN,
            TARGET_NONFLAT_COLUMN,
        ],
        "event_count": int(len(events)),
        "skipped_overlap_count": int(skipped_overlap_count),
        "class_balance": class_balance(events) if not events.empty else {"event_count": 0, "counts": {}, "rates": {}},
        "duplicate_target_overlap": duplicate_target_overlap(events),
        "model": {"family": "ridge_regression", "alpha": 1.0},
        "model_feature_count": len(model_features),
        "top_fraction": float(top_fraction),
        "fold_metrics": fold_metrics,
        "stage_summary": stage_summary(fold_metrics, len(folds)),
        "failures": failures,
        "failure_count": len(failures),
        "report_paths": {"markdown": _relative_path(md_path), "json": _relative_path(json_path)},
    }
    gate_result = evaluate_stage_gates(report)
    report["decision"] = gate_result["decision"]
    report["gates"] = gate_result["gates"]
    if write_reports:
        reports_root.mkdir(parents=True, exist_ok=True)
        _write_json(json_path, report)
        md_path.write_text(_markdown_report(report), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--stage", choices=["discovery", "confirmation", "locked"], default="discovery")
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--target-registry", default=DEFAULT_TARGET_REGISTRY.as_posix())
    parser.add_argument("--feature-cols", default=None)
    parser.add_argument("--folds", default=None)
    parser.add_argument("--top-fraction", type=float, default=DEFAULT_TOP_FRACTION)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    report = run_harness(
        run=args.run,
        stage=args.stage,
        input_root=Path(args.input_root),
        split_plan=Path(args.split_plan),
        reports_root=Path(args.reports_root),
        costs_config=Path(args.costs_config),
        target_registry=Path(args.target_registry),
        feature_cols_path=Path(args.feature_cols) if args.feature_cols else None,
        fold_ids=_parse_csv(args.folds),
        top_fraction=args.top_fraction,
        write_reports=True,
    )
    summary = report["stage_summary"]
    print(
        json.dumps(
            {
                "run": report["run"],
                "hypothesis_id": report["hypothesis_id"],
                "stage": report["stage"],
                "decision": report["decision"],
                "top_total_net_dollars": summary["top_total_net_dollars"],
                "positive_top_net_fold_count": summary["positive_top_net_fold_count"],
                "failure_count": report["failure_count"],
                "report_paths": report["report_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if report["decision"] == "STOP_INPUT_FAILURE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
