#!/usr/bin/env python3
"""Analyze executed trade tick excursions for one single-target policy run."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml


HYPOTHESIS_ID = "opening_range_acceptance_continuation_30m_v1"
RUN_ID = "opening_range_acceptance_continuation_30m_v1_model_expansion_s1"
DEFAULT_TRADES = Path(
    "reports/phase8_single_target_policy/"
    "opening_range_acceptance_continuation_30m_v1_model_expansion_s1/"
    "opening_range_acceptance_continuation_30m_v1_model_expansion_s1_single_target_policy_trades.csv"
)
DEFAULT_BARS = Path(
    "data/feature_matrices/opening_range_acceptance_continuation_30m_v1_wfa_smoke/ES/2024.parquet"
)
DEFAULT_COSTS = Path("configs/costs.yaml")
DEFAULT_OUTPUT = Path(
    "docs/opening_range_acceptance_continuation_30m_v1_trade_tick_excursion_analysis.md"
)
DEFAULT_MARKET = "ES"
EXPECTED_TRADE_COUNT = 2668
THRESHOLDS = (1, 2, 3, 4, 5, 8, 10)

TRADE_REQUIRED_COLUMNS = (
    "market",
    "year",
    "fold_id",
    "timestamp",
    "target_entry_ts",
    "target_exit_ts",
    "position",
    "execution_open",
    "execution_close",
    "gross_dollars",
    "cost_dollars",
    "net_dollars",
)
BAR_REQUIRED_COLUMNS = ("ts", "market", "year", "open", "high", "low")


@dataclass(frozen=True)
class CostConfig:
    market: str
    tick_size: float
    tick_value: float
    round_turn_cost_dollars: float

    @property
    def round_turn_cost_ticks(self) -> float:
        return self.round_turn_cost_dollars / self.tick_value


@dataclass(frozen=True)
class BarGroup:
    timestamps_ns: np.ndarray
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else _repo_root() / candidate


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _timestamp_ns(values: pd.Series) -> pd.Series:
    parsed = pd.Series(pd.to_datetime(values, utc=True, errors="coerce"), index=values.index)
    naive_utc = parsed.dt.tz_convert("UTC").dt.tz_localize(None)
    return pd.Series(naive_utc.to_numpy(dtype="datetime64[ns]").astype("int64"), index=values.index)


def _check_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def load_cost_config(path: Path, market: str = DEFAULT_MARKET) -> CostConfig:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    market_costs = (payload.get("markets") or {}).get(market) or {}
    missing = [
        key
        for key in ("tick_size", "tick_value", "round_turn_cost_dollars")
        if market_costs.get(key) is None
    ]
    if missing:
        raise ValueError(f"{market}: costs config missing {missing}")
    return CostConfig(
        market=market,
        tick_size=float(market_costs["tick_size"]),
        tick_value=float(market_costs["tick_value"]),
        round_turn_cost_dollars=float(market_costs["round_turn_cost_dollars"]),
    )


def load_trades(path: Path) -> pd.DataFrame:
    trades = pd.read_csv(path)
    _check_columns(trades, TRADE_REQUIRED_COLUMNS, "trades")
    for column in ("timestamp", "target_entry_ts", "target_exit_ts"):
        trades[column] = pd.to_datetime(trades[column], utc=True, errors="coerce")
    for column in ("year", "position"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce").astype("Int64")
    for column in ("execution_open", "execution_close", "gross_dollars", "cost_dollars", "net_dollars"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    if len(trades) != EXPECTED_TRADE_COUNT:
        raise ValueError(f"expected {EXPECTED_TRADE_COUNT} executed trades, found {len(trades)}")
    duplicate_keys = trades.duplicated(
        ["market", "year", "timestamp", "target_entry_ts", "target_exit_ts"],
        keep=False,
    )
    if duplicate_keys.any():
        raise ValueError(f"trades contain duplicate join keys: {int(duplicate_keys.sum())}")
    return trades


def load_bars(path: Path) -> pd.DataFrame:
    bars = pd.read_parquet(path, columns=list(BAR_REQUIRED_COLUMNS))
    _check_columns(bars, BAR_REQUIRED_COLUMNS, "bars")
    bars = bars.copy()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True, errors="coerce")
    bars["year"] = pd.to_numeric(bars["year"], errors="coerce").astype("Int64")
    for column in ("open", "high", "low"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    duplicate_keys = bars.duplicated(["market", "year", "ts"], keep=False)
    if duplicate_keys.any():
        raise ValueError(f"bars contain duplicate join keys: {int(duplicate_keys.sum())}")
    return bars


def _build_bar_groups(bars: pd.DataFrame) -> dict[tuple[str, int], BarGroup]:
    groups: dict[tuple[str, int], BarGroup] = {}
    for (market, year), group in bars.groupby(["market", "year"], dropna=False):
        if pd.isna(market) or pd.isna(year):
            continue
        ordered = group.sort_values("ts", kind="mergesort").reset_index(drop=True)
        groups[(str(market), int(year))] = BarGroup(
            timestamps_ns=_timestamp_ns(ordered["ts"]).to_numpy(dtype=np.int64),
            opens=ordered["open"].to_numpy(dtype=float),
            highs=ordered["high"].to_numpy(dtype=float),
            lows=ordered["low"].to_numpy(dtype=float),
        )
    return groups


def _exact_index(timestamps_ns: np.ndarray, value_ns: int, label: str) -> int:
    pos = int(np.searchsorted(timestamps_ns, value_ns, side="left"))
    if pos >= len(timestamps_ns) or int(timestamps_ns[pos]) != int(value_ns):
        raise ValueError(f"missing {label} bar for timestamp_ns={value_ns}")
    return pos


def build_trade_excursion_frame(
    trades: pd.DataFrame,
    bars: pd.DataFrame,
    costs: CostConfig,
) -> pd.DataFrame:
    _check_columns(trades, TRADE_REQUIRED_COLUMNS, "trades")
    _check_columns(bars, BAR_REQUIRED_COLUMNS, "bars")
    bar_groups = _build_bar_groups(bars)
    if not bar_groups:
        raise ValueError("no usable bar groups available")

    out = trades.copy().reset_index(drop=True)
    out["realized_gross_ticks"] = (
        out["position"].astype(float)
        * (out["execution_close"] - out["execution_open"])
        / costs.tick_size
    )
    out["current_cost_ticks"] = out["cost_dollars"] / costs.tick_value
    out["current_cost_net_ticks"] = out["realized_gross_ticks"] - out["current_cost_ticks"]

    favorable_ticks: list[float] = []
    adverse_ticks: list[float] = []
    path_bar_counts: list[int] = []
    path_highs: list[float] = []
    path_lows: list[float] = []
    signal_matches = 0
    entry_matches = 0
    exit_matches = 0

    for row in out.itertuples(index=False):
        market = str(row.market)
        year = int(row.year)
        group = bar_groups.get((market, year))
        if group is None:
            raise ValueError(f"missing bar group for {market} {year}")

        signal_ns = int(pd.Timestamp(row.timestamp).value)
        entry_ns = int(pd.Timestamp(row.target_entry_ts).value)
        exit_ns = int(pd.Timestamp(row.target_exit_ts).value)
        _exact_index(group.timestamps_ns, signal_ns, "signal")
        signal_matches += 1
        entry_pos = _exact_index(group.timestamps_ns, entry_ns, "entry")
        exit_pos = _exact_index(group.timestamps_ns, exit_ns, "exit")
        entry_matches += 1
        exit_matches += 1
        if exit_pos <= entry_pos:
            raise ValueError(f"non-positive path window for {market} {year} {row.timestamp}")

        entry_open = float(group.opens[entry_pos])
        exit_open = float(group.opens[exit_pos])
        if not np.isclose(entry_open, float(row.execution_open), rtol=0.0, atol=1e-9):
            raise ValueError(
                f"entry price mismatch for {market} {year} {row.timestamp}: "
                f"trade={row.execution_open} bar={entry_open}"
            )
        if not np.isclose(exit_open, float(row.execution_close), rtol=0.0, atol=1e-9):
            raise ValueError(
                f"exit price mismatch for {market} {year} {row.timestamp}: "
                f"trade={row.execution_close} bar={exit_open}"
            )

        high_path = float(np.nanmax(group.highs[entry_pos:exit_pos]))
        low_path = float(np.nanmin(group.lows[entry_pos:exit_pos]))
        high_path = max(high_path, float(row.execution_close))
        low_path = min(low_path, float(row.execution_close))
        if int(row.position) == 1:
            favorable = (high_path - float(row.execution_open)) / costs.tick_size
            adverse = (float(row.execution_open) - low_path) / costs.tick_size
        elif int(row.position) == -1:
            favorable = (float(row.execution_open) - low_path) / costs.tick_size
            adverse = (high_path - float(row.execution_open)) / costs.tick_size
        else:
            raise ValueError(f"unexpected flat executed trade at {row.timestamp}")

        favorable_ticks.append(float(favorable))
        adverse_ticks.append(float(adverse))
        path_bar_counts.append(int(exit_pos - entry_pos))
        path_highs.append(high_path)
        path_lows.append(low_path)

    out["path_bar_count"] = path_bar_counts
    out["path_high"] = path_highs
    out["path_low"] = path_lows
    out["favorable_excursion_ticks"] = favorable_ticks
    out["adverse_excursion_ticks"] = adverse_ticks
    out.attrs["join_signal_match_count"] = signal_matches
    out.attrs["join_entry_match_count"] = entry_matches
    out.attrs["join_exit_match_count"] = exit_matches
    return out


def _count_pct(count: int, total: int) -> str:
    pct = 100.0 * count / total if total else 0.0
    return f"{count} ({pct:.1f}%)"


def _series_stats(series: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return {
        "count": float(clean.size),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "p25": float(clean.quantile(0.25)),
        "p75": float(clean.quantile(0.75)),
        "p90": float(clean.quantile(0.90)),
        "min": float(clean.min()),
        "max": float(clean.max()),
    }


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    rendered = ["| " + " | ".join(headers) + " |"]
    rendered.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        rendered.append("| " + " | ".join(str(value) for value in row) + " |")
    return rendered


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def threshold_reach_table(frame: pd.DataFrame, column: str, thresholds: Iterable[int]) -> list[list[object]]:
    total = len(frame)
    rows: list[list[object]] = []
    values = pd.to_numeric(frame[column], errors="coerce")
    for threshold in thresholds:
        count = int(values.ge(threshold).sum())
        rows.append([f">= {threshold}", _count_pct(count, total)])
    return rows


def build_tp_sl_grid(
    frame: pd.DataFrame,
    thresholds: Iterable[int] = THRESHOLDS,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    favorable = pd.to_numeric(frame["favorable_excursion_ticks"], errors="coerce")
    adverse = pd.to_numeric(frame["adverse_excursion_ticks"], errors="coerce")
    total = len(frame)
    for tp_ticks in thresholds:
        tp_hit = favorable.ge(tp_ticks)
        for sl_ticks in thresholds:
            sl_hit = adverse.ge(sl_ticks)
            both = int((tp_hit & sl_hit).sum())
            tp_only = int((tp_hit & ~sl_hit).sum())
            sl_only = int((~tp_hit & sl_hit).sum())
            neither = int((~tp_hit & ~sl_hit).sum())
            rows.append(
                {
                    "tp_ticks": int(tp_ticks),
                    "sl_ticks": int(sl_ticks),
                    "tp_only": tp_only,
                    "sl_only": sl_only,
                    "both_touched_ambiguous": both,
                    "neither": neither,
                    "tp_only_pct": 100.0 * tp_only / total if total else 0.0,
                    "sl_only_pct": 100.0 * sl_only / total if total else 0.0,
                    "both_touched_ambiguous_pct": 100.0 * both / total if total else 0.0,
                    "neither_pct": 100.0 * neither / total if total else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _bucket_rows(frame: pd.DataFrame, column: str) -> list[list[object]]:
    values = pd.to_numeric(frame[column], errors="coerce")
    total = len(values)
    buckets = [
        ("<= 0", values.le(0)),
        ("> 0 to <= 1", values.gt(0) & values.le(1)),
        ("> 1 to <= 2", values.gt(1) & values.le(2)),
        ("> 2 to <= 4", values.gt(2) & values.le(4)),
        ("> 4 to <= 8", values.gt(4) & values.le(8)),
        ("> 8 to <= 10", values.gt(8) & values.le(10)),
        ("> 10", values.gt(10)),
    ]
    return [[label, _count_pct(int(mask.sum()), total)] for label, mask in buckets]


def _summary_by(frame: pd.DataFrame, group_col: str) -> list[list[object]]:
    rows: list[list[object]] = []
    for group, item in frame.groupby(group_col, dropna=False):
        rows.append(
            [
                group,
                len(item),
                _fmt(item["realized_gross_ticks"].mean()),
                _fmt(item["current_cost_net_ticks"].mean()),
                _fmt(item["favorable_excursion_ticks"].median()),
                _fmt(item["adverse_excursion_ticks"].median()),
                _count_pct(int(item["favorable_excursion_ticks"].le(2).sum()), len(item)),
                _count_pct(int(item["adverse_excursion_ticks"].ge(3).sum()), len(item)),
            ]
        )
    return rows


def build_report(
    frame: pd.DataFrame,
    grid: pd.DataFrame,
    *,
    costs: CostConfig,
    trades_path: Path,
    bars_path: Path,
    costs_path: Path,
) -> str:
    total = len(frame)
    gross = _series_stats(frame["realized_gross_ticks"])
    net = _series_stats(frame["current_cost_net_ticks"])
    favorable = _series_stats(frame["favorable_excursion_ticks"])
    adverse = _series_stats(frame["adverse_excursion_ticks"])
    mfe_le_two = int(frame["favorable_excursion_ticks"].le(2).sum())
    mfe_le_cost = int(frame["favorable_excursion_ticks"].le(costs.round_turn_cost_ticks).sum())
    adverse_ge_cost = int(frame["adverse_excursion_ticks"].ge(costs.round_turn_cost_ticks).sum())
    realized_le_two = int(frame["realized_gross_ticks"].le(2).sum())
    total_gross_ticks = float(frame["realized_gross_ticks"].sum())
    total_net_ticks = float(frame["current_cost_net_ticks"].sum())
    total_gross_dollars = float(frame["gross_dollars"].sum())
    total_net_dollars = float(frame["net_dollars"].sum())

    stats_rows = [
        ["Realized gross ticks", _fmt(gross["mean"]), _fmt(gross["median"]), _fmt(gross["p25"]), _fmt(gross["p75"]), _fmt(gross["p90"]), _fmt(gross["min"]), _fmt(gross["max"])],
        ["Current-cost net ticks", _fmt(net["mean"]), _fmt(net["median"]), _fmt(net["p25"]), _fmt(net["p75"]), _fmt(net["p90"]), _fmt(net["min"]), _fmt(net["max"])],
        ["Max favorable excursion ticks", _fmt(favorable["mean"]), _fmt(favorable["median"]), _fmt(favorable["p25"]), _fmt(favorable["p75"]), _fmt(favorable["p90"]), _fmt(favorable["min"]), _fmt(favorable["max"])],
        ["Max adverse excursion ticks", _fmt(adverse["mean"]), _fmt(adverse["median"]), _fmt(adverse["p25"]), _fmt(adverse["p75"]), _fmt(adverse["p90"]), _fmt(adverse["min"]), _fmt(adverse["max"])],
    ]
    same_threshold_rows = []
    for threshold in THRESHOLDS:
        row = grid[(grid["tp_ticks"].eq(threshold)) & (grid["sl_ticks"].eq(threshold))].iloc[0]
        same_threshold_rows.append(
            [
                threshold,
                _count_pct(int(row["tp_only"]), total),
                _count_pct(int(row["sl_only"]), total),
                _count_pct(int(row["both_touched_ambiguous"]), total),
                _count_pct(int(row["neither"]), total),
            ]
        )
    full_grid_rows = [
        [
            int(row.tp_ticks),
            int(row.sl_ticks),
            int(row.tp_only),
            int(row.sl_only),
            int(row.both_touched_ambiguous),
            int(row.neither),
        ]
        for row in grid.itertuples(index=False)
    ]

    lines: list[str] = [
        f"# {HYPOTHESIS_ID} Trade Tick Excursion Analysis",
        "",
        "## Summary",
        "",
        f"- Executed trades analyzed: `{total}`.",
        f"- ES tick size/value: `{costs.tick_size}` points, `${costs.tick_value:.2f}` per tick.",
        f"- Current configured round-turn cost: `${costs.round_turn_cost_dollars:.2f}` = `{costs.round_turn_cost_ticks:.2f}` ticks.",
        f"- Total realized gross: `{total_gross_ticks:.2f}` ticks / `${total_gross_dollars:.2f}`.",
        f"- Total current-cost net: `{total_net_ticks:.2f}` ticks / `${total_net_dollars:.2f}`.",
        f"- Trades whose max favorable excursion was only `<= 2` ticks: `{_count_pct(mfe_le_two, total)}`.",
        f"- Trades whose max favorable excursion did not cover the current `{costs.round_turn_cost_ticks:.2f}`-tick cost: `{_count_pct(mfe_le_cost, total)}`.",
        f"- Trades whose max adverse excursion was at least the current `{costs.round_turn_cost_ticks:.2f}`-tick cost: `{_count_pct(adverse_ge_cost, total)}`.",
        "",
        "## Inputs And Validation",
        "",
        f"- Trades CSV: `{_relative(trades_path)}`.",
        f"- ES 2024 materialized bars: `{_relative(bars_path)}`.",
        f"- Costs config: `{_relative(costs_path)}`.",
        f"- Join checks: `{frame.attrs.get('join_signal_match_count')}` signal bars, `{frame.attrs.get('join_entry_match_count')}` entry bars, and `{frame.attrs.get('join_exit_match_count')}` exit bars matched.",
        "- Path convention: highs/lows from entry timestamp up to but not after the exit-open bar, plus the exit price.",
        "- Caveat: OHLC bars do not prove intrabar first-touch ordering. TP/SL rows where both thresholds touched are intentionally marked ambiguous.",
        "",
        "## Overall Tick Distribution",
        "",
    ]
    lines.extend(_markdown_table(["Metric", "Mean", "Median", "P25", "P75", "P90", "Min", "Max"], stats_rows))
    lines.extend(
        [
            "",
            "## Favorable Excursion Buckets",
            "",
        ]
    )
    lines.extend(_markdown_table(["Max favorable ticks", "Trades"], _bucket_rows(frame, "favorable_excursion_ticks")))
    lines.extend(
        [
            "",
            "## Take-Profit Reach Rates",
            "",
        ]
    )
    lines.extend(_markdown_table(["TP ticks reached", "Trades"], threshold_reach_table(frame, "favorable_excursion_ticks", THRESHOLDS)))
    lines.extend(
        [
            "",
            "## Stop-Loss Reach Rates",
            "",
        ]
    )
    lines.extend(_markdown_table(["SL ticks reached", "Trades"], threshold_reach_table(frame, "adverse_excursion_ticks", THRESHOLDS)))
    lines.extend(
        [
            "",
            "## Same-Size TP/SL Outcomes",
            "",
        ]
    )
    lines.extend(_markdown_table(["TP=SL ticks", "TP only", "SL only", "Both ambiguous", "Neither"], same_threshold_rows))
    lines.extend(
        [
            "",
            "## Long Vs Short",
            "",
        ]
    )
    lines.extend(_markdown_table(["Position", "Trades", "Avg gross ticks", "Avg net ticks", "Median MFE", "Median MAE", "MFE <= 2", "MAE >= 3"], _summary_by(frame, "position")))
    lines.extend(
        [
            "",
            "## Fold Summary",
            "",
        ]
    )
    lines.extend(_markdown_table(["Fold", "Trades", "Avg gross ticks", "Avg net ticks", "Median MFE", "Median MAE", "MFE <= 2", "MAE >= 3"], _summary_by(frame, "fold_id")))
    lines.extend(
        [
            "",
            "## Full TP/SL Grid",
            "",
            "Each row counts whether the path touched the take-profit threshold, the stop-loss threshold, both, or neither. `Both` is not a win or loss because first touch is unknown from OHLC bars.",
            "",
        ]
    )
    lines.extend(_markdown_table(["TP", "SL", "TP only", "SL only", "Both ambiguous", "Neither"], full_grid_rows))
    lines.extend(
        [
            "",
            "## Trader Read",
            "",
            f"- The average realized trade was `{gross['mean']:.2f}` gross ticks before costs, while the current round-turn cost is `{costs.round_turn_cost_ticks:.2f}` ticks.",
            f"- `{_count_pct(realized_le_two, total)}` of trades realized `<= 2` gross ticks, which is below the current cost threshold.",
            f"- `{_count_pct(mfe_le_two, total)}` of trades never offered more than `2` favorable ticks under the tradable path convention.",
            "- Interpretation: this policy did not only lose because costs were high. The realized gross edge was near flat/slightly negative, many trades had limited favorable excursion, and adverse excursion was common enough that simple tight stops would need first-touch validation before being trusted.",
            "- A future stop/target test should use ordered intrabar or lower-timeframe data before treating any ambiguous both-touched TP/SL cell as profitable or losing.",
            "",
        ]
    )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--bars", type=Path, default=DEFAULT_BARS)
    parser.add_argument("--costs-config", type=Path, default=DEFAULT_COSTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--market", default=DEFAULT_MARKET)
    return parser


def run(args: argparse.Namespace) -> Path:
    trades_path = _resolve(args.trades)
    bars_path = _resolve(args.bars)
    costs_path = _resolve(args.costs_config)
    output_path = _resolve(args.output)
    for path in (trades_path, bars_path, costs_path):
        if not path.exists():
            raise ValueError(f"missing input path: {_relative(path)}")

    costs = load_cost_config(costs_path, args.market)
    if costs.market != DEFAULT_MARKET:
        raise ValueError(f"expected ES-only analysis, got {costs.market}")
    trades = load_trades(trades_path)
    bars = load_bars(bars_path)
    frame = build_trade_excursion_frame(trades, bars, costs)
    grid = build_tp_sl_grid(frame)
    report = build_report(
        frame,
        grid,
        costs=costs,
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
        print(f"NO_GO trade tick excursion analysis: {exc}", file=sys.stderr)
        return 1
    print(f"WROTE trade tick excursion analysis: {_relative(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
