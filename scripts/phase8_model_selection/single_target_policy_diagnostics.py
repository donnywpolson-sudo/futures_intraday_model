#!/usr/bin/env python3
"""Costed diagnostic-only policy/PnL checks for one prediction target."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.phase8_model_selection.evaluate_predictions import (
    EXECUTION_POLICY_NAME,
    EXECUTION_REALISM,
    PREDICTION_KEY_CANDIDATES,
    _apply_non_overlapping_execution_policy,
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _load_cost_markets,
    _prediction_manifest_failures,
    _read_json,
    _read_yaml,
    _relative_path,
    _safe_float,
    _write_json,
    build_policy_metrics,
)
from scripts.phase8_model_selection.single_target_diagnostics import (
    DEFAULT_MIN_CLASS_RATE,
    DEFAULT_TARGET_NAME,
    REQUIRED_COLUMNS,
    _class_balance,
    _coverage,
    _duplicate_prediction_count,
    _score_summary,
)
from scripts.validation.target_policy_contract import (
    evaluate_target_policy_compatibility,
    fixed_horizon_exit_policy_contract,
    opening_range_acceptance_contract,
)


DIAGNOSTIC_TYPE = "single_target_costed_policy_pnl"
POLICY_CONTRACT = "single_target_unique_max_probability_non_overlapping_one_contract"
TRADE_COLUMNS = [
    "market",
    "year",
    "fold_id",
    "timestamp",
    "target_entry_ts",
    "target_exit_ts",
    "model_id",
    "target_name",
    "position",
    "policy_reason",
    "execution_run_id",
    "execution_open",
    "execution_close",
    "price_move",
    "gross_dollars",
    "cost_dollars",
    "net_dollars",
]


def _output_paths(reports_root: Path, run: str) -> dict[str, Path]:
    return {
        "diagnostics": reports_root / f"{run}_single_target_policy_diagnostics.json",
        "policy_summary": reports_root / f"{run}_single_target_policy_summary.csv",
        "turnover": reports_root / f"{run}_single_target_policy_turnover.csv",
        "trades": reports_root / f"{run}_single_target_policy_trades.csv",
    }


def _load_market_costs(costs_config: Path, markets: list[str]) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, float], list[str]]:
    costs_by_market, _ = _load_cost_markets(costs_config)
    point_values: dict[str, float] = {}
    round_turn_costs: dict[str, float] = {}
    tick_values: dict[str, float] = {}
    slippage_ticks: dict[str, float] = {}
    missing_cost_markets: list[str] = []
    for market in markets:
        market_costs = costs_by_market.get(market)
        point_value = _safe_float(market_costs.get("point_value") if market_costs else None)
        round_turn = _safe_float(
            market_costs.get("round_turn_cost_dollars") if market_costs else None
        )
        tick_value = _safe_float(market_costs.get("tick_value") if market_costs else None)
        slippage = _safe_float(
            market_costs.get("slippage_ticks_per_side") if market_costs else None
        )
        if point_value is None or round_turn is None:
            missing_cost_markets.append(market)
            continue
        point_values[market] = point_value
        round_turn_costs[market] = round_turn
        if tick_value is not None:
            tick_values[market] = tick_value
        if slippage is not None:
            slippage_ticks[market] = slippage
    return point_values, round_turn_costs, tick_values, slippage_ticks, missing_cost_markets


def _build_single_target_policy_frame(
    target_frame: pd.DataFrame,
    costs_config: Path,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    if target_frame.empty:
        return pd.DataFrame(), ["no prediction rows available for single-target policy diagnostics"], warnings

    base = target_frame.copy()
    for column in (
        "p_long",
        "p_short",
        "p_flat",
        "execution_open",
        "execution_close",
    ):
        if column not in base.columns:
            base[column] = np.nan
        base[column] = pd.to_numeric(base[column], errors="coerce")

    missing_probabilities = base[["p_long", "p_short", "p_flat"]].isna().any(axis=1)
    if bool(missing_probabilities.any()):
        failures.append(
            "single-target policy rows with missing class probabilities: "
            f"{int(missing_probabilities.sum())}"
        )
    missing_prices = base["execution_open"].isna() | base["execution_close"].isna()
    if bool(missing_prices.any()):
        failures.append(f"single-target policy rows with missing execution prices: {int(missing_prices.sum())}")

    probabilities = base[["p_long", "p_short", "p_flat"]]
    max_probability = probabilities.max(axis=1)
    long_selected = (
        base["p_long"].eq(max_probability)
        & base["p_long"].gt(base["p_short"])
        & base["p_long"].gt(base["p_flat"])
        & ~missing_probabilities
    )
    short_selected = (
        base["p_short"].eq(max_probability)
        & base["p_short"].gt(base["p_long"])
        & base["p_short"].gt(base["p_flat"])
        & ~missing_probabilities
    )
    flat_selected = (
        base["p_flat"].eq(max_probability)
        & base["p_flat"].gt(base["p_long"])
        & base["p_flat"].gt(base["p_short"])
        & ~missing_probabilities
    )
    base["candidate_position"] = 0
    base.loc[long_selected, "candidate_position"] = 1
    base.loc[short_selected, "candidate_position"] = -1
    base["candidate_position"] = base["candidate_position"].astype(int)
    base["model_selected_class"] = "tie_or_invalid_flat"
    base.loc[long_selected, "model_selected_class"] = "long"
    base.loc[short_selected, "model_selected_class"] = "short"
    base.loc[flat_selected, "model_selected_class"] = "flat"
    base.loc[missing_probabilities, "model_selected_class"] = "missing_probability"
    base["policy_reason"] = "probability_tie_flat"
    base.loc[flat_selected, "policy_reason"] = "model_selected_flat"
    base.loc[long_selected | short_selected, "policy_reason"] = "trade"
    base.loc[missing_probabilities, "policy_reason"] = "missing_probability"
    base["candidate_trade_count"] = base["candidate_position"].ne(0).astype(int)
    base["direction_margin"] = base["p_long"] - base["p_short"]
    base["direction_probability"] = np.where(
        base["candidate_position"].eq(1),
        base["p_long"],
        np.where(base["candidate_position"].eq(-1), base["p_short"], np.nan),
    )
    base["no_direction_signal"] = base["candidate_position"].eq(0)
    base["blocked_by_fade_filter"] = False
    base["blocked_by_flat_probability"] = False
    base["blocked_by_trend_danger"] = False

    markets = sorted(str(value) for value in base["market"].dropna().unique())
    point_values, round_turn_costs, tick_values, slippage_ticks, missing_cost_markets = _load_market_costs(
        costs_config,
        markets,
    )
    if missing_cost_markets:
        failures.append(f"missing usable costs for markets: {missing_cost_markets}")
    base["point_value"] = base["market"].map(point_values)
    base["round_turn_cost_dollars"] = base["market"].map(round_turn_costs)
    base["tick_value"] = base["market"].map(tick_values)
    base["slippage_ticks_per_side"] = base["market"].map(slippage_ticks).fillna(0.0)
    base["price_move"] = base["execution_close"] - base["execution_open"]
    base["candidate_gross_dollars"] = (
        base["candidate_position"] * base["price_move"] * base["point_value"]
    )
    base["candidate_cost_dollars"] = np.where(
        base["candidate_position"].ne(0),
        base["round_turn_cost_dollars"],
        0.0,
    )
    base["candidate_net_dollars"] = (
        base["candidate_gross_dollars"] - base["candidate_cost_dollars"]
    )

    base, execution_failures = _apply_non_overlapping_execution_policy(base)
    failures.extend(execution_failures)
    base["gross_dollars"] = base["position"] * base["price_move"] * base["point_value"]
    base["cost_dollars"] = np.where(base["position"].ne(0), base["round_turn_cost_dollars"], 0.0)
    base["slippage_cost_dollars"] = np.where(
        base["position"].ne(0),
        2.0 * base["slippage_ticks_per_side"] * base["tick_value"].fillna(0.0),
        0.0,
    )
    base["commission_cost_dollars"] = np.maximum(
        base["cost_dollars"] - base["slippage_cost_dollars"],
        0.0,
    )
    base["net_dollars"] = base["gross_dollars"] - base["cost_dollars"]
    base["trade_count"] = base["position"].ne(0).astype(int)
    base["long_count"] = base["position"].eq(1).astype(int)
    base["short_count"] = base["position"].eq(-1).astype(int)
    base["flat_count"] = base["position"].eq(0).astype(int)

    sort_cols = [column for column in ("market", "fold_id", "timestamp") if column in base.columns]
    base = base.sort_values(sort_cols).reset_index(drop=True)
    group_cols = [column for column in ("market", "fold_id") if column in base.columns]
    if group_cols:
        previous_position = base.groupby(group_cols, dropna=False)["position"].shift(1).fillna(0)
    else:
        previous_position = base["position"].shift(1).fillna(0)
    base["position_change_abs"] = (base["position"] - previous_position).abs()
    base["round_turns_per_bar"] = base["trade_count"].astype(float)
    warnings.append(
        "single-target policy diagnostics use unique max-probability class selection "
        "and max-one-contract non-overlapping target-window execution; partial fills, "
        "order rejection, latency, and capacity remain outside this diagnostic"
    )
    return base, failures, warnings


def evaluate_single_target_policy_diagnostics(
    *,
    predictions_path: Path,
    predictions_manifest: Path,
    costs_config: Path,
    models_config: Path,
    reports_root: Path,
    run: str,
    target_name: str = DEFAULT_TARGET_NAME,
    min_class_rate: float = DEFAULT_MIN_CLASS_RATE,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    warnings: list[str] = []
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

    _read_yaml(models_config)
    if not models_config.exists():
        failures.append(f"models config missing: {_relative_path(models_config)}")
    if not costs_config.exists():
        failures.append(f"costs config missing: {_relative_path(costs_config)}")

    target_names = (
        sorted(predictions["target_name"].dropna().astype(str).unique().tolist())
        if "target_name" in predictions.columns
        else []
    )
    if len(target_names) != 1:
        failures.append(
            f"single-target policy diagnostics require exactly one target, found {target_names}"
        )
    elif target_names[0] != target_name:
        failures.append(
            "single-target policy diagnostics target mismatch: "
            f"observed={target_names[0]!r} expected={target_name!r}"
        )

    target_frame = (
        predictions[predictions["target_name"].astype(str).eq(target_name)].copy()
        if "target_name" in predictions.columns
        else pd.DataFrame()
    )
    if "split_group" in target_frame.columns and target_frame["split_group"].astype(str).eq("final_holdout").any():
        failures.append("final_holdout predictions cannot be used for single-target policy diagnostics")

    duplicate_count, duplicate_failures = _duplicate_prediction_count(target_frame)
    failures.extend(duplicate_failures)
    class_balance, class_failures = _class_balance(target_frame, min_class_rate=min_class_rate)
    failures.extend(class_failures)
    score_summary, score_failures = _score_summary(target_frame, target_name)
    failures.extend(score_failures)

    policy_frame, policy_failures, policy_warnings = _build_single_target_policy_frame(
        target_frame,
        costs_config,
    )
    failures.extend(policy_failures)
    warnings.extend(policy_warnings)
    policy_metrics, policy_summary, turnover = build_policy_metrics(policy_frame)
    target_policy_contract = opening_range_acceptance_contract()
    policy_evaluation_contract = fixed_horizon_exit_policy_contract()
    target_policy_compatibility = evaluate_target_policy_compatibility(
        target_policy_contract,
        policy_evaluation_contract,
    )
    if not bool(target_policy_compatibility["compatible"]):
        warnings.extend(str(item) for item in target_policy_compatibility["warnings"])

    output_paths = _output_paths(reports_root, run)
    reports_root.mkdir(parents=True, exist_ok=True)
    policy_summary.to_csv(output_paths["policy_summary"], index=False)
    turnover.to_csv(output_paths["turnover"], index=False)
    trade_columns = [column for column in TRADE_COLUMNS if column in policy_frame.columns]
    trades = policy_frame.loc[policy_frame.get("trade_count", pd.Series(dtype=int)).eq(1), trade_columns].copy()
    if trades.empty and trade_columns:
        trades = pd.DataFrame(columns=trade_columns)
    trades.to_csv(output_paths["trades"], index=False)

    overall = policy_metrics.get("overall", {})
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "run": run,
        "target_name": target_name,
        "diagnostic_type": DIAGNOSTIC_TYPE,
        "diagnostic_only": True,
        "policy_contract": POLICY_CONTRACT,
        "target_policy_contract": target_policy_contract,
        "policy_evaluation_contract": policy_evaluation_contract,
        "target_policy_compatibility": target_policy_compatibility,
        "fixed_exit_policy_mismatch": not bool(target_policy_compatibility["compatible"]),
        "decisive_economic_evidence_allowed": bool(
            target_policy_compatibility["decisive_economic_evidence_allowed"]
        ),
        "economic_approval_allowed": bool(target_policy_compatibility["economic_approval_allowed"]),
        "economic_rejection_allowed": bool(target_policy_compatibility["economic_rejection_allowed"]),
        "execution_policy": EXECUTION_POLICY_NAME,
        "execution_realism": EXECUTION_REALISM,
        "selection_policy": {
            "position": "unique max of p_long/p_short/p_flat; p_long -> +1, p_short -> -1",
            "flat_rule": "p_flat unique max, probability ties, and invalid probability rows are flat",
            "threshold_search": False,
            "top_fraction_search": False,
            "post_test_retune": False,
            "max_contracts": 1,
        },
        "canonical_phase8_policy_applicable": False,
        "canonical_phase8_policy_reason": (
            "canonical Phase 8 policy evaluation requires expected-return, fade, and "
            "side-aware trend target prediction families; this adapter computes "
            "diagnostic costed PnL for one direction target only"
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
        "costs_config": _relative_path(costs_config),
        "models_config": _relative_path(models_config),
        "output_root": _relative_path(reports_root),
        "input_file_hashes": _file_hash_map(
            [predictions_path, predictions_manifest, costs_config, models_config]
        ),
        "coverage": _coverage(target_frame),
        "duplicate_prediction_count": duplicate_count,
        "class_balance": class_balance,
        "score_summary": score_summary,
        "policy_metrics": policy_metrics,
        "overall": overall,
        "trade_count": int(overall.get("trade_count", 0) or 0),
        "candidate_trade_count": int(overall.get("candidate_trade_count", 0) or 0),
        "blocked_by_execution_overlap": int(overall.get("blocked_by_execution_overlap", 0) or 0),
        "gross_return_dollars": overall.get("gross_return_dollars"),
        "cost_dollars": overall.get("cost_dollars"),
        "net_return_dollars": overall.get("net_return_dollars"),
        "policy_summary_row_count": int(len(policy_summary)),
        "turnover_row_count": int(len(turnover)),
        "trade_row_count": int(len(trades)),
        "diagnostics_path": _relative_path(output_paths["diagnostics"]),
        "policy_summary_path": _relative_path(output_paths["policy_summary"]),
        "turnover_path": _relative_path(output_paths["turnover"]),
        "trades_path": _relative_path(output_paths["trades"]),
        "acceptance_scope": (
            "diagnostic fixed-exit costed single-target policy/PnL evidence only; "
            "for path-opportunity targets this is target/policy mismatch evidence, "
            "not decisive economic approval/rejection, not canonical multi-target "
            "Phase 8 evidence, not model promotion, and not live/paper readiness"
        ),
    }
    _write_json(output_paths["diagnostics"], payload)
    payload["diagnostics_path"] = output_paths["diagnostics"]
    payload["policy_summary_output_path"] = output_paths["policy_summary"]
    payload["turnover_output_path"] = output_paths["turnover"]
    payload["trades_output_path"] = output_paths["trades"]
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--predictions-manifest", required=True)
    parser.add_argument("--costs-config", required=True)
    parser.add_argument("--models-config", required=True)
    parser.add_argument("--reports-root", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--target-name", default=DEFAULT_TARGET_NAME)
    parser.add_argument("--min-class-rate", type=float, default=DEFAULT_MIN_CLASS_RATE)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = evaluate_single_target_policy_diagnostics(
        predictions_path=Path(args.predictions),
        predictions_manifest=Path(args.predictions_manifest),
        costs_config=Path(args.costs_config),
        models_config=Path(args.models_config),
        reports_root=Path(args.reports_root),
        run=args.run,
        target_name=args.target_name,
        min_class_rate=args.min_class_rate,
    )
    overall = result["overall"]
    print(
        "FAIL" if result["failure_count"] else "PASS",
        "single-target policy diagnostics:",
        f"rows={result['coverage'].get('row_count', 0)}",
        f"trades={overall.get('trade_count', 0)}",
        f"net_dollars={overall.get('net_return_dollars', 0.0)}",
        f"promotion_allowed={result['promotion_allowed']}",
        f"failures={result['failure_count']}",
    )
    return 1 if result["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
