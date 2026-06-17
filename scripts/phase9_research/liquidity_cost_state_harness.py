#!/usr/bin/env python3
"""Phase 9 liquidity/cost-state feasibility harness.

This harness is not a trading model and does not run WFA. It tests whether
pre-entry cost-state proxies identify non-overlapping events with better
post-cost feasibility than fixed controls.
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
    COST_COLUMN,
    DEFAULT_COSTS_CONFIG,
    DEFAULT_PROFILE,
    DEFAULT_PROFILE_CONFIG,
    DEFAULT_REPORTS_ROOT,
    GROSS_COLUMN,
    LABEL_COLUMN,
    OPPORTUNITY_COLUMN,
    _class_balance,
    _event_counts,
    _load_split_folds,
    _parse_csv,
    _timestamp,
    apply_opportunity_labels,
    assign_fold_stages,
    load_round_turn_costs,
    non_overlapping_events,
    resolve_profile,
)
from scripts.phase9_research.feature_hypothesis_registry import (
    DEFAULT_REGISTRY,
    validate_registry,
)


HYPOTHESIS_ID = "liquidity_cost_state_features_v1"
DEFAULT_RUN = HYPOTHESIS_ID
REQUIRED_BASE_FEATURES = (
    "feature_realized_vol_15",
    "feature_realized_vol_60",
    "feature_realized_range_30",
    "feature_realized_range_60",
    "feature_volume_z_60",
    "feature_range_per_volume",
)
CANDIDATE_FEATURES = (
    "feature_cost_to_realized_vol_15",
    "feature_cost_to_realized_vol_60",
    "feature_cost_to_realized_range_30",
    "feature_cost_to_realized_range_60",
    "feature_cost_to_volume_z_60",
    "feature_cost_to_range_per_volume",
    "feature_liquidity_state_score",
)
REQUIRED_CONTROLS = (
    "random_score",
    "inverse_score",
    "market_year_session_baseline",
    "baseline_ohlcv_proxy",
)
BASELINE_PROXY_FEATURES = (
    "feature_ret_1",
    "feature_ret_5",
    "feature_range_norm",
    "feature_true_range",
    "feature_ewma_vol_20",
    "feature_volume_z_20",
)
EPS = 1e-12


def _stable_seed(seed: int, *parts: object) -> int:
    digest = hashlib.sha256(":".join(str(part) for part in (seed, *parts)).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _safe_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = denominator.abs().where(denominator.abs() > EPS)
    return numerator / denom


def _source_columns() -> list[str]:
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
        GROSS_COLUMN,
    }
    return sorted(metadata | set(REQUIRED_BASE_FEATURES) | set(BASELINE_PROXY_FEATURES))


def validate_hypothesis_registered(registry_path: Path = DEFAULT_REGISTRY) -> list[str]:
    errors = validate_registry(registry_path)
    if errors:
        return errors
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    rows = payload.get("hypotheses", [])
    if not isinstance(rows, list):
        return ["registry hypotheses must be a list"]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("hypothesis_id") != HYPOTHESIS_ID:
            continue
        if row.get("status") != "CANDIDATE":
            return [f"{HYPOTHESIS_ID}: expected CANDIDATE status before harness run"]
        if row.get("wfa_allowed") is not False:
            return [f"{HYPOTHESIS_ID}: wfa_allowed must be false before freeze"]
        return []
    return [f"{HYPOTHESIS_ID}: missing from feature hypothesis registry"]


def missing_required_features(feature_cols: Sequence[str]) -> list[str]:
    available = set(feature_cols)
    return [feature for feature in REQUIRED_BASE_FEATURES if feature not in available]


def add_liquidity_cost_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add pre-entry cost-state proxy features from existing causal columns."""

    out = frame.copy()
    cost = _safe_numeric(out, COST_COLUMN)
    out["feature_cost_to_realized_vol_15"] = _safe_divide(
        cost, _safe_numeric(out, "feature_realized_vol_15")
    )
    out["feature_cost_to_realized_vol_60"] = _safe_divide(
        cost, _safe_numeric(out, "feature_realized_vol_60")
    )
    out["feature_cost_to_realized_range_30"] = _safe_divide(
        cost, _safe_numeric(out, "feature_realized_range_30")
    )
    out["feature_cost_to_realized_range_60"] = _safe_divide(
        cost, _safe_numeric(out, "feature_realized_range_60")
    )
    out["feature_cost_to_volume_z_60"] = cost / (_safe_numeric(out, "feature_volume_z_60").abs() + 1.0)
    out["feature_cost_to_range_per_volume"] = _safe_divide(
        cost, _safe_numeric(out, "feature_range_per_volume")
    )
    ratio_values = out[list(CANDIDATE_FEATURES[:-1])].replace([np.inf, -np.inf], np.nan)
    out["feature_liquidity_state_score"] = -ratio_values.median(axis=1)
    return out


