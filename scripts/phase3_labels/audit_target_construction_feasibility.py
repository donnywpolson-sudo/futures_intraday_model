#!/usr/bin/env python3
"""Diagnostic target-construction feasibility audit.

This script reads existing labeled/feature rows and evaluates candidate target
definitions without writing new labels or changing Phase 3 semantics.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from scripts.phase3_labels.build_labels import (
    EXIT_OFFSET_BARS,
    ENTRY_OFFSET_BARS,
    LABEL_SEMANTICS_ID,
    _first_hit,
    _future_path_checks,
    _true_range_ticks,
    load_market_config,
)


DEFAULT_INPUT_ROOT = Path("data/labeled")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_REGIME_PERIOD_WIDTH_YEARS = 5

REQUIRED_COLUMNS = [
    "ts",
    "market",
    "year",
    "open",
    "high",
    "low",
    "close",
    "target_valid",
    "target_entry_ts",
    "target_exit_ts",
    "target_gross_dollars_15m",
    "target_estimated_cost_dollars",
    "target_sign_with_deadzone",
    "causal_valid",
    "session_segment_id",
    "is_synthetic",
    "valid_ohlcv",
    "boundary_session_flag",
    "roll_window_flag",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _finite_sum(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return float(values.dropna().sum())


def _finite_mean(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    values = values.dropna()
    if values.empty:
        return None
    return float(values.mean())


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0 or not math.isfinite(denominator):
        return None
    return float(numerator / denominator)


def _read_inputs(paths: Sequence[Path]) -> pd.DataFrame:
    if not paths:
        raise SystemExit("no input parquet paths resolved")
    frames: list[pd.DataFrame] = []
    for path in paths:
        if not path.exists():
            raise SystemExit(f"missing input parquet: {_relative_path(path)}")
        frame = pd.read_parquet(path)
        frame["_source_path"] = _relative_path(path)
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise SystemExit(f"input rows missing required columns: {missing}")
    duplicate_key = data.duplicated(["market", "year", "ts"], keep=False)
    if duplicate_key.any():
        raise SystemExit(f"duplicate market/year/ts rows: {int(duplicate_key.sum())}")
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    data["target_entry_ts"] = pd.to_datetime(
        data["target_entry_ts"], utc=True, errors="coerce"
    )
    data["target_exit_ts"] = pd.to_datetime(data["target_exit_ts"], utc=True, errors="coerce")
    data = data.sort_values(["market", "year", "ts"], kind="mergesort").reset_index(drop=True)
    return data


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing JSON input: {_relative_path(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid JSON object: {_relative_path(path)}")
    return payload


def _utc_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("timestamp is null")
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _assign_fold_ids(data: pd.DataFrame, split_plan_json: Path | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    if split_plan_json is None:
        return data, {"split_plan_json": None, "fold_mapping_enabled": False}

    payload = _read_json(split_plan_json)
    folds = payload.get("folds")
    if not isinstance(folds, list) or not folds:
        raise SystemExit(f"split plan has no folds: {_relative_path(split_plan_json)}")

    mapped = data.copy()
    mapped["fold_id"] = pd.NA
    mapped_fold_count = 0
    skipped_fold_count = 0
    for raw_fold in folds:
        if not isinstance(raw_fold, dict):
            raise SystemExit("split plan fold entry is not an object")
        missing = [
            field
            for field in ("market", "fold_id", "test_start", "test_end", "selection_allowed")
            if field not in raw_fold
        ]
        if missing:
            raise SystemExit(f"split plan fold missing required fields: {missing}")
        if raw_fold.get("selection_allowed") is not True:
            skipped_fold_count += 1
            continue
        if raw_fold.get("split_group", "research") != "research":
            skipped_fold_count += 1
            continue

        market = str(raw_fold["market"])
        fold_id = str(raw_fold["fold_id"])
        try:
            test_start = _utc_timestamp(raw_fold["test_start"])
            test_end = _utc_timestamp(raw_fold["test_end"])
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"{fold_id}: invalid split-plan timestamps: {exc}") from exc
        if test_start > test_end:
            raise SystemExit(f"{fold_id}: test_start after test_end")

        mask = (
            mapped["market"].astype(str).eq(market)
            & mapped["ts"].ge(test_start)
            & mapped["ts"].le(test_end)
        )
        overlap = mask & mapped["fold_id"].notna()
        if overlap.any():
            raise SystemExit(
                f"split plan assigns overlapping test folds to {int(overlap.sum())} rows"
            )
        mapped.loc[mask, "fold_id"] = fold_id
        mapped_fold_count += 1

    return mapped, {
        "split_plan_json": _relative_path(split_plan_json),
        "fold_mapping_enabled": True,
        "selection_allowed_research_folds_mapped": mapped_fold_count,
        "folds_skipped_not_selection_allowed_or_research": skipped_fold_count,
        "rows_with_fold_id": int(mapped["fold_id"].notna().sum()),
        "rows_without_fold_id": int(mapped["fold_id"].isna().sum()),
    }


def _resolve_input_paths(
    *,
    input_parquet: Sequence[Path],
    input_root: Path,
    markets: Sequence[str],
    years: Sequence[int],
) -> list[Path]:
    if input_parquet:
        return list(input_parquet)
    if not markets or not years:
        raise SystemExit("provide --input-parquet or both --markets and --years")
    return [input_root / market / f"{year}.parquet" for market in markets for year in years]


def _parse_regime_period(value: str) -> tuple[str, int, int]:
    try:
        name, years = value.split(":", 1)
        start_raw, end_raw = years.split("-", 1)
        start_year = int(start_raw)
        end_year = int(end_raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "regime periods must use NAME:START-END, for example recent:2020-2024"
        ) from exc
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("regime period name cannot be empty")
    if start_year > end_year:
        raise argparse.ArgumentTypeError("regime period start year must be <= end year")
    return name, start_year, end_year


def _default_regime_periods(years: pd.Series) -> list[tuple[str, int, int]]:
    clean_years = pd.to_numeric(years, errors="coerce").dropna().astype(int)
    if clean_years.empty:
        return []
    start = int(clean_years.min())
    end = int(clean_years.max())
    periods: list[tuple[str, int, int]] = []
    current = start
    while current <= end:
        period_end = min(current + DEFAULT_REGIME_PERIOD_WIDTH_YEARS - 1, end)
        periods.append((f"calendar_{current}_{period_end}", current, period_end))
        current = period_end + 1
    return periods


def _validate_regime_periods(periods: Sequence[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    names: set[str] = set()
    sorted_periods = sorted(periods, key=lambda item: (item[1], item[2], item[0]))
    previous_end: int | None = None
    for name, start_year, end_year in sorted_periods:
        if name in names:
            raise SystemExit(f"duplicate regime period name: {name}")
        names.add(name)
        if start_year > end_year:
            raise SystemExit(f"invalid regime period {name}: start year after end year")
        if previous_end is not None and start_year <= previous_end:
            raise SystemExit("regime periods must not overlap")
        previous_end = end_year
    return sorted_periods


def _market_configs(markets: Iterable[str], costs_config: Path) -> dict[str, Any]:
    configs: dict[str, Any] = {}
    for market in sorted(set(markets)):
        config = load_market_config(market, costs_config)
        if config.defaults_used or config.provisional:
            raise SystemExit(
                "cost assumptions must be explicit for target feasibility audit: "
                f"{market} defaults_used={config.defaults_used} provisional={config.provisional}"
            )
        configs[market] = config
    return configs


def _non_overlapping_events(data: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    valid = data[data["target_valid"].astype(bool)].copy()
    missing_windows = valid["target_entry_ts"].isna() | valid["target_exit_ts"].isna()
    if missing_windows.any():
        raise SystemExit(f"target_valid rows with missing target windows: {int(missing_windows.sum())}")

    selected_indices: list[int] = []
    skipped = 0
    group_cols = ["market", "year", "session_segment_id"]
    for _, group in valid.groupby(group_cols, dropna=False, sort=False):
        last_exit: pd.Timestamp | None = None
        for row in group.sort_values("target_entry_ts", kind="mergesort").itertuples():
            entry_ts = row.target_entry_ts
            exit_ts = row.target_exit_ts
            if last_exit is not None and entry_ts <= last_exit:
                skipped += 1
                continue
            selected_indices.append(int(row.Index))
            last_exit = exit_ts
    events = data.loc[selected_indices].sort_values(["market", "year", "ts"], kind="mergesort")
    return events.copy(), skipped


def _scope_metrics(
    *,
    scope: str,
    labels: pd.Series,
    gross: pd.Series,
    costs: pd.Series,
    key_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = labels.isin(["long", "short"])
    net = gross[selected] - costs[selected]
    selected_count = int(selected.sum())
    row: dict[str, Any] = {
        "scope": scope,
        "event_count": int(len(labels)),
        "selected_event_count": selected_count,
        "flat_event_count": int((labels == "flat").sum()),
        "ambiguous_event_count": int((labels == "ambiguous").sum()),
        "long_label_count": int((labels == "long").sum()),
        "short_label_count": int((labels == "short").sum()),
        "gross_opportunity_dollars": _finite_sum(gross[selected]),
        "cost_dollars": _finite_sum(costs[selected]),
        "net_oracle_dollars": _finite_sum(net),
        "avg_net_oracle_dollars": _finite_mean(net),
        "cost_clear_rate": _safe_ratio(float((net > 0).sum()), float(selected_count)),
    }
    if key_values:
        row.update(key_values)
    return row


def _candidate_breakdowns(
    *,
    events: pd.DataFrame,
    labels: pd.Series,
    gross: pd.Series,
    costs: pd.Series,
    regime_periods: Sequence[tuple[str, int, int]],
) -> dict[str, Any]:
    by_market_year: list[dict[str, Any]] = []
    for (market, year), group in events.groupby(["market", "year"], dropna=False, sort=False):
        idx = group.index
        by_market_year.append(
            _scope_metrics(
                scope="market_year",
                labels=labels.loc[idx],
                gross=gross.loc[idx],
                costs=costs.loc[idx],
                key_values={"market": str(market), "year": int(year)},
            )
        )

    by_side: list[dict[str, Any]] = []
    for side in ("long", "short", "flat", "ambiguous"):
        idx = labels[labels == side].index
        by_side.append(
            _scope_metrics(
                scope="side",
                labels=labels.loc[idx],
                gross=gross.loc[idx],
                costs=costs.loc[idx],
                key_values={"side": side},
            )
        )

    by_fold: list[dict[str, Any]] = []
    if "fold_id" in events.columns:
        fold_events = events.copy()
        fold_events["fold_id"] = fold_events["fold_id"].astype("string").fillna("unmapped")
        for fold_id, group in fold_events.groupby("fold_id", dropna=False, sort=False):
            idx = group.index
            by_fold.append(
                _scope_metrics(
                    scope="fold",
                    labels=labels.loc[idx],
                    gross=gross.loc[idx],
                    costs=costs.loc[idx],
                    key_values={"fold_id": str(fold_id)},
                )
            )

    by_regime_period: list[dict[str, Any]] = []
    event_years = pd.to_numeric(events["year"], errors="coerce")
    covered = pd.Series(False, index=events.index)
    for name, start_year, end_year in regime_periods:
        mask = event_years.between(start_year, end_year, inclusive="both").fillna(False)
        idx = events.index[mask]
        covered.loc[idx] = True
        by_regime_period.append(
            _scope_metrics(
                scope="regime_period",
                labels=labels.loc[idx],
                gross=gross.loc[idx],
                costs=costs.loc[idx],
                key_values={
                    "regime_period": name,
                    "start_year": start_year,
                    "end_year": end_year,
                },
            )
        )
    uncovered_idx = covered[~covered].index
    if len(uncovered_idx) > 0:
        by_regime_period.append(
            _scope_metrics(
                scope="regime_period",
                labels=labels.loc[uncovered_idx],
                gross=gross.loc[uncovered_idx],
                costs=costs.loc[uncovered_idx],
                key_values={
                    "regime_period": "unmapped",
                    "start_year": None,
                    "end_year": None,
                },
            )
        )

    return {
        "by_market_year": by_market_year,
        "by_side": by_side,
        "by_fold": by_fold,
        "by_regime_period": by_regime_period,
        "breakdown_available": {
            "market_year": True,
            "side": True,
            "fold": "fold_id" in events.columns,
            "regime_period": True,
        },
    }


def _fixed_current_summary(
    events: pd.DataFrame,
    regime_periods: Sequence[tuple[str, int, int]],
) -> dict[str, Any]:
    sign = pd.to_numeric(events["target_sign_with_deadzone"], errors="coerce").fillna(0)
    labels = pd.Series("flat", index=events.index, dtype="string")
    labels.loc[sign[sign > 0].index] = "long"
    labels.loc[sign[sign < 0].index] = "short"
    gross = pd.to_numeric(events["target_gross_dollars_15m"], errors="coerce").abs()
    costs = pd.to_numeric(events["target_estimated_cost_dollars"], errors="coerce")
    summary = _scope_metrics(scope="overall", labels=labels, gross=gross, costs=costs)
    summary.update(
        {
        "candidate": "current_fixed_15m_deadzone_direction_oracle",
        "diagnostic_only": True,
        "description": "Non-tradeable upper bound if current deadzone direction label were known at entry.",
        }
    )
    summary.update(
        _candidate_breakdowns(
            events=events,
            labels=labels,
            gross=gross,
            costs=costs,
            regime_periods=regime_periods,
        )
    )
    return summary


def _candidate_metrics(
    *,
    candidate: str,
    events: pd.DataFrame,
    labels: pd.Series,
    gross: pd.Series,
    costs: pd.Series,
    regime_periods: Sequence[tuple[str, int, int]],
    description: str,
) -> dict[str, Any]:
    summary = _scope_metrics(scope="overall", labels=labels, gross=gross, costs=costs)
    summary.update(
        {
        "candidate": candidate,
        "diagnostic_only": True,
        "description": description,
        }
    )
    summary.update(
        _candidate_breakdowns(
            events=events,
            labels=labels,
            gross=gross,
            costs=costs,
            regime_periods=regime_periods,
        )
    )
    return summary


def _barrier_summary(
    data: pd.DataFrame,
    events: pd.DataFrame,
    configs: dict[str, Any],
    regime_periods: Sequence[tuple[str, int, int]],
) -> dict[str, Any]:
    labels = pd.Series("flat", index=events.index, dtype="string")
    gross = pd.Series(np.nan, index=events.index, dtype=float)
    costs = pd.Series(np.nan, index=events.index, dtype=float)

    for (market, year), group in data.groupby(["market", "year"], sort=False):
        config = configs[str(market)]
        group = group.sort_values("ts", kind="mergesort")
        entry_price = pd.to_numeric(group["open"], errors="coerce").shift(-ENTRY_OFFSET_BARS)
        atr_ref_ticks = _true_range_ticks(group, config.tick_size)
        profit_ticks = np.maximum(config.min_profit_ticks, 0.50 * atr_ref_ticks)
        adverse_ticks = np.maximum(config.min_stop_ticks, 1.00 * atr_ref_ticks)

        checks = _future_path_checks(group, EXIT_OFFSET_BARS)
        path_valid = (
            group["target_valid"].astype(bool)
            & ~checks["segment_cross"]
            & ~checks["synthetic"]
            & ~checks["invalid_ohlcv"]
            & ~checks["boundary"]
            & ~checks["roll"]
            & entry_price.notna()
        )

        long_profit_first = _first_hit(
            group, entry_price, profit_ticks, config.tick_size, side="long", kind="profit"
        )
        long_adverse_first = _first_hit(
            group, entry_price, adverse_ticks, config.tick_size, side="long", kind="adverse"
        )
        short_profit_first = _first_hit(
            group, entry_price, profit_ticks, config.tick_size, side="short", kind="profit"
        )
        short_adverse_first = _first_hit(
            group, entry_price, adverse_ticks, config.tick_size, side="short", kind="adverse"
        )

        long_success = path_valid.to_numpy() & np.isfinite(long_profit_first) & (
            long_profit_first < long_adverse_first
        )
        short_success = path_valid.to_numpy() & np.isfinite(short_profit_first) & (
            short_profit_first < short_adverse_first
        )

        group_labels = pd.Series("flat", index=group.index, dtype="string")
        group_labels.loc[long_success & ~short_success] = "long"
        group_labels.loc[short_success & ~long_success] = "short"
        group_labels.loc[long_success & short_success] = "ambiguous"

        group_gross = pd.Series(profit_ticks * config.tick_value, index=group.index, dtype=float)
        group_costs = pd.Series(config.estimated_cost_dollars, index=group.index, dtype=float)
        overlap = events.index.intersection(group.index)
        labels.loc[overlap] = group_labels.loc[overlap]
        gross.loc[overlap] = group_gross.loc[overlap]
        costs.loc[overlap] = group_costs.loc[overlap]

    return _candidate_metrics(
        candidate="pathwise_first_hit_barrier_15m_directional",
        events=events,
        labels=labels,
        gross=gross,
        costs=costs,
        regime_periods=regime_periods,
        description=(
            "Directional label when one side hits a causal profit barrier before "
            "its adverse barrier within the existing 15m path; ambiguous both-side "
            "successes are not accepted as directional labels."
        ),
    )


def build_target_feasibility_report(
    *,
    input_paths: Sequence[Path],
    costs_config: Path,
    split_plan_json: Path | None = None,
    regime_periods: Sequence[tuple[str, int, int]] | None = None,
) -> dict[str, Any]:
    data = _read_inputs(input_paths)
    data, fold_mapping = _assign_fold_ids(data, split_plan_json)
    resolved_regime_periods = _validate_regime_periods(
        regime_periods if regime_periods is not None else _default_regime_periods(data["year"])
    )
    configs = _market_configs(data["market"].astype(str).unique().tolist(), costs_config)
    events, skipped_overlap = _non_overlapping_events(data)
    candidates = [
        _fixed_current_summary(events, resolved_regime_periods),
        _barrier_summary(data, events, configs, resolved_regime_periods),
    ]
    return {
        "generated_at_utc": _utc_now(),
        "diagnostic_only": True,
        "label_semantics_id": LABEL_SEMANTICS_ID,
        "entry_offset_bars": ENTRY_OFFSET_BARS,
        "exit_offset_bars": EXIT_OFFSET_BARS,
        "costs_config": _relative_path(costs_config),
        "fold_mapping": fold_mapping,
        "regime_periods": [
            {"name": name, "start_year": start_year, "end_year": end_year}
            for name, start_year, end_year in resolved_regime_periods
        ],
        "input_paths": [_relative_path(path) for path in input_paths],
        "source_row_count": int(len(data)),
        "target_valid_row_count": int(data["target_valid"].astype(bool).sum()),
        "non_overlapping_event_count": int(len(events)),
        "skipped_overlapping_valid_rows": int(skipped_overlap),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "decision": {
            "next_action": "review_target_candidate_regime_breakdowns_before_phase3_changes",
            "phase3_changed": False,
            "features_changed": False,
            "wfa_run": False,
            "alpha_search_run": False,
        },
        "protected_logic_unchanged": [
            "labels",
            "features",
            "model_training",
            "wfa_split_logic",
            "cost_math",
            "position_policy",
        ],
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    rows = [
        "| Candidate | Events | Selected | Long | Short | Gross | Cost | Net oracle | Cost-clear |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["candidates"]:
        rows.append(
            "| {candidate} | {event_count} | {selected_event_count} | {long_label_count} | "
            "{short_label_count} | {gross_opportunity_dollars:.2f} | {cost_dollars:.2f} | "
            "{net_oracle_dollars:.2f} | {cost_clear_rate} |".format(
                **{
                    **item,
                    "cost_clear_rate": (
                        "null"
                        if item["cost_clear_rate"] is None
                        else f"{item['cost_clear_rate']:.4f}"
                    ),
                }
            )
        )
    text = "\n".join(
        [
            "# Target Construction Feasibility Audit",
            "",
            f"Generated: `{report['generated_at_utc']}`",
            f"Diagnostic only: `{report['diagnostic_only']}`",
            f"Source rows: `{report['source_row_count']}`",
            f"Target-valid rows: `{report['target_valid_row_count']}`",
            f"Non-overlapping events: `{report['non_overlapping_event_count']}`",
            f"Skipped overlapping valid rows: `{report['skipped_overlapping_valid_rows']}`",
            "",
            *rows,
            "",
            "Per-candidate market/year, side, fold, and regime-period breakdowns are included in the JSON report when available.",
            "No Phase 3 labels, Phase 4 features, WFA splits, costs, or position policy were changed.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-parquet", action="append", type=Path, default=[])
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--markets", nargs="*", default=[])
    parser.add_argument("--years", nargs="*", type=int, default=[])
    parser.add_argument("--costs-config", type=Path, default=DEFAULT_COSTS_CONFIG)
    parser.add_argument("--split-plan-json", type=Path)
    parser.add_argument(
        "--regime-period",
        action="append",
        type=_parse_regime_period,
        default=None,
        help="Optional NAME:START-END period; repeatable. Defaults to deterministic 5-year calendar periods.",
    )
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--md-out", type=Path)
    args = parser.parse_args(argv)

    input_paths = _resolve_input_paths(
        input_parquet=args.input_parquet,
        input_root=args.input_root,
        markets=args.markets,
        years=args.years,
    )
    report = build_target_feasibility_report(
        input_paths=input_paths,
        costs_config=args.costs_config,
        split_plan_json=args.split_plan_json,
        regime_periods=args.regime_period,
    )
    _write_json(args.json_out, report)
    if args.md_out:
        _write_markdown(args.md_out, report)
    print(
        "PASS target feasibility audit: "
        f"events={report['non_overlapping_event_count']} "
        f"candidates={report['candidate_count']} report={_relative_path(args.json_out)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
