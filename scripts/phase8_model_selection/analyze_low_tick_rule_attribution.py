#!/usr/bin/env python3
"""Attribute low realized ticks to target, model, policy, and execution rules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from scripts.phase8_model_selection.analyze_trade_tick_excursions import (
    DEFAULT_BARS,
    DEFAULT_COSTS,
    DEFAULT_MARKET,
    DEFAULT_TRADES,
    CostConfig,
    _check_columns,
    _relative,
    _resolve,
    build_trade_excursion_frame,
    load_bars,
    load_cost_config,
    load_trades,
)
from scripts.phase8_model_selection.single_target_policy_diagnostics import (
    _build_single_target_policy_frame,
)


HYPOTHESIS_ID = "opening_range_acceptance_continuation_30m_v1"
DEFAULT_PREDICTIONS = Path(
    "data/predictions/opening_range_acceptance_continuation_30m_v1_model_expansion/"
    "opening_range_acceptance_continuation_30m_v1_model_expansion_s1/oos_predictions.parquet"
)
DEFAULT_OUTPUT = Path(
    "docs/opening_range_acceptance_continuation_30m_v1_low_tick_rule_attribution.md"
)
TARGET_DIRECTION = "target_direction_opening_range_acceptance_continuation_30m"
TARGET_VALID = "target_valid_opening_range_acceptance_continuation_30m"
TARGET_THRESHOLD = "target_threshold_ticks_opening_range_acceptance_continuation_30m"
TARGET_ACCEPTANCE_DISTANCE = "target_acceptance_distance_ticks_opening_range_acceptance_continuation_30m"
TARGET_FAVORABLE = "target_favorable_excursion_ticks_opening_range_acceptance_continuation_30m"
TARGET_ADVERSE = "target_adverse_excursion_ticks_opening_range_acceptance_continuation_30m"

PREDICTION_REQUIRED_COLUMNS = (
    "market",
    "year",
    "fold_id",
    "timestamp",
    "p_long",
    "p_short",
    "p_flat",
    "y_true",
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


def _pct(count: int, total: int) -> float:
    return 100.0 * count / total if total else 0.0


def _count_pct(count: int, total: int) -> str:
    return f"{count} ({_pct(count, total):.1f}%)"


def _fmt(value: float, digits: int = 2) -> str:
    if pd.isna(value):
        return "nan"
    return f"{float(value):.{digits}f}"


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def load_predictions(path: Path) -> pd.DataFrame:
    predictions = pd.read_parquet(path)
    _check_columns(predictions, PREDICTION_REQUIRED_COLUMNS, "predictions")
    out = predictions.copy()
    for column in ("timestamp", "target_entry_ts", "target_exit_ts"):
        out[column] = pd.to_datetime(out[column], utc=True, errors="coerce")
    for column in ("year", "y_true"):
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("Int64")
    for column in ("p_long", "p_short", "p_flat", "execution_open", "execution_close"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def load_target_context(path: Path) -> pd.DataFrame:
    context = pd.read_parquet(path, columns=list(TARGET_CONTEXT_COLUMNS))
    _check_columns(context, TARGET_CONTEXT_COLUMNS, "target context")
    out = context.copy()
    out = out.rename(columns={"ts": "timestamp"})
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


def build_policy_frame(predictions: pd.DataFrame, costs_config: Path, costs: CostConfig) -> pd.DataFrame:
    _check_columns(predictions, PREDICTION_REQUIRED_COLUMNS, "predictions")
    policy_frame, failures, _warnings = _build_single_target_policy_frame(predictions, costs_config)
    if failures:
        raise ValueError(f"single-target policy frame failures: {failures}")
    policy_frame["candidate_fixed_exit_ticks"] = policy_frame["candidate_gross_dollars"] / costs.tick_value
    policy_frame["executed_fixed_exit_ticks"] = policy_frame["gross_dollars"] / costs.tick_value
    policy_frame["current_cost_ticks"] = policy_frame["cost_dollars"] / costs.tick_value
    policy_frame["executed_net_ticks"] = policy_frame["executed_fixed_exit_ticks"] - policy_frame["current_cost_ticks"]
    return policy_frame


def summarize_policy_stages(policy_frame: pd.DataFrame) -> pd.DataFrame:
    stages = [
        ("candidate_pre_nonoverlap", policy_frame["candidate_position"].ne(0), "candidate_fixed_exit_ticks"),
        ("executed_after_nonoverlap", policy_frame["position"].ne(0), "executed_fixed_exit_ticks"),
        ("blocked_by_nonoverlap", policy_frame["blocked_by_execution_overlap"].fillna(False), "candidate_fixed_exit_ticks"),
    ]
    rows: list[dict[str, object]] = []
    for stage, mask, tick_column in stages:
        subset = policy_frame.loc[mask].copy()
        ticks = _numeric(subset, tick_column) if not subset.empty else pd.Series(dtype=float)
        rows.append(
            {
                "stage": stage,
                "row_count": int(len(subset)),
                "mean_ticks": float(ticks.mean()) if not ticks.empty else float("nan"),
                "median_ticks": float(ticks.median()) if not ticks.empty else float("nan"),
                "realized_le_2_count": int(ticks.le(2).sum()) if not ticks.empty else 0,
                "realized_le_2_rate": float(ticks.le(2).mean()) if not ticks.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def confidence_decile_summary(policy_frame: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    candidates = policy_frame.loc[policy_frame["candidate_position"].ne(0)].copy()
    _check_columns(candidates, ("direction_probability", "candidate_fixed_exit_ticks"), "candidate frame")
    if candidates.empty:
        raise ValueError("no candidate trades available for confidence deciles")
    candidates["confidence_decile"] = pd.qcut(
        pd.to_numeric(candidates["direction_probability"], errors="coerce"),
        bins,
        duplicates="drop",
    )
    grouped = candidates.groupby("confidence_decile", observed=True)
    rows: list[dict[str, object]] = []
    for decile, group in grouped:
        ticks = _numeric(group, "candidate_fixed_exit_ticks")
        rows.append(
            {
                "confidence_decile": str(decile),
                "row_count": int(len(group)),
                "mean_ticks": float(ticks.mean()),
                "median_ticks": float(ticks.median()),
                "realized_le_2_rate": float(ticks.le(2).mean()),
                "executed_count": int(group["position"].ne(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def join_executed_context(
    policy_frame: pd.DataFrame,
    excursion_frame: pd.DataFrame,
    target_context: pd.DataFrame,
) -> pd.DataFrame:
    executed = policy_frame.loc[policy_frame["position"].ne(0)].copy()
    _check_columns(
        executed,
        (
            "market",
            "year",
            "fold_id",
            "timestamp",
            "target_entry_ts",
            "target_exit_ts",
            "position",
            "direction_probability",
            "p_long",
            "p_short",
            "p_flat",
            "y_true",
            "executed_fixed_exit_ticks",
        ),
        "executed policy frame",
    )
    keys = ["market", "year", "fold_id", "timestamp", "target_entry_ts", "target_exit_ts", "position"]
    excursion_cols = [
        *keys,
        "realized_gross_ticks",
        "current_cost_net_ticks",
        "favorable_excursion_ticks",
        "adverse_excursion_ticks",
    ]
    _check_columns(excursion_frame, excursion_cols, "excursion frame")
    merged = executed.merge(
        excursion_frame[excursion_cols],
        on=keys,
        how="left",
        validate="one_to_one",
        suffixes=("", "_excursion"),
    )
    if merged["favorable_excursion_ticks"].isna().any():
        raise ValueError("executed policy rows missing excursion join")

    target_keys = ["market", "year", "timestamp"]
    merged = merged.merge(
        target_context[[*target_keys, *[column for column in TARGET_CONTEXT_COLUMNS if column != "ts" and column not in target_keys]]],
        on=target_keys,
        how="left",
        validate="many_to_one",
    )
    if merged[TARGET_DIRECTION].isna().any():
        raise ValueError("executed policy rows missing target context join")

    merged["target_direction_match"] = merged["position"].astype(int).eq(
        pd.to_numeric(merged[TARGET_DIRECTION], errors="coerce").astype(int)
    )
    merged["giveback_ticks"] = merged["favorable_excursion_ticks"] - merged["realized_gross_ticks"]
    merged["mfe_ge_5_realized_le_2"] = merged["favorable_excursion_ticks"].ge(5) & merged[
        "realized_gross_ticks"
    ].le(2)
    merged["mfe_ge_8_realized_le_2"] = merged["favorable_excursion_ticks"].ge(8) & merged[
        "realized_gross_ticks"
    ].le(2)
    return merged


def target_match_summary(executed_context: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for match, group in executed_context.groupby("target_direction_match", dropna=False):
        ticks = _numeric(group, "realized_gross_ticks")
        rows.append(
            {
                "target_direction_match": bool(match),
                "row_count": int(len(group)),
                "mean_realized_ticks": float(ticks.mean()),
                "median_realized_ticks": float(ticks.median()),
                "realized_le_2_rate": float(ticks.le(2).mean()),
                "median_mfe_ticks": float(_numeric(group, "favorable_excursion_ticks").median()),
                "median_giveback_ticks": float(_numeric(group, "giveback_ticks").median()),
            }
        )
    return pd.DataFrame(rows).sort_values("target_direction_match", ascending=False).reset_index(drop=True)


def acceptance_distance_summary(executed_context: pd.DataFrame) -> pd.DataFrame:
    frame = executed_context.copy()
    frame["abs_acceptance_distance_ticks"] = _numeric(frame, TARGET_ACCEPTANCE_DISTANCE).abs()
    frame["acceptance_bucket"] = pd.cut(
        frame["abs_acceptance_distance_ticks"],
        bins=[0, 1, 2, 4, 8, np.inf],
        labels=["0-1", "1-2", "2-4", "4-8", "8+"],
        include_lowest=True,
    )
    rows: list[dict[str, object]] = []
    for bucket, group in frame.groupby("acceptance_bucket", observed=True):
        ticks = _numeric(group, "realized_gross_ticks")
        rows.append(
            {
                "acceptance_bucket": str(bucket),
                "row_count": int(len(group)),
                "mean_realized_ticks": float(ticks.mean()),
                "median_realized_ticks": float(ticks.median()),
                "realized_le_2_rate": float(ticks.le(2).mean()),
            }
        )
    return pd.DataFrame(rows)


def _stage_rows(stage_summary: pd.DataFrame) -> list[list[object]]:
    rows: list[list[object]] = []
    for row in stage_summary.itertuples(index=False):
        rows.append(
            [
                row.stage,
                int(row.row_count),
                _fmt(row.mean_ticks),
                _fmt(row.median_ticks),
                _count_pct(int(row.realized_le_2_count), int(row.row_count)),
            ]
        )
    return rows


def _confidence_rows(confidence_summary: pd.DataFrame) -> list[list[object]]:
    rows: list[list[object]] = []
    for row in confidence_summary.itertuples(index=False):
        rows.append(
            [
                row.confidence_decile,
                int(row.row_count),
                int(row.executed_count),
                _fmt(row.mean_ticks),
                _fmt(row.median_ticks),
                f"{100.0 * row.realized_le_2_rate:.1f}%",
            ]
        )
    return rows


def _target_match_rows(summary: pd.DataFrame) -> list[list[object]]:
    rows: list[list[object]] = []
    for row in summary.itertuples(index=False):
        rows.append(
            [
                "match" if row.target_direction_match else "mismatch",
                int(row.row_count),
                _fmt(row.mean_realized_ticks),
                _fmt(row.median_realized_ticks),
                f"{100.0 * row.realized_le_2_rate:.1f}%",
                _fmt(row.median_mfe_ticks),
                _fmt(row.median_giveback_ticks),
            ]
        )
    return rows


def _acceptance_rows(summary: pd.DataFrame) -> list[list[object]]:
    rows: list[list[object]] = []
    for row in summary.itertuples(index=False):
        rows.append(
            [
                row.acceptance_bucket,
                int(row.row_count),
                _fmt(row.mean_realized_ticks),
                _fmt(row.median_realized_ticks),
                f"{100.0 * row.realized_le_2_rate:.1f}%",
            ]
        )
    return rows


def build_report(
    *,
    policy_frame: pd.DataFrame,
    executed_context: pd.DataFrame,
    stage_summary: pd.DataFrame,
    confidence_summary: pd.DataFrame,
    match_summary: pd.DataFrame,
    acceptance_summary: pd.DataFrame,
    costs: CostConfig,
    predictions_path: Path,
    trades_path: Path,
    bars_path: Path,
    costs_path: Path,
) -> str:
    total_rows = len(policy_frame)
    candidates = policy_frame.loc[policy_frame["candidate_position"].ne(0)]
    executed = executed_context
    blocked = policy_frame.loc[policy_frame["blocked_by_execution_overlap"].fillna(False)]
    candidate_rate = _pct(len(candidates), total_rows)
    executed_count = len(executed)
    mfe_ge_5_low_exit = int(executed["mfe_ge_5_realized_le_2"].sum())
    mfe_ge_8_low_exit = int(executed["mfe_ge_8_realized_le_2"].sum())
    median_mfe = float(executed["favorable_excursion_ticks"].median())
    median_realized = float(executed["realized_gross_ticks"].median())
    median_giveback = float(executed["giveback_ticks"].median())
    mean_realized = float(executed["realized_gross_ticks"].mean())
    target_match = match_summary.loc[match_summary["target_direction_match"].eq(True)].iloc[0]
    target_mismatch = match_summary.loc[match_summary["target_direction_match"].eq(False)].iloc[0]

    rule_rows = [
        [
            "Target",
            "Close outside completed opening range; future path MFE must clear cost + min profit.",
            f"Median executed-trade MFE was {_fmt(median_mfe)} ticks.",
            "Labels opportunity sometime in path, not fixed-exit PnL.",
        ],
        [
            "Materialization",
            "Maps frozen path direction into target_sign_with_deadzone.",
            f"Target-direction matches averaged {_fmt(target_match.mean_realized_ticks)} fixed-exit ticks; mismatches averaged {_fmt(target_mismatch.mean_realized_ticks)}.",
            "Correct class helped, but still did not guarantee enough fixed-exit edge.",
        ],
        [
            "Model",
            "Logistic classifier predicts p_long/p_short/p_flat.",
            "Confidence deciles did not create a monotonic fixed-exit edge.",
            "It predicts class direction, not expected ticks or trade expectancy.",
        ],
        [
            "Policy",
            "Trades any unique max long/short probability.",
            f"{len(candidates)} of {total_rows} rows were candidate trades ({candidate_rate:.1f}%).",
            "No confidence, margin, or minimum expected-tick threshold filtered weak edges.",
        ],
        [
            "Execution",
            "One contract, non-overlap, next-bar entry, fixed 30-minute exit open.",
            f"Executed mean was {_fmt(mean_realized)} ticks and median was {_fmt(median_realized)}.",
            "Fixed exit gave back path opportunity; no TP/SL captured the move.",
        ],
        [
            "Cost",
            "Current ES round turn is configured as all-in cost.",
            f"${costs.round_turn_cost_dollars:.2f} = {costs.round_turn_cost_ticks:.2f} ticks.",
            "Average gross trade did not cover even one round turn.",
        ],
    ]

    lines: list[str] = [
        f"# {HYPOTHESIS_ID} Low Tick Rule Attribution",
        "",
        "## Summary",
        "",
        f"- Prediction rows reviewed: `{total_rows}`.",
        f"- Candidate trades before non-overlap: `{len(candidates)}` (`{candidate_rate:.1f}%` of prediction rows).",
        f"- Executed trades after non-overlap: `{executed_count}`; overlap-blocked candidates: `{len(blocked)}`.",
        f"- Executed fixed-exit realized ticks: mean `{_fmt(mean_realized)}`, median `{_fmt(median_realized)}`.",
        f"- Executed path MFE: median `{_fmt(median_mfe)}` ticks; median giveback to fixed exit `{_fmt(median_giveback)}` ticks.",
        f"- Trades with MFE `>=5` ticks but fixed-exit realized ticks `<=2`: `{_count_pct(mfe_ge_5_low_exit, executed_count)}`.",
        f"- Trades with MFE `>=8` ticks but fixed-exit realized ticks `<=2`: `{_count_pct(mfe_ge_8_low_exit, executed_count)}`.",
        "",
        "Root cause: the target rewarded path opportunity, while the evaluated policy exited at a fixed 30-minute open. The model often identified the target direction, but the policy had no rule to capture favorable excursion before giveback.",
        "",
        "## Inputs",
        "",
        f"- Predictions: `{_relative(predictions_path)}`.",
        f"- Executed trades: `{_relative(trades_path)}`.",
        f"- ES 2024 materialized bars: `{_relative(bars_path)}`.",
        f"- Costs config: `{_relative(costs_path)}`.",
        "",
        "## Rule Stack",
        "",
    ]
    lines.extend(_markdown_table(["Layer", "Rule", "Measured Effect", "Attribution"], rule_rows))
    lines.extend(["", "## Candidate, Executed, And Blocked Stages", ""])
    lines.extend(_markdown_table(["Stage", "Rows", "Mean fixed-exit ticks", "Median fixed-exit ticks", "Realized <= 2 ticks"], _stage_rows(stage_summary)))
    lines.extend(["", "## Path Label Direction Vs Fixed-Exit PnL", ""])
    lines.extend(
        _markdown_table(
            ["Target direction", "Trades", "Mean realized ticks", "Median realized ticks", "Realized <= 2", "Median MFE", "Median giveback"],
            _target_match_rows(match_summary),
        )
    )
    lines.extend(["", "## Model Confidence Deciles", ""])
    lines.extend(
        _markdown_table(
            ["Direction probability decile", "Candidate rows", "Executed rows", "Mean fixed-exit ticks", "Median fixed-exit ticks", "Realized <= 2"],
            _confidence_rows(confidence_summary),
        )
    )
    lines.extend(["", "## Opening-Range Acceptance Distance", ""])
    lines.extend(
        _markdown_table(
            ["Abs acceptance distance", "Executed trades", "Mean realized ticks", "Median realized ticks", "Realized <= 2"],
            _acceptance_rows(acceptance_summary),
        )
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Non-overlap did not create the low-tick problem. Candidate, executed, and blocked candidates all had median fixed-exit ticks around zero.",
            "- The class signal was not useless: target-direction matches were much better than mismatches. The problem is that correct direction at some point in the path did not reliably translate to fixed-exit dollars.",
            "- Large both-side movement means simple TP/SL rescue cannot be inferred from OHLC alone. Any future stop/target policy needs ordered first-touch validation or lower-timeframe execution evidence.",
            "- This report does not approve tuning, stop/target backtests, WFA/modeling, registry/status mutation, promotion, paper trading, or live trading.",
            "",
        ]
    )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--trades", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--bars", type=Path, default=DEFAULT_BARS)
    parser.add_argument("--costs-config", type=Path, default=DEFAULT_COSTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--market", default=DEFAULT_MARKET)
    return parser


def run(args: argparse.Namespace) -> Path:
    predictions_path = _resolve(args.predictions)
    trades_path = _resolve(args.trades)
    bars_path = _resolve(args.bars)
    costs_path = _resolve(args.costs_config)
    output_path = _resolve(args.output)
    for path in (predictions_path, trades_path, bars_path, costs_path):
        if not path.exists():
            raise ValueError(f"missing input path: {_relative(path)}")

    costs = load_cost_config(costs_path, args.market)
    if costs.market != DEFAULT_MARKET:
        raise ValueError(f"expected ES-only analysis, got {costs.market}")
    predictions = load_predictions(predictions_path)
    trades = load_trades(trades_path)
    bars = load_bars(bars_path)
    target_context = load_target_context(bars_path)
    policy_frame = build_policy_frame(predictions, costs_path, costs)
    excursion_frame = build_trade_excursion_frame(trades, bars, costs)
    executed_context = join_executed_context(policy_frame, excursion_frame, target_context)
    stage_summary = summarize_policy_stages(policy_frame)
    confidence_summary = confidence_decile_summary(policy_frame)
    match_summary = target_match_summary(executed_context)
    acceptance_summary = acceptance_distance_summary(executed_context)
    report = build_report(
        policy_frame=policy_frame,
        executed_context=executed_context,
        stage_summary=stage_summary,
        confidence_summary=confidence_summary,
        match_summary=match_summary,
        acceptance_summary=acceptance_summary,
        costs=costs,
        predictions_path=predictions_path,
        trades_path=trades_path,
        bars_path=bars_path,
        costs_path=costs_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        output = run(args)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"NO_GO low tick rule attribution: {exc}", file=sys.stderr)
        return 1
    print(f"WROTE low tick rule attribution: {_relative(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
