from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from scripts.phase1_raw_contract import REQUIRED_DATASET
from scripts.validation.audit_raw_session_gaps import _bucket_synthetic_timestamps, _top_counts


REQUIRED_THIRD_PARTY_SOURCE_TYPE = "trades/time-and-sales, not OHLCV"
WINDOW_DECISION = "pending_trade_source_verification"
ACCEPTED_EXTERNAL_TRADE_SCHEMA = {
    "required_columns": ["timestamp_utc"],
    "preferred_columns": [
        "timestamp_utc",
        "raw_symbol",
        "instrument_id",
        "price",
        "size",
        "source",
        "source_file",
        "source_timestamp_timezone",
    ],
    "timestamp_timezone": "UTC required or source timezone explicitly documented",
    "accepted_source_types": ["trades", "time-and-sales"],
    "not_accepted_as_proof": ["OHLCV bars"],
}
SESSION_EDGE_OR_LOW_LIQUIDITY_BUCKETS = {
    "outside_configured_session",
    "configured_evening_17_18_ct",
    "overnight_19_05_ct",
    "first_60m_after_configured_open",
    "last_60m_before_configured_close",
}
ACTIVE_SESSION_BUCKETS = {
    "pre_us_06_07_ct",
    "us_day_08_13_ct",
    "late_day_14_15_ct",
    "other_in_session",
}
LEAD_MARKET_BY_MARKET = {
    "ES": "ES",
    "NQ": "ES",
    "RTY": "ES",
    "YM": "ES",
    "ZT": "ZN",
    "ZF": "ZN",
    "ZN": "ZN",
    "ZB": "ZN",
    "UB": "ZN",
}


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _utc_iso(ts: pd.Timestamp) -> str:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").isoformat().replace("+00:00", "Z")


def _timestamp_column(frame: pd.DataFrame, path: Path) -> pd.Series:
    for column in ("ts", "ts_event", "datetime", "datetime_utc", "timestamp", "time"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index)
    raise ValueError(f"missing timestamp column/index in {_relative_path(path)}")


def _read_parquet_with_ts(path: Path) -> tuple[pd.DataFrame | None, pd.Series, list[str]]:
    if not path.exists():
        return None, pd.Series(dtype="datetime64[ns, UTC]"), [f"missing input: {_relative_path(path)}"]
    try:
        frame = pd.read_parquet(path)
        return frame, _timestamp_column(frame, path), []
    except Exception as exc:
        return None, pd.Series(dtype="datetime64[ns, UTC]"), [f"unreadable input {_relative_path(path)}: {exc}"]


def _load_profile(config_path: Path, profile: str) -> tuple[str | None, list[str], list[int], list[str]]:
    if not config_path.exists():
        return None, [], [], [f"missing profile config: {_relative_path(config_path)}"]
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return None, [], [], [f"unreadable profile config {_relative_path(config_path)}: {exc}"]
    if not isinstance(payload, dict):
        return None, [], [], ["profile config top-level YAML is not a mapping"]

    profiles = payload.get("profiles") or {}
    aliases = payload.get("aliases") or {}
    if not isinstance(profiles, dict):
        return None, [], [], ["profile config missing profiles mapping"]
    resolved = str(aliases.get(profile, profile)) if isinstance(aliases, dict) else profile
    profile_payload = profiles.get(resolved)
    if not isinstance(profile_payload, dict):
        return None, [], [], [f"profile not found: {profile}"]
    markets = [str(market) for market in profile_payload.get("markets", [])]
    years = [int(year) for year in profile_payload.get("years", [])]
    failures = []
    if not markets:
        failures.append(f"profile has no markets: {resolved}")
    if not years:
        failures.append(f"profile has no years: {resolved}")
    return resolved, markets, years, failures


def _synthetic_work_frame(synthetic: pd.DataFrame, synthetic_ts: pd.Series) -> pd.DataFrame:
    work = synthetic.reset_index(drop=True).copy()
    work["_ts"] = synthetic_ts.reset_index(drop=True)
    work = work.dropna(subset=["_ts"]).sort_values("_ts", kind="mergesort").reset_index(drop=True)
    if work.empty:
        return work
    if "synthetic_gap_id" in work.columns and work["synthetic_gap_id"].notna().all():
        work["_gap_id"] = work["synthetic_gap_id"].astype(str)
        return work

    gap_ids: list[str] = []
    current_id = 1
    previous_ts: pd.Timestamp | None = None
    for value in work["_ts"]:
        current_ts = pd.Timestamp(value)
        if previous_ts is not None and current_ts != previous_ts + pd.Timedelta(minutes=1):
            current_id += 1
        gap_ids.append(f"generated_gap_{current_id:06d}")
        previous_ts = current_ts
    work["_gap_id"] = gap_ids
    return work


