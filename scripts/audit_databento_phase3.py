#!/usr/bin/env python3
"""Phase 3 sampled OHLCV-from-trades reconstruction audit."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from scripts.audit_databento_common import (
    Blocker,
    PhaseResult,
    blocker_from_mutation,
    compare_source_manifests,
    phase_gate_path,
    rel,
    repo_path,
    source_manifest_rows,
    utc_now,
    write_csv,
    write_json,
    write_phase_outputs,
    write_source_manifest,
    write_text,
)
from scripts.audit_databento_phase2 import read_dbn_sample, timestamp_series


PHASE = "phase3"
DEFAULT_MAX_ROWS_PER_FILE = 1_000
PHASE3_SCHEMAS = {"ohlcv-1m", "trades"}


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def unique_sorted(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value) not in {"", "None", "nan"}})


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def interval_days(row: dict[str, Any]) -> int:
    start = pd.to_datetime(row.get("date_start", ""), errors="coerce")
    end = pd.to_datetime(row.get("date_end", ""), errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return 0
    return max(int((end - start).days), 0)


def load_overlap_guard_rows(disposition_path: Path, inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[str]]:
    inventory_by_path = {str(row["path"]): row for row in inventory}
    rows: list[dict[str, Any]] = []
    excluded: set[str] = set()
    for row in read_csv_rows(disposition_path):
        if row.get("blocker_id") != "phase1_overlapping_archive_interval":
            continue
        primary = str(row.get("primary_file", ""))
        paired = str(row.get("paired_file", ""))
        schema = str(row.get("schema", ""))
        in_phase3_scope = schema in PHASE3_SCHEMAS
        action = "outside_phase3_scope"
        canonical = paired
        excluded_path = ""
        if in_phase3_scope:
            primary_row = inventory_by_path.get(primary, {})
            paired_row = inventory_by_path.get(paired, {})
            primary_days = interval_days(primary_row)
            paired_days = interval_days(paired_row)
            if paired and paired_days >= primary_days:
                action = "exclude_overlap_file_keep_wider_interval"
                excluded_path = primary
                canonical = paired
                excluded.add(primary)
            elif primary:
                action = "exclude_paired_file_keep_primary_interval"
                excluded_path = paired
                canonical = primary
                excluded.add(paired)
            else:
                action = "guard_failed_missing_overlap_path"
        rows.append(
            {
                "schema": schema,
                "market": row.get("market", ""),
                "year": row.get("year", ""),
                "primary_file": primary,
                "primary_interval": row.get("primary_interval", ""),
                "paired_file": paired,
                "paired_interval": row.get("paired_interval", ""),
                "in_phase3_scope": in_phase3_scope,
                "rule": "file_level_keep_wider_or_earlier_interval",
                "action": action,
                "canonical_file": canonical,
                "excluded_file": excluded_path,
                "evidence": row.get("evidence", ""),
            }
        )
    return rows, {path for path in excluded if path}


def intervals_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_start = pd.to_datetime(left.get("date_start", ""), errors="coerce")
    left_end = pd.to_datetime(left.get("date_end", ""), errors="coerce")
    right_start = pd.to_datetime(right.get("date_start", ""), errors="coerce")
    right_end = pd.to_datetime(right.get("date_end", ""), errors="coerce")
    if pd.isna(left_start) or pd.isna(left_end) or pd.isna(right_start) or pd.isna(right_end):
        return False
    return max(left_start, right_start) < min(left_end, right_end)


def build_coverage(inventory: list[dict[str, Any]], excluded_paths: set[str]) -> list[dict[str, Any]]:
    trades = [
        row
        for row in inventory
        if row.get("schema") == "trades" and str(row.get("path")) not in excluded_paths
    ]
    ohlcv = [
        row
        for row in inventory
        if row.get("schema") == "ohlcv-1m" and str(row.get("path")) not in excluded_paths
    ]
    ohlcv_by_market_year: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in ohlcv:
        ohlcv_by_market_year.setdefault((str(row.get("market")), str(row.get("year"))), []).append(row)

    rows: list[dict[str, Any]] = []
    for trade in trades:
        for bar in ohlcv_by_market_year.get((str(trade.get("market")), str(trade.get("year"))), []):
            if not intervals_overlap(trade, bar):
                continue
            overlap_start = max(pd.to_datetime(trade["date_start"]), pd.to_datetime(bar["date_start"]))
            overlap_end = min(pd.to_datetime(trade["date_end"]), pd.to_datetime(bar["date_end"]))
            rows.append(
                {
                    "market": trade.get("market", ""),
                    "year": trade.get("year", ""),
                    "trade_file": trade.get("path", ""),
                    "ohlcv_file": bar.get("path", ""),
                    "trade_interval": f"{trade.get('date_start', '')}_{trade.get('date_end', '')}",
                    "ohlcv_interval": f"{bar.get('date_start', '')}_{bar.get('date_end', '')}",
                    "overlap_start": overlap_start.date().isoformat(),
                    "overlap_end": overlap_end.date().isoformat(),
                    "selected_for_sample": False,
                    "selection_reason": "",
                }
            )
    return sorted(rows, key=lambda row: (row["market"], row["year"], row["trade_file"], row["ohlcv_file"]))


def choose_sample_pairs(coverage_rows: list[dict[str, Any]], args: Any) -> list[dict[str, Any]]:
    markets_filter = {str(value) for value in (args.markets or [])}
    years_filter = {str(value) for value in (args.years or [])}
    filtered = [
        row
        for row in coverage_rows
        if (not markets_filter or str(row["market"]) in markets_filter)
        and (not years_filter or str(row["year"]) in years_filter)
    ]
    by_market: dict[str, list[dict[str, Any]]] = {}
    for row in filtered:
        by_market.setdefault(str(row["market"]), []).append(row)

    selected: list[dict[str, Any]] = []
    for market in sorted(by_market):
        rows = sorted(by_market[market], key=lambda row: (int(row["year"]), row["overlap_end"], row["trade_file"], row["ohlcv_file"]))
        if rows:
            item = dict(rows[-1])
            item["selected_for_sample"] = True
            item["selection_reason"] = "latest_overlap_per_market"
            selected.append(item)
    if args.max_files is not None:
        selected = selected[: max(0, int(args.max_files) // 2)]
    return selected


def prepare_trades(frame: pd.DataFrame, market: str, source_path: str) -> tuple[pd.DataFrame, int]:
    ts, _ = timestamp_series(frame)
    if "instrument_id" not in frame.columns:
        return pd.DataFrame(), len(frame)
    prepared = pd.DataFrame(
        {
            "market": market,
            "source_trade_file": source_path,
            "instrument_id": frame["instrument_id"],
            "ts_event": ts,
            "price": numeric(frame, "price"),
            "size": numeric(frame, "size"),
        }
    )
    invalid = int(
        prepared["instrument_id"].isna().sum()
        + prepared["ts_event"].isna().sum()
        + prepared["price"].isna().sum()
        + prepared["size"].isna().sum()
    )
    prepared = prepared.dropna(subset=["instrument_id", "ts_event", "price", "size"])
    prepared = prepared[(prepared["price"] > 0) & (prepared["size"] > 0)].copy()
    prepared["minute"] = prepared["ts_event"].dt.floor("min")
    return prepared.sort_values(["instrument_id", "ts_event"]), invalid


def drop_sample_edge_minutes(trades: pd.DataFrame) -> tuple[pd.DataFrame, int, str]:
    """Remove potentially incomplete first/last minutes from count-limited trade samples."""
    guarded, guard_rows = apply_complete_minute_guard(trades, "", "")
    excluded = sum(int(row["trade_rows_excluded"]) for row in guard_rows)
    reason = "empty_trade_sample" if trades.empty else "dropped_first_last_observed_trade_minute_per_market_instrument"
    return guarded, excluded, reason


def apply_complete_minute_guard(trades: pd.DataFrame, trade_file: str, ohlcv_file: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Drop sample-edge minutes unless full-minute trade coverage is proven."""
    if trades.empty:
        return trades, []

    keep = pd.Series(True, index=trades.index)
    guard_rows: list[dict[str, Any]] = []
    for _, group in trades.groupby(["market", "instrument_id"], sort=False):
        minutes = group["minute"].dropna()
        if minutes.empty:
            continue
        first_minute = minutes.min()
        last_minute = minutes.max()
        edge_minutes = [first_minute] if first_minute == last_minute else [first_minute, last_minute]
        for edge_minute in edge_minutes:
            minute_rows = group[group["minute"] == edge_minute]
            keep.loc[minute_rows.index] = False
            if first_minute == last_minute:
                edge_position = "first_and_last_sample_minute"
                sample_boundary = "start_and_end"
            elif edge_minute == first_minute:
                edge_position = "first_sample_minute"
                sample_boundary = "start"
            else:
                edge_position = "last_sample_minute"
                sample_boundary = "end"
            guard_rows.append(
                {
                    "market": str(minute_rows["market"].iloc[0]),
                    "instrument_id": str(minute_rows["instrument_id"].iloc[0]),
                    "edge_minute": edge_minute.isoformat() if hasattr(edge_minute, "isoformat") else str(edge_minute),
                    "edge_position": edge_position,
                    "sample_boundary": sample_boundary,
                    "trade_rows_excluded": len(minute_rows),
                    "edge_bars_excluded": 1,
                    "full_minute_coverage_proven": False,
                    "action": "excluded_from_comparison",
                    "reason": "sample_boundary_minute_may_be_partial",
                    "trade_file": trade_file,
                    "ohlcv_file": ohlcv_file,
                }
            )

    return trades.loc[keep].copy(), guard_rows


