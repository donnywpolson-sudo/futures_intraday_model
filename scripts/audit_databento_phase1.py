#!/usr/bin/env python3
"""Phase 1 raw Databento DBN inventory."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.audit_databento_common import (
    Blocker,
    PhaseResult,
    blocker_from_mutation,
    compare_source_manifests,
    discover_dbn_zst_files,
    phase_gate_path,
    rel,
    repo_path,
    source_manifest_rows,
    utc_now,
    write_csv,
    write_json,
    write_phase_outputs,
    write_source_manifest,
    write_text,
)


PHASE = "phase1"
EXPECTED_L0_SCHEMAS = ("ohlcv-1m", "definition", "statistics", "status")
EXPECTED_TRADES_SCHEMA = "trades"
EXPECTED_MARKETS = (
    "ES",
    "NQ",
    "RTY",
    "YM",
    "CL",
    "NG",
    "RB",
    "HO",
    "GC",
    "SI",
    "HG",
    "SR3",
    "SR1",
    "TN",
    "ZT",
    "ZF",
    "ZN",
    "ZB",
    "UB",
    "6A",
    "6B",
    "6C",
    "6E",
    "6J",
    "6M",
    "ZC",
    "ZS",
    "ZL",
    "ZM",
    "ZW",
    "KE",
    "LE",
    "HE",
)
MARKET_START_OVERRIDES = {
    "KE": 2013,
    "RTY": 2017,
    "SR1": 2018,
    "SR3": 2018,
    "TN": 2016,
    "ZL": 2011,
    "ZM": 2011,
}
EXPECTED_END_YEAR = 2026
TINY_FILE_BYTES = 1024


def expected_pairs() -> list[tuple[str, int]]:
    pairs: list[tuple[str, int]] = []
    for market in EXPECTED_MARKETS:
        start = MARKET_START_OVERRIDES.get(market, 2010)
        pairs.extend((market, year) for year in range(start, EXPECTED_END_YEAR + 1))
    return pairs


def infer_schema_root(parts: list[str]) -> tuple[str, str, str]:
    try:
        dbn_idx = parts.index("dbn")
    except ValueError:
        return "", "", "unknown"
    root = parts[dbn_idx + 1] if len(parts) > dbn_idx + 1 else ""
    if root == "ohlcv_1m":
        return root, "ohlcv-1m", "l0"
    if root == "ohlcv_1m_parent":
        return root, "ohlcv-1m", "parent_l0"
    if root == "definition":
        return root, "definition", "l0"
    if root == "statistics":
        return root, "statistics", "l0"
    if root == "statistics_parent":
        return root, "statistics", "parent_l0"
    if root == "status":
        return root, "status", "l0"
    if root == "status_parent":
        return root, "status", "parent_l0"
    if root == "trades":
        return root, "trades", "trades"
    if root == "ohlcv_1d":
        return root, "ohlcv-1d", "extra_ohlcv"
    if root == "ohlcv_1h":
        return root, "ohlcv-1h", "extra_ohlcv"
    if root == "ohlcv_1s":
        return root, "ohlcv-1s", "extra_ohlcv"
    return root, root.replace("_", "-"), "unexpected"


def infer_market_year(parts: list[str]) -> tuple[str, int | None]:
    market = ""
    year: int | None = None
    for part in parts:
        if re.fullmatch(r"\d{4}", part):
            year = int(part)
            break
        if part in {"data", "dbn", "status", "statistics"}:
            continue
        if part.endswith("_parent") or part.startswith("ohlcv_") or part in {"definition", "trades"}:
            continue
        market = part
    return market, year


def infer_dates(path: Path) -> tuple[str, str]:
    match = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.dbn\.zst$", path.name)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def read_manifest(path: Path) -> tuple[dict[str, Any] | None, str]:
    manifest_path = path.with_name(f"{path.name}.manifest.json")
    if not manifest_path.exists():
        return None, "missing"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None, "unreadable"
    if not isinstance(payload, dict):
        return None, "invalid"
    return payload, "ok"


def manifest_conflicts(row: dict[str, Any], manifest: dict[str, Any] | None) -> list[str]:
    if manifest is None:
        return []
    conflicts: list[str] = []
    checks = {
        "schema": row["schema"],
        "market": row["market"],
        "start": row["date_start"],
        "end": row["date_end"],
    }
    for key, expected in checks.items():
        actual = str(manifest.get(key, ""))
        if expected and actual and actual != str(expected):
            conflicts.append(f"{key}: path={expected} manifest={actual}")
    manifest_size = manifest.get("file_size_bytes")
    if manifest_size is not None and int(manifest_size) != int(row["size_bytes"]):
        conflicts.append(f"file_size_bytes: stat={row['size_bytes']} manifest={manifest_size}")
    return conflicts


def inventory_row(path: Path) -> dict[str, Any]:
    rel_path = rel(path)
    parts = rel_path.split("/")
    schema_root, schema, tier = infer_schema_root(parts)
    market, year = infer_market_year(parts)
    start, end = infer_dates(path)
    stat = path.stat()
    manifest, metadata_status = read_manifest(path)
    row: dict[str, Any] = {
        "path": rel_path,
        "schema_root": schema_root,
        "schema": schema,
        "tier": tier,
        "market": market,
        "year": year if year is not None else "",
        "date_start": start,
        "date_end": end,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "manifest_path": rel(path.with_name(f"{path.name}.manifest.json")),
        "manifest_present": metadata_status != "missing",
        "metadata_status": metadata_status,
        "metadata_schema": manifest.get("schema", "") if manifest else "",
        "metadata_market": manifest.get("market", "") if manifest else "",
        "metadata_start": manifest.get("start", "") if manifest else "",
        "metadata_end": manifest.get("end", "") if manifest else "",
        "metadata_conflicts": "",
        "anomalies": "",
    }
    conflicts = manifest_conflicts(row, manifest)
    row["metadata_conflicts"] = "; ".join(conflicts)
    anomalies: list[str] = []
    if stat.st_size == 0:
        anomalies.append("empty_file")
    elif stat.st_size < TINY_FILE_BYTES:
        anomalies.append("tiny_file")
    if metadata_status in {"unreadable", "invalid"}:
        anomalies.append(f"metadata_{metadata_status}")
    if conflicts:
        anomalies.append("metadata_path_conflict")
    if not schema:
        anomalies.append("schema_unparsed")
    if not market:
        anomalies.append("market_unparsed")
    if year is None:
        anomalies.append("year_unparsed")
    row["anomalies"] = "; ".join(anomalies)
    return row


def date_overlaps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["date_start"] and row["date_end"]:
            grouped[(str(row["schema_root"]), str(row["market"]), str(row["year"]))].append(row)
    overlaps: list[dict[str, Any]] = []
    for key, items in grouped.items():
        ordered = sorted(items, key=lambda row: str(row["date_start"]))
        previous: dict[str, Any] | None = None
        for item in ordered:
            if previous and str(item["date_start"]) < str(previous["date_end"]):
                overlaps.append(
                    {
                        "schema_root": key[0],
                        "market": key[1],
                        "year": key[2],
                        "path": item["path"],
                        "evidence": f"{item['date_start']} starts before previous end {previous['date_end']}",
                    }
                )
            previous = item
    return overlaps


def duplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["schema_root"]),
            str(row["market"]),
            str(row["year"]),
            str(row["date_start"]),
            str(row["date_end"]),
        )
        grouped[key].append(row)
    duplicates: list[dict[str, Any]] = []
    for key, items in grouped.items():
        if len(items) > 1:
            duplicates.append(
                {
                    "schema_root": key[0],
                    "market": key[1],
                    "year": key[2],
                    "path": "; ".join(str(item["path"]) for item in items),
                    "evidence": f"duplicate_count={len(items)}",
                }
            )
    return duplicates


def coverage_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    expected = expected_pairs()
    by_key = Counter((str(row["schema"]), str(row["market"]), int(row["year"])) for row in rows if row["year"] != "")
    matrix: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for schema in EXPECTED_L0_SCHEMAS:
        for market, year in expected:
            file_count = by_key.get((schema, market, year), 0)
            matrix.append({"schema": schema, "market": market, "year": year, "file_count": file_count, "present": file_count > 0})
            if file_count == 0:
                severity = "Medium" if schema == "status" else "Severe"
                missing.append(
                    {
                        "schema": schema,
                        "market": market,
                        "year": year,
                        "severity": severity,
                        "reason": "missing expected schema-market-year archive",
                    }
                )
    market_schema: list[dict[str, Any]] = []
    for (schema, market), items in sorted(
        defaultdict(list, {}).items()
    ):
        _ = schema, market, items
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    file_counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if row["year"] == "":
            continue
        key = (str(row["market"]), str(row["schema"]))
        grouped[key].append(int(row["year"]))
        file_counts[key] += 1
    for (market, schema), years in sorted(grouped.items()):
        market_schema.append(
            {
                "market": market,
                "schema": schema,
                "year_count": len(set(years)),
                "first_year": min(years),
                "last_year": max(years),
                "file_count": file_counts[(market, schema)],
            }
        )
    return matrix, market_schema, missing


def anomaly_rows(
    rows: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    overlaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    expected_market_set = set(EXPECTED_MARKETS)
    for row in rows:
        path = str(row["path"])
        schema = str(row["schema"])
        market = str(row["market"])
        year = int(row["year"]) if row["year"] != "" else None
        for item in str(row["anomalies"]).split("; "):
            if not item:
                continue
            severity = "Severe" if item == "empty_file" else "Medium"
            anomalies.append({"severity": severity, "type": item, "path": path, "evidence": str(row.get("metadata_conflicts", ""))})
        if schema not in {*EXPECTED_L0_SCHEMAS, EXPECTED_TRADES_SCHEMA, "ohlcv-1d", "ohlcv-1h", "ohlcv-1s"}:
            anomalies.append({"severity": "Medium", "type": "unexpected_schema", "path": path, "evidence": schema})
        if market and market not in expected_market_set:
            anomalies.append({"severity": "Medium", "type": "unexpected_market", "path": path, "evidence": market})
        if year is not None and not 2010 <= year <= 2026:
            anomalies.append({"severity": "Medium", "type": "unexpected_year", "path": path, "evidence": str(year)})
        if schema in {"ohlcv-1d", "ohlcv-1h", "ohlcv-1s"}:
            anomalies.append({"severity": "Low", "type": "extra_ohlcv_schema", "path": path, "evidence": schema})
        if row["metadata_status"] == "missing":
            anomalies.append({"severity": "Low", "type": "missing_sidecar_manifest", "path": path, "evidence": row["manifest_path"]})
    for row in missing:
        anomalies.append(
            {
                "severity": row["severity"],
                "type": "missing_expected_coverage",
                "path": "",
                "evidence": f"{row['schema']} {row['market']} {row['year']}",
            }
        )
    for row in duplicates:
        anomalies.append({"severity": "Medium", "type": "duplicate_archive_interval", "path": row["path"], "evidence": row["evidence"]})
    for row in overlaps:
        anomalies.append({"severity": "Medium", "type": "overlapping_archive_interval", "path": row["path"], "evidence": row["evidence"]})
    return anomalies


def blockers_from_anomalies(anomalies: list[dict[str, Any]], mutation_check: dict[str, Any]) -> list[Blocker]:
    blockers = blocker_from_mutation(PHASE, mutation_check)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in anomalies:
        grouped[(str(row["severity"]), str(row["type"]))].append(row)
    for (severity, issue_type), items in sorted(grouped.items()):
        if severity not in {"Severe", "Medium", "Low"}:
            continue
        blockers.append(
            Blocker(
                severity=severity,
                phase=PHASE,
                issue=issue_type,
                evidence=f"count={len(items)} first={items[0].get('evidence', '')}",
                recommendation="Review Phase 1 inventory reports before later audit phases.",
            )
        )
    return blockers


def metadata_audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "path": row["path"],
            "manifest_path": row["manifest_path"],
            "metadata_status": row["metadata_status"],
            "metadata_schema": row["metadata_schema"],
            "metadata_market": row["metadata_market"],
            "metadata_start": row["metadata_start"],
            "metadata_end": row["metadata_end"],
            "metadata_conflicts": row["metadata_conflicts"],
        }
        for row in rows
    ]


def render_report(summary: dict[str, Any], blockers: list[Blocker]) -> str:
    lines = [
        "# Phase 1 Raw DBN Inventory Report",
        "",
        f"- Status: `{summary['status']}`",
        f"- Canonical raw source: `{summary['canonical_raw_source']}`",
        f"- Raw `.dbn.zst` files found: {summary['raw_dbn_zst_file_count']}",
        f"- Markets found: {summary['market_count']} / {', '.join(summary['markets'])}",
        f"- Years found: {summary['year_count']} / {summary['year_range']}",
        f"- L0 schemas found: {', '.join(summary['l0_schemas_found'])}",
        f"- Trade schemas found: {', '.join(summary['trade_schemas_found'])}",
        f"- Missing schema-market-years: {summary['missing_expected_coverage_count']}",
        f"- Unreadable metadata files: {summary['unreadable_metadata_file_count']}",
        f"- Suspicious files: {summary['suspicious_file_count']}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- `{blocker.severity}`: {blocker.issue} | {blocker.evidence}" for blocker in blockers)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def run_phase1(args: Any) -> dict[str, Any]:
    started = utc_now()
    output_dir = repo_path(args.output_dir)
    phase_dir = output_dir / "phase1_raw_inventory"
    state_dir = output_dir / "state"

    phase0_gate = repo_path(args.output_dir) / "phase0_folder_triage" / "phase0_readiness_gate.json"
    phase0_payload = json.loads(phase0_gate.read_text(encoding="utf-8"))
    if not phase0_payload.get("summary", {}).get("canonical_raw_source_identified"):
        blockers = [
            Blocker(
                "Severe",
                PHASE,
                "canonical raw .dbn.zst source folder not identified by Phase 0",
                rel(phase0_gate),
                "Stop Phase 1 until Phase 0 identifies canonical source.",
            )
        ]
        result = PhaseResult(
            phase=PHASE,
            started_at=started,
            finished_at=utc_now(),
            reports=[],
            blockers=blockers,
            source_mutation_check="not_applicable",
            summary={"canonical_raw_source": ""},
            gate_path=phase_dir / "phase1_readiness_gate.json",
            blockers_csv=phase_dir / "blockers.csv",
        )
        return write_phase_outputs(result)

    before = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    write_source_manifest(state_dir / "source_manifest_before.csv", before)

    paths = discover_dbn_zst_files(Path(args.data_root), max_files=args.max_files)
    rows = [inventory_row(path) for path in paths]
    coverage_matrix, market_schema_coverage, missing = coverage_rows(rows)
    duplicates = duplicate_rows(rows)
    overlaps = date_overlaps(rows)
    anomalies = anomaly_rows(rows, missing, duplicates, overlaps)
    after = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    write_source_manifest(state_dir / "source_manifest_after.csv", after)
    mutation_check = compare_source_manifests(before, after)
    write_json(state_dir / "source_mutation_check.json", mutation_check)

    blockers = blockers_from_anomalies(anomalies, mutation_check)
    severe = sum(1 for blocker in blockers if blocker.severity == "Severe")
    medium = sum(1 for blocker in blockers if blocker.severity == "Medium")
    status = "fail" if severe else "pass_with_medium_blockers" if medium else "pass"
    markets = sorted({str(row["market"]) for row in rows if row["market"]})
    years = sorted({int(row["year"]) for row in rows if row["year"] != ""})
    l0_schemas_found = sorted({str(row["schema"]) for row in rows if row["schema"] in EXPECTED_L0_SCHEMAS})
    trade_schemas_found = sorted({str(row["schema"]) for row in rows if row["schema"] == EXPECTED_TRADES_SCHEMA})
    trades = [row for row in rows if row["schema"] == EXPECTED_TRADES_SCHEMA and row["date_start"] and row["date_end"]]
    trade_starts = sorted(str(row["date_start"]) for row in trades)
    trade_ends = sorted(str(row["date_end"]) for row in trades)
    summary = {
        "status": status,
        "canonical_raw_source": str(args.data_root).replace("\\", "/"),
        "raw_dbn_zst_file_count": len(rows),
        "market_count": len(markets),
        "markets": markets,
        "year_count": len(years),
        "years": years,
        "year_range": f"{min(years)}-{max(years)}" if years else "",
        "schema_counts": dict(sorted(Counter(str(row["schema"]) for row in rows).items())),
        "tier_counts": dict(sorted(Counter(str(row["tier"]) for row in rows).items())),
        "l0_schemas_found": l0_schemas_found,
        "trade_schemas_found": trade_schemas_found,
        "trades_date_start_min": trade_starts[0] if trade_starts else "",
        "trades_date_end_max": trade_ends[-1] if trade_ends else "",
        "missing_expected_coverage_count": len(missing),
        "unreadable_metadata_file_count": sum(1 for row in rows if row["metadata_status"] in {"unreadable", "invalid"}),
        "missing_sidecar_manifest_count": sum(1 for row in rows if row["metadata_status"] == "missing"),
        "suspicious_file_count": sum(1 for row in anomalies if row["severity"] in {"Severe", "Medium"}),
        "empty_file_count": sum(1 for row in rows if row["size_bytes"] == 0),
        "tiny_file_count": sum(1 for row in rows if 0 < row["size_bytes"] < TINY_FILE_BYTES),
        "duplicate_interval_count": len(duplicates),
        "overlap_interval_count": len(overlaps),
        "metadata_conflict_count": sum(1 for row in rows if row["metadata_conflicts"]),
        "severe_issue_count": sum(1 for blocker in blockers if blocker.severity == "Severe"),
        "medium_issue_count": sum(1 for blocker in blockers if blocker.severity == "Medium"),
        "low_issue_count": sum(1 for blocker in blockers if blocker.severity == "Low"),
    }

    write_csv(
        phase_dir / "inventory.csv",
        [
            "path",
            "schema_root",
            "schema",
            "tier",
            "market",
            "year",
            "date_start",
            "date_end",
            "size_bytes",
            "mtime_ns",
            "manifest_path",
            "manifest_present",
            "metadata_status",
            "metadata_schema",
            "metadata_market",
            "metadata_start",
            "metadata_end",
            "metadata_conflicts",
            "anomalies",
        ],
        rows,
    )
    write_json(phase_dir / "inventory_summary.json", summary)
    write_csv(phase_dir / "coverage_matrix_schema_market_year.csv", ["schema", "market", "year", "file_count", "present"], coverage_matrix)
    write_csv(phase_dir / "market_schema_coverage.csv", ["market", "schema", "year_count", "first_year", "last_year", "file_count"], market_schema_coverage)
    write_csv(phase_dir / "missing_expected_coverage.csv", ["schema", "market", "year", "severity", "reason"], missing)
    write_csv(
        phase_dir / "dbn_metadata_audit.csv",
        ["path", "manifest_path", "metadata_status", "metadata_schema", "metadata_market", "metadata_start", "metadata_end", "metadata_conflicts"],
        metadata_audit_rows(rows),
    )
    write_csv(phase_dir / "inventory_anomalies.csv", ["severity", "type", "path", "evidence"], anomalies)
    result = PhaseResult(
        phase=PHASE,
        started_at=started,
        finished_at=utc_now(),
        reports=[
            rel(phase_dir / "inventory.csv"),
            rel(phase_dir / "inventory_summary.json"),
            rel(phase_dir / "coverage_matrix_schema_market_year.csv"),
            rel(phase_dir / "market_schema_coverage.csv"),
            rel(phase_dir / "missing_expected_coverage.csv"),
            rel(phase_dir / "dbn_metadata_audit.csv"),
            rel(phase_dir / "inventory_anomalies.csv"),
            rel(phase_dir / "blockers.csv"),
            rel(phase_dir / "phase1_readiness_gate.json"),
            rel(phase_dir / "phase1_report.md"),
        ],
        blockers=blockers,
        source_mutation_check=str(mutation_check["source_mutation_check"]),
        summary=summary,
        gate_path=phase_gate_path(Path(args.output_dir), 1, "phase1_readiness_gate.json"),
        blockers_csv=phase_dir / "blockers.csv",
    )
    write_text(phase_dir / "phase1_report.md", render_report(summary, blockers))
    gate = write_phase_outputs(result)
    print(
        "phase1 status={status} severe={severe} medium={medium} low={low} files={files} blockers_csv={blockers}".format(
            status=gate["status"],
            severe=gate["severe_count"],
            medium=gate["medium_count"],
            low=gate["low_count"],
            files=summary["raw_dbn_zst_file_count"],
            blockers=gate["blockers_csv"],
        )
    )
    return gate

