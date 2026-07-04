#!/usr/bin/env python3
"""Diagnostic-only rescue feasibility audit for a failed single-target candidate."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from scripts.phase8_model_selection.analyze_low_tick_rule_attribution import (
    TARGET_ACCEPTANCE_DISTANCE,
    TARGET_ADVERSE,
    TARGET_DIRECTION,
    TARGET_FAVORABLE,
    TARGET_THRESHOLD,
    TARGET_VALID,
)
from scripts.phase8_model_selection.analyze_trade_tick_excursions import (
    BAR_REQUIRED_COLUMNS,
    TRADE_REQUIRED_COLUMNS,
    CostConfig,
    _check_columns,
    _relative,
    _resolve,
    build_trade_excursion_frame,
    load_bars,
    load_cost_config,
)
from scripts.phase8_model_selection.evaluate_predictions import (
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _read_json,
    _relative_path,
    _write_json,
)
from scripts.phase8_model_selection.single_target_diagnostics import DEFAULT_TARGET_NAME
from scripts.phase8_model_selection.single_target_policy_diagnostics import (
    _build_single_target_policy_frame,
)


DEFAULT_HYPOTHESIS_ID = "opening_range_acceptance_continuation_30m_v1"
DEFAULT_RUN = "opening_range_acceptance_continuation_30m_v1_model_expansion_s1"
DEFAULT_MARKET = "ES"
DEFAULT_YEAR = 2024
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DIAGNOSTIC_TYPE = "candidate_rescue_feasibility"

PREDICTION_REQUIRED_COLUMNS = (
    "market",
    "year",
    "fold_id",
    "timestamp",
    "model_id",
    "target_name",
    "p_long",
    "p_short",
    "p_flat",
    "execution_open",
    "execution_close",
    "target_entry_ts",
    "target_exit_ts",
)

TARGET_CONTEXT_COLUMNS = (
    "ts",
    "market",
    "year",
    TARGET_VALID,
    TARGET_DIRECTION,
    TARGET_THRESHOLD,
    TARGET_ACCEPTANCE_DISTANCE,
    TARGET_FAVORABLE,
    TARGET_ADVERSE,
)


@dataclass(frozen=True)
class RescuePaths:
    predictions: Path
    predictions_manifest: Path
    wfa_report: Path
    policy_diagnostics: Path
    trades: Path
    bars: Path
    costs_config: Path
    first_touch_diagnostics: Path
    first_touch_grid: Path
    json_out: Path
    md_out: Path


def _run_family(run: str) -> str:
    if "_s" in run:
        prefix, suffix = run.rsplit("_s", 1)
        if suffix.isdigit():
            return prefix
    return run


def default_paths(hypothesis_id: str, run: str) -> RescuePaths:
    run_family = _run_family(run)
    policy_root = Path("reports/phase8_single_target_policy") / run
    first_touch_root = Path("reports/phase8_first_touch_feasibility") / run
    output_root = Path("reports/candidate_rescue_feasibility") / hypothesis_id / run
    return RescuePaths(
        predictions=Path("data/predictions") / run_family / run / "oos_predictions.parquet",
        predictions_manifest=Path("reports/wfa") / run_family / f"{run}_predictions_manifest.json",
        wfa_report=Path("reports/wfa") / run_family / f"{run}_wfa_report.json",
        policy_diagnostics=policy_root / f"{run}_single_target_policy_diagnostics.json",
        trades=policy_root / f"{run}_single_target_policy_trades.csv",
        bars=Path("data/feature_matrices") / f"{hypothesis_id}_wfa_smoke" / DEFAULT_MARKET / f"{DEFAULT_YEAR}.parquet",
        costs_config=DEFAULT_COSTS_CONFIG,
        first_touch_diagnostics=first_touch_root / f"{run}_first_touch_feasibility_diagnostics.json",
        first_touch_grid=first_touch_root / f"{run}_first_touch_feasibility_grid.csv",
        json_out=output_root / "rescue_feasibility.json",
        md_out=output_root / "rescue_feasibility.md",
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        missing = pd.isna(value)
    except TypeError:
        missing = False
    if isinstance(missing, bool) and missing:
        return None
    return value


def _fmt_money(value: Any) -> str:
    return f"${_safe_float(value):,.2f}"


def _fmt_num(value: Any, digits: int = 2) -> str:
    return f"{_safe_float(value):,.{digits}f}"


def _fmt_pct(value: Any, digits: int = 1) -> str:
    return f"{100.0 * _safe_float(value):.{digits}f}%"


def _pct(count: int, total: int) -> float:
    return float(count / total) if total else 0.0


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return lines


def _read_json_required(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"missing required {label}: {_relative(path)}")
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} is not a JSON object: {_relative(path)}")
    return payload


def _validate_outputs_absent(paths: Iterable[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        rendered = ", ".join(_relative(path) for path in existing)
        raise ValueError(f"stale output path exists: {rendered}")


def load_predictions(path: Path) -> pd.DataFrame:
    predictions = pd.read_parquet(path)
    _check_columns(predictions, PREDICTION_REQUIRED_COLUMNS, "predictions")
    out = predictions.copy()
    for column in ("timestamp", "target_entry_ts", "target_exit_ts"):
        out[column] = pd.to_datetime(out[column], utc=True, errors="coerce")
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    for column in ("p_long", "p_short", "p_flat", "execution_open", "execution_close"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    duplicate_keys = out.duplicated(
        ["market", "year", "fold_id", "timestamp", "model_id", "target_name"],
        keep=False,
    )
    if duplicate_keys.any():
        raise ValueError(f"predictions contain duplicate keys: {int(duplicate_keys.sum())}")
    return out


def load_trades_no_count(path: Path) -> pd.DataFrame:
    trades = pd.read_csv(path)
    _check_columns(trades, TRADE_REQUIRED_COLUMNS, "trades")
    for column in ("timestamp", "target_entry_ts", "target_exit_ts"):
        trades[column] = pd.to_datetime(trades[column], utc=True, errors="coerce")
    for column in ("year", "position"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce").astype("Int64")
    for column in ("execution_open", "execution_close", "gross_dollars", "cost_dollars", "net_dollars"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    duplicate_keys = trades.duplicated(
        ["market", "year", "timestamp", "target_entry_ts", "target_exit_ts"],
        keep=False,
    )
    if duplicate_keys.any():
        raise ValueError(f"trades contain duplicate join keys: {int(duplicate_keys.sum())}")
    return trades


def load_target_context(path: Path) -> pd.DataFrame:
    context = pd.read_parquet(path, columns=list(TARGET_CONTEXT_COLUMNS))
    _check_columns(context, TARGET_CONTEXT_COLUMNS, "target context")
    out = context.rename(columns={"ts": "timestamp"}).copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    for column in (
        TARGET_DIRECTION,
        TARGET_THRESHOLD,
        TARGET_ACCEPTANCE_DISTANCE,
        TARGET_FAVORABLE,
        TARGET_ADVERSE,
    ):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    duplicate_keys = out.duplicated(["market", "year", "timestamp"], keep=False)
    if duplicate_keys.any():
        raise ValueError(f"target context contains duplicate join keys: {int(duplicate_keys.sum())}")
    return out


def _add_probability_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    probabilities = out[["p_long", "p_short", "p_flat"]].apply(pd.to_numeric, errors="coerce")
    sorted_probabilities = probabilities.apply(lambda row: sorted(row.dropna().tolist()), axis=1)
    out["top_probability"] = probabilities.max(axis=1)
    out["second_probability"] = sorted_probabilities.apply(
        lambda values: values[-2] if len(values) >= 2 else float("nan")
    )
    out["probability_margin"] = out["top_probability"] - out["second_probability"]
    out["candidate_side"] = "flat"
    out.loc[out["candidate_position"].eq(1), "candidate_side"] = "long"
    out.loc[out["candidate_position"].eq(-1), "candidate_side"] = "short"
    out["timestamp_hour_utc"] = out["timestamp"].dt.hour.astype("Int64").astype(str)
    return out


def _fixed_exit_tick_features(frame: pd.DataFrame, costs: CostConfig) -> pd.DataFrame:
    out = frame.copy()
    out["candidate_fixed_exit_ticks"] = out["candidate_gross_dollars"] / costs.tick_value
    out["candidate_net_ticks"] = out["candidate_net_dollars"] / costs.tick_value
    out["executed_fixed_exit_ticks"] = out["gross_dollars"] / costs.tick_value
    out["executed_net_ticks"] = out["net_dollars"] / costs.tick_value
    return out


def build_policy_context(
    predictions: pd.DataFrame,
    target_context: pd.DataFrame,
    *,
    costs: CostConfig,
    costs_config: Path,
    target_name: str,
) -> pd.DataFrame:
    target_frame = predictions[predictions["target_name"].astype(str).eq(target_name)].copy()
    if target_frame.empty:
        raise ValueError(f"no predictions found for target {target_name!r}")
    policy_frame, failures, _warnings = _build_single_target_policy_frame(target_frame, costs_config)
    if failures:
        raise ValueError(f"single-target policy frame failures: {failures}")
    policy_frame = _add_probability_features(policy_frame)
    policy_frame = _fixed_exit_tick_features(policy_frame, costs)
    merged = policy_frame.merge(
        target_context[
            [
                "market",
                "year",
                "timestamp",
                TARGET_VALID,
                TARGET_DIRECTION,
                TARGET_THRESHOLD,
                TARGET_ACCEPTANCE_DISTANCE,
                TARGET_FAVORABLE,
                TARGET_ADVERSE,
            ]
        ],
        on=["market", "year", "timestamp"],
        how="left",
        validate="many_to_one",
    )
    candidates = merged["candidate_position"].ne(0)
    if merged.loc[candidates, TARGET_DIRECTION].isna().any():
        raise ValueError("candidate rows missing target context join")
    merged["target_direction_match_oracle"] = (
        merged["candidate_position"].astype(int).eq(
            pd.to_numeric(merged[TARGET_DIRECTION], errors="coerce").fillna(0).astype(int)
        )
        & candidates
    )
    merged["abs_acceptance_distance_ticks"] = pd.to_numeric(
        merged[TARGET_ACCEPTANCE_DISTANCE],
        errors="coerce",
    ).abs()
    return merged


def _bucket_qcut(series: pd.Series, bins: int, *, label: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().nunique() <= 1:
        return pd.Series([f"{label}_all"] * len(series), index=series.index, dtype="object")
    try:
        buckets = pd.qcut(numeric, bins, duplicates="drop")
    except ValueError:
        return pd.Series([f"{label}_all"] * len(series), index=series.index, dtype="object")
    return buckets.astype(str)


def _bucket_acceptance_distance(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    buckets = pd.cut(
        numeric,
        bins=[0, 1, 2, 4, 8, float("inf")],
        labels=["0-1", "1-2", "2-4", "4-8", "8+"],
        include_lowest=True,
    )
    return buckets.astype(str)


def _positive_fold_count(frame: pd.DataFrame) -> int:
    if frame.empty or "fold_id" not in frame.columns:
        return 0
    return int(
        frame.groupby("fold_id", dropna=False)["candidate_net_dollars"].sum().gt(0).sum()
    )


def _summarize_bucket_family(
    candidates: pd.DataFrame,
    *,
    family: str,
    column: str,
    min_bucket_trades: int,
    min_positive_folds: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, group in candidates.groupby(column, dropna=False):
        trade_count = int(len(group))
        fold_count = int(group["fold_id"].nunique())
        positive_folds = _positive_fold_count(group)
        net = float(group["candidate_net_dollars"].sum())
        gross = float(group["candidate_gross_dollars"].sum())
        costs = float(group["candidate_cost_dollars"].sum())
        rows.append(
            {
                "bucket_family": family,
                "bucket": str(bucket),
                "candidate_trade_count": trade_count,
                "fold_count": fold_count,
                "positive_fold_count": positive_folds,
                "gross_dollars": gross,
                "cost_dollars": costs,
                "net_dollars": net,
                "avg_net_dollars": net / trade_count if trade_count else 0.0,
                "mean_fixed_exit_ticks": float(group["candidate_fixed_exit_ticks"].mean()),
                "median_fixed_exit_ticks": float(group["candidate_fixed_exit_ticks"].median()),
                "stable_positive": bool(
                    trade_count >= min_bucket_trades
                    and net > 0
                    and positive_folds >= min_positive_folds
                ),
            }
        )
    return rows


def summarize_pretrade_buckets(
    policy_context: pd.DataFrame,
    *,
    min_bucket_trades: int,
    min_positive_folds: int,
) -> list[dict[str, Any]]:
    candidates = policy_context.loc[policy_context["candidate_position"].ne(0)].copy()
    if candidates.empty:
        raise ValueError("no candidate trades available for pre-trade bucket audit")
    candidates["confidence_decile"] = _bucket_qcut(
        candidates["direction_probability"],
        10,
        label="confidence",
    )
    candidates["margin_decile"] = _bucket_qcut(
        candidates["probability_margin"],
        10,
        label="margin",
    )
    candidates["acceptance_distance_bucket"] = _bucket_acceptance_distance(
        candidates["abs_acceptance_distance_ticks"]
    )
    families = [
        ("fold", "fold_id"),
        ("side", "candidate_side"),
        ("time_hour_utc", "timestamp_hour_utc"),
        ("confidence_decile", "confidence_decile"),
        ("probability_margin_decile", "margin_decile"),
        ("opening_range_distance", "acceptance_distance_bucket"),
    ]
    rows: list[dict[str, Any]] = []
    for family, column in families:
        rows.extend(
            _summarize_bucket_family(
                candidates,
                family=family,
                column=column,
                min_bucket_trades=min_bucket_trades,
                min_positive_folds=min_positive_folds,
            )
        )
    return rows


def executed_path_summary(
    *,
    policy_context: pd.DataFrame,
    trades: pd.DataFrame,
    bars: pd.DataFrame,
    costs: CostConfig,
) -> dict[str, Any]:
    _check_columns(bars, BAR_REQUIRED_COLUMNS, "bars")
    excursion = build_trade_excursion_frame(trades, bars, costs)
    keys = ["market", "year", "fold_id", "timestamp", "target_entry_ts", "target_exit_ts", "position"]
    executed = policy_context.loc[policy_context["position"].ne(0)].copy()
    merged = executed.merge(
        excursion[
            [
                *keys,
                "realized_gross_ticks",
                "current_cost_net_ticks",
                "favorable_excursion_ticks",
                "adverse_excursion_ticks",
            ]
        ],
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if merged["favorable_excursion_ticks"].isna().any():
        raise ValueError("executed policy rows missing excursion join")
    merged["optimistic_mfe_capture_gross_dollars"] = (
        merged["favorable_excursion_ticks"] * costs.tick_value
    )
    merged["optimistic_mfe_capture_net_dollars"] = (
        merged["optimistic_mfe_capture_gross_dollars"] - merged["cost_dollars"]
    )
    fold_positive = int(
        merged.groupby("fold_id", dropna=False)["optimistic_mfe_capture_net_dollars"]
        .sum()
        .gt(0)
        .sum()
    )
    giveback = merged["favorable_excursion_ticks"] - merged["realized_gross_ticks"]
    return {
        "trade_count": int(len(merged)),
        "optimistic_mfe_capture_gross_dollars": float(
            merged["optimistic_mfe_capture_gross_dollars"].sum()
        ),
        "optimistic_mfe_capture_net_dollars": float(
            merged["optimistic_mfe_capture_net_dollars"].sum()
        ),
        "optimistic_mfe_capture_positive_fold_count": fold_positive,
        "median_mfe_ticks": float(merged["favorable_excursion_ticks"].median()),
        "median_mae_ticks": float(merged["adverse_excursion_ticks"].median()),
        "median_realized_ticks": float(merged["realized_gross_ticks"].median()),
        "median_giveback_ticks": float(giveback.median()),
    }


def first_touch_summary(diagnostics_path: Path, grid_path: Path) -> dict[str, Any]:
    diagnostics = _read_json_required(diagnostics_path, "first-touch diagnostics")
    if not grid_path.exists():
        raise ValueError(f"missing required first-touch grid: {_relative(grid_path)}")
    grid = pd.read_csv(grid_path)
    support = diagnostics.get("decision_support") or {}
    overall = grid.loc[grid.get("scope_type", pd.Series(dtype=str)).astype(str).eq("overall")]
    if overall.empty:
        raise ValueError("first-touch grid missing overall rows")
    best_stop_first_net = float(pd.to_numeric(overall["stop_first_net_dollars"], errors="coerce").max())
    best_ambiguous_excluded_net = float(
        pd.to_numeric(overall["ambiguous_excluded_net_dollars"], errors="coerce").max()
    )
    return {
        "screen_status": support.get("screen_status"),
        "grid_count": _safe_int(support.get("grid_count")),
        "stop_first_positive_overall_grid_count": _safe_int(
            support.get("stop_first_positive_overall_grid_count")
        ),
        "ambiguous_excluded_positive_overall_grid_count": _safe_int(
            support.get("ambiguous_excluded_positive_overall_grid_count")
        ),
        "stop_first_at_least_3_positive_fold_grid_count": _safe_int(
            support.get("stop_first_at_least_3_positive_fold_grid_count")
        ),
        "best_stop_first_net_dollars": best_stop_first_net,
        "best_ambiguous_excluded_net_dollars": best_ambiguous_excluded_net,
    }


def overall_policy_summary(policy_context: pd.DataFrame) -> dict[str, Any]:
    candidates = policy_context.loc[policy_context["candidate_position"].ne(0)]
    executed = policy_context.loc[policy_context["position"].ne(0)]
    target_match = candidates.loc[candidates["target_direction_match_oracle"]]
    target_mismatch = candidates.loc[~candidates["target_direction_match_oracle"]]
    row_count = int(len(policy_context))
    candidate_count = int(len(candidates))
    return {
        "prediction_row_count": row_count,
        "candidate_trade_count": candidate_count,
        "candidate_trade_rate": _pct(candidate_count, row_count),
        "executed_trade_count": int(len(executed)),
        "candidate_fixed_exit_gross_dollars": float(candidates["candidate_gross_dollars"].sum()),
        "candidate_fixed_exit_cost_dollars": float(candidates["candidate_cost_dollars"].sum()),
        "candidate_fixed_exit_net_dollars": float(candidates["candidate_net_dollars"].sum()),
        "executed_fixed_exit_gross_dollars": float(executed["gross_dollars"].sum()),
        "executed_fixed_exit_cost_dollars": float(executed["cost_dollars"].sum()),
        "executed_fixed_exit_net_dollars": float(executed["net_dollars"].sum()),
        "oracle_target_direction_match_count": int(len(target_match)),
        "oracle_target_direction_match_net_dollars": float(
            target_match["candidate_net_dollars"].sum()
        ),
        "oracle_target_direction_mismatch_count": int(len(target_mismatch)),
        "oracle_target_direction_mismatch_net_dollars": float(
            target_mismatch["candidate_net_dollars"].sum()
        ),
    }


def classify_rescue(
    *,
    policy: dict[str, Any],
    path: dict[str, Any],
    first_touch: dict[str, Any],
    bucket_rows: list[dict[str, Any]],
) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    stable_rows = [row for row in bucket_rows if row.get("stable_positive")]
    stable_families = sorted({str(row["bucket_family"]) for row in stable_rows})
    classifications: list[dict[str, str]] = [
        {
            "code": "DIAGNOSTIC_ONLY_NOT_V1_RESCUE",
            "metric": "v1_rescue_allowed=false",
            "explanation": "This audit can preserve research signal but cannot approve the failed v1 policy.",
        }
    ]
    first_touch_positive = _safe_int(first_touch.get("stop_first_positive_overall_grid_count")) > 0
    if not first_touch_positive:
        classifications.append(
            {
                "code": "FIRST_TOUCH_NO_GO_CONFIRMED",
                "metric": (
                    "positive stop-first grids "
                    f"{first_touch.get('stop_first_positive_overall_grid_count')}/"
                    f"{first_touch.get('grid_count')}"
                ),
                "explanation": "The already-tested simple TP/SL path-capture grid did not rescue v1.",
            }
        )
    optimistic_net = _safe_float(path.get("optimistic_mfe_capture_net_dollars"))
    if optimistic_net <= 0:
        classifications.append(
            {
                "code": "UPPER_BOUND_PATH_CAPTURE_NEGATIVE",
                "metric": f"optimistic MFE-capture net {_fmt_money(optimistic_net)}",
                "explanation": "Even optimistic path capture did not clear costs.",
            }
        )
        decision = "RETIRE_THESIS_REVIEW"
    else:
        classifications.append(
            {
                "code": "UPPER_BOUND_PATH_CAPTURE_POSITIVE_NON_TRADABLE",
                "metric": f"optimistic MFE-capture net {_fmt_money(optimistic_net)}",
                "explanation": "The path contained value, but this is an oracle upper bound, not tradable proof.",
            }
        )
        decision = "V1_NOT_RESCUED_V2_HYPOTHESIS_REQUIRED"
    if stable_rows:
        classifications.append(
            {
                "code": "PRETRADE_STABLE_BUCKETS_PRESENT",
                "metric": (
                    f"stable positive buckets {len(stable_rows)} across "
                    f"{len(stable_families)} families"
                ),
                "explanation": "Some predeclared pre-trade buckets may justify a separate v2 packet.",
            }
        )
    else:
        classifications.append(
            {
                "code": "PRETRADE_STABLE_BUCKETS_ABSENT",
                "metric": "stable positive buckets 0",
                "explanation": "No predeclared pre-trade bucket met the fold-stability and size screen.",
            }
        )
    if str(first_touch.get("screen_status")) == "LOWER_TIMEFRAME_REQUIRED_AMBIGUITY_ONLY":
        classifications.append(
            {
                "code": "LOWER_TIMEFRAME_REQUIRED",
                "metric": "first-touch screen status LOWER_TIMEFRAME_REQUIRED_AMBIGUITY_ONLY",
                "explanation": "Any apparent rescue depends on intrabar ordering that OHLC bars cannot prove.",
            }
        )
    v2_packet_review_allowed = bool(len(stable_rows) >= 2 and len(stable_families) >= 2)
    if v2_packet_review_allowed:
        decision = "V2_PACKET_REVIEW_READY"
    support = {
        "decision": decision,
        "v1_rescue_allowed": False,
        "v2_packet_review_allowed": v2_packet_review_allowed,
        "stable_positive_bucket_count": int(len(stable_rows)),
        "stable_positive_bucket_family_count": int(len(stable_families)),
        "stable_positive_bucket_families": stable_families,
        "selected_bucket": None,
        "selected_tp_sl": None,
        "tuning_or_selection_allowed": False,
        "promotion_allowed": False,
        "registry_status_mutation_allowed": False,
        "live_execution_ready": False,
    }
    return decision, classifications, support


def build_payload(
    *,
    hypothesis_id: str,
    run: str,
    paths: RescuePaths,
    market: str,
    target_name: str,
    min_bucket_trades: int,
    min_positive_folds: int,
) -> dict[str, Any]:
    for path, label in (
        (paths.predictions, "predictions"),
        (paths.predictions_manifest, "prediction manifest"),
        (paths.wfa_report, "WFA report"),
        (paths.policy_diagnostics, "policy diagnostics"),
        (paths.trades, "trades"),
        (paths.bars, "bars"),
        (paths.costs_config, "costs config"),
        (paths.first_touch_diagnostics, "first-touch diagnostics"),
        (paths.first_touch_grid, "first-touch grid"),
    ):
        if not path.exists():
            raise ValueError(f"missing required {label}: {_relative(path)}")
    manifest = _read_json_required(paths.predictions_manifest, "prediction manifest")
    wfa_report = _read_json_required(paths.wfa_report, "WFA report")
    policy_diagnostics = _read_json_required(paths.policy_diagnostics, "policy diagnostics")
    costs = load_cost_config(paths.costs_config, market)
    predictions = load_predictions(paths.predictions)
    bars = load_bars(paths.bars)
    target_context = load_target_context(paths.bars)
    trades = load_trades_no_count(paths.trades)
    policy_context = build_policy_context(
        predictions,
        target_context,
        costs=costs,
        costs_config=paths.costs_config,
        target_name=target_name,
    )
    policy = overall_policy_summary(policy_context)
    path = executed_path_summary(
        policy_context=policy_context,
        trades=trades,
        bars=bars,
        costs=costs,
    )
    first_touch = first_touch_summary(paths.first_touch_diagnostics, paths.first_touch_grid)
    bucket_rows = summarize_pretrade_buckets(
        policy_context,
        min_bucket_trades=min_bucket_trades,
        min_positive_folds=min_positive_folds,
    )
    decision, classifications, support = classify_rescue(
        policy=policy,
        path=path,
        first_touch=first_touch,
        bucket_rows=bucket_rows,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "diagnostic_type": DIAGNOSTIC_TYPE,
        "diagnostic_only": True,
        "hypothesis_id": hypothesis_id,
        "run": run,
        "target_name": target_name,
        "market": market,
        "failure_count": 0,
        "decision": decision,
        "decision_support": support,
        "classifications": classifications,
        "audit_policy": {
            "scope": "predeclared diagnostic buckets and non-tradable oracle upper bounds only",
            "min_bucket_trades": int(min_bucket_trades),
            "min_positive_folds": int(min_positive_folds),
            "post_hoc_winner_selection_allowed": False,
            "v1_policy_rescue_allowed": False,
        },
        "cost_model": {
            "tick_size": costs.tick_size,
            "tick_value": costs.tick_value,
            "round_turn_cost_dollars": costs.round_turn_cost_dollars,
            "round_turn_cost_ticks": costs.round_turn_cost_ticks,
        },
        "wfa": {
            "prediction_count": _safe_int(manifest.get("prediction_count")),
            "fold_count": _safe_int(manifest.get("fold_count")),
            "model_ids": manifest.get("model_ids") or [],
            "target_names": manifest.get("target_names") or [],
            "artifact_evidence_ready": bool(manifest.get("artifact_evidence_ready")),
            "model_risk_gate": (wfa_report.get("model_risk_gate") or {}).get("status"),
        },
        "policy_diagnostics_review": {
            "failure_count": _safe_int(policy_diagnostics.get("failure_count")),
            "fixed_exit_policy_mismatch": bool(policy_diagnostics.get("fixed_exit_policy_mismatch")),
            "economic_approval_allowed": bool(policy_diagnostics.get("economic_approval_allowed")),
            "economic_rejection_allowed": bool(policy_diagnostics.get("economic_rejection_allowed")),
            "diagnostics_path": _relative(paths.policy_diagnostics),
        },
        "overall_policy": policy,
        "executed_path_upper_bound": path,
        "first_touch": first_touch,
        "pretrade_bucket_summaries": bucket_rows,
        "input_file_hashes": _file_hash_map(
            [
                paths.predictions,
                paths.predictions_manifest,
                paths.wfa_report,
                paths.policy_diagnostics,
                paths.trades,
                paths.bars,
                paths.costs_config,
                paths.first_touch_diagnostics,
                paths.first_touch_grid,
            ]
        ),
        "output_paths": {
            "json": _relative(paths.json_out),
            "md": _relative(paths.md_out),
        },
    }


def _classification_rows(payload: dict[str, Any]) -> list[list[object]]:
    return [
        [item["code"], item["metric"], item["explanation"]]
        for item in payload["classifications"]
    ]


def _bucket_rows(payload: dict[str, Any]) -> list[list[object]]:
    rows: list[list[object]] = []
    for item in payload["pretrade_bucket_summaries"]:
        if bool(item.get("stable_positive")):
            rows.append(
                [
                    item["bucket_family"],
                    item["bucket"],
                    item["candidate_trade_count"],
                    item["positive_fold_count"],
                    _fmt_money(item["net_dollars"]),
                    _fmt_num(item["mean_fixed_exit_ticks"]),
                ]
            )
    return rows


def build_markdown(payload: dict[str, Any]) -> str:
    policy = payload["overall_policy"]
    path = payload["executed_path_upper_bound"]
    first_touch = payload["first_touch"]
    support = payload["decision_support"]
    lines: list[str] = [
        f"# {payload['hypothesis_id']} Rescue Feasibility Audit",
        "",
        "## Summary",
        "",
        "This is a diagnostic-only salvage audit. It can show whether the research idea deserves a separate v2 packet, but it cannot rescue v1, select a bucket, select TP/SL parameters, promote a model, or approve paper/live trading.",
        "",
        f"- Decision: `{payload['decision']}`.",
        f"- V1 rescue allowed: `{support['v1_rescue_allowed']}`.",
        f"- V2 packet review allowed: `{support['v2_packet_review_allowed']}`.",
        f"- Candidate trade rate: `{_fmt_pct(policy['candidate_trade_rate'])}`.",
        f"- Fixed-exit executed net: `{_fmt_money(policy['executed_fixed_exit_net_dollars'])}`.",
        f"- Optimistic MFE-capture net upper bound: `{_fmt_money(path['optimistic_mfe_capture_net_dollars'])}`.",
        f"- First-touch positive stop-first grids: `{first_touch['stop_first_positive_overall_grid_count']}/{first_touch['grid_count']}`.",
        "",
        "## Classifications",
        "",
    ]
    lines.extend(_markdown_table(["Code", "Trigger Metric", "Plain English"], _classification_rows(payload)))
    lines.extend(
        [
            "",
            "## What This Audit Tested",
            "",
            "| Layer | Test | Decisive? |",
            "| --- | --- | --- |",
            "| Oracle path capture | What if executed trades captured MFE perfectly after costs? | No. This is an upper bound. |",
            "| Pre-trade buckets | Fold, side, hour, confidence, margin, and opening-range-distance buckets. | No. Buckets can only justify a separate v2 packet. |",
            "| First-touch evidence | Existing TP/SL grid under stop-first and ambiguous-excluded logic. | No promotion. It can block naive TP/SL rescue. |",
            "",
            "## Overall Evidence",
            "",
        ]
    )
    overall_rows = [
        ["Predictions", policy["prediction_row_count"]],
        ["Candidate trades", policy["candidate_trade_count"]],
        ["Executed trades", policy["executed_trade_count"]],
        ["Candidate fixed-exit net", _fmt_money(policy["candidate_fixed_exit_net_dollars"])],
        ["Executed fixed-exit net", _fmt_money(policy["executed_fixed_exit_net_dollars"])],
        ["Oracle target-direction match net", _fmt_money(policy["oracle_target_direction_match_net_dollars"])],
        ["Oracle target-direction mismatch net", _fmt_money(policy["oracle_target_direction_mismatch_net_dollars"])],
    ]
    lines.extend(_markdown_table(["Metric", "Value"], overall_rows))
    lines.extend(
        [
            "",
            "## Path Upper Bound",
            "",
            f"- Optimistic MFE-capture gross: `{_fmt_money(path['optimistic_mfe_capture_gross_dollars'])}`.",
            f"- Optimistic MFE-capture net: `{_fmt_money(path['optimistic_mfe_capture_net_dollars'])}`.",
            f"- Positive folds under optimistic MFE capture: `{path['optimistic_mfe_capture_positive_fold_count']}`.",
            f"- Median MFE / MAE / realized / giveback ticks: `{_fmt_num(path['median_mfe_ticks'])}` / `{_fmt_num(path['median_mae_ticks'])}` / `{_fmt_num(path['median_realized_ticks'])}` / `{_fmt_num(path['median_giveback_ticks'])}`.",
            "",
            "Plain English: this section asks whether there was enough movement in the path to be worth learning from. It is not a tradable result because it assumes favorable excursion could be captured.",
            "",
            "## Stable Pre-Trade Buckets",
            "",
        ]
    )
    stable_rows = _bucket_rows(payload)
    if stable_rows:
        lines.extend(
            _markdown_table(
                ["Family", "Bucket", "Candidate Trades", "Positive Folds", "Net", "Mean Fixed-Exit Ticks"],
                stable_rows,
            )
        )
    else:
        lines.append("- No predeclared bucket met the stable-positive screen.")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- No selected bucket is produced.",
            "- No selected TP/SL pair is produced.",
            "- No tuning, registry/status mutation, promotion, paper trading, or live trading is approved.",
            "- Any v2 must be a separately approved hypothesis with target and policy aligned before WFA/modeling.",
            "",
        ]
    )
    return "\n".join(lines)


def run_rescue_audit(
    *,
    hypothesis_id: str,
    run: str,
    paths: RescuePaths,
    market: str,
    target_name: str = DEFAULT_TARGET_NAME,
    min_bucket_trades: int = 50,
    min_positive_folds: int = 3,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    if not allow_overwrite:
        _validate_outputs_absent((paths.json_out, paths.md_out))
    payload = _json_ready(
        build_payload(
            hypothesis_id=hypothesis_id,
            run=run,
            paths=paths,
            market=market,
            target_name=target_name,
            min_bucket_trades=min_bucket_trades,
            min_positive_folds=min_positive_folds,
        )
    )
    markdown = build_markdown(payload)
    paths.json_out.parent.mkdir(parents=True, exist_ok=True)
    _write_json(paths.json_out, payload)
    paths.md_out.write_text(markdown, encoding="utf-8")
    payload["json_output_path"] = paths.json_out
    payload["md_output_path"] = paths.md_out
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis-id", default=DEFAULT_HYPOTHESIS_ID)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--predictions-manifest", type=Path)
    parser.add_argument("--wfa-report", type=Path)
    parser.add_argument("--policy-diagnostics", type=Path)
    parser.add_argument("--trades", type=Path)
    parser.add_argument("--bars", type=Path)
    parser.add_argument("--costs-config", type=Path)
    parser.add_argument("--first-touch-diagnostics", type=Path)
    parser.add_argument("--first-touch-grid", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--market", default=DEFAULT_MARKET)
    parser.add_argument("--target-name", default=DEFAULT_TARGET_NAME)
    parser.add_argument("--min-bucket-trades", type=int, default=50)
    parser.add_argument("--min-positive-folds", type=int, default=3)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser


def _paths_from_args(args: argparse.Namespace) -> RescuePaths:
    defaults = default_paths(args.hypothesis_id, args.run)
    return RescuePaths(
        predictions=_resolve(args.predictions or defaults.predictions),
        predictions_manifest=_resolve(args.predictions_manifest or defaults.predictions_manifest),
        wfa_report=_resolve(args.wfa_report or defaults.wfa_report),
        policy_diagnostics=_resolve(args.policy_diagnostics or defaults.policy_diagnostics),
        trades=_resolve(args.trades or defaults.trades),
        bars=_resolve(args.bars or defaults.bars),
        costs_config=_resolve(args.costs_config or defaults.costs_config),
        first_touch_diagnostics=_resolve(
            args.first_touch_diagnostics or defaults.first_touch_diagnostics
        ),
        first_touch_grid=_resolve(args.first_touch_grid or defaults.first_touch_grid),
        json_out=_resolve(args.json_out or defaults.json_out),
        md_out=_resolve(args.md_out or defaults.md_out),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    paths = _paths_from_args(args)
    try:
        result = run_rescue_audit(
            hypothesis_id=args.hypothesis_id,
            run=args.run,
            paths=paths,
            market=args.market,
            target_name=args.target_name,
            min_bucket_trades=args.min_bucket_trades,
            min_positive_folds=args.min_positive_folds,
            allow_overwrite=args.allow_overwrite,
        )
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"NO_GO candidate rescue feasibility: {exc}")
        return 1
    support = result["decision_support"]
    print(
        "WROTE candidate rescue feasibility:",
        f"decision={result['decision']}",
        f"v2_packet_review_allowed={support['v2_packet_review_allowed']}",
        f"stable_buckets={support['stable_positive_bucket_count']}",
        f"json={_relative(result['json_output_path'])}",
        f"md={_relative(result['md_output_path'])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