def reconstruct_bars(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["market", "instrument_id", "ts_event", "open", "high", "low", "close", "volume", "trade_count", "source_trade_file"])
    grouped = trades.groupby(["market", "instrument_id", "minute"], sort=True)
    bars = grouped.agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
        trade_count=("price", "size"),
        source_trade_file=("source_trade_file", "first"),
    ).reset_index()
    return bars.rename(columns={"minute": "ts_event"})


def prepare_ohlcv(frame: pd.DataFrame, market: str, source_path: str) -> tuple[pd.DataFrame, int]:
    ts, _ = timestamp_series(frame)
    required = ["instrument_id", "open", "high", "low", "close", "volume"]
    missing_required = [column for column in required if column not in frame.columns]
    if missing_required:
        return pd.DataFrame(), len(frame)
    prepared = pd.DataFrame(
        {
            "market": market,
            "source_ohlcv_file": source_path,
            "instrument_id": frame["instrument_id"],
            "ts_event": ts,
            "open": numeric(frame, "open"),
            "high": numeric(frame, "high"),
            "low": numeric(frame, "low"),
            "close": numeric(frame, "close"),
            "volume": numeric(frame, "volume"),
        }
    )
    invalid = int(prepared[["instrument_id", "ts_event", "open", "high", "low", "close", "volume"]].isna().sum().sum())
    prepared = prepared.dropna(subset=["instrument_id", "ts_event", "open", "high", "low", "close", "volume"])
    return prepared.drop_duplicates(subset=["market", "instrument_id", "ts_event"]), invalid


