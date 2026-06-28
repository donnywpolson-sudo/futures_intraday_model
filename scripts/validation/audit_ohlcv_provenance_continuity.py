from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.phase1_raw_contract import (
    EXPECTED_COMPRESSION,
    EXPECTED_ENCODING,
    REQUIRED_DATASET,
    REQUIRED_MANIFEST_FIELDS,
    SCHEMA_PATHS,
    VENDOR,
)
from scripts.validation.audit_raw_session_gaps import (
    _bucket_synthetic_timestamps,
    _gap_size_counts,
    _largest_gaps,
    _top_counts,
)


LOW_LIQUIDITY_BUCKETS = {
    "outside_configured_session",
    "configured_evening_17_18_ct",
    "overnight_19_05_ct",
    "first_60m_after_configured_open",
    "last_60m_before_configured_close",
}


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _timestamp_column(frame: pd.DataFrame) -> pd.Series:
    if "ts_event" in frame.columns:
        return pd.to_datetime(frame["ts_event"], utc=True, errors="coerce")
    if "ts" in frame.columns:
        return pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index)
    raise ValueError("missing timestamp column/index")


def _find_single_dbn(dbn_root: Path, schema: str, market: str, year: int) -> tuple[Path | None, list[str]]:
    schema_dir = SCHEMA_PATHS[schema]
    root = dbn_root / schema_dir / market / str(year)
    if not root.exists():
        return None, [f"missing {schema} DBN directory: {_relative_path(root)}"]
    candidates = sorted(
        path
        for path in root.iterdir()
        if path.is_file()
        and (path.name.endswith(".dbn") or path.name.endswith(".dbn.zst"))
        and not path.name.endswith(".manifest.json")
    )
    if not candidates:
        return None, [f"missing {schema} DBN file: {_relative_path(root)}"]
    if len(candidates) > 1:
        return None, [f"multiple {schema} DBN files found: {_relative_path(root)}"]
    return candidates[0], []


