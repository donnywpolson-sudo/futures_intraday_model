#!/usr/bin/env python3
"""Diagnose Phase 2 readiness blockers from checkpoint evidence only."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.validation.audit_phase2_readiness import load_checkpoint_rows
from scripts.validation.summarize_phase2_readiness_blockers import classify_blocker

DEFAULT_CHECKPOINT = Path("reports/phase2_readiness/tier3_readiness_20260620.jsonl")
PRODUCT_GROUPS = {
    "equity_index": {"ES", "NQ", "RTY", "YM"},
    "energy": {"CL", "HO", "NG", "RB"},
    "metals": {"GC", "HG", "SI"},
    "fx": {"6A", "6B", "6C", "6E", "6J", "6M"},
    "rates": {"SR1", "SR3", "TN", "UB", "ZB", "ZF", "ZN", "ZT"},
    "grains": {"KE", "ZC", "ZL", "ZM", "ZS", "ZW"},
    "livestock": {"HE", "LE"},
}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-jsonl", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--json-out")
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


def product_group(market: object) -> str:
    market_text = str(market)
    for group, markets in PRODUCT_GROUPS.items():
        if market_text in markets:
            return group
    return "unknown"


def _enrichment_flags(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "status": (
            _as_int(row.get("status_enrichment_missing_rows")) > 0
            or _as_int(row.get("status_enrichment_stale_rows")) > 0
        ),
        "statistics": (
            _as_int(row.get("statistics_enrichment_missing_rows")) > 0
            or _as_int(row.get("statistics_enrichment_stale_rows")) > 0
        ),
    }


def _reason_combo(classes: set[str], enrichments: dict[str, bool]) -> str:
    parts = []
    for name in ("synthetic", "degraded", "roll"):
        if name in classes:
            parts.append(name)
    for name in ("status", "statistics"):
        if enrichments[name]:
            parts.append(f"{name}_enrichment")
    return "+".join(parts) if parts else "PASS"


def _diagnostic_market_year(row: dict[str, Any]) -> dict[str, Any]:
    classes, other_reasons = classify_blocker(row)
    enrichments = _enrichment_flags(row)
    market = str(row.get("market"))
    return {
        "market": market,
        "year": _as_int(row.get("year")),
        "product_group": product_group(market),
        "status": row.get("status"),
        "blocker_classes": sorted(classes),
        "enrichment_blockers": [
            name for name in ("status", "statistics") if enrichments[name]
        ],
        "reason_combo": _reason_combo(classes, enrichments),
        "other_reasons": other_reasons,
        "top_blocker_reason": row.get("top_blocker_reason"),
        "synthetic_rows_pct": _as_float(row.get("synthetic_rows_pct")),
        "synthetic_rows": _as_int(row.get("synthetic_rows")),
        "max_synthetic_gap_minutes": _as_int(row.get("max_synthetic_gap_minutes")),
        "degraded_rows_pct": _as_float(row.get("degraded_rows_pct")),
        "degraded_bar_rows": _as_int(row.get("degraded_bar_rows")),
        "degraded_session_rows": _as_int(row.get("degraded_session_rows")),
        "roll_window_rows_pct": _as_float(row.get("roll_window_rows_pct")),
        "roll_window_rows": _as_int(row.get("roll_window_rows")),
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
        "session_date_detail": "not_available_in_checkpoint",
        "trading_quoting_state_detail": "not_available_in_checkpoint",
    }


def _top_rows(
    rows: list[dict[str, Any]],
    key: str,
    *,
    top_n: int,
    secondary_key: str | None = None,
) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _as_float(row.get(key)),
            _as_float(row.get(secondary_key)) if secondary_key else 0.0,
        ),
        reverse=True,
    )[: max(0, int(top_n))]


def _root_cause_groups(blockers: list[dict[str, Any]], *, top_n: int) -> dict[str, Any]:
    groups: dict[str, Any] = {}
    synthetic = [row for row in blockers if "synthetic" in row["blocker_classes"]]
    degraded = [row for row in blockers if "degraded" in row["blocker_classes"]]
    roll = [row for row in blockers if "roll" in row["blocker_classes"]]
    status_enrichment = [
        row for row in blockers if "status" in row["enrichment_blockers"]
    ]
    statistics_enrichment = [
        row for row in blockers if "statistics" in row["enrichment_blockers"]
    ]

    groups["synthetic_coverage_or_session_scope"] = {
        "market_year_count": len(synthetic),
        "product_group_counts": dict(
            sorted(Counter(row["product_group"] for row in synthetic).items())
        ),
        "top_offenders": _top_rows(
            synthetic,
            "synthetic_rows_pct",
            secondary_key="max_synthetic_gap_minutes",
            top_n=top_n,
        ),
        "missing_detail": [
            "session_date",
            "status_is_trading",
            "status_is_quoting",
        ],
        "next_diagnostic": (
            "Run targeted raw/session gap drilldown for top synthetic offenders; "
            "checkpoint evidence cannot prove no-trade semantics."
        ),
    }
    groups["degraded_raw_quality"] = {
        "market_year_count": len(degraded),
        "product_group_counts": dict(
            sorted(Counter(row["product_group"] for row in degraded).items())
        ),
        "top_offenders": _top_rows(degraded, "degraded_rows_pct", top_n=top_n),
        "next_diagnostic": (
            "Inspect raw data_quality_status dates for concentrated degraded sessions."
        ),
    }
    groups["enrichment_coverage_or_join"] = {
        "status_market_year_count": len(status_enrichment),
        "statistics_market_year_count": len(statistics_enrichment),
        "status_top_offenders": _top_rows(
            status_enrichment,
            "status_enrichment_missing_rows",
            secondary_key="status_enrichment_stale_rows",
            top_n=top_n,
        ),
        "statistics_top_offenders": _top_rows(
            statistics_enrichment,
            "statistics_enrichment_missing_rows",
            secondary_key="statistics_enrichment_stale_rows",
            top_n=top_n,
        ),
        "next_diagnostic": (
            "Compare raw status/statistics enrichment availability against DBN sidecars "
            "and join windows before changing Phase 2 scope."
        ),
    }
    groups["roll_metadata_or_roll_window"] = {
        "market_year_count": len(roll),
        "product_group_counts": dict(
            sorted(Counter(row["product_group"] for row in roll).items())
        ),
        "top_offenders": _top_rows(roll, "roll_window_rows_pct", top_n=top_n),
        "next_diagnostic": (
            "Audit roll metadata and roll-window exclusion for these market-years."
        ),
    }
    return groups


def _decision_tables(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = [row for row in rows if row["status"] != "PASS"]
    passable = [row for row in rows if row["status"] == "PASS"]
    repair_candidates = []
    for row in blockers:
        action_reasons = []
        classes = set(row["blocker_classes"])
        enrichments = set(row["enrichment_blockers"])
        if "synthetic" in classes:
            action_reasons.append("session_scope_or_raw_coverage_review")
        if "degraded" in classes:
            action_reasons.append("raw_quality_status_review")
        if "roll" in classes:
            action_reasons.append("roll_metadata_review")
        if enrichments:
            action_reasons.append("enrichment_join_or_availability_review")
        repair_candidates.append(
            {
                "market": row["market"],
                "year": row["year"],
                "product_group": row["product_group"],
                "reason_combo": row["reason_combo"],
                "diagnostic_actions": action_reasons,
                "status": "DIAGNOSTIC_ONLY",
            }
        )

    return {
        "repair_candidates": repair_candidates,
        "exclusion_candidates": {
            "status": "DIAGNOSTIC_ONLY",
            "caveat": (
                "Not an approved exclusion list. These market-years are unready until "
                "repair evidence passes or an explicit exclusion policy is approved."
            ),
            "market_years": [
                {
                    "market": row["market"],
                    "year": row["year"],
                    "product_group": row["product_group"],
                    "reason_combo": row["reason_combo"],
                }
                for row in blockers
            ],
        },
        "already_passable": [
            {
                "market": row["market"],
                "year": row["year"],
                "product_group": row["product_group"],
                "status": "PASS_DIAGNOSTIC_ONLY",
            }
            for row in passable
        ],
    }


def build_root_cause_report(
    rows: list[dict[str, Any]],
    *,
    top_n: int = 25,
) -> dict[str, Any]:
    normalized = [_diagnostic_market_year(row) for row in rows]
    normalized = sorted(normalized, key=lambda row: (row["market"], row["year"]))
    blockers = [row for row in normalized if row["status"] != "PASS"]
    status_counts = Counter(str(row["status"]) for row in normalized)
    reason_combo_counts = Counter(str(row["reason_combo"]) for row in blockers)
    return {
        "stage": "phase2_readiness_root_cause_diagnostic",
        "status": "FAIL" if blockers else "PASS",
        "policy": "FAIL_CLOSED_DIAGNOSTIC_ONLY",
        "ready_to_rebuild_tier3_phase2": False,
        "evidence_scope": {
            "source": "phase2_readiness_checkpoint_jsonl",
            "raw_parquet_read": False,
            "canonical_phase2_written": False,
            "labels_features_wfa_touched": False,
            "session_date_detail": "not_available_in_checkpoint",
            "trading_quoting_state_detail": "not_available_in_checkpoint",
        },
        "selected_market_year_count": len(normalized),
        "checked_market_year_count": len(normalized),
        "pass_count": len(normalized) - len(blockers),
        "blocker_count": len(blockers),
        "status_counts": dict(sorted(status_counts.items())),
        "reason_combo_counts": dict(sorted(reason_combo_counts.items())),
        "root_cause_groups": _root_cause_groups(blockers, top_n=top_n),
        "decision_tables": _decision_tables(normalized),
        "next_actions": [
            "Do not rebuild canonical Tier 3 Phase 2 while status is FAIL.",
            "Run targeted drilldowns for top synthetic and enrichment offenders.",
            "Choose repair versus explicit exclusion only after primary evidence review.",
        ],
    }


def _compact_stdout(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": report["stage"],
        "status": report["status"],
        "policy": report["policy"],
        "ready_to_rebuild_tier3_phase2": report["ready_to_rebuild_tier3_phase2"],
        "checked_market_year_count": report["checked_market_year_count"],
        "pass_count": report["pass_count"],
        "blocker_count": report["blocker_count"],
        "reason_combo_counts": report["reason_combo_counts"],
        "root_cause_counts": {
            name: {
                key: value
                for key, value in group.items()
                if key.endswith("_count") or key == "market_year_count"
            }
            for name, group in report["root_cause_groups"].items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        rows = load_checkpoint_rows(Path(args.checkpoint_jsonl))
        report = build_root_cause_report(rows, top_n=args.top_n)
    except Exception as exc:
        report = {
            "stage": "phase2_readiness_root_cause_diagnostic",
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
    print(json.dumps(_compact_stdout(report), indent=2))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
