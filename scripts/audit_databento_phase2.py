#!/usr/bin/env python3
"""Phase 2 sampled raw DBN source validity audit."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
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


PHASE = "phase2"
CORE_SCHEMAS = ("ohlcv-1m", "definition", "statistics", "status", "trades")
DEFAULT_MAX_ROWS_PER_FILE = 1_000


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def unique_sorted(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value) not in {"", "None", "nan"}})


def choose_sample(inventory: list[dict[str, Any]], anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path = {str(row["path"]): row for row in inventory}
    selected: dict[str, dict[str, Any]] = {}

    def add(path: str, reason: str) -> None:
        row = by_path.get(path)
        if row is None:
            return
        item = dict(row)
        existing = selected.get(path)
        if existing:
            existing["sample_reason"] = existing["sample_reason"] + "|" + reason
        else:
            item["sample_reason"] = reason
            selected[path] = item

    core_rows = [row for row in inventory if row["schema"] in CORE_SCHEMAS]
    for schema in CORE_SCHEMAS:
        rows = sorted([row for row in core_rows if row["schema"] == schema], key=lambda row: (row["year"], row["market"], row["path"]))
        for year in ("2010", "2014", "2018", "2022", "2026"):
            matches = [row for row in rows if row["year"] == year]
            if matches:
                add(str(matches[0]["path"]), f"schema_year_representative:{schema}:{year}")
        for market in sorted({str(row["market"]) for row in rows}):
            matches = sorted([row for row in rows if row["market"] == market], key=lambda row: (row["year"], row["path"]))
            if matches:
                add(str(matches[-1]["path"]), f"schema_market_representative:{schema}:{market}")

    for row in anomalies:
        if row.get("type") in {"overlapping_archive_interval", "tiny_file"} and row.get("path"):
            add(str(row["path"]), f"phase1_anomaly:{row['type']}")

    for row in core_rows:
        if row["schema"] == "status" and row["market"] == "KE" and row["year"] in {"2014", "2015"}:
            add(str(row["path"]), "nearby_missing_status_KE_2013")

    return sorted(selected.values(), key=lambda row: (row["schema"], row["market"], row["year"], row["path"]))


def manifest_schema(path: Path) -> str:
    manifest_path = path.with_name(f"{path.name}.manifest.json")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(payload.get("schema", "")) if isinstance(payload, dict) else ""


def to_frames(value: Any, max_rows: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    remaining = max_rows
    if isinstance(value, pd.DataFrame):
        return value.head(max_rows).copy()
    for frame in value:
        if remaining <= 0:
            break
        if not isinstance(frame, pd.DataFrame):
            continue
        frames.append(frame.head(remaining).copy())
        remaining -= min(len(frame), remaining)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=False).head(max_rows)


def read_dbn_sample(path: Path, schema: str, max_rows: int) -> tuple[pd.DataFrame | None, str]:
    try:
        import databento as db
    except Exception as exc:
        return None, f"databento import failed: {exc}"
    attempts = [
        {"count": max_rows, "pretty_ts": False, "map_symbols": False, "schema": schema, "price_type": "float"},
        {"count": max_rows, "pretty_ts": False, "map_symbols": False, "schema": schema},
        {"count": max_rows, "pretty_ts": False, "map_symbols": False},
        {"pretty_ts": False, "map_symbols": False},
    ]
    errors: list[str] = []
    for kwargs in attempts:
        try:
            store = db.DBNStore.from_file(path)
            frame = to_frames(store.to_df(**kwargs), max_rows)
            return frame, ""
        except Exception as exc:
            errors.append(str(exc))
    return None, " | ".join(errors[:2])


def timestamp_series(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    for column in ("ts_event", "ts_recv", "timestamp", "datetime", "time"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce"), column
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index), "index"
    index_name = str(frame.index.name or "")
    if index_name in {"ts_event", "ts_recv", "timestamp", "datetime", "time"}:
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index), f"index:{index_name}"
    return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]"), ""


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def column_list(frame: pd.DataFrame, pattern: str) -> list[str]:
    regex = re.compile(pattern, re.IGNORECASE)
    return [column for column in frame.columns if regex.search(str(column))]


def schema_row(sample: dict[str, Any], frame: pd.DataFrame | None, read_error: str) -> dict[str, Any]:
    path = repo_path(sample["path"])
    metadata_schema = manifest_schema(path)
    if frame is None:
        return {
            "path": sample["path"],
            "sample_reason": sample["sample_reason"],
            "read_status": "skipped",
            "skip_reason": read_error,
            "inferred_schema": sample["schema"],
            "dbn_metadata_schema": metadata_schema,
            "record_type": "",
            "fields": "",
            "dtypes": "",
            "timestamp_fields": "",
            "instrument_id_fields": "",
            "price_fields": "",
            "size_volume_fields": "",
            "status_statistic_action_fields": "",
            "missing_required_fields": "",
            "null_required_fields": "",
            "schema_mismatch": bool(metadata_schema and metadata_schema != sample["schema"]),
        }
    required = {
        "ohlcv-1m": ["open", "high", "low", "close", "volume", "instrument_id"],
        "trades": ["price", "size", "instrument_id"],
        "definition": ["instrument_id"],
        "statistics": ["instrument_id"],
        "status": ["instrument_id"],
    }.get(str(sample["schema"]), [])
    missing = [field for field in required if field not in frame.columns]
    nulls = [
        field
        for field in required
        if field in frame.columns and frame[field].isna().any()
    ]
    return {
        "path": sample["path"],
        "sample_reason": sample["sample_reason"],
        "read_status": "read",
        "skip_reason": "",
        "inferred_schema": sample["schema"],
        "dbn_metadata_schema": metadata_schema,
        "record_type": "|".join(str(value) for value in frame["rtype"].dropna().unique()[:10]) if "rtype" in frame.columns else "",
        "fields": "|".join(str(column) for column in frame.columns),
        "dtypes": "|".join(f"{column}:{dtype}" for column, dtype in frame.dtypes.items()),
        "timestamp_fields": "|".join(column_list(frame, r"^ts_|timestamp|datetime|time")),
        "instrument_id_fields": "|".join(column_list(frame, r"instrument_id|raw_instrument_id")),
        "price_fields": "|".join(column_list(frame, r"open|high|low|close|price|px")),
        "size_volume_fields": "|".join(column_list(frame, r"size|volume|qty")),
        "status_statistic_action_fields": "|".join(column_list(frame, r"status|stat|action|type")),
        "missing_required_fields": "|".join(missing),
        "null_required_fields": "|".join(nulls),
        "schema_mismatch": bool(metadata_schema and metadata_schema != sample["schema"]),
    }


def timestamp_row(sample: dict[str, Any], frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {
            "path": sample["path"],
            "schema": sample["schema"],
            "row_count": 0,
            "timestamp_field": "",
            "min_ts": "",
            "max_ts": "",
            "invalid_timestamp_count": 0,
            "out_of_order_count": 0,
            "negative_gap_count": 0,
            "duplicate_timestamp_count": 0,
            "minute_alignment_fail_count": 0,
            "schema_time_model": "bar" if sample["schema"] == "ohlcv-1m" else "event",
        }
    ts, field = timestamp_series(frame)
    diffs = ts.dropna().diff()
    minute_fail = 0
    if sample["schema"] == "ohlcv-1m":
        minute_fail = int((ts.dropna().dt.floor("min") != ts.dropna()).sum())
    return {
        "path": sample["path"],
        "schema": sample["schema"],
        "row_count": len(frame),
        "timestamp_field": field,
        "min_ts": ts.min().isoformat() if ts.notna().any() else "",
        "max_ts": ts.max().isoformat() if ts.notna().any() else "",
        "invalid_timestamp_count": int(ts.isna().sum()),
        "out_of_order_count": int((diffs < pd.Timedelta(0)).sum()),
        "negative_gap_count": int((diffs < pd.Timedelta(0)).sum()),
        "duplicate_timestamp_count": int(ts.duplicated().sum()),
        "minute_alignment_fail_count": minute_fail,
        "schema_time_model": "bar" if sample["schema"] == "ohlcv-1m" else "event",
    }


def ohlcv_row(sample: dict[str, Any], frame: pd.DataFrame | None) -> dict[str, Any]:
    base = {"path": sample["path"], "market": sample["market"], "year": sample["year"], "row_count": 0}
    if frame is None or frame.empty:
        return {**base, "status": "skipped", "invariant_failure_count": 0, "zero_price_count": 0, "huge_range_count": 0, "stale_close_run_count": 0, "duplicate_bar_count": 0}
    open_ = numeric(frame, "open")
    high = numeric(frame, "high")
    low = numeric(frame, "low")
    close = numeric(frame, "close")
    volume = numeric(frame, "volume")
    failure_count = int(
        open_.isna().sum()
        + high.isna().sum()
        + low.isna().sum()
        + close.isna().sum()
        + (open_ < 0).sum()
        + (high < 0).sum()
        + (low < 0).sum()
        + (close < 0).sum()
        + (high < low).sum()
        + ((open_ < low) | (open_ > high)).sum()
        + ((close < low) | (close > high)).sum()
        + (volume < 0).sum()
    )
    ts, _ = timestamp_series(frame)
    duplicate_cols = [column for column in ("instrument_id",) if column in frame.columns]
    dup_frame = frame.assign(_ts=ts)
    duplicate_count = int(dup_frame.duplicated(subset=duplicate_cols + ["_ts"]).sum()) if duplicate_cols else int(ts.duplicated().sum())
    ranges = (high - low).dropna()
    median_range = ranges[ranges > 0].median() if not ranges.empty else math.nan
    huge_range_count = int((ranges > median_range * 100).sum()) if pd.notna(median_range) and median_range > 0 else 0
    stale_close = int((close.diff().fillna(1) == 0).rolling(25).sum().fillna(0).ge(25).sum()) if not close.empty else 0
    return {
        **base,
        "status": "checked",
        "row_count": len(frame),
        "invariant_failure_count": failure_count,
        "zero_price_count": int(((open_ == 0) | (high == 0) | (low == 0) | (close == 0)).sum()),
        "huge_range_count": huge_range_count,
        "stale_close_run_count": stale_close,
        "duplicate_bar_count": duplicate_count,
        "volume_integer_like_failure_count": int(((volume.dropna() % 1) != 0).sum()) if not volume.empty else 0,
    }


def trades_row(sample: dict[str, Any], frame: pd.DataFrame | None) -> dict[str, Any]:
    base = {"path": sample["path"], "market": sample["market"], "year": sample["year"], "row_count": 0}
    if frame is None or frame.empty:
        return {**base, "status": "skipped", "sanity_failure_count": 0, "duplicate_trade_count": 0, "out_of_order_count": 0, "long_gap_count": 0}
    price = numeric(frame, "price")
    size = numeric(frame, "size")
    ts, _ = timestamp_series(frame)
    diffs = ts.dropna().diff()
    duplicate_cols = [column for column in ("instrument_id", "price", "size") if column in frame.columns]
    dup_frame = frame.assign(_ts=ts)
    duplicate_count = int(dup_frame.duplicated(subset=duplicate_cols + ["_ts"]).sum()) if duplicate_cols else 0
    return {
        **base,
        "status": "checked",
        "row_count": len(frame),
        "sanity_failure_count": int(price.isna().sum() + size.isna().sum() + (price <= 0).sum() + (size <= 0).sum()),
        "duplicate_trade_count": duplicate_count,
        "out_of_order_count": int((diffs < pd.Timedelta(0)).sum()),
        "long_gap_count": int((diffs > pd.Timedelta(hours=12)).sum()),
        "extreme_price_jump_count": int((price.pct_change().abs() > 0.5).sum()) if len(price.dropna()) > 1 else 0,
        "instrument_id_missing_count": int(frame["instrument_id"].isna().sum()) if "instrument_id" in frame.columns else len(frame),
    }


def definition_rows(sample: dict[str, Any], frame: pd.DataFrame | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base = {"path": sample["path"], "market": sample["market"], "year": sample["year"], "row_count": 0}
    if frame is None or frame.empty:
        return {**base, "status": "skipped", "instrument_id_missing_count": 0, "malformed_symbol_count": 0, "duplicate_definition_count": 0}, []
    symbol_col = "raw_symbol" if "raw_symbol" in frame.columns else "symbol" if "symbol" in frame.columns else ""
    symbols = frame[symbol_col].astype(str) if symbol_col else pd.Series([], dtype="object")
    malformed = int((~symbols.str.match(r"^[A-Z0-9]+[FGHJKMNQUVXZ]\d{1,2}$|^[A-Z0-9]+\.v\.\d+$", na=False)).sum()) if symbol_col else len(frame)
    roots = symbols.str.extract(r"^([A-Z0-9]+)", expand=False) if symbol_col else pd.Series([], dtype="object")
    contract_rows: list[dict[str, Any]] = []
    if symbol_col:
        month = symbols.str.extract(r"^[A-Z0-9]+([FGHJKMNQUVXZ])", expand=False).fillna("")
        grouped = pd.DataFrame({"root": roots, "contract_month": month}).value_counts().reset_index(name="definition_count")
        for item in grouped.itertuples(index=False):
            contract_rows.append({"path": sample["path"], "root": item.root, "year": sample["year"], "contract_month": item.contract_month, "definition_count": item.definition_count})
    return {
        **base,
        "status": "checked",
        "row_count": len(frame),
        "instrument_id_missing_count": int(frame["instrument_id"].isna().sum()) if "instrument_id" in frame.columns else len(frame),
        "malformed_symbol_count": malformed,
        "unexpected_root_count": int((roots.dropna() != str(sample["market"])).sum()) if not roots.empty else 0,
        "duplicate_definition_count": int(frame.duplicated(subset=[column for column in ("instrument_id", "raw_symbol") if column in frame.columns]).sum()),
    }, contract_rows


def generic_event_row(sample: dict[str, Any], frame: pd.DataFrame | None, *, schema: str) -> dict[str, Any]:
    base = {"path": sample["path"], "market": sample["market"], "year": sample["year"], "row_count": 0}
    if frame is None or frame.empty:
        return {**base, "status": "skipped", "instrument_id_missing_count": 0, "duplicate_event_count": 0, "unknown_type_count": 0}
    ts, _ = timestamp_series(frame)
    type_cols = column_list(frame, r"stat|status|action|type")
    subset = [column for column in ("instrument_id",) + tuple(type_cols[:1]) if column in frame.columns] + ["_ts"]
    dup_frame = frame.assign(_ts=ts)
    value_cols = column_list(frame, r"value|price|size|qty")
    negative_values = 0
    for column in value_cols:
        values = numeric(frame, column).dropna()
        negative_values += int((values < 0).sum())
    return {
        **base,
        "status": "checked",
        "row_count": len(frame),
        "schema": schema,
        "type_fields": "|".join(type_cols),
        "instrument_id_missing_count": int(frame["instrument_id"].isna().sum()) if "instrument_id" in frame.columns else len(frame),
        "duplicate_event_count": int(dup_frame.duplicated(subset=subset).sum()) if len(subset) > 1 else 0,
        "unknown_type_count": 0 if type_cols else len(frame),
        "negative_value_count": negative_values,
    }


def classify_phase1_followups(inventory: list[dict[str, Any]], anomalies: list[dict[str, Any]], sample_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    nearby_ke = [row for row in inventory if row["schema"] == "status" and row["market"] == "KE" and row["year"] in {"2014", "2015"}]
    rows.append(
        {
            "phase1_issue": "missing_expected_coverage",
            "item": "status KE 2013",
            "classification": "unresolved_true_missing_or_provider_unavailable",
            "evidence": f"nearby_status_files={len(nearby_ke)} missing_expected_coverage.csv",
            "carried_forward": True,
        }
    )
    overlap_paths = [str(row["path"]) for row in anomalies if row.get("type") == "overlapping_archive_interval"]
    rows.append(
        {
            "phase1_issue": "overlapping_archive_interval",
            "item": f"{len(overlap_paths)} overlapping intervals",
            "classification": "duplicate_source_risk_until_later_source_validity_review",
            "evidence": "inventory_anomalies.csv",
            "carried_forward": True,
        }
    )
    tiny_paths = [str(row["path"]) for row in anomalies if row.get("type") == "tiny_file"]
    unreadable_tiny = [path for path in tiny_paths if sample_results.get(path, {}).get("read_status") != "read"]
    rows.append(
        {
            "phase1_issue": "tiny_file",
            "item": f"{len(tiny_paths)} tiny files",
            "classification": "valid_sparse_files_in_sample" if not unreadable_tiny else "corrupt_or_unreadable_risk",
            "evidence": f"sampled_unreadable_tiny={len(unreadable_tiny)}",
            "carried_forward": bool(unreadable_tiny),
        }
    )
    rows.append(
        {
            "phase1_issue": "extra_ohlcv_schema",
            "item": "ohlcv-1d/1h/1s",
            "classification": "low_non_l0_extra_schema_not_interfering_with_l0_sample",
            "evidence": "inventory_summary.json",
            "carried_forward": False,
        }
    )
    return rows


def blockers_from_metrics(summary: dict[str, Any], followups: list[dict[str, Any]]) -> list[Blocker]:
    blockers: list[Blocker] = []
    severe_metrics = {
        "unreadable_files": "unreadable sampled files",
        "timestamp_failures": "timestamp failures",
        "ohlcv_invariant_failures": "OHLCV invariant failures",
        "trade_sanity_failures": "trade sanity failures",
    }
    for key, issue in severe_metrics.items():
        if int(summary.get(key, 0)) > 0:
            blockers.append(Blocker("Severe", PHASE, issue, f"{key}={summary[key]}", "Stop before later phases."))
    for row in followups:
        if str(row.get("carried_forward")) in {"True", "true", "1"}:
            blockers.append(Blocker("Medium", PHASE, f"phase1_{row['phase1_issue']}", str(row["evidence"]), "Resolve or explicitly accept before model-readiness."))
    blockers.append(Blocker("Low", PHASE, "phase1_extra_ohlcv_schema", "extra OHLCV schemas remain non-L0 and non-blocking", "Keep excluded from expected L0 handling."))
    return blockers


def render_report(summary: dict[str, Any], blockers: list[Blocker]) -> str:
    lines = [
        "# Phase 2 Raw Source Validity Sample Report",
        "",
        f"- Status: `{summary['status']}`",
        f"- Sample files scanned: {summary['sample_files_scanned']}",
        f"- Sample rows scanned: {summary['sample_rows_scanned']}",
        f"- Schemas audited: {', '.join(summary['schemas_audited'])}",
        f"- Markets sampled: {summary['markets_sampled_count']}",
        f"- Years sampled: {summary['years_sampled_count']}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- `{blocker.severity}`: {blocker.issue} | {blocker.evidence}" for blocker in blockers)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def run_phase2(args: Any) -> dict[str, Any]:
    if not args.sample:
        raise SystemExit("Phase 2 must be run with --sample for this sampled audit")
    if args.full or args.allow_full_scan:
        raise SystemExit("Phase 2 sampled audit must not use --full or --allow-full-scan")

    started = utc_now()
    output_dir = repo_path(args.output_dir)
    phase_dir = output_dir / "phase2_raw_validity"
    state_dir = output_dir / "state"
    inventory_path = output_dir / "phase1_raw_inventory" / "inventory.csv"
    anomalies_path = output_dir / "phase1_raw_inventory" / "inventory_anomalies.csv"
    phase1_gate = json.loads((output_dir / "phase1_raw_inventory" / "phase1_readiness_gate.json").read_text(encoding="utf-8"))
    if int(phase1_gate.get("severe_count", 0)) > 0:
        blockers = [Blocker("Severe", PHASE, "Phase 1 severe blockers present", rel(output_dir / "phase1_raw_inventory" / "phase1_readiness_gate.json"), "Stop Phase 2.")]
        result = PhaseResult(PHASE, started, utc_now(), [], blockers, "not_applicable", {}, phase_dir / "phase2_readiness_gate.json", phase_dir / "blockers.csv")
        return write_phase_outputs(result)

    before = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    write_source_manifest(state_dir / "source_manifest_before.csv", before)

    inventory = read_csv_rows(inventory_path)
    anomalies = read_csv_rows(anomalies_path)
    samples = choose_sample(inventory, anomalies)
    max_rows = int(args.max_rows or DEFAULT_MAX_ROWS_PER_FILE)

    schema_rows: list[dict[str, Any]] = []
    timestamp_rows: list[dict[str, Any]] = []
    ohlcv_rows: list[dict[str, Any]] = []
    trades_rows: list[dict[str, Any]] = []
    definition_audit_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []
    statistics_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    cross_rows: list[dict[str, Any]] = []
    sample_results: dict[str, dict[str, Any]] = {}
    sample_rows_scanned = 0

    for sample in samples:
        path = repo_path(sample["path"])
        frame, error = read_dbn_sample(path, str(sample["schema"]), max_rows)
        read_status = "read" if frame is not None else "skipped"
        row_count = int(len(frame)) if frame is not None else 0
        sample_rows_scanned += row_count
        sample_results[str(sample["path"])] = {"read_status": read_status, "row_count": row_count, "skip_reason": error}
        cross_rows.append(
            {
                "path": sample["path"],
                "schema": sample["schema"],
                "market": sample["market"],
                "year": sample["year"],
                "sample_reason": sample["sample_reason"],
                "read_status": read_status,
                "row_count": row_count,
                "skip_reason": error,
            }
        )
        schema_rows.append(schema_row(sample, frame, error))
        timestamp_rows.append(timestamp_row(sample, frame))
        if sample["schema"] == "ohlcv-1m":
            ohlcv_rows.append(ohlcv_row(sample, frame))
        elif sample["schema"] == "trades":
            trades_rows.append(trades_row(sample, frame))
        elif sample["schema"] == "definition":
            definition_row, coverage = definition_rows(sample, frame)
            definition_audit_rows.append(definition_row)
            contract_rows.extend(coverage)
        elif sample["schema"] == "statistics":
            statistics_rows.append(generic_event_row(sample, frame, schema="statistics"))
        elif sample["schema"] == "status":
            status_rows.append(generic_event_row(sample, frame, schema="status"))

    after = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    write_source_manifest(state_dir / "source_manifest_after.csv", after)
    mutation_check = compare_source_manifests(before, after)
    write_json(state_dir / "source_mutation_check.json", mutation_check)

    followups = classify_phase1_followups(inventory, anomalies, sample_results)
    ohlcv_invariant_failures = sum(int(row.get("invariant_failure_count", 0)) for row in ohlcv_rows)
    trade_sanity_failures = sum(int(row.get("sanity_failure_count", 0)) for row in trades_rows)
    timestamp_failures = 0
    timestamp_order_warnings = 0
    for row in timestamp_rows:
        schema = str(row.get("schema", ""))
        invalid_count = int(row.get("invalid_timestamp_count", 0))
        out_of_order_count = int(row.get("out_of_order_count", 0))
        minute_alignment_count = int(row.get("minute_alignment_fail_count", 0))
        if schema in CORE_SCHEMAS:
            timestamp_failures += invalid_count
        if schema in {"ohlcv-1m", "trades"}:
            timestamp_failures += out_of_order_count + minute_alignment_count
        elif schema in CORE_SCHEMAS:
            timestamp_order_warnings += out_of_order_count
    instrument_mapping_failures = (
        sum(int(row.get("instrument_id_missing_count", 0)) for row in trades_rows)
        + sum(int(row.get("instrument_id_missing_count", 0)) for row in definition_audit_rows)
        + sum(int(row.get("instrument_id_missing_count", 0)) for row in statistics_rows)
        + sum(int(row.get("instrument_id_missing_count", 0)) for row in status_rows)
    )
    summary = {
        "sample_files_scanned": len(samples),
        "sample_rows_scanned": sample_rows_scanned,
        "schemas_audited": sorted({str(row["schema"]) for row in samples}),
        "markets_sampled_count": len({str(row["market"]) for row in samples if row["market"]}),
        "markets_sampled": unique_sorted(row["market"] for row in samples),
        "years_sampled_count": len({str(row["year"]) for row in samples if row["year"]}),
        "years_sampled": unique_sorted(row["year"] for row in samples),
        "phase1_blockers_resolved": sum(1 for row in followups if str(row["carried_forward"]) in {"False", "false", "0"}),
        "phase1_blockers_carried_forward": sum(1 for row in followups if str(row["carried_forward"]) in {"True", "true", "1"}),
        "unreadable_files": sum(1 for row in cross_rows if row["read_status"] != "read"),
        "ohlcv_invariant_failures": ohlcv_invariant_failures,
        "trade_sanity_failures": trade_sanity_failures,
        "timestamp_failures": timestamp_failures,
        "timestamp_order_warnings": timestamp_order_warnings,
        "instrument_mapping_failures": instrument_mapping_failures,
        "source_mutation_check": mutation_check["source_mutation_check"],
    }
    blockers = blocker_from_mutation(PHASE, mutation_check) + blockers_from_metrics(summary, followups)
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

    write_csv(phase_dir / "schema_audit.csv", list(schema_rows[0].keys()) if schema_rows else ["path"], schema_rows)
    write_csv(phase_dir / "timestamp_audit.csv", list(timestamp_rows[0].keys()) if timestamp_rows else ["path"], timestamp_rows)
    write_csv(phase_dir / "ohlcv_1m_audit.csv", list(ohlcv_rows[0].keys()) if ohlcv_rows else ["path"], ohlcv_rows)
    write_json(phase_dir / "ohlcv_1m_summary.json", {"sampled_files": len(ohlcv_rows), "invariant_failures": ohlcv_invariant_failures})
    write_csv(phase_dir / "trades_audit.csv", list(trades_rows[0].keys()) if trades_rows else ["path"], trades_rows)
    write_json(phase_dir / "trades_coverage_summary.json", {"sampled_files": len(trades_rows), "trade_sanity_failures": trade_sanity_failures})
    write_csv(phase_dir / "definition_audit.csv", list(definition_audit_rows[0].keys()) if definition_audit_rows else ["path"], definition_audit_rows)
    write_csv(phase_dir / "contract_coverage.csv", ["path", "root", "year", "contract_month", "definition_count"], contract_rows)
    write_csv(phase_dir / "statistics_audit.csv", list(statistics_rows[0].keys()) if statistics_rows else ["path"], statistics_rows)
    write_csv(phase_dir / "status_audit.csv", list(status_rows[0].keys()) if status_rows else ["path"], status_rows)
    write_csv(phase_dir / "cross_schema_sample_audit.csv", list(cross_rows[0].keys()) if cross_rows else ["path"], cross_rows)
    write_csv(phase_dir / "phase1_blocker_followup.csv", list(followups[0].keys()) if followups else ["phase1_issue"], followups)

    result = PhaseResult(
        phase=PHASE,
        started_at=started,
        finished_at=utc_now(),
        reports=[
            rel(phase_dir / "schema_audit.csv"),
            rel(phase_dir / "timestamp_audit.csv"),
            rel(phase_dir / "ohlcv_1m_audit.csv"),
            rel(phase_dir / "ohlcv_1m_summary.json"),
            rel(phase_dir / "trades_audit.csv"),
            rel(phase_dir / "trades_coverage_summary.json"),
            rel(phase_dir / "definition_audit.csv"),
            rel(phase_dir / "contract_coverage.csv"),
            rel(phase_dir / "statistics_audit.csv"),
            rel(phase_dir / "status_audit.csv"),
            rel(phase_dir / "cross_schema_sample_audit.csv"),
            rel(phase_dir / "phase1_blocker_followup.csv"),
            rel(phase_dir / "blockers.csv"),
            rel(phase_dir / "phase2_readiness_gate.json"),
            rel(phase_dir / "phase2_report.md"),
        ],
        blockers=blockers,
        source_mutation_check=str(mutation_check["source_mutation_check"]),
        summary=summary,
        gate_path=phase_gate_path(Path(args.output_dir), 2, "phase2_readiness_gate.json"),
        blockers_csv=phase_dir / "blockers.csv",
    )
    write_text(phase_dir / "phase2_report.md", render_report(summary, blockers))
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
        "phase2 status={status} severe={severe} medium={medium} low={low} sample_files={files} sample_rows={rows} blockers_csv={blockers}".format(
            status=gate["status"],
            severe=gate["severe_count"],
            medium=gate["medium_count"],
            low=gate["low_count"],
            files=summary["sample_files_scanned"],
            rows=summary["sample_rows_scanned"],
            blockers=gate["blockers_csv"],
        )
    )
    return gate
