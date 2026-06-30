#!/usr/bin/env python3
"""Report-only DBN-vs-raw gap diagnosis for a single market-year."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.phase1A_download.download_databento_raw import (
    drop_exact_duplicate_ohlcv_rows,
    file_sha256,
    iter_dbn_files,
    store_to_required_dataframe,
)
from scripts.validation.drilldown_phase2_readiness_blockers import (
    _phase2_session_gap_summary,
    _raw_gap_summary,
    _timestamp_series,
)


FrameLoader = Callable[[list[Path]], pd.DataFrame]


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_ohlcv_dbn_frame(paths: list[Path]) -> pd.DataFrame:
    import databento as db

    frames: list[pd.DataFrame] = []
    for path in paths:
        store = db.DBNStore.from_file(path)
        frames.append(store_to_required_dataframe(store))
    if not frames:
        raise ValueError("no OHLCV DBN frames loaded")
    frame = pd.concat(frames, ignore_index=True).sort_values("ts_event", kind="mergesort")
    return drop_exact_duplicate_ohlcv_rows(frame)


def _timestamp_values(ts: pd.Series) -> set[int]:
    valid = pd.to_datetime(ts, utc=True, errors="coerce").dropna()
    if valid.empty:
        return set()
    return set(valid.astype("int64").tolist())


def _top_missing_examples(values: set[int], *, limit: int = 10) -> list[str]:
    return [
        pd.Timestamp(value, tz="UTC").isoformat()
        for value in sorted(values)[: max(0, int(limit))]
    ]


def _read_readiness_context(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    blockers = payload.get("blockers") or []
    first = blockers[0] if blockers else {}
    return {
        "path": _relative_path(path),
        "status": payload.get("status"),
        "blocker_count": payload.get("blocker_count"),
        "first_blocker": {
            "market": first.get("market"),
            "year": first.get("year"),
            "synthetic_rows_pct": first.get("synthetic_rows_pct"),
            "max_synthetic_gap_minutes": first.get("max_synthetic_gap_minutes"),
            "synthetic_rows": first.get("synthetic_rows"),
            "status_enrichment_missing_rows": first.get("status_enrichment_missing_rows"),
            "statistics_enrichment_missing_rows": first.get("statistics_enrichment_missing_rows"),
            "top_blocker_reason": first.get("top_blocker_reason"),
        },
    }


def _source_vs_raw_call(
    *,
    dbn_missing_from_raw_count: int,
    raw_missing_from_dbn_count: int,
    raw_session_candidate_gap_count: int,
) -> str:
    if dbn_missing_from_raw_count:
        return "conversion_or_raw_write_dropped_dbn_timestamps_possible"
    if raw_missing_from_dbn_count:
        return "raw_contains_timestamps_not_present_in_ohlcv_dbn"
    if raw_session_candidate_gap_count:
        return "raw_timestamp_set_matches_ohlcv_dbn_source_gaps"
    return "raw_timestamp_set_matches_ohlcv_dbn_no_session_gap_signal"


def build_report(
    *,
    market: str,
    year: int,
    raw_root: Path,
    dbn_root: Path,
    readiness_json: Path,
    session_config: Path,
    load_dbn_frame: FrameLoader = _load_ohlcv_dbn_frame,
) -> dict[str, Any]:
    raw_path = raw_root / market / f"{year}.parquet"
    dbn_dir = dbn_root / market / str(year)
    failures: list[str] = []

    if not raw_path.exists():
        failures.append(f"missing raw parquet: {_relative_path(raw_path)}")
    if not dbn_dir.exists():
        failures.append(f"missing OHLCV DBN directory: {_relative_path(dbn_dir)}")
    if not readiness_json.exists():
        failures.append(f"missing readiness JSON: {_relative_path(readiness_json)}")
    if failures:
        return {
            "stage": "market_year_source_vs_raw_gap_diagnosis",
            "status": "FAIL",
            "policy": "REPORT_ONLY_NO_PROVIDER_NO_DATA_MUTATION",
            "market": market,
            "year": year,
            "failures": failures,
        }

    dbn_paths = iter_dbn_files(dbn_dir)
    if not dbn_paths:
        failures.append(f"no OHLCV DBN files found: {_relative_path(dbn_dir)}")
        return {
            "stage": "market_year_source_vs_raw_gap_diagnosis",
            "status": "FAIL",
            "policy": "REPORT_ONLY_NO_PROVIDER_NO_DATA_MUTATION",
            "market": market,
            "year": year,
            "failures": failures,
        }

    raw_frame = pd.read_parquet(raw_path)
    dbn_frame = load_dbn_frame(dbn_paths)
    raw_ts, raw_timestamp_source = _timestamp_series(raw_frame)
    dbn_ts, dbn_timestamp_source = _timestamp_series(dbn_frame)
    raw_values = _timestamp_values(raw_ts)
    dbn_values = _timestamp_values(dbn_ts)
    dbn_missing_from_raw = dbn_values - raw_values
    raw_missing_from_dbn = raw_values - dbn_values
    readiness_context = _read_readiness_context(readiness_json)

    raw_session_gap = _phase2_session_gap_summary(
        raw_frame,
        raw_ts,
        market=market,
        session_config_path=session_config,
        max_synthetic_gap_minutes=120,
        top_n=25,
    )
    dbn_session_gap = _phase2_session_gap_summary(
        dbn_frame,
        dbn_ts,
        market=market,
        session_config_path=session_config,
        max_synthetic_gap_minutes=120,
        top_n=25,
    )
    raw_session_candidate_gap_count = int(raw_session_gap.get("candidate_gap_count") or 0)

    return {
        "stage": "market_year_source_vs_raw_gap_diagnosis",
        "status": "PASS",
        "policy": "REPORT_ONLY_NO_PROVIDER_NO_DATA_MUTATION",
        "generated_at_utc": _iso_now(),
        "market": market,
        "year": year,
        "source_vs_raw_call": _source_vs_raw_call(
            dbn_missing_from_raw_count=len(dbn_missing_from_raw),
            raw_missing_from_dbn_count=len(raw_missing_from_dbn),
            raw_session_candidate_gap_count=raw_session_candidate_gap_count,
        ),
        "paths": {
            "raw": _relative_path(raw_path),
            "dbn_dir": _relative_path(dbn_dir),
            "readiness_json": _relative_path(readiness_json),
            "session_config": _relative_path(session_config),
        },
        "dbn_files": [
            {
                "path": _relative_path(path),
                "sha256": file_sha256(path),
            }
            for path in dbn_paths
        ],
        "raw_row_count": int(len(raw_frame)),
        "raw_unique_timestamp_count": len(raw_values),
        "raw_timestamp_source": raw_timestamp_source,
        "dbn_row_count": int(len(dbn_frame)),
        "dbn_unique_timestamp_count": len(dbn_values),
        "dbn_timestamp_source": dbn_timestamp_source,
        "dbn_timestamps_missing_from_raw_count": len(dbn_missing_from_raw),
        "raw_timestamps_missing_from_dbn_count": len(raw_missing_from_dbn),
        "dbn_timestamps_missing_from_raw_examples": _top_missing_examples(dbn_missing_from_raw),
        "raw_timestamps_missing_from_dbn_examples": _top_missing_examples(raw_missing_from_dbn),
        "timestamp_sets_match": raw_values == dbn_values,
        "raw_gap_summary": _raw_gap_summary(raw_ts, limit=25),
        "dbn_gap_summary": _raw_gap_summary(dbn_ts, limit=25),
        "raw_phase2_session_gap_summary": raw_session_gap,
        "dbn_phase2_session_gap_summary": dbn_session_gap,
        "readiness_context": readiness_context,
        "interpretation": {
            "conversion_bug_evidence": len(dbn_missing_from_raw) > 0,
            "source_gap_evidence": raw_values == dbn_values and raw_session_candidate_gap_count > 0,
            "status_statistics_redownload_expected_to_help": False,
        },
        "forbidden_actions_performed": {
            "provider_or_network_call": False,
            "data_mutation": False,
            "config_mutation": False,
            "broad_build": False,
        },
        "failures": [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Market-Year Source vs Raw Gap Diagnosis",
        "",
        f"- Status: `{report['status']}`.",
        f"- Market/year: `{report['market']}:{report['year']}`.",
        f"- Source-vs-raw call: `{report.get('source_vs_raw_call')}`.",
        f"- Raw rows: `{report.get('raw_row_count')}`.",
        f"- DBN rows: `{report.get('dbn_row_count')}`.",
        f"- Timestamp sets match: `{str(report.get('timestamp_sets_match')).lower()}`.",
        f"- DBN timestamps missing from raw: `{report.get('dbn_timestamps_missing_from_raw_count')}`.",
        f"- Raw timestamps missing from DBN: `{report.get('raw_timestamps_missing_from_dbn_count')}`.",
        f"- Raw session candidate gaps: `{report.get('raw_phase2_session_gap_summary', {}).get('candidate_gap_count')}`.",
        f"- Raw synthetic missing estimate: `{report.get('raw_phase2_session_gap_summary', {}).get('synthetic_missing_rows_estimate')}`.",
        "",
        "## Safety",
        "",
        "- Provider/network call: `false`.",
        "- Data mutation: `false`.",
        "- Config mutation: `false`.",
        "- Broad build: `false`.",
        "",
    ]
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", default="6A")
    parser.add_argument("--year", type=int, default=2010)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--dbn-root", default="data/dbn/ohlcv_1m")
    parser.add_argument(
        "--readiness-json",
        default=(
            "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/"
            "broad_manifest_527_rebuild_phase2_readiness_after_6A_2010_repair.json"
        ),
    )
    parser.add_argument("--session-config", default="configs/market_sessions.yaml")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_report(
        market=args.market,
        year=args.year,
        raw_root=Path(args.raw_root),
        dbn_root=Path(args.dbn_root),
        readiness_json=Path(args.readiness_json),
        session_config=Path(args.session_config),
    )

    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_out:
        md_out = Path(args.md_out)
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("stage", "status", "source_vs_raw_call")}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