def _audit_dbn_manifest(
    dbn_root: Path,
    schema: str,
    market: str,
    year: int,
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    dbn_path, path_failures = _find_single_dbn(dbn_root, schema, market, year)
    failures.extend(path_failures)
    if dbn_path is None:
        return {"schema": schema, "path": None, "manifest_path": None}, failures

    manifest_path = dbn_path.with_name(f"{dbn_path.name}.manifest.json")
    if not manifest_path.exists():
        failures.append(f"missing {schema} DBN manifest: {_relative_path(manifest_path)}")
        return {
            "schema": schema,
            "path": _relative_path(dbn_path),
            "manifest_path": _relative_path(manifest_path),
        }, failures

    try:
        manifest = _read_json(manifest_path)
    except Exception as exc:
        failures.append(f"unreadable {schema} DBN manifest: {exc}")
        manifest = {}

    missing_fields = [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
    if missing_fields:
        failures.append(f"{schema} DBN manifest missing fields: {missing_fields}")

    expected = {
        "vendor": VENDOR,
        "dataset": REQUIRED_DATASET,
        "schema": schema,
        "market": market,
        "encoding": EXPECTED_ENCODING,
        "compression": EXPECTED_COMPRESSION,
        "request_status": "ok",
    }
    for field, expected_value in expected.items():
        if manifest.get(field) != expected_value:
            failures.append(f"{schema} DBN manifest {field}={manifest.get(field)!r}, expected {expected_value!r}")

    current_sha256 = _file_sha256(dbn_path)
    manifest_sha256 = str(manifest.get("file_sha256", ""))
    if current_sha256 != manifest_sha256:
        failures.append(f"{schema} DBN hash mismatch: {_relative_path(dbn_path)}")
    if int(manifest.get("file_size_bytes") or -1) != dbn_path.stat().st_size:
        failures.append(f"{schema} DBN size mismatch: {_relative_path(dbn_path)}")

    return (
        {
            "schema": schema,
            "path": _relative_path(dbn_path),
            "manifest_path": _relative_path(manifest_path),
            "manifest_start": manifest.get("start"),
            "manifest_end": manifest.get("end"),
            "manifest_symbols_requested": manifest.get("symbols_requested"),
            "manifest_sha256": manifest_sha256,
            "current_sha256": current_sha256,
            "hash_matches_manifest": current_sha256 == manifest_sha256,
            "size_matches_manifest": int(manifest.get("file_size_bytes") or -1) == dbn_path.stat().st_size,
            "request_status": manifest.get("request_status"),
        },
        failures,
    )


def _non_null_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(frame[column].notna().sum())


def _source_values(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    values = frame[column].dropna().astype(str).unique().tolist()
    return sorted(values)


def _raw_consecutive_gap_summary(raw_ts: pd.Series) -> dict[str, Any]:
    clean = raw_ts.dropna().sort_values(kind="mergesort")
    if len(clean) < 2:
        return {"largest_gap_minutes": None, "gap_count_gt_1m": 0, "top_gaps": []}
    deltas = clean.diff().dropna()
    gap_minutes = (deltas.dt.total_seconds() / 60.0).round().astype("int64")
    large = gap_minutes[gap_minutes > 1]
    top_rows: list[dict[str, Any]] = []
    if not large.empty:
        for idx, minutes in large.sort_values(ascending=False).head(10).items():
            current_ts = pd.Timestamp(clean.loc[idx])
            previous_pos = clean.index.get_loc(idx) - 1
            previous_ts = pd.Timestamp(clean.iloc[previous_pos]) if previous_pos >= 0 else pd.NaT
            top_rows.append(
                {
                    "gap_minutes": int(minutes),
                    "previous_ts": previous_ts.isoformat() if not pd.isna(previous_ts) else None,
                    "next_ts": current_ts.isoformat(),
                }
            )
    return {
        "largest_gap_minutes": int(large.max()) if not large.empty else 1,
        "gap_count_gt_1m": int(len(large)),
        "top_gaps": top_rows,
    }


def _truthy_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(frame[column].fillna(False).astype(bool).sum())


def _decision(
    *,
    failures: list[str],
    synthetic_rows: int,
    synthetic_missing_from_raw: int,
    synthetic_present_in_raw: int,
    synthetic_row_share: float,
    active_session_share: float,
    largest_synthetic_gap_minutes: int | None,
    roll_window_rows: int,
    symbol_change_rows: int,
    instrument_change_rows: int,
    max_synthetic_row_share: float,
    max_active_session_gap_share: float,
    max_gap_minutes_for_accept: int,
) -> tuple[str, list[str]]:
    if failures:
        return "blocked_missing_or_mismatched_provenance", ["required OHLCV-only evidence is missing or mismatched"]
    if synthetic_rows == 0:
        return "usable_no_synthetic_gaps_detected", ["no Phase 2 synthetic rows detected"]

    reasons = [
        "L1/trades unavailable: OHLCV-only audit cannot prove no trades occurred inside missing minutes"
    ]
    if synthetic_present_in_raw:
        reasons.append("some synthetic timestamps are present in raw OHLCV parquet")
    if synthetic_missing_from_raw:
        reasons.append("synthetic timestamps are absent from raw OHLCV parquet")
    if synthetic_row_share > max_synthetic_row_share:
        reasons.append(
            f"synthetic row share {synthetic_row_share:.6f} exceeds ceiling {max_synthetic_row_share:.6f}"
        )
    if active_session_share > max_active_session_gap_share:
        reasons.append(
            f"active-session synthetic share {active_session_share:.6f} exceeds ceiling {max_active_session_gap_share:.6f}"
        )
    if largest_synthetic_gap_minutes is not None and largest_synthetic_gap_minutes > max_gap_minutes_for_accept:
        reasons.append(
            f"largest synthetic gap {largest_synthetic_gap_minutes}m exceeds ceiling {max_gap_minutes_for_accept}m"
        )
    if roll_window_rows or symbol_change_rows or instrument_change_rows:
        reasons.append("synthetic rows overlap roll/symbol/instrument-change evidence")

    can_accept = (
        synthetic_present_in_raw == 0
        and synthetic_row_share <= max_synthetic_row_share
        and active_session_share <= max_active_session_gap_share
        and (largest_synthetic_gap_minutes is None or largest_synthetic_gap_minutes <= max_gap_minutes_for_accept)
        and roll_window_rows == 0
        and symbol_change_rows == 0
        and instrument_change_rows == 0
    )
    if can_accept:
        return "accept_with_caveat_ohlcv_empty_minutes_assumed", reasons
    return "keep_quarantined_ohlcv_only_evidence_insufficient", reasons


def audit_market_year(
    *,
    market: str,
    year: int,
    raw_root: Path,
    causal_root: Path,
    dbn_root: Path,
    session_config: Path,
    max_synthetic_row_share: float,
    max_active_session_gap_share: float,
    max_gap_minutes_for_accept: int,
) -> dict[str, Any]:
    raw_path = raw_root / market / f"{year}.parquet"
    causal_path = causal_root / market / f"{year}.parquet"
    failures: list[str] = []

    if not raw_path.exists():
        failures.append(f"missing raw parquet: {_relative_path(raw_path)}")
    if not causal_path.exists():
        failures.append(f"missing causal parquet: {_relative_path(causal_path)}")
    if not session_config.exists():
        failures.append(f"missing session config: {_relative_path(session_config)}")

    ohlcv_dbn, ohlcv_failures = _audit_dbn_manifest(dbn_root, "ohlcv-1m", market, year)
    definition_dbn, definition_failures = _audit_dbn_manifest(dbn_root, "definition", market, year)
    failures.extend(ohlcv_failures)
    failures.extend(definition_failures)

    raw: pd.DataFrame | None = None
    causal: pd.DataFrame | None = None
    raw_ts = pd.Series(dtype="datetime64[ns, UTC]")
    causal_ts = pd.Series(dtype="datetime64[ns, UTC]")

    if raw_path.exists():
        try:
            raw = pd.read_parquet(raw_path)
            raw_ts = _timestamp_column(raw)
        except Exception as exc:
            failures.append(f"unreadable raw parquet: {exc}")
    if causal_path.exists():
        try:
            causal = pd.read_parquet(causal_path)
            causal_ts = _timestamp_column(causal)
        except Exception as exc:
            failures.append(f"unreadable causal parquet: {exc}")

    raw_source_hashes = _source_values(raw, "source_sha256") if raw is not None else []
    raw_source_files = _source_values(raw, "source_file") if raw is not None else []
    manifest_hash = str(ohlcv_dbn.get("manifest_sha256") or "")
    if raw is not None:
        if not raw_source_hashes:
            failures.append(f"raw parquet missing source_sha256 evidence: {_relative_path(raw_path)}")
        elif manifest_hash and manifest_hash not in raw_source_hashes:
            failures.append("raw parquet source_sha256 does not match OHLCV DBN manifest hash")
        for column in ("instrument_id", "raw_symbol", "tick_size"):
            if column not in raw.columns:
                failures.append(f"raw parquet missing definition-derived column: {column}")

    synthetic = pd.DataFrame()
    synthetic_ts = pd.Series(dtype="datetime64[ns, UTC]")
    if causal is not None:
        if "is_synthetic" not in causal.columns:
            failures.append(f"causal parquet missing is_synthetic: {_relative_path(causal_path)}")
        else:
            synthetic_mask = causal["is_synthetic"].fillna(False).astype(bool)
            synthetic = causal.loc[synthetic_mask].copy()
            synthetic_ts = causal_ts.loc[synthetic_mask]

    raw_timestamp_set = set(raw_ts.dropna().astype("int64").tolist())
    synthetic_timestamp_values = synthetic_ts.dropna().astype("int64")
    present_mask = synthetic_timestamp_values.isin(raw_timestamp_set)
    synthetic_present = int(present_mask.sum())
    synthetic_missing = int(len(synthetic_timestamp_values) - synthetic_present)

    metadata = (
        _bucket_synthetic_timestamps(synthetic_ts, market, session_config)
        if session_config.exists() and not synthetic_ts.empty
        else pd.DataFrame()
    )
    session_bucket_counts = _top_counts(metadata.get("session_bucket", pd.Series(dtype="string")), "bucket")
    low_liquidity_rows = sum(
        int(row["rows"]) for row in session_bucket_counts if row["bucket"] in LOW_LIQUIDITY_BUCKETS
    )
    active_session_rows = max(int(len(synthetic_ts)) - low_liquidity_rows, 0)
    active_session_share = float(active_session_rows / len(synthetic_ts)) if len(synthetic_ts) else 0.0
    synthetic_row_share = float(len(synthetic) / len(causal)) if causal is not None and len(causal) else 0.0
    gap_buckets = _gap_size_counts(synthetic)
    largest_synthetic_gap_minutes = max((int(row["gap_size_minutes"]) for row in gap_buckets), default=None)
    roll_window_rows = _truthy_count(synthetic, "roll_window_flag")
    symbol_change_rows = _truthy_count(synthetic, "symbol_change_flag")
    instrument_change_rows = _truthy_count(synthetic, "instrument_id_change_flag")

    decision, decision_reasons = _decision(
        failures=failures,
        synthetic_rows=int(len(synthetic)),
        synthetic_missing_from_raw=synthetic_missing,
        synthetic_present_in_raw=synthetic_present,
        synthetic_row_share=synthetic_row_share,
        active_session_share=active_session_share,
        largest_synthetic_gap_minutes=largest_synthetic_gap_minutes,
        roll_window_rows=roll_window_rows,
        symbol_change_rows=symbol_change_rows,
        instrument_change_rows=instrument_change_rows,
        max_synthetic_row_share=max_synthetic_row_share,
        max_active_session_gap_share=max_active_session_gap_share,
        max_gap_minutes_for_accept=max_gap_minutes_for_accept,
    )

    raw_rows = int(len(raw)) if raw is not None else None
    causal_rows = int(len(causal)) if causal is not None else None
    return {
        "market": market,
        "year": int(year),
        "status": "FAIL" if failures else "PASS",
        "decision": decision,
        "decision_reasons": decision_reasons,
        "failures": failures,
        "paths": {
            "raw_parquet": _relative_path(raw_path),
            "causal_parquet": _relative_path(causal_path),
        },
        "provenance": {
            "raw_parquet_rows": raw_rows,
            "causal_parquet_rows": causal_rows,
            "raw_ts_min": raw_ts.min().isoformat() if len(raw_ts.dropna()) else None,
            "raw_ts_max": raw_ts.max().isoformat() if len(raw_ts.dropna()) else None,
            "raw_duplicate_timestamp_rows": int(raw_ts.duplicated().sum()) if len(raw_ts) else None,
            "raw_null_timestamp_rows": int(raw_ts.isna().sum()) if len(raw_ts) else None,
            "raw_source_files": raw_source_files,
            "raw_source_sha256": raw_source_hashes,
            "raw_source_matches_ohlcv_manifest": bool(manifest_hash and manifest_hash in raw_source_hashes),
            "ohlcv_dbn": ohlcv_dbn,
            "definition_dbn": definition_dbn,
            "definition_metadata": {
                "instrument_id_nonnull_rows": _non_null_count(raw, "instrument_id") if raw is not None else 0,
                "instrument_id_nunique": int(raw["instrument_id"].nunique()) if raw is not None and "instrument_id" in raw.columns else 0,
                "raw_symbol_nonnull_rows": _non_null_count(raw, "raw_symbol") if raw is not None else 0,
                "raw_symbol_nunique": int(raw["raw_symbol"].nunique()) if raw is not None and "raw_symbol" in raw.columns else 0,
                "tick_size_nonnull_rows": _non_null_count(raw, "tick_size") if raw is not None else 0,
            },
        },
        "continuity": {
            "synthetic_rows": int(len(synthetic)),
            "synthetic_row_share_of_causal": synthetic_row_share,
            "synthetic_timestamps_missing_from_raw": synthetic_missing,
            "synthetic_timestamps_present_in_raw": synthetic_present,
            "active_session_synthetic_rows": active_session_rows,
            "active_session_synthetic_share": active_session_share,
            "low_liquidity_or_edge_synthetic_rows": low_liquidity_rows,
            "gap_size_buckets": gap_buckets,
            "ct_hour_buckets": _top_counts(
                metadata.get("ct_hour", pd.Series(dtype="int64")).astype("string"), "ct_hour"
            ),
            "session_buckets": session_bucket_counts,
            "top_session_dates": _top_counts(
                metadata.get("session_date", pd.Series(dtype="string")), "session_date", limit=5
            ),
            "largest_synthetic_gaps": _largest_gaps(synthetic, synthetic_ts, metadata),
            "raw_consecutive_gap_summary": _raw_consecutive_gap_summary(raw_ts),
            "roll_window_synthetic_rows": roll_window_rows,
            "symbol_change_synthetic_rows": symbol_change_rows,
            "instrument_id_change_synthetic_rows": instrument_change_rows,
        },
        "decision_thresholds": {
            "max_synthetic_row_share": max_synthetic_row_share,
            "max_active_session_gap_share": max_active_session_gap_share,
            "max_gap_minutes_for_accept": max_gap_minutes_for_accept,
        },
        "caveat": "OHLCV-only audit cannot prove whether missing OHLCV minutes had underlying trades.",
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    raw_root = Path(args.raw_root)
    causal_root = Path(args.causal_root)
    dbn_root = Path(args.dbn_root)
    session_config = Path(args.session_config)
    entries = [
        audit_market_year(
            market=market,
            year=int(year),
            raw_root=raw_root,
            causal_root=causal_root,
            dbn_root=dbn_root,
            session_config=session_config,
            max_synthetic_row_share=float(args.max_synthetic_row_share),
            max_active_session_gap_share=float(args.max_active_session_gap_share),
            max_gap_minutes_for_accept=int(args.max_gap_minutes_for_accept),
        )
        for market in args.markets
        for year in args.years
    ]
    failures = [
        f"{entry['market']} {entry['year']}: {failure}"
        for entry in entries
        for failure in entry.get("failures", [])
    ]
    summary = [
        {
            "market": entry["market"],
            "year": entry["year"],
            "status": entry["status"],
            "decision": entry["decision"],
            "synthetic_rows": entry["continuity"]["synthetic_rows"],
            "synthetic_timestamps_missing_from_raw": entry["continuity"][
                "synthetic_timestamps_missing_from_raw"
            ],
            "active_session_synthetic_share": entry["continuity"]["active_session_synthetic_share"],
            "raw_source_matches_ohlcv_manifest": entry["provenance"][
                "raw_source_matches_ohlcv_manifest"
            ],
        }
        for entry in entries
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "method": (
            "OHLCV-only provenance and continuity audit using local raw parquet, "
            "causal parquet, DBN sidecar manifests, definition DBNs, and session config"
        ),
        "raw_root": _relative_path(raw_root),
        "causal_root": _relative_path(causal_root),
        "dbn_root": _relative_path(dbn_root),
        "session_config": _relative_path(session_config),
        "summary": summary,
        "entries": entries,
    }


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# OHLCV Provenance Continuity Audit",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Status: `{report['status']}`",
        "",
        "| Market | Year | Status | Decision | Synthetic rows | Missing from raw | Active share | Provenance match |",
        "|---|---:|---|---|---:|---:|---:|---|",
    ]
    for row in report["summary"]:
        lines.append(
            "| `{market}` | {year} | `{status}` | `{decision}` | {synthetic_rows} | "
            "{missing} | {active_share:.6f} | `{provenance}` |".format(
                market=row["market"],
                year=row["year"],
                status=row["status"],
                decision=row["decision"],
                synthetic_rows=row["synthetic_rows"],
                missing=row["synthetic_timestamps_missing_from_raw"],
                active_share=float(row["active_session_synthetic_share"]),
                provenance=row["raw_source_matches_ohlcv_manifest"],
            )
        )
    lines.extend(
        [
            "",
            "Caveat: OHLCV-only audit cannot prove whether missing OHLCV minutes had underlying trades.",
        ]
    )
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markets", nargs="+", required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--causal-root", default=None)
    parser.add_argument("--dbn-root", default="data/dbn")
    parser.add_argument("--session-config", default="configs/market_sessions.yaml")
    parser.add_argument(
        "--json-out",
        default="reports/pipeline_audit/ohlcv_provenance_continuity_audit.json",
    )
    parser.add_argument(
        "--md-out",
        default="reports/pipeline_audit/ohlcv_provenance_continuity_audit.md",
    )
    parser.add_argument("--max-synthetic-row-share", type=float, default=0.01)
    parser.add_argument("--max-active-session-gap-share", type=float, default=0.05)
    parser.add_argument("--max-gap-minutes-for-accept", type=int, default=5)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.causal_root is None:
        parser.error("--causal-root is required; pass an explicit causal root")
    report = build_report(args)
    write_json_report(report, Path(args.json_out))
    write_markdown_report(report, Path(args.md_out))
    if report["status"] != "PASS":
        print(f"FAIL OHLCV provenance continuity audit: failures={len(report['failures'])}")
        return 1
    decisions = sorted({entry["decision"] for entry in report["entries"]})
    print(
        "PASS OHLCV provenance continuity audit: "
        f"entries={len(report['entries'])} decisions={','.join(decisions)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
