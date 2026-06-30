#!/usr/bin/env python3
"""Metadata-only inventory for local trade archive coverage of uncovered Phase 2 markets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.phase1A_download.download_databento_raw import raw_file_manifest_path
from scripts.phase1_raw_contract import (
    EXPECTED_COMPRESSION,
    EXPECTED_ENCODING,
    REQUIRED_DATASET,
    REQUIRED_MANIFEST_FIELDS,
    SCHEMA_PATHS,
)
from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import check_phase2_local_trade_ohlcv_gap_proof as proof_gate


STATUS_READY = "READY_FOR_BOUNDED_PROOF_RUN"
STATUS_NO_GO = "NO_GO_LOCAL_ARCHIVE_COVERAGE_INCOMPLETE"
SCHEMAS_TO_INVENTORY = ("ohlcv-1m", "definition", "trades")


def _utc_ts(value: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _utc_iso(value: str | pd.Timestamp) -> str:
    return _utc_ts(value).isoformat().replace("+00:00", "Z")


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _read_manifest(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    manifest_path = raw_file_manifest_path(path)
    if not manifest_path.exists():
        return None, [f"missing manifest: {manifest_path.as_posix()}"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"unreadable manifest: {type(exc).__name__}: {exc}"]
    if not isinstance(payload, dict):
        return None, [f"manifest is not an object: {manifest_path.as_posix()}"]
    return payload, []


def _manifest_interval(manifest: dict[str, Any]) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    try:
        start = _utc_ts(str(manifest["start"]))
        end = _utc_ts(str(manifest["end"]))
    except Exception:
        return None
    return (start, end) if end > start else None


def _overlaps(interval: tuple[pd.Timestamp, pd.Timestamp] | None, start: pd.Timestamp, end: pd.Timestamp) -> bool:
    if interval is None:
        return True
    interval_start, interval_end = interval
    return interval_start < end and interval_end > start


def _archive_year(path: Path) -> int | None:
    try:
        return int(path.parent.name)
    except ValueError:
        return None


def _validate_manifest_metadata(
    *,
    path: Path,
    manifest: dict[str, Any] | None,
    schema: str,
    market: str,
    repo_root: Path,
) -> tuple[tuple[pd.Timestamp, pd.Timestamp] | None, list[str]]:
    failures: list[str] = []
    if manifest is None:
        return None, ["missing manifest payload"]
    missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
    if missing:
        failures.append("manifest missing fields: " + ",".join(missing))
    if manifest.get("dataset") != REQUIRED_DATASET:
        failures.append("manifest dataset mismatch")
    if manifest.get("schema") != schema:
        failures.append("manifest schema mismatch")
    if manifest.get("market") != market:
        failures.append("manifest market mismatch")
    if manifest.get("encoding") != EXPECTED_ENCODING:
        failures.append("manifest encoding mismatch")
    if manifest.get("compression") != EXPECTED_COMPRESSION:
        failures.append("manifest compression mismatch")
    if manifest.get("path") != scope_gate.rel(path, repo_root):
        failures.append("manifest path mismatch")
    if int(manifest.get("file_size_bytes") or 0) <= 0:
        failures.append("manifest file_size_bytes invalid")
    elif path.exists() and int(manifest.get("file_size_bytes") or 0) != path.stat().st_size:
        failures.append("manifest file_size_bytes does not match current path size")
    if not manifest.get("file_sha256"):
        failures.append("manifest file_sha256 missing")
    interval = _manifest_interval(manifest)
    if interval is None:
        failures.append("manifest time range invalid")
    else:
        year = _archive_year(path)
        if year is not None:
            max_end = pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC")
            if interval[0].year != year or interval[1] > max_end:
                failures.append("manifest time range does not match path year")
    return interval, failures


def _coverage_gaps(
    intervals: list[dict[str, str]],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[dict[str, str]]:
    def bounds(row: dict[str, str]) -> tuple[pd.Timestamp, pd.Timestamp]:
        return _utc_ts(row["start"]), _utc_ts(row["end"])

    current = start
    gaps: list[dict[str, str]] = []
    ordered = sorted(intervals, key=lambda row: (bounds(row)[0], bounds(row)[1]))
    while current < end:
        candidates = [row for row in ordered if bounds(row)[0] <= current < bounds(row)[1]]
        if candidates:
            best = max(candidates, key=lambda row: bounds(row)[1])
            current = min(bounds(best)[1], end)
            continue
        future_starts = [bounds(row)[0] for row in ordered if bounds(row)[0] > current]
        gap_end = min(future_starts) if future_starts else end
        gap_end = min(gap_end, end)
        gaps.append({"start": _utc_iso(current), "end": _utc_iso(gap_end)})
        current = gap_end
    return gaps


def _inventory_schema_market(
    *,
    repo_root: Path,
    dbn_root: Path,
    schema: str,
    market: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    root = dbn_root / SCHEMA_PATHS[schema] / market
    if not root.is_dir():
        return {
            "schema": schema,
            "market": market,
            "root": scope_gate.rel(root, repo_root),
            "status": "FAIL",
            "failures": [f"{market} {schema}: missing market directory"],
            "archive_count": 0,
            "invalid_manifest_count": 0,
            "valid_intervals": [],
            "coverage_gaps": [{"start": _utc_iso(start), "end": _utc_iso(end)}],
            "archives": [],
        }

    archives: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in sorted(root.rglob("*.dbn.zst")):
        manifest, manifest_failures = _read_manifest(path)
        interval = _manifest_interval(manifest) if manifest is not None else None
        if not _overlaps(interval, start, end):
            continue
        archive_failures = list(manifest_failures)
        if not path.is_file() or path.stat().st_size <= 0:
            archive_failures.append("empty archive")
        if manifest is not None:
            interval, metadata_failures = _validate_manifest_metadata(
                path=path,
                manifest=manifest,
                schema=schema,
                market=market,
                repo_root=repo_root,
            )
            archive_failures.extend(metadata_failures)
        row: dict[str, Any] = {
            "path": scope_gate.rel(path, repo_root),
            "manifest_path": scope_gate.rel(raw_file_manifest_path(path), repo_root),
            "file_size_bytes": path.stat().st_size if path.exists() else 0,
            "failures": archive_failures,
        }
        if interval is not None and not archive_failures:
            row["start"] = _utc_iso(interval[0])
            row["end"] = _utc_iso(interval[1])
        archives.append(row)
        failures.extend(f"{market} {schema}: {failure}" for failure in archive_failures)

    valid_intervals = [
        {"start": str(row["start"]), "end": str(row["end"]), "path": str(row["path"])}
        for row in archives
        if not row["failures"] and row.get("start") and row.get("end")
    ]
    gaps = _coverage_gaps(valid_intervals, start, end)
    failures.extend(
        f"{market} {schema}: uncovered requested window segments={len(gaps)}"
        for _ in ([None] if gaps else [])
    )
    return {
        "schema": schema,
        "market": market,
        "root": scope_gate.rel(root, repo_root),
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "archive_count": len(archives),
        "invalid_manifest_count": sum(1 for row in archives if row["failures"]),
        "valid_intervals": valid_intervals,
        "coverage_gaps": gaps,
        "archives": archives,
    }


def evaluate_inventory(
    *,
    repo_root: Path,
    dbn_root: Path,
    data_manifest_path: Path,
    canonical_root: Path,
    reports_root: Path,
    phase2_manifest_path: Path,
    phase2_validation_path: Path,
    profile_config_path: Path,
    build_script_path: Path,
    local_report_paths: list[Path],
    expected_count: int = scope_gate.EXPECTED_CANONICAL_COUNT,
    feature_cols: Iterable[str] | None = None,
    git_head: str | None = None,
    staged_names: list[str] | None = None,
    scoped_status_lines: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    proof_report = proof_gate.evaluate_gap_proof(
        repo_root=repo_root,
        data_manifest_path=data_manifest_path,
        canonical_root=canonical_root,
        reports_root=reports_root,
        phase2_manifest_path=phase2_manifest_path,
        phase2_validation_path=phase2_validation_path,
        profile_config_path=profile_config_path,
        build_script_path=build_script_path,
        local_report_paths=local_report_paths,
        expected_count=expected_count,
        feature_cols=feature_cols,
        git_head=git_head,
        staged_names=staged_names,
        scoped_status_lines=scoped_status_lines,
        generated_at_utc=generated_at_utc,
    )
    proof_failures = [check for check in proof_report["checks"] if check["status"] == "FAIL"]
    non_coverage_proof_failures = [
        check for check in proof_failures if check["name"] != "canonical_markets_covered_by_convention_evidence"
    ]
    uncovered_markets = [str(market) for market in proof_report.get("missing_markets", [])]
    start = _utc_ts(proof_gate.EXPECTED_ACCESS_WINDOW["start"])
    end = _utc_ts(proof_gate.EXPECTED_ACCESS_WINDOW["end"])

    by_market: dict[str, dict[str, Any]] = {}
    schema_failures: list[str] = []
    for market in uncovered_markets:
        by_schema: dict[str, Any] = {}
        for schema in SCHEMAS_TO_INVENTORY:
            row = _inventory_schema_market(
                repo_root=repo_root,
                dbn_root=dbn_root,
                schema=schema,
                market=market,
                start=start,
                end=end,
            )
            by_schema[schema] = row
            schema_failures.extend(row["failures"])
        by_market[market] = {
            "status": "PASS" if all(row["status"] == "PASS" for row in by_schema.values()) else "FAIL",
            "schemas": by_schema,
        }

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="proof_gate_usable_for_uncovered_markets",
        passed=not non_coverage_proof_failures and bool(uncovered_markets),
        observed={
            "proof_status": proof_report["summary"]["status"],
            "non_coverage_failures": [check["name"] for check in non_coverage_proof_failures],
            "uncovered_market_count": len(uncovered_markets),
        },
        expected={"non_coverage_failures": [], "uncovered_market_count": ">0"},
        detail="Inventory is valid only when proof gate no-go is attributable to uncovered markets.",
    )
    _check(
        checks,
        name="archive_metadata_coverage_complete",
        passed=not schema_failures,
        observed=schema_failures[:100],
        expected=[],
        detail="Every uncovered market must have manifest-valid OHLCV, definition, and trades archive coverage.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_READY if not failures else STATUS_NO_GO
    return {
        "summary": {
            "stage": "phase2_local_trade_archive_coverage_inventory",
            "generated_at_utc": generated_at_utc or scope_gate.utc_now(),
            "status": status,
            "approved_scope": "promoted canonical broad_manifest_527_rebuild_v1 460-row Phase 2 only",
            "access_window": dict(proof_gate.EXPECTED_ACCESS_WINDOW),
            "schemas": list(SCHEMAS_TO_INVENTORY),
            "canonical_market_count": proof_report["summary"]["canonical_market_count"],
            "covered_market_count": proof_report["summary"]["covered_market_count"],
            "uncovered_market_count": len(uncovered_markets),
            "schema_failure_count": len(schema_failures),
            "proof_gate_status": proof_report["summary"]["status"],
            "dbn_payload_rows_scanned": False,
            "provider_download_performed": False,
            "reports_refreshed": False,
            "data_mutation_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "live_or_paper_execution_approved": False,
            "failure_count": len(failures),
        },
        "checks": checks,
        "uncovered_markets": uncovered_markets,
        "covered_markets": proof_report.get("covered_markets", []),
        "by_market": by_market,
    }


def render_console(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "phase2_local_trade_archive_coverage_inventory "
        f"status={summary['status']} "
        f"uncovered_markets={summary['uncovered_market_count']} "
        f"schema_failure_count={summary['schema_failure_count']} "
        f"failure_count={summary['failure_count']}",
    ]
    for check in report["checks"]:
        if check["status"] == "FAIL":
            lines.append(
                f"FAIL {check['name']}: observed={check['observed']!r} expected={check['expected']!r}"
            )
    if summary["schema_failure_count"]:
        for market, row in report["by_market"].items():
            if row["status"] == "PASS":
                continue
            for schema, schema_row in row["schemas"].items():
                if schema_row["status"] == "FAIL":
                    lines.append(
                        f"FAIL {market} {schema}: failures={schema_row['failures'][:5]!r}"
                    )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--dbn-root", default=str(REPO_ROOT / "data/dbn"))
    parser.add_argument("--data-manifest", default=str(scope_gate.DEFAULT_DATA_MANIFEST))
    parser.add_argument("--canonical-root", default=str(scope_gate.DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--reports-root", default=str(scope_gate.DEFAULT_REPORTS_ROOT))
    parser.add_argument("--phase2-manifest", default=str(scope_gate.DEFAULT_PHASE2_MANIFEST))
    parser.add_argument("--phase2-validation", default=str(scope_gate.DEFAULT_PHASE2_VALIDATION))
    parser.add_argument("--profile-config", default=str(scope_gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--build-script", default=str(scope_gate.DEFAULT_BUILD_SCRIPT))
    parser.add_argument("--local-trade-report", action="append", default=None)
    parser.add_argument("--expected-count", type=int, default=scope_gate.EXPECTED_CANONICAL_COUNT)
    parser.add_argument("--json", action="store_true", help="Print the read-only inventory JSON to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    local_report_paths = [
        scope_gate.resolve_path(repo_root, path)
        for path in (args.local_trade_report or [str(proof_gate.DEFAULT_LOCAL_TRADE_REPORT)])
    ]
    report = evaluate_inventory(
        repo_root=repo_root,
        dbn_root=scope_gate.resolve_path(repo_root, args.dbn_root),
        data_manifest_path=scope_gate.resolve_path(repo_root, args.data_manifest),
        canonical_root=scope_gate.resolve_path(repo_root, args.canonical_root),
        reports_root=scope_gate.resolve_path(repo_root, args.reports_root),
        phase2_manifest_path=scope_gate.resolve_path(repo_root, args.phase2_manifest),
        phase2_validation_path=scope_gate.resolve_path(repo_root, args.phase2_validation),
        profile_config_path=scope_gate.resolve_path(repo_root, args.profile_config),
        build_script_path=scope_gate.resolve_path(repo_root, args.build_script),
        local_report_paths=local_report_paths,
        expected_count=args.expected_count,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_console(report))
    return 0 if report["summary"]["status"] == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
