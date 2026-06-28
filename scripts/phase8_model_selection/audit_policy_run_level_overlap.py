#!/usr/bin/env python3
"""Audit Phase 8 row-level policy costs against run-level and overlap diagnostics."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from scripts.phase8_model_selection.evaluate_predictions import (
    DEFAULT_COSTS_CONFIG,
    PolicyConfig,
    build_policy_frame,
)


POSITION_LABELS = {-1: "short", 0: "flat", 1: "long"}
DEFAULT_RUN = "baseline"
REQUIRED_POLICY_COLUMNS = {
    "market",
    "fold_id",
    "timestamp",
    "target_entry_ts",
    "target_exit_ts",
    "position",
    "trade_count",
    "gross_dollars",
    "cost_dollars",
    "slippage_cost_dollars",
    "commission_cost_dollars",
    "round_turn_cost_dollars",
    "net_dollars",
}


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _json_default(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            pass
    return str(value)


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, default=_json_default, allow_nan=False),
        encoding="utf-8",
    )


def _sum_float(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").fillna(0.0).sum())


def _mean_or_none(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def _timestamp_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _metrics(frame: pd.DataFrame, scope: str, keys: Mapping[str, Any]) -> dict[str, Any]:
    rows = int(len(frame))
    traded = frame[frame["trade_count"].eq(1)] if "trade_count" in frame else frame.iloc[0:0]
    trade_count = int(len(traded))
    gross = _sum_float(frame["gross_dollars"]) if "gross_dollars" in frame else 0.0
    cost = _sum_float(frame["cost_dollars"]) if "cost_dollars" in frame else 0.0
    net = _sum_float(frame["net_dollars"]) if "net_dollars" in frame else 0.0
    return {
        "scope": scope,
        **dict(keys),
        "row_count": rows,
        "trade_count": trade_count,
        "long_count": int(frame["position"].eq(1).sum()) if "position" in frame else 0,
        "short_count": int(frame["position"].eq(-1).sum()) if "position" in frame else 0,
        "flat_count": int(frame["position"].eq(0).sum()) if "position" in frame else rows,
        "gross_return_dollars": gross,
        "slippage_cost_dollars": _sum_float(frame["slippage_cost_dollars"])
        if "slippage_cost_dollars" in frame
        else 0.0,
        "commission_cost_dollars": _sum_float(frame["commission_cost_dollars"])
        if "commission_cost_dollars" in frame
        else 0.0,
        "cost_dollars": cost,
        "net_return_dollars": net,
        "avg_gross_per_trade": gross / trade_count if trade_count else None,
        "avg_cost_per_trade": cost / trade_count if trade_count else None,
        "avg_net_per_trade": net / trade_count if trade_count else None,
        "net_win_rate": float(traded["net_dollars"].gt(0.0).mean()) if trade_count else None,
        "cost_drag_to_abs_gross": cost / abs(gross) if abs(gross) > 0.0 else None,
    }


def _execution_netting_summary(frame: pd.DataFrame) -> dict[str, Any]:
    candidate_trades = (
        int(frame["candidate_trade_count"].sum())
        if "candidate_trade_count" in frame
        else int(frame["trade_count"].sum())
    )
    executed_trades = int(frame["trade_count"].sum()) if "trade_count" in frame else 0
    blocked_overlap = (
        int(frame["blocked_by_execution_overlap"].sum())
        if "blocked_by_execution_overlap" in frame
        else 0
    )
    policy_values = (
        sorted(str(value) for value in frame["execution_policy"].dropna().unique())
        if "execution_policy" in frame
        else []
    )
    return {
        "policy": policy_values[0] if len(policy_values) == 1 else policy_values,
        "candidate_trade_count": candidate_trades,
        "executed_trade_count": executed_trades,
        "blocked_by_execution_overlap": blocked_overlap,
    }


def _group_metrics(
    frame: pd.DataFrame,
    *,
    scope: str,
    group_cols: list[str],
    sort_col: str = "net_return_dollars",
) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    records: list[dict[str, Any]] = []
    for keys, group in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        records.append(_metrics(group, scope, dict(zip(group_cols, keys))))
    records.sort(key=lambda item: float(item.get(sort_col) or 0.0))
    return records


def _prepare_policy_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    missing = sorted(REQUIRED_POLICY_COLUMNS - set(frame.columns))
    if missing:
        raise SystemExit(f"policy frame missing required diagnostic columns: {missing}")

    out = frame.copy()
    out["timestamp"] = _timestamp_series(out["timestamp"])
    out["target_entry_ts"] = _timestamp_series(out["target_entry_ts"])
    out["target_exit_ts"] = _timestamp_series(out["target_exit_ts"])
    traded = out["trade_count"].eq(1)
    bad_target_times = traded & (out["target_entry_ts"].isna() | out["target_exit_ts"].isna())
    if bool(bad_target_times.any()):
        raise SystemExit(
            f"traded policy rows with missing target timestamps: {int(bad_target_times.sum())}"
        )
    inverted = traded & out["target_exit_ts"].lt(out["target_entry_ts"])
    if bool(inverted.any()):
        raise SystemExit(
            f"traded policy rows with target_exit_ts before target_entry_ts: {int(inverted.sum())}"
        )

    warnings: list[str] = []
    out["side"] = out["position"].map(POSITION_LABELS).fillna("unknown")
    if "session_id" not in out.columns:
        warnings.append("session_id missing; run grouping uses market/fold only")
    if out["timestamp"].isna().any():
        warnings.append(f"unparseable policy timestamps: {int(out['timestamp'].isna().sum())}")
    return out, warnings


def _assign_position_runs(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    group_cols = [column for column in ("market", "fold_id", "session_id") if column in out.columns]
    sort_cols = group_cols + ["timestamp"]
    out = out.sort_values(sort_cols).reset_index(drop=True)
    previous_position = out.groupby(group_cols, dropna=False)["position"].shift(1).fillna(0)
    nonzero = out["position"].ne(0)
    run_start = nonzero & previous_position.ne(out["position"])
    out["_run_sequence"] = run_start.groupby(
        [out[column] for column in group_cols],
        dropna=False,
    ).cumsum()
    out["position_run_id"] = None
    out.loc[nonzero, "position_run_id"] = (
        out.loc[nonzero, group_cols].astype(str).agg("|".join, axis=1)
        + "|run_"
        + out.loc[nonzero, "_run_sequence"].astype(int).astype(str).str.zfill(6)
    )
    return out.drop(columns=["_run_sequence"])


def _build_run_frame(frame: pd.DataFrame) -> pd.DataFrame:
    traded = frame[frame["trade_count"].eq(1)].copy()
    if traded.empty:
        return pd.DataFrame()
    records: list[dict[str, Any]] = []
    for run_id, group in traded.groupby("position_run_id", dropna=False):
        ordered = group.sort_values("timestamp")
        first = ordered.iloc[0]
        gross = _sum_float(ordered["gross_dollars"])
        row_cost = _sum_float(ordered["cost_dollars"])
        run_cost = float(pd.to_numeric(ordered["round_turn_cost_dollars"], errors="coerce").iloc[0])
        run_slippage = float(pd.to_numeric(ordered["slippage_cost_dollars"], errors="coerce").iloc[0])
        run_commission = max(run_cost - run_slippage, 0.0)
        record = {
            "position_run_id": run_id,
            "market": first.get("market"),
            "fold_id": first.get("fold_id"),
            "session_id": first.get("session_id") if "session_id" in ordered else None,
            "side": first.get("side"),
            "position": int(first.get("position")),
            "start_timestamp": ordered["timestamp"].min(),
            "end_timestamp": ordered["timestamp"].max(),
            "row_count": int(len(ordered)),
            "gross_return_dollars": gross,
            "row_level_cost_dollars": row_cost,
            "run_level_cost_dollars": run_cost,
            "run_level_slippage_cost_dollars": run_slippage,
            "run_level_commission_cost_dollars": run_commission,
            "row_level_net_dollars": gross - row_cost,
            "run_level_net_dollars": gross - run_cost,
            "minutes_until_session_close_min": float(
                pd.to_numeric(ordered["minutes_until_session_close"], errors="coerce").min()
            )
            if "minutes_until_session_close" in ordered
            else None,
            "minutes_until_session_close_max": float(
                pd.to_numeric(ordered["minutes_until_session_close"], errors="coerce").max()
            )
            if "minutes_until_session_close" in ordered
            else None,
        }
        records.append(record)
    return pd.DataFrame(records).sort_values("run_level_net_dollars").reset_index(drop=True)


def _run_level_summary(frame: pd.DataFrame, runs: pd.DataFrame) -> dict[str, Any]:
    traded = frame[frame["trade_count"].eq(1)]
    row_level = _metrics(frame, "row_level_policy", {})
    if runs.empty:
        return {
            "run_count": 0,
            "one_bar_run_count": 0,
            "max_rows_per_run": 0,
            "avg_rows_per_run": None,
            "gross_return_dollars": 0.0,
            "row_level_cost_dollars": 0.0,
            "run_level_estimated_cost_dollars": 0.0,
            "row_level_net_dollars": 0.0,
            "run_level_estimated_net_dollars": 0.0,
            "cost_savings_vs_row_level_dollars": 0.0,
            "row_level": row_level,
        }
    gross = _sum_float(runs["gross_return_dollars"])
    row_cost = _sum_float(runs["row_level_cost_dollars"])
    run_cost = _sum_float(runs["run_level_cost_dollars"])
    return {
        "run_count": int(len(runs)),
        "one_bar_run_count": int(runs["row_count"].eq(1).sum()),
        "max_rows_per_run": int(runs["row_count"].max()),
        "avg_rows_per_run": float(runs["row_count"].mean()),
        "trade_rows_per_run": int(len(traded)) / int(len(runs)),
        "gross_return_dollars": gross,
        "row_level_cost_dollars": row_cost,
        "run_level_estimated_cost_dollars": run_cost,
        "row_level_slippage_cost_dollars": _sum_float(traded["slippage_cost_dollars"]),
        "run_level_estimated_slippage_cost_dollars": _sum_float(
            runs["run_level_slippage_cost_dollars"]
        ),
        "row_level_commission_cost_dollars": _sum_float(traded["commission_cost_dollars"]),
        "run_level_estimated_commission_cost_dollars": _sum_float(
            runs["run_level_commission_cost_dollars"]
        ),
        "row_level_net_dollars": gross - row_cost,
        "run_level_estimated_net_dollars": gross - run_cost,
        "cost_savings_vs_row_level_dollars": row_cost - run_cost,
        "row_level": row_level,
    }


def _select_non_overlapping_target_windows(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    traded = frame[frame["trade_count"].eq(1)].copy()
    if traded.empty:
        return traded, {
            "status": "PASS",
            "selected_trade_count": 0,
            "skipped_overlap_count": 0,
            "note": "no traded rows",
        }
    selected_indices: list[int] = []
    group_cols = [column for column in ("market", "fold_id") if column in traded.columns]
    for _, group in traded.sort_values(["target_entry_ts", "timestamp"]).groupby(
        group_cols,
        dropna=False,
    ):
        last_exit: pd.Timestamp | None = None
        for index, row in group.iterrows():
            entry = row["target_entry_ts"]
            exit_ = row["target_exit_ts"]
            if last_exit is None or entry >= last_exit:
                selected_indices.append(index)
                last_exit = exit_
            elif exit_ > last_exit:
                last_exit = exit_
    traded["non_overlapping_target_window"] = traded.index.isin(selected_indices)
    selected = traded[traded["non_overlapping_target_window"]].copy()
    skipped = int((~traded["non_overlapping_target_window"]).sum())
    summary = _metrics(selected, "non_overlapping_target_windows", {})
    summary.update(
        {
            "status": "PASS",
            "selected_trade_count": int(len(selected)),
            "skipped_overlap_count": skipped,
            "source_trade_count": int(len(traded)),
        }
    )
    return selected, summary


def _attach_time_buckets(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["hour_utc"] = out["timestamp"].dt.hour
    if "minutes_until_session_close" in out.columns:
        minutes = pd.to_numeric(out["minutes_until_session_close"], errors="coerce")
        out["minutes_to_close_bucket"] = pd.cut(
            minutes,
            bins=[-float("inf"), 30, 60, 120, 240, float("inf")],
            labels=["0-30", "31-60", "61-120", "121-240", "241+"],
        ).astype(str)
        out.loc[minutes.isna(), "minutes_to_close_bucket"] = "missing"
    else:
        out["minutes_to_close_bucket"] = "unavailable"
    return out


def _top_records(frame: pd.DataFrame, sort_col: str, limit: int = 10) -> list[dict[str, Any]]:
    if frame.empty or sort_col not in frame.columns:
        return []
    return frame.sort_values(sort_col, ascending=True).head(limit).to_dict(orient="records")


def _largest_run_records(runs: pd.DataFrame, limit: int = 10) -> list[dict[str, Any]]:
    if runs.empty or "row_count" not in runs.columns:
        return []
    return runs.sort_values("row_count", ascending=False).head(limit).to_dict(orient="records")


def _duplicate_policy_key_count(frame: pd.DataFrame) -> int:
    key_cols = [column for column in ("market", "fold_id", "timestamp") if column in frame.columns]
    if not key_cols:
        return 0
    return int(frame.duplicated(key_cols, keep=False).sum())


def _write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    row = report["row_vs_run_level"]
    overlap = report["non_overlapping_target_windows"]
    lines = [
        "# Phase 8 Policy Run-Level Overlap Audit",
        "",
        f"Run: `{report['run']}`",
        "",
        "This diagnostic reads saved predictions and reuses the existing Phase 8 policy frame.",
        "It does not change labels, features, WFA splits, costs, predictions, or policy behavior.",
        "",
        "## Summary",
        "",
        f"- Row-level net: `{row['row_level_net_dollars']}`",
        f"- Run-level estimated net: `{row['run_level_estimated_net_dollars']}`",
        f"- Policy trade rows: `{row['row_level']['trade_count']}`",
        f"- Continuous position runs: `{row['run_count']}`",
        f"- Non-overlapping selected trades: `{overlap['selected_trade_count']}`",
        f"- Overlapping trades skipped by diagnostic: `{overlap['skipped_overlap_count']}`",
        "",
        "## Caveat",
        "",
        "Run-level costs are a diagnostic sensitivity only; existing Phase 8 row-level metrics remain unchanged.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_policy_run_level_overlap_audit(
    *,
    predictions_path: Path,
    costs_config: Path,
    json_out: Path,
    md_out: Path | None,
    run: str,
    policy: PolicyConfig,
) -> dict[str, Any]:
    if not predictions_path.exists():
        raise SystemExit(f"prediction parquet missing: {_relative_path(predictions_path)}")

    predictions = pd.read_parquet(predictions_path)
    policy_frame, failures, warnings = build_policy_frame(predictions, costs_config, policy)
    if failures:
        raise SystemExit("; ".join(failures))

    policy_frame, prepare_warnings = _prepare_policy_frame(policy_frame)
    warnings.extend(prepare_warnings)
    policy_frame = _assign_position_runs(policy_frame)
    run_frame = _build_run_frame(policy_frame)
    selected_non_overlap, non_overlap_summary = _select_non_overlapping_target_windows(policy_frame)
    time_frame = _attach_time_buckets(policy_frame)

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run": run,
        "prediction_path": _relative_path(predictions_path),
        "costs_config": _relative_path(costs_config),
        "prediction_count": int(len(predictions)),
        "policy_row_count": int(len(policy_frame)),
        "diagnostic_only": True,
        "protected_logic_unchanged": [
            "labels",
            "features",
            "WFA splits",
            "model training",
            "cost math",
            "position policy",
        ],
        "integrity": {
            "duplicate_policy_key_rows": _duplicate_policy_key_count(policy_frame),
            "market_count": int(policy_frame["market"].nunique(dropna=True)),
            "fold_count": int(policy_frame["fold_id"].nunique(dropna=True)),
        },
        "row_vs_run_level": _run_level_summary(policy_frame, run_frame),
        "execution_netting": _execution_netting_summary(policy_frame),
        "non_overlapping_target_windows": non_overlap_summary,
        "breakdowns": {
            "by_side": _group_metrics(policy_frame, scope="side", group_cols=["side"]),
            "by_fold": _group_metrics(policy_frame, scope="fold", group_cols=["fold_id"]),
            "by_hour_utc": _group_metrics(time_frame, scope="hour_utc", group_cols=["hour_utc"]),
            "by_minutes_to_close_bucket": _group_metrics(
                time_frame,
                scope="minutes_to_close_bucket",
                group_cols=["minutes_to_close_bucket"],
            ),
            "non_overlapping_by_side": _group_metrics(
                selected_non_overlap,
                scope="non_overlapping_side",
                group_cols=["side"],
            ),
        },
        "worst_runs_by_run_level_net": _top_records(run_frame, "run_level_net_dollars"),
        "largest_runs_by_row_count": _largest_run_records(run_frame),
        "warnings": warnings,
    }
    _write_json(json_out, report)
    if md_out:
        _write_markdown(md_out, report)
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions",
        default=None,
        help="Explicit prediction parquet path. Required; no data/predictions default is used.",
    )
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out")
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--long-short-margin", type=float, default=0.05)
    parser.add_argument("--min-fade-success", type=float, default=0.50)
    parser.add_argument("--max-trend-danger", type=float, default=0.50)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.predictions:
        parser.error("--predictions is required; pass an explicit prediction parquet path")
    report = build_policy_run_level_overlap_audit(
        predictions_path=Path(args.predictions),
        costs_config=Path(args.costs_config),
        json_out=Path(args.json_out),
        md_out=Path(args.md_out) if args.md_out else None,
        run=args.run,
        policy=PolicyConfig(
            long_short_margin=args.long_short_margin,
            min_fade_success=args.min_fade_success,
            max_trend_danger=args.max_trend_danger,
            side_aware_trend_blocks_fade_trades=True,
        ),
    )
    row = report["row_vs_run_level"]
    print(
        "PASS policy run-level overlap audit: "
        f"trades={row['row_level']['trade_count']} "
        f"runs={row['run_count']} "
        f"row_net={row['row_level_net_dollars']} "
        f"run_net={row['run_level_estimated_net_dollars']} "
        f"report={_relative_path(Path(args.json_out))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
