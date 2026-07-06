#!/usr/bin/env python3
"""Report-only ES/NQ 2026 degraded-session drilldown."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.phase2_causal_base.build_causal_base_data import (
    DEFAULT_SESSION_CONFIG,
    _session_metadata,
    load_session_calendar,
)

DEFAULT_YEAR = 2026
DEFAULT_RAW_ROOT = Path("data/raw")
DEFAULT_CAUSAL_ROOT = Path("data/causally_gated_normalized")
DEFAULT_ES_READINESS = Path(
    "reports/data_audit/current_state/"
    "holdout_forward_8_phase2_staged_20260706/forward_2026/"
    "phase2_readiness_summary.json"
)
DEFAULT_PHASE_CHAIN_DIAGNOSTIC = Path(
    "reports/data_audit/current_state/es_nq_2026_phase_chain_diagnostic_20260706.json"
)
DEFAULT_REPORT_ROOT = Path(
    "reports/data_audit/current_state/es_nq_2026_degraded_session_drilldown_20260706"
)
TIMESTAMP_COLUMNS = ("ts_event", "ts", "datetime_utc", "datetime", "timestamp", "time")


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root is not an object: {_relative_path(path)}")
    return payload


def _timestamp_series(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    for column in TIMESTAMP_COLUMNS:
        if column in frame.columns:
            return pd.to_datetime(frame[column], utc=True, errors="coerce"), column
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index), "datetime_index"
    return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]"), "missing"


def _bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    return (
        series.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
    )


def _degraded_mask(frame: pd.DataFrame) -> pd.Series:
    mask = _bool_series(frame, "data_quality_degraded")
    if "session_data_quality_degraded" in frame.columns:
        mask = mask | _bool_series(frame, "session_data_quality_degraded")
    if "data_quality_status" in frame.columns:
        status = frame["data_quality_status"].astype("string").str.strip().str.lower()
        mask = mask | (status.notna() & status.ne("") & status.ne("available"))
    return mask.fillna(False).astype(bool)


def _top_counts(values: pd.Series, *, key: str, limit: int = 10) -> list[dict[str, Any]]:
    counts = Counter(str(value) for value in values.dropna())
    return [{key: item, "row_count": count} for item, count in counts.most_common(limit)]


def _market_raw_summary(
    *,
    raw_root: Path,
    market: str,
    year: int,
    session_config: Path,
) -> tuple[dict[str, Any], list[str]]:
    path = raw_root / market / f"{year}.parquet"
    failures: list[str] = []
    if not path.exists():
        return (
            {
                "market": market,
                "year": year,
                "path": _relative_path(path),
                "exists": False,
            },
            [f"missing raw parquet: {_relative_path(path)}"],
        )

    frame = pd.read_parquet(path)
    ts, timestamp_source = _timestamp_series(frame)
    if ts.isna().all():
        failures.append(f"missing timestamp column/index in {_relative_path(path)}")
        metadata = pd.DataFrame(index=frame.index)
    else:
        calendar = load_session_calendar(
            market,
            session_config,
            allow_hardcoded_calendar=False,
        )
        metadata = _session_metadata(ts.reset_index(drop=True), calendar).reset_index(drop=True)

    degraded = _degraded_mask(frame).reset_index(drop=True)
    work = pd.DataFrame({"ts": ts.reset_index(drop=True), "degraded": degraded})
    if not metadata.empty:
        work = pd.concat([work, metadata], axis=1)
    degraded_rows = work[work["degraded"] & work["ts"].notna()].copy()
    degraded_inside = degraded_rows[
        degraded_rows.get("inside_session", pd.Series(False, index=degraded_rows.index))
        .fillna(False)
        .astype(bool)
    ]
    degraded_session_dates = sorted(
        str(value)
        for value in degraded_inside.get("session_date", pd.Series(dtype="string")).dropna().unique()
    )

    session_rows: list[dict[str, Any]] = []
    if not degraded_inside.empty and {"session_id", "session_date"}.issubset(degraded_inside.columns):
        grouped = degraded_inside.groupby(["session_id", "session_date"], dropna=False)
        for (session_id, session_date), group in grouped:
            session_rows.append(
                {
                    "session_id": None if pd.isna(session_id) else str(session_id),
                    "session_date": None if pd.isna(session_date) else str(session_date),
                    "degraded_rows": int(len(group)),
                    "first_ts": pd.Timestamp(group["ts"].min()).isoformat(),
                    "last_ts": pd.Timestamp(group["ts"].max()).isoformat(),
                }
            )
        session_rows.sort(key=lambda row: (-int(row["degraded_rows"]), str(row["session_date"])))

    status_counts: dict[str, int] = {}
    if "data_quality_status" in frame.columns:
        counts = frame["data_quality_status"].fillna("null").astype(str).value_counts()
        status_counts = {str(key): int(value) for key, value in counts.sort_index().items()}

    row_count = int(len(frame))
    degraded_count = int(degraded.sum())
    return (
        {
            "market": market,
            "year": year,
            "path": _relative_path(path),
            "exists": True,
            "row_count": row_count,
            "column_count": int(len(frame.columns)),
            "timestamp_source": timestamp_source,
            "timestamp_null_count": int(ts.isna().sum()),
            "first_ts": pd.Timestamp(ts.dropna().min()).isoformat() if ts.notna().any() else None,
            "last_ts": pd.Timestamp(ts.dropna().max()).isoformat() if ts.notna().any() else None,
            "data_quality_status_counts": status_counts,
            "degraded_rows": degraded_count,
            "degraded_rows_pct": round((degraded_count / row_count) * 100, 6) if row_count else 0.0,
            "degraded_inside_session_rows": int(len(degraded_inside)),
            "degraded_outside_session_rows": int(len(degraded_rows) - len(degraded_inside)),
            "degraded_session_count": len(degraded_session_dates),
            "degraded_session_dates": degraded_session_dates,
            "top_degraded_utc_dates": _top_counts(degraded_rows["ts"].dt.date.astype("string"), key="utc_date"),
            "top_degraded_sessions": session_rows[:10],
        },
        failures,
    )


def _causal_summary(causal_root: Path, market: str, year: int) -> dict[str, Any]:
    path = causal_root / market / f"{year}.parquet"
    if not path.exists():
        return {"path": _relative_path(path), "exists": False}
    frame = pd.read_parquet(path)
    degraded = _degraded_mask(frame)
    synthetic = _bool_series(frame, "is_synthetic")
    session_dates: list[str] = []
    if "session_date" in frame.columns:
        session_dates = sorted(
            str(value)
            for value in frame.loc[degraded, "session_date"].dropna().astype(str).unique()
        )
    return {
        "path": _relative_path(path),
        "exists": True,
        "row_count": int(len(frame)),
        "degraded_rows": int(degraded.sum()),
        "degraded_rows_pct": round((int(degraded.sum()) / len(frame)) * 100, 6) if len(frame) else 0.0,
        "synthetic_rows": int(synthetic.sum()),
        "degraded_session_count": len(session_dates),
        "degraded_session_dates": session_dates,
    }


def _exception_review_call(
    *,
    es_summary: dict[str, Any],
    nq_summary: dict[str, Any],
    overlap_count: int,
) -> str:
    es_dates = set(es_summary.get("degraded_session_dates", []))
    nq_dates = set(nq_summary.get("degraded_session_dates", []))
    pct_diff = abs(
        float(es_summary.get("degraded_rows_pct", 0.0))
        - float(nq_summary.get("degraded_rows_pct", 0.0))
    )
    if not es_dates or not nq_dates:
        return "NOT_ESTABLISHED_MISSING_DEGRADED_SESSION_DATES"
    if es_dates == nq_dates and pct_diff <= 0.05:
        return "SCOPED_EXCEPTION_REVIEW_SUPPORTED_NOT_APPROVED"
    if es_dates.issubset(nq_dates) and pct_diff <= 0.05:
        return "SCOPED_EXCEPTION_REVIEW_PLAUSIBLE_NOT_APPROVED"
    if overlap_count:
        return "PARTIAL_OVERLAP_REQUIRES_POLICY_REVIEW"
    return "EXCEPTION_NOT_SUPPORTED_BY_SESSION_OVERLAP"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    raw_root = Path(args.raw_root)
    causal_root = Path(args.causal_root)
    session_config = Path(args.session_config)
    year = int(args.year)
    failures: list[str] = []

    raw_summaries: dict[str, dict[str, Any]] = {}
    for market in ("ES", "NQ"):
        summary, market_failures = _market_raw_summary(
            raw_root=raw_root,
            market=market,
            year=year,
            session_config=session_config,
        )
        raw_summaries[market] = summary
        failures.extend(market_failures)

    es_dates = set(raw_summaries["ES"].get("degraded_session_dates", []))
    nq_dates = set(raw_summaries["NQ"].get("degraded_session_dates", []))
    overlap = sorted(es_dates & nq_dates)
    es_only = sorted(es_dates - nq_dates)
    nq_only = sorted(nq_dates - es_dates)
    if es_dates and nq_dates:
        union_count = len(es_dates | nq_dates)
        jaccard = round(len(overlap) / union_count, 6) if union_count else 0.0
    else:
        jaccard = 0.0

    es_readiness = _read_json(Path(args.es_readiness_summary))
    phase_chain = _read_json(Path(args.phase_chain_diagnostic))
    nq_causal = _causal_summary(causal_root, "NQ", year)

    exception_call = _exception_review_call(
        es_summary=raw_summaries["ES"],
        nq_summary=raw_summaries["NQ"],
        overlap_count=len(overlap),
    )

    return {
        "schema_version": 1,
        "stage": "es_nq_2026_degraded_session_drilldown",
        "status": "FAIL" if failures else "PASS_DIAGNOSTIC_NO_MUTATION",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "policy": "REPORT_ONLY_NO_DATA_MUTATION",
        "scope": {
            "markets": ["ES", "NQ"],
            "year": year,
            "raw_root": _relative_path(raw_root),
            "causal_root": _relative_path(causal_root),
            "session_config": _relative_path(session_config),
            "es_readiness_summary": _relative_path(Path(args.es_readiness_summary)),
            "phase_chain_diagnostic": _relative_path(Path(args.phase_chain_diagnostic)),
        },
        "forbidden_actions": [
            "provider_calls",
            "dbn_writes",
            "raw_writes",
            "causal_writes",
            "label_writes",
            "feature_writes",
            "staged_or_active_replacement",
            "rebuilds",
            "cleanup",
            "commits",
            "pushes",
            "paper_or_live_claims",
        ],
        "raw_degraded_session_summaries": raw_summaries,
        "nq_existing_causal_summary": nq_causal,
        "es_readiness_evidence": {
            "path": _relative_path(Path(args.es_readiness_summary)),
            "present": es_readiness is not None,
            "status": es_readiness.get("status") if es_readiness else None,
            "failure_count": es_readiness.get("failure_count") if es_readiness else None,
            "blocker_count": es_readiness.get("blocker_count") if es_readiness else None,
            "failures": es_readiness.get("failures", []) if es_readiness else [],
            "blockers": es_readiness.get("blockers", []) if es_readiness else [],
        },
        "phase_chain_evidence": {
            "path": _relative_path(Path(args.phase_chain_diagnostic)),
            "present": phase_chain is not None,
            "status": phase_chain.get("status") if phase_chain else None,
            "conclusion": phase_chain.get("conclusion", {}) if phase_chain else {},
        },
        "comparison": {
            "degraded_session_overlap_count": len(overlap),
            "degraded_session_union_count": len(es_dates | nq_dates),
            "degraded_session_jaccard": jaccard,
            "overlapping_session_dates": overlap,
            "es_only_degraded_session_dates": es_only,
            "nq_only_degraded_session_dates": nq_only,
            "raw_degraded_pct_abs_diff": round(
                abs(
                    float(raw_summaries["ES"].get("degraded_rows_pct", 0.0))
                    - float(raw_summaries["NQ"].get("degraded_rows_pct", 0.0))
                ),
                6,
            ),
            "cluster_call": (
                "MATCHED_DEGRADED_SESSION_DATES"
                if es_dates and es_dates == nq_dates
                else "PARTIAL_DEGRADED_SESSION_DATE_OVERLAP"
                if overlap
                else "NO_DEGRADED_SESSION_DATE_OVERLAP"
            ),
            "exception_review_call": exception_call,
        },
        "authorization": {
            "scoped_exception_approved": False,
            "phase2_2026_rebuild_approved": False,
            "active_replacement_approved": False,
            "labels_features_wfa_predictions_approved": False,
            "paper_or_live_supported": False,
        },
        "next_recommended_action": (
            "Review the ES/NQ degraded-session overlap and decide whether to create a "
            "separate scoped tier_3_forward readiness-exception approval packet; do not "
            "rerun Phase 2, rebuild labels/features, or replace active roots from this "
            "diagnostic alone."
        ),
        "failures": failures,
    }


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    es = report["raw_degraded_session_summaries"]["ES"]
    nq = report["raw_degraded_session_summaries"]["NQ"]
    comparison = report["comparison"]
    lines = [
        "# ES/NQ 2026 Degraded-Session Drilldown",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Status: `{report['status']}`",
        f"Policy: `{report['policy']}`",
        "",
        "## Raw Degraded Sessions",
        "",
        "| Market | Rows | Degraded Rows | Degraded % | Degraded Sessions | Outside-Session Degraded Rows |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in (es, nq):
        lines.append(
            "| `{market}` | {rows} | {degraded} | {pct:.6f} | {sessions} | {outside} |".format(
                market=row["market"],
                rows=row.get("row_count", "NA"),
                degraded=row.get("degraded_rows", "NA"),
                pct=float(row.get("degraded_rows_pct", 0.0)),
                sessions=row.get("degraded_session_count", "NA"),
                outside=row.get("degraded_outside_session_rows", "NA"),
            )
        )
    lines.extend(
        [
            "",
            "## Comparison",
            "",
            f"- Cluster call: `{comparison['cluster_call']}`",
            f"- Exception review call: `{comparison['exception_review_call']}`",
            f"- Overlap sessions: {comparison['degraded_session_overlap_count']}/{comparison['degraded_session_union_count']}",
            f"- Raw degraded pct abs diff: {comparison['raw_degraded_pct_abs_diff']}",
            f"- Overlapping session dates: {', '.join(comparison['overlapping_session_dates']) or 'None'}",
            f"- ES-only degraded session dates: {', '.join(comparison['es_only_degraded_session_dates']) or 'None'}",
            f"- NQ-only degraded session dates: {', '.join(comparison['nq_only_degraded_session_dates']) or 'None'}",
            "",
            "## Authorization",
            "",
            "- Scoped exception approved: `false`",
            "- Phase 2 2026 rebuild approved: `false`",
            "- Active replacement approved: `false`",
            "- Labels/features/WFA/predictions approved: `false`",
            "- Paper/live supported: `false`",
            "",
            "## Next Recommended Action",
            "",
            report["next_recommended_action"],
        ]
    )
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--causal-root", default=str(DEFAULT_CAUSAL_ROOT))
    parser.add_argument("--session-config", default=str(DEFAULT_SESSION_CONFIG))
    parser.add_argument("--es-readiness-summary", default=str(DEFAULT_ES_READINESS))
    parser.add_argument("--phase-chain-diagnostic", default=str(DEFAULT_PHASE_CHAIN_DIAGNOSTIC))
    parser.add_argument(
        "--json-out",
        default=str(DEFAULT_REPORT_ROOT / "es_nq_2026_degraded_session_drilldown.json"),
    )
    parser.add_argument(
        "--md-out",
        default=str(DEFAULT_REPORT_ROOT / "es_nq_2026_degraded_session_drilldown.md"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_report(args)
    write_json_report(report, Path(args.json_out))
    write_markdown_report(report, Path(args.md_out))
    print(
        json.dumps(
            {
                "stage": report["stage"],
                "status": report["status"],
                "cluster_call": report["comparison"]["cluster_call"],
                "exception_review_call": report["comparison"]["exception_review_call"],
                "json_out": args.json_out,
                "md_out": args.md_out,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS_DIAGNOSTIC_NO_MUTATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
