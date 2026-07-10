#!/usr/bin/env python3
"""Build Phase 3 target/label parquet files from causal 1-minute bars."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml

from scripts.pipeline_gates import resolve_upstream_manifest_gate
from scripts.profile_scope import load_profile_scope, scope_authority_metadata


DEFAULT_PROFILE = "all_causal"
DISCOVERY_PROFILES = {"all_causal", "all_causal_data", "all_raw", "all_raw_data"}
DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")
DEFAULT_CAUSAL_BASE_MANIFEST = Path("reports/causal_base/causal_base_manifest.json")
APPROVED_TIER1_CANDIDATE_ROOT = Path("data/causally_gated_normalized")
APPROVED_TIER1_ACCEPTED_EXCEPTIONS_PATH = Path(
    "reports/data_audit/causal_base_repair_plan/tier1_candidate_v1/"
    "accepted_readiness_exceptions.json"
)
APPROVED_TIER1_ACCEPTED_EXCEPTIONS = {
    ("6E", 2023): {
        "category": "vendor_trusted_ohlcv_no_trade",
        "metric": "synthetic_rows_pct",
        "observed": 2.057954,
        "approved_limit": 2.1,
        "warning": "synthetic threshold breached: rows_pct=2.057954 max_gap_minutes=48",
    },
    ("6E", 2024): {
        "category": "vendor_trusted_ohlcv_no_trade",
        "metric": "synthetic_rows_pct",
        "observed": 2.539287,
        "approved_limit": 2.6,
        "warning": "synthetic threshold breached: rows_pct=2.539287 max_gap_minutes=54",
    },
}
APPROVED_TIER1_GLOBAL_SYNTHETIC_THRESHOLD = 2.0
APPROVED_ES2026_CANDIDATE_ROOT = Path(
    "data/causally_gated_normalized/local_trade_es2026_p1_candidate"
)
APPROVED_ES2026_ACCEPTED_EXCEPTIONS_PATH = Path("configs/alpha_tiered.yaml")
APPROVED_ES2026_ACCEPTED_EXCEPTIONS_PROFILE = "tier_3_forward"
APPROVED_ES2026_ACCEPTED_EXCEPTION = {
    "category": "statistics_enrichment_sparse",
    "market": "ES",
    "year": 2026,
    "reason": "bounded_es2026_statistics_enrichment_sparse_accepted_warning_packet_20260703",
    "evidence_paths": [
        "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/readiness_warning_evidence/ES_2026_readiness_warning_evidence.json",
        "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/readiness_warning_evidence/ES_2026_readiness_warning_evidence.md",
    ],
    "warning": "statistics enrichment sparse: missing_rows=6 stale_rows=6",
}
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

ENTRY_OFFSET_BARS = 1
PRIMARY_TARGET_HORIZON_BARS = 30
CONFIRMATION_TARGET_HORIZON_BARS = 60
DIAGNOSTIC_TARGET_HORIZON_BARS = 15
EXIT_OFFSET_BARS = ENTRY_OFFSET_BARS + PRIMARY_TARGET_HORIZON_BARS
REGIME_OFFSET_BARS = ENTRY_OFFSET_BARS + CONFIRMATION_TARGET_HORIZON_BARS
DIAGNOSTIC_EXIT_OFFSET_BARS = ENTRY_OFFSET_BARS + DIAGNOSTIC_TARGET_HORIZON_BARS
ATR_LOOKBACK_BARS = 60
LABEL_SEMANTICS_ID = (
    "phase3_labels_v2_next_1m_open_30m_primary_60m_confirm_apex_aware"
)
APEX_EOD_TIMEZONE = ZoneInfo("America/New_York")
APEX_EOD_SNAPSHOT_TIME = time(16, 59, 59)
APEX_NO_HOLD_CLOSE_BUFFER_MINUTES = 5
APEX_ROW_MAE_REJECT_DOLLARS = 250.0

REQUIRED_INPUT_COLUMNS = [
    "ts",
    "market",
    "year",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "causal_valid",
    "session_segment_id",
    "is_synthetic",
    "valid_ohlcv",
    "boundary_session_flag",
    "roll_window_flag",
]

GENERIC_LABEL_COLUMNS = [
    "target_entry_ts",
    "target_exit_ts",
    "target_entry_price",
    "target_exit_price",
    "target_horizon_bars",
    "target_ret_30m",
    "target_ret_ticks_30m",
    "target_gross_dollars_30m",
    "target_estimated_cost_ticks",
    "target_estimated_cost_dollars",
    "target_net_ticks_after_est_cost",
    "target_net_dollars_after_est_cost",
    "target_sign_30m",
    "target_sign_with_deadzone",
    "target_tradeable_after_cost",
    "target_valid",
    "target_invalid_reason",
]

REGIME_LABEL_COLUMNS = [
    "target_entry_ts_30m",
    "target_exit_ts_30m",
    "target_entry_price_30m",
    "target_exit_price_30m",
    "target_horizon_bars_30m",
    "target_30m_valid",
    "target_30m_invalid_reason",
    "target_net_ticks_after_est_cost_30m",
    "target_net_dollars_after_est_cost_30m",
    "target_sign_with_deadzone_30m",
    "target_tradeable_after_cost_30m",
    "target_mfe_long_ticks_30m",
    "target_mae_long_ticks_30m",
    "target_mfe_short_ticks_30m",
    "target_mae_short_ticks_30m",
    "target_mfe_long_dollars_30m",
    "target_mae_long_dollars_30m",
    "target_mfe_short_dollars_30m",
    "target_mae_short_dollars_30m",
    "target_favorable_after_cost_long_30m",
    "target_favorable_after_cost_short_30m",
    "target_favorable_after_cost_30m",
    "target_fillable_after_slippage_long_30m",
    "target_fillable_after_slippage_short_30m",
    "target_fillable_after_slippage_30m",
    "target_apex_dll_eod_threat_long_30m",
    "target_apex_dll_eod_threat_short_30m",
    "target_apex_dll_eod_threat_30m",
    "target_no_hold_into_close_30m",
    "target_accept_long_30m",
    "target_accept_short_30m",
    "target_accept_any_30m",
    "target_entry_ts_60m",
    "target_exit_ts_60m",
    "target_entry_price_60m",
    "target_exit_price_60m",
    "target_horizon_bars_60m",
    "target_60m_valid",
    "target_60m_invalid_reason",
    "target_ret_60m",
    "target_ret_ticks_60m",
    "target_gross_dollars_60m",
    "target_net_ticks_after_est_cost_60m",
    "target_net_dollars_after_est_cost_60m",
    "target_sign_60m",
    "target_sign_with_deadzone_60m",
    "target_tradeable_after_cost_60m",
    "target_mfe_long_ticks_60m",
    "target_mae_long_ticks_60m",
    "target_mfe_short_ticks_60m",
    "target_mae_short_ticks_60m",
    "target_mfe_long_dollars_60m",
    "target_mae_long_dollars_60m",
    "target_mfe_short_dollars_60m",
    "target_mae_short_dollars_60m",
    "target_favorable_after_cost_long_60m",
    "target_favorable_after_cost_short_60m",
    "target_favorable_after_cost_60m",
    "target_fillable_after_slippage_long_60m",
    "target_fillable_after_slippage_short_60m",
    "target_fillable_after_slippage_60m",
    "target_apex_dll_eod_threat_long_60m",
    "target_apex_dll_eod_threat_short_60m",
    "target_apex_dll_eod_threat_60m",
    "target_no_hold_into_close_60m",
    "target_accept_long_60m",
    "target_accept_short_60m",
    "target_accept_any_60m",
    "target_apex_confirmed_long_30m_60m",
    "target_apex_confirmed_short_30m_60m",
    "target_apex_confirmed_any_30m_60m",
    "diagnostic_valid_15m",
    "diagnostic_ret_15m",
    "diagnostic_ret_ticks_15m",
    "diagnostic_gross_dollars_15m",
    "diagnostic_mfe_long_ticks_15m",
    "diagnostic_mae_long_ticks_15m",
    "diagnostic_mfe_short_ticks_15m",
    "diagnostic_mae_short_ticks_15m",
    "diagnostic_favorable_after_cost_15m",
]

LABEL_PROVENANCE_COLUMNS = [
    "label_semantics",
    "cost_source",
    "cost_provisional",
]

LABEL_COLUMNS = GENERIC_LABEL_COLUMNS + REGIME_LABEL_COLUMNS + LABEL_PROVENANCE_COLUMNS

DEFAULT_MARKET_CONFIGS = {
    "CL": {
        "tick_size": 0.01,
        "tick_value": 10.0,
        "point_value": 1000.0,
        "min_profit_ticks": 2.0,
        "min_stop_ticks": 4.0,
        "estimated_cost_ticks": 2.0,
    },
    "ES": {
        "tick_size": 0.25,
        "tick_value": 12.5,
        "point_value": 50.0,
        "min_profit_ticks": 2.0,
        "min_stop_ticks": 4.0,
        "estimated_cost_ticks": 2.0,
    },
    "ZN": {
        "tick_size": 1.0 / 64.0,
        "tick_value": 15.625,
        "point_value": 1000.0,
        "min_profit_ticks": 2.0,
        "min_stop_ticks": 4.0,
        "estimated_cost_ticks": 2.0,
    },
}

UNKNOWN_MARKET_DEFAULT = {
    "tick_size": 0.01,
    "tick_value": 10.0,
    "point_value": 1000.0,
    "min_profit_ticks": 2.0,
    "min_stop_ticks": 4.0,
    "estimated_cost_ticks": 2.0,
}


@dataclass
class MarketConfig:
    market: str
    tick_size: float
    tick_value: float
    point_value: float
    min_profit_ticks: float
    min_stop_ticks: float
    estimated_cost_ticks: float
    estimated_cost_dollars: float
    source: str
    cost_source: str
    provisional: bool
    defaults_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "market": self.market,
            "tick_size": self.tick_size,
            "tick_value": self.tick_value,
            "point_value": self.point_value,
            "min_profit_ticks": self.min_profit_ticks,
            "min_stop_ticks": self.min_stop_ticks,
            "estimated_cost_ticks": self.estimated_cost_ticks,
            "estimated_cost_dollars": self.estimated_cost_dollars,
            "source": self.source,
            "cost_source": self.cost_source,
            "provisional": self.provisional,
            "defaults_used": self.defaults_used,
        }


@dataclass
class LabelResult:
    profile: str
    market: str
    year: int
    input_path: str
    output_path: str
    input_rows: int = 0
    output_rows: int = 0
    target_valid_rows: int = 0
    target_invalid_rows: int = 0
    invalid_reason_counts: dict[str, int] = field(default_factory=dict)
    roll_detection_available: bool = False
    roll_detection_available_rows: int = 0
    roll_detection_unavailable_rows: int = 0
    roll_protection_unavailable: bool = False
    config: dict[str, object] = field(default_factory=dict)
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
        return data


@dataclass(frozen=True)
class AcceptedReadinessExceptions:
    path: Path
    warning_messages: list[str]
    exceptions: list[dict[str, object]]


def relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def config_hash(paths: Iterable[Path]) -> str:
    payload = {
        relative_path(path): hash_optional_file(path)
        for path in paths
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _resolved_path(path: Path) -> Path:
    candidate = path if path.is_absolute() else Path.cwd() / path
    return candidate.expanduser().resolve()


def _same_path(left: Path, right: Path) -> bool:
    return _resolved_path(left) == _resolved_path(right)


def load_accepted_readiness_exceptions(
    exceptions_path: Path | None,
    input_root: Path,
    *,
    profile: str,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    selected_market_years: Iterable[tuple[str, int]] | None = None,
) -> AcceptedReadinessExceptions | None:
    if exceptions_path is None:
        return None
    if _same_path(exceptions_path, profile_config_path) and _same_path(
        exceptions_path, APPROVED_ES2026_ACCEPTED_EXCEPTIONS_PATH
    ):
        return load_es2026_accepted_readiness_exceptions(
            exceptions_path,
            input_root,
            profile=profile,
            selected_market_years=selected_market_years,
        )
    if not _same_path(exceptions_path, APPROVED_TIER1_ACCEPTED_EXCEPTIONS_PATH):
        raise SystemExit(
            "accepted_readiness_exceptions path is not approved: "
            f"{relative_path(exceptions_path)}"
        )
    if not _same_path(input_root, APPROVED_TIER1_CANDIDATE_ROOT):
        raise SystemExit(
            "accepted_readiness_exceptions require input-root "
            f"{APPROVED_TIER1_CANDIDATE_ROOT.as_posix()}: "
            f"{relative_path(input_root)}"
        )
    if not exceptions_path.exists():
        raise SystemExit(
            "accepted_readiness_exceptions file missing: "
            f"{relative_path(exceptions_path)}"
        )
    try:
        payload = json.loads(exceptions_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(
            "accepted_readiness_exceptions file unreadable: "
            f"{relative_path(exceptions_path)}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise SystemExit("accepted_readiness_exceptions file is not a JSON object")
    if payload.get("profile") != "tier_1":
        raise SystemExit("accepted_readiness_exceptions profile is not tier_1")
    if payload.get("resolved_profile") != "tier_1_research":
        raise SystemExit(
            "accepted_readiness_exceptions resolved_profile is not tier_1_research"
        )
    if float(payload.get("global_threshold", -1.0)) != APPROVED_TIER1_GLOBAL_SYNTHETIC_THRESHOLD:
        raise SystemExit(
            "accepted_readiness_exceptions global_threshold changed: "
            f"{payload.get('global_threshold')!r}"
        )

    raw_exceptions = payload.get("exceptions")
    if not isinstance(raw_exceptions, list):
        raise SystemExit("accepted_readiness_exceptions exceptions is not a list")
    if len(raw_exceptions) != len(APPROVED_TIER1_ACCEPTED_EXCEPTIONS):
        raise SystemExit(
            "accepted_readiness_exceptions count is not exactly "
            f"{len(APPROVED_TIER1_ACCEPTED_EXCEPTIONS)}"
        )

    seen: set[tuple[str, int]] = set()
    accepted: list[dict[str, object]] = []
    for item in raw_exceptions:
        if not isinstance(item, Mapping):
            raise SystemExit("accepted_readiness_exceptions contains a non-object row")
        try:
            key = (str(item.get("market")), int(item.get("year")))  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SystemExit(
                "accepted_readiness_exceptions row has invalid market/year"
            ) from exc
        expected = APPROVED_TIER1_ACCEPTED_EXCEPTIONS.get(key)
        if expected is None or key in seen:
            raise SystemExit(
                "accepted_readiness_exceptions row is not an approved market/year: "
                f"{key[0]} {key[1]}"
            )
        seen.add(key)
        for field_name in ("category", "metric"):
            if item.get(field_name) != expected[field_name]:
                raise SystemExit(
                    "accepted_readiness_exceptions row has wrong "
                    f"{field_name} for {key[0]} {key[1]}: {item.get(field_name)!r}"
                )
        for field_name in ("observed", "approved_limit"):
            if float(item.get(field_name, -1.0)) != float(expected[field_name]):
                raise SystemExit(
                    "accepted_readiness_exceptions row has wrong "
                    f"{field_name} for {key[0]} {key[1]}: {item.get(field_name)!r}"
                )
        warning_prefixes = item.get("warning_prefixes")
        if warning_prefixes != [expected["warning"]]:
            raise SystemExit(
                "accepted_readiness_exceptions row has wrong warning for "
                f"{key[0]} {key[1]}"
            )
        accepted.append(
            {
                "market": key[0],
                "year": key[1],
                "category": expected["category"],
                "metric": expected["metric"],
                "observed": expected["observed"],
                "approved_limit": expected["approved_limit"],
                "warning": expected["warning"],
            }
        )

    missing = sorted(set(APPROVED_TIER1_ACCEPTED_EXCEPTIONS) - seen)
    if missing:
        raise SystemExit(f"accepted_readiness_exceptions missing rows: {missing}")

    return AcceptedReadinessExceptions(
        path=exceptions_path,
        warning_messages=[
            str(APPROVED_TIER1_ACCEPTED_EXCEPTIONS[key]["warning"])
            for key in sorted(APPROVED_TIER1_ACCEPTED_EXCEPTIONS)
        ],
        exceptions=sorted(accepted, key=lambda row: (str(row["market"]), int(row["year"]))),
    )


def load_es2026_accepted_readiness_exceptions(
    exceptions_path: Path,
    input_root: Path,
    *,
    profile: str,
    selected_market_years: Iterable[tuple[str, int]] | None,
) -> AcceptedReadinessExceptions:
    if profile != APPROVED_ES2026_ACCEPTED_EXCEPTIONS_PROFILE:
        raise SystemExit(
            "accepted_readiness_exceptions ES 2026 packet requires profile "
            f"{APPROVED_ES2026_ACCEPTED_EXCEPTIONS_PROFILE}: {profile}"
        )
    if not _same_path(input_root, APPROVED_ES2026_CANDIDATE_ROOT):
        raise SystemExit(
            "accepted_readiness_exceptions ES 2026 packet requires input-root "
            f"{APPROVED_ES2026_CANDIDATE_ROOT.as_posix()}: "
            f"{relative_path(input_root)}"
        )
    selected = sorted(
        (str(market), int(year))
        for market, year in (selected_market_years or [])
    )
    if selected != [("ES", 2026)]:
        raise SystemExit(
            "accepted_readiness_exceptions ES 2026 packet requires exact selected scope "
            f"[('ES', 2026)]: {selected}"
        )
    if not exceptions_path.exists():
        raise SystemExit(
            "accepted_readiness_exceptions file missing: "
            f"{relative_path(exceptions_path)}"
        )
    try:
        payload = yaml.safe_load(exceptions_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise SystemExit(
            "accepted_readiness_exceptions file unreadable: "
            f"{relative_path(exceptions_path)}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise SystemExit("accepted_readiness_exceptions profile config is not a YAML object")
    profiles = payload.get("profiles")
    profile_payload = (
        profiles.get(APPROVED_ES2026_ACCEPTED_EXCEPTIONS_PROFILE)
        if isinstance(profiles, Mapping)
        else None
    )
    if not isinstance(profile_payload, Mapping):
        raise SystemExit(
            "accepted_readiness_exceptions profile config missing "
            f"{APPROVED_ES2026_ACCEPTED_EXCEPTIONS_PROFILE}"
        )
    raw_exceptions = profile_payload.get("accepted_readiness_exceptions")
    if not isinstance(raw_exceptions, list):
        raise SystemExit("accepted_readiness_exceptions ES 2026 packet is not a list")
    if len(raw_exceptions) != 1:
        raise SystemExit(
            "accepted_readiness_exceptions ES 2026 packet count is not exactly 1"
        )
    item = raw_exceptions[0]
    if not isinstance(item, Mapping):
        raise SystemExit("accepted_readiness_exceptions ES 2026 packet row is not an object")
    expected = APPROVED_ES2026_ACCEPTED_EXCEPTION
    for field_name in ("category", "market", "year", "reason", "evidence_paths"):
        if item.get(field_name) != expected[field_name]:
            raise SystemExit(
                "accepted_readiness_exceptions ES 2026 packet has wrong "
                f"{field_name}: {item.get(field_name)!r}"
            )
    if item.get("warning_prefixes") != [expected["warning"]]:
        raise SystemExit(
            "accepted_readiness_exceptions ES 2026 packet has wrong warning_prefixes"
        )
    accepted = {
        "market": expected["market"],
        "year": expected["year"],
        "category": expected["category"],
        "reason": expected["reason"],
        "evidence_paths": expected["evidence_paths"],
        "warning": expected["warning"],
    }
    return AcceptedReadinessExceptions(
        path=exceptions_path,
        warning_messages=[str(expected["warning"])],
        exceptions=[accepted],
    )


def validate_manifest_accepted_readiness_exceptions(
    manifest: Mapping[str, object] | None,
    accepted: AcceptedReadinessExceptions | None,
) -> None:
    if accepted is None:
        return
    if manifest is None:
        raise SystemExit("causal_base_manifest_gate returned no manifest")
    expected_warnings = {
        (str(row["market"]), int(row["year"])): str(row["warning"])
        for row in accepted.exceptions
    }
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        raise SystemExit("causal_base_manifest outputs missing for accepted warnings")
    failures: list[str] = []
    seen: set[tuple[str, int]] = set()
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        try:
            key = (str(output.get("market")), int(output.get("year")))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        warnings = [str(item) for item in output.get("warnings", []) or []]
        if not warnings:
            continue
        expected = expected_warnings.get(key)
        if expected is None:
            failures.append(f"unapproved warning row: {key[0]} {key[1]}")
            continue
        if warnings != [expected]:
            failures.append(f"unexpected warning text for {key[0]} {key[1]}")
            continue
        seen.add(key)
    missing = sorted(set(expected_warnings) - seen)
    if missing:
        failures.append(f"approved warnings not carried by manifest: {missing}")
    if failures:
        raise SystemExit("accepted_readiness_exceptions manifest check failed: " + "; ".join(failures))


def annotate_gate_with_accepted_readiness_exceptions(
    evidence: dict[str, object],
    accepted: AcceptedReadinessExceptions | None,
) -> None:
    if accepted is None:
        return
    evidence["accepted_readiness_exceptions_path"] = relative_path(accepted.path)
    evidence["accepted_readiness_exception_count"] = len(accepted.exceptions)
    evidence["accepted_readiness_exceptions"] = accepted.exceptions


def discover_inputs(input_root: Path) -> list[tuple[str, int, Path]]:
    if not input_root.exists():
        raise SystemExit(f"Input root does not exist: {input_root}")

    inputs: list[tuple[str, int, Path]] = []
    for market_dir in sorted(path for path in input_root.iterdir() if path.is_dir()):
        for parquet_path in sorted(market_dir.glob("*.parquet")):
            if parquet_path.stem.isdigit():
                inputs.append((market_dir.name, int(parquet_path.stem), parquet_path))

    if not inputs:
        raise SystemExit(f"No causal year parquet files found under {input_root}")
    return inputs


def _read_yaml(path: Path) -> Mapping[str, object]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        return {}
    return payload


def load_profile_map(
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
) -> tuple[dict[str, list[str]], dict[str, list[int]], dict[str, str], set[str]]:
    markets = {key: value[:] for key, value in STATIC_PROFILE_MARKETS.items()}
    years = {key: value[:] for key, value in STATIC_PROFILE_YEARS.items()}
    aliases: dict[str, str] = {}
    discovery = set(DISCOVERY_PROFILES)

    payload = _read_yaml(profile_config_path)
    if not payload:
        aliases.update(STATIC_PROFILE_ALIASES)
    profiles = payload.get("profiles", {})
    if isinstance(profiles, Mapping):
        for profile_name, profile in profiles.items():
            if not isinstance(profile_name, str) or not isinstance(profile, Mapping):
                continue
            if bool(profile.get("discovery", False)):
                discovery.add(profile_name)
                continue
            profile_markets = profile.get("markets", [])
            profile_years = profile.get("years", [])
            if isinstance(profile_markets, list) and isinstance(profile_years, list):
                markets[profile_name] = [str(item) for item in profile_markets]
                years[profile_name] = [int(item) for item in profile_years]

    raw_aliases = payload.get("aliases", {})
    if isinstance(raw_aliases, Mapping):
        aliases.update({str(key): str(value) for key, value in raw_aliases.items()})

    return markets, years, aliases, discovery


def resolve_profile_name(profile: str, aliases: Mapping[str, str]) -> str:
    seen: set[str] = set()
    resolved = profile
    while resolved in aliases:
        if resolved in seen:
            raise SystemExit(f"Profile alias cycle detected at {resolved!r}")
        seen.add(resolved)
        resolved = aliases[resolved]
    return resolved


def resolve_profile_inputs(
    profile: str,
    input_root: Path,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
) -> list[tuple[str, int, Path]]:
    profile_markets, profile_years, aliases, discovery_profiles = load_profile_map(
        profile_config_path
    )
    resolved_profile = resolve_profile_name(profile, aliases)

    if resolved_profile in discovery_profiles:
        return discover_inputs(input_root)

    if resolved_profile not in profile_markets:
        known = ", ".join(sorted([*profile_markets, *discovery_profiles]))
        raise SystemExit(f"Unknown profile {profile!r}. Known profiles: {known}")

    return [
        (market, year, input_root / market / f"{year}.parquet")
        for market in profile_markets[resolved_profile]
        for year in profile_years[resolved_profile]
    ]


def parse_csv_filter(value: str | None, *, cast_type: type = str) -> set[object] | None:
    if value is None or not value.strip():
        return None
    parsed: set[object] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if item:
            parsed.add(cast_type(item))
    return parsed


def select_profile_inputs(
    inputs: list[tuple[str, int, Path]],
    *,
    markets: set[object] | None = None,
    years: set[object] | None = None,
) -> tuple[list[tuple[str, int, Path]], dict[str, object]]:
    selected = list(inputs)
    requested_markets = {str(item) for item in markets} if markets else None
    requested_years = {int(item) for item in years} if years else None
    if requested_markets is not None:
        selected = [item for item in selected if item[0] in requested_markets]
    if requested_years is not None:
        selected = [item for item in selected if item[1] in requested_years]
    if not selected:
        raise SystemExit("No Phase 3 inputs selected after filters")
    selection = {
        "profile_input_count": len(inputs),
        "selected_input_count": len(selected),
        "requested_markets": sorted(requested_markets) if requested_markets else None,
        "requested_years": sorted(requested_years) if requested_years else None,
        "selected_markets": sorted({market for market, _, _ in selected}),
        "selected_years": sorted({year for _, year, _ in selected}),
    }
    return selected, selection


def infer_market_year(path: Path) -> tuple[str, int]:
    try:
        return path.parent.name, int(path.stem)
    except ValueError as exc:
        raise ValueError(f"Cannot infer market/year from {path}") from exc


def _market_config_blob(raw: Mapping[str, object], market: str) -> Mapping[str, object]:
    for key in ("markets", "market_configs", "contracts"):
        nested = raw.get(key)
        if isinstance(nested, Mapping) and isinstance(nested.get(market), Mapping):
            return nested[market]  # type: ignore[return-value]
    if isinstance(raw.get(market), Mapping):
        return raw[market]  # type: ignore[return-value]
    return {}


def _float_field(
    data: Mapping[str, object],
    defaults: Mapping[str, float],
    field_name: str,
    defaults_used: list[str],
) -> float:
    value = data.get(field_name)
    if value is None:
        defaults_used.append(field_name)
        return float(defaults[field_name])
    return float(value)


def _cost_ticks(
    data: Mapping[str, object],
    tick_value: float,
    default_cost_ticks: float,
    defaults_used: list[str],
) -> float:
    for field_name in (
        "estimated_cost_ticks",
        "target_estimated_cost_ticks",
        "round_trip_cost_ticks",
        "round_turn_cost_ticks",
        "cost_ticks",
        "total_cost_ticks",
    ):
        if data.get(field_name) is not None:
            return float(data[field_name])

    for field_name in (
        "estimated_cost_dollars",
        "target_estimated_cost_dollars",
        "round_trip_cost_dollars",
        "round_turn_cost_dollars",
        "cost_dollars",
        "total_cost_dollars",
    ):
        if data.get(field_name) is not None:
            return float(data[field_name]) / tick_value

    slippage = float(data.get("slippage_ticks_per_side", 0.0) or 0.0)
    commission = float(
        data.get("commission_per_side_dollars", data.get("commission_per_contract_dollars", 0.0))
        or 0.0
    )
    fees = float(data.get("fees_per_side_dollars", 0.0) or 0.0)
    if slippage or commission or fees:
        return (2.0 * slippage) + (2.0 * (commission + fees) / tick_value)

    defaults_used.append("estimated_cost_ticks")
    return float(default_cost_ticks)


def load_market_config(market: str, costs_config: Path) -> MarketConfig:
    base_defaults = DEFAULT_MARKET_CONFIGS.get(market, UNKNOWN_MARKET_DEFAULT)
    data: Mapping[str, object] = {}
    source = "embedded_defaults"
    defaults_used: list[str] = []

    if costs_config.exists():
        raw = yaml.safe_load(costs_config.read_text(encoding="utf-8")) or {}
        if isinstance(raw, Mapping):
            data = _market_config_blob(raw, market)
            source = relative_path(costs_config)
            if not data:
                defaults_used.append("market_cost_missing")
        else:
            defaults_used.append("invalid_costs_config_shape")
    else:
        defaults_used.append("costs_config_missing")

    tick_size = _float_field(data, base_defaults, "tick_size", defaults_used)
    tick_value = _float_field(data, base_defaults, "tick_value", defaults_used)
    point_value = _float_field(data, base_defaults, "point_value", defaults_used)
    min_profit_ticks = _float_field(data, base_defaults, "min_profit_ticks", defaults_used)
    min_stop_ticks = _float_field(data, base_defaults, "min_stop_ticks", defaults_used)
    estimated_cost_ticks = _cost_ticks(
        data,
        tick_value,
        float(base_defaults["estimated_cost_ticks"]),
        defaults_used,
    )

    return MarketConfig(
        market=market,
        tick_size=tick_size,
        tick_value=tick_value,
        point_value=point_value,
        min_profit_ticks=min_profit_ticks,
        min_stop_ticks=min_stop_ticks,
        estimated_cost_ticks=estimated_cost_ticks,
        estimated_cost_dollars=estimated_cost_ticks * tick_value,
        source=source,
        cost_source=str(data.get("cost_source", source)),
        provisional=bool(data.get("provisional", bool(defaults_used))),
        defaults_used=sorted(set(defaults_used)),
    )


def _as_bool(df: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=bool)
    return df[column].fillna(default).astype(bool)


def _future_path_checks(df: pd.DataFrame, horizon_offset: int) -> dict[str, pd.Series]:
    idx = df.index
    current_segment = df["session_segment_id"].astype("string")
    synthetic = pd.Series(False, index=idx)
    invalid_ohlcv = pd.Series(False, index=idx)
    boundary = pd.Series(False, index=idx)
    roll = pd.Series(False, index=idx)
    segment_cross = pd.Series(False, index=idx)
    phase2_not_ready = pd.Series(False, index=idx)

    roll_boundary = _as_bool(df, "roll_boundary_flag")
    phase2_ready = (
        _as_bool(df, "phase2_ready")
        if "phase2_ready" in df.columns
        else _as_bool(df, "causal_valid")
    )
    for offset in range(0, horizon_offset + 1):
        synthetic |= _as_bool(df, "is_synthetic").shift(-offset, fill_value=False)
        invalid_ohlcv |= ~_as_bool(df, "valid_ohlcv", default=True).shift(
            -offset, fill_value=True
        )
        phase2_not_ready |= ~phase2_ready.shift(-offset, fill_value=True)
        boundary |= _as_bool(df, "boundary_session_flag").shift(-offset, fill_value=False)
        roll |= _as_bool(df, "roll_window_flag").shift(-offset, fill_value=False)
        roll |= roll_boundary.shift(-offset, fill_value=False)
        if offset == 0:
            continue
        shifted_segment = df["session_segment_id"].astype("string").shift(-offset)
        segment_cross |= shifted_segment.ne(current_segment).fillna(True)

    return {
        "synthetic": synthetic.astype(bool),
        "invalid_ohlcv": invalid_ohlcv.astype(bool),
        "boundary": boundary.astype(bool),
        "roll": roll.astype(bool),
        "segment_cross": segment_cross.astype(bool),
        "phase2_not_ready": phase2_not_ready.astype(bool),
    }


def _true_range_ticks(df: pd.DataFrame, tick_size: float) -> pd.Series:
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    session = df["session_segment_id"].astype("string")
    valid = (
        _as_bool(df, "causal_valid")
        & _as_bool(df, "valid_ohlcv", default=True)
        & ~_as_bool(df, "is_synthetic")
        & ~_as_bool(df, "boundary_session_flag")
        & ~_as_bool(df, "roll_window_flag")
        & ~_as_bool(df, "roll_boundary_flag")
        & _price_valid(high)
        & _price_valid(low)
        & _price_valid(close)
    )
    run_start = session.ne(session.shift()).fillna(True) | ~valid | ~valid.shift(
        fill_value=False
    )
    run_id = pd.Series(run_start.to_numpy(dtype=bool), index=df.index).cumsum()
    prev_close = close.groupby(run_id, dropna=False).shift(1)
    true_range = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1).where(valid)
    atr = true_range.groupby(run_id, dropna=False).rolling(
        ATR_LOOKBACK_BARS, min_periods=1
    ).mean()
    return atr.reset_index(level=0, drop=True) / tick_size


def _future_extreme(df: pd.DataFrame, column: str, horizon_offset: int, op: str) -> pd.Series:
    shifted = [
        pd.to_numeric(df[column], errors="coerce").shift(-offset)
        for offset in range(1, horizon_offset + 1)
    ]
    frame = pd.concat(shifted, axis=1)
    if op == "max":
        return frame.max(axis=1)
    if op == "min":
        return frame.min(axis=1)
    raise ValueError(f"Unknown future extreme op: {op}")


def _first_hit(
    df: pd.DataFrame,
    entry_price: pd.Series,
    threshold_ticks: pd.Series,
    tick_size: float,
    *,
    horizon_offset: int,
    side: str,
    kind: str,
) -> np.ndarray:
    first = np.full(len(df), np.inf)
    for offset in range(1, horizon_offset + 1):
        high = pd.to_numeric(df["high"], errors="coerce").shift(-offset)
        low = pd.to_numeric(df["low"], errors="coerce").shift(-offset)
        if side == "long" and kind == "profit":
            hit = high >= entry_price + threshold_ticks * tick_size
        elif side == "long" and kind == "adverse":
            hit = low <= entry_price - threshold_ticks * tick_size
        elif side == "short" and kind == "profit":
            hit = low <= entry_price - threshold_ticks * tick_size
        elif side == "short" and kind == "adverse":
            hit = high >= entry_price + threshold_ticks * tick_size
        else:
            raise ValueError(f"Unsupported hit type: {side} {kind}")
        mask = np.isinf(first) & hit.fillna(False).to_numpy()
        first[mask] = float(offset)
    return first


def _past_session_levels(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    segment = df["session_segment_id"].astype("string")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
    typical = (high + low + close) / 3.0

    pv = (typical * volume).groupby(segment, dropna=False).cumsum()
    cum_volume = volume.groupby(segment, dropna=False).cumsum()
    vwap = pv / cum_volume.replace(0.0, np.nan)
    session_mid = (
        high.groupby(segment, dropna=False).cummax()
        + low.groupby(segment, dropna=False).cummin()
    ) / 2.0
    return vwap, session_mid


def _price_valid(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.notna() & np.isfinite(numeric) & (numeric > 0)


def _apex_close_buffer_start_seconds() -> int:
    close_seconds = (
        APEX_EOD_SNAPSHOT_TIME.hour * 3600
        + APEX_EOD_SNAPSHOT_TIME.minute * 60
        + APEX_EOD_SNAPSHOT_TIME.second
    )
    return max(0, close_seconds - APEX_NO_HOLD_CLOSE_BUFFER_MINUTES * 60)


def _apex_eod_close_buffer_flag(df: pd.DataFrame, horizon_offset: int) -> pd.Series:
    timestamps = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    close_seconds = (
        APEX_EOD_SNAPSHOT_TIME.hour * 3600
        + APEX_EOD_SNAPSHOT_TIME.minute * 60
        + APEX_EOD_SNAPSHOT_TIME.second
    )
    buffer_start = _apex_close_buffer_start_seconds()
    flagged = pd.Series(False, index=df.index)

    for offset in range(ENTRY_OFFSET_BARS, horizon_offset + 1):
        local_ts = timestamps.shift(-offset).dt.tz_convert(APEX_EOD_TIMEZONE)
        seconds = (
            local_ts.dt.hour * 3600
            + local_ts.dt.minute * 60
            + local_ts.dt.second
        )
        flagged |= (
            local_ts.notna()
            & seconds.ge(buffer_start)
            & seconds.le(close_seconds)
        )

    return flagged.astype(bool)


def _target_invalid_reason(
    index: pd.Index,
    target_valid: pd.Series,
    reason_masks: list[tuple[str, pd.Series]],
) -> pd.Series:
    invalid_reason = pd.Series(pd.NA, index=index, dtype="string")
    for reason, mask in reason_masks:
        invalid_reason = invalid_reason.mask(
            invalid_reason.isna() & ~target_valid & mask,
            reason,
        )
    return invalid_reason


def _horizon_label_values(
    df: pd.DataFrame,
    config: MarketConfig,
    *,
    horizon_bars: int,
    horizon_offset: int,
    suffix: str,
    causal_valid: pd.Series,
    entry_price: pd.Series,
    entry_ts: pd.Series,
    tick_size: float,
    tick_value: float,
) -> dict[str, pd.Series]:
    exit_price = pd.to_numeric(df["open"], errors="coerce").shift(-horizon_offset)
    exit_ts = pd.to_datetime(df["ts"], utc=True, errors="coerce").shift(-horizon_offset)
    checks = _future_path_checks(df, horizon_offset)
    close_buffer = _apex_eod_close_buffer_flag(df, horizon_offset)
    no_hold_into_close = ~close_buffer

    entry_missing = entry_ts.isna()
    exit_missing = exit_ts.isna()
    entry_exit_invalid = ~_price_valid(entry_price) | ~_price_valid(exit_price)
    target_valid = (
        causal_valid
        & ~entry_missing
        & ~exit_missing
        & no_hold_into_close
        & ~checks["segment_cross"]
        & ~checks["synthetic"]
        & ~checks["invalid_ohlcv"]
        & ~checks["phase2_not_ready"]
        & ~checks["boundary"]
        & ~checks["roll"]
        & ~entry_exit_invalid
    )
    invalid_reason = _target_invalid_reason(
        df.index,
        target_valid,
        [
            ("current_causal_valid_false", ~causal_valid),
            ("entry_missing", entry_missing),
            ("exit_missing", exit_missing),
            ("apex_eod_close_buffer", close_buffer),
            ("session_segment_cross", checks["segment_cross"]),
            ("synthetic_path", checks["synthetic"]),
            ("invalid_ohlcv_path", checks["invalid_ohlcv"]),
            ("phase2_not_ready_path", checks["phase2_not_ready"]),
            ("boundary_session_path", checks["boundary"]),
            ("roll_path", checks["roll"]),
            ("entry_exit_price_invalid", entry_exit_invalid),
        ],
    )

    gross_ticks = (exit_price - entry_price) / tick_size
    gross_dollars = gross_ticks * tick_value
    net_magnitude = (gross_ticks.abs() - config.estimated_cost_ticks).clip(lower=0.0)
    net_ticks = np.sign(gross_ticks) * net_magnitude
    net_dollars = net_ticks * tick_value
    sign = np.sign(gross_ticks).fillna(0).astype("int64")
    deadzone_ticks = config.estimated_cost_ticks + config.min_profit_ticks
    sign_deadzone = sign.mask(gross_ticks.abs() <= deadzone_ticks, 0).astype("int64")
    tradeable_after_cost = target_valid & gross_ticks.abs().gt(config.estimated_cost_ticks)

    future_high = _future_extreme(df, "high", horizon_offset, "max")
    future_low = _future_extreme(df, "low", horizon_offset, "min")
    mfe_long_ticks = (future_high - entry_price) / tick_size
    mae_long_ticks = (future_low - entry_price) / tick_size
    mfe_short_ticks = (entry_price - future_low) / tick_size
    mae_short_ticks = (entry_price - future_high) / tick_size
    mfe_long_dollars = mfe_long_ticks * tick_value
    mae_long_dollars = mae_long_ticks * tick_value
    mfe_short_dollars = mfe_short_ticks * tick_value
    mae_short_dollars = mae_short_ticks * tick_value

    stressed_deadzone_ticks = (2.0 * config.estimated_cost_ticks) + config.min_profit_ticks
    favorable_long = target_valid & gross_ticks.gt(deadzone_ticks)
    favorable_short = target_valid & gross_ticks.lt(-deadzone_ticks)
    fillable_long = target_valid & gross_ticks.gt(stressed_deadzone_ticks)
    fillable_short = target_valid & gross_ticks.lt(-stressed_deadzone_ticks)
    apex_threat_long = target_valid & mae_long_dollars.le(-APEX_ROW_MAE_REJECT_DOLLARS)
    apex_threat_short = target_valid & mae_short_dollars.le(-APEX_ROW_MAE_REJECT_DOLLARS)
    accept_long = favorable_long & fillable_long & ~apex_threat_long
    accept_short = favorable_short & fillable_short & ~apex_threat_short

    return {
        f"target_entry_ts_{suffix}": entry_ts.where(target_valid),
        f"target_exit_ts_{suffix}": exit_ts.where(target_valid),
        f"target_entry_price_{suffix}": entry_price.where(target_valid),
        f"target_exit_price_{suffix}": exit_price.where(target_valid),
        f"target_horizon_bars_{suffix}": pd.Series(horizon_bars, index=df.index).where(
            target_valid
        ),
        f"target_{suffix}_valid": target_valid.astype(bool),
        f"target_{suffix}_invalid_reason": invalid_reason,
        f"target_ret_{suffix}": (exit_price / entry_price - 1.0).where(target_valid),
        f"target_ret_ticks_{suffix}": gross_ticks.where(target_valid),
        f"target_gross_dollars_{suffix}": gross_dollars.where(target_valid),
        f"target_net_ticks_after_est_cost_{suffix}": net_ticks.where(target_valid),
        f"target_net_dollars_after_est_cost_{suffix}": net_dollars.where(target_valid),
        f"target_sign_{suffix}": sign.where(target_valid, 0).astype("int64"),
        f"target_sign_with_deadzone_{suffix}": sign_deadzone.where(
            target_valid, 0
        ).astype("int64"),
        f"target_tradeable_after_cost_{suffix}": tradeable_after_cost.astype(bool),
        f"target_mfe_long_ticks_{suffix}": mfe_long_ticks.where(target_valid),
        f"target_mae_long_ticks_{suffix}": mae_long_ticks.where(target_valid),
        f"target_mfe_short_ticks_{suffix}": mfe_short_ticks.where(target_valid),
        f"target_mae_short_ticks_{suffix}": mae_short_ticks.where(target_valid),
        f"target_mfe_long_dollars_{suffix}": mfe_long_dollars.where(target_valid),
        f"target_mae_long_dollars_{suffix}": mae_long_dollars.where(target_valid),
        f"target_mfe_short_dollars_{suffix}": mfe_short_dollars.where(target_valid),
        f"target_mae_short_dollars_{suffix}": mae_short_dollars.where(target_valid),
        f"target_favorable_after_cost_long_{suffix}": favorable_long.astype(bool),
        f"target_favorable_after_cost_short_{suffix}": favorable_short.astype(bool),
        f"target_favorable_after_cost_{suffix}": (favorable_long | favorable_short).astype(
            bool
        ),
        f"target_fillable_after_slippage_long_{suffix}": fillable_long.astype(bool),
        f"target_fillable_after_slippage_short_{suffix}": fillable_short.astype(bool),
        f"target_fillable_after_slippage_{suffix}": (fillable_long | fillable_short).astype(
            bool
        ),
        f"target_apex_dll_eod_threat_long_{suffix}": apex_threat_long.astype(bool),
        f"target_apex_dll_eod_threat_short_{suffix}": apex_threat_short.astype(bool),
        f"target_apex_dll_eod_threat_{suffix}": (
            apex_threat_long | apex_threat_short
        ).astype(bool),
        f"target_no_hold_into_close_{suffix}": no_hold_into_close.astype(bool),
        f"target_accept_long_{suffix}": accept_long.astype(bool),
        f"target_accept_short_{suffix}": accept_short.astype(bool),
        f"target_accept_any_{suffix}": (accept_long | accept_short).astype(bool),
    }


def _diagnostic_15m_values(
    horizon_values: Mapping[str, pd.Series],
) -> dict[str, pd.Series]:
    valid = horizon_values["target_15m_valid"]
    favorable = (
        horizon_values["target_favorable_after_cost_long_15m"]
        | horizon_values["target_favorable_after_cost_short_15m"]
    )
    return {
        "diagnostic_valid_15m": valid,
        "diagnostic_ret_15m": horizon_values["target_ret_15m"],
        "diagnostic_ret_ticks_15m": horizon_values["target_ret_ticks_15m"],
        "diagnostic_gross_dollars_15m": horizon_values["target_gross_dollars_15m"],
        "diagnostic_mfe_long_ticks_15m": horizon_values["target_mfe_long_ticks_15m"],
        "diagnostic_mae_long_ticks_15m": horizon_values["target_mae_long_ticks_15m"],
        "diagnostic_mfe_short_ticks_15m": horizon_values["target_mfe_short_ticks_15m"],
        "diagnostic_mae_short_ticks_15m": horizon_values["target_mae_short_ticks_15m"],
        "diagnostic_favorable_after_cost_15m": favorable.astype(bool),
    }


def add_labels(df: pd.DataFrame, config: MarketConfig) -> pd.DataFrame:
    df = df.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    tick_size = config.tick_size
    tick_value = config.tick_value

    entry_price = pd.to_numeric(df["open"], errors="coerce").shift(-ENTRY_OFFSET_BARS)
    entry_ts = pd.to_datetime(df["ts"], utc=True, errors="coerce").shift(-ENTRY_OFFSET_BARS)

    causal_valid = _as_bool(df, "causal_valid")

    labels_30m = _horizon_label_values(
        df,
        config,
        horizon_bars=PRIMARY_TARGET_HORIZON_BARS,
        horizon_offset=EXIT_OFFSET_BARS,
        suffix="30m",
        causal_valid=causal_valid,
        entry_price=entry_price,
        entry_ts=entry_ts,
        tick_size=tick_size,
        tick_value=tick_value,
    )
    labels_60m = _horizon_label_values(
        df,
        config,
        horizon_bars=CONFIRMATION_TARGET_HORIZON_BARS,
        horizon_offset=REGIME_OFFSET_BARS,
        suffix="60m",
        causal_valid=causal_valid,
        entry_price=entry_price,
        entry_ts=entry_ts,
        tick_size=tick_size,
        tick_value=tick_value,
    )
    labels_15m = _horizon_label_values(
        df,
        config,
        horizon_bars=DIAGNOSTIC_TARGET_HORIZON_BARS,
        horizon_offset=DIAGNOSTIC_EXIT_OFFSET_BARS,
        suffix="15m",
        causal_valid=causal_valid,
        entry_price=entry_price,
        entry_ts=entry_ts,
        tick_size=tick_size,
        tick_value=tick_value,
    )

    for column, values in labels_30m.items():
        df[column] = values
    for column, values in labels_60m.items():
        df[column] = values
    for column, values in _diagnostic_15m_values(labels_15m).items():
        df[column] = values

    df["target_entry_ts"] = df["target_entry_ts_30m"]
    df["target_exit_ts"] = df["target_exit_ts_30m"]
    df["target_entry_price"] = df["target_entry_price_30m"]
    df["target_exit_price"] = df["target_exit_price_30m"]
    df["target_horizon_bars"] = df["target_horizon_bars_30m"]
    df["target_estimated_cost_ticks"] = pd.Series(
        config.estimated_cost_ticks, index=df.index
    ).where(df["target_30m_valid"])
    df["target_estimated_cost_dollars"] = pd.Series(
        config.estimated_cost_dollars, index=df.index
    ).where(df["target_30m_valid"])
    df["target_net_ticks_after_est_cost"] = df["target_net_ticks_after_est_cost_30m"]
    df["target_net_dollars_after_est_cost"] = df["target_net_dollars_after_est_cost_30m"]
    df["target_sign_with_deadzone"] = df["target_sign_with_deadzone_30m"]
    df["target_tradeable_after_cost"] = df["target_tradeable_after_cost_30m"]
    df["target_valid"] = df["target_30m_valid"]
    df["target_invalid_reason"] = df["target_30m_invalid_reason"]
    df["target_apex_confirmed_long_30m_60m"] = (
        df["target_accept_long_30m"] & df["target_accept_long_60m"]
    )
    df["target_apex_confirmed_short_30m_60m"] = (
        df["target_accept_short_30m"] & df["target_accept_short_60m"]
    )
    df["target_apex_confirmed_any_30m_60m"] = (
        df["target_apex_confirmed_long_30m_60m"]
        | df["target_apex_confirmed_short_30m_60m"]
    )
    df["label_semantics"] = LABEL_SEMANTICS_ID
    df["cost_source"] = config.cost_source
    df["cost_provisional"] = bool(config.provisional)

    return df[[column for column in df.columns if column not in LABEL_COLUMNS] + LABEL_COLUMNS]


def process_file(
    input_path: Path,
    output_path: Path,
    *,
    profile: str,
    costs_config: Path,
) -> LabelResult:
    market, year = infer_market_year(input_path)
    config = load_market_config(market, costs_config)
    result = LabelResult(
        profile=profile,
        market=market,
        year=year,
        input_path=relative_path(input_path),
        output_path=relative_path(output_path),
        config=config.to_dict(),
    )

    if config.defaults_used:
        result.warnings.append("market config defaults used: " + ",".join(config.defaults_used))
    if (
        "costs_config_missing" in config.defaults_used
        or "market_cost_missing" in config.defaults_used
        or "estimated_cost_ticks" in config.defaults_used
    ):
        result.warnings.append("placeholder costs used")
        result.failures.append(
            "placeholder/default costs unavailable for canonical labels: "
            + ",".join(config.defaults_used)
        )
        return result
    if config.provisional:
        result.warnings.append(f"provisional costs used: {config.cost_source}")

    if not input_path.exists():
        result.failures.append("input file missing")
        return result

    df = pd.read_parquet(input_path)
    result.input_rows = len(df)
    if df.empty:
        result.failures.append("empty file")
        return result

    missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in df.columns]
    if missing:
        result.failures.append("missing required input columns: " + ",".join(missing))
        return result

    roll_detection_available = _as_bool(df, "roll_detection_available", default=False)
    result.roll_detection_available_rows = int(roll_detection_available.sum())
    result.roll_detection_unavailable_rows = int((~roll_detection_available).sum())
    result.roll_detection_available = result.roll_detection_unavailable_rows == 0
    if result.roll_detection_unavailable_rows:
        result.roll_protection_unavailable = True
        message = (
            "roll protection unavailable for "
            f"{result.roll_detection_unavailable_rows} rows: roll_detection_available false"
        )
        result.warnings.append(message)
        result.failures.append(message)
        return result

    output = add_labels(df, config)
    result.output_rows = len(output)
    result.target_valid_rows = int(output["target_valid"].sum())
    result.target_invalid_rows = result.output_rows - result.target_valid_rows
    counts = output["target_invalid_reason"].dropna().value_counts().sort_index()
    result.invalid_reason_counts = {str(k): int(v) for k, v in counts.items()}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(output_path, index=False)
    return result


def _aggregate_invalid_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    aggregate: dict[str, int] = {}
    for row in rows:
        counts = row.get("invalid_reason_counts", {})
        if not isinstance(counts, Mapping):
            continue
        for reason, count in counts.items():
            aggregate[str(reason)] = aggregate.get(str(reason), 0) + int(count)
    return dict(sorted(aggregate.items()))


def write_reports(
    results: Iterable[LabelResult],
    reports_root: Path,
    profile: str,
    *,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    costs_config_path: Path = Path("configs/costs.yaml"),
    input_root: Path | None = None,
    output_root: Path | None = None,
    causal_base_gate: Mapping[str, object] | None = None,
    input_selection: Mapping[str, object] | None = None,
) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    rows = [result.to_dict() for result in results]
    resolved_input_root = input_root or infer_artifact_root(rows, "input_path")
    resolved_output_root = output_root or infer_artifact_root(rows, "output_path")
    run_failures = [
        {
            "market": row["market"],
            "year": row["year"],
            "failures": row["failures"],
        }
        for row in rows
        if row["failures"]
    ]
    script_path = Path(__file__).resolve()
    status = (
        "FAIL"
        if any(row["status"] == "FAIL" for row in rows)
        else "WARN"
        if any(row["status"] == "WARN" for row in rows)
        else "PASS"
    )
    warning_count = int(sum(row["warning_count"] for row in rows))
    failure_count = int(sum(row["failure_count"] for row in rows))
    authority = scope_authority_metadata(
        profile=profile,
        selected_market_years=((row["market"], row["year"]) for row in rows),
        profile_config=profile_config_path,
        status=status,
        failure_count=failure_count,
        selected_input_count=int(input_selection.get("selected_input_count", len(rows)))
        if input_selection
        else len(rows),
    )
    scope = load_profile_scope(profile, profile_config_path, strict=False)
    resolved_profile = scope.resolved_profile if scope is not None else profile
    provenance = {
        "generated_at": utc_timestamp(),
        "git_commit": current_git_commit(),
        "script_path": relative_path(script_path),
        "script_hash": sha256_file(script_path),
        "config_hash": config_hash([profile_config_path, costs_config_path]),
        "input_root": resolved_input_root.as_posix() if resolved_input_root else None,
        "output_root": resolved_output_root.as_posix() if resolved_output_root else None,
        "reports_root": reports_root.as_posix(),
        "input_file_hashes": {
            str(row["input_path"]): hash_optional_file(Path(str(row["input_path"])))
            for row in rows
        },
        "output_file_hashes": {
            str(row["output_path"]): hash_optional_file(Path(str(row["output_path"])))
            for row in rows
        },
        "profile": profile,
        "resolved_profile": resolved_profile,
        "markets": sorted({str(row["market"]) for row in rows}),
        "years": sorted({int(row["year"]) for row in rows}),
        "input_selection": dict(input_selection or {}),
        "warning_count": warning_count,
        "failure_count": failure_count,
        "failures": run_failures,
        "causal_base_manifest_gate": dict(causal_base_gate or {}),
        **authority,
    }
    summary = {
        "file_count": len(rows),
        "pass_count": sum(row["status"] == "PASS" for row in rows),
        "warn_count": sum(row["status"] == "WARN" for row in rows),
        "fail_count": sum(row["status"] == "FAIL" for row in rows),
        "input_rows": int(sum(row["input_rows"] for row in rows)),
        "output_rows": int(sum(row["output_rows"] for row in rows)),
        "target_valid_rows": int(sum(row["target_valid_rows"] for row in rows)),
        "target_invalid_rows": int(sum(row["target_invalid_rows"] for row in rows)),
        "invalid_reason_counts": _aggregate_invalid_counts(rows),
        "roll_protection_unavailable_files": int(
            sum(bool(row["roll_protection_unavailable"]) for row in rows)
        ),
        "roll_detection_available_rows": int(
            sum(row["roll_detection_available_rows"] for row in rows)
        ),
        "roll_detection_unavailable_rows": int(
            sum(row["roll_detection_unavailable_rows"] for row in rows)
        ),
    }
    label_semantics = {
        "label_semantics_id": LABEL_SEMANTICS_ID,
        "target_ret_ticks_30m": (
            "primary 30m signed next-1m-open to next-31m-open move; positive means price "
            "moved up, negative means price moved down"
        ),
        "target_ret_ticks_60m": (
            "independent robustness signed next-1m-open to next-61m-open move; positive means "
            "price moved up, negative means price moved down"
        ),
        "target_net_ticks_after_est_cost": (
            "primary 30m signed directional move beyond estimated round-turn cost; costs reduce "
            "magnitude and never flip sign"
        ),
        "target_favorable_after_cost_30m": (
            "primary 30m path has enough signed close-to-close move to clear configured cost plus "
            "minimum profit deadzone"
        ),
        "target_fillable_after_slippage_30m": (
            "primary 30m path clears minimum profit after a 2x configured-cost stress"
        ),
        "target_apex_dll_eod_threat_30m": (
            "one-contract primary 30m MFE/MAE path breaches the conservative "
            f"${APEX_ROW_MAE_REJECT_DOLLARS:.0f} Apex row-risk danger threshold"
        ),
        "target_no_hold_into_close_30m": (
            "primary 30m path does not enter the Apex EOD close buffer ending at "
            f"{APEX_EOD_SNAPSHOT_TIME.isoformat()} America/New_York"
        ),
        "target_accept_any_30m": (
            "primary 30m side-aware acceptance: favorable after cost, fillable under stressed "
            "costs, no Apex row-risk danger, and no hold into close"
        ),
        "target_apex_confirmed_any_30m_60m": (
            "same side accepted by both independent 30m primary and 60m robustness labels"
        ),
        "diagnostic_ret_ticks_15m": "optional diagnostic only; not a primary target",
    }

    report = {
        **provenance,
        "stage": "labels",
        "status": status,
        "label_semantics": label_semantics,
        "files": rows,
        "summary": summary,
    }
    manifest = {
        **provenance,
        "stage": "labels",
        "status": status,
        "label_semantics": label_semantics,
        "outputs": [
            {
                "market": row["market"],
                "year": row["year"],
                "input_path": row["input_path"],
                "output_path": row["output_path"],
                "input_rows": row["input_rows"],
                "output_rows": row["output_rows"],
                "target_valid_rows": row["target_valid_rows"],
                "target_invalid_rows": row["target_invalid_rows"],
                "invalid_reason_counts": row["invalid_reason_counts"],
                "roll_detection_available": row["roll_detection_available"],
                "roll_detection_available_rows": row["roll_detection_available_rows"],
                "roll_detection_unavailable_rows": row["roll_detection_unavailable_rows"],
                "roll_protection_unavailable": row["roll_protection_unavailable"],
                "config": row["config"],
                "warnings": row["warnings"],
                "failures": row["failures"],
                "status": row["status"],
                "warning_count": row["warning_count"],
                "failure_count": row["failure_count"],
            }
            for row in rows
        ],
        "summary": summary,
    }

    (reports_root / "label_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (reports_root / "label_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--input-root", default=None)
    parser.add_argument("--output-root", default="data/labeled")
    parser.add_argument("--reports-root", default="reports/labels")
    parser.add_argument("--costs-config", default="configs/costs.yaml")
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument(
        "--markets",
        default=None,
        help="Optional comma-separated market roots to process inside the selected profile.",
    )
    parser.add_argument(
        "--years",
        default=None,
        help="Optional comma-separated years to process inside the selected profile.",
    )
    parser.add_argument(
        "--causal-base-manifest",
        default="auto",
        help="Path to Phase 2 causal_base_manifest.json, or 'auto' to find a matching PASS manifest under reports/.",
    )
    parser.add_argument(
        "--accepted-readiness-exceptions",
        default=None,
        help=(
            "Approved accepted-readiness exceptions evidence. Supported values are the "
            "legacy tier_1 candidate JSON or the bounded ES 2026 profile config packet."
        ),
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if not args.input_root:
        parser.error("--input-root is required; pass an explicit causal root")
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    reports_root = Path(args.reports_root)
    costs_config = Path(args.costs_config)
    profile_config = Path(args.profile_config)
    profile_inputs = resolve_profile_inputs(args.profile, input_root, profile_config)
    inputs, input_selection = select_profile_inputs(
        profile_inputs,
        markets=parse_csv_filter(args.markets),
        years=parse_csv_filter(args.years, cast_type=int),
    )
    scope = load_profile_scope(args.profile, profile_config, strict=False)
    resolved_profile = scope.resolved_profile if scope is not None else None
    accepted_readiness_exceptions = load_accepted_readiness_exceptions(
        Path(args.accepted_readiness_exceptions)
        if args.accepted_readiness_exceptions
        else None,
        input_root,
        profile=args.profile,
        profile_config_path=profile_config,
        selected_market_years=((market, year) for market, year, _ in inputs),
    )
    causal_base_gate = resolve_upstream_manifest_gate(
        manifest_arg=args.causal_base_manifest,
        default_manifest_path=DEFAULT_CAUSAL_BASE_MANIFEST,
        search_name="causal_base_manifest.json",
        expected_stage="causal_base",
        expected_profile=args.profile,
        expected_resolved_profile=resolved_profile,
        expected_output_root=input_root,
        expected_market_years=((market, year) for market, year, _ in inputs),
        gate_name="causal_base_manifest_gate",
        accepted_warning_messages=(
            accepted_readiness_exceptions.warning_messages
            if accepted_readiness_exceptions is not None
            else None
        ),
    )
    validate_manifest_accepted_readiness_exceptions(
        causal_base_gate.manifest,
        accepted_readiness_exceptions,
    )
    annotate_gate_with_accepted_readiness_exceptions(
        causal_base_gate.evidence,
        accepted_readiness_exceptions,
    )

    results: list[LabelResult] = []
    for market, year, input_path in inputs:
        output_path = output_root / market / f"{year}.parquet"
        result = process_file(
            input_path,
            output_path,
            profile=args.profile,
            costs_config=costs_config,
        )
        results.append(result)
        print(
            f"{result.status} {market} {year}: rows={result.input_rows} "
            f"valid={result.target_valid_rows} invalid={result.target_invalid_rows} "
            f"warnings={len(result.warnings)} failures={len(result.failures)}"
        )

    write_reports(
        results,
        reports_root,
        args.profile,
        profile_config_path=profile_config,
        costs_config_path=costs_config,
        input_root=input_root,
        output_root=output_root,
        causal_base_gate=causal_base_gate.evidence,
        input_selection=input_selection,
    )
    return 1 if any(result.failures for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
