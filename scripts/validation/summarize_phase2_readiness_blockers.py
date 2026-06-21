#!/usr/bin/env python3
"""Summarize Phase 2 readiness checkpoint blockers for repair planning."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.validation.audit_phase2_readiness import load_checkpoint_rows

DEFAULT_CHECKPOINT = Path("reports/phase2_readiness/tier3_readiness_20260620.jsonl")
BLOCKER_CLASSES = ("synthetic", "degraded", "roll")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-jsonl", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--json-out")
    parser.add_argument("--csv-out")
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


def classify_blocker(row: dict[str, Any]) -> tuple[set[str], list[str]]:
    classes: set[str] = set()
    other_reasons: list[str] = []
    for reason in (row.get("warnings") or []) + (row.get("failures") or []):
        reason_text = str(reason or "unknown")
        if reason_text.startswith("synthetic threshold breached"):
            classes.add("synthetic")
        elif reason_text.startswith("degraded threshold breached"):
            classes.add("degraded")
        elif reason_text.startswith("roll exclusion threshold breached") or reason_text.startswith(
            "roll maturity sequence not monotonic"
        ):
            classes.add("roll")
        else:
            other_reasons.append(reason_text)
    if not classes and not other_reasons and row.get("status") != "PASS":
        other_reasons.append(str(row.get("top_blocker_reason") or "unknown"))
    return classes, sorted(set(other_reasons))


def _reason_combo(classes: set[str], other_reasons: list[str]) -> str:
    parts = [item for item in BLOCKER_CLASSES if item in classes]
    parts.extend(other_reasons)
    return "+".join(parts) if parts else "PASS"


def _enrichment_flags(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "status_missing": _as_int(row.get("status_enrichment_missing_rows")) > 0,
        "status_stale": _as_int(row.get("status_enrichment_stale_rows")) > 0,
        "statistics_missing": _as_int(row.get("statistics_enrichment_missing_rows")) > 0,
        "statistics_stale": _as_int(row.get("statistics_enrichment_stale_rows")) > 0,
    }


def _market_year_row(row: dict[str, Any]) -> dict[str, Any]:
    classes, other_reasons = classify_blocker(row)
    flags = _enrichment_flags(row)
    return {
        "market": str(row.get("market")),
        "year": _as_int(row.get("year")),
        "status": row.get("status"),
        "blocker_classes": sorted(classes),
        "other_reasons": other_reasons,
        "reason_combo": _reason_combo(classes, other_reasons),
        "top_blocker_reason": row.get("top_blocker_reason"),
        "synthetic_rows_pct": _as_float(row.get("synthetic_rows_pct")),
        "max_synthetic_gap_minutes": _as_int(row.get("max_synthetic_gap_minutes")),
        "degraded_rows_pct": _as_float(row.get("degraded_rows_pct")),
        "status_enrichment_missing_rows": _as_int(
            row.get("status_enrichment_missing_rows")
        ),
        "status_enrichment_stale_rows": _as_int(row.get("status_enrichment_stale_rows")),
        "statistics_enrichment_missing_rows": _as_int(
            row.get("statistics_enrichment_missing_rows")
        ),
        "statistics_enrichment_stale_rows": _as_int(
            row.get("statistics_enrichment_stale_rows")
        ),
        "status_enrichment_blocker": flags["status_missing"] or flags["status_stale"],
        "statistics_enrichment_blocker": (
            flags["statistics_missing"] or flags["statistics_stale"]
        ),
    }


def _top_rows(
    rows: list[dict[str, Any]],
    key: str,
    *,
    limit: int,
    secondary_key: str | None = None,
) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _as_float(row.get(key)),
            _as_float(row.get(secondary_key)) if secondary_key else 0.0,
        ),
        reverse=True,
    )[:limit]


def build_triage_report(rows: list[dict[str, Any]], *, top_n: int = 25) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: (str(row.get("market")), _as_int(row.get("year"))))
    blockers = [_market_year_row(row) for row in rows if row.get("status") != "PASS"]
    passable = [
        {"market": str(row.get("market")), "year": _as_int(row.get("year"))}
        for row in rows
        if row.get("status") == "PASS"
    ]
    status_counts = Counter(str(row.get("status")) for row in rows)
    class_totals = {name: 0 for name in BLOCKER_CLASSES}
    class_pure = {name: 0 for name in BLOCKER_CLASSES}
    reason_combo_counts: Counter[str] = Counter()
    market_counts: dict[str, Counter[str]] = defaultdict(Counter)
    enrichment_counts = Counter()
    for blocker in blockers:
        classes = set(blocker["blocker_classes"])
        combo = str(blocker["reason_combo"])
        reason_combo_counts[combo] += 1
        market = str(blocker["market"])
        market_counts[market]["blocker_count"] += 1
        for blocker_class in classes:
            class_totals[blocker_class] += 1
            market_counts[market][f"{blocker_class}_blockers"] += 1
        if len(classes) == 1:
            class_pure[next(iter(classes))] += 1
        if blocker["status_enrichment_blocker"]:
            enrichment_counts["status_missing_or_stale"] += 1
            market_counts[market]["status_enrichment_blockers"] += 1
        if blocker["statistics_enrichment_blocker"]:
            enrichment_counts["statistics_missing_or_stale"] += 1
            market_counts[market]["statistics_enrichment_blockers"] += 1

    pass_counts_by_market = Counter(str(row.get("market")) for row in rows if row.get("status") == "PASS")
    total_counts_by_market = Counter(str(row.get("market")) for row in rows)
    market_level_counts = []
    for market in sorted(total_counts_by_market):
        counts = market_counts[market]
        market_level_counts.append(
            {
                "market": market,
                "total_count": total_counts_by_market[market],
                "pass_count": pass_counts_by_market[market],
                "blocker_count": counts["blocker_count"],
                "synthetic_blockers": counts["synthetic_blockers"],
                "degraded_blockers": counts["degraded_blockers"],
                "roll_blockers": counts["roll_blockers"],
                "status_enrichment_blockers": counts["status_enrichment_blockers"],
                "statistics_enrichment_blockers": counts["statistics_enrichment_blockers"],
            }
        )

    limit = max(0, int(top_n))
    return {
        "stage": "phase2_readiness_blocker_triage",
        "status": "FAIL" if blockers else "PASS",
        "policy": "FAIL_CLOSED_DIAGNOSTIC_ONLY",
        "ready_to_rebuild_tier3_phase2": False,
        "selected_market_year_count": len(rows),
        "checked_market_year_count": len(rows),
        "pass_count": len(passable),
        "blocker_count": len(blockers),
        "status_counts": dict(sorted(status_counts.items())),
        "blocker_class_counts": {
            name: {"total": class_totals[name], "pure": class_pure[name]}
            for name in BLOCKER_CLASSES
        },
        "enrichment_blocker_counts": dict(sorted(enrichment_counts.items())),
        "reason_combo_counts": dict(sorted(reason_combo_counts.items())),
        "market_level_counts": market_level_counts,
        "market_year_blockers": blockers,
        "passable_market_years": passable,
        "top_offenders": {
            "synthetic": _top_rows(
                blockers,
                "synthetic_rows_pct",
                secondary_key="max_synthetic_gap_minutes",
                limit=limit,
            ),
            "degraded": _top_rows(blockers, "degraded_rows_pct", limit=limit),
            "status_enrichment": _top_rows(
                blockers,
                "status_enrichment_missing_rows",
                secondary_key="status_enrichment_stale_rows",
                limit=limit,
            ),
            "statistics_enrichment": _top_rows(
                blockers,
                "statistics_enrichment_missing_rows",
                secondary_key="statistics_enrichment_stale_rows",
                limit=limit,
            ),
        },
        "candidate_exclusion_universe": {
            "status": "DIAGNOSTIC_ONLY",
            "caveat": (
                "Not a training universe and not approval to exclude data; use only "
                "for repair versus exclusion review."
            ),
            "market_years": [
                {
                    "market": row["market"],
                    "year": row["year"],
                    "reason_combo": row["reason_combo"],
                }
                for row in blockers
            ],
        },
    }


def write_market_year_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = report.get("market_year_blockers", [])
    fieldnames = [
        "market",
        "year",
        "status",
        "reason_combo",
        "top_blocker_reason",
        "synthetic_rows_pct",
        "max_synthetic_gap_minutes",
        "degraded_rows_pct",
        "status_enrichment_missing_rows",
        "status_enrichment_stale_rows",
        "statistics_enrichment_missing_rows",
        "statistics_enrichment_stale_rows",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        rows = load_checkpoint_rows(Path(args.checkpoint_jsonl))
        report = build_triage_report(rows, top_n=args.top_n)
    except Exception as exc:
        report = {
            "stage": "phase2_readiness_blocker_triage",
            "status": "FAIL",
            "failure_count": 1,
            "failures": [str(exc)],
        }
        print(json.dumps(report, indent=2))
        return 1

    if args.json_out:
        json_out = Path(args.json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.csv_out:
        write_market_year_csv(Path(args.csv_out), report)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
