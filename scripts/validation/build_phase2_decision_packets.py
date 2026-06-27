#!/usr/bin/env python3
"""Build fail-closed Phase 2 decision packets from readiness evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.validation.audit_phase2_readiness import load_checkpoint_rows
from scripts.validation.summarize_phase2_readiness_blockers import classify_blocker

DEFAULT_CHECKPOINT = Path(
    "reports/phase2_readiness/tier3_research_after_status_sparse_exceptions_20260624.jsonl"
)

DECISION_STATUS = "BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-jsonl", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--reports-root", default="reports/phase2_readiness")
    parser.add_argument("--markets", nargs="+", required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--date-tag", required=True)
    return parser


def _as_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _values(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    return sorted(str(value) for value in df[column].dropna().astype(str).unique())


def raw_evidence(raw_root: Path, market: str, year: int) -> dict[str, Any]:
    path = raw_root / market / f"{year}.parquet"
    evidence: dict[str, Any] = {
        "path": path.as_posix(),
        "exists": path.exists(),
    }
    if not path.exists():
        return evidence
    df = pd.read_parquet(path)
    evidence.update(
        {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
            "row_count": int(len(df)),
            "market_values": _values(df, "market"),
            "year_values": _values(df, "year"),
            "source_files": _values(df, "source_file"),
            "status_source_files": _values(df, "status_source_file"),
            "statistics_source_files": sorted(
                {
                    value
                    for column in df.columns
                    if column.startswith("stat_") and column.endswith("_source_file")
                    for value in _values(df, column)
                }
            ),
            "status_missing_rows": _bool_sum(df, "status_missing"),
            "status_stale_rows": _bool_sum(df, "status_stale"),
            "statistics_missing_rows": _bool_sum(df, "statistics_missing"),
            "statistics_stale_rows": _bool_sum(df, "statistics_stale"),
            "degraded_bar_rows": _bool_sum(df, "data_quality_degraded"),
        }
    )
    return evidence


def _bool_sum(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    return int(df[column].fillna(False).astype(bool).sum())


def _matching_rows(
    checkpoint_rows: list[dict[str, Any]],
    *,
    markets: list[str],
    years: list[int],
) -> list[dict[str, Any]]:
    selected = []
    wanted = {(market, year) for market in markets for year in years}
    seen: set[tuple[str, int]] = set()
    for row in checkpoint_rows:
        key = (str(row.get("market")), _as_int(row.get("year")))
        if key not in wanted:
            continue
        seen.add(key)
        selected.append(row)
    missing = sorted(wanted - seen)
    if missing:
        label = ", ".join(f"{market} {year}" for market, year in missing)
        raise ValueError(f"missing checkpoint rows: {label}")
    return sorted(selected, key=lambda row: (str(row.get("market")), _as_int(row.get("year"))))


def build_packet(
    row: dict[str, Any],
    *,
    raw: dict[str, Any],
    generated_at_utc: str,
    checkpoint_jsonl: Path,
) -> dict[str, Any]:
    market = str(row.get("market"))
    year = _as_int(row.get("year"))
    if row.get("status") == "PASS":
        raise ValueError(f"{market} {year} is PASS; fail-closed packet not allowed")
    blocker_classes, other_reasons = classify_blocker(row)
    warnings = list(row.get("warnings") or [])
    return {
        "packet": f"{market}_{year}_read_only_phase2_decision_packet",
        "generated_at_utc": generated_at_utc,
        "status": "ACTION_REQUIRED",
        "market": market,
        "year": year,
        "source_reports": {
            "handoff": "CODEX_HANDOFF.md",
            "checkpoint_jsonl": checkpoint_jsonl.as_posix(),
        },
        "phase2_readiness_evidence": {
            "checkpoint_status": row.get("status"),
            "decision_status": DECISION_STATUS,
            "blocker_classes": sorted(blocker_classes),
            "other_reasons": other_reasons,
            "warnings": warnings,
            "failures": list(row.get("failures") or []),
            "output_rows": _as_int(row.get("output_rows")),
            "synthetic_rows": _as_int(row.get("synthetic_rows")),
            "synthetic_rows_pct": _as_float(row.get("synthetic_rows_pct")),
            "max_synthetic_gap_minutes": _as_int(row.get("max_synthetic_gap_minutes")),
            "degraded_bar_rows": _as_int(row.get("degraded_bar_rows")),
            "degraded_session_rows": _as_int(row.get("degraded_session_rows")),
            "roll_maturity_backstep_count": _as_int(
                row.get("roll_maturity_backstep_count")
            ),
            "roll_window_rows": _as_int(row.get("roll_window_rows")),
            "roll_window_rows_pct": _as_float(row.get("roll_window_rows_pct")),
            "status_enrichment_missing_rows": _as_int(
                row.get("status_enrichment_missing_rows")
            ),
            "status_enrichment_stale_rows": _as_int(
                row.get("status_enrichment_stale_rows")
            ),
            "statistics_enrichment_missing_rows": _as_int(
                row.get("statistics_enrichment_missing_rows")
            ),
            "statistics_enrichment_stale_rows": _as_int(
                row.get("statistics_enrichment_stale_rows")
            ),
            "top_blocker_reason": row.get("top_blocker_reason"),
        },
        "canonical_raw_evidence": raw,
        "policy_decision": {
            "decision": "keep_fail_closed",
            "reason": (
                "ACTION_REQUIRED packet with current Phase 2 readiness WARN evidence; "
                "no diagnostic use, threshold loosening, accepted-readiness exception, "
                "source mutation, provider command, source repair, canonical raw overwrite, "
                "or canonical Phase 2 rebuild is approved."
            ),
            "finalized_canonical_dataset_status": "excluded",
            "diagnostic_use_approved": False,
            "accepted_readiness_exception_added": False,
            "thresholds_loosened": False,
            "provider_command_approved": False,
            "source_repair_approved": False,
            "canonical_raw_overwrite_approved": False,
            "canonical_phase2_rebuild_approved": False,
        },
        "decision_gate_result": {
            "status": "ACTION_REQUIRED",
            "action": "record_fail_closed_and_move_next",
        },
    }


def write_markdown(path: Path, packet: dict[str, Any]) -> None:
    ev = packet["phase2_readiness_evidence"]
    raw = packet["canonical_raw_evidence"]
    policy = packet["policy_decision"]
    lines = [
        f"# {packet['market']} {packet['year']} Read-Only Phase 2 Decision Packet",
        "",
        f"Status: {packet['status']}",
        "",
        (
            f"Decision: keep {packet['market']} {packet['year']} fail-closed and excluded "
            "from finalized canonical datasets pending source repair, paid source "
            "acquisition, or a separately approved diagnostic-only branch."
        ),
        "",
        "## Evidence",
        "",
        f"- Phase 2 readiness checkpoint_status={ev['checkpoint_status']} and decision_status={ev['decision_status']}.",
        *[f"- Warning: {warning}." for warning in ev["warnings"]],
        (
            f"- Synthetic rows: {ev['synthetic_rows']}, "
            f"synthetic_rows_pct={ev['synthetic_rows_pct']}, "
            f"max_synthetic_gap_minutes={ev['max_synthetic_gap_minutes']}."
        ),
        (
            f"- Degraded evidence: degraded_bar_rows={ev['degraded_bar_rows']}, "
            f"degraded_session_rows={ev['degraded_session_rows']}."
        ),
        f"- Roll evidence: roll_maturity_backstep_count={ev['roll_maturity_backstep_count']}.",
        (
            "- Enrichment gaps: "
            f"status_enrichment_missing_rows={ev['status_enrichment_missing_rows']}, "
            f"status_enrichment_stale_rows={ev['status_enrichment_stale_rows']}, "
            f"statistics_enrichment_missing_rows={ev['statistics_enrichment_missing_rows']}, "
            f"statistics_enrichment_stale_rows={ev['statistics_enrichment_stale_rows']}."
        ),
        (
            f"- Canonical raw file {raw.get('path')} exists={raw.get('exists')} "
            f"row_count={raw.get('row_count')} sha256={raw.get('sha256')}."
        ),
        f"- Canonical raw source files: {', '.join(raw.get('source_files') or [])}.",
        "",
        "## Policy Result",
        "",
        (
            "No diagnostic use, threshold loosening, accepted-readiness exception, "
            "source mutation, provider command, source repair, canonical raw overwrite, "
            "or canonical Phase 2 rebuild is approved."
        ),
        f"Under the default decision policy, {packet['market']} {packet['year']} remains fail-closed.",
        "",
        "## Policy Flags",
        "",
        f"- diagnostic_use_approved={policy['diagnostic_use_approved']}",
        f"- accepted_readiness_exception_added={policy['accepted_readiness_exception_added']}",
        f"- thresholds_loosened={policy['thresholds_loosened']}",
        f"- provider_command_approved={policy['provider_command_approved']}",
        f"- source_repair_approved={policy['source_repair_approved']}",
        f"- canonical_raw_overwrite_approved={policy['canonical_raw_overwrite_approved']}",
        f"- canonical_phase2_rebuild_approved={policy['canonical_phase2_rebuild_approved']}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_packet(output_dir: Path, packet: dict[str, Any], *, date_tag: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    stem = f"{packet['market']}_{packet['year']}_decision_packet_{date_tag}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, packet)


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    checkpoint_jsonl = Path(args.checkpoint_jsonl)
    rows = _matching_rows(
        load_checkpoint_rows(checkpoint_jsonl),
        markets=[str(market) for market in args.markets],
        years=[int(year) for year in args.years],
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    written: list[str] = []
    for row in rows:
        market = str(row.get("market"))
        year = _as_int(row.get("year"))
        packet = build_packet(
            row,
            raw=raw_evidence(Path(args.raw_root), market, year),
            generated_at_utc=generated_at,
            checkpoint_jsonl=checkpoint_jsonl,
        )
        out_dir = Path(args.reports_root) / f"{market}_{year}_scope_{args.date_tag}"
        write_packet(out_dir, packet, date_tag=args.date_tag)
        written.append(out_dir.as_posix())
    print(json.dumps({"status": "PASS", "written_dirs": written}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
