#!/usr/bin/env python3
"""Add provenance continuity counts to the Tier 1 data audit decision table."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_PROVENANCE_JSONS = [
    "reports/pipeline_audit/ohlcv_provenance_ES_2010_2024.json",
    "reports/pipeline_audit/ohlcv_provenance_CL_2010_2024.json",
    "reports/pipeline_audit/ohlcv_provenance_ZN_2010_2024.json",
    "reports/pipeline_audit/ohlcv_provenance_6E_2010_2024.json",
]

COUNT_FIELDS = (
    "roll_window_synthetic_rows",
    "symbol_change_synthetic_rows",
    "instrument_id_change_synthetic_rows",
)


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"missing JSON: {_relative_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"unreadable JSON {_relative_path(path)}: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"JSON must be an object: {_relative_path(path)}"]
    return payload, []


def _entry_count_map(paths: list[Path]) -> tuple[dict[tuple[str, int], dict[str, int | None]], list[str]]:
    counts: dict[tuple[str, int], dict[str, int | None]] = {}
    failures: list[str] = []
    for path in paths:
        payload, read_failures = _read_json(path)
        failures.extend(read_failures)
        for entry in payload.get("entries", []) if isinstance(payload.get("entries"), list) else []:
            if not isinstance(entry, dict):
                continue
            market = str(entry.get("market") or "")
            year = int(entry.get("year") or 0)
            continuity = entry.get("continuity")
            if not market or not year or not isinstance(continuity, dict):
                continue
            counts[(market, year)] = {
                field: _nullable_int(continuity.get(field)) for field in COUNT_FIELDS
            }
    return counts, failures


def _nullable_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    decision_path = Path(args.decision_table_json)
    decision_payload, failures = _read_json(decision_path)
    rows = decision_payload.get("rows", [])
    if not isinstance(rows, list):
        rows = []
        failures.append("decision table missing rows list")

    provenance_paths = [Path(path) for path in (args.provenance_json or DEFAULT_PROVENANCE_JSONS)]
    count_map, count_failures = _entry_count_map(provenance_paths)
    failures.extend(count_failures)

    augmented_rows: list[dict[str, Any]] = []
    missing_counts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        market = str(row.get("market") or "")
        year = int(row.get("year") or 0)
        augmented = dict(row)
        counts = count_map.get((market, year))
        if counts is None:
            counts = {field: None for field in COUNT_FIELDS}
            missing_counts.append(f"{market} {year}")
        for field in COUNT_FIELDS:
            augmented[field] = counts.get(field)
        augmented_rows.append(augmented)

    decision_counts = Counter(str(row.get("final_decision")) for row in augmented_rows)
    provenance_counts = Counter(str(row.get("provenance_status")) for row in augmented_rows)
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "method": (
            "augment existing Tier 1 data audit decisions with roll/symbol/instrument synthetic "
            "counts from existing OHLCV provenance reports; decisions preserved"
        ),
        "source_decision_table_json": _relative_path(decision_path),
        "provenance_jsons": [_relative_path(path) for path in provenance_paths],
        "count_fields": list(COUNT_FIELDS),
        "missing_count_market_years": missing_counts,
        "decision_counts": dict(sorted(decision_counts.items())),
        "provenance_status_counts": dict(sorted(provenance_counts.items())),
        "rows": augmented_rows,
    }


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Tier 1 Data Audit Decisions",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Status: `{report['status']}`",
        "",
        "This report preserves existing data-audit decisions and adds roll/symbol/instrument synthetic counts from provenance reports.",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in report["decision_counts"].items())
    lines.extend(
        [
            "",
            "## Decisions",
            "",
            "| Market | Year | Missing status | Provenance status | Provenance decision | Synthetic rows | Active-session synthetic rows | Largest gap min | Roll-window synthetic | Symbol-change synthetic | Instrument-change synthetic | Final decision | Reason |",
            "|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in report["rows"]:
        lines.append(
            "| `{market}` | {year} | `{missing}` | `{prov_status}` | `{prov_decision}` | {synthetic} | "
            "{active} | {largest_gap} | {roll} | {symbol} | {instrument} | `{final}` | {reason} |".format(
                market=row.get("market"),
                year=row.get("year"),
                missing=row.get("missing_minute_status"),
                prov_status=row.get("provenance_status"),
                prov_decision=row.get("provenance_decision"),
                synthetic=row.get("synthetic_rows", ""),
                active=row.get("active_session_synthetic_rows", ""),
                largest_gap=row.get("largest_gap_size_minutes", ""),
                roll="" if row.get("roll_window_synthetic_rows") is None else row.get("roll_window_synthetic_rows"),
                symbol="" if row.get("symbol_change_synthetic_rows") is None else row.get("symbol_change_synthetic_rows"),
                instrument=""
                if row.get("instrument_id_change_synthetic_rows") is None
                else row.get("instrument_id_change_synthetic_rows"),
                final=row.get("final_decision"),
                reason=row.get("reason"),
            )
        )
    if report["missing_count_market_years"]:
        lines.extend(["", "## Missing Count Evidence", ""])
        lines.extend(f"- `{item}`" for item in report["missing_count_market_years"])
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decision-table-json",
        default="reports/pipeline_audit/tier_1_data_audit_decisions.json",
    )
    parser.add_argument("--provenance-json", action="append", default=[])
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_report(args)
    write_json_report(report, Path(args.json_out))
    if args.md_out:
        write_markdown_report(report, Path(args.md_out))
    if report["status"] != "PASS":
        print(f"FAIL Tier 1 data audit decisions: failures={len(report['failures'])}")
        return 1
    print(f"PASS Tier 1 data audit decisions: rows={len(report['rows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
