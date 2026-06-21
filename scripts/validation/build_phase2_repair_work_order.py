#!/usr/bin/env python3
"""Build a Phase 2 repair work-order report from readiness evidence."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.validation.audit_phase2_readiness import load_checkpoint_rows
from scripts.validation.diagnose_phase2_readiness_blockers import product_group
from scripts.validation.summarize_phase2_readiness_blockers import classify_blocker

DEFAULT_CHECKPOINT = Path("reports/phase2_readiness/tier3_readiness_20260620.jsonl")
DEFAULT_DRILLDOWN = Path("reports/phase2_readiness/tier3_readiness_raw_drilldown_20260620.json")

WORK_ORDER_ACTIONS = (
    "repair_raw_coverage",
    "repair_status_statistics_enrichment",
    "review_session_scope",
    "review_degraded_raw_quality",
    "review_roll_metadata",
    "exclude_only_if_explicitly_approved",
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-jsonl", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--drilldown-json", default=str(DEFAULT_DRILLDOWN))
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--p0-batch-size", type=int, default=25)
    parser.add_argument("--json-out")
    parser.add_argument("--csv-out")
    parser.add_argument("--md-out")
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


def _enrichment_blocked(row: dict[str, Any]) -> bool:
    return any(
        _as_int(row.get(column)) > 0
        for column in (
            "status_enrichment_missing_rows",
            "status_enrichment_stale_rows",
            "statistics_enrichment_missing_rows",
            "statistics_enrichment_stale_rows",
        )
    )


def _load_drilldown(path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"drilldown JSON must be a mapping: {path}")
    rows = payload.get("drilldowns", [])
    if not isinstance(rows, list):
        raise ValueError(f"drilldown JSON drilldowns must be a list: {path}")
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        by_key[(str(row.get("market")), _as_int(row.get("year")))] = row
    return by_key


def _work_order_actions(row: dict[str, Any]) -> list[str]:
    classes, _ = classify_blocker(row)
    actions: list[str] = []
    if "synthetic" in classes:
        actions.extend(["repair_raw_coverage", "review_session_scope"])
    if _enrichment_blocked(row):
        actions.append("repair_status_statistics_enrichment")
    if "degraded" in classes:
        actions.append("review_degraded_raw_quality")
    if "roll" in classes:
        actions.append("review_roll_metadata")
    actions.append("exclude_only_if_explicitly_approved")
    return [action for action in WORK_ORDER_ACTIONS if action in set(actions)]


def _priority(row: dict[str, Any], actions: list[str]) -> str:
    synthetic_pct = _as_float(row.get("synthetic_rows_pct"))
    degraded_pct = _as_float(row.get("degraded_rows_pct"))
    max_gap = _as_int(row.get("max_synthetic_gap_minutes"))
    if (
        synthetic_pct >= 10.0
        or max_gap >= 120
        or degraded_pct >= 5.0
        or "repair_raw_coverage" in actions
        and "repair_status_statistics_enrichment" in actions
    ):
        return "P0"
    if "repair_raw_coverage" in actions or "review_degraded_raw_quality" in actions:
        return "P1"
    if "repair_status_statistics_enrichment" in actions:
        return "P2"
    return "P3"


def _work_order_row(
    row: dict[str, Any],
    *,
    drilldown: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    market = str(row.get("market"))
    year = _as_int(row.get("year"))
    actions = _work_order_actions(row)
    classes, other_reasons = classify_blocker(row)
    drilldown_row = drilldown.get((market, year), {})
    session_gap = drilldown_row.get("phase2_session_gap_summary", {})
    if not isinstance(session_gap, dict):
        session_gap = {}
    return {
        "market": market,
        "year": year,
        "product_group": product_group(market),
        "checkpoint_status": row.get("status"),
        "priority": _priority(row, actions),
        "work_order_actions": actions,
        "blocker_classes": sorted(classes),
        "other_reasons": other_reasons,
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
        "drilldown_available": bool(drilldown_row),
        "phase2_session_candidate_gap_count": _as_int(
            session_gap.get("candidate_gap_count")
        ),
        "phase2_session_synthetic_missing_rows_estimate": _as_int(
            session_gap.get("synthetic_missing_rows_estimate")
        ),
        "phase2_session_max_candidate_gap_minutes": _as_float(
            session_gap.get("max_candidate_gap_minutes")
        ),
        "decision_status": "BLOCKED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED",
        "candidate_exclusion_status": "DIAGNOSTIC_ONLY_NOT_APPROVED",
    }


def _action_counts(work_orders: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in work_orders:
        counts.update(row["work_order_actions"])
    return {action: counts[action] for action in WORK_ORDER_ACTIONS if counts[action]}


def _market_action_counts(work_orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    total_by_market: Counter[str] = Counter()
    p0_by_market: Counter[str] = Counter()
    for row in work_orders:
        market = str(row["market"])
        total_by_market[market] += 1
        if row["priority"] == "P0":
            p0_by_market[market] += 1
        counts[market].update(row["work_order_actions"])
    rows = []
    for market in sorted(total_by_market):
        payload = {
            "market": market,
            "product_group": product_group(market),
            "work_order_count": total_by_market[market],
            "p0_count": p0_by_market[market],
        }
        payload.update({action: counts[market][action] for action in WORK_ORDER_ACTIONS})
        rows.append(payload)
    return rows


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


def _p0_raw_session_rows(work_orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in work_orders
        if row["priority"] == "P0"
        and "repair_raw_coverage" in row["work_order_actions"]
        and "review_session_scope" in row["work_order_actions"]
    ]
    return sorted(
        selected,
        key=lambda row: (
            -_as_float(row.get("synthetic_rows_pct")),
            -_as_int(row.get("max_synthetic_gap_minutes")),
            str(row.get("market")),
            _as_int(row.get("year")),
        ),
    )


def _readiness_commands_by_market(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    years_by_market: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        years_by_market[str(row["market"])].append(_as_int(row["year"]))
    commands = []
    for market in sorted(years_by_market):
        years = sorted(set(years_by_market[market]))
        commands.append(
            {
                "market": market,
                "years": years,
                "when_to_run": "after these market-years have explicit repair evidence",
                "command": (
                    "python -m scripts.validation.audit_phase2_readiness "
                    "--profile tier_3 --raw-root data\\raw "
                    "--raw-alignment-report reports\\raw_ingest\\raw_dbn_alignment.json "
                    "--jobs 1 --summary-only --top-blockers 25 "
                    f"--markets {market} --years {' '.join(str(year) for year in years)}"
                ),
            }
        )
    return commands


def _p0_start_batch(
    work_orders: list[dict[str, Any]],
    *,
    batch_size: int,
) -> dict[str, Any]:
    all_p0 = _p0_raw_session_rows(work_orders)
    batch = all_p0[: max(0, int(batch_size))]
    return {
        "status": "REPAIR_REQUIRED_BEFORE_READINESS_RERUN",
        "all_p0_raw_session_count": len(all_p0),
        "batch_size": len(batch),
        "repaired_market_year_count": 0,
        "readiness_rerun_status": "NOT_RUN_NO_REPAIRED_MARKET_YEARS_DECLARED",
        "repair_preconditions": [
            "Do not rerun readiness for a market-year until raw coverage, session scope, or explicit exclusion evidence has changed.",
            "Do not accept WARN as training-ready.",
            "Do not change canonical Phase 2 until a repaired market-year rerun returns PASS.",
        ],
        "batch_market_years": [
            {
                "market": row["market"],
                "year": row["year"],
                "product_group": row["product_group"],
                "synthetic_rows_pct": row["synthetic_rows_pct"],
                "max_synthetic_gap_minutes": row["max_synthetic_gap_minutes"],
                "phase2_session_candidate_gap_count": row[
                    "phase2_session_candidate_gap_count"
                ],
                "phase2_session_synthetic_missing_rows_estimate": row[
                    "phase2_session_synthetic_missing_rows_estimate"
                ],
                "required_decision": (
                    "repair_raw_coverage_or_session_scope_before_bounded_readiness"
                ),
            }
            for row in batch
        ],
        "bounded_readiness_commands_after_repair": _readiness_commands_by_market(batch),
    }


def build_repair_work_order_report(
    checkpoint_rows: list[dict[str, Any]],
    *,
    drilldown_rows: dict[tuple[str, int], dict[str, Any]] | None = None,
    top_n: int = 25,
    p0_batch_size: int = 25,
) -> dict[str, Any]:
    drilldown_rows = drilldown_rows or {}
    blockers = [row for row in checkpoint_rows if row.get("status") != "PASS"]
    passable = [row for row in checkpoint_rows if row.get("status") == "PASS"]
    work_orders = [
        _work_order_row(row, drilldown=drilldown_rows)
        for row in sorted(blockers, key=lambda item: (str(item.get("market")), _as_int(item.get("year"))))
    ]
    priority_counts = Counter(str(row["priority"]) for row in work_orders)
    return {
        "stage": "phase2_repair_work_order",
        "status": "FAIL" if work_orders else "PASS",
        "policy": "FAIL_CLOSED_REPAIR_OR_EXPLICIT_EXCLUSION_REQUIRED",
        "ready_to_rebuild_tier3_phase2": False,
        "evidence_scope": {
            "checkpoint_jsonl_read": True,
            "drilldown_json_read": bool(drilldown_rows),
            "raw_parquet_read": False,
            "raw_parquet_written": False,
            "canonical_phase2_written": False,
            "labels_features_wfa_predictions_written": False,
        },
        "selected_market_year_count": len(checkpoint_rows),
        "pass_count": len(passable),
        "work_order_count": len(work_orders),
        "priority_counts": dict(sorted(priority_counts.items())),
        "action_counts": _action_counts(work_orders),
        "market_action_counts": _market_action_counts(work_orders),
        "top_work_orders": {
            "synthetic": _top_rows(
                work_orders,
                "synthetic_rows_pct",
                secondary_key="max_synthetic_gap_minutes",
                top_n=top_n,
            ),
            "degraded": _top_rows(work_orders, "degraded_rows_pct", top_n=top_n),
            "status_enrichment": _top_rows(
                work_orders,
                "status_enrichment_missing_rows",
                secondary_key="status_enrichment_stale_rows",
                top_n=top_n,
            ),
            "statistics_enrichment": _top_rows(
                work_orders,
                "statistics_enrichment_missing_rows",
                secondary_key="statistics_enrichment_stale_rows",
                top_n=top_n,
            ),
            "session_gap_drilldown": _top_rows(
                work_orders,
                "phase2_session_synthetic_missing_rows_estimate",
                secondary_key="phase2_session_candidate_gap_count",
                top_n=top_n,
            ),
        },
        "p0_repair_start_batch": _p0_start_batch(
            work_orders,
            batch_size=p0_batch_size,
        ),
        "work_orders": work_orders,
        "passable_market_years": [
            {
                "market": str(row.get("market")),
                "year": _as_int(row.get("year")),
                "status": "PASS_DIAGNOSTIC_ONLY",
            }
            for row in sorted(passable, key=lambda item: (str(item.get("market")), _as_int(item.get("year"))))
        ],
        "decision_rules": [
            "Do not rebuild canonical Tier 3 Phase 2 while work_order_count is nonzero.",
            "Repair evidence must turn each market-year PASS before use in canonical training data.",
            "Exclusion candidates are diagnostic-only until explicitly approved as a universe change.",
            "Do not loosen thresholds or accept WARN as training-ready.",
        ],
        "next_exact_action": (
            "Start with P0 repair_raw_coverage/review_session_scope markets, then rerun "
            "bounded readiness for repaired market-years only."
        ),
    }


def write_work_order_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "market",
        "year",
        "product_group",
        "priority",
        "work_order_actions",
        "blocker_classes",
        "synthetic_rows_pct",
        "max_synthetic_gap_minutes",
        "degraded_rows_pct",
        "status_enrichment_missing_rows",
        "status_enrichment_stale_rows",
        "statistics_enrichment_missing_rows",
        "statistics_enrichment_stale_rows",
        "phase2_session_candidate_gap_count",
        "phase2_session_synthetic_missing_rows_estimate",
        "decision_status",
        "candidate_exclusion_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in report.get("work_orders", []):
            output = row.copy()
            output["work_order_actions"] = ";".join(row.get("work_order_actions", []))
            output["blocker_classes"] = ";".join(row.get("blocker_classes", []))
            writer.writerow(output)


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase 2 Repair Work Order",
        "",
        f"- Status: {report['status']}",
        f"- Policy: {report['policy']}",
        f"- Ready to rebuild Tier 3 Phase 2: {report['ready_to_rebuild_tier3_phase2']}",
        f"- Checked market-years: {report['selected_market_year_count']}",
        f"- Pass count: {report['pass_count']}",
        f"- Work order count: {report['work_order_count']}",
        f"- Priority counts: {json.dumps(report['priority_counts'], sort_keys=True)}",
        f"- Action counts: {json.dumps(report['action_counts'], sort_keys=True)}",
        "",
        "## Top Markets",
        "",
        "| market | work orders | P0 | raw coverage | enrichment | degraded | roll |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["market_action_counts"][:40]:
        lines.append(
            "| {market} | {work_order_count} | {p0_count} | {raw} | {enrich} | {degraded} | {roll} |".format(
                market=row["market"],
                work_order_count=row["work_order_count"],
                p0_count=row["p0_count"],
                raw=row["repair_raw_coverage"],
                enrich=row["repair_status_statistics_enrichment"],
                degraded=row["review_degraded_raw_quality"],
                roll=row["review_roll_metadata"],
            )
        )
    lines.extend(
        [
            "",
            "## P0 Starter Batch",
            "",
            f"- Status: {report['p0_repair_start_batch']['status']}",
            f"- All P0 raw/session count: {report['p0_repair_start_batch']['all_p0_raw_session_count']}",
            f"- Batch size: {report['p0_repair_start_batch']['batch_size']}",
            f"- Readiness rerun status: {report['p0_repair_start_batch']['readiness_rerun_status']}",
            "",
            "| market | year | group | synthetic % | max gap min | session gap count |",
            "|---|---:|---|---:|---:|---:|",
        ]
    )
    for row in report["p0_repair_start_batch"]["batch_market_years"][:40]:
        lines.append(
            "| {market} | {year} | {group} | {synthetic:.6f} | {gap} | {session_gaps} |".format(
                market=row["market"],
                year=row["year"],
                group=row["product_group"],
                synthetic=float(row["synthetic_rows_pct"]),
                gap=row["max_synthetic_gap_minutes"],
                session_gaps=row["phase2_session_candidate_gap_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Decision Rules",
            "",
            *[f"- {item}" for item in report["decision_rules"]],
            "",
            f"Next exact action: {report['next_exact_action']}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _compact_stdout(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": report["stage"],
        "status": report["status"],
        "policy": report["policy"],
        "ready_to_rebuild_tier3_phase2": report["ready_to_rebuild_tier3_phase2"],
        "pass_count": report["pass_count"],
        "work_order_count": report["work_order_count"],
        "priority_counts": report["priority_counts"],
        "action_counts": report["action_counts"],
        "p0_repair_start_batch": {
            "status": report["p0_repair_start_batch"]["status"],
            "all_p0_raw_session_count": report["p0_repair_start_batch"][
                "all_p0_raw_session_count"
            ],
            "batch_size": report["p0_repair_start_batch"]["batch_size"],
            "readiness_rerun_status": report["p0_repair_start_batch"][
                "readiness_rerun_status"
            ],
        },
        "next_exact_action": report["next_exact_action"],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        rows = load_checkpoint_rows(Path(args.checkpoint_jsonl))
        drilldown_rows = _load_drilldown(Path(args.drilldown_json))
        report = build_repair_work_order_report(
            rows,
            drilldown_rows=drilldown_rows,
            top_n=args.top_n,
            p0_batch_size=args.p0_batch_size,
        )
    except Exception as exc:
        report = {
            "stage": "phase2_repair_work_order",
            "status": "FAIL",
            "failure_count": 1,
            "failures": [str(exc)],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    if args.json_out:
        json_out = Path(args.json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.csv_out:
        write_work_order_csv(Path(args.csv_out), report)
    if args.md_out:
        write_markdown(Path(args.md_out), report)
    print(json.dumps(_compact_stdout(report), indent=2, sort_keys=True))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
