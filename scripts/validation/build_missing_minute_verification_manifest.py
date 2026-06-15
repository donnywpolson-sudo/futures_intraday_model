from __future__ import annotations

import argparse
import json
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


def _group_synthetic_minutes(synthetic: pd.DataFrame, synthetic_ts: pd.Series) -> list[tuple[str, pd.DataFrame]]:
    work = synthetic.reset_index(drop=True).copy()
    work["_ts"] = synthetic_ts.reset_index(drop=True)
    work = work.dropna(subset=["_ts"]).sort_values("_ts", kind="mergesort").reset_index(drop=True)
    if work.empty:
        return []
    if "synthetic_gap_id" in work.columns and work["synthetic_gap_id"].notna().all():
        return [(str(gap_id), group.copy()) for gap_id, group in work.groupby("synthetic_gap_id", sort=False)]

    gap_ids: list[str] = []
    current_id = 1
    previous_ts: pd.Timestamp | None = None
    for value in work["_ts"]:
        current_ts = pd.Timestamp(value)
        if previous_ts is not None and current_ts != previous_ts + pd.Timedelta(minutes=1):
            current_id += 1
        gap_ids.append(f"generated_gap_{current_id:06d}")
        previous_ts = current_ts
    work["_generated_gap_id"] = gap_ids
    return [(str(gap_id), group.copy()) for gap_id, group in work.groupby("_generated_gap_id", sort=False)]


def _truthy_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(frame[column].fillna(False).astype(bool).sum())


def _resolve_adjacent_contract(
    raw: pd.DataFrame,
    raw_ts: pd.Series,
    first_ts: pd.Timestamp,
    last_ts: pd.Timestamp,
) -> dict[str, Any]:
    work = raw.copy()
    work["_ts"] = raw_ts
    work = work.dropna(subset=["_ts"]).sort_values("_ts", kind="mergesort")
    before = work[work["_ts"] < first_ts].tail(1)
    after = work[work["_ts"] > last_ts].head(1)
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
    }


def _window_metadata(group: pd.DataFrame, market: str, session_config: Path) -> dict[str, Any]:
    ts = pd.to_datetime(group["_ts"], utc=True, errors="coerce").dropna()
    metadata = _bucket_synthetic_timestamps(ts, market, session_config).reset_index(drop=True)
    session_buckets = _top_counts(metadata.get("session_bucket", pd.Series(dtype="string")), "bucket")
    ct_hours = _top_counts(metadata.get("ct_hour", pd.Series(dtype="int64")).astype("string"), "ct_hour")
    return {
        "session_bucket_counts": session_buckets,
        "ct_hour_buckets": ct_hours,
        "session_dates": sorted(set(metadata.get("session_date", pd.Series(dtype="string")).dropna().astype(str))),
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

    synthetic_mask = causal["is_synthetic"].fillna(False).astype(bool)
    synthetic = causal.loc[synthetic_mask].copy()
    synthetic_ts = causal_ts.loc[synthetic_mask]
    groups = _group_synthetic_minutes(synthetic, synthetic_ts)
    windows: list[dict[str, Any]] = []
    for gap_id, group in groups:
        ts = pd.to_datetime(group["_ts"], utc=True, errors="coerce").dropna()
        if ts.empty:
            continue
        first_ts = pd.Timestamp(ts.min())
        last_ts = pd.Timestamp(ts.max())
        contract = _resolve_adjacent_contract(raw, raw_ts, first_ts, last_ts)
        if contract["status"] != "resolved" and not allow_unresolved_contracts:
            failures.append(f"{market} {year} {gap_id}: adjacent contract unresolved")
            continue

        metadata = _window_metadata(group, market, session_config)
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
                "session_dates": metadata["session_dates"],
                "roll_symbol_instrument_change_flags": flag_counts,
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
    if markets and years:
        for market in markets:
            for year in years:
                market_windows, market_failures = _build_windows_for_market_year(
                    market=market,
                    year=year,
                    raw_root=Path(args.raw_root),
                    causal_root=Path(args.causal_root),
                    session_config=Path(args.session_config),
                    buffer_minutes=int(args.buffer_minutes),
                    allow_unresolved_contracts=bool(args.allow_unresolved_contracts),
                )
                windows.extend(market_windows)
                failures.extend(market_failures)

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
        "required_third_party_source_type": REQUIRED_THIRD_PARTY_SOURCE_TYPE,
        "accepted_external_trade_schema": ACCEPTED_EXTERNAL_TRADE_SCHEMA,
        "decision_placeholder": WINDOW_DECISION,
        "failures": failures,
        "summary": _summary(windows),
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.buffer_minutes < 0:
        raise SystemExit("--buffer-minutes must be >= 0")
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