def _group_synthetic_minutes(synthetic: pd.DataFrame, synthetic_ts: pd.Series) -> list[tuple[str, pd.DataFrame]]:
    work = _synthetic_work_frame(synthetic, synthetic_ts)
    if work.empty:
        return []
    return [(str(gap_id), group.copy()) for gap_id, group in work.groupby("_gap_id", sort=False)]


def _truthy_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(frame[column].fillna(False).astype(bool).sum())


def _prepare_raw_context(raw: pd.DataFrame, raw_ts: pd.Series) -> pd.DataFrame:
    work = raw.copy()
    work["_ts"] = raw_ts
    return work.dropna(subset=["_ts"]).sort_values("_ts", kind="mergesort").reset_index(drop=True)


def _resolve_adjacent_contract(
    raw_context: pd.DataFrame,
    first_ts: pd.Timestamp,
    last_ts: pd.Timestamp,
) -> dict[str, Any]:
    if raw_context.empty:
        adjacent = pd.DataFrame()
        before = pd.DataFrame()
        after = pd.DataFrame()
    else:
        ts = raw_context["_ts"]
        before_pos = int(ts.searchsorted(first_ts, side="left")) - 1
        after_pos = int(ts.searchsorted(last_ts, side="right"))
        before = raw_context.iloc[[before_pos]] if before_pos >= 0 else pd.DataFrame()
        after = raw_context.iloc[[after_pos]] if after_pos < len(raw_context) else pd.DataFrame()
        adjacent = pd.concat([before, after], ignore_index=True)
    symbols = sorted(set(adjacent.get("raw_symbol", pd.Series(dtype="object")).dropna().astype(str)))
    instrument_ids = sorted(
        set(
            int(value)
            for value in pd.to_numeric(adjacent.get("instrument_id"), errors="coerce")
            .dropna()
            .astype("int64")
            .tolist()
        )
    )
    status = "resolved" if len(symbols) == 1 and len(instrument_ids) == 1 else "ambiguous_or_missing"
    source_files = sorted(set(adjacent.get("source_file", pd.Series(dtype="object")).dropna().astype(str)))
    source_hashes = sorted(set(adjacent.get("source_sha256", pd.Series(dtype="object")).dropna().astype(str)))
    prev_volume = _numeric_row_value(before, ["volume", "vol"])
    next_volume = _numeric_row_value(after, ["volume", "vol"])
    prev_range = _bar_range(before)
    next_range = _bar_range(after)
    return {
        "status": status,
        "raw_symbol": symbols[0] if len(symbols) == 1 else None,
        "raw_symbols": symbols,
        "instrument_id": instrument_ids[0] if len(instrument_ids) == 1 else None,
        "instrument_ids": instrument_ids,
        "before_ts": _utc_iso(pd.Timestamp(before["_ts"].iloc[0])) if not before.empty else None,
        "after_ts": _utc_iso(pd.Timestamp(after["_ts"].iloc[0])) if not after.empty else None,
        "raw_ohlcv_source_files": source_files,
        "raw_ohlcv_source_hashes": source_hashes,
        "previous_volume": prev_volume,
        "next_volume": next_volume,
        "previous_range": prev_range,
        "next_range": next_range,
    }


def _numeric_row_value(frame: pd.DataFrame, columns: list[str]) -> float | None:
    if frame.empty:
        return None
    row = frame.iloc[0]
    for column in columns:
        if column not in frame.columns:
            continue
        value = pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]
        if pd.notna(value):
            return float(value)
    return None


def _bar_range(frame: pd.DataFrame) -> float | None:
    if frame.empty or "high" not in frame.columns or "low" not in frame.columns:
        return None
    high = _numeric_row_value(frame, ["high"])
    low = _numeric_row_value(frame, ["low"])
    if high is None or low is None:
        return None
    return float(high - low)


