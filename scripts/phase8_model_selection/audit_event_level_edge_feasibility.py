#!/usr/bin/env python3
"""Audit non-overlapping event-level edge feasibility from saved Phase 8 predictions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from scripts.phase8_model_selection.audit_policy_run_level_overlap import (
    _relative_path,
    _sum_float,
    _timestamp_series,
    _write_json,
)
from scripts.phase8_model_selection.evaluate_predictions import (
    DEFAULT_COSTS_CONFIG,
    DEFAULT_PREDICTIONS,
    PolicyConfig,
    build_policy_frame,
)


DEFAULT_RUN = "baseline"
POSITION_LABELS = {-1: "short", 0: "flat", 1: "long"}
REQUIRED_POLICY_COLUMNS = {
    "market",
    "fold_id",
    "timestamp",
    "target_entry_ts",
    "target_exit_ts",
    "base_position",
    "position",
    "trade_count",
    "p_long",
    "p_short",
    "p_flat",
    "direction_margin",
    "observed_direction_target",
    "price_move",
    "point_value",
    "round_turn_cost_dollars",
    "tick_value",
    "slippage_ticks_per_side",
}
MIN_EVENT_COUNT = 100
MIN_POSITIVE_FOLD_RATE = 0.50


def _mean_or_none(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def _accuracy_or_none(position: pd.Series, target: pd.Series) -> float | None:
    aligned = pd.DataFrame({"position": position, "target": target}).dropna()
    aligned = aligned[aligned["position"].ne(0) & aligned["target"].isin([-1, 0, 1])]
    if aligned.empty:
        return None
    return float(aligned["position"].eq(aligned["target"]).mean())


def _validate_policy_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_POLICY_COLUMNS - set(frame.columns))
    if missing:
        raise SystemExit(f"policy frame missing required diagnostic columns: {missing}")

    out = frame.copy()
    key_cols = ["market", "fold_id", "timestamp"]
    duplicate_count = int(out.duplicated(key_cols, keep=False).sum())
    if duplicate_count:
        raise SystemExit(f"duplicate policy keys found for {key_cols}: {duplicate_count}")

    out["timestamp"] = _timestamp_series(out["timestamp"])
    out["target_entry_ts"] = _timestamp_series(out["target_entry_ts"])
    out["target_exit_ts"] = _timestamp_series(out["target_exit_ts"])
    bad_times = out["target_entry_ts"].isna() | out["target_exit_ts"].isna()
    if bool(bad_times.any()):
        raise SystemExit(f"policy rows with missing target timestamps: {int(bad_times.sum())}")
    inverted = out["target_exit_ts"].lt(out["target_entry_ts"])
    if bool(inverted.any()):
        raise SystemExit(f"target_exit_ts before target_entry_ts rows: {int(inverted.sum())}")

    costs_missing = out["round_turn_cost_dollars"].isna() | out["point_value"].isna()
    if bool(costs_missing.any()):
        raise SystemExit(f"policy rows with missing costs: {int(costs_missing.sum())}")
    return out


def _candidate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    candidates = frame[frame["base_position"].ne(0)].copy()
    if candidates.empty:
        return candidates
    candidates["candidate_position"] = candidates["base_position"].astype(int)
    candidates["candidate_side"] = candidates["candidate_position"].map(POSITION_LABELS).fillna("unknown")
    candidates["candidate_direction_probability"] = candidates["p_short"]
    long_mask = candidates["candidate_position"].eq(1)
    candidates.loc[long_mask, "candidate_direction_probability"] = candidates.loc[long_mask, "p_long"]
    candidates["candidate_rank_score"] = (
        pd.to_numeric(candidates["candidate_direction_probability"], errors="coerce")
        - pd.to_numeric(candidates["p_flat"], errors="coerce")
    )
    candidates["candidate_gross_dollars"] = (
        candidates["candidate_position"]
        * pd.to_numeric(candidates["price_move"], errors="coerce").fillna(0.0)
        * pd.to_numeric(candidates["point_value"], errors="coerce").fillna(0.0)
    )
    row_slippage = (
        2.0
        * pd.to_numeric(candidates["slippage_ticks_per_side"], errors="coerce").fillna(0.0)
        * pd.to_numeric(candidates["tick_value"], errors="coerce").fillna(0.0)
    )
    round_turn = pd.to_numeric(candidates["round_turn_cost_dollars"], errors="coerce").fillna(0.0)
    candidates["candidate_slippage_cost_dollars"] = row_slippage
    candidates["candidate_commission_cost_dollars"] = (round_turn - row_slippage).clip(lower=0.0)
    candidates["candidate_cost_dollars"] = round_turn
    candidates["candidate_net_dollars"] = (
        candidates["candidate_gross_dollars"] - candidates["candidate_cost_dollars"]
    )
    candidates["candidate_direction_correct"] = candidates["candidate_position"].eq(
        pd.to_numeric(candidates["observed_direction_target"], errors="coerce")
    )
    return candidates


def _select_non_overlapping_events(candidates: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if candidates.empty:
        return candidates.copy(), 0
    selected_indices: list[int] = []
    skipped = 0
    group_cols = ["market", "fold_id"]
    ordered = candidates.sort_values(group_cols + ["target_entry_ts", "timestamp"])
    for _, group in ordered.groupby(group_cols, dropna=False):
        last_exit: pd.Timestamp | None = None
        for index, row in group.iterrows():
            entry = row["target_entry_ts"]
            exit_ = row["target_exit_ts"]
            if last_exit is None or entry >= last_exit:
                selected_indices.append(index)
                last_exit = exit_
            else:
                skipped += 1
                if exit_ > last_exit:
                    last_exit = exit_
    events = candidates.loc[selected_indices].copy().sort_values(group_cols + ["target_entry_ts"])
    events = events.reset_index(drop=True)
    return events, skipped


def _metrics(frame: pd.DataFrame, scope: str, keys: Mapping[str, Any]) -> dict[str, Any]:
    event_count = int(len(frame))
    gross = _sum_float(frame["candidate_gross_dollars"]) if "candidate_gross_dollars" in frame else 0.0
    cost = _sum_float(frame["candidate_cost_dollars"]) if "candidate_cost_dollars" in frame else 0.0
    net = _sum_float(frame["candidate_net_dollars"]) if "candidate_net_dollars" in frame else 0.0
    return {
        "scope": scope,
        **dict(keys),
        "event_count": event_count,
        "long_count": int(frame["candidate_position"].eq(1).sum()) if "candidate_position" in frame else 0,
        "short_count": int(frame["candidate_position"].eq(-1).sum())
        if "candidate_position" in frame
        else 0,
        "gross_return_dollars": gross,
        "slippage_cost_dollars": _sum_float(frame["candidate_slippage_cost_dollars"])
        if "candidate_slippage_cost_dollars" in frame
        else 0.0,
        "commission_cost_dollars": _sum_float(frame["candidate_commission_cost_dollars"])
        if "candidate_commission_cost_dollars" in frame
        else 0.0,
        "cost_dollars": cost,
        "net_return_dollars": net,
        "avg_gross_per_event": gross / event_count if event_count else None,
        "avg_cost_per_event": cost / event_count if event_count else None,
        "avg_net_per_event": net / event_count if event_count else None,
        "net_win_rate": float(frame["candidate_net_dollars"].gt(0.0).mean()) if event_count else None,
        "direction_accuracy": _accuracy_or_none(
            frame["candidate_position"],
            pd.to_numeric(frame["observed_direction_target"], errors="coerce"),
        )
        if event_count
        else None,
        "avg_rank_score": _mean_or_none(frame["candidate_rank_score"]) if event_count else None,
        "cost_drag_to_abs_gross": cost / abs(gross) if abs(gross) > 0.0 else None,
    }


def _group_metrics(frame: pd.DataFrame, *, scope: str, group_cols: list[str]) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    records: list[dict[str, Any]] = []
    for keys, group in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        records.append(_metrics(group, scope, dict(zip(group_cols, keys))))
    records.sort(key=lambda item: float(item.get("net_return_dollars") or 0.0))
    return records


def _attach_rank_buckets(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    if out.empty:
        out["rank_bucket"] = []
        return out
    out = out.sort_values("candidate_rank_score", ascending=False, na_position="last").reset_index(drop=True)
    rank_fraction = (pd.Series(range(len(out)), index=out.index, dtype=float) + 1.0) / float(len(out))
    out["rank_bucket"] = "bottom_50_pct"
    out.loc[rank_fraction.le(0.10), "rank_bucket"] = "top_10_pct"
    out.loc[rank_fraction.gt(0.10) & rank_fraction.le(0.25), "rank_bucket"] = "top_10_to_25_pct"
    out.loc[rank_fraction.gt(0.25) & rank_fraction.le(0.50), "rank_bucket"] = "top_25_to_50_pct"
    return out


def _decision(overall: Mapping[str, Any], by_fold: list[Mapping[str, Any]]) -> dict[str, Any]:
    event_count = int(overall.get("event_count") or 0)
    gross = float(overall.get("gross_return_dollars") or 0.0)
    net = float(overall.get("net_return_dollars") or 0.0)
    positive_folds = [row for row in by_fold if float(row.get("net_return_dollars") or 0.0) > 0.0]
    fold_count = len(by_fold)
    positive_fold_rate = len(positive_folds) / fold_count if fold_count else 0.0
    reasons: list[str] = []
    if event_count < MIN_EVENT_COUNT:
        reasons.append(f"event_count {event_count} below minimum {MIN_EVENT_COUNT}")
    if gross <= 0.0:
        reasons.append("gross_return_dollars is not positive")
    if net <= 0.0:
        reasons.append("net_return_dollars is not positive")
    if positive_fold_rate < MIN_POSITIVE_FOLD_RATE:
        reasons.append(
            f"positive_fold_rate {positive_fold_rate:.4f} below minimum {MIN_POSITIVE_FOLD_RATE:.4f}"
        )
    supports = not reasons
    return {
        "supports_new_edge_model_research": supports,
        "decision": "supports_new_edge_model_research"
        if supports
        else "does_not_support_new_edge_model_research",
        "positive_fold_count": len(positive_folds),
        "fold_count": fold_count,
        "positive_fold_rate": positive_fold_rate,
        "minimum_event_count": MIN_EVENT_COUNT,
        "minimum_positive_fold_rate": MIN_POSITIVE_FOLD_RATE,
        "reasons": reasons,
    }


def _write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    overall = report["event_metrics"]["overall"]
    decision = report["decision"]
    lines = [
        "# Phase 8 Event-Level Edge Feasibility Audit",
        "",
        f"Run: `{report['run']}`",
        "",
        "This diagnostic converts saved Phase 8 prediction rows into chronological,",
        "non-overlapping target-window events. It does not change labels, features,",
        "model training, WFA splits, cost math, existing Phase 8 metrics, or position policy.",
        "",
        "## Summary",
        "",
        f"- Source prediction rows: `{report['source_prediction_rows']}`",
        f"- Policy rows: `{report['policy_row_count']}`",
        f"- Current-policy traded rows: `{report['current_policy_traded_rows']}`",
        f"- Direction candidate rows: `{report['direction_candidate_rows']}`",
        f"- Non-overlapping events: `{report['non_overlapping_event_count']}`",
        f"- Skipped overlapping rows: `{report['skipped_overlapping_rows']}`",
        f"- Event net dollars: `{overall['net_return_dollars']}`",
        f"- Event direction accuracy: `{overall['direction_accuracy']}`",
        f"- Decision: `{decision['decision']}`",
        "",
        "## Decision Reasons",
        "",
    ]
    reasons = decision.get("reasons") or ["none"]
    lines.extend(f"- {reason}" for reason in reasons)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_event_level_edge_feasibility(
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
    policy_frame = _validate_policy_frame(policy_frame)
    candidates = _candidate_frame(policy_frame)
    events, skipped = _select_non_overlapping_events(candidates)
    events = _attach_rank_buckets(events)

    overall = _metrics(events, "event_overall", {})
    by_fold = _group_metrics(events, scope="event_fold", group_cols=["fold_id"])
    by_side = _group_metrics(events, scope="event_side", group_cols=["candidate_side"])
    by_rank_bucket = _group_metrics(events, scope="event_rank_bucket", group_cols=["rank_bucket"])
    decision = _decision(overall, by_fold)
    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run": run,
        "prediction_path": _relative_path(predictions_path),
        "costs_config": _relative_path(costs_config),
        "diagnostic_only": True,
        "source_prediction_rows": int(len(predictions)),
        "policy_row_count": int(len(policy_frame)),
        "current_policy_traded_rows": int(policy_frame["trade_count"].sum()),
        "direction_candidate_rows": int(len(candidates)),
        "non_overlapping_event_count": int(len(events)),
        "skipped_overlapping_rows": skipped,
        "event_selection": "chronological_non_overlapping_by_market_fold",
        "ranker_use": "direction probabilities are reported as diagnostic rankers only",
        "policy_config": {
            "long_short_margin": policy.long_short_margin,
            "min_fade_success": policy.min_fade_success,
            "max_trend_danger": policy.max_trend_danger,
        },
        "event_metrics": {
            "overall": overall,
            "by_fold": by_fold,
            "by_side": by_side,
            "by_rank_bucket": by_rank_bucket,
        },
        "decision": decision,
        "warnings": warnings,
    }
    _write_json(json_out, report)
    if md_out:
        _write_markdown(md_out, report)
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out")
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--long-short-margin", type=float, default=0.05)
    parser.add_argument("--min-fade-success", type=float, default=0.50)
    parser.add_argument("--max-trend-danger", type=float, default=0.50)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    report = build_event_level_edge_feasibility(
        predictions_path=Path(args.predictions),
        costs_config=Path(args.costs_config),
        json_out=Path(args.json_out),
        md_out=Path(args.md_out) if args.md_out else None,
        run=args.run,
        policy=PolicyConfig(
            long_short_margin=args.long_short_margin,
            min_fade_success=args.min_fade_success,
            max_trend_danger=args.max_trend_danger,
        ),
    )
    overall = report["event_metrics"]["overall"]
    decision = report["decision"]
    print(
        "PASS event-level edge feasibility: "
        f"events={report['non_overlapping_event_count']} "
        f"skipped_overlap={report['skipped_overlapping_rows']} "
        f"net_dollars={overall['net_return_dollars']} "
        f"decision={decision['decision']} "
        f"report={_relative_path(Path(args.json_out))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
