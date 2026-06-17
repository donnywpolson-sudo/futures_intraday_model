#!/usr/bin/env python3
"""Tier 1 event-level feasibility harness for cost-clearable 15m moves."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml
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
    _read_json,
    _relative_path,
    _validate_fold_fields,
    load_feature_cols,
)


DEFAULT_PROFILE = "tier_1"
DEFAULT_RUN = "tier1_cost_clearability_event_harness"
DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_REPORTS_ROOT = Path("reports/pipeline_audit")
BUCKETS: tuple[tuple[str, float | None], ...] = (
    ("all_events", None),
    ("top_1pct", 0.01),
    ("top_5pct", 0.05),
    ("top_10pct", 0.10),
)
REQUIRED_CONTROLS = (
    "random_label",
    "shuffled_feature",
    "market_year_session_baseline",
    "inverse_score",
)
LEAKAGE_PREFIXES = ("target", "label", "future", "entry", "exit")
LEAKAGE_SUBSTRINGS = ("forward", "gross", "net", "pnl", "profit", "cost")
LABEL_COLUMN = "cost_clearable_15m"
OPPORTUNITY_COLUMN = "opportunity_net_dollars"
GROSS_COLUMN = "target_gross_dollars_15m"
COST_COLUMN = "target_estimated_cost_dollars"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing config: {_relative_path(path)}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid YAML mapping: {_relative_path(path)}")
    return payload


def _parse_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _finite_float(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def resolve_profile(profile_config: Path, profile: str) -> dict[str, Any]:
    payload = _read_yaml(profile_config)
    aliases = payload.get("aliases", {})
    profiles = payload.get("profiles", {})
    if not isinstance(aliases, Mapping) or not isinstance(profiles, Mapping):
        raise SystemExit("profile config missing aliases/profiles mappings")

    resolved = profile
    seen = {profile}
    while resolved in aliases:
        resolved = str(aliases[resolved])
        if resolved in seen:
            raise SystemExit(f"profile alias cycle detected for {profile}")
        seen.add(resolved)

    raw = profiles.get(resolved)
    if not isinstance(raw, Mapping):
        raise SystemExit(f"profile not found: {profile}")
    markets = [str(item) for item in raw.get("markets", [])]
    years = [int(item) for item in raw.get("years", [])]
    if not markets or not years:
        raise SystemExit(f"profile has empty markets/years: {resolved}")
    return {
        "requested_profile": profile,
        "resolved_profile": resolved,
        "markets": markets,
        "years": years,
    }


def load_round_turn_costs(costs_config: Path, markets: Sequence[str]) -> dict[str, float]:
    payload = _read_yaml(costs_config)
    raw_markets = payload.get("markets", {})
    if not isinstance(raw_markets, Mapping):
        raise SystemExit("costs config missing markets mapping")
    costs: dict[str, float] = {}
    for market in markets:
        raw = raw_markets.get(market)
        if not isinstance(raw, Mapping):
            raise SystemExit(f"missing cost config for market: {market}")
        value = _finite_float(raw.get("round_turn_cost_dollars"))
        if value is None or value <= 0:
            raise SystemExit(f"invalid round_turn_cost_dollars for market: {market}")
        costs[market] = value
    return costs


def is_leakage_feature(column: str) -> bool:
    value = column.lower()
    if value in {LABEL_COLUMN, OPPORTUNITY_COLUMN}:
        return True
    if any(value.startswith(prefix) for prefix in LEAKAGE_PREFIXES):
        return True
    return any(item in value for item in LEAKAGE_SUBSTRINGS)


def select_model_features(feature_cols: Sequence[str]) -> list[str]:
    return [column for column in feature_cols if not is_leakage_feature(column)]


def _source_columns(features: Sequence[str]) -> list[str]:
    metadata = {
        "ts",
        "market",
        "year",
        "session_id",
        "session_segment_id",
        "causal_valid",
        "valid_ohlcv",
        "inside_session",
        "is_synthetic",
        "roll_window_flag",
        "boundary_session_flag",
        "feature_input_valid",
        "feature_row_valid",
        "training_row_valid",
        "target_valid",
        "target_entry_ts",
        "target_exit_ts",
        "target_gross_dollars_15m",
    }
    return sorted(set(features) | metadata)


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


def _valid_event_mask(df: pd.DataFrame) -> pd.Series:
    required = [
        "ts",
        "target_entry_ts",
        "target_exit_ts",
        GROSS_COLUMN,
        COST_COLUMN,
    ]
    mask = pd.Series(True, index=df.index, dtype=bool)
    for column in required:
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


def apply_opportunity_labels(frame: pd.DataFrame, market_costs: Mapping[str, float]) -> pd.DataFrame:
    out = frame.copy()
    out["target_entry_ts"] = pd.to_datetime(out["target_entry_ts"], utc=True, errors="coerce")
    out["target_exit_ts"] = pd.to_datetime(out["target_exit_ts"], utc=True, errors="coerce")
    out[GROSS_COLUMN] = pd.to_numeric(out[GROSS_COLUMN], errors="coerce")
    out[COST_COLUMN] = out["market"].map({market: float(cost) for market, cost in market_costs.items()})
    out[OPPORTUNITY_COLUMN] = out[GROSS_COLUMN].abs() - out[COST_COLUMN]
    out[LABEL_COLUMN] = out[OPPORTUNITY_COLUMN] > 0.0
    out["event_hour"] = pd.to_datetime(out["target_entry_ts"], utc=True, errors="coerce").dt.hour
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
    events = frame.loc[selected_indices].sort_values(["market", "year", "target_entry_ts"], kind="mergesort")
    return events.reset_index(drop=True), skipped


def _load_split_folds(
    split_plan: Path,
    markets: Sequence[str],
    fold_ids: Sequence[str] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    payload = _read_json(split_plan)
    folds = payload.get("folds", [])
    if not isinstance(folds, list) or not folds:
        raise SystemExit("split plan has no folds")
    requested = set(fold_ids or [])
    selected: list[dict[str, Any]] = []
    failures: list[str] = []
    for fold in folds:
        if not isinstance(fold, Mapping):
            continue
        fold_id = str(fold.get("fold_id", ""))
        market = str(fold.get("market", ""))
        if market not in markets:
            continue
        if requested and fold_id not in requested:
            continue
        failures.extend(_validate_fold_fields(fold))
        if str(fold.get("split_group", "")) != "research":
            continue
        if fold.get("selection_allowed") is not True:
            continue
        selected.append(dict(fold))
    if requested:
        found = {str(fold["fold_id"]) for fold in selected}
        missing = sorted(requested - found)
        if missing:
            failures.append(f"requested folds missing or not research-selected: {missing}")
    if failures:
        raise SystemExit("; ".join(failures))
    if not selected:
        raise SystemExit("no research folds selected")
    return selected, sorted({str(fold["fold_id"]) for fold in selected})


def assign_fold_stages(folds: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    stages: dict[str, str] = {}
    by_market: dict[str, list[Mapping[str, Any]]] = {}
    for fold in folds:
        by_market.setdefault(str(fold["market"]), []).append(fold)
    for market_folds in by_market.values():
        ordered = sorted(market_folds, key=lambda item: str(item.get("test_start", item["fold_id"])))
        split = max(1, len(ordered) // 2)
        for idx, fold in enumerate(ordered):
            stages[str(fold["fold_id"])] = "discovery" if idx < split else "confirmation"
    return stages


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


def _stable_seed(seed: int, fold_id: str, control: str) -> int:
    digest = hashlib.sha256(f"{seed}:{fold_id}:{control}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _shuffled_features(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    shuffled = frame.copy()
    for column in shuffled.columns:
        shuffled[column] = rng.permutation(shuffled[column].to_numpy())
    return shuffled


def _baseline_scores(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    global_rate = float(train[LABEL_COLUMN].mean()) if len(train) else 0.0
    by_market_hour = train.groupby(["market", "event_hour"], dropna=False)[LABEL_COLUMN].mean()
    by_market = train.groupby(["market"], dropna=False)[LABEL_COLUMN].mean()
    scores: list[float] = []
    for row in test.itertuples():
        key = (row.market, row.event_hour)
        value = by_market_hour.get(key)
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
    gross = pd.to_numeric(selected[GROSS_COLUMN], errors="coerce").abs()
    costs = pd.to_numeric(selected[COST_COLUMN], errors="coerce")
    net = pd.to_numeric(selected[OPPORTUNITY_COLUMN], errors="coerce")
    oracle_gross = float(gross.dropna().sum())
    oracle_cost = float(costs.dropna().sum())
    oracle_net = float(net.dropna().sum())
    return {
        "selected_event_count": int(len(selected)),
        "clearable_event_count": int(pd.to_numeric(selected[LABEL_COLUMN], errors="coerce").fillna(0).sum()),
        "oracle_gross_upper_bound": oracle_gross,
        "oracle_cost_dollars": oracle_cost,
        "oracle_net_upper_bound": oracle_net,
        "oracle_net_upper_bound_per_event": (
            float(oracle_net / len(selected)) if len(selected) else None
        ),
        "cost_drag": float(oracle_cost / oracle_gross) if oracle_gross > 0 else None,
    }


def _evaluate_score_columns(scored: pd.DataFrame, score_columns: Mapping[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for scorer, score_col in score_columns.items():
        out[scorer] = {}
        for bucket_name, fraction in BUCKETS:
            out[scorer][bucket_name] = _bucket_metrics(_select_bucket(scored, score_col, fraction))
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
    baseline_score = _baseline_scores(train, test)

    scored = test.copy()
    scored["model_score"] = model_score
    scored["random_label_score"] = random_score
    scored["shuffled_feature_score"] = shuffled_score
    scored["market_year_session_baseline_score"] = baseline_score
    scored["inverse_score"] = -model_score
    scored["fold_id"] = fold_id
    scored["stage"] = stage
    score_columns = {
        "model": "model_score",
        "random_label": "random_label_score",
        "shuffled_feature": "shuffled_feature_score",
        "market_year_session_baseline": "market_year_session_baseline_score",
        "inverse_score": "inverse_score",
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
        "positive_top_5pct": bool(metrics["model"]["top_5pct"]["oracle_net_upper_bound"] > 0),
    }
    return result, model_top_5


def _summarize_stage(fold_results: Sequence[Mapping[str, Any]], stage: str) -> dict[str, Any]:
    rows = [item for item in fold_results if item["stage"] == stage]
    scorer_summaries: dict[str, Any] = {}
    for scorer in ("model", *REQUIRED_CONTROLS):
        selected = sum(
            int(item["bucket_metrics"][scorer]["top_5pct"]["selected_event_count"])
            for item in rows
        )
        net = sum(
            float(item["bucket_metrics"][scorer]["top_5pct"]["oracle_net_upper_bound"])
            for item in rows
        )
        scorer_summaries[scorer] = {
            "top_5pct_selected_event_count": selected,
            "top_5pct_oracle_net_upper_bound": net,
            "top_5pct_oracle_net_upper_bound_per_event": (
                float(net / selected) if selected else None
            ),
        }
    return {
        "stage": stage,
        "fold_count": len(rows),
        "scored_event_count": sum(int(item["scored_event_count"]) for item in rows),
        "positive_top_5pct_fold_count": sum(1 for item in rows if item["positive_top_5pct"]),
        "scorers": scorer_summaries,
    }


def _event_counts(events: pd.DataFrame, folds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
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
        rows.append(
            {
                "market": str(market),
                "event_count": int(len(group)),
                "cost_clearable_count": int(group[LABEL_COLUMN].astype(bool).sum()),
                "cost_clearable_rate": float(group[LABEL_COLUMN].mean()) if len(group) else None,
            }
        )
    return {"by_market": rows}


def _concentration(top_rows: pd.DataFrame) -> dict[str, Any]:
    if top_rows.empty or OPPORTUNITY_COLUMN not in top_rows.columns:
        empty = {"max_key": None, "max_share": None}
        return {
            "positive_oracle_net_upper_bound": 0.0,
            "fold": dict(empty),
            "market": dict(empty),
            "hour": dict(empty),
        }
    positive = top_rows[pd.to_numeric(top_rows[OPPORTUNITY_COLUMN], errors="coerce") > 0].copy()
    total = float(positive[OPPORTUNITY_COLUMN].sum()) if len(positive) else 0.0

    def max_share(column: str) -> dict[str, Any]:
        if total <= 0 or column not in positive.columns:
            return {"max_key": None, "max_share": None}
        grouped = positive.groupby(column, dropna=False)[OPPORTUNITY_COLUMN].sum()
        key = grouped.idxmax()
        return {"max_key": str(key), "max_share": float(grouped.max() / total)}

    return {
        "positive_oracle_net_upper_bound": total,
        "fold": max_share("fold_id"),
        "market": max_share("market"),
        "hour": max_share("event_hour"),
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
                "oracle_gross_upper_bound": 0.0,
                "oracle_cost_dollars": 0.0,
                "oracle_net_upper_bound": 0.0,
            },
        )
        current["selected_event_count"] += int(bucket["selected_event_count"])
        current["oracle_gross_upper_bound"] += float(bucket["oracle_gross_upper_bound"])
        current["oracle_cost_dollars"] += float(bucket["oracle_cost_dollars"])
        current["oracle_net_upper_bound"] += float(bucket["oracle_net_upper_bound"])
    return out


def _limit_events_for_folds(
    events: pd.DataFrame,
    folds: Sequence[Mapping[str, Any]],
    max_events_per_market: int | None,
) -> pd.DataFrame:
    if max_events_per_market is None or events.empty:
        return events

    selected_indices: list[int] = []
    for market, group in events.groupby("market", dropna=False, sort=False):
        group = group.sort_values("target_entry_ts", kind="mergesort")
        market_folds = [fold for fold in folds if str(fold.get("market")) == str(market)]
        if not market_folds:
            selected_indices.extend(group.head(max_events_per_market).index.tolist())
            continue

        y = group[LABEL_COLUMN].astype(int)
        train_mask = pd.Series(False, index=group.index)
        test_mask = pd.Series(False, index=group.index)
        for fold in market_folds:
            fold_train, fold_test = _fold_masks(group, fold, y)
            train_mask |= fold_train
            test_mask |= fold_test

        train_idx = group.index[train_mask].tolist()
        test_idx = group.index[test_mask].tolist()
        if not train_idx or not test_idx:
            relevant = group.index[train_mask | test_mask].tolist()
            selected_indices.extend(relevant[:max_events_per_market])
            continue

        test_quota = min(len(test_idx), max(1, max_events_per_market // 2))
        train_quota = min(len(train_idx), max_events_per_market - test_quota)
        chosen_train = train_idx[-train_quota:] if train_quota else []
        chosen = chosen_train + test_idx[:test_quota]
        if len(chosen) < max_events_per_market:
            chosen_set = set(chosen)
            fill = [idx for idx in group.index.tolist() if idx not in chosen_set]
            chosen.extend(fill[: max_events_per_market - len(chosen)])
        selected_indices.extend(chosen[:max_events_per_market])

    return events.loc[selected_indices].sort_values(
        ["market", "year", "target_entry_ts"], kind="mergesort"
    ).reset_index(drop=True)


def evaluate_gates(report: Mapping[str, Any]) -> dict[str, Any]:
    markets = list(report["scope"]["markets"])
    event_counts = report["event_counts"]["by_market"]
    fold_results = report["fold_results"]
    stage_summaries = report["stage_summaries"]
    top_5_by_market = report["top_5_by_market"]
    concentration = report["concentration"]
    failures = list(report.get("failures", []))

    gates: list[dict[str, Any]] = []

    schema_pass = not failures and all(int(event_counts.get(market, 0)) > 0 for market in markets)
    gates.append(
        {
            "gate": "schema_provenance_and_all_markets_have_events",
            "pass": schema_pass,
            "failure_decision": "STOP",
        }
    )

    underpowered_markets = [
        market
        for market in markets
        if sum(
            int(item["scored_event_count"]) for item in fold_results if item["market"] == market
        )
        < 500
        or int(top_5_by_market.get(market, {}).get("selected_event_count", 0)) < 100
    ]
    gates.append(
        {
            "gate": "minimum_events_per_market",
            "pass": not underpowered_markets,
            "failure_decision": "STOP_UNDERPOWERED",
            "underpowered_markets": underpowered_markets,
        }
    )

    controls_present = all(
        control in stage_summaries.get("discovery", {}).get("scorers", {})
        and control in stage_summaries.get("confirmation", {}).get("scorers", {})
        for control in REQUIRED_CONTROLS
    )
    control_failures: list[str] = []
    if controls_present:
        for stage in ("discovery", "confirmation"):
            model_value = stage_summaries[stage]["scorers"]["model"][
                "top_5pct_oracle_net_upper_bound_per_event"
            ]
            for control in REQUIRED_CONTROLS:
                control_value = stage_summaries[stage]["scorers"][control][
                    "top_5pct_oracle_net_upper_bound_per_event"
                ]
                if model_value is None or control_value is None or model_value <= control_value:
                    control_failures.append(f"{stage}:{control}")
    gates.append(
        {
            "gate": "model_beats_all_controls_discovery_and_confirmation",
            "pass": controls_present and not control_failures,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "required_controls": list(REQUIRED_CONTROLS),
            "failures": control_failures,
        }
    )

    positives_by_market = {
        market: sum(
            1 for item in fold_results if item["market"] == market and item["positive_top_5pct"]
        )
        for market in markets
    }
    total_positive = sum(positives_by_market.values())
    market_rule = all(value >= 8 for value in positives_by_market.values())
    overall_rule = total_positive >= 36 and all(value >= 6 for value in positives_by_market.values())
    gates.append(
        {
            "gate": "positive_fold_requirement",
            "pass": market_rule or overall_rule,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "positive_folds_by_market": positives_by_market,
            "total_positive_folds": total_positive,
        }
    )

    concentration_failures = [
        scope
        for scope in ("fold", "market", "hour")
        if concentration.get(scope, {}).get("max_share") is None
        or float(concentration[scope]["max_share"]) > 0.35
    ]
    gates.append(
        {
            "gate": "positive_oracle_net_concentration_limit",
            "pass": not concentration_failures,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "max_allowed_share": 0.35,
            "failures": concentration_failures,
        }
    )

    total_gross = sum(float(item.get("oracle_gross_upper_bound", 0.0)) for item in top_5_by_market.values())
    total_cost = sum(float(item.get("oracle_cost_dollars", 0.0)) for item in top_5_by_market.values())
    cost_drag = float(total_cost / total_gross) if total_gross > 0 else None
    gates.append(
        {
            "gate": "top_5pct_cost_drag_below_50pct",
            "pass": cost_drag is not None and cost_drag < 0.50,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "cost_drag": cost_drag,
        }
    )

    non_es_failures = [
        market
        for market in markets
        if market != "ES"
        and (
            int(top_5_by_market.get(market, {}).get("selected_event_count", 0)) < 100
            or float(top_5_by_market.get(market, {}).get("oracle_net_upper_bound", 0.0)) <= 0.0
        )
    ]
    gates.append(
        {
            "gate": "non_es_markets_participate_materially",
            "pass": not non_es_failures,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "failures": non_es_failures,
        }
    )

    decision = "PASS"
    for gate in gates:
        if gate["pass"]:
            continue
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
    top_rows: pd.DataFrame,
    failures: Sequence[str],
) -> dict[str, Any]:
    stages = {
        stage: _summarize_stage(fold_results, stage)
        for stage in ("discovery", "confirmation")
    }
    report: dict[str, Any] = {
        "run": run,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_type": "phase9_cost_clearability_feasibility_only",
        "not_trading_model": True,
        "scope": dict(scope),
        "input_paths": dict(input_paths),
        "input_hashes": dict(input_hashes),
        "fold_list": [str(fold["fold_id"]) for fold in folds],
        "event_counts": _event_counts(events, folds),
        "skipped_overlap_count": int(skipped_overlap_count),
        "class_balance": _class_balance(events),
        "fold_results": list(fold_results),
        "stage_summaries": stages,
        "top_5_by_market": _top_5_by_market(fold_results),
        "concentration": _concentration(top_rows),
        "controls": {"required": list(REQUIRED_CONTROLS)},
        "failures": list(failures),
        "do_not_do": [
            "Do not treat oracle/feasibility output as executable PnL or strategy PnL.",
            "Do not tune thresholds, policy gates, costs, features, or model hyperparameters.",
            "Do not use tier1_locked_baseline_20260616 predictions.",
            "Do not rerun WFA or Phase 8 from this harness result.",
        ],
    }
    gate_result = evaluate_gates(report)
    report["gates"] = gate_result["gates"]
    report["decision"] = gate_result["decision"]
    return report


def _markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Tier 1 Cost-Clearability Event Harness",
        "",
        f"- run: {report['run']}",
        f"- decision: {report['decision']}",
        f"- resolved_profile: {report['scope']['resolved_profile']}",
        f"- markets: {', '.join(report['scope']['markets'])}",
        f"- years: {', '.join(str(item) for item in report['scope']['years'])}",
        "- output_type: oracle/feasibility upper bounds only",
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
            "## Event Counts By Market",
            "",
            "| market | events |",
            "| --- | ---: |",
        ]
    )
    for market, count in report["event_counts"]["by_market"].items():
        lines.append(f"| {market} | {count} |")
    lines.extend(
        [
            "",
            "## Stage Top 5% Oracle Net Per Event",
            "",
            "| stage | model | random_label | shuffled_feature | market_year_session_baseline | inverse_score |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for stage in ("discovery", "confirmation"):
        scorers = report["stage_summaries"][stage]["scorers"]
        values = [
            scorers[name]["top_5pct_oracle_net_upper_bound_per_event"]
            for name in ("model", *REQUIRED_CONTROLS)
        ]
        rendered = [f"{value:.4f}" if value is not None else "NA" for value in values]
        lines.append(f"| {stage} | " + " | ".join(rendered) + " |")
    lines.extend(["", "## Do Not Do", ""])
    for item in report["do_not_do"]:
        lines.append(f"- {item}")
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
    fold_ids: Sequence[str] | None = None,
    max_events_per_market: int | None = None,
    seed: int = 1729,
    write_reports: bool = True,
) -> dict[str, Any]:
    scope = resolve_profile(profile_config, profile)
    costs = load_round_turn_costs(costs_config, scope["markets"])
    feature_cols, resolved_feature_cols = load_feature_cols(input_root, feature_cols_path)
    model_features = select_model_features(feature_cols)
    if not model_features:
        raise SystemExit("no non-leaking model features available")
    folds, requested_folds = _load_split_folds(split_plan, scope["markets"], fold_ids)
    stages = assign_fold_stages(folds)

    all_events: list[pd.DataFrame] = []
    matrix_paths: list[Path] = []
    failures: list[str] = []
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
        labeled = apply_opportunity_labels(frame, costs)
        events, skipped = non_overlapping_events(labeled)
        skipped_overlap_count += skipped
        all_events.append(events)
    if all_events:
        events = pd.concat(all_events, ignore_index=True).sort_values(
            ["market", "year", "target_entry_ts"], kind="mergesort"
        )
    else:
        events = pd.DataFrame()
    events = _limit_events_for_folds(events, folds, max_events_per_market)

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

    top_5_rows = pd.concat(top_rows, ignore_index=True) if top_rows else pd.DataFrame()
    input_paths = {
        "profile_config": _relative_path(profile_config),
        "costs_config": _relative_path(costs_config),
        "input_root": _relative_path(input_root),
        "feature_cols": _relative_path(resolved_feature_cols),
        "split_plan": _relative_path(split_plan),
    }
    hash_paths = [profile_config, costs_config, resolved_feature_cols, split_plan, *matrix_paths]
    report = _build_report(
        run=run,
        scope=scope,
        input_paths=input_paths,
        input_hashes=_file_hash_map(hash_paths),
        folds=folds,
        events=events,
        skipped_overlap_count=skipped_overlap_count,
        fold_results=fold_results,
        top_rows=top_5_rows,
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
        fold_ids=_parse_csv(args.folds),
        max_events_per_market=args.max_events_per_market,
        seed=args.seed,
        write_reports=True,
    )
    print(
        f"{report['decision']} cost-clearability harness: "
        f"run={report['run']} folds={len(report['fold_list'])} "
        f"events={sum(report['event_counts']['by_market'].values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