def _window_metadata(group: pd.DataFrame) -> dict[str, Any]:
    session_buckets = _top_counts(group.get("_session_bucket", pd.Series(dtype="string")), "bucket")
    ct_hours = _top_counts(group.get("_ct_hour", pd.Series(dtype="int64")).astype("string"), "ct_hour")
    ts = pd.to_datetime(group.get("_ts", pd.Series(dtype="datetime64[ns, UTC]")), utc=True, errors="coerce").dropna()
    minute_of_day_utc = (ts.dt.hour * 60 + ts.dt.minute).astype("int64") if not ts.empty else pd.Series(dtype="int64")
    return {
        "session_bucket_counts": session_buckets,
        "ct_hour_buckets": ct_hours,
        "minute_of_day_utc_buckets": _top_counts(minute_of_day_utc.astype("string"), "minute_of_day_utc"),
        "session_dates": sorted(set(group.get("_session_date", pd.Series(dtype="string")).dropna().astype(str))),
    }


def _session_classification(session_bucket_counts: list[dict[str, Any]]) -> str:
    buckets = {str(row["bucket"]) for row in session_bucket_counts}
    if not buckets:
        return "unknown"
    if buckets == {"outside_configured_session"}:
        return "outside_session"
    if buckets & ACTIVE_SESSION_BUCKETS:
        return "mixed_session" if buckets - ACTIVE_SESSION_BUCKETS else "inside_session"
    if buckets <= SESSION_EDGE_OR_LOW_LIQUIDITY_BUCKETS:
        return "session_edge_or_low_liquidity"
    return "mixed_session"


def _compute_panel_metrics(
    windows: list[dict[str, Any]],
    *,
    systemic_threshold: float,
    min_denominator: int,
) -> dict[str, Any]:
    pairs_by_year: dict[int, set[str]] = {}
    timestamp_counts: Counter[tuple[int, str]] = Counter()
    for window in windows:
        year = int(window["year"])
        pairs_by_year.setdefault(year, set()).add(str(window["market"]))
        for value in window["source_gap_timestamps"]:
            timestamp_counts[(year, str(value))] += 1

    ratios: dict[tuple[int, str], dict[str, Any]] = {}
    for key, missing_count in timestamp_counts.items():
        year, ts = key
        denominator = len(pairs_by_year.get(year, set()))
        ratio = float(missing_count / denominator) if denominator else 0.0
        ratios[key] = {
            "year": year,
            "timestamp_utc": ts,
            "missing_count": int(missing_count),
            "denominator": int(denominator),
            "missing_ratio": ratio,
            "is_systemic_gap": bool(denominator >= min_denominator and ratio >= systemic_threshold),
        }

    top = sorted(
        ratios.values(),
        key=lambda row: (-float(row["missing_ratio"]), -int(row["missing_count"]), str(row["timestamp_utc"])),
    )[:20]
    systemic_count = sum(1 for row in ratios.values() if row["is_systemic_gap"])
    return {
        "systemic_threshold": float(systemic_threshold),
        "min_denominator": int(min_denominator),
        "timestamp_count": len(ratios),
        "systemic_timestamp_count": int(systemic_count),
        "top_missing_ratio_timestamps": top,
        "_ratios": ratios,
    }


