#!/usr/bin/env python3
"""Build a report-only Phase 8 model failure analysis workbench."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from scripts.phase8_model_selection.evaluate_predictions import (
    DEFAULT_COSTS_CONFIG,
    DEFAULT_MODELS_CONFIG,
    PolicyConfig,
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _prediction_manifest_failures,
    _read_json,
    _relative_path,
    _safe_float,
    _safe_int,
    _sum_float,
    _write_json,
    build_policy_frame,
    build_policy_metrics,
    load_policy_config,
)


DEFAULT_OUTPUT_ROOT = Path("reports") / "failure_analysis"
DEFAULT_RUN = "baseline"
RANDOM_BASELINE_SEEDS = tuple(range(1001, 1026))
COST_STRESS_MULTIPLIERS = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def _side(position: pd.Series) -> pd.Series:
    return position.map({-1: "short", 0: "flat", 1: "long"}).fillna("unknown")


def _policy_with_buckets(policy_frame: pd.DataFrame) -> pd.DataFrame:
    frame = policy_frame.copy()
    frame["side"] = _side(frame["position"]) if "position" in frame else "unknown"
    if "timestamp" in frame:
        timestamp = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
        frame["hour_utc"] = timestamp.dt.hour if not timestamp.isna().all() else pd.NA
    else:
        frame["hour_utc"] = pd.NA
    if "session_segment_id" in frame:
        frame["session_bucket"] = frame["session_segment_id"].fillna("missing").astype(str)
    else:
        frame["session_bucket"] = "missing"
    if "direction_margin" in frame:
        confidence = _numeric(frame, "direction_margin").abs()
        frame["confidence_bucket"] = pd.cut(
            confidence,
            bins=[-np.inf, 0.05, 0.10, 0.20, 0.40, np.inf],
            labels=["<=0.05", "0.05-0.10", "0.10-0.20", "0.20-0.40", ">0.40"],
        ).astype(str)
    else:
        frame["confidence_bucket"] = "missing"
    if "policy_reason" in frame:
        frame["regime_bucket"] = frame["policy_reason"].fillna("missing").astype(str)
    else:
        frame["regime_bucket"] = "missing"
    return frame


def _metrics(frame: pd.DataFrame, scope: str, keys: Mapping[str, Any]) -> dict[str, Any]:
    rows = int(len(frame))
    trades = frame[frame["trade_count"].eq(1)] if "trade_count" in frame else frame.iloc[0:0]
    trade_count = int(len(trades))
    gross = _sum_float(frame["gross_dollars"]) if "gross_dollars" in frame else 0.0
    cost = _sum_float(frame["cost_dollars"]) if "cost_dollars" in frame else 0.0
    net = _sum_float(frame["net_dollars"]) if "net_dollars" in frame else 0.0
    net_trades = _numeric(trades, "net_dollars")
    gross_trades = _numeric(trades, "gross_dollars")
    return {
        "scope": scope,
        **dict(keys),
        "row_count": rows,
        "trade_count": trade_count,
        "gross_return_dollars": gross,
        "cost_dollars": cost,
        "net_return_dollars": net,
        "avg_gross_dollars_per_trade": gross / trade_count if trade_count else None,
        "avg_net_dollars_per_trade": net / trade_count if trade_count else None,
        "median_net_dollars_per_trade": _safe_float(net_trades.median())
        if trade_count
        else None,
        "net_win_rate": _safe_float(net_trades.gt(0.0).mean()) if trade_count else None,
        "gross_win_rate": _safe_float(gross_trades.gt(0.0).mean()) if trade_count else None,
        "cost_drag_to_abs_gross": cost / abs(gross) if abs(gross) > 0.0 else None,
    }


def _group_metrics(frame: pd.DataFrame, scope: str, group_cols: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    records: list[dict[str, Any]] = []
    for keys, group in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        records.append(_metrics(group, scope, dict(zip(group_cols, keys))))
    return pd.DataFrame(records).sort_values("net_return_dollars").reset_index(drop=True)


def _pnl_attribution(policy_frame: pd.DataFrame) -> pd.DataFrame:
    frame = _policy_with_buckets(policy_frame)
    frames = [
        _group_metrics(frame, "market", ["market"]),
        _group_metrics(frame, "year", ["year"]) if "year" in frame else pd.DataFrame(),
        _group_metrics(frame, "fold", ["fold_id"]) if "fold_id" in frame else pd.DataFrame(),
        _group_metrics(frame, "side", ["side"]),
        _group_metrics(frame, "hour", ["hour_utc"]),
        _group_metrics(frame, "session", ["session_bucket"]),
        _group_metrics(frame, "confidence", ["confidence_bucket"]),
        _group_metrics(frame, "regime", ["regime_bucket"]),
    ]
    return pd.concat([item for item in frames if not item.empty], ignore_index=True)


def _trade_distribution(policy_frame: pd.DataFrame) -> pd.DataFrame:
    trades = policy_frame[policy_frame["trade_count"].eq(1)].copy()
    if trades.empty:
        return pd.DataFrame(
            [
                {
                    "scope": "overall",
                    "trade_count": 0,
                    "unavailable_reason": "no trades",
                }
            ]
        )
    net = _numeric(trades, "net_dollars").sort_values(ascending=False)
    total_net = float(net.sum())
    records: list[dict[str, Any]] = []
    for pct in (0.01, 0.05, 0.10):
        count = max(1, int(round(len(net) * pct)))
        top = float(net.head(count).sum())
        bottom = float(net.tail(count).sum())
        records.append(
            {
                "scope": f"top_bottom_{int(pct * 100)}pct",
                "trade_count": int(len(net)),
                "selected_trade_count": count,
                "top_net_dollars": top,
                "bottom_net_dollars": bottom,
                "top_share_of_total_net": top / total_net if total_net else None,
                "bottom_share_of_total_net": bottom / total_net if total_net else None,
            }
        )
    records.append(
        {
            "scope": "overall",
            "trade_count": int(len(net)),
            "selected_trade_count": int(len(net)),
            "top_net_dollars": float(net.max()),
            "bottom_net_dollars": float(net.min()),
            "top_share_of_total_net": None,
            "bottom_share_of_total_net": None,
            "median_net_dollars": _safe_float(net.median()),
            "mean_net_dollars": _safe_float(net.mean()),
            "net_std_dollars": _safe_float(net.std(ddof=0)),
        }
    )
    return pd.DataFrame(records)


def _cost_stress(policy_frame: pd.DataFrame) -> pd.DataFrame:
    gross = _sum_float(policy_frame["gross_dollars"]) if "gross_dollars" in policy_frame else 0.0
    base_cost = _sum_float(policy_frame["cost_dollars"]) if "cost_dollars" in policy_frame else 0.0
    rows = []
    for multiplier in COST_STRESS_MULTIPLIERS:
        stressed_cost = base_cost * multiplier
        rows.append(
            {
                "stress_type": "cost_multiplier",
                "stress_value": multiplier,
                "gross_return_dollars": gross,
                "cost_dollars": stressed_cost,
                "net_return_dollars": gross - stressed_cost,
                "edge_survives": gross - stressed_cost > 0.0,
            }
        )
    trades = policy_frame[policy_frame.get("trade_count", pd.Series(dtype=int)).eq(1)].copy()
    if not trades.empty:
        net = _numeric(trades, "net_dollars").sort_values(ascending=False)
        for pct in (0.01, 0.05, 0.10):
            count = max(1, int(round(len(net) * pct)))
            remaining_net = float(net.iloc[count:].sum())
            rows.append(
                {
                    "stress_type": "remove_top_trades",
                    "stress_value": pct,
                    "gross_return_dollars": None,
                    "cost_dollars": None,
                    "net_return_dollars": remaining_net,
                    "edge_survives": remaining_net > 0.0,
                }
            )
    return pd.DataFrame(rows)


def _position_metrics(frame: pd.DataFrame, position: pd.Series, baseline_id: str) -> dict[str, Any]:
    position = position.reindex(frame.index).fillna(0).astype(int)
    gross = position * _numeric(frame, "price_move").fillna(0.0) * _numeric(frame, "point_value").fillna(0.0)
    cost = pd.Series(
        np.where(position.ne(0), _numeric(frame, "round_turn_cost_dollars").fillna(0.0), 0.0),
        index=frame.index,
    )
    net = gross - cost
    trade_count = int(position.ne(0).sum())
    return {
        "baseline_id": baseline_id,
        "status": "PASS",
        "row_count": int(len(frame)),
        "trade_count": trade_count,
        "gross_return_dollars": float(gross.sum()),
        "cost_dollars": float(cost.sum()),
        "net_return_dollars": float(net.sum()),
        "avg_net_dollars_per_trade": float(net.sum()) / trade_count if trade_count else None,
    }


def _random_entry_baseline(frame: pd.DataFrame, seeds: Iterable[int] = RANDOM_BASELINE_SEEDS) -> dict[str, Any]:
    candidate = frame[frame["trade_count"].eq(1)]
    trade_count = int(len(candidate))
    if trade_count <= 0 or frame.empty:
        return {
            "baseline_id": "random_entry",
            "status": "MISSING_WITH_REASON",
            "reason": "candidate has no trades",
        }
    candidate_position = candidate["position"].astype(int)
    long_rate = float(candidate_position.eq(1).mean())
    records: list[dict[str, Any]] = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        selected = rng.choice(frame.index.to_numpy(), size=min(trade_count, len(frame)), replace=False)
        position = pd.Series(0, index=frame.index, dtype=int)
        random_sides = np.where(rng.random(len(selected)) < long_rate, 1, -1)
        position.loc[selected] = random_sides
        record = _position_metrics(frame, position, f"random_entry_seed_{seed}")
        record["seed"] = seed
        records.append(record)
    net_values = pd.Series([record["net_return_dollars"] for record in records])
    return {
        "baseline_id": "random_entry",
        "status": "PASS",
        "simulation_count": len(records),
        "trade_count": trade_count,
        "mean_net_return_dollars": _safe_float(net_values.mean()),
        "median_net_return_dollars": _safe_float(net_values.median()),
        "p05_net_return_dollars": _safe_float(net_values.quantile(0.05)),
        "p95_net_return_dollars": _safe_float(net_values.quantile(0.95)),
        "best_net_return_dollars": _safe_float(net_values.max()),
        "candidate_beats_random_median": bool(
            _sum_float(candidate["net_dollars"]) > float(net_values.median())
        ),
    }


def _simple_trend_position(frame: pd.DataFrame) -> pd.Series | None:
    if not {"market", "fold_id", "timestamp", "execution_open"} <= set(frame.columns):
        return None
    work = frame.sort_values(["market", "fold_id", "timestamp"]).copy()
    prior_open = work.groupby(["market", "fold_id"], dropna=False)["execution_open"].shift(1)
    move = _numeric(work, "execution_open") - pd.to_numeric(prior_open, errors="coerce")
    position = pd.Series(np.sign(move).fillna(0).astype(int).to_numpy(), index=work.index)
    return position.reindex(frame.index).fillna(0).astype(int)


def _baseline_comparison(policy_frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = policy_frame.copy()
    candidate_net = _sum_float(frame["net_dollars"]) if "net_dollars" in frame else 0.0
    candidate_gross = _sum_float(frame["gross_dollars"]) if "gross_dollars" in frame else 0.0
    candidate_cost = _sum_float(frame["cost_dollars"]) if "cost_dollars" in frame else 0.0
    candidate_trades = int(frame["trade_count"].sum()) if "trade_count" in frame else 0
    rows: list[dict[str, Any]] = [
        {
            "baseline_id": "candidate",
            "status": "PASS",
            "row_count": int(len(frame)),
            "trade_count": candidate_trades,
            "gross_return_dollars": candidate_gross,
            "cost_dollars": candidate_cost,
            "net_return_dollars": candidate_net,
            "avg_net_dollars_per_trade": candidate_net / candidate_trades
            if candidate_trades
            else None,
        },
        {
            "baseline_id": "no_trade",
            "status": "PASS",
            "row_count": int(len(frame)),
            "trade_count": 0,
            "gross_return_dollars": 0.0,
            "cost_dollars": 0.0,
            "net_return_dollars": 0.0,
            "avg_net_dollars_per_trade": None,
        },
        {
            "baseline_id": "cost_only",
            "status": "PASS",
            "row_count": int(len(frame)),
            "trade_count": candidate_trades,
            "gross_return_dollars": 0.0,
            "cost_dollars": candidate_cost,
            "net_return_dollars": -candidate_cost,
            "avg_net_dollars_per_trade": -candidate_cost / candidate_trades
            if candidate_trades
            else None,
        },
    ]
    random_baseline = _random_entry_baseline(frame)
    rows.append(random_baseline)
    trend_position = _simple_trend_position(frame)
    if trend_position is None:
        rows.append(
            {
                "baseline_id": "simple_trend",
                "status": "MISSING_WITH_REASON",
                "reason": "timestamp/execution_open columns unavailable",
            }
        )
        rows.append(
            {
                "baseline_id": "simple_mean_reversion",
                "status": "MISSING_WITH_REASON",
                "reason": "timestamp/execution_open columns unavailable",
            }
        )
    else:
        rows.append(_position_metrics(frame, trend_position, "simple_trend"))
        rows.append(_position_metrics(frame, -trend_position, "simple_mean_reversion"))
    rows.append(
        {
            "baseline_id": "simple_carry",
            "status": "MISSING_WITH_REASON",
            "reason": "carry/term-structure fields are not present in Phase 8 policy rows",
        }
    )
    comparison = pd.DataFrame(rows)
    missing = comparison[
        comparison["baseline_id"].isin(
            ["random_entry", "simple_trend", "simple_mean_reversion", "simple_carry"]
        )
        & ~comparison["status"].eq("PASS")
    ]["baseline_id"].astype(str).tolist()
    candidate_beats_no_trade = candidate_net > 0.0
    required_baselines_ready = not missing
    summary = {
        "gate_name": "baseline_comparison_gate",
        "status": "PASS" if candidate_beats_no_trade and required_baselines_ready else "FAIL",
        "baseline_comparison_ready": candidate_beats_no_trade and required_baselines_ready,
        "candidate_beats_no_trade": candidate_beats_no_trade,
        "missing_required_baselines": missing,
        "baselines": comparison.to_dict(orient="records"),
        "failure_count": (0 if candidate_beats_no_trade else 1) + len(missing),
        "failures": (
            ([] if candidate_beats_no_trade else ["candidate net_return_dollars does not beat no-trade baseline"])
            + [f"baseline comparison missing: {baseline_id}" for baseline_id in missing]
        ),
    }
    return comparison, summary


def _capacity_liquidity(policy_frame: pd.DataFrame) -> dict[str, Any]:
    trade_count = int(policy_frame["trade_count"].sum()) if "trade_count" in policy_frame else 0
    cost = _sum_float(policy_frame["cost_dollars"]) if "cost_dollars" in policy_frame else 0.0
    return {
        "gate_name": "capacity_liquidity_gate",
        "status": "MISSING_EVIDENCE",
        "capacity_liquidity_ready": False,
        "trade_count": trade_count,
        "avg_cost_dollars_per_trade": cost / trade_count if trade_count else None,
        "avg_trades_per_session": _safe_float(
            policy_frame.groupby("session_id")["trade_count"].sum().mean()
        )
        if "session_id" in policy_frame and "trade_count" in policy_frame
        else None,
        "failures": [
            "capacity evidence missing",
            "liquidity evidence missing",
            "market-impact evidence missing",
        ],
        "policy": "report-only turnover and cost proxy; external liquidity/depth evidence is required for PASS",
    }


def _failure_classifications(
    *,
    policy_metrics: Mapping[str, Any],
    baseline_summary: Mapping[str, Any],
    stress: pd.DataFrame,
    attribution: pd.DataFrame,
) -> pd.DataFrame:
    overall = policy_metrics.get("overall", {}) if isinstance(policy_metrics, Mapping) else {}
    gross = _safe_float(overall.get("gross_return_dollars")) or 0.0
    net = _safe_float(overall.get("net_return_dollars")) or 0.0
    cost = _safe_float(overall.get("cost_dollars")) or 0.0
    trade_count = _safe_int(overall.get("trade_count")) or 0
    row_count = _safe_int(overall.get("row_count")) or 0
    labels: list[dict[str, Any]] = []
    if gross <= 0.0:
        labels.append(
            {
                "classification": "gross_edge_absent",
                "severity": "Severe",
                "metric": gross,
                "explanation": "The policy lost money before costs.",
            }
        )
    if gross > 0.0 and net <= 0.0:
        labels.append(
            {
                "classification": "cost_drag_dominant",
                "severity": "Severe",
                "metric": cost / abs(gross) if abs(gross) else None,
                "explanation": "Gross edge was positive but execution costs consumed it.",
            }
        )
    if row_count and trade_count / row_count > 0.20:
        labels.append(
            {
                "classification": "overtrading",
                "severity": "Medium",
                "metric": trade_count / row_count,
                "explanation": "The policy traded a large share of eligible rows.",
            }
        )
    if not baseline_summary.get("candidate_beats_no_trade"):
        labels.append(
            {
                "classification": "baseline_failure",
                "severity": "Severe",
                "metric": net,
                "explanation": "The candidate did not beat the no-trade baseline.",
            }
        )
    required = stress[
        stress["stress_type"].eq("cost_multiplier") & stress["stress_value"].eq(2.0)
    ]
    if not required.empty and bool(required.iloc[0]["edge_survives"]) is False:
        labels.append(
            {
                "classification": "cost_stress_failure",
                "severity": "Severe",
                "metric": required.iloc[0]["net_return_dollars"],
                "explanation": "The candidate does not survive 2x cost stress.",
            }
        )
    if not attribution.empty:
        market_rows = attribution[attribution["scope"].eq("market")]
        if not market_rows.empty and market_rows["trade_count"].sum() > 0:
            share = float(market_rows["trade_count"].max() / market_rows["trade_count"].sum())
            if share > 0.75:
                labels.append(
                    {
                        "classification": "market_concentration",
                        "severity": "Medium",
                        "metric": share,
                        "explanation": "Trades are concentrated in one market.",
                    }
                )
    if not labels:
        labels.append(
            {
                "classification": "no_failure_classification_triggered",
                "severity": "Low",
                "metric": None,
                "explanation": "No failure classifier triggered from available evidence.",
            }
        )
    return pd.DataFrame(labels)


def _markdown(payload: Mapping[str, Any]) -> str:
    findings = "\n".join(f"- {item}" for item in payload["top_findings"])
    classifications = "\n".join(
        f"- `{row['classification']}` ({row['severity']}): {row['explanation']}"
        for row in payload["failure_classifications"]
    )
    return "\n".join(
        [
            "# Phase 8 Failure Analysis",
            "",
            f"Run: `{payload['run']}`",
            "",
            "This is a report-only failure analysis. It does not tune, promote, paper trade, or live trade.",
            "",
            "## Top Findings",
            "",
            findings or "- None.",
            "",
            "## Failure Classifications",
            "",
            classifications or "- None.",
            "",
            "## Proceed Status",
            "",
            f"`{payload['proceed_status']}`",
            "",
        ]
    )


def build_failure_analysis(
    *,
    predictions_path: Path,
    predictions_manifest: Path,
    costs_config: Path,
    models_config: Path,
    output_root: Path,
    run: str,
    policy: PolicyConfig,
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
    )

    if failures:
        policy_frame = pd.DataFrame()
        policy_metrics, _, _ = build_policy_metrics(policy_frame)
    else:
        policy_frame, policy_failures, _ = build_policy_frame(predictions, costs_config, policy)
        failures.extend(policy_failures)
        policy_metrics, _, _ = build_policy_metrics(policy_frame)

    attribution = _pnl_attribution(policy_frame)
    gross_net = pd.DataFrame([policy_metrics["overall"]])
    trade_distribution = _trade_distribution(policy_frame)
    stress = _cost_stress(policy_frame)
    baseline_comparison, baseline_summary = _baseline_comparison(policy_frame)
    capacity = _capacity_liquidity(policy_frame)
    classifications = _failure_classifications(
        policy_metrics=policy_metrics,
        baseline_summary=baseline_summary,
        stress=stress,
        attribution=attribution,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "failure_analysis_summary.json"
    md_path = output_root / "failure_analysis.md"
    attribution_path = output_root / "pnl_attribution.csv"
    gross_net_path = output_root / "gross_net_cost_decomposition.csv"
    trade_distribution_path = output_root / "trade_distribution.csv"
    regime_path = output_root / "regime_session_breakdown.csv"
    baseline_path = output_root / "baseline_comparison.csv"
    stress_path = output_root / "stress_tests.csv"
    classifications_path = output_root / "failure_classifications.csv"
    paths = {
        "summary": summary_path,
        "markdown": md_path,
        "pnl_attribution": attribution_path,
        "gross_net_cost_decomposition": gross_net_path,
        "trade_distribution": trade_distribution_path,
        "regime_session_breakdown": regime_path,
        "baseline_comparison": baseline_path,
        "stress_tests": stress_path,
        "failure_classifications": classifications_path,
    }
    _write_csv(attribution_path, attribution)
    _write_csv(gross_net_path, gross_net)
    _write_csv(trade_distribution_path, trade_distribution)
    _write_csv(regime_path, attribution[attribution["scope"].isin(["session", "regime", "hour", "confidence"])])
    _write_csv(baseline_path, baseline_comparison)
    _write_csv(stress_path, stress)
    _write_csv(classifications_path, classifications)

    overall = policy_metrics["overall"]
    top_findings = [
        (
            "Gross PnL is "
            f"{overall.get('gross_return_dollars')} and net PnL is {overall.get('net_return_dollars')}."
        ),
        f"Total costs are {overall.get('cost_dollars')}.",
        (
            "Baseline gate status is "
            f"{baseline_summary['status']} with {baseline_summary['failure_count']} failures."
        ),
        f"Capacity/liquidity status is {capacity['status']}.",
    ]
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "diagnostic_type": "phase8_failure_analysis",
        "diagnostic_only": True,
        "status": "PASS" if not failures else "FAIL",
        "failure_analysis_ready": not failures,
        "run": run,
        "prediction_path": _relative_path(predictions_path),
        "predictions_manifest_path": _relative_path(predictions_manifest),
        "prediction_count": int(len(predictions)),
        "policy_row_count": int(len(policy_frame)),
        "failure_count": len(failures),
        "failures": failures,
        "top_findings": top_findings,
        "policy_metrics_overall": overall,
        "baseline_comparison_gate": baseline_summary,
        "capacity_liquidity_gate": capacity,
        "failure_classifications": classifications.to_dict(orient="records"),
        "proceed_status": "no" if failures or baseline_summary["status"] != "PASS" else "yes with problems",
        "input_file_hashes": _file_hash_map([predictions_path, predictions_manifest, costs_config, models_config]),
        "outputs": {key: _relative_path(value) for key, value in paths.items()},
        "research_only": True,
        "model_promotion_allowed": False,
    }
    _write_json(summary_path, payload)
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--predictions-manifest", required=True)
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--long-short-margin", type=float, default=0.05)
    parser.add_argument("--min-fade-success", type=float, default=0.50)
    parser.add_argument("--max-trend-danger", type=float, default=0.50)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    policy = load_policy_config(
        Path(args.models_config),
        long_short_margin=args.long_short_margin,
        min_fade_success=args.min_fade_success,
        max_trend_danger=args.max_trend_danger,
    )
    result = build_failure_analysis(
        predictions_path=Path(args.predictions),
        predictions_manifest=Path(args.predictions_manifest),
        costs_config=Path(args.costs_config),
        models_config=Path(args.models_config),
        output_root=Path(args.output_root),
        run=args.run,
        policy=policy,
    )
    print(
        "PASS" if not result["failure_count"] else "FAIL",
        "failure analysis:",
        f"rows={result['policy_row_count']}",
        f"net={result['policy_metrics_overall'].get('net_return_dollars')}",
        f"baseline_gate={result['baseline_comparison_gate']['status']}",
        f"summary={result['outputs']['summary']}",
    )
    return 1 if result["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
