#!/usr/bin/env python3
"""Add provenance continuity counts to the Tier 1 data audit decision table."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


LOCAL_TRADES_USABLE_DECISION = "acceptable_with_caveat_ohlcv_empty_minutes_assumed"
LOCAL_TRADES_PROVENANCE_DECISION = "local_trades_access_window_validated_ohlcv_convention"
LOCAL_TRADES_PASS_REASON = (
    "configured local trades access window validated the same-market OHLCV no-trade convention; "
    "applying user-approved dataset-wide OHLCV validation assumption"
)
LOCAL_TRADES_SCHEMA_ACCESS_START = datetime(2025, 6, 18, tzinfo=UTC)
LOCAL_TRADES_SCHEMA_ACCESS_END = datetime(2026, 6, 13, tzinfo=UTC)

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


def _utc_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _access_window_years() -> list[int]:
    return list(range(LOCAL_TRADES_SCHEMA_ACCESS_START.year, LOCAL_TRADES_SCHEMA_ACCESS_END.year + 1))


def _local_trades_report_covers_access_window(window: dict[str, Any]) -> tuple[bool, str | None]:
    start = _utc_timestamp(window.get("start"))
    end = _utc_timestamp(window.get("end"))
    if start is None or end is None:
        return False, "local trades evidence missing parseable window"
    if start > LOCAL_TRADES_SCHEMA_ACCESS_START or end < LOCAL_TRADES_SCHEMA_ACCESS_END:
        return (
            False,
            f"local trades evidence window [{_iso_z(start)}, {_iso_z(end)}) does not cover "
            "configured local trades schema access window "
            f"[{_iso_z(LOCAL_TRADES_SCHEMA_ACCESS_START)}, {_iso_z(LOCAL_TRADES_SCHEMA_ACCESS_END)})",
        )
    return True, None


def _local_trades_evidence_for_market(
    *,
    report: dict[str, Any],
    report_path: Path,
    market: str,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    window = report.get("window") if isinstance(report.get("window"), dict) else {}
    by_year = {int(entry.get("year") or 0): entry for entry in entries}
    expected_years = _access_window_years()
    missing = 0
    verified = 0
    failed = 0
    unverified = 0
    trade_rows_scanned = 0
    archives_read = 0

    stop_reasons: list[str] = []
    window_covers, window_reason = _local_trades_report_covers_access_window(window)
    if not window_covers and window_reason:
        stop_reasons.append(window_reason)
    missing_years = [year for year in expected_years if year not in by_year]
    if missing_years:
        stop_reasons.append(
            "local trades report missing access-window year slices: "
            + ", ".join(str(year) for year in missing_years)
        )
    for year in expected_years:
        entry = by_year.get(year)
        if entry is None:
            continue
        summary = entry.get("summary") if isinstance(entry.get("summary"), dict) else {}
        entry_missing = _nullable_int(summary.get("missing_minute_count")) or 0
        entry_verified = _nullable_int(summary.get("verified_empty_minutes")) or 0
        entry_failed = _nullable_int(summary.get("failed_minutes")) or 0
        entry_unverified = _nullable_int(summary.get("unverified_minutes")) or 0
        entry_archives = _nullable_int(summary.get("archives_read")) or 0
        missing += entry_missing
        verified += entry_verified
        failed += entry_failed
        unverified += entry_unverified
        trade_rows_scanned += _nullable_int(summary.get("trade_rows_scanned")) or 0
        archives_read += entry_archives
        if str(entry.get("status") or "") != "PASS":
            stop_reasons.append(
                f"{market} {year} local trades market-year status is {entry.get('status')!r}"
            )
        if entry_failed != 0:
            stop_reasons.append(f"{market} {year} failed_minutes={entry_failed}")
        if entry_unverified != 0:
            stop_reasons.append(f"{market} {year} unverified_minutes={entry_unverified}")
        if entry_verified != entry_missing:
            stop_reasons.append(
                f"{market} {year} verified_empty_minutes={entry_verified} "
                f"does not equal missing_minute_count={entry_missing}"
            )
        if entry_archives <= 0 and entry_missing > 0:
            stop_reasons.append(
                f"{market} {year} local trades evidence read no archives for missing-minute proof"
            )

    return {
        "path": _relative_path(report_path),
        "report_status": report.get("status"),
        "window_start": window.get("start"),
        "window_end": window.get("end"),
        "schema_access_start": _iso_z(LOCAL_TRADES_SCHEMA_ACCESS_START),
        "schema_access_end": _iso_z(LOCAL_TRADES_SCHEMA_ACCESS_END),
        "status": "PASS" if not stop_reasons else "FAIL",
        "missing_minute_count": missing,
        "verified_empty_minutes": verified,
        "failed_minutes": failed,
        "unverified_minutes": unverified,
        "trade_rows_scanned": trade_rows_scanned,
        "archives_read": archives_read,
        "validation_scope": "market_access_window_to_dataset_inference",
        "validation_years": expected_years,
        "wfa_usable": not stop_reasons,
        "stop_reason": "; ".join(stop_reasons) if stop_reasons else None,
        "market": market,
    }


def _local_trades_evidence_map(
    paths: list[Path],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    evidence: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for path in paths:
        payload, read_failures = _read_json(path)
        failures.extend(read_failures)
        entries = payload.get("market_years", []) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            failures.append(f"local trades gap report missing market_years list: {_relative_path(path)}")
            continue
        entries_by_market: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            market = str(entry.get("market") or "")
            if not market:
                continue
            entries_by_market.setdefault(market, []).append(entry)
        for market, market_entries in sorted(entries_by_market.items()):
            if market in evidence:
                failures.append(f"duplicate local trades gap evidence for {market}")
                continue
            evidence[market] = _local_trades_evidence_for_market(
                report=payload,
                report_path=path,
                market=market,
                entries=market_entries,
            )
    return evidence, failures


def _add_local_trades_fields(
    row: dict[str, Any],
    evidence: dict[str, Any] | None,
) -> None:
    row["local_trades_gap_evidence_path"] = evidence.get("path") if evidence else None
    row["local_trades_gap_report_status"] = evidence.get("report_status") if evidence else None
    row["local_trades_gap_window_start"] = evidence.get("window_start") if evidence else None
    row["local_trades_gap_window_end"] = evidence.get("window_end") if evidence else None
    row["local_trades_schema_access_start"] = (
        evidence.get("schema_access_start") if evidence else _iso_z(LOCAL_TRADES_SCHEMA_ACCESS_START)
    )
    row["local_trades_schema_access_end"] = (
        evidence.get("schema_access_end") if evidence else _iso_z(LOCAL_TRADES_SCHEMA_ACCESS_END)
    )
    row["local_trades_gap_status"] = evidence.get("status") if evidence else None
    row["local_trades_gap_missing_minute_count"] = (
        evidence.get("missing_minute_count") if evidence else None
    )
    row["local_trades_gap_verified_empty_minutes"] = (
        evidence.get("verified_empty_minutes") if evidence else None
    )
    row["local_trades_gap_failed_minutes"] = evidence.get("failed_minutes") if evidence else None
    row["local_trades_gap_unverified_minutes"] = (
        evidence.get("unverified_minutes") if evidence else None
    )
    row["local_trades_gap_trade_rows_scanned"] = (
        evidence.get("trade_rows_scanned") if evidence else None
    )
    row["local_trades_gap_archives_read"] = evidence.get("archives_read") if evidence else None
    row["local_trades_gap_validation_scope"] = (
        evidence.get("validation_scope") if evidence else "market_access_window_to_dataset_inference"
    )
    row["local_trades_gap_validation_years"] = evidence.get("validation_years") if evidence else []
    row["local_trades_gap_wfa_usable"] = bool(evidence.get("wfa_usable")) if evidence else False
    row["local_trades_gap_stop_reason"] = (
        evidence.get("stop_reason") if evidence else "missing same-market local trades access-window evidence"
    )


def _can_promote_with_local_trades(row: dict[str, Any], evidence: dict[str, Any] | None) -> bool:
    if not evidence or not evidence.get("wfa_usable"):
        return False
    if row.get("failures") or []:
        return False
    if str(row.get("missing_minute_status") or "") != "PASS":
        return False
    if str(row.get("provenance_status") or "") != "PASS":
        return False
    return True


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
    local_trades_paths = [Path(path) for path in getattr(args, "local_trades_gap_json", [])]
    local_trades_map, local_trades_failures = _local_trades_evidence_map(local_trades_paths)
    failures.extend(local_trades_failures)

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
        local_trades_evidence = local_trades_map.get(market)
        _add_local_trades_fields(augmented, local_trades_evidence)
        if _can_promote_with_local_trades(augmented, local_trades_evidence):
            augmented["provenance_decision"] = LOCAL_TRADES_PROVENANCE_DECISION
            augmented["final_decision"] = LOCAL_TRADES_USABLE_DECISION
            augmented["reason"] = LOCAL_TRADES_PASS_REASON
            augmented["local_trades_gap_stop_reason"] = None
        augmented_rows.append(augmented)

    decision_counts = Counter(str(row.get("final_decision")) for row in augmented_rows)
    provenance_counts = Counter(str(row.get("provenance_status")) for row in augmented_rows)
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "method": (
            "augment existing Tier 1 data audit decisions with roll/symbol/instrument synthetic "
            "counts from existing OHLCV provenance reports and optional same-market local-trades "
            "access-window validation"
        ),
        "source_decision_table_json": _relative_path(decision_path),
        "provenance_jsons": [_relative_path(path) for path in provenance_paths],
        "local_trades_gap_jsons": [_relative_path(path) for path in local_trades_paths],
        "local_trades_schema_access": {
            "start": _iso_z(LOCAL_TRADES_SCHEMA_ACCESS_START),
            "end": _iso_z(LOCAL_TRADES_SCHEMA_ACCESS_END),
            "wfa_usage": (
                "a passing same-market local trades audit for the configured access window validates "
                "the OHLCV no-trade convention for the broader OHLCV dataset by explicit policy assumption"
            ),
        },
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
        "This report augments existing data-audit decisions with provenance counts and optional same-market local-trades access-window validation.",
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
            "| Market | Year | Missing status | Provenance status | Provenance decision | Synthetic rows | Active-session synthetic rows | Largest gap min | Roll-window synthetic | Symbol-change synthetic | Instrument-change synthetic | Local trades status | Local trades usable | Final decision | Reason |",
            "|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|---|",
        ]
    )
    for row in report["rows"]:
        lines.append(
            "| `{market}` | {year} | `{missing}` | `{prov_status}` | `{prov_decision}` | {synthetic} | "
            "{active} | {largest_gap} | {roll} | {symbol} | {instrument} | `{local_status}` | {local_usable} | `{final}` | {reason} |".format(
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
                local_status=row.get("local_trades_gap_status"),
                local_usable=str(bool(row.get("local_trades_gap_wfa_usable"))).lower(),
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
    parser.add_argument("--local-trades-gap-json", action="append", default=[])
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