def _fit_score_params(train: pd.DataFrame) -> dict[str, dict[str, float]]:
    params: dict[str, dict[str, float]] = {}
    for column in CANDIDATE_FEATURES[:-1]:
        values = pd.to_numeric(train[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
        median = float(values.median()) if values.notna().any() else 0.0
        mad = float((values - median).abs().median()) if values.notna().any() else 1.0
        if not math.isfinite(mad) or mad <= EPS:
            mad = 1.0
        params[column] = {"median": median, "mad": mad}
    return params


def score_liquidity_state(frame: pd.DataFrame, params: Mapping[str, Mapping[str, float]]) -> pd.Series:
    components: list[pd.Series] = []
    for column in CANDIDATE_FEATURES[:-1]:
        values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
        median = float(params[column]["median"])
        mad = float(params[column]["mad"])
        components.append((values.fillna(median) - median) / mad)
    if not components:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    friction_z = pd.concat(components, axis=1).mean(axis=1)
    return -friction_z


def _baseline_ohlcv_proxy(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    available = [column for column in BASELINE_PROXY_FEATURES if column in test.columns]
    if not available:
        return pd.Series(0.0, index=test.index)
    train_medians = {
        column: float(pd.to_numeric(train[column], errors="coerce").median())
        if column in train.columns and pd.to_numeric(train[column], errors="coerce").notna().any()
        else 0.0
        for column in available
    }
    scores = []
    for column in available:
        values = pd.to_numeric(test[column], errors="coerce").fillna(train_medians[column])
        scores.append(values.abs())
    return pd.concat(scores, axis=1).mean(axis=1)


def _market_year_session_baseline(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    global_rate = float(train[OPPORTUNITY_COLUMN].mean()) if len(train) else 0.0
    by_market_hour = train.groupby(["market", "event_hour"], dropna=False)[OPPORTUNITY_COLUMN].mean()
    by_market = train.groupby(["market"], dropna=False)[OPPORTUNITY_COLUMN].mean()
    scores: list[float] = []
    for row in test.itertuples():
        value = by_market_hour.get((row.market, row.event_hour))
        if value is None or pd.isna(value):
            value = by_market.get(row.market, global_rate)
        scores.append(float(value if pd.notna(value) else global_rate))
    return pd.Series(scores, index=test.index, dtype=float)


def _quantile_thresholds(train_scores: pd.Series) -> dict[str, float]:
    values = pd.to_numeric(train_scores, errors="coerce").dropna()
    if values.empty:
        return {"q10": 0.0, "q33": 0.0, "q66": 0.0, "q90": 0.0}
    return {
        "q10": float(values.quantile(0.10)),
        "q33": float(values.quantile(1.0 / 3.0)),
        "q66": float(values.quantile(2.0 / 3.0)),
        "q90": float(values.quantile(0.90)),
    }


def _bucket_mask(scores: pd.Series, bucket: str, thresholds: Mapping[str, float]) -> pd.Series:
    values = pd.to_numeric(scores, errors="coerce")
    if bucket == "all_events":
        return pd.Series(True, index=scores.index)
    if bucket == "low_friction_tercile":
        return values >= thresholds["q66"]
    if bucket == "mid_friction_tercile":
        return (values > thresholds["q33"]) & (values < thresholds["q66"])
    if bucket == "high_friction_tercile":
        return values <= thresholds["q33"]
    if bucket == "top_score_decile":
        return values >= thresholds["q90"]
    if bucket == "bottom_score_decile":
        return values <= thresholds["q10"]
    raise ValueError(f"unknown bucket: {bucket}")


def _bucket_metrics(selected: pd.DataFrame) -> dict[str, Any]:
    gross = pd.to_numeric(selected[GROSS_COLUMN], errors="coerce").abs()
    cost = pd.to_numeric(selected[COST_COLUMN], errors="coerce")
    net = pd.to_numeric(selected[OPPORTUNITY_COLUMN], errors="coerce")
    ratio = gross / cost.where(cost.abs() > EPS)
    oracle_gross = float(gross.dropna().sum())
    oracle_cost = float(cost.dropna().sum())
    oracle_net = float(net.dropna().sum())
    return {
        "selected_event_count": int(len(selected)),
        "oracle_gross_upper_bound": oracle_gross,
        "oracle_cost_dollars": oracle_cost,
        "oracle_net_upper_bound": oracle_net,
        "oracle_net_upper_bound_per_event": float(oracle_net / len(selected)) if len(selected) else None,
        "median_gross_to_cost_ratio": float(ratio.median()) if ratio.notna().any() else None,
        "clearable_rate": float(selected[LABEL_COLUMN].mean()) if len(selected) else None,
    }


def _score_bucket_metrics(
    scored: pd.DataFrame,
    score_column: str,
    train_scores: pd.Series,
) -> dict[str, Any]:
    thresholds = _quantile_thresholds(train_scores)
    out: dict[str, Any] = {}
    for bucket in (
        "all_events",
        "low_friction_tercile",
        "mid_friction_tercile",
        "high_friction_tercile",
        "top_score_decile",
        "bottom_score_decile",
    ):
        out[bucket] = _bucket_metrics(scored.loc[_bucket_mask(scored[score_column], bucket, thresholds)])
    return out


def _fold_result(
    *,
    fold: Mapping[str, Any],
    stage: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    seed: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    fold_id = str(fold["fold_id"])
    params = _fit_score_params(train)
    train_score = score_liquidity_state(train, params)
    test_score = score_liquidity_state(test, params)
    rng = np.random.default_rng(_stable_seed(seed, fold_id, "random_score"))
    random_score = pd.Series(rng.random(len(test)), index=test.index)
    baseline_score = _market_year_session_baseline(train, test)
    ohlcv_score = _baseline_ohlcv_proxy(train, test)

    scored = test.copy()
    scored["liquidity_state_score"] = test_score
    scored["random_score"] = random_score
    scored["inverse_score"] = -test_score
    scored["market_year_session_baseline_score"] = baseline_score
    scored["baseline_ohlcv_proxy_score"] = ohlcv_score
    scored["fold_id"] = fold_id
    scored["stage"] = stage

    train_scores = {
        "liquidity_state": train_score,
        "random_score": pd.Series(rng.random(len(train)), index=train.index),
        "inverse_score": -train_score,
        "market_year_session_baseline": pd.Series(train[OPPORTUNITY_COLUMN].to_numpy(), index=train.index),
        "baseline_ohlcv_proxy": _baseline_ohlcv_proxy(train, train),
    }
    score_columns = {
        "liquidity_state": "liquidity_state_score",
        "random_score": "random_score",
        "inverse_score": "inverse_score",
        "market_year_session_baseline": "market_year_session_baseline_score",
        "baseline_ohlcv_proxy": "baseline_ohlcv_proxy_score",
    }
    bucket_metrics = {
        scorer: _score_bucket_metrics(scored, score_column, train_scores[scorer])
        for scorer, score_column in score_columns.items()
    }
    selected = scored.loc[
        _bucket_mask(
            scored["liquidity_state_score"],
            "low_friction_tercile",
            _quantile_thresholds(train_score),
        )
    ].copy()
    result = {
        "fold_id": fold_id,
        "stage": stage,
        "market": str(fold["market"]),
        "train_event_count": int(len(train)),
        "scored_event_count": int(len(test)),
        "bucket_metrics": bucket_metrics,
    }
    return result, selected


def _aggregate_rows(rows: pd.DataFrame) -> dict[str, Any]:
    return _bucket_metrics(rows)


def _stage_summaries(fold_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for stage in ("discovery", "confirmation"):
        stage_rows = [item for item in fold_results if item["stage"] == stage]
        scorers: dict[str, Any] = {}
        for scorer in ("liquidity_state", *REQUIRED_CONTROLS):
            low = sum(
                float(item["bucket_metrics"][scorer]["low_friction_tercile"]["oracle_net_upper_bound"])
                for item in stage_rows
            )
            low_count = sum(
                int(item["bucket_metrics"][scorer]["low_friction_tercile"]["selected_event_count"])
                for item in stage_rows
            )
            top = sum(
                float(item["bucket_metrics"][scorer]["top_score_decile"]["oracle_net_upper_bound"])
                for item in stage_rows
            )
            top_count = sum(
                int(item["bucket_metrics"][scorer]["top_score_decile"]["selected_event_count"])
                for item in stage_rows
            )
            all_net = sum(
                float(item["bucket_metrics"][scorer]["all_events"]["oracle_net_upper_bound"])
                for item in stage_rows
            )
            all_count = sum(
                int(item["bucket_metrics"][scorer]["all_events"]["selected_event_count"])
                for item in stage_rows
            )
            scorers[scorer] = {
                "low_friction_oracle_net_per_event": float(low / low_count) if low_count else None,
                "top_decile_oracle_net_per_event": float(top / top_count) if top_count else None,
                "all_events_oracle_net_per_event": float(all_net / all_count) if all_count else None,
                "low_friction_selected_event_count": low_count,
                "top_decile_selected_event_count": top_count,
            }
        out[stage] = {
            "stage": stage,
            "fold_count": len(stage_rows),
            "scored_event_count": sum(int(item["scored_event_count"]) for item in stage_rows),
            "scorers": scorers,
        }
    return out


def _market_stage_summaries(fold_results: Sequence[Mapping[str, Any]], markets: Sequence[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for market in markets:
        out[market] = {}
        for stage in ("discovery", "confirmation"):
            rows = [
                item for item in fold_results
                if item["market"] == market and item["stage"] == stage
            ]
            low = sum(
                float(item["bucket_metrics"]["liquidity_state"]["low_friction_tercile"]["oracle_net_upper_bound"])
                for item in rows
            )
            low_count = sum(
                int(item["bucket_metrics"]["liquidity_state"]["low_friction_tercile"]["selected_event_count"])
                for item in rows
            )
            all_net = sum(
                float(item["bucket_metrics"]["liquidity_state"]["all_events"]["oracle_net_upper_bound"])
                for item in rows
            )
            all_count = sum(
                int(item["bucket_metrics"]["liquidity_state"]["all_events"]["selected_event_count"])
                for item in rows
            )
            out[market][stage] = {
                "scored_event_count": all_count,
                "low_friction_selected_event_count": low_count,
                "low_friction_oracle_net_per_event": float(low / low_count) if low_count else None,
                "all_events_oracle_net_per_event": float(all_net / all_count) if all_count else None,
            }
    return out


def _concentration(selected: pd.DataFrame) -> dict[str, Any]:
    if selected.empty or OPPORTUNITY_COLUMN not in selected.columns:
        return {
            "positive_oracle_net_upper_bound": 0.0,
            "market": {"max_key": None, "max_share": None},
            "fold": {"max_key": None, "max_share": None},
            "hour": {"max_key": None, "max_share": None},
        }
    positive = selected[pd.to_numeric(selected[OPPORTUNITY_COLUMN], errors="coerce") > 0].copy()
    total = float(positive[OPPORTUNITY_COLUMN].sum()) if len(positive) else 0.0

    def max_share(column: str) -> dict[str, Any]:
        if total <= 0.0 or column not in positive.columns:
            return {"max_key": None, "max_share": None}
        grouped = positive.groupby(column, dropna=False)[OPPORTUNITY_COLUMN].sum()
        return {"max_key": str(grouped.idxmax()), "max_share": float(grouped.max() / total)}

    return {
        "positive_oracle_net_upper_bound": total,
        "market": max_share("market"),
        "fold": max_share("fold_id"),
        "hour": max_share("event_hour"),
    }


def _safe_event_counts(events: pd.DataFrame, folds: Sequence[Mapping[str, Any]], markets: Sequence[str]) -> dict[str, Any]:
    if events.empty or "market" not in events.columns:
        return {
            "by_market": {str(market): 0 for market in markets},
            "by_market_year": [],
            "by_fold": [
                {
                    "fold_id": str(fold["fold_id"]),
                    "market": str(fold["market"]),
                    "event_count": 0,
                }
                for fold in folds
            ],
        }
    return _event_counts(events, folds)


def _limit_events_for_selected_folds(
    events: pd.DataFrame,
    folds: Sequence[Mapping[str, Any]],
    max_events_per_market: int | None,
) -> pd.DataFrame:
    if max_events_per_market is None or events.empty:
        return events

    selected_indices: list[int] = []
    for market, group in events.groupby("market", dropna=False, sort=False):
        group = group.sort_values("target_entry_ts", kind="mergesort")
        market_folds = sorted(
            [fold for fold in folds if str(fold.get("market")) == str(market)],
            key=lambda fold: str(fold.get("test_start", fold.get("fold_id", ""))),
        )
        if not market_folds:
            selected_indices.extend(group.head(max_events_per_market).index.tolist())
            continue

        y = group[LABEL_COLUMN].astype(int)
        per_side_quota = max(1, max_events_per_market // max(1, len(market_folds) * 2))
        chosen: list[int] = []
        for fold in market_folds:
            train_mask, test_mask = _fold_masks(group, fold, y)
            train_idx = group.index[train_mask].tolist()
            test_idx = group.index[test_mask].tolist()
            chosen.extend(train_idx[-per_side_quota:])
            chosen.extend(test_idx[:per_side_quota])

        deduped = list(dict.fromkeys(chosen))
        if len(deduped) < max_events_per_market:
            chosen_set = set(deduped)
            fill = [idx for idx in group.index.tolist() if idx not in chosen_set]
            deduped.extend(fill[: max_events_per_market - len(deduped)])
        selected_indices.extend(deduped[:max_events_per_market])

    return events.loc[selected_indices].sort_values(
        ["market", "year", "target_entry_ts"], kind="mergesort"
    ).reset_index(drop=True)


def evaluate_gates(report: Mapping[str, Any]) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []
    failures = list(report.get("failures", []))
    markets = list(report["scope"]["markets"])
    by_market_stage = report["market_stage_summaries"]
    stage_summaries = report["stage_summaries"]
    concentration = report["concentration"]

    gates.append(
        {
            "gate": "schema_registry_and_inputs_valid",
            "pass": not failures,
            "failure_decision": "STOP",
            "failures": failures,
        }
    )

    underpowered = [
        f"{market}:{stage}"
        for market in markets
        for stage in ("discovery", "confirmation")
        if int(by_market_stage.get(market, {}).get(stage, {}).get("scored_event_count", 0)) < 500
    ]
    gates.append(
        {
            "gate": "minimum_events_per_market_per_stage",
            "pass": not underpowered,
            "failure_decision": "STOP_UNDERPOWERED",
            "failures": underpowered,
        }
    )

    improvement_failures = []
    for stage in ("discovery", "confirmation"):
        model = stage_summaries[stage]["scorers"]["liquidity_state"]
        low = model["low_friction_oracle_net_per_event"]
        all_events = model["all_events_oracle_net_per_event"]
        if low is None or all_events is None or low <= all_events:
            improvement_failures.append(stage)
    gates.append(
        {
            "gate": "low_friction_beats_all_events_discovery_and_confirmation",
            "pass": not improvement_failures,
            "failure_decision": "REJECTED",
            "failures": improvement_failures,
        }
    )

    market_failures = []
    for market in markets:
        for stage in ("discovery", "confirmation"):
            row = by_market_stage[market][stage]
            low = row["low_friction_oracle_net_per_event"]
            all_events = row["all_events_oracle_net_per_event"]
            if low is None or all_events is None or low <= all_events:
                market_failures.append(f"{market}:{stage}")
    gates.append(
        {
            "gate": "improvement_all_markets_no_es_only_pass",
            "pass": not market_failures,
            "failure_decision": "REJECTED",
            "failures": market_failures,
        }
    )

    control_failures = []
    for stage in ("discovery", "confirmation"):
        model_value = stage_summaries[stage]["scorers"]["liquidity_state"]["top_decile_oracle_net_per_event"]
        for control in REQUIRED_CONTROLS:
            control_value = stage_summaries[stage]["scorers"][control]["top_decile_oracle_net_per_event"]
            if model_value is None or control_value is None or model_value <= control_value:
                control_failures.append(f"{stage}:{control}")
    gates.append(
        {
            "gate": "top_decile_beats_controls",
            "pass": not control_failures,
            "failure_decision": "REJECTED",
            "required_controls": list(REQUIRED_CONTROLS),
            "failures": control_failures,
        }
    )

    concentration_failures = [
        scope
        for scope, limit in (("market", 0.35), ("fold", 0.25), ("hour", 0.25))
        if concentration.get(scope, {}).get("max_share") is None
        or float(concentration[scope]["max_share"]) > limit
    ]
    gates.append(
        {
            "gate": "positive_feasibility_concentration_limits",
            "pass": not concentration_failures,
            "failure_decision": "REJECTED",
            "failures": concentration_failures,
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
    selected_low_friction: pd.DataFrame,
    failures: Sequence[str],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "run": run,
        "hypothesis_id": HYPOTHESIS_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_type": "phase9_liquidity_cost_state_feasibility_only",
        "not_trading_model": True,
        "not_wfa": True,
        "uses_saved_predictions": False,
        "scope": dict(scope),
        "input_paths": dict(input_paths),
        "input_hashes": dict(input_hashes),
        "fold_list": [str(fold["fold_id"]) for fold in folds],
        "event_counts": _safe_event_counts(events, folds, scope["markets"]),
        "skipped_overlap_count": int(skipped_overlap_count),
        "class_balance": _class_balance(events) if not events.empty else {"by_market": []},
        "candidate_features": list(CANDIDATE_FEATURES),
        "required_base_features": list(REQUIRED_BASE_FEATURES),
        "controls": {"required": list(REQUIRED_CONTROLS)},
        "fold_results": list(fold_results),
        "stage_summaries": _stage_summaries(fold_results),
        "market_stage_summaries": _market_stage_summaries(fold_results, scope["markets"]),
        "concentration": _concentration(selected_low_friction),
        "failures": list(failures),
        "do_not_do": [
            "Do not run WFA or Phase 8 from this result.",
            "Do not treat this as executable PnL or strategy PnL.",
            "Do not tune thresholds or feature formulas against this result.",
            "Do not freeze the feature family unless confirmation gates pass unchanged.",
        ],
    }
    gate_result = evaluate_gates(report)
    report["gates"] = gate_result["gates"]
    report["decision"] = gate_result["decision"]
    return report


def _markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Liquidity Cost-State Phase 9 Harness",
        "",
        f"- run: {report['run']}",
        f"- hypothesis_id: {report['hypothesis_id']}",
        f"- decision: {report['decision']}",
        f"- resolved_profile: {report['scope']['resolved_profile']}",
        f"- markets: {', '.join(report['scope']['markets'])}",
        f"- years: {', '.join(str(year) for year in report['scope']['years'])}",
        "- output_type: feasibility diagnostics only",
        "",
        "## Gates",
        "",
        "| gate | pass |",
        "| --- | --- |",
    ]
    for gate in report["gates"]:
        lines.append(f"| {gate['gate']} | {gate['pass']} |")
    lines.extend(["", "## Candidate Features", ""])
    for feature in report["candidate_features"]:
        lines.append(f"- {feature}")
    lines.extend(["", "## Stage Summary", ""])
    lines.append("| stage | low friction net/event | all events net/event | top decile net/event |")
    lines.append("| --- | ---: | ---: | ---: |")
    for stage in ("discovery", "confirmation"):
        metrics = report["stage_summaries"][stage]["scorers"]["liquidity_state"]
        values = [
            metrics["low_friction_oracle_net_per_event"],
            metrics["all_events_oracle_net_per_event"],
            metrics["top_decile_oracle_net_per_event"],
        ]
        rendered = [f"{value:.4f}" if value is not None else "NA" for value in values]
        lines.append(f"| {stage} | {' | '.join(rendered)} |")
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
    registry_path: Path = DEFAULT_REGISTRY,
    feature_cols_path: Path | None = None,
    fold_ids: Sequence[str] | None = None,
    max_events_per_market: int | None = None,
    seed: int = 20260617,
    write_reports: bool = True,
) -> dict[str, Any]:
    scope = resolve_profile(profile_config, profile)
    registry_failures = validate_hypothesis_registered(registry_path)
    costs = load_round_turn_costs(costs_config, scope["markets"])
    feature_cols, resolved_feature_cols = load_feature_cols(input_root, feature_cols_path)
    missing_features = missing_required_features(feature_cols)
    folds, requested_folds = _load_split_folds(split_plan, scope["markets"], fold_ids)
    stages = assign_fold_stages(folds)

    failures = list(registry_failures)
    if missing_features:
        failures.append(f"missing required base features: {missing_features}")

    all_events: list[pd.DataFrame] = []
    matrix_paths: list[Path] = []
    skipped_overlap_count = 0
    if not missing_features:
        for market in scope["markets"]:
            frame, load_failures, paths = _load_market_frame(
                market,
                scope["years"],
                input_root,
                _source_columns(),
            )
            matrix_paths.extend(paths)
            failures.extend(load_failures)
            if frame is None:
                continue
            labeled = apply_opportunity_labels(frame, costs)
            with_features = add_liquidity_cost_features(labeled)
            events, skipped = non_overlapping_events(with_features)
            skipped_overlap_count += skipped
            all_events.append(events)

    if all_events:
        events = pd.concat(all_events, ignore_index=True).sort_values(
            ["market", "year", "target_entry_ts"], kind="mergesort"
        )
    else:
        events = pd.DataFrame()
    events = _limit_events_for_selected_folds(events, folds, max_events_per_market)

    fold_results: list[dict[str, Any]] = []
    selected_rows: list[pd.DataFrame] = []
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
            result, selected = _fold_result(
                fold=fold,
                stage=stages[fold_id],
                train=train,
                test=test,
                seed=seed,
            )
            fold_results.append(result)
            selected_rows.append(selected)

    selected_low_friction = pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame()
    input_paths = {
        "profile_config": _relative_path(profile_config),
        "costs_config": _relative_path(costs_config),
        "input_root": _relative_path(input_root),
        "feature_cols": _relative_path(resolved_feature_cols),
        "split_plan": _relative_path(split_plan),
        "registry": _relative_path(registry_path),
    }
    hash_paths = [profile_config, costs_config, resolved_feature_cols, split_plan, registry_path, *matrix_paths]
    report = _build_report(
        run=run,
        scope=scope,
        input_paths=input_paths,
        input_hashes=_file_hash_map(hash_paths),
        folds=folds,
        events=events,
        skipped_overlap_count=skipped_overlap_count,
        fold_results=fold_results,
        selected_low_friction=selected_low_friction,
        failures=failures,
    )
    report["requested_fold_ids"] = requested_folds
    if write_reports:
        md_path, json_path = _write_report(report, reports_root, run)
        report["report_paths"] = {
            "markdown": _relative_path(md_path),
            "json": _relative_path(json_path),
        }
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
    parser.add_argument("--registry", default=DEFAULT_REGISTRY.as_posix())
    parser.add_argument("--feature-cols", default=None)
    parser.add_argument("--folds", default=None)
    parser.add_argument("--max-events-per-market", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260617)
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
        registry_path=Path(args.registry),
        feature_cols_path=Path(args.feature_cols) if args.feature_cols else None,
        fold_ids=_parse_csv(args.folds),
        max_events_per_market=args.max_events_per_market,
        seed=args.seed,
        write_reports=True,
    )
    print(
        f"{report['decision']} liquidity-cost-state harness: "
        f"run={report['run']} folds={len(report['fold_list'])} "
        f"events={sum(report['event_counts']['by_market'].values()) if report['event_counts']['by_market'] else 0}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