def compare_pair(pair: dict[str, Any], trades_frame: pd.DataFrame, ohlcv_frame: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
    market = str(pair["market"])
    prepared_trades, invalid_trades = prepare_trades(trades_frame, market, str(pair["trade_file"]))
    guarded_trades, guard_rows = apply_complete_minute_guard(prepared_trades, str(pair["trade_file"]), str(pair["ohlcv_file"]))
    sample_edge_rows_excluded = sum(int(row["trade_rows_excluded"]) for row in guard_rows)
    sample_edge_minutes_excluded = len(guard_rows)
    sample_edge_bars_excluded = sum(int(row["edge_bars_excluded"]) for row in guard_rows)
    sample_edge_guard = "complete_minute_guard_applied"
    bars = reconstruct_bars(guarded_trades)
    raw, invalid_ohlcv = prepare_ohlcv(ohlcv_frame, market, str(pair["ohlcv_file"]))

    reco_out = [dict(row._asdict()) for row in bars.itertuples(index=False)]
    metrics = {
        "invalid_trade_rows": invalid_trades,
        "invalid_ohlcv_rows": invalid_ohlcv,
        "sample_edge_trade_rows_excluded": sample_edge_rows_excluded,
        "edge_minutes_excluded": sample_edge_minutes_excluded,
        "edge_bars_excluded": sample_edge_bars_excluded,
        "reconstructed_bars": len(bars),
        "raw_ohlcv_bars": len(raw),
        "matched_bars": 0,
        "mismatched_bars": 0,
        "missing_ohlcv_where_trades_exist": 0,
        "ohlcv_bars_with_no_matching_trades": 0,
    }
    if bars.empty or raw.empty:
        return reco_out, [], metrics | {"sample_edge_guard": sample_edge_guard}, [], guard_rows

    trade_min = bars["ts_event"].min()
    trade_max = bars["ts_event"].max()
    raw_in_window = raw[(raw["ts_event"] >= trade_min) & (raw["ts_event"] <= trade_max)].copy()

    keys = ["market", "instrument_id", "ts_event"]
    left = bars.set_index(keys)
    right = raw_in_window.set_index(keys)
    joined = left.join(right, how="outer", lsuffix="_reconstructed", rsuffix="_databento")
    examples: list[dict[str, Any]] = []
    mismatch_rows: list[dict[str, Any]] = []
    for key, row in joined.iterrows():
        market_key, instrument_id, ts_event = key
        has_reco = pd.notna(row.get("open_reconstructed"))
        has_raw = pd.notna(row.get("open_databento"))
        status = "matched"
        mismatches: list[str] = []
        if has_reco and not has_raw:
            status = "missing_ohlcv_where_trades_exist"
            metrics["missing_ohlcv_where_trades_exist"] += 1
        elif has_raw and not has_reco:
            status = "ohlcv_bar_with_no_matching_trades"
            metrics["ohlcv_bars_with_no_matching_trades"] += 1
        else:
            for column in ("open", "high", "low", "close", "volume"):
                left_value = float(row.get(f"{column}_reconstructed"))
                right_value = float(row.get(f"{column}_databento"))
                tolerance = max(1e-9, abs(right_value) * 1e-9)
                if abs(left_value - right_value) > tolerance:
                    mismatches.append(column)
            if mismatches:
                status = "mismatch"
                metrics["mismatched_bars"] += 1
            else:
                metrics["matched_bars"] += 1
        output = {
            "market": market_key,
            "instrument_id": instrument_id,
            "ts_event": ts_event.isoformat() if hasattr(ts_event, "isoformat") else str(ts_event),
            "status": status,
            "mismatch_fields": "|".join(mismatches),
            "open_reconstructed": row.get("open_reconstructed", ""),
            "high_reconstructed": row.get("high_reconstructed", ""),
            "low_reconstructed": row.get("low_reconstructed", ""),
            "close_reconstructed": row.get("close_reconstructed", ""),
            "volume_reconstructed": row.get("volume_reconstructed", ""),
            "open_databento": row.get("open_databento", ""),
            "high_databento": row.get("high_databento", ""),
            "low_databento": row.get("low_databento", ""),
            "close_databento": row.get("close_databento", ""),
            "volume_databento": row.get("volume_databento", ""),
            "trade_file": pair["trade_file"],
            "ohlcv_file": pair["ohlcv_file"],
        }
        if status != "matched":
            mismatch_rows.append(output)
        if len(examples) < 200 and (status != "matched" or metrics["matched_bars"] <= 25):
            examples.append(output)
    return reco_out, examples + mismatch_rows[:0], metrics | {"mismatch_rows_list_len": len(mismatch_rows), "sample_edge_guard": sample_edge_guard}, mismatch_rows, guard_rows


def blockers_from_summary(summary: dict[str, Any], mutation_check: dict[str, Any]) -> list[Blocker]:
    blockers = blocker_from_mutation(PHASE, mutation_check)
    if summary["overlap_guard_status"] != "pass":
        blockers.append(Blocker("Severe", PHASE, "overlap guard failed", "overlap_guard_status=fail", "Stop before reading overlap-risk records."))
    if int(summary["unreadable_selected_files"]) > 0:
        blockers.append(Blocker("Severe", PHASE, "unreadable selected Phase 3 files", f"unreadable_selected_files={summary['unreadable_selected_files']}", "Stop before trusting reconstruction."))
    compared = int(summary["matched_bars"]) + int(summary["mismatched_bars"])
    if compared >= 20 and int(summary["mismatched_bars"]) / max(compared, 1) >= 0.25:
        blockers.append(Blocker("Severe", PHASE, "systematic OHLCV-from-trades mismatch", f"mismatched_bars={summary['mismatched_bars']} compared_bars={compared}", "Stop before modeling."))
    elif int(summary["mismatched_bars"]) > 0:
        blockers.append(Blocker("Medium", PHASE, "sampled OHLCV-from-trades mismatches", f"mismatched_bars={summary['mismatched_bars']}", "Review mismatch examples before broader use."))
    if int(summary["missing_ohlcv_where_trades_exist"]) > 0:
        blockers.append(Blocker("Medium", PHASE, "missing OHLCV bars where sampled trades exist", f"missing_ohlcv_where_trades_exist={summary['missing_ohlcv_where_trades_exist']}", "Review before full reconstruction."))
    if int(summary["ohlcv_bars_with_no_matching_trades"]) > 0:
        blockers.append(Blocker("Low", PHASE, "sampled OHLCV bars without matching sampled trades", f"ohlcv_bars_with_no_matching_trades={summary['ohlcv_bars_with_no_matching_trades']}", "May reflect sample-window limits; review examples."))
    if int(summary["overlap_risk_files_excluded"]) > 0:
        blockers.append(Blocker("Low", PHASE, "overlap-risk files excluded by guard", f"excluded={summary['overlap_risk_files_excluded']}", "Keep guard for later phases."))
    blockers.append(Blocker("Low", PHASE, "status KE 2013 caveat carried", "accepted_with_caveat from Phase 2 disposition", "Keep visible for status-dependent modeling gates."))
    return blockers


def render_report(summary: dict[str, Any], blockers: list[Blocker]) -> str:
    lines = [
        "# Phase 3 OHLCV-From-Trades Sample Report",
        "",
        f"- Status: `{summary['status']}`",
        f"- Complete-minute guard status: `{summary['complete_minute_guard_status']}`",
        f"- Edge minutes excluded: {summary['edge_minutes_excluded']}",
        f"- Edge bars excluded: {summary['edge_bars_excluded']}",
        f"- Overlap guard status: `{summary['overlap_guard_status']}`",
        f"- Overlap-risk files excluded: {summary['overlap_risk_files_excluded']}",
        f"- Overlap-risk rows deduplicated: {summary['overlap_risk_rows_deduplicated']}",
        f"- Overlap markets: {summary['overlap_markets_count']} / {', '.join(summary['overlap_markets'])}",
        f"- Overlap date range: {summary['overlap_date_range']}",
        f"- Sample trade rows scanned: {summary['sample_trade_rows_scanned']}",
        f"- Sample edge trade rows excluded: {summary['sample_edge_trade_rows_excluded']}",
        f"- Sample raw OHLCV bars checked: {summary['sample_raw_ohlcv_bars_checked']}",
        f"- Reconstructed OHLCV bars: {summary['reconstructed_ohlcv_bars']}",
        f"- Matched bars: {summary['matched_bars']}",
        f"- Mismatched bars: {summary['mismatched_bars']}",
        "",
        "## Guard Rule",
        "",
        "The Phase 3 sample uses file-level duplicate handling: for overlapping archive pairs, keep the wider or earlier interval file and exclude the shorter overlap file before reading records.",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- `{blocker.severity}`: {blocker.issue} | {blocker.evidence}" for blocker in blockers)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def run_phase3(args: Any) -> dict[str, Any]:
    if not args.sample:
        raise SystemExit("Phase 3 must be run with --sample for this sampled reconstruction audit")
    if not args.reconstruct_ohlcv_from_trades:
        raise SystemExit("Phase 3 requires --reconstruct-ohlcv-from-trades")
    if args.full or args.allow_full_scan:
        raise SystemExit("Phase 3 sampled audit must not use --full or --allow-full-scan")

    started = utc_now()
    output_dir = repo_path(args.output_dir)
    phase_dir = output_dir / "phase3_ohlcv_reconstruction"
    state_dir = output_dir / "state"
    phase2_gate = json.loads((output_dir / "phase2_raw_validity" / "phase2_readiness_gate.json").read_text(encoding="utf-8"))
    if int(phase2_gate.get("severe_count", 0)) > 0:
        blockers = [Blocker("Severe", PHASE, "Phase 2 severe blockers present", rel(output_dir / "phase2_raw_validity" / "phase2_readiness_gate.json"), "Stop Phase 3.")]
        result = PhaseResult(PHASE, started, utc_now(), [], blockers, "not_applicable", {}, phase_dir / "phase3_readiness_gate.json", phase_dir / "blockers.csv")
        return write_phase_outputs(result)

    inventory = read_csv_rows(output_dir / "phase1_raw_inventory" / "inventory.csv")
    guard_rows, excluded_paths = load_overlap_guard_rows(output_dir / "phase2_raw_validity" / "blocker_disposition.csv", inventory)
    phase3_excluded = {
        row["excluded_file"]
        for row in guard_rows
        if row.get("in_phase3_scope") is True and row.get("excluded_file")
    }
    overlap_guard_status = "pass" if guard_rows and not any(row["action"].startswith("guard_failed") for row in guard_rows) else "fail"

    before = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    write_source_manifest(state_dir / "source_manifest_before.csv", before)

    coverage_rows = build_coverage(inventory, excluded_paths)
    selected_pairs = choose_sample_pairs(coverage_rows, args)
    selected_keys = {(row["trade_file"], row["ohlcv_file"]) for row in selected_pairs}
    for row in coverage_rows:
        if (row["trade_file"], row["ohlcv_file"]) in selected_keys:
            row["selected_for_sample"] = True
            row["selection_reason"] = "latest_overlap_per_market"

    max_rows = int(args.max_rows or DEFAULT_MAX_ROWS_PER_FILE)
    reconstruction_rows: list[dict[str, Any]] = []
    example_rows: list[dict[str, Any]] = []
    mismatch_rows: list[dict[str, Any]] = []
    complete_minute_guard_rows: list[dict[str, Any]] = []
    sample_trade_rows = 0
    sample_ohlcv_rows = 0
    unreadable_selected_files = 0
    invalid_mapping_rows = 0
    reconstructed_count = 0
    matched_count = 0
    mismatched_count = 0
    missing_ohlcv_count = 0
    raw_without_trade_count = 0
    sample_edge_trade_rows_excluded = 0
    edge_minutes_excluded = 0
    edge_bars_excluded = 0

    if overlap_guard_status == "pass":
        for pair in selected_pairs:
            trade_frame, trade_error = read_dbn_sample(repo_path(pair["trade_file"]), "trades", max_rows)
            ohlcv_frame, ohlcv_error = read_dbn_sample(repo_path(pair["ohlcv_file"]), "ohlcv-1m", max_rows)
            if trade_frame is None or ohlcv_frame is None:
                unreadable_selected_files += int(trade_frame is None) + int(ohlcv_frame is None)
                mismatch_rows.append(
                    {
                        "market": pair["market"],
                        "instrument_id": "",
                        "ts_event": "",
                        "status": "read_error",
                        "mismatch_fields": "",
                        "trade_file": pair["trade_file"],
                        "ohlcv_file": pair["ohlcv_file"],
                        "trade_error": trade_error,
                        "ohlcv_error": ohlcv_error,
                    }
                )
                continue
            sample_trade_rows += len(trade_frame)
            sample_ohlcv_rows += len(ohlcv_frame)
            reco, examples, metrics, mismatches, guard_rows_for_pair = compare_pair(pair, trade_frame, ohlcv_frame)
            reconstruction_rows.extend(reco)
            example_rows.extend(examples)
            mismatch_rows.extend(mismatches)
            complete_minute_guard_rows.extend(guard_rows_for_pair)
            invalid_mapping_rows += int(metrics["invalid_trade_rows"]) + int(metrics["invalid_ohlcv_rows"])
            reconstructed_count += int(metrics["reconstructed_bars"])
            matched_count += int(metrics["matched_bars"])
            mismatched_count += int(metrics["mismatched_bars"])
            missing_ohlcv_count += int(metrics["missing_ohlcv_where_trades_exist"])
            raw_without_trade_count += int(metrics["ohlcv_bars_with_no_matching_trades"])
            sample_edge_trade_rows_excluded += int(metrics["sample_edge_trade_rows_excluded"])
            edge_minutes_excluded += int(metrics["edge_minutes_excluded"])
            edge_bars_excluded += int(metrics["edge_bars_excluded"])

    after = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    write_source_manifest(state_dir / "source_manifest_after.csv", after)
    mutation_check = compare_source_manifests(before, after)
    write_json(state_dir / "source_mutation_check.json", mutation_check)

    overlap_dates = [row["overlap_start"] for row in coverage_rows] + [row["overlap_end"] for row in coverage_rows]
    summary = {
        "overlap_guard_status": overlap_guard_status,
        "overlap_risk_files_excluded": len(phase3_excluded),
        "overlap_risk_rows_deduplicated": 0,
        "overlap_markets_count": len({row["market"] for row in coverage_rows}),
        "overlap_markets": unique_sorted(row["market"] for row in coverage_rows),
        "overlap_date_range": f"{min(overlap_dates)} to {max(overlap_dates)}" if overlap_dates else "",
        "sample_pairs": len(selected_pairs),
        "complete_minute_guard_status": "pass" if overlap_guard_status == "pass" else "not_applicable",
        "sample_trade_rows_scanned": sample_trade_rows,
        "sample_edge_trade_rows_excluded": sample_edge_trade_rows_excluded,
        "edge_minutes_excluded": edge_minutes_excluded,
        "edge_bars_excluded": edge_bars_excluded,
        "sample_raw_ohlcv_bars_checked": sample_ohlcv_rows,
        "reconstructed_ohlcv_bars": reconstructed_count,
        "matched_bars": matched_count,
        "mismatched_bars": mismatched_count,
        "missing_ohlcv_where_trades_exist": missing_ohlcv_count,
        "ohlcv_bars_with_no_matching_trades": raw_without_trade_count,
        "instrument_mapping_failures": invalid_mapping_rows,
        "unreadable_selected_files": unreadable_selected_files,
        "source_mutation_check": mutation_check["source_mutation_check"],
    }
    blockers = blockers_from_summary(summary, mutation_check)
    severe = sum(1 for blocker in blockers if blocker.severity == "Severe")
    medium = sum(1 for blocker in blockers if blocker.severity == "Medium")
    low = sum(1 for blocker in blockers if blocker.severity == "Low")
    summary.update(
        {
            "status": "fail" if severe else "pass_with_medium_blockers" if medium else "pass",
            "severe_issue_count": severe,
            "medium_issue_count": medium,
            "low_issue_count": low,
        }
    )

    reports = [
        phase_dir / "overlap_guard.csv",
        phase_dir / "overlap_coverage.csv",
        phase_dir / "ohlcv_from_trades_reconstruction.csv",
        phase_dir / "ohlcv_from_trades_examples.csv",
        phase_dir / "ohlcv_from_trades_mismatches.csv",
        phase_dir / "complete_minute_guard.csv",
        phase_dir / "ohlcv_from_trades_summary.json",
        phase_dir / "blockers.csv",
        phase_dir / "phase3_readiness_gate.json",
        phase_dir / "phase3_report.md",
    ]
    write_csv(phase_dir / "overlap_guard.csv", list(guard_rows[0].keys()) if guard_rows else ["schema"], guard_rows)
    write_csv(phase_dir / "overlap_coverage.csv", list(coverage_rows[0].keys()) if coverage_rows else ["market"], coverage_rows)
    write_csv(
        phase_dir / "ohlcv_from_trades_reconstruction.csv",
        ["market", "instrument_id", "ts_event", "open", "high", "low", "close", "volume", "trade_count", "source_trade_file"],
        reconstruction_rows,
    )
    write_csv(
        phase_dir / "ohlcv_from_trades_examples.csv",
        ["market", "instrument_id", "ts_event", "status", "mismatch_fields", "open_reconstructed", "high_reconstructed", "low_reconstructed", "close_reconstructed", "volume_reconstructed", "open_databento", "high_databento", "low_databento", "close_databento", "volume_databento", "trade_file", "ohlcv_file"],
        example_rows[:500],
    )
    write_csv(
        phase_dir / "ohlcv_from_trades_mismatches.csv",
        ["market", "instrument_id", "ts_event", "status", "mismatch_fields", "open_reconstructed", "high_reconstructed", "low_reconstructed", "close_reconstructed", "volume_reconstructed", "open_databento", "high_databento", "low_databento", "close_databento", "volume_databento", "trade_file", "ohlcv_file", "trade_error", "ohlcv_error"],
        mismatch_rows,
    )
    write_csv(
        phase_dir / "complete_minute_guard.csv",
        ["market", "instrument_id", "edge_minute", "edge_position", "sample_boundary", "trade_rows_excluded", "edge_bars_excluded", "full_minute_coverage_proven", "action", "reason", "trade_file", "ohlcv_file"],
        complete_minute_guard_rows,
    )
    write_json(phase_dir / "ohlcv_from_trades_summary.json", summary)

    result = PhaseResult(
        phase=PHASE,
        started_at=started,
        finished_at=utc_now(),
        reports=[rel(path) for path in reports],
        blockers=blockers,
        source_mutation_check=str(mutation_check["source_mutation_check"]),
        summary=summary,
        gate_path=phase_gate_path(Path(args.output_dir), 3, "phase3_readiness_gate.json"),
        blockers_csv=phase_dir / "blockers.csv",
    )
    write_text(phase_dir / "phase3_report.md", render_report(summary, blockers))
    gate = write_phase_outputs(result)
    state = {
        "last_phase": PHASE,
        "last_gate": rel(result.gate_path),
        "updated_at": utc_now(),
        "data_root": str(args.data_root),
        "output_dir": str(args.output_dir),
        "sample": bool(args.sample),
        "full": bool(args.full),
        "allow_full_scan": bool(args.allow_full_scan),
        "gate": gate,
    }
    write_json(state_dir / "audit_state.json", state)
    print(
        "phase3 status={status} severe={severe} medium={medium} low={low} overlap_guard={guard} sample_trade_rows={trade_rows} reconstructed_bars={bars} mismatches={mismatches} blockers_csv={blockers}".format(
            status=gate["status"],
            severe=gate["severe_count"],
            medium=gate["medium_count"],
            low=gate["low_count"],
            guard=summary["overlap_guard_status"],
            trade_rows=summary["sample_trade_rows_scanned"],
            bars=summary["reconstructed_ohlcv_bars"],
            mismatches=summary["mismatched_bars"],
            blockers=gate["blockers_csv"],
        )
    )
    return gate
