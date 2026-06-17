#!/usr/bin/env python3
"""Phase 9 directional path-quality target-construction harness.

This is a bounded feasibility harness. It does not run WFA, does not use saved
predictions, and reports target/oracle feasibility diagnostics only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts.phase7_wfa.run_wfa import (
    DEFAULT_INPUT_ROOT,
    DEFAULT_SPLIT_PLAN,
    _file_hash_map,
    _fold_masks,
    _load_market_frame,
    _relative_path,
    load_feature_cols,
)
from scripts.phase9_research.tier1_cost_clearability_event_harness import (
    DEFAULT_COSTS_CONFIG,
    DEFAULT_PROFILE,
    DEFAULT_PROFILE_CONFIG,
    DEFAULT_REPORTS_ROOT,
    _load_split_folds,
    _parse_csv,
    _timestamp,
    assign_fold_stages,
    resolve_profile,
)


HYPOTHESIS_ID = "directional_path_quality_target_v1"
DEFAULT_RUN = HYPOTHESIS_ID
DEFAULT_TARGET_REGISTRY = Path("manifests/target_hypotheses/registry.json")
DEFAULT_TARGET_TRIALS = Path("manifests/target_hypotheses/trial_statuses.jsonl")

LABEL_COLUMN = "directional_path_quality_label"
DIRECTION_COLUMN = "directional_path_quality_direction"
FIRST_HIT_PROXY_COLUMN = "first_hit_proxy_positive"
EVENT_HOUR_COLUMN = "event_hour"
QUALITY_GROSS_COLUMN = "target_quality_oracle_gross_dollars"
QUALITY_COST_COLUMN = "target_quality_oracle_cost_dollars"
QUALITY_NET_COLUMN = "target_quality_oracle_net_dollars"

REQUIRED_CONTROLS = (
    "random_label",
    "shuffled_feature",
    "market_year_session_baseline",
    "current_deadzone_baseline",
    "inverse_score",
    "no_trade_baseline",
)
BUCKETS: tuple[tuple[str, float | None], ...] = (
    ("all_events", None),
    ("top_1pct", 0.01),
    ("top_5pct", 0.05),
    ("top_10pct", 0.10),
)
LEAKAGE_PREFIXES = ("target", "label", "future", "entry", "exit")
LEAKAGE_SUBSTRINGS = (
    "forward",
    "gross",
    "net",
    "pnl",
    "profit",
    "cost",
    "mfe",
    "mae",
)
REQUIRED_EVENT_COLUMNS = (
    "ts",
    "market",
    "year",
    "session_segment_id",
    "causal_valid",
    "valid_ohlcv",
    "inside_session",
    "feature_input_valid",
    "feature_row_valid",
    "training_row_valid",
    "target_valid",
    "target_entry_ts",
    "target_exit_ts",
    "target_ret_ticks_15m",
    "target_gross_dollars_15m",
    "target_estimated_cost_ticks",
    "target_estimated_cost_dollars",
    "target_sign_with_deadzone",
    "mfe_ticks_15m",
    "mae_ticks_15m",
    "target_fade_success_15m",
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root is not an object: {_relative_path(path)}")
    return payload


def _finite_float(value: object) -> float | None:
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


def _safe_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _stable_seed(seed: int, fold_id: str, control: str) -> int:
    digest = hashlib.sha256(f"{seed}:{fold_id}:{control}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def validate_target_hypothesis_registered(registry_path: Path = DEFAULT_TARGET_REGISTRY) -> list[str]:
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
        if row.get("status") != "CANDIDATE":
            return [f"{HYPOTHESIS_ID}: expected CANDIDATE status before harness run"]
        if row.get("wfa_allowed") is not False:
            return [f"{HYPOTHESIS_ID}: wfa_allowed must be false before freeze"]
        return []
    return [f"{HYPOTHESIS_ID}: missing from target hypothesis registry"]


def load_market_target_configs(costs_config: Path, markets: Sequence[str]) -> dict[str, dict[str, float]]:
    import yaml

    payload = yaml.safe_load(costs_config.read_text(encoding="utf-8")) or {}
    raw_markets = payload.get("markets", {})
    if not isinstance(raw_markets, Mapping):
        raise SystemExit("costs config missing markets mapping")
    configs: dict[str, dict[str, float]] = {}
    for market in markets:
        raw = raw_markets.get(market)
        if not isinstance(raw, Mapping):
            raise SystemExit(f"missing cost config for market: {market}")
        cost_dollars = _finite_float(raw.get("round_turn_cost_dollars"))
        tick_value = _finite_float(raw.get("tick_value"))
        min_profit_ticks = _finite_float(raw.get("min_profit_ticks"))
        if cost_dollars is None or cost_dollars <= 0:
            raise SystemExit(f"invalid round_turn_cost_dollars for market: {market}")
        if tick_value is None or tick_value <= 0:
            raise SystemExit(f"invalid tick_value for market: {market}")
        if min_profit_ticks is None or min_profit_ticks < 0:
            raise SystemExit(f"invalid min_profit_ticks for market: {market}")
        configs[market] = {
            "round_turn_cost_dollars": cost_dollars,
            "estimated_cost_ticks": cost_dollars / tick_value,
            "min_profit_ticks": min_profit_ticks,
            "tick_value": tick_value,
        }
    return configs


def is_leakage_feature(column: str) -> bool:
    value = column.lower()
    if value in {LABEL_COLUMN, DIRECTION_COLUMN, QUALITY_GROSS_COLUMN, QUALITY_COST_COLUMN, QUALITY_NET_COLUMN}:
        return True
    if any(value.startswith(prefix) for prefix in LEAKAGE_PREFIXES):
        return True
    return any(item in value for item in LEAKAGE_SUBSTRINGS)


def select_model_features(feature_cols: Sequence[str]) -> list[str]:
    return [column for column in feature_cols if column.startswith("feature_") and not is_leakage_feature(column)]


def _source_columns(features: Sequence[str]) -> list[str]:
    return sorted(set(features) | set(REQUIRED_EVENT_COLUMNS) | {"is_synthetic", "roll_window_flag", "boundary_session_flag"})


def _valid_event_mask(df: pd.DataFrame) -> pd.Series:
    mask = pd.Series(True, index=df.index, dtype=bool)
    for column in REQUIRED_EVENT_COLUMNS:
        if column not in df.columns:
            return pd.Series(False, index=df.index, dtype=bool)
        mask &= df[column].notna()
    mask &= _bool_col(df, "target_valid", False)
    mask &= _bool_col(df, "causal_valid", False)
    mask &= _bool_col(df, "valid_ohlcv", True)
    mask &= _bool_col(df, "inside_session", True)
    mask &= _bool_col(df, "feature_input_valid", False)
    mask &= _bool_col(df, "feature_row_valid", True)
    mask &= ~_bool_col(df, "is_synthetic", False)
    mask &= ~_bool_col(df, "roll_window_flag", False)
    mask &= ~_bool_col(df, "boundary_session_flag", False)
    return mask


def apply_directional_path_quality_labels(
    frame: pd.DataFrame,
    market_configs: Mapping[str, Mapping[str, float]],
) -> pd.DataFrame:
    out = frame.copy()
    out["target_entry_ts"] = pd.to_datetime(out["target_entry_ts"], utc=True, errors="coerce")
    out["target_exit_ts"] = pd.to_datetime(out["target_exit_ts"], utc=True, errors="coerce")
    ret_ticks = _safe_numeric(out, "target_ret_ticks_15m")
    gross_dollars = _safe_numeric(out, "target_gross_dollars_15m")
    mfe_ticks = _safe_numeric(out, "mfe_ticks_15m")
    mae_ticks = _safe_numeric(out, "mae_ticks_15m")
    configured_cost_ticks = out["market"].map(
        {market: float(config["estimated_cost_ticks"]) for market, config in market_configs.items()}
    )
    configured_cost_dollars = out["market"].map(
        {market: float(config["round_turn_cost_dollars"]) for market, config in market_configs.items()}
    )
    min_profit_ticks = out["market"].map(
        {market: float(config["min_profit_ticks"]) for market, config in market_configs.items()}
    )
    cost_ticks = _safe_numeric(out, "target_estimated_cost_ticks").where(
        _safe_numeric(out, "target_estimated_cost_ticks") > 0,
        configured_cost_ticks,
    )
    cost_dollars = _safe_numeric(out, "target_estimated_cost_dollars").where(
        _safe_numeric(out, "target_estimated_cost_dollars") > 0,
        configured_cost_dollars,
    )

    long_adverse = (-mae_ticks).clip(lower=0.0)
    long_favorable = mfe_ticks.clip(lower=0.0)
    short_adverse = mfe_ticks.clip(lower=0.0)
    short_favorable = (-mae_ticks).clip(lower=0.0)
    threshold = cost_ticks + min_profit_ticks
    long_label = (
        (ret_ticks > threshold)
        & (long_adverse <= cost_ticks)
        & (long_favorable >= 2.0 * long_adverse.clip(lower=1.0))
    )
    short_label = (
        (ret_ticks < -threshold)
        & (short_adverse <= cost_ticks)
        & (short_favorable >= 2.0 * short_adverse.clip(lower=1.0))
    )
    valid = _valid_event_mask(out)
    long_label &= valid
    short_label &= valid
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(long_label, 1)
    direction = direction.mask(short_label, -1)
    label = direction.ne(0)

    out[QUALITY_COST_COLUMN] = cost_dollars
    out[DIRECTION_COLUMN] = direction
    out[LABEL_COLUMN] = label
    out[QUALITY_GROSS_COLUMN] = gross_dollars.abs().where(label, 0.0)
    out[QUALITY_NET_COLUMN] = out[QUALITY_GROSS_COLUMN] - out[QUALITY_COST_COLUMN]
    out[FIRST_HIT_PROXY_COLUMN] = _bool_col(out, "target_fade_success_15m", False) & valid
    out[EVENT_HOUR_COLUMN] = out["target_entry_ts"].dt.hour
    return out


def non_overlapping_events(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    frame = frame.reset_index(drop=True).copy()
    valid = frame.loc[_valid_event_mask(frame)].copy()
    group_cols = ["market", "year", "session_segment_id"]
    group_ends = (
        frame.assign(ts=pd.to_datetime(frame["ts"], utc=True, errors="coerce"))
        .groupby(group_cols, dropna=False)["ts"]
        .max()
    )
    selected_indices: list[int] = []
    skipped = 0
    for key, group in valid.groupby(group_cols, dropna=False, sort=False):
        group = group.sort_values("target_entry_ts", kind="mergesort")
        group_end = group_ends.get(key)
        last_exit: pd.Timestamp | None = None
        for row in group.itertuples():
            entry_ts = row.target_entry_ts
            exit_ts = row.target_exit_ts
            if pd.isna(entry_ts) or pd.isna(exit_ts) or exit_ts <= entry_ts:
                skipped += 1
                continue
            if pd.notna(group_end) and exit_ts > group_end:
                skipped += 1
                continue
            if last_exit is not None and entry_ts <= last_exit:
                skipped += 1
                continue
            selected_indices.append(int(row.Index))
            last_exit = exit_ts
    events = frame.loc[selected_indices].sort_values(
        ["market", "year", "target_entry_ts"],
        kind="mergesort",
    )
    return events.reset_index(drop=True), skipped


def _fit_logistic(x_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    if y_train.nunique(dropna=True) < 2:
        raise ValueError("train labels contain fewer than two classes")
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=500, random_state=0)),
        ]
    )
    model.fit(x_train, y_train.astype(int))
    return model


def _shuffled_features(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    shuffled = frame.copy()
    for column in shuffled.columns:
        shuffled[column] = rng.permutation(shuffled[column].to_numpy())
    return shuffled


def _group_rate_scores(
    train: pd.DataFrame,
    test: pd.DataFrame,
    label_column: str,
) -> np.ndarray:
    global_rate = float(train[label_column].mean()) if len(train) else 0.0
    by_market_year_hour = train.groupby(["market", "year", EVENT_HOUR_COLUMN], dropna=False)[
        label_column
    ].mean()
    by_market_hour = train.groupby(["market", EVENT_HOUR_COLUMN], dropna=False)[label_column].mean()
    by_market = train.groupby(["market"], dropna=False)[label_column].mean()
    scores: list[float] = []
    for row in test.itertuples():
        value = by_market_year_hour.get((row.market, row.year, row.event_hour))
        if value is None or pd.isna(value):
            value = by_market_hour.get((row.market, row.event_hour))
        if value is None or pd.isna(value):
            value = by_market.get(row.market, global_rate)
        scores.append(float(value if pd.notna(value) else global_rate))
    return np.asarray(scores, dtype=float)


def _select_bucket(scored: pd.DataFrame, score_col: str, fraction: float | None) -> pd.DataFrame:
    if fraction is None:
        return scored.copy()
    count = int(math.ceil(len(scored) * fraction)) if len(scored) else 0
    if count <= 0:
        return scored.iloc[0:0].copy()
    return scored.nlargest(count, score_col, keep="first").copy()


def _bucket_metrics(selected: pd.DataFrame) -> dict[str, Any]:
    count = int(len(selected))
    if count == 0:
        return {
            "selected_event_count": 0,
            "target_positive_count": 0,
            "target_precision": None,
            "target_quality_oracle_gross_upper_bound": 0.0,
            "target_quality_oracle_cost_dollars": 0.0,
            "target_quality_oracle_net_upper_bound": 0.0,
            "target_quality_oracle_net_upper_bound_per_event": None,
            "cost_drag": None,
            "long_label_count": 0,
            "short_label_count": 0,
        }
    labels = selected[LABEL_COLUMN].astype(bool)
    gross = float(pd.to_numeric(selected[QUALITY_GROSS_COLUMN], errors="coerce").fillna(0.0).sum())
    cost = float(pd.to_numeric(selected[QUALITY_COST_COLUMN], errors="coerce").fillna(0.0).sum())
    net = float(gross - cost)
    direction = pd.to_numeric(selected[DIRECTION_COLUMN], errors="coerce").fillna(0)
    return {
        "selected_event_count": count,
        "target_positive_count": int(labels.sum()),
        "target_precision": float(labels.mean()),
        "target_quality_oracle_gross_upper_bound": gross,
        "target_quality_oracle_cost_dollars": cost,
        "target_quality_oracle_net_upper_bound": net,
        "target_quality_oracle_net_upper_bound_per_event": float(net / count),
        "cost_drag": float(cost / gross) if gross > 0 else None,
        "long_label_count": int((direction > 0).sum()),
        "short_label_count": int((direction < 0).sum()),
    }


def _evaluate_score_columns(scored: pd.DataFrame, score_columns: Mapping[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, column in score_columns.items():
        out[name] = {
            bucket_name: _bucket_metrics(_select_bucket(scored, column, fraction))
            for bucket_name, fraction in BUCKETS
        }
    return out


def _fold_result(
    *,
    fold: Mapping[str, Any],
    stage: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: Sequence[str],
    seed: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    fold_id = str(fold["fold_id"])
    x_train = train[list(features)]
    x_test = test[list(features)]
    y_train = train[LABEL_COLUMN].astype(int)

    model = _fit_logistic(x_train, y_train)
    model_score = model.predict_proba(x_test)[:, 1]

    rng = np.random.default_rng(_stable_seed(seed, fold_id, "random_label"))
    random_y = pd.Series(rng.permutation(y_train.to_numpy()), index=y_train.index)
    random_model = _fit_logistic(x_train, random_y)
    random_score = random_model.predict_proba(x_test)[:, 1]

    shuffled_model = _fit_logistic(
        _shuffled_features(x_train, _stable_seed(seed, fold_id, "shuffled_feature")),
        y_train,
    )
    shuffled_score = shuffled_model.predict_proba(x_test)[:, 1]
    baseline_score = _group_rate_scores(train, test, LABEL_COLUMN)
    deadzone_train = train.assign(
        current_deadzone_positive=pd.to_numeric(
            train["target_sign_with_deadzone"],
            errors="coerce",
        ).fillna(0).ne(0)
    )
    deadzone_score = _group_rate_scores(deadzone_train, test, "current_deadzone_positive")

    scored = test.copy()
    scored["model_score"] = model_score
    scored["random_label_score"] = random_score
    scored["shuffled_feature_score"] = shuffled_score
    scored["market_year_session_baseline_score"] = baseline_score
    scored["current_deadzone_baseline_score"] = deadzone_score
    scored["inverse_score"] = -model_score
    scored["no_trade_baseline_score"] = 0.0
    scored["fold_id"] = fold_id
    scored["stage"] = stage
    score_columns = {
        "model": "model_score",
        "random_label": "random_label_score",
        "shuffled_feature": "shuffled_feature_score",
        "market_year_session_baseline": "market_year_session_baseline_score",
        "current_deadzone_baseline": "current_deadzone_baseline_score",
        "inverse_score": "inverse_score",
        "no_trade_baseline": "no_trade_baseline_score",
    }
    metrics = _evaluate_score_columns(scored, score_columns)
    model_top_5 = _select_bucket(scored, "model_score", 0.05)
    result = {
        "fold_id": fold_id,
        "stage": stage,
        "market": str(fold["market"]),
        "train_event_count": int(len(train)),
        "scored_event_count": int(len(test)),
        "positive_train_rate": float(y_train.mean()) if len(y_train) else None,
        "positive_test_rate": float(test[LABEL_COLUMN].mean()) if len(test) else None,
        "bucket_metrics": metrics,
        "positive_top_5pct": bool(
            metrics["model"]["top_5pct"]["target_quality_oracle_net_upper_bound"] > 0
        ),
    }
    return result, model_top_5


def _sum_bucket(rows: Sequence[Mapping[str, Any]], scorer: str, bucket: str) -> dict[str, Any]:
    selected = sum(int(item["bucket_metrics"][scorer][bucket]["selected_event_count"]) for item in rows)
    positives = sum(int(item["bucket_metrics"][scorer][bucket]["target_positive_count"]) for item in rows)
    gross = sum(
        float(item["bucket_metrics"][scorer][bucket]["target_quality_oracle_gross_upper_bound"])
        for item in rows
    )
    cost = sum(
        float(item["bucket_metrics"][scorer][bucket]["target_quality_oracle_cost_dollars"])
        for item in rows
    )
    net = gross - cost
    return {
        f"{bucket}_selected_event_count": selected,
        f"{bucket}_target_positive_count": positives,
        f"{bucket}_target_precision": float(positives / selected) if selected else None,
        f"{bucket}_target_quality_oracle_gross_upper_bound": float(gross),
        f"{bucket}_target_quality_oracle_cost_dollars": float(cost),
        f"{bucket}_target_quality_oracle_net_upper_bound": float(net),
        f"{bucket}_target_quality_oracle_net_upper_bound_per_event": (
            float(net / selected) if selected else None
        ),
        f"{bucket}_cost_drag": float(cost / gross) if gross > 0 else None,
    }


def _stage_summaries(fold_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for stage in ("discovery", "confirmation"):
        rows = [item for item in fold_results if item["stage"] == stage]
        out[stage] = {
            "stage": stage,
            "fold_count": len(rows),
            "scored_event_count": sum(int(item["scored_event_count"]) for item in rows),
            "positive_top_5pct_fold_count": sum(1 for item in rows if item["positive_top_5pct"]),
            "scorers": {
                scorer: _sum_bucket(rows, scorer, "top_5pct")
                for scorer in ("model", *REQUIRED_CONTROLS)
            },
        }
    return out


def _market_stage_summaries(
    fold_results: Sequence[Mapping[str, Any]],
    markets: Sequence[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for market in markets:
        out[market] = {}
        for stage in ("discovery", "confirmation"):
            rows = [
                item
                for item in fold_results
                if item["market"] == market and item["stage"] == stage
            ]
            out[market][stage] = {
                "fold_count": len(rows),
                "scored_event_count": sum(int(item["scored_event_count"]) for item in rows),
                "scorers": {
                    scorer: _sum_bucket(rows, scorer, "top_5pct")
                    for scorer in ("model", *REQUIRED_CONTROLS)
                },
            }
    return out


def _event_counts(events: pd.DataFrame, folds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if events.empty:
        return {"by_market": {}, "by_market_year": [], "by_fold": []}
    by_market = {
        str(market): int(len(group))
        for market, group in events.groupby("market", dropna=False, sort=True)
    }
    by_market_year = [
        {"market": str(market), "year": int(year), "event_count": int(len(group))}
        for (market, year), group in events.groupby(["market", "year"], dropna=False, sort=True)
    ]
    by_fold: list[dict[str, Any]] = []
    for fold in folds:
        market_events = events[events["market"].astype(str) == str(fold["market"])]
        y = market_events[LABEL_COLUMN].astype(int)
        _, test_mask = _fold_masks(market_events, fold, y)
        by_fold.append(
            {
                "fold_id": str(fold["fold_id"]),
                "market": str(fold["market"]),
                "event_count": int(test_mask.sum()),
            }
        )
    return {"by_market": by_market, "by_market_year": by_market_year, "by_fold": by_fold}


def _class_balance(events: pd.DataFrame) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for market, group in events.groupby("market", dropna=False, sort=True):
        direction = pd.to_numeric(group[DIRECTION_COLUMN], errors="coerce").fillna(0)
        rows.append(
            {
                "market": str(market),
                "event_count": int(len(group)),
                "quality_count": int(group[LABEL_COLUMN].astype(bool).sum()),
                "quality_rate": float(group[LABEL_COLUMN].mean()) if len(group) else None,
                "long_count": int((direction > 0).sum()),
                "short_count": int((direction < 0).sum()),
            }
        )
    return {"by_market": rows}


def _duplicate_target_overlap(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty or FIRST_HIT_PROXY_COLUMN not in events.columns:
        return {"available": False, "overlap_with_first_hit_proxy": None}
    quality = events[LABEL_COLUMN].astype(bool)
    proxy = events[FIRST_HIT_PROXY_COLUMN].astype(bool)
    denominator = int(quality.sum())
    overlap = int((quality & proxy).sum())
    return {
        "available": True,
        "quality_count": denominator,
        "first_hit_proxy_count": int(proxy.sum()),
        "overlap_count": overlap,
        "overlap_with_first_hit_proxy": float(overlap / denominator) if denominator else None,
    }


def _concentration(selected_rows: pd.DataFrame) -> dict[str, Any]:
    if selected_rows.empty:
        empty = {"max_key": None, "max_share": None}
        return {
            "positive_target_quality_oracle_net": 0.0,
            "fold": dict(empty),
            "market": dict(empty),
            "hour": dict(empty),
            "side": dict(empty),
            "market_shares": {},
        }
    rows = selected_rows.copy()
    rows["row_quality_net"] = pd.to_numeric(rows[QUALITY_NET_COLUMN], errors="coerce").fillna(0.0)
    positive = rows[rows["row_quality_net"] > 0].copy()
    total = float(positive["row_quality_net"].sum()) if len(positive) else 0.0

    def max_share(column: str) -> dict[str, Any]:
        if total <= 0 or column not in positive.columns:
            return {"max_key": None, "max_share": None}
        grouped = positive.groupby(column, dropna=False)["row_quality_net"].sum()
        key = grouped.idxmax()
        return {"max_key": str(key), "max_share": float(grouped.max() / total)}

    market_shares: dict[str, float] = {}
    if total > 0:
        grouped_market = positive.groupby("market", dropna=False)["row_quality_net"].sum()
        market_shares = {str(key): float(value / total) for key, value in grouped_market.items()}
    return {
        "positive_target_quality_oracle_net": total,
        "fold": max_share("fold_id"),
        "market": max_share("market"),
        "hour": max_share(EVENT_HOUR_COLUMN),
        "side": max_share(DIRECTION_COLUMN),
        "market_shares": market_shares,
    }


def _top_5_by_market(fold_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in fold_results:
        market = str(item["market"])
        bucket = item["bucket_metrics"]["model"]["top_5pct"]
        current = out.setdefault(
            market,
            {
                "selected_event_count": 0,
                "target_positive_count": 0,
                "target_quality_oracle_gross_upper_bound": 0.0,
                "target_quality_oracle_cost_dollars": 0.0,
                "target_quality_oracle_net_upper_bound": 0.0,
            },
        )
        current["selected_event_count"] += int(bucket["selected_event_count"])
        current["target_positive_count"] += int(bucket["target_positive_count"])
        current["target_quality_oracle_gross_upper_bound"] += float(
            bucket["target_quality_oracle_gross_upper_bound"]
        )
        current["target_quality_oracle_cost_dollars"] += float(
            bucket["target_quality_oracle_cost_dollars"]
        )
        current["target_quality_oracle_net_upper_bound"] += float(
            bucket["target_quality_oracle_net_upper_bound"]
        )
    for current in out.values():
        selected = int(current["selected_event_count"])
        current["target_precision"] = (
            float(current["target_positive_count"] / selected) if selected else None
        )
    return out


def _limit_events_for_selected_folds(
    events: pd.DataFrame,
    folds: Sequence[Mapping[str, Any]],
    max_events_per_market: int | None,
) -> pd.DataFrame:
    if max_events_per_market is None or events.empty:
        return events
    selected_indices: list[int] = []
    for market, group in events.groupby("market", sort=False):
        market_folds = [fold for fold in folds if str(fold["market"]) == str(market)]
        if not market_folds:
            continue
        per_fold_quota = max(2, max_events_per_market // max(len(market_folds), 1))
        chosen: list[int] = []
        for fold in market_folds:
            y = group[LABEL_COLUMN].astype(int)
            train_mask, test_mask = _fold_masks(group, fold, y)
            train_idx = group.loc[train_mask].sort_values("target_entry_ts", kind="mergesort").index.tolist()
            test_idx = group.loc[test_mask].sort_values("target_entry_ts", kind="mergesort").index.tolist()
            per_side_quota = max(1, per_fold_quota // 2)
            chosen.extend(train_idx[-per_side_quota:])
            chosen.extend(test_idx[:per_side_quota])
        deduped = list(dict.fromkeys(chosen))
        if len(deduped) < max_events_per_market:
            chosen_set = set(deduped)
            fill = [idx for idx in group.index.tolist() if idx not in chosen_set]
            deduped.extend(fill[: max_events_per_market - len(deduped)])
        selected_indices.extend(deduped[:max_events_per_market])
    return events.loc[selected_indices].sort_values(
        ["market", "year", "target_entry_ts"],
        kind="mergesort",
    ).reset_index(drop=True)


def evaluate_gates(report: Mapping[str, Any]) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []
    failures = list(report.get("failures", []))
    markets = list(report["scope"]["markets"])
    class_rows = {
        row["market"]: row
        for row in report.get("class_balance", {}).get("by_market", [])
        if isinstance(row, Mapping)
    }
    market_stage = report["market_stage_summaries"]
    concentration = report["concentration"]

    gates.append(
        {
            "gate": "schema_registry_and_inputs_valid",
            "pass": not failures,
            "failure_decision": "STOP",
            "failures": failures,
        }
    )

    underpowered = []
    for market in markets:
        row = class_rows.get(market, {})
        if int(row.get("quality_count", 0)) < 5000:
            underpowered.append(f"{market}:quality_count")
        if int(row.get("long_count", 0)) < 1500:
            underpowered.append(f"{market}:long_count")
        if int(row.get("short_count", 0)) < 1500:
            underpowered.append(f"{market}:short_count")
    gates.append(
        {
            "gate": "minimum_quality_events_and_sides_by_market",
            "pass": not underpowered,
            "failure_decision": "STOP_UNDERPOWERED",
            "failures": underpowered,
        }
    )

    overlap = report.get("duplicate_target_overlap", {})
    overlap_value = overlap.get("overlap_with_first_hit_proxy") if isinstance(overlap, Mapping) else None
    gates.append(
        {
            "gate": "not_duplicate_of_first_hit_target",
            "pass": overlap_value is not None and float(overlap_value) <= 0.80,
            "failure_decision": "STOP_DUPLICATE_TARGET",
            "overlap_with_first_hit_proxy": overlap_value,
            "max_allowed_overlap": 0.80,
        }
    )

    control_failures: list[str] = []
    for market in markets:
        for stage in ("discovery", "confirmation"):
            model = market_stage.get(market, {}).get(stage, {}).get("scorers", {}).get("model", {})
            model_precision = model.get("top_5pct_target_precision")
            model_net = model.get("top_5pct_target_quality_oracle_net_upper_bound_per_event")
            for control in REQUIRED_CONTROLS:
                control_row = (
                    market_stage.get(market, {})
                    .get(stage, {})
                    .get("scorers", {})
                    .get(control, {})
                )
                control_precision = control_row.get("top_5pct_target_precision")
                control_net = control_row.get("top_5pct_target_quality_oracle_net_upper_bound_per_event")
                if (
                    model_precision is None
                    or control_precision is None
                    or model_net is None
                    or control_net is None
                    or float(model_precision) <= float(control_precision)
                    or float(model_net) <= float(control_net)
                ):
                    control_failures.append(f"{market}:{stage}:{control}")
    gates.append(
        {
            "gate": "each_market_stage_beats_controls_top_5",
            "pass": not control_failures,
            "failure_decision": "REJECTED",
            "required_controls": list(REQUIRED_CONTROLS),
            "failures": control_failures,
        }
    )

    fold_results = report.get("fold_results", [])
    positive_by_market = {
        market: sum(
            1
            for item in fold_results
            if isinstance(item, Mapping) and item.get("market") == market and item.get("positive_top_5pct")
        )
        for market in markets
    }
    confirmation_by_market = {
        market: sum(
            1
            for item in fold_results
            if isinstance(item, Mapping)
            and item.get("market") == market
            and item.get("stage") == "confirmation"
            and item.get("positive_top_5pct")
        )
        for market in markets
    }
    fold_failures = [
        market
        for market in markets
        if positive_by_market.get(market, 0) < 8 or confirmation_by_market.get(market, 0) < 3
    ]
    gates.append(
        {
            "gate": "positive_fold_requirement_by_market",
            "pass": not fold_failures,
            "failure_decision": "REJECTED",
            "positive_folds_by_market": positive_by_market,
            "positive_confirmation_folds_by_market": confirmation_by_market,
            "failures": fold_failures,
        }
    )

    market_shares = concentration.get("market_shares", {})
    balance_failures = [
        market
        for market in markets
        if market not in market_shares
        or float(market_shares[market]) > 0.35
        or float(market_shares[market]) < 0.15
    ]
    gates.append(
        {
            "gate": "market_contribution_balance",
            "pass": not balance_failures,
            "failure_decision": "REJECTED",
            "min_share": 0.15,
            "max_share": 0.35,
            "market_shares": market_shares,
            "failures": balance_failures,
        }
    )

    concentration_failures = []
    for scope_name, limit in (("fold", 0.25), ("hour", 0.25), ("side", 0.65)):
        share = concentration.get(scope_name, {}).get("max_share")
        if share is None or float(share) > limit:
            concentration_failures.append(scope_name)
    gates.append(
        {
            "gate": "fold_hour_side_concentration_limits",
            "pass": not concentration_failures,
            "failure_decision": "REJECTED",
            "failures": concentration_failures,
        }
    )

    top_5_by_market = report.get("top_5_by_market", {})
    gross = sum(
        float(row.get("target_quality_oracle_gross_upper_bound", 0.0))
        for row in top_5_by_market.values()
        if isinstance(row, Mapping)
    )
    cost = sum(
        float(row.get("target_quality_oracle_cost_dollars", 0.0))
        for row in top_5_by_market.values()
        if isinstance(row, Mapping)
    )
    cost_drag = float(cost / gross) if gross > 0 else None
    gates.append(
        {
            "gate": "top_5pct_cost_drag_below_50pct",
            "pass": cost_drag is not None and cost_drag < 0.50,
            "failure_decision": "REJECTED",
            "cost_drag": cost_drag,
        }
    )

    decision = "CONFIRMATION_PASS"
    for gate in gates:
        if not gate["pass"]:
            decision = str(gate["failure_decision"])
            break
    return {"decision": decision, "gates": gates}


def _build_report(
    *,
    run: str,
    scope: Mapping[str, Any],
    input_paths: Mapping[str, Any],
    input_hashes: Mapping[str, str],
    folds: Sequence[Mapping[str, Any]],
    events: pd.DataFrame,
    skipped_overlap_count: int,
    fold_results: Sequence[Mapping[str, Any]],
    selected_top_5: pd.DataFrame,
    failures: Sequence[str],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "run": run,
        "hypothesis_id": HYPOTHESIS_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_type": "phase9_target_construction_feasibility_only",
        "not_trading_model": True,
        "not_wfa": True,
        "uses_saved_predictions": False,
        "scope": dict(scope),
        "input_paths": dict(input_paths),
        "input_hashes": dict(input_hashes),
        "fold_list": [str(fold["fold_id"]) for fold in folds],
        "event_counts": _event_counts(events, folds),
        "skipped_overlap_count": int(skipped_overlap_count),
        "class_balance": _class_balance(events) if not events.empty else {"by_market": []},
        "label_definition": {
            "long": "terminal ret ticks > cost ticks + min_profit_ticks, adverse <= cost ticks, favorable >= 2x adverse",
            "short": "terminal ret ticks < -(cost ticks + min_profit_ticks), adverse <= cost ticks, favorable >= 2x adverse",
            "otherwise": "no-trade target",
        },
        "duplicate_target_overlap": _duplicate_target_overlap(events),
        "controls": {"required": list(REQUIRED_CONTROLS)},
        "fold_results": list(fold_results),
        "stage_summaries": _stage_summaries(fold_results),
        "market_stage_summaries": _market_stage_summaries(fold_results, scope["markets"]),
        "top_5_by_market": _top_5_by_market(fold_results),
        "concentration": _concentration(selected_top_5),
        "failures": list(failures),
        "do_not_do": [
            "Do not run WFA or Phase 8 from this result.",
            "Do not use saved tier1_locked_baseline_20260616 predictions.",
            "Do not treat this as executable PnL or strategy PnL.",
            "Do not tune target thresholds, model hyperparameters, costs, policy gates, or feature selection.",
            "Do not freeze the target hypothesis unless confirmation gates pass unchanged.",
        ],
    }
    gate_result = evaluate_gates(report)
    report["gates"] = gate_result["gates"]
    report["decision"] = gate_result["decision"]
    return report


def _markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Directional Path-Quality Target Phase 9 Harness",
        "",
        f"- run: {report['run']}",
        f"- hypothesis_id: {report['hypothesis_id']}",
        f"- decision: {report['decision']}",
        f"- resolved_profile: {report['scope']['resolved_profile']}",
        f"- markets: {', '.join(report['scope']['markets'])}",
        f"- years: {', '.join(str(year) for year in report['scope']['years'])}",
        "- output_type: target/oracle feasibility diagnostics only",
        "- executable_pnl: false",
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
            "## Class Balance",
            "",
            "| market | events | quality | rate | long | short |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report["class_balance"]["by_market"]:
        rate = row["quality_rate"]
        rate_text = "NA" if rate is None else f"{rate:.4f}"
        lines.append(
            f"| {row['market']} | {row['event_count']} | {row['quality_count']} | "
            f"{rate_text} | {row['long_count']} | {row['short_count']} |"
        )
    lines.extend(
        [
            "",
            "## Top 5 By Market",
            "",
            "| market | selected | precision | oracle gross | oracle cost | oracle net |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for market, row in sorted(report["top_5_by_market"].items()):
        precision = row["target_precision"]
        precision_text = "NA" if precision is None else f"{precision:.4f}"
        lines.append(
            f"| {market} | {row['selected_event_count']} | {precision_text} | "
            f"{row['target_quality_oracle_gross_upper_bound']:.2f} | "
            f"{row['target_quality_oracle_cost_dollars']:.2f} | "
            f"{row['target_quality_oracle_net_upper_bound']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Duplicate Target Overlap",
            "",
            f"- overlap_with_first_hit_proxy: {report['duplicate_target_overlap'].get('overlap_with_first_hit_proxy')}",
            "",
            "## Concentration",
            "",
            f"- market: {report['concentration'].get('market')}",
            f"- fold: {report['concentration'].get('fold')}",
            f"- hour: {report['concentration'].get('hour')}",
            f"- side: {report['concentration'].get('side')}",
            "",
            "## Do Not Do",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["do_not_do"])
    lines.append("")
    return "\n".join(lines)


def _write_report(report: Mapping[str, Any], reports_root: Path, run: str) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp()
    json_path = reports_root / f"{run}_{suffix}.json"
    md_path = reports_root / f"{run}_{suffix}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return md_path, json_path


def run_harness(
    *,
    run: str = DEFAULT_RUN,
    profile: str = DEFAULT_PROFILE,
    profile_config: Path = DEFAULT_PROFILE_CONFIG,
    costs_config: Path = DEFAULT_COSTS_CONFIG,
    input_root: Path = DEFAULT_INPUT_ROOT,
    split_plan: Path = DEFAULT_SPLIT_PLAN,
    reports_root: Path = DEFAULT_REPORTS_ROOT,
    feature_cols_path: Path | None = None,
    target_registry: Path = DEFAULT_TARGET_REGISTRY,
    fold_ids: Sequence[str] | None = None,
    max_events_per_market: int | None = None,
    seed: int = 1729,
    write_reports: bool = True,
) -> dict[str, Any]:
    scope = resolve_profile(profile_config, profile)
    registry_errors = validate_target_hypothesis_registered(target_registry)
    market_configs = load_market_target_configs(costs_config, scope["markets"])
    feature_cols, resolved_feature_cols = load_feature_cols(input_root, feature_cols_path)
    model_features = select_model_features(feature_cols)
    if not model_features:
        raise SystemExit("no non-leaking model features available")
    folds, requested_folds = _load_split_folds(split_plan, scope["markets"], fold_ids)
    stages = assign_fold_stages(folds)

    all_events: list[pd.DataFrame] = []
    matrix_paths: list[Path] = []
    failures: list[str] = list(registry_errors)
    skipped_overlap_count = 0
    for market in scope["markets"]:
        frame, load_failures, paths = _load_market_frame(
            market,
            scope["years"],
            input_root,
            _source_columns(model_features),
        )
        matrix_paths.extend(paths)
        failures.extend(load_failures)
        if frame is None:
            continue
        labeled = apply_directional_path_quality_labels(frame, market_configs)
        events, skipped = non_overlapping_events(labeled)
        skipped_overlap_count += skipped
        all_events.append(events)
    if all_events:
        events = pd.concat(all_events, ignore_index=True).sort_values(
            ["market", "year", "target_entry_ts"],
            kind="mergesort",
        )
    else:
        events = pd.DataFrame()
    events = _limit_events_for_selected_folds(events, folds, max_events_per_market)

    fold_results: list[dict[str, Any]] = []
    top_rows: list[pd.DataFrame] = []
    if not events.empty:
        for fold in folds:
            fold_id = str(fold["fold_id"])
            market_events = events[events["market"].astype(str) == str(fold["market"])].copy()
            if market_events.empty:
                failures.append(f"{fold_id}: no events for market")
                continue
            y = market_events[LABEL_COLUMN].astype(int)
            train_mask, test_mask = _fold_masks(market_events, fold, y)
            train = market_events.loc[train_mask].copy()
            test = market_events.loc[test_mask].copy()
            if train.empty or test.empty:
                failures.append(f"{fold_id}: empty train or test events")
                continue
            try:
                result, selected = _fold_result(
                    fold=fold,
                    stage=stages[fold_id],
                    train=train,
                    test=test,
                    features=model_features,
                    seed=seed,
                )
            except ValueError as exc:
                failures.append(f"{fold_id}: {exc}")
                continue
            fold_results.append(result)
            top_rows.append(selected)

    selected_top_5 = pd.concat(top_rows, ignore_index=True) if top_rows else pd.DataFrame()
    input_paths = {
        "profile_config": _relative_path(profile_config),
        "costs_config": _relative_path(costs_config),
        "input_root": _relative_path(input_root),
        "feature_cols": _relative_path(resolved_feature_cols),
        "split_plan": _relative_path(split_plan),
        "target_registry": _relative_path(target_registry),
    }
    hash_paths = [profile_config, costs_config, resolved_feature_cols, split_plan, target_registry, *matrix_paths]
    report = _build_report(
        run=run,
        scope=scope,
        input_paths=input_paths,
        input_hashes=_file_hash_map(hash_paths),
        folds=folds,
        events=events,
        skipped_overlap_count=skipped_overlap_count,
        fold_results=fold_results,
        selected_top_5=selected_top_5,
        failures=failures,
    )
    report["model_features"] = model_features
    report["requested_fold_ids"] = requested_folds
    if write_reports:
        md_path, json_path = _write_report(report, reports_root, run)
        report["report_paths"] = {"markdown": _relative_path(md_path), "json": _relative_path(json_path)}
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--feature-cols", default=None)
    parser.add_argument("--target-registry", default=DEFAULT_TARGET_REGISTRY.as_posix())
    parser.add_argument("--folds", default=None)
    parser.add_argument("--max-events-per-market", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1729)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    report = run_harness(
        run=args.run,
        profile=args.profile,
        profile_config=Path(args.profile_config),
        costs_config=Path(args.costs_config),
        input_root=Path(args.input_root),
        split_plan=Path(args.split_plan),
        reports_root=Path(args.reports_root),
        feature_cols_path=Path(args.feature_cols) if args.feature_cols else None,
        target_registry=Path(args.target_registry),
        fold_ids=_parse_csv(args.folds),
        max_events_per_market=args.max_events_per_market,
        seed=args.seed,
        write_reports=True,
    )
    print(
        json.dumps(
            {
                "run": report["run"],
                "decision": report["decision"],
                "events": sum(report["event_counts"]["by_market"].values()),
                "report_paths": report.get("report_paths", {}),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["decision"] in {"CONFIRMATION_PASS", "REJECTED", "STOP_UNDERPOWERED", "STOP_DUPLICATE_TARGET", "STOP"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
