#!/usr/bin/env python3
"""First-touch TP/SL feasibility diagnostic for one path-opportunity target."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from scripts.phase8_model_selection.analyze_trade_tick_excursions import (
    DEFAULT_BARS,
    DEFAULT_COSTS,
    DEFAULT_MARKET,
    DEFAULT_TRADES,
    EXPECTED_TRADE_COUNT,
    BAR_REQUIRED_COLUMNS,
    CostConfig,
    _build_bar_groups,
    _check_columns,
    _exact_index,
    _relative,
    _resolve,
    _timestamp_ns,
    load_bars,
    load_cost_config,
    load_trades,
)
from scripts.phase8_model_selection.evaluate_predictions import (
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _relative_path,
    _write_json,
)
from scripts.phase8_model_selection.single_target_diagnostics import DEFAULT_TARGET_NAME
from scripts.validation.target_policy_contract import (
    evaluate_target_policy_compatibility,
    first_touch_path_capture_policy_contract,
    opening_range_acceptance_contract,
    simulate_first_touch_outcome,
)


HYPOTHESIS_ID = "opening_range_acceptance_continuation_30m_v1"
RUN_ID = "opening_range_acceptance_continuation_30m_v1_model_expansion_s1"
DIAGNOSTIC_TYPE = "single_target_first_touch_feasibility"
DEFAULT_PREDICTIONS = Path(
    "data/predictions/opening_range_acceptance_continuation_30m_v1_model_expansion/"
    "opening_range_acceptance_continuation_30m_v1_model_expansion_s1/oos_predictions.parquet"
)
DEFAULT_REPORTS_ROOT = Path(
    "reports/phase8_first_touch_feasibility/"
    "opening_range_acceptance_continuation_30m_v1_model_expansion_s1"
)
DEFAULT_GRID = (2, 3, 4, 5, 8, 10)
EXPECTED_YEAR = 2024
EXPECTED_MARKET = "ES"
PREDICTION_REQUIRED_COLUMNS = (
    "market",
    "year",
    "fold_id",
    "timestamp",
    "model_id",
    "target_name",
)


@dataclass(frozen=True)
class TradePath:
    market: str
    year: int
    fold_id: str
    timestamp: pd.Timestamp
    month: str
    position: int
    entry_price: float
    exit_price: float
    cost_dollars: float
    highs: tuple[float, ...]
    lows: tuple[float, ...]


def output_paths(reports_root: Path, run: str) -> dict[str, Path]:
    return {
        "diagnostics": reports_root / f"{run}_first_touch_feasibility_diagnostics.json",
        "grid": reports_root / f"{run}_first_touch_feasibility_grid.csv",
    }


def _parse_grid(raw: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    if not values:
        raise argparse.ArgumentTypeError("grid must contain at least one integer tick value")
    if any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("grid tick values must be positive")
    return tuple(dict.fromkeys(values))


def _validate_outputs_absent(paths: Iterable[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        rendered = ", ".join(_relative(path) for path in existing)
        raise ValueError(f"stale output path exists: {rendered}")


def load_prediction_scope(path: Path) -> pd.DataFrame:
    predictions = pd.read_parquet(path, columns=list(PREDICTION_REQUIRED_COLUMNS))
    _check_columns(predictions, PREDICTION_REQUIRED_COLUMNS, "predictions")
    out = predictions.copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    duplicate_keys = out.duplicated(
        ["market", "year", "fold_id", "timestamp", "model_id", "target_name"],
        keep=False,
    )
    if duplicate_keys.any():
        raise ValueError(f"predictions contain duplicate keys: {int(duplicate_keys.sum())}")
    return out


def validate_scope(predictions: pd.DataFrame, trades: pd.DataFrame, bars: pd.DataFrame) -> None:
    pred_markets = sorted(predictions["market"].dropna().astype(str).unique().tolist())
    pred_years = sorted(int(value) for value in predictions["year"].dropna().unique().tolist())
    trade_markets = sorted(trades["market"].dropna().astype(str).unique().tolist())
    trade_years = sorted(int(value) for value in trades["year"].dropna().unique().tolist())
    bar_markets = sorted(bars["market"].dropna().astype(str).unique().tolist())
    bar_years = sorted(int(value) for value in bars["year"].dropna().unique().tolist())
    target_names = sorted(predictions["target_name"].dropna().astype(str).unique().tolist())
    if pred_markets != [EXPECTED_MARKET] or trade_markets != [EXPECTED_MARKET] or bar_markets != [EXPECTED_MARKET]:
        raise ValueError(
            "first-touch feasibility scope must be ES-only: "
            f"predictions={pred_markets} trades={trade_markets} bars={bar_markets}"
        )
    if pred_years != [EXPECTED_YEAR] or trade_years != [EXPECTED_YEAR] or bar_years != [EXPECTED_YEAR]:
        raise ValueError(
            "first-touch feasibility scope must be 2024-only: "
            f"predictions={pred_years} trades={trade_years} bars={bar_years}"
        )
    if target_names != [DEFAULT_TARGET_NAME]:
        raise ValueError(f"expected target {DEFAULT_TARGET_NAME!r}, found {target_names}")
    if len(trades) != EXPECTED_TRADE_COUNT:
        raise ValueError(f"expected {EXPECTED_TRADE_COUNT} executed trades, found {len(trades)}")


def build_trade_paths(trades: pd.DataFrame, bars: pd.DataFrame, costs: CostConfig) -> list[TradePath]:
    _check_columns(trades, ("market", "year", "fold_id", "timestamp", "target_entry_ts", "target_exit_ts", "position", "execution_open", "execution_close", "cost_dollars"), "trades")
    _check_columns(bars, BAR_REQUIRED_COLUMNS, "bars")
    duplicate_trades = trades.duplicated(
        ["market", "year", "timestamp", "target_entry_ts", "target_exit_ts"],
        keep=False,
    )
    if duplicate_trades.any():
        raise ValueError(f"trades contain duplicate join keys: {int(duplicate_trades.sum())}")
    duplicate_bars = bars.duplicated(["market", "year", "ts"], keep=False)
    if duplicate_bars.any():
        raise ValueError(f"bars contain duplicate join keys: {int(duplicate_bars.sum())}")
    bar_groups = _build_bar_groups(bars)
    if not bar_groups:
        raise ValueError("no usable bar groups available")

    paths: list[TradePath] = []
    for row in trades.itertuples(index=False):
        market = str(row.market)
        year = int(row.year)
        if market != costs.market:
            raise ValueError(f"trade market {market!r} does not match cost market {costs.market!r}")
        if int(row.position) not in (-1, 1):
            raise ValueError(f"unexpected flat executed trade at {row.timestamp}")
        if abs(float(row.cost_dollars) - costs.round_turn_cost_dollars) > 1e-9:
            raise ValueError(
                f"trade cost mismatch for {row.timestamp}: "
                f"trade={row.cost_dollars} config={costs.round_turn_cost_dollars}"
            )
        group = bar_groups.get((market, year))
        if group is None:
            raise ValueError(f"missing bar group for {market} {year}")

        signal_ns = int(pd.Timestamp(row.timestamp).value)
        entry_ts = pd.Timestamp(row.target_entry_ts)
        exit_ts = pd.Timestamp(row.target_exit_ts)
        entry_ns = int(entry_ts.value)
        exit_ns = int(exit_ts.value)
        _exact_index(group.timestamps_ns, signal_ns, "signal")
        entry_pos = _exact_index(group.timestamps_ns, entry_ns, "entry")
        exit_pos = _exact_index(group.timestamps_ns, exit_ns, "exit")
        if exit_pos <= entry_pos:
            raise ValueError(f"non-positive path window for {market} {year} {row.timestamp}")

        expected_bars = int((exit_ts - entry_ts) / pd.Timedelta(minutes=1))
        actual_bars = int(exit_pos - entry_pos)
        if expected_bars <= 0 or actual_bars != expected_bars:
            raise ValueError(
                f"missing OHLC path rows for {market} {year} {row.timestamp}: "
                f"expected={expected_bars} actual={actual_bars}"
            )

        entry_open = float(group.opens[entry_pos])
        exit_open = float(group.opens[exit_pos])
        if abs(entry_open - float(row.execution_open)) > 1e-9:
            raise ValueError(
                f"entry price mismatch for {market} {year} {row.timestamp}: "
                f"trade={row.execution_open} bar={entry_open}"
            )
        if abs(exit_open - float(row.execution_close)) > 1e-9:
            raise ValueError(
                f"exit price mismatch for {market} {year} {row.timestamp}: "
                f"trade={row.execution_close} bar={exit_open}"
            )

        highs = tuple(float(value) for value in group.highs[entry_pos:exit_pos])
        lows = tuple(float(value) for value in group.lows[entry_pos:exit_pos])
        if len(highs) != expected_bars or len(lows) != expected_bars:
            raise ValueError(f"path extraction length mismatch for {market} {year} {row.timestamp}")

        timestamp = pd.Timestamp(row.timestamp)
        paths.append(
            TradePath(
                market=market,
                year=year,
                fold_id=str(row.fold_id),
                timestamp=timestamp,
                month=timestamp.strftime("%Y-%m"),
                position=int(row.position),
                entry_price=float(row.execution_open),
                exit_price=float(row.execution_close),
                cost_dollars=costs.round_turn_cost_dollars,
                highs=highs,
                lows=lows,
            )
        )
    return paths


def _trade_results_for_grid(
    paths: list[TradePath],
    costs: CostConfig,
    *,
    take_profit_ticks: int,
    stop_loss_ticks: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        ambiguous = simulate_first_touch_outcome(
            position=path.position,
            entry_price=path.entry_price,
            highs=path.highs,
            lows=path.lows,
            exit_price=path.exit_price,
            tick_size=costs.tick_size,
            take_profit_ticks=float(take_profit_ticks),
            stop_loss_ticks=float(stop_loss_ticks),
            same_bar_policy="ambiguous",
        )
        stop_first = simulate_first_touch_outcome(
            position=path.position,
            entry_price=path.entry_price,
            highs=path.highs,
            lows=path.lows,
            exit_price=path.exit_price,
            tick_size=costs.tick_size,
            take_profit_ticks=float(take_profit_ticks),
            stop_loss_ticks=float(stop_loss_ticks),
            same_bar_policy="stop_first",
        )
        stop_first_gross_ticks = float(stop_first["gross_ticks"])
        stop_first_net_dollars = stop_first_gross_ticks * costs.tick_value - path.cost_dollars
        ambiguous_gross_ticks = ambiguous["gross_ticks"]
        ambiguous_net_dollars = (
            None
            if ambiguous_gross_ticks is None
            else float(ambiguous_gross_ticks) * costs.tick_value - path.cost_dollars
        )
        rows.append(
            {
                "fold_id": path.fold_id,
                "position": path.position,
                "month": path.month,
                "ambiguous_outcome": ambiguous["outcome"],
                "stop_first_outcome": stop_first["outcome"],
                "ambiguous_first_touch": bool(ambiguous["ambiguous_first_touch"]),
                "stop_first_gross_ticks": stop_first_gross_ticks,
                "stop_first_net_dollars": stop_first_net_dollars,
                "ambiguous_gross_ticks": ambiguous_gross_ticks,
                "ambiguous_net_dollars": ambiguous_net_dollars,
            }
        )
    return pd.DataFrame(rows)


def _count(frame: pd.DataFrame, column: str, value: object) -> int:
    return int(frame[column].eq(value).sum())


def _safe_sum(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").dropna().sum())


def summarize_trade_results(
    frame: pd.DataFrame,
    costs: CostConfig,
    *,
    take_profit_ticks: int,
    stop_loss_ticks: int,
    scope_type: str,
    scope_value: str,
) -> dict[str, Any]:
    total = int(len(frame))
    ambiguous_mask = frame["ambiguous_first_touch"].fillna(False)
    non_ambiguous = frame.loc[~ambiguous_mask].copy()
    stop_first_gross_ticks = _safe_sum(frame["stop_first_gross_ticks"])
    stop_first_gross_dollars = stop_first_gross_ticks * costs.tick_value
    cost_dollars = float(total * costs.round_turn_cost_dollars)
    stop_first_net_dollars = _safe_sum(frame["stop_first_net_dollars"])
    ambiguous_excluded_trade_count = int(len(non_ambiguous))
    ambiguous_excluded_cost_dollars = float(ambiguous_excluded_trade_count * costs.round_turn_cost_dollars)
    ambiguous_excluded_net_dollars = _safe_sum(non_ambiguous["ambiguous_net_dollars"])
    return {
        "take_profit_ticks": int(take_profit_ticks),
        "stop_loss_ticks": int(stop_loss_ticks),
        "scope_type": scope_type,
        "scope_value": scope_value,
        "trade_count": total,
        "take_profit_count": _count(frame, "ambiguous_outcome", "take_profit"),
        "stop_loss_count": _count(frame, "ambiguous_outcome", "stop_loss"),
        "horizon_exit_count": _count(frame, "ambiguous_outcome", "horizon_exit"),
        "same_bar_ambiguous_count": int(ambiguous_mask.sum()),
        "same_bar_ambiguous_rate": float(ambiguous_mask.mean()) if total else 0.0,
        "stop_first_take_profit_count": _count(frame, "stop_first_outcome", "take_profit"),
        "stop_first_stop_loss_count": _count(frame, "stop_first_outcome", "stop_loss"),
        "stop_first_horizon_exit_count": _count(frame, "stop_first_outcome", "horizon_exit"),
        "stop_first_gross_ticks": stop_first_gross_ticks,
        "stop_first_gross_dollars": stop_first_gross_dollars,
        "stop_first_cost_dollars": cost_dollars,
        "stop_first_net_dollars": stop_first_net_dollars,
        "stop_first_avg_net_dollars": stop_first_net_dollars / total if total else 0.0,
        "stop_first_net_positive_count": int(frame["stop_first_net_dollars"].gt(0).sum()),
        "stop_first_net_positive_rate": float(frame["stop_first_net_dollars"].gt(0).mean()) if total else 0.0,
        "ambiguous_excluded_trade_count": ambiguous_excluded_trade_count,
        "ambiguous_excluded_cost_dollars": ambiguous_excluded_cost_dollars,
        "ambiguous_excluded_net_dollars": ambiguous_excluded_net_dollars,
        "ambiguous_excluded_avg_net_dollars": (
            ambiguous_excluded_net_dollars / ambiguous_excluded_trade_count
            if ambiguous_excluded_trade_count
            else 0.0
        ),
        "ambiguous_excluded_net_positive_count": int(non_ambiguous["ambiguous_net_dollars"].gt(0).sum()),
        "ambiguous_excluded_net_positive_rate": (
            float(non_ambiguous["ambiguous_net_dollars"].gt(0).mean())
            if ambiguous_excluded_trade_count
            else 0.0
        ),
    }


def _scope_frames(frame: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    scopes: list[tuple[str, str, pd.DataFrame]] = [("overall", "all", frame)]
    for fold_id, group in frame.groupby("fold_id", dropna=False):
        scopes.append(("fold", str(fold_id), group))
    position_labels = {1: "long", -1: "short"}
    for position, group in frame.groupby("position", dropna=False):
        scopes.append(("position", position_labels.get(int(position), str(position)), group))
    for month, group in frame.groupby("month", dropna=False):
        scopes.append(("month", str(month), group))
    return scopes


def build_grid_summary(paths: list[TradePath], costs: CostConfig, grid: Iterable[int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grid_values = tuple(grid)
    for take_profit_ticks in grid_values:
        for stop_loss_ticks in grid_values:
            trade_results = _trade_results_for_grid(
                paths,
                costs,
                take_profit_ticks=take_profit_ticks,
                stop_loss_ticks=stop_loss_ticks,
            )
            for scope_type, scope_value, scope_frame in _scope_frames(trade_results):
                rows.append(
                    summarize_trade_results(
                        scope_frame,
                        costs,
                        take_profit_ticks=take_profit_ticks,
                        stop_loss_ticks=stop_loss_ticks,
                        scope_type=scope_type,
                        scope_value=scope_value,
                    )
                )
    return pd.DataFrame(rows)


def _neighbor_pair_count(positive_cells: set[tuple[int, int]], grid: tuple[int, ...]) -> int:
    index = {value: offset for offset, value in enumerate(grid)}
    cells = sorted(positive_cells)
    count = 0
    for offset, left in enumerate(cells):
        for right in cells[offset + 1 :]:
            if max(abs(index[left[0]] - index[right[0]]), abs(index[left[1]] - index[right[1]])) <= 1:
                count += 1
    return count


def decision_support(grid_summary: pd.DataFrame, grid: tuple[int, ...]) -> dict[str, Any]:
    overall = grid_summary.loc[grid_summary["scope_type"].eq("overall")].copy()
    folds = grid_summary.loc[grid_summary["scope_type"].eq("fold")].copy()
    positive = overall.loc[overall["stop_first_net_dollars"].gt(0)]
    ambiguous_excluded_positive = overall.loc[overall["ambiguous_excluded_net_dollars"].gt(0)]
    positive_cells = {
        (int(row.take_profit_ticks), int(row.stop_loss_ticks))
        for row in positive.itertuples(index=False)
    }
    fold_positive_counts: dict[tuple[int, int], int] = {}
    for (tp_ticks, sl_ticks), group in folds.groupby(["take_profit_ticks", "stop_loss_ticks"]):
        fold_positive_counts[(int(tp_ticks), int(sl_ticks))] = int(group["stop_first_net_dollars"].gt(0).sum())
    at_least_three_fold_positive = {
        cell for cell, count in fold_positive_counts.items() if count >= 3
    }
    neighbor_pairs = _neighbor_pair_count(positive_cells, grid)
    if not positive_cells and len(ambiguous_excluded_positive) > 0:
        screen_status = "LOWER_TIMEFRAME_REQUIRED_AMBIGUITY_ONLY"
    elif len(positive_cells) <= 1:
        screen_status = "FIRST_TOUCH_FEASIBILITY_NO_GO"
    elif len(positive_cells & at_least_three_fold_positive) >= 2 and neighbor_pairs >= 1:
        screen_status = "FIRST_TOUCH_FEASIBILITY_REVIEW_READY"
    else:
        screen_status = "FIRST_TOUCH_FEASIBILITY_WEAK_REVIEW"
    return {
        "screen_status": screen_status,
        "stop_first_positive_overall_grid_count": int(len(positive_cells)),
        "ambiguous_excluded_positive_overall_grid_count": int(len(ambiguous_excluded_positive)),
        "stop_first_at_least_3_positive_fold_grid_count": int(len(at_least_three_fold_positive)),
        "stop_first_positive_neighbor_pair_count": int(neighbor_pairs),
        "all_or_nearly_all_stop_first_grids_negative": bool(len(positive_cells) <= 1),
        "grid_count": int(len(overall)),
        "fold_count": int(folds["scope_value"].nunique()),
        "decision_note": (
            "Diagnostic only: this can justify review of a separate v2 packet, "
            "but cannot tune/select a TP/SL pair or promote the candidate."
        ),
    }


def evaluate_first_touch_feasibility(
    *,
    predictions_path: Path,
    trades_path: Path,
    bars_path: Path,
    costs_config: Path,
    reports_root: Path,
    run: str,
    grid: tuple[int, ...] = DEFAULT_GRID,
    market: str = DEFAULT_MARKET,
) -> dict[str, Any]:
    output = output_paths(reports_root, run)
    _validate_outputs_absent(output.values())
    for path in (predictions_path, trades_path, bars_path, costs_config):
        if not path.exists():
            raise ValueError(f"missing input path: {_relative(path)}")

    costs = load_cost_config(costs_config, market)
    if costs.market != EXPECTED_MARKET:
        raise ValueError(f"expected ES-only costs, got {costs.market}")
    predictions = load_prediction_scope(predictions_path)
    trades = load_trades(trades_path)
    bars = load_bars(bars_path)
    validate_scope(predictions, trades, bars)
    paths = build_trade_paths(trades, bars, costs)
    if len(paths) != EXPECTED_TRADE_COUNT:
        raise ValueError(f"expected {EXPECTED_TRADE_COUNT} trade paths, found {len(paths)}")
    grid_summary = build_grid_summary(paths, costs, grid)
    compatibility = evaluate_target_policy_compatibility(
        opening_range_acceptance_contract(),
        first_touch_path_capture_policy_contract(),
    )
    support = decision_support(grid_summary, grid)

    reports_root.mkdir(parents=True, exist_ok=True)
    grid_summary.to_csv(output["grid"], index=False)
    overall = grid_summary.loc[grid_summary["scope_type"].eq("overall")].copy()
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "run": run,
        "hypothesis_id": HYPOTHESIS_ID,
        "target_name": DEFAULT_TARGET_NAME,
        "diagnostic_type": DIAGNOSTIC_TYPE,
        "diagnostic_only": True,
        "tuning_or_selection_allowed": False,
        "promotion_allowed": False,
        "registry_status_mutation_allowed": False,
        "live_execution_ready": False,
        "failure_count": 0,
        "failures": [],
        "warnings": [
            "OHLC bars cannot prove first-touch order when TP and SL are touched in the same bar",
            "This diagnostic does not select a TP/SL pair and does not approve tuning, promotion, paper, or live trading",
        ],
        "market": EXPECTED_MARKET,
        "year": EXPECTED_YEAR,
        "trade_count": int(len(paths)),
        "prediction_count": int(len(predictions)),
        "fold_ids": sorted({path.fold_id for path in paths}),
        "grid_ticks": list(grid),
        "cost_model": {
            "tick_size": costs.tick_size,
            "tick_value": costs.tick_value,
            "round_turn_cost_dollars": costs.round_turn_cost_dollars,
            "round_turn_cost_ticks": costs.round_turn_cost_ticks,
        },
        "path_convention": (
            "evaluate highs/lows from entry timestamp up to but not after the "
            "fixed-horizon exit-open bar; if neither TP nor SL is reached, exit at "
            "the fixed-horizon exit open"
        ),
        "target_policy_contract": opening_range_acceptance_contract(),
        "policy_evaluation_contract": first_touch_path_capture_policy_contract(),
        "target_policy_compatibility": compatibility,
        "decisive_economic_evidence_allowed": bool(
            compatibility["decisive_economic_evidence_allowed"]
        ),
        "economic_approval_allowed": False,
        "economic_rejection_allowed": False,
        "decision_support": support,
        "overall_grid_summary": overall.to_dict(orient="records"),
        "input_file_hashes": _file_hash_map([predictions_path, trades_path, bars_path, costs_config]),
        "prediction_path": _relative_path(predictions_path),
        "trades_path": _relative_path(trades_path),
        "bars_path": _relative_path(bars_path),
        "costs_config": _relative_path(costs_config),
        "diagnostics_path": _relative_path(output["diagnostics"]),
        "grid_path": _relative_path(output["grid"]),
    }
    _write_json(output["diagnostics"], payload)
    payload["diagnostics_output_path"] = output["diagnostics"]
    payload["grid_output_path"] = output["grid"]
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--trades", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--bars", type=Path, default=DEFAULT_BARS)
    parser.add_argument("--costs-config", type=Path, default=DEFAULT_COSTS)
    parser.add_argument("--reports-root", type=Path, default=DEFAULT_REPORTS_ROOT)
    parser.add_argument("--run", default=RUN_ID)
    parser.add_argument("--grid", type=_parse_grid, default=DEFAULT_GRID)
    parser.add_argument("--market", default=DEFAULT_MARKET)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        result = evaluate_first_touch_feasibility(
            predictions_path=_resolve(args.predictions),
            trades_path=_resolve(args.trades),
            bars_path=_resolve(args.bars),
            costs_config=_resolve(args.costs_config),
            reports_root=_resolve(args.reports_root),
            run=args.run,
            grid=args.grid,
            market=args.market,
        )
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"NO_GO first-touch feasibility diagnostics: {exc}")
        return 1
    support = result["decision_support"]
    print(
        "PASS first-touch feasibility diagnostics:",
        f"trades={result['trade_count']}",
        f"grid_count={support['grid_count']}",
        f"screen_status={support['screen_status']}",
        f"stop_first_positive_grids={support['stop_first_positive_overall_grid_count']}",
        f"failures={result['failure_count']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
