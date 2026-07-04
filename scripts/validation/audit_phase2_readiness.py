#!/usr/bin/env python3
"""Read-only fail-closed readiness audit for Phase 2 causal base inputs."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from scripts.phase2_causal_base.build_causal_base_data import (
    DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    DEFAULT_PROFILE,
    DEFAULT_PROFILE_CONFIG,
    DEFAULT_RAW_ALIGNMENT_REPORT,
    DEFAULT_ROLL_WINDOW_BARS,
    DEFAULT_SESSION_CONFIG,
    build_phase2_readiness_report,
    filter_inputs_by_raw_alignment,
    load_profile_map,
    raw_alignment_expected_market_years,
    raw_alignment_guard_failures,
    resolve_profile_inputs,
    resolve_profile_name,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--raw-alignment-report", default=str(DEFAULT_RAW_ALIGNMENT_REPORT))
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--session-config", default=str(DEFAULT_SESSION_CONFIG))
    parser.add_argument("--allow-hardcoded-calendar", action="store_true")
    parser.add_argument("--roll-window-bars", type=int, default=DEFAULT_ROLL_WINDOW_BARS)
    parser.add_argument(
        "--max-synthetic-gap-minutes",
        type=int,
        default=DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    )
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--top-blockers", type=int, default=20)
    parser.add_argument("--json-out")
    parser.add_argument("--checkpoint-jsonl")
    parser.add_argument("--resume-from")
    parser.add_argument("--checkpoint-summary-only", action="store_true")
    parser.add_argument("--max-market-years", type=int)
    parser.add_argument("--stop-after-blockers", type=int)
    parser.add_argument("--markets", nargs="+")
    parser.add_argument("--years", nargs="+", type=int)
    return parser


def _as_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _classified_reason(raw_reason: object) -> str:
    reason = str(raw_reason or "unknown")
    if reason.startswith("synthetic threshold breached"):
        return "synthetic threshold breached"
    if reason.startswith("degraded threshold breached"):
        return "degraded threshold breached"
    return reason


def _blocker_reasons(blocker: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for item in blocker.get("failures", []) or []:
        reasons.append(_classified_reason(item))
    for item in blocker.get("warnings", []) or []:
        reasons.append(_classified_reason(item))
    if not reasons:
        reasons.append(_classified_reason(blocker.get("top_blocker_reason")))
    return sorted(set(reasons))


def _compact_blocker(blocker: dict[str, Any]) -> dict[str, Any]:
    return {
        "market": blocker.get("market"),
        "year": blocker.get("year"),
        "status": blocker.get("status"),
        "reason": "+".join(_blocker_reasons(blocker)),
        "top_blocker_reason": blocker.get("top_blocker_reason"),
        "synthetic_rows_pct": _as_float(blocker.get("synthetic_rows_pct")),
        "max_synthetic_gap_minutes": _as_int(blocker.get("max_synthetic_gap_minutes")),
        "degraded_rows_pct": _as_float(blocker.get("degraded_rows_pct")),
        "status_missing_rows": _as_int(blocker.get("status_enrichment_missing_rows")),
        "status_stale_rows": _as_int(blocker.get("status_enrichment_stale_rows")),
        "statistics_missing_rows": _as_int(blocker.get("statistics_enrichment_missing_rows")),
        "statistics_stale_rows": _as_int(blocker.get("statistics_enrichment_stale_rows")),
    }


def _market_year_key(row: dict[str, Any]) -> tuple[str, int]:
    return str(row["market"]), int(row["year"])


def dedupe_checkpoint_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        by_key[_market_year_key(row)] = row
    return [
        by_key[key]
        for key in sorted(by_key, key=lambda item: (item[0], item[1]))
    ]


CHECKPOINT_METADATA_STAGES = {
    "phase2_readiness_checkpoint_start",
    "phase2_readiness_checkpoint_summary",
}


def load_checkpoint_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"resume checkpoint missing: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"checkpoint row {line_number} is not a JSON object")
        if "market" not in row or "year" not in row:
            if row.get("stage") in CHECKPOINT_METADATA_STAGES:
                continue
            raise ValueError(f"checkpoint row {line_number} missing market/year")
        rows.append(row)
    return dedupe_checkpoint_rows(rows)


def append_checkpoint_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()


def summarize_checkpoint_rows(
    rows: list[dict[str, Any]],
    *,
    base_report: dict[str, Any] | None = None,
    top_blockers: int = 20,
) -> dict[str, Any]:
    report = base_report or {}
    rows = dedupe_checkpoint_rows(rows)
    blockers = [row for row in rows if row.get("status") != "PASS"]
    market_counts = Counter(str(blocker.get("market", "unknown")) for blocker in blockers)
    reason_counts: Counter[str] = Counter()
    reason_combo_counts: Counter[str] = Counter()
    for blocker in blockers:
        reasons = _blocker_reasons(blocker)
        reason_counts.update(reasons)
        reason_combo_counts.update(["+".join(reasons)])

    limit = max(0, int(top_blockers))
    compact_blockers = [_compact_blocker(blocker) for blocker in blockers]
    top_synthetic = sorted(
        compact_blockers,
        key=lambda row: (
            _as_float(row.get("synthetic_rows_pct")),
            _as_int(row.get("max_synthetic_gap_minutes")),
        ),
        reverse=True,
    )[:limit]
    top_degraded = sorted(
        compact_blockers,
        key=lambda row: _as_float(row.get("degraded_rows_pct")),
        reverse=True,
    )[:limit]
    checked_count = len(rows)
    selected_count = _as_int(report.get("selected_market_year_count")) or checked_count
    pending_count = max(0, selected_count - checked_count)
    failure_count = _as_int(report.get("failure_count"))
    failures = list(report.get("failures", []) or [])
    status = "FAIL" if failure_count or blockers or pending_count else "PASS"
    return {
        "stage": "phase2_readiness_summary",
        "source_stage": report.get("stage", "phase2_readiness_checkpoint"),
        "status": status,
        "profile": report.get("profile") or (rows[0].get("profile") if rows else None),
        "resolved_profile": report.get("resolved_profile")
        or (rows[0].get("resolved_profile") if rows else None),
        "market_filter": report.get("market_filter"),
        "year_filter": report.get("year_filter"),
        "selected_market_year_count": selected_count,
        "expected_market_year_count": _as_int(report.get("expected_market_year_count"))
        or selected_count,
        "checked_market_year_count": checked_count,
        "resumed_market_year_count": _as_int(report.get("resumed_market_year_count")),
        "pending_market_year_count": pending_count,
        "pass_count": sum(1 for row in rows if row.get("status") == "PASS"),
        "blocker_count": len(blockers),
        "failure_count": failure_count,
        "failures": failures,
        "reason_counts": dict(sorted(reason_counts.items())),
        "reason_combo_counts": dict(sorted(reason_combo_counts.items())),
        "market_blocker_counts": dict(sorted(market_counts.items())),
        "enrichment_totals": {
            "status_missing_rows": sum(
                _as_int(blocker.get("status_enrichment_missing_rows"))
                for blocker in blockers
            ),
            "status_stale_rows": sum(
                _as_int(blocker.get("status_enrichment_stale_rows"))
                for blocker in blockers
            ),
            "statistics_missing_rows": sum(
                _as_int(blocker.get("statistics_enrichment_missing_rows"))
                for blocker in blockers
            ),
            "statistics_stale_rows": sum(
                _as_int(blocker.get("statistics_enrichment_stale_rows"))
                for blocker in blockers
            ),
        },
        "enrichment_blocker_counts": {
            "status_missing": sum(
                1
                for blocker in blockers
                if _as_int(blocker.get("status_enrichment_missing_rows")) > 0
            ),
            "status_stale": sum(
                1
                for blocker in blockers
                if _as_int(blocker.get("status_enrichment_stale_rows")) > 0
            ),
            "statistics_missing": sum(
                1
                for blocker in blockers
                if _as_int(blocker.get("statistics_enrichment_missing_rows")) > 0
            ),
            "statistics_stale": sum(
                1
                for blocker in blockers
                if _as_int(blocker.get("statistics_enrichment_stale_rows")) > 0
            ),
        },
        "top_synthetic_pct": top_synthetic,
        "top_degraded_pct": top_degraded,
    }


def report_with_checkpoint_rows(
    report: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = dedupe_checkpoint_rows(rows)
    if not rows:
        return report
    blockers = [row for row in rows if row.get("status") != "PASS"]
    selected_count = _as_int(report.get("selected_market_year_count")) or len(rows)
    pending_count = max(0, selected_count - len(rows))
    merged = dict(report)
    merged.update(
        {
            "status": "FAIL"
            if report.get("failure_count") or blockers or pending_count
            else "PASS",
            "checked_market_year_count": len(rows),
            "pending_market_year_count": pending_count,
            "blocker_count": len(blockers),
            "blockers": sorted(
                blockers, key=lambda row: (str(row["market"]), int(row["year"]))
            ),
        }
    )
    return merged


def checkpoint_summary_base_report(
    *,
    profile: str,
    raw_root: Path,
    raw_alignment_report: Path,
    profile_config_path: Path,
    markets: list[str] | None = None,
    years: list[int] | None = None,
) -> dict[str, Any]:
    _, _, aliases, _ = load_profile_map(profile_config_path)
    resolved_profile = resolve_profile_name(profile, aliases)
    market_filter = {str(market) for market in markets} if markets else None
    year_filter = {int(year) for year in years} if years else None

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
        "stage": "phase2_readiness_checkpoint_summary",
        "status": "FAIL" if failures else "PASS",
        "profile": profile,
        "resolved_profile": resolved_profile,
        "market_filter": sorted(market_filter) if market_filter else None,
        "year_filter": sorted(year_filter) if year_filter else None,
        "selected_market_year_count": 0,
        "expected_market_year_count": 0,
        "checked_market_year_count": 0,
        "resumed_market_year_count": 0,
        "pending_market_year_count": 0,
        "blocker_count": 0,
        "failure_count": len(failures),
        "failures": failures,
        "blockers": [],
    }
    if failures:
        return report

    raw_alignment = json.loads(raw_alignment_report.read_text(encoding="utf-8"))
    expected_pairs = {
        pair
        for pair in raw_alignment_expected_market_years(raw_alignment)
        if market_year_selected(pair[0], pair[1])
    }
    inputs, missing_expected_pairs = filter_inputs_by_raw_alignment(
        resolve_profile_inputs(profile, raw_root, profile_config_path),
        raw_alignment,
    )
    inputs = [
        (market, year, path)
        for market, year, path in inputs
        if market_year_selected(market, year)
    ]
    missing_expected_pairs = {
        pair for pair in missing_expected_pairs if market_year_selected(pair[0], pair[1])
    }
    if missing_expected_pairs:
        failures.append(
            "raw alignment eligible market-years missing from profile config: "
            f"{len(missing_expected_pairs)}"
        )
    report.update(
        {
            "status": "FAIL" if failures else "PASS",
            "selected_market_year_count": len(inputs),
            "expected_market_year_count": len(expected_pairs) if expected_pairs else len(inputs),
            "failure_count": len(failures),
            "failures": failures,
        }
    )
    return report


def summarize_readiness_report(
    report: dict[str, Any],
    *,
    top_blockers: int = 20,
) -> dict[str, Any]:
    blockers = [
        blocker for blocker in report.get("blockers", []) if isinstance(blocker, dict)
    ]
    market_counts = Counter(str(blocker.get("market", "unknown")) for blocker in blockers)
    reason_counts: Counter[str] = Counter()
    reason_combo_counts: Counter[str] = Counter()
    for blocker in blockers:
        reasons = _blocker_reasons(blocker)
        reason_counts.update(reasons)
        reason_combo_counts.update(["+".join(reasons)])

    limit = max(0, int(top_blockers))
    compact_blockers = [_compact_blocker(blocker) for blocker in blockers]
    top_synthetic = sorted(
        compact_blockers,
        key=lambda row: (
            _as_float(row.get("synthetic_rows_pct")),
            _as_int(row.get("max_synthetic_gap_minutes")),
        ),
        reverse=True,
    )[:limit]
    top_degraded = sorted(
        compact_blockers,
        key=lambda row: _as_float(row.get("degraded_rows_pct")),
        reverse=True,
    )[:limit]
    selected_count = _as_int(report.get("selected_market_year_count"))
    checked_count = _as_int(report.get("checked_market_year_count"))
    blocker_count = len(blockers)
    return {
        "stage": "phase2_readiness_summary",
        "source_stage": report.get("stage"),
        "status": report.get("status"),
        "profile": report.get("profile"),
        "resolved_profile": report.get("resolved_profile"),
        "selected_market_year_count": selected_count,
        "checked_market_year_count": checked_count,
        "pass_count": max(0, checked_count - blocker_count),
        "blocker_count": blocker_count,
        "failure_count": _as_int(report.get("failure_count")),
        "failures": report.get("failures", []),
        "reason_counts": dict(sorted(reason_counts.items())),
        "reason_combo_counts": dict(sorted(reason_combo_counts.items())),
        "market_blocker_counts": dict(sorted(market_counts.items())),
        "enrichment_totals": {
            "status_missing_rows": sum(
                _as_int(blocker.get("status_enrichment_missing_rows"))
                for blocker in blockers
            ),
            "status_stale_rows": sum(
                _as_int(blocker.get("status_enrichment_stale_rows"))
                for blocker in blockers
            ),
            "statistics_missing_rows": sum(
                _as_int(blocker.get("statistics_enrichment_missing_rows"))
                for blocker in blockers
            ),
            "statistics_stale_rows": sum(
                _as_int(blocker.get("statistics_enrichment_stale_rows"))
                for blocker in blockers
            ),
        },
        "enrichment_blocker_counts": {
            "status_missing": sum(
                1
                for blocker in blockers
                if _as_int(blocker.get("status_enrichment_missing_rows")) > 0
            ),
            "status_stale": sum(
                1
                for blocker in blockers
                if _as_int(blocker.get("status_enrichment_stale_rows")) > 0
            ),
            "statistics_missing": sum(
                1
                for blocker in blockers
                if _as_int(blocker.get("statistics_enrichment_missing_rows")) > 0
            ),
            "statistics_stale": sum(
                1
                for blocker in blockers
                if _as_int(blocker.get("statistics_enrichment_stale_rows")) > 0
            ),
        },
        "top_synthetic_pct": top_synthetic,
        "top_degraded_pct": top_degraded,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        resume_rows = (
            load_checkpoint_rows(Path(args.resume_from)) if args.resume_from else []
        )
    except Exception as exc:
        output = {
            "stage": "phase2_readiness_preflight",
            "status": "FAIL",
            "failure_count": 1,
            "failures": [str(exc)],
        }
        print(json.dumps(output, indent=2))
        return 1

    if args.checkpoint_summary_only:
        if not resume_rows:
            output = {
                "stage": "phase2_readiness_checkpoint_summary",
                "status": "FAIL",
                "failure_count": 1,
                "failures": ["--checkpoint-summary-only requires --resume-from"],
            }
            print(json.dumps(output, indent=2))
            return 1
        base_report = checkpoint_summary_base_report(
            profile=args.profile,
            raw_root=Path(args.raw_root),
            raw_alignment_report=Path(args.raw_alignment_report),
            profile_config_path=Path(args.profile_config),
            markets=args.markets,
            years=args.years,
        )
        output = summarize_checkpoint_rows(
            resume_rows,
            base_report=base_report,
            top_blockers=args.top_blockers,
        )
        if args.json_out:
            json_out = Path(args.json_out)
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(output, indent=2))
        return 0 if output.get("status") == "PASS" else 1

    if not args.output_root:
        parser.error("--output-root is required; pass an explicit causal output root")

    checkpoint_path = Path(args.checkpoint_jsonl) if args.checkpoint_jsonl else None
    new_rows: list[dict[str, Any]] = []

    def checkpoint_callback(row: dict[str, Any]) -> None:
        new_rows.append(row)
        if checkpoint_path is not None:
            append_checkpoint_row(checkpoint_path, row)

    report = build_phase2_readiness_report(
        profile=args.profile,
        raw_root=Path(args.raw_root),
        raw_alignment_report=Path(args.raw_alignment_report),
        output_root=Path(args.output_root),
        profile_config_path=Path(args.profile_config),
        session_config_path=Path(args.session_config),
        roll_window_bars=args.roll_window_bars,
        max_synthetic_gap_minutes=args.max_synthetic_gap_minutes,
        allow_hardcoded_calendar=args.allow_hardcoded_calendar,
        fail_fast=args.fail_fast,
        jobs=args.jobs,
        progress=args.progress,
        markets=args.markets,
        years=args.years,
        skip_market_years=[_market_year_key(row) for row in resume_rows],
        checkpoint_row_callback=(
            checkpoint_callback
            if checkpoint_path is not None or resume_rows or args.summary_only
            else None
        ),
        max_market_years=args.max_market_years,
        stop_after_blockers=args.stop_after_blockers,
    )
    checkpoint_rows = dedupe_checkpoint_rows([*resume_rows, *new_rows])
    output = (
        summarize_checkpoint_rows(
            checkpoint_rows,
            base_report=report,
            top_blockers=args.top_blockers,
        )
        if args.summary_only and checkpoint_rows
        else summarize_readiness_report(report, top_blockers=args.top_blockers)
        if args.summary_only
        else report_with_checkpoint_rows(report, checkpoint_rows)
        if resume_rows
        else report
    )
    if args.json_out:
        json_out = Path(args.json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if output.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
