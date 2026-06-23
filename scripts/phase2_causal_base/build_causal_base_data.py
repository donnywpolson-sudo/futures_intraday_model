#!/usr/bin/env python3
"""Build Phase 2 causal base parquet files from raw 1-minute futures bars."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from scripts.profile_scope import load_profile_scope, scope_authority_metadata
from scripts.validation.audit_local_trade_ohlcv_gaps import (
    build_report as build_local_trade_gap_report,
    write_json_report as write_local_trade_gap_json_report,
    write_markdown_report as write_local_trade_gap_markdown_report,
)


DEFAULT_PROFILE = "all_raw"
DISCOVERY_PROFILES = {"all_raw", "all_raw_data"}
DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")
DEFAULT_SESSION_CONFIG = Path("configs/market_sessions.yaml")
DEFAULT_RAW_ALIGNMENT_REPORT = Path("reports/raw_ingest/raw_dbn_alignment.json")
LOCAL_TRADE_GAP_AUDIT_START = "2025-06-18"
LOCAL_TRADE_GAP_AUDIT_END = "2026-06-13"
LOCAL_TRADE_GAP_AUDIT_PROFILES = ("tier_3_holdout", "tier_3_forward")
LOCAL_TRADE_GAP_AUDIT_DBN_ROOT = Path("data/dbn")
LOCAL_TRADE_GAP_AUDIT_JSON = "local_trade_ohlcv_gap_crosscheck_2025_2026.json"
LOCAL_TRADE_GAP_AUDIT_MD = "local_trade_ohlcv_gap_crosscheck_2025_2026.md"
LOCAL_TRADE_GAP_VALIDATED_STATUS = "validated_by_local_trades_window_convention"
LOCAL_TRADE_GAP_FAILED_STATUS = "failed_local_trades_window_gate"
LOCAL_TRADE_GAP_NOT_RUN_STATUS = "local_trades_window_gate_not_run"
LOCAL_TRADE_GAP_NOT_IN_SCOPE_STATUS = "not_in_local_trades_window_gate_scope"
CONTEXT_PADDING_DAYS = 14

# Discovery profiles process every top-level data/raw/{market}/{year}.parquet file.
# Static profiles mirror configs/alpha_tiered.yaml when that file is unavailable.
CORE_PROFILE_MARKETS = ["ES", "CL", "ZN", "6E"]
BALANCED_PROFILE_MARKETS = ["ES", "NQ", "CL", "NG", "GC", "HG", "SR3", "ZN", "ZB", "6E", "6J", "6B", "ZC", "ZS", "LE"]
FULL_PROFILE_MARKETS = ["ES", "NQ", "RTY", "YM", "CL", "NG", "RB", "HO", "GC", "SI", "HG", "SR3", "SR1", "TN", "ZT", "ZF", "ZN", "ZB", "UB", "6A", "6B", "6C", "6E", "6J", "6M", "ZC", "ZS", "ZL", "ZM", "ZW", "KE", "LE", "HE"]
RECENT_RESEARCH_YEARS = [2023, 2024]
BALANCED_RESEARCH_YEARS = list(range(2018, 2025))
LONG_RESEARCH_YEARS = list(range(2010, 2025))
FINAL_HOLDOUT_YEARS = [2025]
FORWARD_YEARS = [2026]
STATIC_PROFILE_ALIASES = {
    "tier_0_smoke": "tier_0",
    "tier_1": "tier_1_research",
    "tier_1_core": "tier_1_research",
    "tier_1_core_recent": "tier_1_research",
    "tier_1_recent": "tier_1_research",
    "tier_1_final_holdout": "tier_1_holdout",
    "tier_1_forward_2026": "tier_1_forward",
    "tier_2": "tier_2_research",
    "tier_2_long": "tier_2_research",
    "tier_2_final_holdout": "tier_2_holdout",
    "tier_2_forward_2026": "tier_2_forward",
    "tier_3": "tier_3_research",
    "tier_3_final_holdout": "tier_3_holdout",
    "tier_3_forward_2026": "tier_3_forward",
    "all_raw": "all_raw",
}

STATIC_PROFILE_MARKETS = {
    "tier_0": ["ES"],
    "tier_1": CORE_PROFILE_MARKETS,
    "tier_1_research": CORE_PROFILE_MARKETS,
    "tier_1_holdout": CORE_PROFILE_MARKETS,
    "tier_1_forward": CORE_PROFILE_MARKETS,
    "tier_2": BALANCED_PROFILE_MARKETS,
    "tier_2_research": BALANCED_PROFILE_MARKETS,
    "tier_2_holdout": BALANCED_PROFILE_MARKETS,
    "tier_2_forward": BALANCED_PROFILE_MARKETS,
    "tier_3": FULL_PROFILE_MARKETS,
    "tier_3_research": FULL_PROFILE_MARKETS,
    "tier_3_holdout": FULL_PROFILE_MARKETS,
    "tier_3_forward": FULL_PROFILE_MARKETS,
    "metadata_optional_test": ["ES"],
}

STATIC_PROFILE_YEARS = {
    "tier_0": [2024],
    "tier_1": RECENT_RESEARCH_YEARS,
    "tier_1_research": RECENT_RESEARCH_YEARS,
    "tier_1_holdout": FINAL_HOLDOUT_YEARS,
    "tier_1_forward": FORWARD_YEARS,
    "tier_2": BALANCED_RESEARCH_YEARS,
    "tier_2_research": BALANCED_RESEARCH_YEARS,
    "tier_2_holdout": FINAL_HOLDOUT_YEARS,
    "tier_2_forward": FORWARD_YEARS,
    "tier_3": LONG_RESEARCH_YEARS,
    "tier_3_research": LONG_RESEARCH_YEARS,
    "tier_3_holdout": FINAL_HOLDOUT_YEARS,
    "tier_3_forward": FORWARD_YEARS,
    "metadata_optional_test": [2024],
}

REQUIRED_OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
AUDIT_RAW_COLUMNS = ["rtype", "publisher_id", "instrument_id", "symbol"]
STRICT_RAW_COLUMNS = [
    "ts_event",
    *REQUIRED_OHLCV_COLUMNS,
    *AUDIT_RAW_COLUMNS,
    "data_quality_status",
    "data_quality_degraded",
]
RELAXED_RAW_SCHEMA_PROFILES = {"metadata_optional_test"}

OUTPUT_COLUMNS = [
    "ts",
    "market",
    "year",
    "symbol",
    "instrument_id",
    "publisher_id",
    "rtype",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "raw_row_present",
    "is_synthetic",
    "synthetic_gap_id",
    "synthetic_gap_size_minutes",
    "synthetic_gap_reason",
    "valid_ohlcv",
    "data_quality_status",
    "data_quality_degraded",
    "session_data_quality_degraded",
    "trainable_data_quality",
    "inside_session",
    "causal_valid",
    "causal_invalid_reason",
    "session_id",
    "session_date",
    "session_segment_id",
    "boundary_session_flag",
    "session_calendar_status",
    "holiday_calendar_available",
    "early_close_calendar_available",
    "calendar_coverage_status",
    "session_template",
    "is_session_open",
    "is_session_close",
    "minutes_since_session_open",
    "minutes_until_session_close",
    "session_progress",
    "minute_of_day",
    "day_of_week",
    "roll_boundary_flag",
    "symbol_change_flag",
    "instrument_id_change_flag",
    "bars_since_roll",
    "bars_until_roll",
    "roll_window_flag",
    "source_path",
    "source_file_hash",
    "source_row_number",
    "raw_schema_variant",
    "timestamp_source",
    "metadata_available",
    "roll_detection_available",
    "roll_detection_source",
    "roll_policy_status",
]
RAW_ENRICHMENT_COLUMN_PREFIXES = ("status_", "stat_", "statistics_")

SESSION_TEMPLATE = "cme_globex_17_16_ct"
EXCHANGE_TZ = "America/Chicago"
DEFAULT_ROLL_WINDOW_BARS = 15
DEFAULT_MAX_SYNTHETIC_GAP_MINUTES = 120
DEFAULT_MAX_SYNTHETIC_ROWS_PCT = 2.0
DEFAULT_MAX_DEGRADED_ROWS_PCT = 1.0
DEFAULT_MAX_ROLL_WINDOW_ROWS_PCT = 1.0
DEFAULT_SYNTHETIC_GAP_THRESHOLD_ACTION = "warn"
SYNTHETIC_GAP_THRESHOLD_ACTIONS = {"warn", "diagnostic"}
ROLL_MATURITY_EXCEPTION_CATEGORY = "roll_maturity"
ROLL_MATURITY_EXCEPTION_WARNING_PREFIXES = (
    "roll maturity sequence not monotonic",
    "roll exclusion threshold breached",
)
DEFAULT_REQUIRE_ROLL_METADATA_PROFILES = {
    "tier_1",
    "tier_1_research",
    "tier_1_holdout",
    "tier_1_forward",
    "tier_2",
    "tier_2_research",
    "tier_2_holdout",
    "tier_2_forward",
    "tier_3",
    "tier_3_research",
    "tier_3_holdout",
    "tier_3_forward",
}


@dataclass(frozen=True)
class AcceptedReadinessException:
    market: str
    year: int
    category: str
    reason: str
    evidence_paths: tuple[str, ...]
    warning_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class CausalBaseConfig:
    max_synthetic_rows_pct: float = DEFAULT_MAX_SYNTHETIC_ROWS_PCT
    max_synthetic_gap_minutes: int = DEFAULT_MAX_SYNTHETIC_GAP_MINUTES
    synthetic_gap_threshold_action: str = DEFAULT_SYNTHETIC_GAP_THRESHOLD_ACTION
    max_degraded_rows_pct: float = DEFAULT_MAX_DEGRADED_ROWS_PCT
    max_roll_window_rows_pct: float = DEFAULT_MAX_ROLL_WINDOW_ROWS_PCT
    sparse_trade_derived_ohlcv_markets: tuple[str, ...] = tuple()
    sparse_trade_derived_roll_window_minutes: int = DEFAULT_ROLL_WINDOW_BARS
    vendor_trusted_ohlcv_no_trade_markets: tuple[str, ...] = tuple()
    require_roll_metadata_for_profiles: tuple[str, ...] = tuple(
        sorted(DEFAULT_REQUIRE_ROLL_METADATA_PROFILES)
    )
    accepted_readiness_exceptions: tuple[AcceptedReadinessException, ...] = tuple()


@dataclass(frozen=True)
class SessionCalendar:
    session_template: str = SESSION_TEMPLATE
    timezone: str = EXCHANGE_TZ
    regular_open: str = "17:00"
    regular_close: str = "16:00"
    intraday_breaks: tuple[tuple[str, str], ...] = tuple()
    holidays: frozenset[str] = frozenset()
    closed_dates: frozenset[str] = frozenset()
    early_closes: dict[str, str] = field(default_factory=dict)
    source: str = "hardcoded_regular_session"
    config_available: bool = False

    @property
    def status(self) -> str:
        if self.config_available and (
            bool(self.holidays)
            or bool(self.closed_dates)
            or bool(self.early_closes)
            or bool(self.intraday_breaks)
        ):
            return "config_backed"
        if self.config_available:
            return "config_backed_regular_session"
        return "hardcoded_regular_session"

    @property
    def holiday_calendar_available(self) -> bool:
        return bool(self.holidays) or bool(self.closed_dates)

    @property
    def early_close_calendar_available(self) -> bool:
        return bool(self.early_closes)

    @property
    def calendar_coverage_status(self) -> str:
        if not self.config_available:
            return "hardcoded_regular_session"
        if (
            self.holiday_calendar_available
            or self.early_close_calendar_available
            or bool(self.intraday_breaks)
        ):
            return "config_backed"
        return "regular_session_only"


@dataclass
class ValidationResult:
    profile: str
    market: str
    year: int
    input_path: str
    output_path: str
    source_file_hash: str | None = None
    raw_rows: int = 0
    output_rows: int = 0
    synthetic_rows: int = 0
    synthetic_gap_count: int = 0
    max_synthetic_gap_minutes: int = 0
    synthetic_rows_pct: float = 0.0
    synthetic_gap_threshold_breached: bool = False
    synthetic_gap_threshold_action: str = DEFAULT_SYNTHETIC_GAP_THRESHOLD_ACTION
    outside_session_rows: int = 0
    roll_boundary_rows: int = 0
    roll_window_rows: int = 0
    roll_window_rows_pct: float = 0.0
    roll_window_threshold_breached: bool = False
    roll_window_policy: str = "bar_count"
    roll_window_minutes: int | None = None
    roll_maturity_sequence_available: bool = False
    roll_maturity_backstep_count: int = 0
    roll_maturity_backstep_examples: list[dict[str, object]] = field(default_factory=list)
    boundary_session_rows: int = 0
    causal_valid_rows: int = 0
    causal_invalid_rows: int = 0
    raw_schema_variant: str | None = None
    timestamp_source: str | None = None
    metadata_available: bool = False
    roll_detection_available: bool = False
    roll_detection_source: str = "unavailable"
    roll_policy_status: str = "unavailable_metadata"
    raw_schema_policy: str = "strict"
    required_raw_schema_cols: list[str] = field(default_factory=lambda: STRICT_RAW_COLUMNS.copy())
    raw_schema_missing_cols: list[str] = field(default_factory=list)
    session_calendar_status: str = "hardcoded_regular_session"
    holiday_calendar_available: bool = False
    early_close_calendar_available: bool = False
    calendar_coverage_status: str = "hardcoded_regular_session"
    symbol_nonnull_count: int = 0
    instrument_id_nonnull_count: int = 0
    instrument_id_nunique: int = 0
    raw_enrichment_column_count: int = 0
    raw_enrichment_columns: list[str] = field(default_factory=list)
    status_enrichment_missing_rows: int = 0
    status_enrichment_stale_rows: int = 0
    statistics_enrichment_missing_rows: int = 0
    statistics_enrichment_stale_rows: int = 0
    missing_required_raw_cols: list[str] = field(default_factory=list)
    missing_audit_cols: list[str] = field(default_factory=list)
    duplicate_timestamps: int = 0
    null_ts: int = 0
    invalid_ohlcv_rows: int = 0
    negative_volume_rows: int = 0
    degraded_bar_rows: int = 0
    degraded_session_rows: int = 0
    degraded_rows_pct: float = 0.0
    degraded_threshold_breached: bool = False
    sparse_ohlcv_policy: str = "standard_synthetic_gap_fill"
    sparse_ohlcv_assumption_status: str = "not_applicable"
    sparse_ohlcv_suppressed_synthetic_rows: int = 0
    sparse_ohlcv_suppressed_gap_count: int = 0
    sparse_ohlcv_suppressed_max_gap_minutes: int = 0
    vendor_trusted_ohlcv_no_trade_policy: str = "not_applicable"
    vendor_trusted_ohlcv_no_trade_status: str = "not_applicable"
    max_synthetic_rows_pct_threshold: float = DEFAULT_MAX_SYNTHETIC_ROWS_PCT
    max_synthetic_gap_minutes_threshold: int = DEFAULT_MAX_SYNTHETIC_GAP_MINUTES
    max_degraded_rows_pct_threshold: float = DEFAULT_MAX_DEGRADED_ROWS_PCT
    max_roll_window_rows_pct_threshold: float = DEFAULT_MAX_ROLL_WINDOW_ROWS_PCT
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.failures:
            return "FAIL"
        if self.warnings:
            return "WARN"
        return "PASS"

    def to_dict(self) -> dict[str, object]:
        data = self.__dict__.copy()
        data["status"] = self.status
        data["warning_count"] = len(self.warnings)
        data["failure_count"] = len(self.failures)
        data["roll_boundary_count"] = self.roll_boundary_rows
        data["roll_window_count"] = self.roll_window_rows
        return data

    def to_csv_row(self) -> dict[str, object]:
        data = self.to_dict()
        data["required_raw_schema_cols"] = ";".join(self.required_raw_schema_cols)
        data["raw_schema_missing_cols"] = ";".join(self.raw_schema_missing_cols)
        data["raw_enrichment_columns"] = ";".join(self.raw_enrichment_columns)
        data["missing_required_raw_cols"] = ";".join(self.missing_required_raw_cols)
        data["missing_audit_cols"] = ";".join(self.missing_audit_cols)
        data["warnings"] = ";".join(self.warnings)
        data["failures"] = ";".join(self.failures)
        return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_source_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _evidence_path_exists(path_value: str) -> bool:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.exists()


def _accepted_readiness_exception_for_result(
    result: ValidationResult,
    config: CausalBaseConfig,
) -> dict[str, Any] | None:
    if result.failures or not result.warnings:
        return None
    for exception in config.accepted_readiness_exceptions:
        if exception.market != result.market or exception.year != result.year:
            continue
        if exception.category != ROLL_MATURITY_EXCEPTION_CATEGORY:
            continue
        if not all(
            any(warning.startswith(prefix) for prefix in exception.warning_prefixes)
            for warning in result.warnings
        ):
            continue
        if not all(_evidence_path_exists(path) for path in exception.evidence_paths):
            continue
        return {
            "category": exception.category,
            "reason": exception.reason,
            "evidence_paths": list(exception.evidence_paths),
            "accepted_warnings": list(result.warnings),
        }
    return None


def hash_optional_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return sha256_file(path)


def infer_artifact_root(rows: list[dict[str, object]], key: str) -> Path | None:
    roots: list[Path] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        path = Path(str(value))
        roots.append(path.parent.parent if path.parent != path.parent.parent else path.parent)
    if not roots:
        return None
    return Path(os.path.commonpath([str(root) for root in roots]))


def _local_trade_gate_report_paths(reports_root: Path) -> tuple[Path, Path]:
    return (
        reports_root / LOCAL_TRADE_GAP_AUDIT_JSON,
        reports_root / LOCAL_TRADE_GAP_AUDIT_MD,
    )


def _local_trade_market_gate_statuses(
    report: dict[str, Any],
    selected_markets: Iterable[str],
) -> dict[str, str]:
    entries_by_market: dict[str, list[dict[str, Any]]] = {}
    for entry in report.get("market_years", []):
        if not isinstance(entry, dict):
            continue
        market = str(entry.get("market", ""))
        if market:
            entries_by_market.setdefault(market, []).append(entry)

    preflight = report.get("preflight", {})
    by_schema_market = (
        preflight.get("by_schema_market", {}) if isinstance(preflight, dict) else {}
    )
    statuses: dict[str, str] = {}
    for market in selected_markets:
        schema_rows = []
        if isinstance(by_schema_market, dict):
            for schema_rows_by_market in by_schema_market.values():
                if isinstance(schema_rows_by_market, dict) and market in schema_rows_by_market:
                    schema_rows.append(schema_rows_by_market[market])
        schema_ok = len(schema_rows) >= 3 and all(
            isinstance(row, dict) and row.get("status") == "PASS" for row in schema_rows
        )
        entries = entries_by_market.get(market, [])
        entries_ok = bool(entries) and all(entry.get("status") == "PASS" for entry in entries)
        statuses[market] = "PASS" if schema_ok and entries_ok else "FAIL"
    return statuses


def summarize_local_trade_ohlcv_gap_gate(
    report: dict[str, Any],
    *,
    json_path: Path,
    markdown_path: Path,
    selected_markets: Iterable[str],
) -> dict[str, Any]:
    markets = sorted({str(market) for market in selected_markets})
    market_statuses = _local_trade_market_gate_statuses(report, markets)
    validation_status_by_market = {
        market: (
            LOCAL_TRADE_GAP_VALIDATED_STATUS
            if status == "PASS"
            else LOCAL_TRADE_GAP_FAILED_STATUS
        )
        for market, status in market_statuses.items()
    }
    return {
        "status": str(report.get("status", "FAIL")),
        "method": report.get("method"),
        "profiles": list(LOCAL_TRADE_GAP_AUDIT_PROFILES),
        "selected_markets": markets,
        "window": report.get(
            "window",
            {"start": LOCAL_TRADE_GAP_AUDIT_START, "end": LOCAL_TRADE_GAP_AUDIT_END},
        ),
        "report_paths": {
            "json": relative_source_path(json_path),
            "markdown": relative_source_path(markdown_path),
        },
        "caveat": report.get("caveat"),
        "summary": report.get("summary", {}),
        "market_statuses": market_statuses,
        "validation_status_by_market": validation_status_by_market,
        "failures": report.get("failures", []),
    }


def build_local_trade_ohlcv_gap_gate(
    *,
    markets: Iterable[str],
    raw_root: Path,
    causal_root: Path,
    reports_root: Path,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    dbn_root: Path = LOCAL_TRADE_GAP_AUDIT_DBN_ROOT,
    chunk_size: int = 250_000,
) -> dict[str, Any]:
    selected_markets = sorted({str(market) for market in markets})
    json_path, markdown_path = _local_trade_gate_report_paths(reports_root)
    if not selected_markets:
        return {
            "status": "PASS",
            "method": "local trades DBN cross-check of OHLCV synthetic missing minutes",
            "profiles": list(LOCAL_TRADE_GAP_AUDIT_PROFILES),
            "selected_markets": [],
            "window": {
                "start": f"{LOCAL_TRADE_GAP_AUDIT_START}T00:00:00Z",
                "end": f"{LOCAL_TRADE_GAP_AUDIT_END}T00:00:00Z",
            },
            "report_paths": {
                "json": relative_source_path(json_path),
                "markdown": relative_source_path(markdown_path),
            },
            "caveat": "No selected markets were available for local-trades gap validation.",
            "summary": {},
            "market_statuses": {},
            "validation_status_by_market": {},
            "failures": [],
        }

    args = argparse.Namespace(
        profile_config=str(profile_config_path),
        profiles=list(LOCAL_TRADE_GAP_AUDIT_PROFILES),
        markets=selected_markets,
        start=LOCAL_TRADE_GAP_AUDIT_START,
        end=LOCAL_TRADE_GAP_AUDIT_END,
        dbn_root=str(dbn_root),
        raw_root=str(raw_root),
        causal_root=str(causal_root),
        json_out=str(json_path),
        md_out=str(markdown_path),
        chunk_size=chunk_size,
        max_gap_windows=None,
        inventory_only=False,
    )
    report = build_local_trade_gap_report(args)
    write_local_trade_gap_json_report(report, json_path)
    write_local_trade_gap_markdown_report(report, markdown_path)
    return summarize_local_trade_ohlcv_gap_gate(
        report,
        json_path=json_path,
        markdown_path=markdown_path,
        selected_markets=selected_markets,
    )


def _local_trade_validation_status_for_market(
    local_trade_gap_gate: dict[str, Any] | None,
    market: str,
) -> str:
    if local_trade_gap_gate is None:
        return LOCAL_TRADE_GAP_NOT_RUN_STATUS
    validation_status_by_market = local_trade_gap_gate.get("validation_status_by_market", {})
    if not isinstance(validation_status_by_market, dict):
        return LOCAL_TRADE_GAP_FAILED_STATUS
    return str(validation_status_by_market.get(market, LOCAL_TRADE_GAP_NOT_IN_SCOPE_STATUS))


def _with_local_trade_validation_fields(
    row: dict[str, object],
    local_trade_gap_gate: dict[str, Any] | None,
) -> dict[str, object]:
    enriched = row.copy()
    market = str(row.get("market", ""))
    report_paths = (
        local_trade_gap_gate.get("report_paths", {})
        if isinstance(local_trade_gap_gate, dict)
        else {}
    )
    enriched["local_trade_gap_validation_status"] = (
        _local_trade_validation_status_for_market(local_trade_gap_gate, market)
    )
    enriched["local_trade_gap_gate_status"] = (
        str(local_trade_gap_gate.get("status", "NOT_RUN"))
        if isinstance(local_trade_gap_gate, dict)
        else "NOT_RUN"
    )
    enriched["local_trade_gap_gate_window"] = (
        local_trade_gap_gate.get("window") if isinstance(local_trade_gap_gate, dict) else None
    )
    enriched["local_trade_gap_gate_report_json"] = (
        report_paths.get("json") if isinstance(report_paths, dict) else None
    )
    enriched["local_trade_gap_gate_caveat"] = (
        local_trade_gap_gate.get("caveat") if isinstance(local_trade_gap_gate, dict) else None
    )
    return enriched


def phase2_exit_code(
    results: Iterable[ValidationResult],
    local_trade_gap_gate: dict[str, Any] | None = None,
) -> int:
    if any(result.failures for result in results):
        return 1
    if local_trade_gap_gate is not None and local_trade_gap_gate.get("status") != "PASS":
        return 1
    return 0


def profile_requires_local_trade_gap_gate(
    profile: str,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
) -> bool:
    _, _, aliases, _ = load_profile_map(profile_config_path)
    resolved_profile = resolve_profile_name(profile, aliases)
    return resolved_profile in LOCAL_TRADE_GAP_AUDIT_PROFILES


def current_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    commit = result.stdout.strip()
    if result.returncode != 0 or not commit:
        return "unknown"
    return commit


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_yaml(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML config must be a mapping: {path}")
    return payload


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be a mapping: {path}")
    return payload


def _as_mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _as_nonempty_str_list(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    items = tuple(str(item).strip() for item in value if str(item).strip())
    if not items:
        raise ValueError(f"{field_name} must contain at least one value")
    return items


def _parse_accepted_readiness_exceptions(
    value: object,
) -> tuple[AcceptedReadinessException, ...]:
    if value in (None, ""):
        return tuple()
    if not isinstance(value, list):
        raise ValueError("accepted_readiness_exceptions must be a list")

    exceptions: list[AcceptedReadinessException] = []
    for index, raw_entry in enumerate(value):
        entry = _as_mapping(raw_entry)
        if not entry:
            raise ValueError(
                f"accepted_readiness_exceptions[{index}] must be a mapping"
            )
        category = str(entry.get("category", "")).strip()
        if category != ROLL_MATURITY_EXCEPTION_CATEGORY:
            raise ValueError(
                "accepted_readiness_exceptions only supports category "
                f"{ROLL_MATURITY_EXCEPTION_CATEGORY!r}"
            )
        market = str(entry.get("market", "")).strip()
        if not market:
            raise ValueError(
                f"accepted_readiness_exceptions[{index}].market is required"
            )
        try:
            year = int(entry["year"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"accepted_readiness_exceptions[{index}].year must be an integer"
            ) from exc
        reason = str(entry.get("reason", "")).strip()
        if not reason:
            raise ValueError(
                f"accepted_readiness_exceptions[{index}].reason is required"
            )
        evidence_paths = _as_nonempty_str_list(
            entry.get("evidence_paths", entry.get("evidence")),
            field_name=f"accepted_readiness_exceptions[{index}].evidence_paths",
        )
        warning_prefixes = _as_nonempty_str_list(
            entry.get(
                "warning_prefixes",
                list(ROLL_MATURITY_EXCEPTION_WARNING_PREFIXES),
            ),
            field_name=f"accepted_readiness_exceptions[{index}].warning_prefixes",
        )
        exceptions.append(
            AcceptedReadinessException(
                market=market,
                year=year,
                category=category,
                reason=reason,
                evidence_paths=evidence_paths,
                warning_prefixes=warning_prefixes,
            )
        )
    return tuple(exceptions)


def load_causal_base_config(
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    profile: str = DEFAULT_PROFILE,
) -> CausalBaseConfig:
    payload = _read_yaml(profile_config_path)
    defaults = _as_mapping(payload.get("defaults", {}))
    causal_base = _as_mapping(payload.get("causal_base", {}))
    aliases = _as_mapping(payload.get("aliases", {}))
    resolved_profile = resolve_profile_name(profile, {str(k): str(v) for k, v in aliases.items()})
    profiles = _as_mapping(payload.get("profiles", {}))
    profile_config = _as_mapping(profiles.get(resolved_profile, {}))
    settings_profile = str(profile_config.get("settings_profile", ""))
    profile_defaults = _as_mapping(payload.get("profile_defaults", {}))
    settings_defaults = _as_mapping(profile_defaults.get(settings_profile, {}))

    def get_value(name: str, default: object) -> object:
        if name in causal_base:
            return causal_base[name]
        if name in defaults:
            return defaults[name]
        if name in settings_defaults:
            return settings_defaults[name]
        return default

    def get_float(name: str, default: float) -> float:
        return float(get_value(name, default))

    def get_int(name: str, default: int) -> int:
        return int(get_value(name, default))

    def get_str(name: str, default: str) -> str:
        return str(get_value(name, default))

    required = causal_base.get(
        "require_roll_metadata_for_profiles",
        defaults.get("require_roll_metadata_for_profiles", sorted(DEFAULT_REQUIRE_ROLL_METADATA_PROFILES)),
    )
    if not isinstance(required, list):
        required = sorted(DEFAULT_REQUIRE_ROLL_METADATA_PROFILES)
    synthetic_gap_threshold_action = get_str(
        "synthetic_gap_threshold_action",
        DEFAULT_SYNTHETIC_GAP_THRESHOLD_ACTION,
    )
    if synthetic_gap_threshold_action not in SYNTHETIC_GAP_THRESHOLD_ACTIONS:
        raise ValueError(
            "synthetic_gap_threshold_action must be one of "
            f"{sorted(SYNTHETIC_GAP_THRESHOLD_ACTIONS)}"
        )

    return CausalBaseConfig(
        max_synthetic_rows_pct=get_float(
            "max_synthetic_rows_pct", DEFAULT_MAX_SYNTHETIC_ROWS_PCT
        ),
        max_synthetic_gap_minutes=get_int(
            "max_synthetic_gap_minutes", DEFAULT_MAX_SYNTHETIC_GAP_MINUTES
        ),
        synthetic_gap_threshold_action=synthetic_gap_threshold_action,
        max_degraded_rows_pct=get_float(
            "max_degraded_rows_pct", DEFAULT_MAX_DEGRADED_ROWS_PCT
        ),
        max_roll_window_rows_pct=get_float(
            "max_roll_window_rows_pct", DEFAULT_MAX_ROLL_WINDOW_ROWS_PCT
        ),
        sparse_trade_derived_ohlcv_markets=tuple(
            sorted(
                {
                    str(item)
                    for item in (
                        causal_base.get(
                            "sparse_trade_derived_ohlcv_markets",
                            defaults.get("sparse_trade_derived_ohlcv_markets", []),
                        )
                        or []
                    )
                }
            )
        ),
        sparse_trade_derived_roll_window_minutes=int(
            causal_base.get(
                "sparse_trade_derived_roll_window_minutes",
                defaults.get(
                    "sparse_trade_derived_roll_window_minutes",
                    DEFAULT_ROLL_WINDOW_BARS,
                ),
            )
        ),
        vendor_trusted_ohlcv_no_trade_markets=tuple(
            sorted(
                {
                    str(item)
                    for item in (
                        causal_base.get(
                            "vendor_trusted_ohlcv_no_trade_markets",
                            defaults.get("vendor_trusted_ohlcv_no_trade_markets", []),
                        )
                        or []
                    )
                }
            )
        ),
        require_roll_metadata_for_profiles=tuple(str(item) for item in required),
        accepted_readiness_exceptions=_parse_accepted_readiness_exceptions(
            profile_config.get(
                "accepted_readiness_exceptions",
                causal_base.get(
                    "accepted_readiness_exceptions",
                    defaults.get("accepted_readiness_exceptions", []),
                ),
            )
        ),
    )


def load_profile_map(profile_config_path: Path = DEFAULT_PROFILE_CONFIG) -> tuple[
    dict[str, list[str]], dict[str, list[int]], dict[str, str], set[str]
]:
    markets = {key: value[:] for key, value in STATIC_PROFILE_MARKETS.items()}
    years = {key: value[:] for key, value in STATIC_PROFILE_YEARS.items()}
    aliases: dict[str, str] = {}
    discovery = set(DISCOVERY_PROFILES)

    payload = _read_yaml(profile_config_path)
    if not payload:
        aliases.update(STATIC_PROFILE_ALIASES)
    raw_aliases = payload.get("aliases", {})
    if isinstance(raw_aliases, dict):
        aliases.update({str(k): str(v) for k, v in raw_aliases.items()})
    profiles = payload.get("profiles", {})
    if isinstance(profiles, dict):
        default_years = payload.get("defaults", {}).get("years", []) if isinstance(payload.get("defaults", {}), dict) else []
        for name, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            profile_name = str(name)
            if profile.get("discovery"):
                discovery.add(profile_name)
                continue
            profile_markets = profile.get("markets", [])
            profile_years = profile.get("years", default_years)
            if isinstance(profile_markets, list) and isinstance(profile_years, list):
                markets[profile_name] = [str(item) for item in profile_markets]
                years[profile_name] = [int(item) for item in profile_years]

    return markets, years, aliases, discovery


def resolve_profile_name(profile: str, aliases: dict[str, str]) -> str:
    seen: set[str] = set()
    resolved = profile
    while resolved in aliases and resolved not in seen:
        seen.add(resolved)
        resolved = aliases[resolved]
    return resolved


def raw_schema_policy_for_profile(resolved_profile: str) -> str:
    if resolved_profile in RELAXED_RAW_SCHEMA_PROFILES:
        return "relaxed"
    return "strict"


def required_raw_schema_cols_for_policy(policy: str) -> list[str]:
    if policy == "relaxed":
        return REQUIRED_OHLCV_COLUMNS.copy()
    return STRICT_RAW_COLUMNS.copy()


def strict_raw_value_failures(raw: pd.DataFrame, required_raw_cols: list[str]) -> list[str]:
    failed = [col for col in required_raw_cols if col in raw.columns and raw[col].isna().any()]
    if "symbol" in raw.columns:
        blank_symbols = raw["symbol"].astype("string").str.strip().eq("").fillna(False)
        if bool(blank_symbols.any()) and "symbol" not in failed:
            failed.append("symbol")
    return failed


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.split(":", 1)
    return int(hour_text), int(minute_text)


def load_session_calendar(
    market: str,
    config_path: Path = DEFAULT_SESSION_CONFIG,
    *,
    allow_hardcoded_calendar: bool = False,
) -> SessionCalendar:
    if not config_path.exists():
        if not allow_hardcoded_calendar:
            raise FileNotFoundError(
                f"Session calendar config missing: {config_path}. "
                "Use --allow-hardcoded-calendar only for tests."
            )
        return SessionCalendar(source="hardcoded_regular_session", config_available=False)

    payload = _read_yaml(config_path)
    markets = payload.get("markets", {})
    templates = payload.get("session_templates", {})
    if not isinstance(markets, dict) or not isinstance(templates, dict):
        raise ValueError("market_sessions.yaml requires markets and session_templates mappings")

    market_cfg = markets.get(market, markets.get("default", {}))
    if not isinstance(market_cfg, dict):
        market_cfg = {}
    template_name = str(market_cfg.get("session_template", SESSION_TEMPLATE))
    template = templates.get(template_name)
    if not isinstance(template, dict):
        raise ValueError(f"Missing session template {template_name!r} for {market}")

    holidays = template.get("holidays", [])
    closed_dates = template.get("closed_dates", [])
    early_closes = template.get("early_closes", {})
    if not isinstance(holidays, list):
        holidays = []
    if not isinstance(closed_dates, list):
        closed_dates = []
    if not isinstance(early_closes, dict):
        early_closes = {}

    return SessionCalendar(
        session_template=template_name,
        timezone=str(template.get("timezone", EXCHANGE_TZ)),
        regular_open=str(template.get("regular_open", "17:00")),
        regular_close=str(template.get("regular_close", "16:00")),
        intraday_breaks=_parse_intraday_breaks(
            market_cfg.get("intraday_breaks", template.get("intraday_breaks", []))
        ),
        holidays=frozenset(str(item) for item in holidays),
        closed_dates=frozenset(str(item) for item in closed_dates),
        early_closes={str(k): str(v) for k, v in early_closes.items()},
        source=relative_source_path(config_path),
        config_available=True,
    )


def _parse_intraday_breaks(raw_breaks: object) -> tuple[tuple[str, str], ...]:
    breaks: list[tuple[str, str]] = []
    if not isinstance(raw_breaks, list):
        return tuple()
    for item in raw_breaks:
        if isinstance(item, dict):
            start = item.get("start")
            end = item.get("end")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            start, end = item
        else:
            continue
        if start is None or end is None:
            continue
        breaks.append((str(start), str(end)))
    return tuple(breaks)


def discover_raw_inputs(raw_root: Path) -> list[tuple[str, int, Path]]:
    """Discover top-level data/raw/{market}/{year}.parquet files only."""
    if not raw_root.exists():
        raise SystemExit(f"Raw root does not exist: {raw_root}")

    inputs: list[tuple[str, int, Path]] = []
    for market_dir in sorted(path for path in raw_root.iterdir() if path.is_dir()):
        for parquet_path in sorted(market_dir.glob("*.parquet")):
            if not parquet_path.stem.isdigit():
                continue
            inputs.append((market_dir.name, int(parquet_path.stem), parquet_path))

    if not inputs:
        raise SystemExit(f"No raw year parquet files found under {raw_root}")
    return inputs


def resolve_profile_inputs(
    profile: str,
    raw_root: Path,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
) -> list[tuple[str, int, Path]]:
    profile_markets, profile_years, aliases, discovery_profiles = load_profile_map(
        profile_config_path
    )
    resolved_profile = resolve_profile_name(profile, aliases)
    if resolved_profile in discovery_profiles:
        return discover_raw_inputs(raw_root)

    if resolved_profile not in profile_markets:
        known = ", ".join(sorted([*profile_markets, *discovery_profiles]))
        raise SystemExit(f"Unknown profile {profile!r}. Known profiles: {known}")

    inputs: list[tuple[str, int, Path]] = []
    for market in profile_markets[resolved_profile]:
        for year in profile_years[resolved_profile]:
            inputs.append((market, year, raw_root / market / f"{year}.parquet"))
    return inputs


def raw_alignment_guard_failures(
    *,
    report_path: Path,
    raw_root: Path,
    profile: str,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
) -> list[str]:
    if not report_path.exists():
        return [f"raw alignment report missing: {relative_source_path(report_path)}"]

    try:
        report = _read_json(report_path)
    except Exception as exc:
        return [f"raw alignment report unreadable: {exc}"]

    profile_markets, profile_years, aliases, discovery_profiles = load_profile_map(
        profile_config_path
    )
    del profile_markets, profile_years, discovery_profiles
    resolved_profile = resolve_profile_name(profile, aliases)
    failures: list[str] = []

    if report.get("stage") != "raw_dbn_alignment_audit":
        failures.append("raw alignment report stage is not raw_dbn_alignment_audit")
    if report.get("status") != "PASS":
        failures.append(f"raw alignment report status is {report.get('status')!r}, not PASS")
    if report.get("audit_completeness") != "full":
        failures.append("raw alignment report audit_completeness is not full")
    if report.get("definition_join_status") != "checked":
        failures.append("raw alignment report definition_join_status is not checked")

    report_raw_root = report.get("raw_root")
    if not isinstance(report_raw_root, str) or not report_raw_root:
        failures.append("raw alignment report raw_root missing")
    else:
        if (Path.cwd() / report_raw_root).resolve() != raw_root.resolve():
            failures.append(
                "raw alignment report raw_root does not match Phase 2 raw_root: "
                f"{report_raw_root} != {relative_source_path(raw_root)}"
            )

    report_profile = str(report.get("profile", ""))
    report_resolved_profile = str(report.get("resolved_profile", ""))
    if report_profile != profile and report_resolved_profile != resolved_profile:
        failures.append(
            "raw alignment report profile does not match Phase 2 profile: "
            f"{report_profile}/{report_resolved_profile} != {profile}/{resolved_profile}"
        )

    zero_count_fields = [
        "missing_raw_count",
        "needs_phase1b_conversion_count",
        "missing_ohlcv_dbn_count",
        "missing_definition_dbn_count",
        "invalid_manifest_count",
        "raw_schema_failure_count",
        "source_hash_mismatch_count",
        "definition_join_mismatch_count",
    ]
    for field_name in zero_count_fields:
        value = report.get(field_name)
        if value != 0:
            failures.append(f"raw alignment report {field_name} is {value}, not 0")
    return failures


def raw_alignment_expected_market_years(report: dict[str, Any]) -> set[tuple[str, int]]:
    explicit_pairs: set[tuple[str, int]] = set()
    for item in report.get("market_years", []):
        try:
            if isinstance(item, dict):
                explicit_pairs.add((str(item["market"]), int(item["year"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                explicit_pairs.add((str(item[0]), int(item[1])))
        except (KeyError, TypeError, ValueError):
            continue
    markets = [str(market) for market in report.get("markets", [])]
    years = [int(year) for year in report.get("years", [])]
    exemptions: set[tuple[str, int]] = set()
    for item in report.get("pre_availability_exemptions", []):
        try:
            if isinstance(item, dict):
                exemptions.add((str(item["market"]), int(item["year"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                exemptions.add((str(item[0]), int(item[1])))
        except (KeyError, TypeError, ValueError):
            continue
    expected = explicit_pairs if explicit_pairs else {
        (market, year) for market in markets for year in years
    }
    return expected - exemptions


def filter_inputs_by_raw_alignment(
    inputs: Iterable[tuple[str, int, Path]],
    raw_alignment: dict[str, Any],
) -> tuple[list[tuple[str, int, Path]], list[tuple[str, int]]]:
    expected_pairs = raw_alignment_expected_market_years(raw_alignment)
    inputs_list = list(inputs)
    if not expected_pairs:
        return inputs_list, []
    input_pairs = {(market, year) for market, year, _ in inputs_list}
    selected = [
        (market, year, path)
        for market, year, path in inputs_list
        if (market, year) in expected_pairs
    ]
    return selected, sorted(expected_pairs - input_pairs)


def infer_market_year(path: Path) -> tuple[str, int]:
    try:
        return path.parent.name, int(path.stem)
    except ValueError as exc:
        raise ValueError(f"Cannot infer market/year from {path}") from exc


def _session_metadata(ts: pd.Series, calendar: SessionCalendar | None = None) -> pd.DataFrame:
    calendar = calendar or SessionCalendar()
    local = ts.dt.tz_convert(calendar.timezone)
    dow = local.dt.dayofweek
    minutes = local.dt.hour * 60 + local.dt.minute
    open_hour, open_minute = _parse_hhmm(calendar.regular_open)
    close_hour, close_minute = _parse_hhmm(calendar.regular_close)
    open_minutes = open_hour * 60 + open_minute
    close_minutes = close_hour * 60 + close_minute

    after_open = minutes >= open_minutes
    before_close = minutes < close_minutes

    local_midnight = local.dt.normalize().dt.tz_localize(None)
    session_date = local_midnight.where(before_close, local_midnight + pd.Timedelta(days=1))
    session_date = pd.to_datetime(session_date.dt.date)

    session_date_str = session_date.dt.strftime("%Y-%m-%d")
    close_times = session_date_str.map(calendar.early_closes).fillna(calendar.regular_close)
    close_parts = close_times.str.split(":", n=1, expand=True).astype(int)

    open_naive = (
        session_date
        - pd.Timedelta(days=1)
        + pd.to_timedelta(open_hour, unit="h")
        + pd.to_timedelta(open_minute, unit="m")
    )
    close_naive = (
        session_date
        + pd.to_timedelta(close_parts[0], unit="h")
        + pd.to_timedelta(close_parts[1], unit="m")
    )
    open_local = open_naive.dt.tz_localize(calendar.timezone)
    close_local = close_naive.dt.tz_localize(calendar.timezone)

    trade_date_open = session_date.dt.dayofweek.isin([0, 1, 2, 3, 4])
    closed = session_date_str.isin(calendar.holidays | calendar.closed_dates)
    inside = (local >= open_local) & (local < close_local) & trade_date_open & ~closed
    if calendar.intraday_breaks:
        in_break = pd.Series(False, index=ts.index)
        for break_start, break_end in calendar.intraday_breaks:
            break_start_hour, break_start_minute = _parse_hhmm(break_start)
            break_end_hour, break_end_minute = _parse_hhmm(break_end)
            break_start_minutes = break_start_hour * 60 + break_start_minute
            break_end_minutes = break_end_hour * 60 + break_end_minute
            if break_start_minutes <= break_end_minutes:
                break_mask = (minutes >= break_start_minutes) & (minutes < break_end_minutes)
            else:
                break_mask = (minutes >= break_start_minutes) | (minutes < break_end_minutes)
            in_break = in_break | break_mask
        inside = inside & ~in_break

    since_open = (local - open_local).dt.total_seconds() / 60.0
    until_close = (close_local - local).dt.total_seconds() / 60.0
    denom = since_open + until_close
    progress = np.where(denom > 0, since_open / denom, np.nan)

    session_id = session_date_str.where(inside, pd.NA)

    metadata = pd.DataFrame(
        {
            "inside_session": inside.astype(bool),
            "session_date": session_date_str.where(inside, pd.NA),
            "session_id": session_id.where(session_id.isna(), "session_" + session_id),
            "session_template": np.where(inside, calendar.session_template, pd.NA),
            "minutes_since_session_open": np.where(inside, since_open, np.nan),
            "minutes_until_session_close": np.where(inside, until_close, np.nan),
            "session_progress": np.where(inside, progress, np.nan),
            "minute_of_day": minutes.astype("int64"),
            "day_of_week": dow.astype("int64"),
        },
        index=ts.index,
    )
    return metadata


def _valid_ohlcv(df: pd.DataFrame) -> pd.Series:
    price_cols = ["open", "high", "low", "close"]
    prices = df[price_cols].apply(pd.to_numeric, errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")
    return (
        prices.notna().all(axis=1)
        & volume.notna()
        & (prices["high"] >= prices["low"])
        & (prices["open"] <= prices["high"])
        & (prices["open"] >= prices["low"])
        & (prices["close"] <= prices["high"])
        & (prices["close"] >= prices["low"])
        & (volume >= 0)
    )


def _timestamp_from_raw(raw: pd.DataFrame) -> tuple[pd.Series | None, str | None]:
    if "ts_event" in raw.columns:
        return pd.to_datetime(raw["ts_event"], utc=True, errors="coerce"), "ts_event_column"
    if isinstance(raw.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(raw.index, utc=True, errors="coerce"), index=raw.index), "dataframe_index"
    return None, None


def _schema_variant(raw: pd.DataFrame, timestamp_source: str) -> str:
    metadata_cols_present = all(col in raw.columns for col in AUDIT_RAW_COLUMNS)
    if metadata_cols_present and timestamp_source == "ts_event_column":
        return "databento_full"
    if metadata_cols_present and timestamp_source == "dataframe_index":
        return "metadata_no_ts_event"
    return "ohlcv_only"


def _prepare_raw_frame(
    input_path: Path,
    *,
    market: str,
    year: int,
    result: ValidationResult | None,
    required: bool,
    raw_schema_policy: str = "relaxed",
) -> pd.DataFrame | None:
    if not input_path.exists():
        if required and result is not None:
            result.failures.append("input file missing")
        return None

    source_hash = sha256_file(input_path)
    raw = pd.read_parquet(input_path)
    if required and result is not None:
        result.source_file_hash = source_hash
        result.raw_rows = len(raw)
    if raw.empty:
        if required and result is not None:
            result.failures.append("empty file")
        return None

    required_raw_cols = required_raw_schema_cols_for_policy(raw_schema_policy)
    missing_required = [c for c in required_raw_cols if c not in raw.columns]
    if missing_required:
        if required and result is not None:
            result.missing_required_raw_cols = missing_required
            result.raw_schema_missing_cols = missing_required
            result.failures.append(
                "missing required raw schema columns: " + ", ".join(missing_required)
            )
        return None
    if raw_schema_policy == "strict":
        invalid_required = strict_raw_value_failures(raw, required_raw_cols)
        if invalid_required:
            if required and result is not None:
                result.missing_required_raw_cols = invalid_required
                result.failures.append(
                    "null or blank required raw schema columns: "
                    + ", ".join(invalid_required)
                )
            return None

    ts, timestamp_source = _timestamp_from_raw(raw)
    if ts is None or timestamp_source is None:
        if required and result is not None:
            result.failures.append("missing timestamp source")
        return None

    raw_schema_variant = _schema_variant(raw, timestamp_source)
    missing_audit = [c for c in AUDIT_RAW_COLUMNS if c not in raw.columns]
    raw = raw.copy()
    for col in missing_audit:
        raw[col] = pd.NA

    raw["source_row_number"] = np.arange(len(raw), dtype=np.int64)
    raw["ts"] = pd.DatetimeIndex(ts)
    raw = raw.reset_index(drop=True)
    null_ts = int(raw["ts"].isna().sum())
    if null_ts:
        if required and result is not None:
            result.null_ts = null_ts
            result.failures.append("null or unparseable timestamp")
        return None

    duplicate_timestamps = int(raw["ts"].duplicated().sum())
    if duplicate_timestamps:
        if required and result is not None:
            result.duplicate_timestamps = duplicate_timestamps
            result.failures.append("duplicate ts_event rows")
        return None

    raw["valid_ohlcv"] = _valid_ohlcv(raw)
    invalid_ohlcv_rows = int((~raw["valid_ohlcv"]).sum())
    if invalid_ohlcv_rows:
        if required and result is not None:
            result.invalid_ohlcv_rows = invalid_ohlcv_rows
            result.failures.append("invalid OHLCV rows")
        return None

    volume = pd.to_numeric(raw["volume"], errors="coerce")
    negative_volume_rows = int((volume < 0).sum())
    if negative_volume_rows:
        if required and result is not None:
            result.negative_volume_rows = negative_volume_rows
            result.failures.append("negative volume rows")
        return None

    if "data_quality_status" not in raw.columns:
        raw["data_quality_status"] = "unknown"
        if required and result is not None:
            result.warnings.append("missing data_quality_status; assuming trainable data quality")
    else:
        raw["data_quality_status"] = raw["data_quality_status"].fillna("unknown").astype(str)

    if "data_quality_degraded" not in raw.columns:
        raw["data_quality_degraded"] = False
        if required and result is not None:
            result.warnings.append("missing data_quality_degraded; assuming no degraded bars")
    else:
        raw["data_quality_degraded"] = raw["data_quality_degraded"].fillna(False).astype(bool)

    if required and result is not None:
        result.timestamp_source = timestamp_source
        result.raw_schema_variant = raw_schema_variant
        result.missing_audit_cols = missing_audit
        if missing_audit:
            result.warnings.append("missing optional Databento audit metadata columns")
        result.symbol_nonnull_count = int(raw["symbol"].notna().sum())
        result.instrument_id_nonnull_count = int(raw["instrument_id"].notna().sum())
        result.instrument_id_nunique = int(raw["instrument_id"].dropna().nunique())
        result.degraded_bar_rows = int(raw["data_quality_degraded"].sum())
        non_integer_volume = int(((volume.dropna() % 1) != 0).sum())
        if non_integer_volume:
            result.warnings.append(f"non-integer-like volume rows={non_integer_volume}")

    raw = raw.sort_values("ts", kind="mergesort").reset_index(drop=True)
    raw["market"] = market
    raw["year"] = year
    raw["raw_row_present"] = True
    raw["is_synthetic"] = False
    raw["synthetic_gap_id"] = pd.NA
    raw["synthetic_gap_size_minutes"] = pd.NA
    raw["synthetic_gap_reason"] = pd.NA
    raw["source_path"] = relative_source_path(input_path)
    raw["source_file_hash"] = source_hash
    raw["raw_schema_variant"] = raw_schema_variant
    raw["timestamp_source"] = timestamp_source
    return raw


def _build_synthetic_rows(
    df: pd.DataFrame,
    max_gap_minutes: int,
    calendar: SessionCalendar,
) -> pd.DataFrame:
    inside = df[df["inside_session"]].sort_values("ts")
    if len(inside) < 2:
        return pd.DataFrame(columns=df.columns)

    prev_rows = inside.iloc[:-1]
    next_rows = inside.iloc[1:]
    gaps = (next_rows["ts"].to_numpy() - prev_rows["ts"].to_numpy()).astype(
        "timedelta64[m]"
    ).astype(int)
    same_session = (
        prev_rows["session_id"].to_numpy(dtype=object)
        == next_rows["session_id"].to_numpy(dtype=object)
    )
    candidate_mask = same_session & (gaps > 1) & (gaps <= max_gap_minutes)
    if not candidate_mask.any():
        return pd.DataFrame(columns=df.columns)

    prev_instruments = prev_rows["instrument_id"].to_numpy(dtype=object)
    next_instruments = next_rows["instrument_id"].to_numpy(dtype=object)
    both_instruments_known = pd.notna(prev_instruments) & pd.notna(next_instruments)
    instrument_changed = both_instruments_known & (prev_instruments != next_instruments)
    candidate_mask &= ~instrument_changed & prev_rows["close"].notna().to_numpy()
    if not candidate_mask.any():
        return pd.DataFrame(columns=df.columns)

    candidate_positions = np.flatnonzero(candidate_mask)
    candidates = prev_rows.iloc[candidate_positions].reset_index(drop=True)
    candidate_gaps = gaps[candidate_mask]
    repeat_counts = candidate_gaps - 1
    repeated_positions = np.repeat(np.arange(len(candidates)), repeat_counts)
    if len(repeated_positions) == 0:
        return pd.DataFrame(columns=df.columns)

    offset_minutes = np.concatenate(
        [np.arange(1, int(gap), dtype=np.int64) for gap in candidate_gaps]
    )
    base_ts = candidates["ts"].iloc[repeated_positions].reset_index(drop=True)
    synthetic_ts = base_ts + pd.to_timedelta(offset_minutes, unit="m")

    def repeated_values(column: str) -> np.ndarray:
        return candidates[column].to_numpy()[repeated_positions]

    close_values = repeated_values("close")
    synth_df = pd.DataFrame(
        {
            "ts": synthetic_ts,
            "_candidate_gap_id": np.repeat(
                np.arange(1, len(candidates) + 1, dtype=np.int64), repeat_counts
            ),
            "market": repeated_values("market"),
            "year": synthetic_ts.dt.year.to_numpy(dtype=np.int64),
            "symbol": repeated_values("symbol"),
            "instrument_id": repeated_values("instrument_id"),
            "publisher_id": repeated_values("publisher_id"),
            "rtype": repeated_values("rtype"),
            "open": close_values,
            "high": close_values,
            "low": close_values,
            "close": close_values,
            "volume": np.zeros(len(repeated_positions), dtype=np.int64),
            "raw_row_present": False,
            "is_synthetic": True,
            "synthetic_gap_id": pd.NA,
            "synthetic_gap_size_minutes": np.repeat(candidate_gaps, repeat_counts),
            "synthetic_gap_reason": "missing_in_session_minute",
            "valid_ohlcv": True,
            "data_quality_status": repeated_values("data_quality_status"),
            "data_quality_degraded": repeated_values("data_quality_degraded"),
            "source_path": repeated_values("source_path"),
            "source_file_hash": repeated_values("source_file_hash"),
            "source_row_number": pd.NA,
            "raw_schema_variant": repeated_values("raw_schema_variant"),
            "timestamp_source": repeated_values("timestamp_source"),
            "metadata_available": repeated_values("metadata_available"),
            "roll_detection_available": repeated_values("roll_detection_available"),
            "roll_detection_source": repeated_values("roll_detection_source"),
            "roll_policy_status": repeated_values("roll_policy_status"),
            "session_calendar_status": repeated_values("session_calendar_status"),
            "holiday_calendar_available": repeated_values("holiday_calendar_available"),
            "early_close_calendar_available": repeated_values("early_close_calendar_available"),
            "calendar_coverage_status": repeated_values("calendar_coverage_status"),
        }
    )
    synth_meta = _session_metadata(synth_df["ts"], calendar)
    inside_missing = synth_meta["inside_session"].fillna(False).astype(bool)
    if not inside_missing.any():
        return pd.DataFrame(columns=df.columns)
    synth_df = synth_df.loc[inside_missing].reset_index(drop=True)
    synth_meta = synth_meta.loc[inside_missing].reset_index(drop=True)
    gap_ids = pd.unique(synth_df["_candidate_gap_id"])
    remapped_gap_ids = {gap_id: idx for idx, gap_id in enumerate(gap_ids, start=1)}
    synth_df["synthetic_gap_id"] = (
        synth_df["_candidate_gap_id"].map(remapped_gap_ids).astype("Int64")
    )
    synth_df = synth_df.drop(columns=["_candidate_gap_id"])
    return pd.concat([synth_df, synth_meta], axis=1)


def _clip_previous_context(
    raw: pd.DataFrame,
    *,
    year_start: pd.Timestamp,
    context_rows: int,
) -> pd.DataFrame:
    lower_bound = year_start - pd.Timedelta(days=CONTEXT_PADDING_DAYS)
    selected = raw.index[raw["ts"].ge(lower_bound)].union(raw.tail(context_rows).index)
    return raw.loc[selected].sort_values("ts", kind="mergesort").reset_index(drop=True)


def _clip_next_context(
    raw: pd.DataFrame,
    *,
    year_end: pd.Timestamp,
    context_rows: int,
) -> pd.DataFrame:
    upper_bound = year_end + pd.Timedelta(days=CONTEXT_PADDING_DAYS)
    selected = raw.index[raw["ts"].lt(upper_bound)].union(raw.head(context_rows).index)
    return raw.loc[selected].sort_values("ts", kind="mergesort").reset_index(drop=True)


def _roll_maturity_backsteps(raw: pd.DataFrame) -> tuple[bool, int, list[dict[str, object]]]:
    required = {"ts", "instrument_id", "raw_symbol", "maturity_year", "maturity_month"}
    if not required.issubset(raw.columns):
        return False, 0, []

    frame = raw.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    maturity_year = pd.to_numeric(frame["maturity_year"], errors="coerce")
    maturity_month = pd.to_numeric(frame["maturity_month"], errors="coerce")
    maturity_ordinal = maturity_year * 12 + maturity_month
    valid = maturity_ordinal.notna() & frame["instrument_id"].notna()
    if not bool(valid.any()):
        return False, 0, []

    instrument_changed = frame["instrument_id"].ne(frame["instrument_id"].shift(1))
    backstep = valid & valid.shift(1, fill_value=False) & instrument_changed & (
        maturity_ordinal < maturity_ordinal.shift(1)
    )
    examples: list[dict[str, object]] = []
    for idx in frame.index[backstep][:5]:
        previous = frame.loc[idx - 1]
        current = frame.loc[idx]
        examples.append(
            {
                "ts": current["ts"].isoformat() if hasattr(current["ts"], "isoformat") else str(current["ts"]),
                "previous_raw_symbol": str(previous.get("raw_symbol")),
                "current_raw_symbol": str(current.get("raw_symbol")),
                "previous_instrument_id": (
                    int(previous["instrument_id"])
                    if pd.notna(previous["instrument_id"])
                    else None
                ),
                "current_instrument_id": (
                    int(current["instrument_id"])
                    if pd.notna(current["instrument_id"])
                    else None
                ),
                "previous_maturity": (
                    int(maturity_ordinal.loc[idx - 1])
                    if pd.notna(maturity_ordinal.loc[idx - 1])
                    else None
                ),
                "current_maturity": (
                    int(maturity_ordinal.loc[idx])
                    if pd.notna(maturity_ordinal.loc[idx])
                    else None
                ),
            }
        )
    return True, int(backstep.sum()), examples


def _add_roll_fields(
    df: pd.DataFrame,
    roll_window_bars: int,
    *,
    roll_window_policy: str = "bar_count",
    roll_window_minutes: int | None = None,
) -> pd.DataFrame:
    df = df.sort_values("ts", kind="mergesort").reset_index(drop=True)

    prev_symbol = df["symbol"].shift(1)
    prev_instrument = df["instrument_id"].shift(1)
    same_context = df["inside_session"] & df["inside_session"].shift(1, fill_value=False)

    symbol_known = df["symbol"].notna() & prev_symbol.notna()
    instrument_known = df["instrument_id"].notna() & prev_instrument.notna()
    df["symbol_change_flag"] = (same_context & symbol_known & (df["symbol"] != prev_symbol)).astype(bool)
    if bool(df["roll_detection_available"].fillna(False).any()):
        df["instrument_id_change_flag"] = (
            same_context & instrument_known & (df["instrument_id"] != prev_instrument)
        ).astype(bool)
        df["roll_boundary_flag"] = df["instrument_id_change_flag"].astype(bool)
    else:
        df["instrument_id_change_flag"] = False
        df["roll_boundary_flag"] = False

    roll_positions = np.flatnonzero(df["roll_boundary_flag"].to_numpy())
    n = len(df)
    if len(roll_positions) == 0:
        df["bars_since_roll"] = pd.Series([pd.NA] * n, dtype="Int64")
        df["bars_until_roll"] = pd.Series([pd.NA] * n, dtype="Int64")
        df["roll_window_flag"] = False
    else:
        positions = np.arange(n)
        last_roll_idx = np.searchsorted(roll_positions, positions, side="right") - 1
        next_roll_idx = np.searchsorted(roll_positions, positions, side="left")

        since = np.full(n, np.nan)
        has_last = last_roll_idx >= 0
        since[has_last] = positions[has_last] - roll_positions[last_roll_idx[has_last]]

        until = np.full(n, np.nan)
        has_next = next_roll_idx < len(roll_positions)
        until[has_next] = roll_positions[next_roll_idx[has_next]] - positions[has_next]

        df["bars_since_roll"] = pd.Series(since).round().astype("Int64")
        df["bars_until_roll"] = pd.Series(until).round().astype("Int64")
        if roll_window_policy == "elapsed_minutes":
            window_minutes = roll_window_minutes or roll_window_bars
            ts = pd.to_datetime(df["ts"], utc=True, errors="coerce")
            roll_ts = ts.iloc[roll_positions].reset_index(drop=True)

            since_minutes = pd.Series(np.nan, index=df.index, dtype="float64")
            if has_last.any():
                since_minutes.loc[has_last] = (
                    (
                        ts.loc[has_last].reset_index(drop=True)
                        - roll_ts.iloc[last_roll_idx[has_last]].reset_index(drop=True)
                    )
                    .dt.total_seconds()
                    .to_numpy()
                    / 60.0
                )

            until_minutes = pd.Series(np.nan, index=df.index, dtype="float64")
            if has_next.any():
                until_minutes.loc[has_next] = (
                    (
                        roll_ts.iloc[next_roll_idx[has_next]].reset_index(drop=True)
                        - ts.loc[has_next].reset_index(drop=True)
                    )
                    .dt.total_seconds()
                    .to_numpy()
                    / 60.0
                )

            df["roll_window_flag"] = (
                since_minutes.le(window_minutes).fillna(False)
                | until_minutes.le(window_minutes).fillna(False)
            ).astype(bool)
        else:
            df["roll_window_flag"] = (
                df["bars_since_roll"].le(roll_window_bars).fillna(False)
                | df["bars_until_roll"].le(roll_window_bars).fillna(False)
            ).astype(bool)

    segment_number = df.groupby("session_id", dropna=False)["roll_boundary_flag"].cumsum()
    df["session_segment_id"] = np.where(
        df["inside_session"],
        df["session_id"].astype("string") + "_seg" + segment_number.astype("int64").astype(str),
        pd.NA,
    )
    return df


def _add_session_edge_flags(df: pd.DataFrame) -> pd.DataFrame:
    df["is_session_open"] = False
    df["is_session_close"] = False
    inside = df["inside_session"] & df["session_segment_id"].notna()
    if inside.any():
        first_idx = df.loc[inside].groupby("session_segment_id", sort=False)["ts"].idxmin()
        last_idx = df.loc[inside].groupby("session_segment_id", sort=False)["ts"].idxmax()
        df.loc[first_idx, "is_session_open"] = True
        df.loc[last_idx, "is_session_close"] = True
    return df


def _add_boundary_session_flag(
    df: pd.DataFrame,
    *,
    target_year: int,
    has_previous_context: bool,
    has_next_context: bool,
) -> pd.DataFrame:
    df["boundary_session_flag"] = False
    inside = (
        df["inside_session"]
        & df["session_segment_id"].notna()
        & df["year"].eq(target_year)
    )
    if not inside.any():
        return df

    for _, group in df.loc[inside].groupby(["market", "year"], sort=False):
        ordered_segments = group.sort_values("ts", kind="mergesort")["session_segment_id"]
        if ordered_segments.empty:
            continue
        boundary_segments: set[object] = set()
        if not has_previous_context:
            boundary_segments.add(ordered_segments.iloc[0])
        if not has_next_context:
            boundary_segments.add(ordered_segments.iloc[-1])
        df.loc[df["session_segment_id"].isin(boundary_segments), "boundary_session_flag"] = True
    return df


def _build_causal_invalid_reason(df: pd.DataFrame, missing_required_raw_cols: list[str]) -> pd.Series:
    reasons = pd.Series([""] * len(df), index=df.index, dtype="string")

    reason_masks = [
        ("raw_row_missing", ~df["raw_row_present"]),
        ("synthetic", df["is_synthetic"]),
        ("invalid_ohlcv", ~df["valid_ohlcv"]),
        ("outside_session", ~df["inside_session"]),
        ("degraded_session", df["session_data_quality_degraded"]),
        ("roll_window", df["roll_window_flag"]),
        ("boundary_session", df["boundary_session_flag"]),
    ]
    for reason, mask in reason_masks:
        mask = mask.fillna(False).astype(bool) & ~df["causal_valid"]
        reasons.loc[mask] = np.where(
            reasons.loc[mask].eq(""),
            reason,
            reasons.loc[mask] + "|" + reason,
        )

    if missing_required_raw_cols:
        invalid = ~df["causal_valid"]
        reasons.loc[invalid] = np.where(
            reasons.loc[invalid].eq(""),
            "missing_required_raw_cols",
            reasons.loc[invalid] + "|missing_required_raw_cols",
        )

    reasons.loc[df["causal_valid"]] = ""
    return reasons


def _raw_enrichment_columns(df: pd.DataFrame) -> list[str]:
    return [
        column
        for column in df.columns
        if column not in OUTPUT_COLUMNS
        and any(column.startswith(prefix) for prefix in RAW_ENRICHMENT_COLUMN_PREFIXES)
    ]


def _coerce_output_types(df: pd.DataFrame, extra_columns: Iterable[str] | None = None) -> pd.DataFrame:
    extra_output_columns = [
        column for column in (extra_columns or []) if column not in OUTPUT_COLUMNS
    ]
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    for col in extra_output_columns:
        if col not in df.columns:
            df[col] = pd.NA

    bool_cols = [
        "raw_row_present",
        "is_synthetic",
        "valid_ohlcv",
        "data_quality_degraded",
        "session_data_quality_degraded",
        "trainable_data_quality",
        "inside_session",
        "causal_valid",
        "boundary_session_flag",
        "is_session_open",
        "is_session_close",
        "roll_boundary_flag",
        "symbol_change_flag",
        "instrument_id_change_flag",
        "roll_window_flag",
        "metadata_available",
        "roll_detection_available",
        "holiday_calendar_available",
        "early_close_calendar_available",
    ]
    for col in bool_cols:
        df[col] = df[col].fillna(False).astype(bool)

    int_nullable_cols = [
        "instrument_id",
        "publisher_id",
        "rtype",
        "source_row_number",
        "synthetic_gap_id",
        "synthetic_gap_size_minutes",
        "bars_since_roll",
        "bars_until_roll",
    ]
    for col in int_nullable_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    df["year"] = pd.to_numeric(df["year"], errors="raise").astype("int64")
    df["minute_of_day"] = pd.to_numeric(df["minute_of_day"], errors="coerce").astype("Int64")
    df["day_of_week"] = pd.to_numeric(df["day_of_week"], errors="coerce").astype("Int64")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["data_quality_status"] = df["data_quality_status"].fillna("unknown").astype(str)
    df["synthetic_gap_reason"] = df["synthetic_gap_reason"].astype("string")
    df["causal_invalid_reason"] = df["causal_invalid_reason"].fillna("").astype("string")

    return df[OUTPUT_COLUMNS + extra_output_columns]


def process_file(
    input_path: Path,
    output_path: Path,
    *,
    profile: str,
    roll_window_bars: int = DEFAULT_ROLL_WINDOW_BARS,
    max_synthetic_gap_minutes: int = DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    session_config_path: Path = DEFAULT_SESSION_CONFIG,
    allow_hardcoded_calendar: bool = False,
    write_output: bool = True,
) -> ValidationResult:
    market, year = infer_market_year(input_path)
    config = load_causal_base_config(profile_config_path, profile)
    _, _, aliases, _ = load_profile_map(profile_config_path)
    resolved_profile = resolve_profile_name(profile, aliases)
    raw_schema_policy = raw_schema_policy_for_profile(resolved_profile)
    required_raw_schema_cols = required_raw_schema_cols_for_policy(raw_schema_policy)
    effective_max_synthetic_gap_minutes = (
        config.max_synthetic_gap_minutes
        if max_synthetic_gap_minutes == DEFAULT_MAX_SYNTHETIC_GAP_MINUTES
        else max_synthetic_gap_minutes
    )
    vendor_trusted_ohlcv_no_trade_policy_enabled = (
        market in config.vendor_trusted_ohlcv_no_trade_markets
    )
    synthetic_gap_threshold_action = (
        "diagnostic"
        if vendor_trusted_ohlcv_no_trade_policy_enabled
        else config.synthetic_gap_threshold_action
    )
    calendar = load_session_calendar(
        market,
        session_config_path,
        allow_hardcoded_calendar=allow_hardcoded_calendar,
    )
    result = ValidationResult(
        profile=profile,
        market=market,
        year=year,
        input_path=relative_source_path(input_path),
        output_path=relative_source_path(output_path),
        raw_schema_policy=raw_schema_policy,
        required_raw_schema_cols=required_raw_schema_cols,
        session_calendar_status=calendar.status,
        holiday_calendar_available=calendar.holiday_calendar_available,
        early_close_calendar_available=calendar.early_close_calendar_available,
        calendar_coverage_status=calendar.calendar_coverage_status,
        max_synthetic_rows_pct_threshold=config.max_synthetic_rows_pct,
        max_synthetic_gap_minutes_threshold=effective_max_synthetic_gap_minutes,
        synthetic_gap_threshold_action=synthetic_gap_threshold_action,
        max_degraded_rows_pct_threshold=config.max_degraded_rows_pct,
        max_roll_window_rows_pct_threshold=config.max_roll_window_rows_pct,
        vendor_trusted_ohlcv_no_trade_policy=(
            "databento_ohlcv_1m_trade_derived_no_bar_no_trade"
            if vendor_trusted_ohlcv_no_trade_policy_enabled
            else "not_applicable"
        ),
        vendor_trusted_ohlcv_no_trade_status=(
            "synthetic_thresholds_diagnostic_l0_gate_still_fail_closed"
            if vendor_trusted_ohlcv_no_trade_policy_enabled
            else "not_applicable"
        ),
    )

    if not calendar.config_available:
        result.warnings.append("hardcoded session calendar used")
    elif calendar.calendar_coverage_status == "regular_session_only":
        result.warnings.append(
            "holiday/early-close calendar coverage unavailable: regular session only"
        )

    current_raw = _prepare_raw_frame(
        input_path,
        market=market,
        year=year,
        result=result,
        required=True,
        raw_schema_policy=raw_schema_policy,
    )
    if result.failures or current_raw is None:
        return result
    enrichment_columns = _raw_enrichment_columns(current_raw)
    result.raw_enrichment_columns = enrichment_columns
    result.raw_enrichment_column_count = len(enrichment_columns)
    if "status_missing" in current_raw.columns:
        result.status_enrichment_missing_rows = int(
            current_raw["status_missing"].fillna(True).astype(bool).sum()
        )
    if "status_stale" in current_raw.columns:
        result.status_enrichment_stale_rows = int(
            current_raw["status_stale"].fillna(True).astype(bool).sum()
        )
    if "statistics_missing" in current_raw.columns:
        result.statistics_enrichment_missing_rows = int(
            current_raw["statistics_missing"].fillna(True).astype(bool).sum()
        )
    if "statistics_stale" in current_raw.columns:
        result.statistics_enrichment_stale_rows = int(
            current_raw["statistics_stale"].fillna(True).astype(bool).sum()
        )
    (
        result.roll_maturity_sequence_available,
        result.roll_maturity_backstep_count,
        result.roll_maturity_backstep_examples,
    ) = _roll_maturity_backsteps(current_raw)
    if result.roll_maturity_backstep_count > 0:
        result.warnings.append(
            "roll maturity sequence not monotonic: "
            f"backsteps={result.roll_maturity_backstep_count}"
        )

    result.metadata_available = result.instrument_id_nonnull_count > 0
    result.roll_detection_available = result.metadata_available
    sparse_ohlcv_policy_enabled = market in config.sparse_trade_derived_ohlcv_markets
    if sparse_ohlcv_policy_enabled:
        result.roll_window_policy = "elapsed_minutes_sparse_ohlcv"
        result.roll_window_minutes = config.sparse_trade_derived_roll_window_minutes
    else:
        result.roll_window_policy = "bar_count"
        result.roll_window_minutes = None

    if result.roll_detection_available:
        result.roll_detection_source = "instrument_id"
        result.roll_policy_status = (
            "active_elapsed_time_sparse_ohlcv"
            if sparse_ohlcv_policy_enabled
            else "active"
        )
    else:
        result.roll_detection_source = "unavailable"
        result.roll_policy_status = "unavailable_metadata"
        if resolved_profile in config.require_roll_metadata_for_profiles:
            result.failures.append("required roll metadata unavailable")
            return result
        result.warnings.append("roll detection unavailable: missing populated instrument_id")

    year_start = pd.Timestamp(f"{year}-01-01", tz="UTC")
    year_end = pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
    context_rows = max(roll_window_bars + 2, effective_max_synthetic_gap_minutes + 2)
    frames = []
    prev_raw = _prepare_raw_frame(
        input_path.parent / f"{year - 1}.parquet",
        market=market,
        year=year - 1,
        result=None,
        required=False,
        raw_schema_policy="relaxed",
    )
    if prev_raw is not None:
        prev_context = _clip_previous_context(
            prev_raw,
            year_start=year_start,
            context_rows=context_rows,
        )
        if not prev_context.empty:
            frames.append(prev_context)
    frames.append(current_raw)
    next_raw = _prepare_raw_frame(
        input_path.parent / f"{year + 1}.parquet",
        market=market,
        year=year + 1,
        result=None,
        required=False,
        raw_schema_policy="relaxed",
    )
    if next_raw is not None:
        next_context = _clip_next_context(
            next_raw,
            year_end=year_end,
            context_rows=context_rows,
        )
        if not next_context.empty:
            frames.append(next_context)

    raw_all = pd.concat(frames, ignore_index=True).sort_values("ts", kind="mergesort").reset_index(drop=True)
    raw_meta = _session_metadata(raw_all["ts"], calendar)
    df = pd.concat([raw_all, raw_meta], axis=1)
    df["metadata_available"] = result.metadata_available
    df["roll_detection_available"] = result.roll_detection_available
    df["roll_detection_source"] = result.roll_detection_source
    df["roll_policy_status"] = result.roll_policy_status
    df["session_calendar_status"] = result.session_calendar_status
    df["holiday_calendar_available"] = result.holiday_calendar_available
    df["early_close_calendar_available"] = result.early_close_calendar_available
    df["calendar_coverage_status"] = result.calendar_coverage_status

    base_cols = [
        "ts",
        "market",
        "year",
        "symbol",
        "instrument_id",
        "publisher_id",
        "rtype",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "raw_row_present",
        "is_synthetic",
        "synthetic_gap_id",
        "synthetic_gap_size_minutes",
        "synthetic_gap_reason",
        "valid_ohlcv",
        "data_quality_status",
        "data_quality_degraded",
        "inside_session",
        "session_id",
        "session_date",
        "session_template",
        "minutes_since_session_open",
        "minutes_until_session_close",
        "session_progress",
        "minute_of_day",
        "day_of_week",
        "source_path",
        "source_file_hash",
        "source_row_number",
        "raw_schema_variant",
        "timestamp_source",
        "metadata_available",
        "roll_detection_available",
        "roll_detection_source",
        "roll_policy_status",
        "session_calendar_status",
        "holiday_calendar_available",
        "early_close_calendar_available",
        "calendar_coverage_status",
    ]
    base_cols.extend(col for col in enrichment_columns if col in df.columns)
    df = df[base_cols]

    synthetic = _build_synthetic_rows(
        df,
        effective_max_synthetic_gap_minutes,
        calendar,
    )
    if sparse_ohlcv_policy_enabled:
        result.sparse_ohlcv_policy = "trade_derived_no_trade_gaps_not_filled"
        result.sparse_ohlcv_assumption_status = "ASSUMPTION_BACKED"
        result.sparse_ohlcv_suppressed_synthetic_rows = int(len(synthetic))
        result.sparse_ohlcv_suppressed_gap_count = int(
            synthetic["synthetic_gap_id"].dropna().nunique()
        ) if not synthetic.empty else 0
        suppressed_gap_sizes = pd.to_numeric(
            synthetic["synthetic_gap_size_minutes"], errors="coerce"
        ) if not synthetic.empty else pd.Series(dtype="float64")
        result.sparse_ohlcv_suppressed_max_gap_minutes = (
            int(suppressed_gap_sizes.max()) if suppressed_gap_sizes.notna().any() else 0
        )
    elif not synthetic.empty:
        for col in enrichment_columns:
            if col not in synthetic.columns:
                synthetic[col] = pd.NA
        df = pd.concat([df, synthetic[base_cols]], ignore_index=True)

    df = _add_roll_fields(
        df,
        roll_window_bars,
        roll_window_policy=(
            "elapsed_minutes"
            if result.roll_window_policy == "elapsed_minutes_sparse_ohlcv"
            else "bar_count"
        ),
        roll_window_minutes=result.roll_window_minutes,
    )
    df = _add_session_edge_flags(df)
    has_previous_context = bool(
        (df["ts"].lt(year_start) & df["inside_session"]).any()
    )
    has_next_context = bool(
        (df["ts"].ge(year_end) & df["inside_session"]).any()
    )
    df = df[df["ts"].ge(year_start) & df["ts"].lt(year_end)].copy()
    df = _add_boundary_session_flag(
        df,
        target_year=year,
        has_previous_context=has_previous_context,
        has_next_context=has_next_context,
    )
    df["data_quality_degraded"] = df["data_quality_degraded"].fillna(False).astype(bool)
    df["session_data_quality_degraded"] = False
    session_mask = df["session_id"].notna()
    if session_mask.any():
        df.loc[session_mask, "session_data_quality_degraded"] = (
            df.loc[session_mask]
            .groupby("session_id", sort=False)["data_quality_degraded"]
            .transform("any")
            .astype(bool)
        )
    df["trainable_data_quality"] = ~df["session_data_quality_degraded"].astype(bool)
    df["causal_valid"] = (
        df["raw_row_present"]
        & ~df["is_synthetic"]
        & df["valid_ohlcv"]
        & df["inside_session"]
        & df["trainable_data_quality"]
        & ~df["roll_window_flag"]
        & ~df["boundary_session_flag"]
    ).astype(bool)
    df["causal_invalid_reason"] = _build_causal_invalid_reason(
        df, result.missing_required_raw_cols
    )

    result.output_rows = len(df)
    result.synthetic_rows = int(df["is_synthetic"].sum())
    result.synthetic_gap_count = int(df["synthetic_gap_id"].dropna().nunique())
    synthetic_gap_sizes = pd.to_numeric(df["synthetic_gap_size_minutes"], errors="coerce")
    result.max_synthetic_gap_minutes = (
        int(synthetic_gap_sizes.max()) if synthetic_gap_sizes.notna().any() else 0
    )
    result.synthetic_rows_pct = (
        round(100.0 * result.synthetic_rows / result.output_rows, 6)
        if result.output_rows
        else 0.0
    )
    result.outside_session_rows = int((~df["inside_session"]).sum())
    result.roll_boundary_rows = int(df["roll_boundary_flag"].sum())
    result.roll_window_rows = int(df["roll_window_flag"].sum())
    result.roll_window_rows_pct = (
        round(100.0 * result.roll_window_rows / result.output_rows, 6)
        if result.output_rows
        else 0.0
    )
    result.boundary_session_rows = int(df["boundary_session_flag"].sum())
    result.causal_valid_rows = int(df["causal_valid"].sum())
    result.causal_invalid_rows = result.output_rows - result.causal_valid_rows
    result.degraded_session_rows = int(
        df.loc[df["is_session_open"], "session_data_quality_degraded"].sum()
    )
    result.degraded_rows_pct = (
        round(100.0 * result.degraded_bar_rows / result.raw_rows, 6)
        if result.raw_rows
        else 0.0
    )
    result.synthetic_gap_threshold_breached = (
        result.synthetic_rows_pct > config.max_synthetic_rows_pct
        or result.max_synthetic_gap_minutes > effective_max_synthetic_gap_minutes
    )
    result.roll_window_threshold_breached = (
        result.roll_window_rows_pct > config.max_roll_window_rows_pct
    )
    result.degraded_threshold_breached = (
        result.degraded_rows_pct > config.max_degraded_rows_pct
    )

    if (
        result.synthetic_gap_threshold_breached
        and result.synthetic_gap_threshold_action == "warn"
    ):
        result.warnings.append(
            "synthetic threshold breached: "
            f"rows_pct={result.synthetic_rows_pct} "
            f"max_gap_minutes={result.max_synthetic_gap_minutes}"
        )
    if result.roll_window_threshold_breached:
        result.warnings.append(
            "roll exclusion threshold breached: "
            f"rows_pct={result.roll_window_rows_pct} rows={result.roll_window_rows}"
        )
    if result.degraded_threshold_breached:
        result.warnings.append(
            "degraded threshold breached: "
            f"rows_pct={result.degraded_rows_pct} bars={result.degraded_bar_rows} "
            f"sessions={result.degraded_session_rows}"
        )

    if write_output:
        output = _coerce_output_types(
            df.sort_values("ts", kind="mergesort").reset_index(drop=True),
            extra_columns=enrichment_columns,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output.to_parquet(output_path, index=False)
    return result


def write_reports(
    results: Iterable[ValidationResult],
    reports_root: Path,
    profile: str,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    *,
    input_root: Path | None = None,
    output_root: Path | None = None,
    local_trade_gap_gate: dict[str, Any] | None = None,
) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    rows = [result.to_dict() for result in results]
    report_rows = [
        _with_local_trade_validation_fields(row, local_trade_gap_gate) for row in rows
    ]
    csv_rows = [result.to_csv_row() for result in results]
    script_path = Path(__file__).resolve()
    resolved_input_root = input_root or infer_artifact_root(rows, "input_path")
    resolved_output_root = output_root or infer_artifact_root(rows, "output_path")
    output_file_hashes = {
        str(row["output_path"]): hash_optional_file(Path(str(row["output_path"])))
        for row in rows
    }
    run_failures = [
        {
            "market": row["market"],
            "year": row["year"],
            "failures": row["failures"],
        }
        for row in rows
        if row["failures"]
    ]
    gate_failed = (
        local_trade_gap_gate is not None and local_trade_gap_gate.get("status") != "PASS"
    )
    if gate_failed:
        run_failures.append(
            {
                "gate": "local_trade_ohlcv_gap_gate",
                "status": local_trade_gap_gate.get("status"),
                "failures": local_trade_gap_gate.get("failures", []),
            }
        )
    failure_count = int(sum(row["failure_count"] for row in rows)) + (1 if gate_failed else 0)
    warning_count = int(sum(row["warning_count"] for row in rows))
    status = (
        "FAIL"
        if gate_failed or any(row["status"] == "FAIL" for row in rows)
        else "WARN"
        if any(row["status"] == "WARN" for row in rows)
        else "PASS"
    )
    authority = scope_authority_metadata(
        profile=profile,
        selected_market_years=((row["market"], row["year"]) for row in rows),
        profile_config=profile_config_path,
        status=status,
        failure_count=failure_count,
        selected_input_count=len(rows),
    )
    scope = load_profile_scope(profile, profile_config_path, strict=False)
    resolved_profile = scope.resolved_profile if scope is not None else profile
    provenance = {
        "generated_at": utc_timestamp(),
        "git_commit": current_git_commit(),
        "script_path": relative_source_path(script_path),
        "script_hash": sha256_file(script_path),
        "config_hash": hash_optional_file(profile_config_path),
        "input_root": resolved_input_root.as_posix() if resolved_input_root else None,
        "output_root": resolved_output_root.as_posix() if resolved_output_root else None,
        "reports_root": reports_root.as_posix(),
        "input_file_hashes": {
            str(row["input_path"]): row["source_file_hash"] for row in rows
        },
        "output_file_hashes": output_file_hashes,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "markets": sorted({str(row["market"]) for row in rows}),
        "years": sorted({int(row["year"]) for row in rows}),
        "warning_count": warning_count,
        "failure_count": failure_count,
        "failures": run_failures,
        **authority,
    }

    validation_json = {
        **provenance,
        "stage": "causal_base",
        "status": status,
        "local_trade_ohlcv_gap_gate": local_trade_gap_gate,
        "files": report_rows,
        "summary": {
            "file_count": len(rows),
            "pass_count": sum(r["status"] == "PASS" for r in rows),
            "warn_count": sum(r["status"] == "WARN" for r in rows),
            "fail_count": sum(r["status"] == "FAIL" for r in rows),
            "raw_rows": int(sum(r["raw_rows"] for r in rows)),
            "output_rows": int(sum(r["output_rows"] for r in rows)),
            "synthetic_rows": int(sum(r["synthetic_rows"] for r in rows)),
            "synthetic_gap_count": int(sum(r["synthetic_gap_count"] for r in rows)),
            "max_synthetic_gap_minutes": int(
                max([r["max_synthetic_gap_minutes"] for r in rows] or [0])
            ),
            "synthetic_gap_threshold_breached_files": int(
                sum(bool(r["synthetic_gap_threshold_breached"]) for r in rows)
            ),
            "roll_boundary_rows": int(sum(r["roll_boundary_rows"] for r in rows)),
            "roll_window_rows": int(sum(r["roll_window_rows"] for r in rows)),
            "roll_window_threshold_breached_files": int(
                sum(bool(r["roll_window_threshold_breached"]) for r in rows)
            ),
            "roll_boundary_count": int(sum(r["roll_boundary_rows"] for r in rows)),
            "roll_window_count": int(sum(r["roll_window_rows"] for r in rows)),
            "boundary_session_rows": int(sum(r["boundary_session_rows"] for r in rows)),
            "causal_valid_rows": int(sum(r["causal_valid_rows"] for r in rows)),
            "causal_invalid_rows": int(sum(r["causal_invalid_rows"] for r in rows)),
            "degraded_bar_rows": int(sum(r["degraded_bar_rows"] for r in rows)),
            "degraded_session_rows": int(sum(r["degraded_session_rows"] for r in rows)),
            "degraded_threshold_breached_files": int(
                sum(bool(r["degraded_threshold_breached"]) for r in rows)
            ),
            "local_trade_ohlcv_gap_gate_status": (
                local_trade_gap_gate.get("status")
                if isinstance(local_trade_gap_gate, dict)
                else "NOT_RUN"
            ),
        },
    }

    manifest = {
        **provenance,
        "stage": "causal_base",
        "status": status,
        "local_trade_ohlcv_gap_gate": local_trade_gap_gate,
        "outputs": [
            {
                "market": row["market"],
                "year": row["year"],
                "input_path": row["input_path"],
                "output_path": row["output_path"],
                "source_file_hash": row["source_file_hash"],
                "raw_rows": row["raw_rows"],
                "output_rows": row["output_rows"],
                "synthetic_rows": row["synthetic_rows"],
                "synthetic_gap_count": row["synthetic_gap_count"],
                "max_synthetic_gap_minutes": row["max_synthetic_gap_minutes"],
                "synthetic_rows_pct": row["synthetic_rows_pct"],
                "synthetic_gap_threshold_breached": row["synthetic_gap_threshold_breached"],
                "raw_schema_variant": row["raw_schema_variant"],
                "raw_schema_policy": row["raw_schema_policy"],
                "required_raw_schema_cols": row["required_raw_schema_cols"],
                "raw_schema_missing_cols": row["raw_schema_missing_cols"],
                "missing_required_raw_cols": row["missing_required_raw_cols"],
                "timestamp_source": row["timestamp_source"],
                "metadata_available": row["metadata_available"],
                "roll_detection_available": row["roll_detection_available"],
                "roll_detection_source": row["roll_detection_source"],
                "roll_policy_status": row["roll_policy_status"],
                "symbol_nonnull_count": row["symbol_nonnull_count"],
                "instrument_id_nonnull_count": row["instrument_id_nonnull_count"],
                "instrument_id_nunique": row["instrument_id_nunique"],
                "roll_boundary_count": row["roll_boundary_count"],
                "roll_window_count": row["roll_window_count"],
                "roll_window_rows_pct": row["roll_window_rows_pct"],
                "roll_window_threshold_breached": row["roll_window_threshold_breached"],
                "roll_window_policy": row["roll_window_policy"],
                "roll_window_minutes": row["roll_window_minutes"],
                "roll_maturity_sequence_available": row[
                    "roll_maturity_sequence_available"
                ],
                "roll_maturity_backstep_count": row["roll_maturity_backstep_count"],
                "roll_maturity_backstep_examples": row[
                    "roll_maturity_backstep_examples"
                ],
                "boundary_session_rows": row["boundary_session_rows"],
                "causal_valid_rows": row["causal_valid_rows"],
                "causal_invalid_rows": row["causal_invalid_rows"],
                "degraded_bar_rows": row["degraded_bar_rows"],
                "degraded_session_rows": row["degraded_session_rows"],
                "degraded_rows_pct": row["degraded_rows_pct"],
                "degraded_threshold_breached": row["degraded_threshold_breached"],
                "sparse_ohlcv_policy": row["sparse_ohlcv_policy"],
                "sparse_ohlcv_assumption_status": row[
                    "sparse_ohlcv_assumption_status"
                ],
                "sparse_ohlcv_suppressed_synthetic_rows": row[
                    "sparse_ohlcv_suppressed_synthetic_rows"
                ],
                "sparse_ohlcv_suppressed_gap_count": row[
                    "sparse_ohlcv_suppressed_gap_count"
                ],
                "sparse_ohlcv_suppressed_max_gap_minutes": row[
                    "sparse_ohlcv_suppressed_max_gap_minutes"
                ],
                "vendor_trusted_ohlcv_no_trade_policy": row[
                    "vendor_trusted_ohlcv_no_trade_policy"
                ],
                "vendor_trusted_ohlcv_no_trade_status": row[
                    "vendor_trusted_ohlcv_no_trade_status"
                ],
                "max_synthetic_rows_pct_threshold": row["max_synthetic_rows_pct_threshold"],
                "max_synthetic_gap_minutes_threshold": row[
                    "max_synthetic_gap_minutes_threshold"
                ],
                "max_degraded_rows_pct_threshold": row["max_degraded_rows_pct_threshold"],
                "max_roll_window_rows_pct_threshold": row[
                    "max_roll_window_rows_pct_threshold"
                ],
                "session_calendar_status": row["session_calendar_status"],
                "holiday_calendar_available": row["holiday_calendar_available"],
                "early_close_calendar_available": row["early_close_calendar_available"],
                "calendar_coverage_status": row["calendar_coverage_status"],
                "warning_count": row["warning_count"],
                "warnings": row["warnings"],
                "failure_count": row["failure_count"],
                "failures": row["failures"],
                "local_trade_gap_validation_status": row[
                    "local_trade_gap_validation_status"
                ],
                "local_trade_gap_gate_status": row["local_trade_gap_gate_status"],
                "local_trade_gap_gate_window": row["local_trade_gap_gate_window"],
                "local_trade_gap_gate_report_json": row[
                    "local_trade_gap_gate_report_json"
                ],
                "local_trade_gap_gate_caveat": row["local_trade_gap_gate_caveat"],
                "status": row["status"],
            }
            for row in report_rows
        ],
        "summary": validation_json["summary"],
    }

    (reports_root / "causal_base_validation.json").write_text(
        json.dumps(validation_json, indent=2), encoding="utf-8"
    )
    (reports_root / "causal_base_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    pd.DataFrame(csv_rows).to_csv(reports_root / "causal_base_validation.csv", index=False)


def write_readiness_report(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Phase 2 Readiness Summary",
        "",
        f"- Status: {report.get('status')}",
        f"- Profile: {report.get('profile')} -> {report.get('resolved_profile')}",
        f"- Raw root: {report.get('raw_root')}",
        f"- Raw alignment report: {report.get('raw_alignment_report')}",
        f"- Selected market-years: {report.get('selected_market_year_count')}",
        f"- Checked market-years: {report.get('checked_market_year_count')}",
        f"- Pending market-years: {report.get('pending_market_year_count')}",
        f"- Blockers: {report.get('blocker_count')}",
        f"- Failures: {report.get('failure_count')}",
        "",
        "## Failures",
        "",
    ]
    failures = report.get("failures") or []
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    blockers = report.get("blockers") or []
    lines.extend(["", "## Blockers", ""])
    if blockers:
        for blocker in blockers[:100]:
            lines.append(
                f"- {blocker.get('market')} {blocker.get('year')}: {blocker.get('status')} "
                f"failures={len(blocker.get('failures') or [])} warnings={len(blocker.get('warnings') or [])}"
            )
    else:
        lines.append("- None")
    accepted = report.get("accepted_readiness_exceptions") or []
    lines.extend(["", "## Accepted Readiness Exceptions", ""])
    if accepted:
        for item in accepted[:100]:
            lines.append(
                f"- {item.get('market')} {item.get('year')}: "
                f"{item.get('category')} warnings={len(item.get('warnings') or [])}"
            )
    else:
        lines.append("- None")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def phase2_readiness_result_row(
    result: ValidationResult,
    *,
    resolved_profile: str | None = None,
) -> dict[str, Any]:
    status_columns = [
        col for col in result.raw_enrichment_columns if col.startswith("status_")
    ]
    statistics_columns = [
        col
        for col in result.raw_enrichment_columns
        if col.startswith("stat_") or col.startswith("statistics_")
    ]
    top_blocker_reason = None
    if result.failures:
        top_blocker_reason = result.failures[0]
    elif result.warnings:
        top_blocker_reason = result.warnings[0]
    return {
        "stage": "phase2_readiness_market_year",
        "profile": result.profile,
        "resolved_profile": resolved_profile,
        "market": result.market,
        "year": result.year,
        "status": result.status,
        "top_blocker_reason": top_blocker_reason,
        "synthetic_rows_pct": result.synthetic_rows_pct,
        "max_synthetic_gap_minutes": result.max_synthetic_gap_minutes,
        "synthetic_rows": result.synthetic_rows,
        "synthetic_gap_threshold_breached": result.synthetic_gap_threshold_breached,
        "synthetic_gap_threshold_action": result.synthetic_gap_threshold_action,
        "output_rows": result.output_rows,
        "degraded_rows_pct": result.degraded_rows_pct,
        "degraded_bar_rows": result.degraded_bar_rows,
        "degraded_session_rows": result.degraded_session_rows,
        "roll_window_rows_pct": result.roll_window_rows_pct,
        "roll_window_rows": result.roll_window_rows,
        "roll_window_policy": result.roll_window_policy,
        "roll_window_minutes": result.roll_window_minutes,
        "roll_maturity_sequence_available": result.roll_maturity_sequence_available,
        "roll_maturity_backstep_count": result.roll_maturity_backstep_count,
        "roll_maturity_backstep_examples": result.roll_maturity_backstep_examples,
        "status_enrichment_available": bool(status_columns),
        "status_enrichment_column_count": len(status_columns),
        "statistics_enrichment_available": bool(statistics_columns),
        "statistics_enrichment_column_count": len(statistics_columns),
        "status_enrichment_missing_rows": result.status_enrichment_missing_rows,
        "status_enrichment_stale_rows": result.status_enrichment_stale_rows,
        "statistics_enrichment_missing_rows": result.statistics_enrichment_missing_rows,
        "statistics_enrichment_stale_rows": result.statistics_enrichment_stale_rows,
        "sparse_ohlcv_policy": result.sparse_ohlcv_policy,
        "sparse_ohlcv_assumption_status": result.sparse_ohlcv_assumption_status,
        "sparse_ohlcv_suppressed_synthetic_rows": (
            result.sparse_ohlcv_suppressed_synthetic_rows
        ),
        "sparse_ohlcv_suppressed_gap_count": result.sparse_ohlcv_suppressed_gap_count,
        "sparse_ohlcv_suppressed_max_gap_minutes": (
            result.sparse_ohlcv_suppressed_max_gap_minutes
        ),
        "vendor_trusted_ohlcv_no_trade_policy": (
            result.vendor_trusted_ohlcv_no_trade_policy
        ),
        "vendor_trusted_ohlcv_no_trade_status": (
            result.vendor_trusted_ohlcv_no_trade_status
        ),
        "warnings": result.warnings,
        "failures": result.failures,
    }


def _phase2_readiness_blocker(
    result: ValidationResult,
    *,
    resolved_profile: str | None = None,
) -> dict[str, Any]:
    return phase2_readiness_result_row(result, resolved_profile=resolved_profile)


def _run_phase2_readiness_task(task: dict[str, Any]) -> ValidationResult:
    return process_file(
        Path(str(task["input_path"])),
        Path(str(task["output_path"])),
        profile=str(task["profile"]),
        roll_window_bars=int(task["roll_window_bars"]),
        max_synthetic_gap_minutes=int(task["max_synthetic_gap_minutes"]),
        profile_config_path=Path(str(task["profile_config_path"])),
        session_config_path=Path(str(task["session_config_path"])),
        allow_hardcoded_calendar=bool(task["allow_hardcoded_calendar"]),
        write_output=False,
    )


def build_phase2_readiness_report(
    *,
    profile: str,
    raw_root: Path,
    raw_alignment_report: Path,
    output_root: Path = Path("data/causally_gated_normalized"),
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    session_config_path: Path = DEFAULT_SESSION_CONFIG,
    roll_window_bars: int = DEFAULT_ROLL_WINDOW_BARS,
    max_synthetic_gap_minutes: int = DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    allow_hardcoded_calendar: bool = False,
    fail_fast: bool = False,
    jobs: int = 1,
    progress: bool = False,
    markets: Iterable[str] | None = None,
    years: Iterable[int] | None = None,
    skip_market_years: Iterable[tuple[str, int]] | None = None,
    checkpoint_row_callback: Callable[[dict[str, Any]], None] | None = None,
    max_market_years: int | None = None,
    stop_after_blockers: int | None = None,
) -> dict[str, Any]:
    _, _, aliases, _ = load_profile_map(profile_config_path)
    resolved_profile = resolve_profile_name(profile, aliases)
    market_filter = {str(market) for market in markets} if markets else None
    year_filter = {int(year) for year in years} if years else None
    skipped_pairs = {
        (str(market), int(year)) for market, year in (skip_market_years or [])
    }

    def market_year_selected(market: str, year: int) -> bool:
        if market_filter is not None and market not in market_filter:
            return False
        if year_filter is not None and year not in year_filter:
            return False
        return True

    failures = raw_alignment_guard_failures(
        report_path=raw_alignment_report,
        raw_root=raw_root,
        profile=profile,
        profile_config_path=profile_config_path,
    )
    report: dict[str, Any] = {
        "stage": "phase2_readiness_preflight",
        "status": "FAIL" if failures else "PASS",
        "profile": profile,
        "resolved_profile": resolved_profile,
        "raw_root": relative_source_path(raw_root),
        "raw_alignment_report": relative_source_path(raw_alignment_report),
        "market_filter": sorted(market_filter) if market_filter else None,
        "year_filter": sorted(year_filter) if year_filter else None,
        "selected_market_year_count": 0,
        "expected_market_year_count": 0,
        "checked_market_year_count": 0,
        "resumed_market_year_count": 0,
        "pending_market_year_count": 0,
        "blocker_count": 0,
        "accepted_exception_count": 0,
        "failure_count": len(failures),
        "failures": failures,
        "blockers": [],
        "accepted_readiness_exceptions": [],
    }
    if failures:
        return report

    raw_alignment = _read_json(raw_alignment_report)
    expected_pairs = raw_alignment_expected_market_years(raw_alignment)
    selected_expected_pairs = {
        pair for pair in expected_pairs if market_year_selected(pair[0], pair[1])
    }
    inputs, missing_expected_pairs = filter_inputs_by_raw_alignment(
        resolve_profile_inputs(profile, raw_root, profile_config_path),
        raw_alignment,
    )
    inputs = [
        (market, year, input_path)
        for market, year, input_path in inputs
        if market_year_selected(market, year)
    ]
    missing_expected_pairs = {
        pair for pair in missing_expected_pairs if market_year_selected(pair[0], pair[1])
    }
    if (market_filter or year_filter) and not inputs:
        failures.append("market/year filters selected no eligible Phase 2 inputs")
        report["status"] = "FAIL"
        report["failure_count"] = len(failures)
        report["failures"] = failures
        return report
    if missing_expected_pairs:
        failures.append(
            "raw alignment eligible market-years missing from profile config: "
            f"{len(missing_expected_pairs)}"
        )
        report["status"] = "FAIL"
        report["failure_count"] = len(failures)
        report["failures"] = failures
        report["missing_expected_market_years"] = [
            {"market": market, "year": year}
            for market, year in missing_expected_pairs
        ]
        return report

    config = load_causal_base_config(profile_config_path, profile)
    effective_max_gap = (
        config.max_synthetic_gap_minutes
        if max_synthetic_gap_minutes == DEFAULT_MAX_SYNTHETIC_GAP_MINUTES
        else max_synthetic_gap_minutes
    )
    blockers: list[dict[str, Any]] = []
    accepted_exceptions: list[dict[str, Any]] = []
    checked_count = 0
    resumed_count = len(
        {
            (market, year)
            for market, year, _input_path in inputs
            if (market, year) in skipped_pairs
        }
    )
    effective_jobs = max(1, int(jobs))
    if fail_fast:
        effective_jobs = 1
    tasks = [
        {
            "input_path": input_path.as_posix(),
            "output_path": (output_root / market / f"{year}.parquet").as_posix(),
            "profile": profile,
            "roll_window_bars": roll_window_bars,
            "max_synthetic_gap_minutes": effective_max_gap,
            "profile_config_path": profile_config_path.as_posix(),
            "session_config_path": session_config_path.as_posix(),
            "allow_hardcoded_calendar": allow_hardcoded_calendar,
        }
        for market, year, input_path in inputs
        if (market, year) not in skipped_pairs
    ]
    total_unskipped_count = len(tasks)
    if max_market_years is not None:
        tasks = tasks[: max(0, int(max_market_years))]
    blocker_limit = int(stop_after_blockers) if stop_after_blockers is not None else None

    def record_result(result: ValidationResult) -> dict[str, Any]:
        row = phase2_readiness_result_row(result, resolved_profile=resolved_profile)
        if result.status != "PASS":
            accepted_exception = _accepted_readiness_exception_for_result(result, config)
            if accepted_exception is None:
                blockers.append(row)
            else:
                row["original_status"] = row["status"]
                row["status"] = "PASS"
                row["accepted_readiness_exception"] = accepted_exception
                accepted_exceptions.append(
                    {
                        "market": result.market,
                        "year": result.year,
                        "original_status": result.status,
                        "category": accepted_exception["category"],
                        "reason": accepted_exception["reason"],
                        "evidence_paths": accepted_exception["evidence_paths"],
                        "warnings": list(result.warnings),
                    }
                )
        if checkpoint_row_callback is not None:
            checkpoint_row_callback(row)
        return row

    def emit_progress(result: ValidationResult) -> None:
        if progress:
            print(
                "phase2_readiness "
                f"checked={checked_count + resumed_count}/{len(inputs)} "
                f"blockers={len(blockers)} "
                f"latest={result.market} {result.year} status={result.status}",
                file=sys.stderr,
                flush=True,
            )

    if effective_jobs == 1:
        for task in tasks:
            result = _run_phase2_readiness_task(task)
            checked_count += 1
            record_result(result)
            emit_progress(result)
            if result.status != "PASS" and fail_fast:
                break
            if blocker_limit is not None and len(blockers) >= blocker_limit:
                break
    else:
        with ThreadPoolExecutor(max_workers=effective_jobs) as executor:
            futures = [executor.submit(_run_phase2_readiness_task, task) for task in tasks]
            for future in as_completed(futures):
                result = future.result()
                checked_count += 1
                record_result(result)
                emit_progress(result)
                if blocker_limit is not None and len(blockers) >= blocker_limit:
                    for pending in futures:
                        pending.cancel()
                    break
    blockers = sorted(blockers, key=lambda row: (str(row["market"]), int(row["year"])))
    pending_count = max(0, len(inputs) - checked_count - resumed_count)

    report.update(
        {
            "status": "FAIL" if blockers or pending_count else "PASS",
            "jobs": effective_jobs,
            "selected_market_year_count": len(inputs),
            "scheduled_market_year_count": len(tasks),
            "total_unskipped_market_year_count": total_unskipped_count,
            "expected_market_year_count": (
                len(selected_expected_pairs) if selected_expected_pairs else len(inputs)
            ),
            "checked_market_year_count": checked_count + resumed_count,
            "resumed_market_year_count": resumed_count,
            "pending_market_year_count": pending_count,
            "blocker_count": len(blockers),
            "accepted_exception_count": len(accepted_exceptions),
            "failure_count": 0,
            "failures": [],
            "blockers": blockers,
            "accepted_readiness_exceptions": accepted_exceptions,
        }
    )
    return report


def output_root_guard_failures(
    *,
    output_root: Path,
    reports_root: Path,
    planned_outputs: Iterable[Path] | None = None,
) -> list[str]:
    manifest_path = reports_root / "causal_base_manifest.json"
    if manifest_path.exists():
        return []
    if not output_root.exists():
        return []
    if planned_outputs is not None:
        existing_planned = [path for path in planned_outputs if path.exists()]
        if not existing_planned:
            return []
        return [
            "planned output already exists but paired Phase 2 manifest is missing: "
            f"output={relative_source_path(existing_planned[0])} "
            f"manifest={relative_source_path(manifest_path)}"
        ]
    try:
        has_parquet = next(output_root.rglob("*.parquet"), None) is not None
    except OSError as exc:
        return [f"output_root unreadable: {relative_source_path(output_root)} ({exc})"]
    if not has_parquet:
        return []
    return [
        "output_root already contains parquet files but paired Phase 2 manifest is missing: "
        f"output_root={relative_source_path(output_root)} "
        f"manifest={relative_source_path(manifest_path)}"
    ]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=(
            "Use all_raw to process every top-level raw market/year file, or "
            "tier_1 for the small recent core proof set."
        ),
    )
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--output-root", default="data/causally_gated_normalized")
    parser.add_argument("--reports-root", default="reports/causal_base")
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--session-config", default=str(DEFAULT_SESSION_CONFIG))
    parser.add_argument("--raw-alignment-report", default=str(DEFAULT_RAW_ALIGNMENT_REPORT))
    parser.add_argument("--allow-hardcoded-calendar", action="store_true")
    parser.add_argument("--roll-window-bars", type=int, default=DEFAULT_ROLL_WINDOW_BARS)
    parser.add_argument(
        "--max-synthetic-gap-minutes",
        type=int,
        default=DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
        help="Fill only missing in-session gaps up to this size.",
    )
    parser.add_argument(
        "--readiness-only",
        action="store_true",
        help="Run bounded Phase 2 readiness checks and write reports without writing causal parquet outputs.",
    )
    parser.add_argument("--readiness-json-out", help="Override readiness-only JSON report path.")
    parser.add_argument("--readiness-md-out", help="Override readiness-only markdown report path.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    raw_root = Path(args.raw_root)
    output_root = Path(args.output_root)
    reports_root = Path(args.reports_root)
    profile_config_path = Path(args.profile_config)
    session_config_path = Path(args.session_config)
    raw_alignment_report = Path(args.raw_alignment_report)
    raw_alignment_failures = raw_alignment_guard_failures(
        report_path=raw_alignment_report,
        raw_root=raw_root,
        profile=args.profile,
        profile_config_path=profile_config_path,
    )
    if raw_alignment_failures:
        for failure in raw_alignment_failures:
            print(f"FAIL raw_alignment_guard: {failure}")
        return 1
    config = load_causal_base_config(profile_config_path, args.profile)
    raw_alignment = _read_json(raw_alignment_report)
    inputs, _ = filter_inputs_by_raw_alignment(
        resolve_profile_inputs(args.profile, raw_root, profile_config_path),
        raw_alignment,
    )
    if not args.readiness_only:
        output_root_failures = output_root_guard_failures(
            output_root=output_root,
            reports_root=reports_root,
            planned_outputs=[
                output_root / market / f"{year}.parquet"
                for market, year, _input_path in inputs
            ],
        )
        if output_root_failures:
            for failure in output_root_failures:
                print(f"FAIL output_root_guard: {failure}")
            return 1
    readiness = build_phase2_readiness_report(
        profile=args.profile,
        raw_root=raw_root,
        raw_alignment_report=raw_alignment_report,
        output_root=output_root,
        profile_config_path=profile_config_path,
        session_config_path=session_config_path,
        roll_window_bars=args.roll_window_bars,
        max_synthetic_gap_minutes=config.max_synthetic_gap_minutes,
        allow_hardcoded_calendar=args.allow_hardcoded_calendar,
        fail_fast=True,
    )
    if args.readiness_only:
        json_path = Path(args.readiness_json_out) if args.readiness_json_out else reports_root / "phase2_readiness_summary.json"
        markdown_path = Path(args.readiness_md_out) if args.readiness_md_out else reports_root / "phase2_readiness_summary.md"
        write_readiness_report(readiness, json_path, markdown_path)
        print(
            "phase2_readiness_only "
            f"status={readiness.get('status')} checked={readiness.get('checked_market_year_count')} "
            f"blockers={readiness.get('blocker_count')} json={json_path.as_posix()}"
        )
        return 0 if readiness.get("status") == "PASS" else 1
    if readiness.get("status") != "PASS":
        print("FAIL phase2_readiness_preflight")
        print(json.dumps(readiness, indent=2))
        return 1

    results: list[ValidationResult] = []
    for market, year, input_path in inputs:
        output_path = output_root / market / f"{year}.parquet"
        result = process_file(
            input_path,
            output_path,
            profile=args.profile,
            roll_window_bars=args.roll_window_bars,
            max_synthetic_gap_minutes=config.max_synthetic_gap_minutes,
            profile_config_path=profile_config_path,
            session_config_path=session_config_path,
            allow_hardcoded_calendar=args.allow_hardcoded_calendar,
        )
        results.append(result)
        print(
            f"{result.status} {market} {year}: raw={result.raw_rows} "
            f"out={result.output_rows} synthetic={result.synthetic_rows} "
            f"warnings={len(result.warnings)} failures={len(result.failures)}"
        )

    local_trade_gap_gate = None
    if profile_requires_local_trade_gap_gate(args.profile, profile_config_path):
        local_trade_gap_gate = build_local_trade_ohlcv_gap_gate(
            markets=sorted({result.market for result in results}),
            raw_root=raw_root,
            causal_root=output_root,
            reports_root=reports_root,
            profile_config_path=profile_config_path,
        )
        print(
            "local_trade_ohlcv_gap_gate "
            f"status={local_trade_gap_gate['status']} "
            f"markets={len(local_trade_gap_gate['selected_markets'])}"
        )
    else:
        print("local_trade_ohlcv_gap_gate status=SKIPPED")

    write_reports(
        results,
        reports_root,
        args.profile,
        profile_config_path,
        input_root=raw_root,
        output_root=output_root,
        local_trade_gap_gate=local_trade_gap_gate,
    )
    return phase2_exit_code(results, local_trade_gap_gate)


if __name__ == "__main__":
    raise SystemExit(main())