def _diagnostic_score(
    *,
    session_classification: str,
    microstructure: dict[str, Any],
    flags: dict[str, int],
    panel: dict[str, Any],
    contract_resolution_status: str,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if contract_resolution_status != "resolved":
        score += 0.2
        reasons.append("adjacent contract unresolved")
    if session_classification in {"inside_session", "mixed_session"}:
        score += 0.2
        reasons.append("gap overlaps configured active session buckets")
    if bool(microstructure["volume_sandwich_flag"]):
        score += 0.2
        reasons.append("nonzero adjacent OHLCV volume before and after gap")
    if bool(microstructure["range_sandwich_flag"]):
        score += 0.1
        reasons.append("nonzero adjacent OHLCV range before and after gap")
    if any(int(value) > 0 for value in flags.values()):
        score += 0.2
        reasons.append("gap overlaps roll/symbol/instrument-change flags")
    if bool(panel["is_systemic_gap"]):
        score += 0.1
        reasons.append("same UTC timestamp missing across multiple processed markets")
    return min(score, 1.0), reasons


def build_gap_labels(
    windows: list[dict[str, Any]],
    *,
    systemic_threshold: float,
    min_panel_denominator: int,
) -> dict[str, Any]:
    panel_metrics = _compute_panel_metrics(
        windows,
        systemic_threshold=systemic_threshold,
        min_denominator=min_panel_denominator,
    )
    ratios = panel_metrics["_ratios"]
    score_counts: Counter[str] = Counter()
    for window in windows:
        timestamp_panels = [
            ratios[(int(window["year"]), str(value))]
            for value in window["source_gap_timestamps"]
            if (int(window["year"]), str(value)) in ratios
        ]
        max_panel = max(timestamp_panels, key=lambda row: float(row["missing_ratio"]), default=None)
        panel = {
            "max_missing_ratio": float(max_panel["missing_ratio"]) if max_panel else 0.0,
            "max_missing_count": int(max_panel["missing_count"]) if max_panel else 0,
            "denominator": int(max_panel["denominator"]) if max_panel else 0,
            "is_systemic_gap": bool(max_panel["is_systemic_gap"]) if max_panel else False,
            "status": "computed" if max_panel and int(max_panel["denominator"]) >= min_panel_denominator else "insufficient_panel_scope",
        }
        flags = window["roll_symbol_instrument_change_flags"]
        session_classification = _session_classification(window["session_bucket_counts"])
        microstructure = {
            "previous_volume": window["adjacent_ohlcv_context"]["previous_volume"],
            "next_volume": window["adjacent_ohlcv_context"]["next_volume"],
            "previous_range": window["adjacent_ohlcv_context"]["previous_range"],
            "next_range": window["adjacent_ohlcv_context"]["next_range"],
            "volume_sandwich_flag": bool(
                (window["adjacent_ohlcv_context"]["previous_volume"] or 0) > 0
                and (window["adjacent_ohlcv_context"]["next_volume"] or 0) > 0
            ),
            "range_sandwich_flag": bool(
                (window["adjacent_ohlcv_context"]["previous_range"] or 0) > 0
                and (window["adjacent_ohlcv_context"]["next_range"] or 0) > 0
            ),
            "uses_next_bar_for_audit_label_only": True,
        }
        score, reasons = _diagnostic_score(
            session_classification=session_classification,
            microstructure=microstructure,
            flags=flags,
            panel=panel,
            contract_resolution_status=window["contract_resolution_status"],
        )
        is_suspect = score >= 0.5
        score_counts["suspect" if is_suspect else "not_suspect"] += 1
        window["diagnostic_features"] = {
            "session_classification": session_classification,
            "panel_consistency": panel,
            "microstructure_context": microstructure,
            "lead_market_check": {
                "lead_market": LEAD_MARKET_BY_MARKET.get(str(window["market"])),
                "status": "not_evaluated_without_lead_trade_evidence",
                "suspicion_increment": 0.0,
            },
            "potential_bias_flags": {
                "lookahead_bias_risk": "next_volume/next_range are audit-label-only and must not feed model features",
                "calendar_misalignment_risk": session_classification in {"outside_session", "mixed_session"},
                "survivorship_bias_risk": "panel scope is limited to selected processed market-years",
            },
        }
        window["audit_labels"] = {
            "is_missing": True,
            "gap_length": int(window["missing_minute_count"]),
            "is_systemic_gap": bool(panel["is_systemic_gap"]),
            "is_session_valid": session_classification != "outside_session",
            "is_suspect_gap": bool(is_suspect),
            "combined_confidence_score": round(float(score), 6),
            "score_direction": "0=lower diagnostic suspicion, 1=higher diagnostic suspicion; not proof of no-trade or bad data",
            "score_reasons": reasons,
        }
    panel_metrics.pop("_ratios", None)
    return {
        "panel_metrics": panel_metrics,
        "suspect_gap_windows": int(score_counts["suspect"]),
        "not_suspect_gap_windows": int(score_counts["not_suspect"]),
        "root_cause_interpretation": [
            "This audit labels suspicion only; it does not prove true no-trade minutes without trade/time-and-sales evidence.",
            "Session-edge or low-liquidity gaps are less suspicious than active-session gaps with adjacent OHLCV activity.",
            "Panel and lead-market checks are limited by the processed market-year scope.",
        ],
    }


def _build_windows_for_market_year(
    *,
    market: str,
    year: int,
    raw_root: Path,
    causal_root: Path,
    session_config: Path,
    buffer_minutes: int,
    allow_unresolved_contracts: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    raw_path = raw_root / market / f"{year}.parquet"
    causal_path = causal_root / market / f"{year}.parquet"
    raw, raw_ts, raw_failures = _read_parquet_with_ts(raw_path)
    causal, causal_ts, causal_failures = _read_parquet_with_ts(causal_path)
    failures = raw_failures + causal_failures
    if not session_config.exists():
        failures.append(f"missing session config: {_relative_path(session_config)}")
    if failures or raw is None or causal is None:
        return [], failures
    if "is_synthetic" not in causal.columns:
        return [], [f"missing is_synthetic column: {_relative_path(causal_path)}"]

    raw_context = _prepare_raw_context(raw, raw_ts)
    synthetic_mask = causal["is_synthetic"].fillna(False).astype(bool)
    synthetic = causal.loc[synthetic_mask].copy()
    synthetic_ts = causal_ts.loc[synthetic_mask]
    work = _synthetic_work_frame(synthetic, synthetic_ts)
    if not work.empty:
        metadata = _bucket_synthetic_timestamps(work["_ts"], market, session_config).reset_index(drop=True)
        work["_session_bucket"] = metadata.get("session_bucket", pd.Series(dtype="string"))
        work["_ct_hour"] = metadata.get("ct_hour", pd.Series(dtype="Int64"))
        work["_session_date"] = metadata.get("session_date", pd.Series(dtype="string"))
    groups = [] if work.empty else [(str(gap_id), group.copy()) for gap_id, group in work.groupby("_gap_id", sort=False)]
    windows: list[dict[str, Any]] = []
    for gap_id, group in groups:
        ts = pd.to_datetime(group["_ts"], utc=True, errors="coerce").dropna()
        if ts.empty:
            continue
        first_ts = pd.Timestamp(ts.min())
        last_ts = pd.Timestamp(ts.max())
        contract = _resolve_adjacent_contract(raw_context, first_ts, last_ts)
        if contract["status"] != "resolved" and not allow_unresolved_contracts:
            failures.append(f"{market} {year} {gap_id}: adjacent contract unresolved")
            continue

        metadata = _window_metadata(group)
        flag_counts = {
            "roll_window_rows": _truthy_count(group, "roll_window_flag"),
            "symbol_change_rows": _truthy_count(group, "symbol_change_flag"),
            "instrument_id_change_rows": _truthy_count(group, "instrument_id_change_flag"),
        }
        windows.append(
            {
                "market": market,
                "year": int(year),
                "synthetic_gap_id": str(gap_id),
                "raw_symbol": contract["raw_symbol"],
                "raw_symbols": contract["raw_symbols"],
                "instrument_id": contract["instrument_id"],
                "instrument_ids": contract["instrument_ids"],
                "contract_resolution_status": contract["status"],
                "adjacent_before_ts": contract["before_ts"],
                "adjacent_after_ts": contract["after_ts"],
                "raw_ohlcv_source_files": contract["raw_ohlcv_source_files"],
                "raw_ohlcv_source_hashes": contract["raw_ohlcv_source_hashes"],
                "first_missing_ts_utc": _utc_iso(first_ts),
                "last_missing_ts_utc": _utc_iso(last_ts),
                "query_start_utc": _utc_iso(first_ts - pd.Timedelta(minutes=buffer_minutes)),
                "query_end_utc": _utc_iso(last_ts + pd.Timedelta(minutes=buffer_minutes + 1)),
                "missing_minute_count": int(len(ts)),
                "source_gap_timestamps": [_utc_iso(pd.Timestamp(value)) for value in ts.tolist()],
                "session_bucket_counts": metadata["session_bucket_counts"],
                "ct_hour_buckets": metadata["ct_hour_buckets"],
                "minute_of_day_utc_buckets": metadata["minute_of_day_utc_buckets"],
                "session_dates": metadata["session_dates"],
                "roll_symbol_instrument_change_flags": flag_counts,
                "adjacent_ohlcv_context": {
                    "previous_volume": contract["previous_volume"],
                    "next_volume": contract["next_volume"],
                    "previous_range": contract["previous_range"],
                    "next_range": contract["next_range"],
                    "uses_next_bar_for_audit_label_only": True,
                },
                "required_third_party_source_type": REQUIRED_THIRD_PARTY_SOURCE_TYPE,
                "accepted_external_schema": ACCEPTED_EXTERNAL_TRADE_SCHEMA,
                "decision": WINDOW_DECISION,
                "reason": "verify_missing_ohlcv_minute_had_no_trade_using_independent_trade_source",
            }
        )
    return windows, failures


def _summary(windows: list[dict[str, Any]]) -> dict[str, Any]:
    by_market_year = Counter(f"{window['market']} {window['year']}" for window in windows)
    return {
        "window_count": len(windows),
        "total_missing_minutes": int(sum(int(window["missing_minute_count"]) for window in windows)),
        "unresolved_contract_windows": int(
            sum(1 for window in windows if window["contract_resolution_status"] != "resolved")
        ),
        "windows_by_market_year": [
            {"market_year": key, "windows": int(value)} for key, value in sorted(by_market_year.items())
        ],
    }


def _market_year_pairs(markets: list[str], years: list[int]) -> list[tuple[str, int]]:
    return [(market, int(year)) for market in markets for year in years]


def _read_progress_keys(path: Path) -> tuple[set[tuple[str, int]], list[str]]:
    if not path.exists():
        return set(), []
    keys: set[tuple[str, int]] = set()
    failures: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except Exception as exc:
            failures.append(f"unreadable progress JSONL line {line_number}: {exc}")
            continue
        try:
            keys.add((str(record["market"]), int(record["year"])))
        except Exception:
            failures.append(f"progress JSONL line {line_number} missing market/year")
    return keys, failures


def _append_progress_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    resolved_profile, profile_markets, profile_years, profile_failures = _load_profile(config_path, args.profile)
    markets = [str(market) for market in (args.markets or profile_markets)]
    years = [int(year) for year in (args.years or profile_years)]
    failures = profile_failures if not args.markets or not args.years else []
    if not markets:
        failures.append("no markets selected")
    if not years:
        failures.append("no years selected")

    windows: list[dict[str, Any]] = []
    progress_path = Path(args.progress_jsonl) if getattr(args, "progress_jsonl", None) else None
    resume_progress = bool(getattr(args, "resume_progress", False))
    max_market_years = getattr(args, "max_market_years", None)
    if max_market_years is not None and int(max_market_years) <= 0:
        failures.append("max_market_years must be > 0")
    completed_keys: set[tuple[str, int]] = set()
    skipped_market_years: list[dict[str, Any]] = []
    if progress_path is not None and resume_progress:
        completed_keys, progress_failures = _read_progress_keys(progress_path)
        failures.extend(progress_failures)

    selected_pairs = _market_year_pairs(markets, years)
    pending_pairs = [
        (market, year)
        for market, year in selected_pairs
        if (market, year) not in completed_keys
    ]
    skipped_market_years = [
        {"market": market, "year": year}
        for market, year in selected_pairs
        if (market, year) in completed_keys
    ]
    if max_market_years is not None:
        pending_pairs = pending_pairs[: int(max_market_years)]

    if markets and years:
        for market, year in pending_pairs:
            market_windows, market_failures = _build_windows_for_market_year(
                market=market,
                year=year,
                raw_root=Path(args.raw_root),
                causal_root=Path(args.causal_root),
                session_config=Path(args.session_config),
                buffer_minutes=int(args.buffer_minutes),
                allow_unresolved_contracts=bool(args.allow_unresolved_contracts),
            )
            market_diagnostics = build_gap_labels(
                market_windows,
                systemic_threshold=float(args.panel_systemic_threshold),
                min_panel_denominator=int(args.min_panel_denominator),
            )
            windows.extend(market_windows)
            failures.extend(market_failures)
            if progress_path is not None:
                _append_progress_record(
                    progress_path,
                    {
                        "generated_at_utc": datetime.now(UTC).isoformat(),
                        "market": market,
                        "year": int(year),
                        "status": "FAIL" if market_failures else "PASS",
                        "failures": market_failures,
                        "summary": _summary(market_windows),
                        "diagnostics": market_diagnostics,
                        "windows": market_windows,
                    },
                )

    diagnostics = build_gap_labels(
        windows,
        systemic_threshold=float(args.panel_systemic_threshold),
        min_panel_denominator=int(args.min_panel_denominator),
    )
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "dry_run_only": True,
        "profile": args.profile,
        "resolved_profile": resolved_profile,
        "config": _relative_path(config_path),
        "markets": markets,
        "years": years,
        "dataset": REQUIRED_DATASET,
        "raw_root": _relative_path(Path(args.raw_root)),
        "causal_root": _relative_path(Path(args.causal_root)),
        "session_config": _relative_path(Path(args.session_config)),
        "buffer_minutes": int(args.buffer_minutes),
        "allow_unresolved_contracts": bool(args.allow_unresolved_contracts),
        "progress_jsonl": _relative_path(progress_path) if progress_path is not None else None,
        "resume_progress": resume_progress,
        "max_market_years": int(max_market_years) if max_market_years is not None else None,
        "panel_systemic_threshold": float(args.panel_systemic_threshold),
        "min_panel_denominator": int(args.min_panel_denominator),
        "required_third_party_source_type": REQUIRED_THIRD_PARTY_SOURCE_TYPE,
        "accepted_external_trade_schema": ACCEPTED_EXTERNAL_TRADE_SCHEMA,
        "decision_placeholder": WINDOW_DECISION,
        "failures": failures,
        "summary": {
            **_summary(windows),
            "selected_market_year_count": len(selected_pairs),
            "processed_market_year_count": len(pending_pairs),
            "skipped_market_year_count": len(skipped_market_years),
            "suspect_gap_windows": diagnostics["suspect_gap_windows"],
            "not_suspect_gap_windows": diagnostics["not_suspect_gap_windows"],
        },
        "diagnostics": diagnostics,
        "skipped_market_years": skipped_market_years,
        "windows": windows,
    }


def write_json_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Missing-Minute Trade Source Verification Manifest",
        "",
        f"Generated: {manifest['generated_at_utc']}",
        f"Status: `{manifest['status']}`",
        f"Profile: `{manifest['resolved_profile'] or manifest['profile']}`",
        "",
        "| Market | Year | Symbol | Instrument ID | Gap | First missing | Last missing | Missing min | Decision |",
        "|---|---:|---|---:|---|---|---|---:|---|",
    ]
    for window in manifest["windows"]:
        lines.append(
            "| `{market}` | {year} | `{symbol}` | {instrument_id} | `{gap}` | {first} | {last} | {count} | `{decision}` |".format(
                market=window["market"],
                year=window["year"],
                symbol=window.get("raw_symbol") or "UNRESOLVED",
                instrument_id=window.get("instrument_id") or "",
                gap=window["synthetic_gap_id"],
                first=window["first_missing_ts_utc"],
                last=window["last_missing_ts_utc"],
                count=window["missing_minute_count"],
                decision=window["decision"],
            )
        )
    lines.extend(
        [
            "",
            "Required third-party source type: trades/time-and-sales, not OHLCV.",
            "No no-trade status is inferred by this manifest.",
        ]
    )
    if manifest["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in manifest["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="tier_3_research")
    parser.add_argument("--config", default="configs/alpha_tiered.yaml")
    parser.add_argument("--markets", nargs="+")
    parser.add_argument("--years", nargs="+", type=int)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--causal-root", default="data/causally_gated_normalized")
    parser.add_argument("--session-config", default="configs/market_sessions.yaml")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out")
    parser.add_argument("--buffer-minutes", type=int, default=2)
    parser.add_argument("--allow-unresolved-contracts", action="store_true")
    parser.add_argument("--max-market-years", type=int)
    parser.add_argument("--progress-jsonl")
    parser.add_argument("--resume-progress", action="store_true")
    parser.add_argument("--panel-systemic-threshold", type=float, default=0.4)
    parser.add_argument("--min-panel-denominator", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.buffer_minutes < 0:
        raise SystemExit("--buffer-minutes must be >= 0")
    if args.max_market_years is not None and args.max_market_years <= 0:
        raise SystemExit("--max-market-years must be > 0")
    if not 0.0 <= args.panel_systemic_threshold <= 1.0:
        raise SystemExit("--panel-systemic-threshold must be in [0, 1]")
    if args.min_panel_denominator <= 0:
        raise SystemExit("--min-panel-denominator must be > 0")
    manifest = build_manifest(args)
    write_json_manifest(manifest, Path(args.json_out))
    if args.md_out:
        write_markdown_manifest(manifest, Path(args.md_out))
    if manifest["status"] != "PASS":
        print(f"FAIL missing-minute verification manifest: failures={len(manifest['failures'])}")
        return 1
    print(
        "PASS missing-minute verification manifest: "
        f"windows={manifest['summary']['window_count']} missing_minutes={manifest['summary']['total_missing_minutes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
