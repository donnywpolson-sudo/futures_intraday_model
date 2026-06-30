#!/usr/bin/env python3
"""Read-only reconciliation of 2025/2026 causal inputs for local trade proof."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import check_phase2_local_trade_ohlcv_gap_proof as proof_gate


STATUS_READY = "READY_FOR_BOUNDED_PROOF_SCAN_WITH_CAUSAL_ROOT"
STATUS_MISSING = "NO_GO_LOCAL_TRADE_CAUSAL_INPUTS_MISSING"
STATUS_AMBIGUOUS = "NO_GO_LOCAL_TRADE_CAUSAL_INPUTS_AMBIGUOUS"

DEFAULT_PROOF_CAUSAL_ROOT = REPO_ROOT / "data/causally_gated_normalized"
DEFAULT_CANDIDATE_ROOTS = (DEFAULT_PROOF_CAUSAL_ROOT, scope_gate.DEFAULT_CANONICAL_ROOT)
PROOF_YEARS = (2025, 2026)
TIMESTAMP_COLUMNS = ("ts", "ts_event", "datetime", "datetime_utc", "timestamp", "time")
REQUIRED_CAUSAL_COLUMNS = ("is_synthetic",)
OPTIONAL_GAP_COLUMNS = ("synthetic_gap_id", "synthetic_gap_size_minutes")


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


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _expected_pairs(markets: Iterable[str], years: Iterable[int] = PROOF_YEARS) -> list[tuple[str, int]]:
    return [(market, year) for market in sorted(str(item) for item in markets) for year in years]


def _read_parquet_metadata(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        parquet = pq.ParquetFile(path)
    except Exception as exc:
        return None, [f"unreadable parquet metadata: {type(exc).__name__}: {exc}"]
    return {
        "row_count": int(parquet.metadata.num_rows),
        "columns": list(parquet.schema_arrow.names),
    }, []


def _schema_failures(columns: list[str]) -> list[str]:
    failures: list[str] = []
    for column in REQUIRED_CAUSAL_COLUMNS:
        if column not in columns:
            failures.append(f"missing required column: {column}")
    if not any(column in columns for column in TIMESTAMP_COLUMNS):
        failures.append("missing timestamp column")
    return failures


def _root_summary(
    *,
    repo_root: Path,
    root: Path,
    expected_pairs: list[tuple[str, int]],
) -> dict[str, Any]:
    missing_files: list[str] = []
    unreadable_files: list[dict[str, Any]] = []
    schema_failures: list[dict[str, Any]] = []
    optional_schema_warnings: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []

    for market, year in expected_pairs:
        path = root / market / f"{year}.parquet"
        rel_path = scope_gate.rel(path, repo_root)
        if not path.exists():
            missing_files.append(rel_path)
            continue
        metadata, failures = _read_parquet_metadata(path)
        if metadata is None:
            unreadable_files.append({"path": rel_path, "failures": failures})
            continue
        columns = [str(column) for column in metadata["columns"]]
        failures = _schema_failures(columns)
        missing_optional = [column for column in OPTIONAL_GAP_COLUMNS if column not in columns]
        if failures:
            schema_failures.append({"path": rel_path, "failures": failures})
        if missing_optional:
            optional_schema_warnings.append({"path": rel_path, "missing_optional_columns": missing_optional})
        files.append(
            {
                "market": market,
                "year": year,
                "path": rel_path,
                "row_count": metadata["row_count"],
                "columns": columns,
            }
        )

    status = "PASS" if not missing_files and not unreadable_files and not schema_failures else "FAIL"
    return {
        "root": scope_gate.rel(root, repo_root),
        "status": status,
        "expected_file_count": len(expected_pairs),
        "existing_file_count": len(files),
        "missing_file_count": len(missing_files),
        "unreadable_file_count": len(unreadable_files),
        "schema_failure_count": len(schema_failures),
        "optional_schema_warning_count": len(optional_schema_warnings),
        "missing_files": missing_files,
        "unreadable_files": unreadable_files,
        "schema_failures": schema_failures,
        "optional_schema_warnings": optional_schema_warnings,
        "files": files,
    }


def evaluate_reconciliation(
    *,
    repo_root: Path,
    data_manifest_path: Path,
    canonical_root: Path,
    reports_root: Path,
    phase2_manifest_path: Path,
    phase2_validation_path: Path,
    profile_config_path: Path,
    build_script_path: Path,
    local_report_paths: list[Path],
    candidate_roots: list[Path],
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
    non_coverage_failures = [
        check for check in proof_failures if check["name"] != "canonical_markets_covered_by_convention_evidence"
    ]
    uncovered_markets = [str(market) for market in proof_report.get("missing_markets", [])]
    expected_pairs = _expected_pairs(uncovered_markets)
    root_reports = [
        _root_summary(repo_root=repo_root, root=root, expected_pairs=expected_pairs)
        for root in _dedupe_paths(candidate_roots)
    ]
    usable_roots = [row["root"] for row in root_reports if row["status"] == "PASS"]

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="proof_gate_usable_for_uncovered_markets",
        passed=not non_coverage_failures and bool(uncovered_markets),
        observed={
            "proof_status": proof_report["summary"]["status"],
            "non_coverage_failures": [check["name"] for check in non_coverage_failures],
            "uncovered_market_count": len(uncovered_markets),
        },
        expected={"non_coverage_failures": [], "uncovered_market_count": ">0"},
        detail="Reconciliation is valid only when the proof no-go is attributable to uncovered markets.",
    )
    _check(
        checks,
        name="candidate_causal_roots_checked",
        passed=bool(root_reports),
        observed=[row["root"] for row in root_reports],
        expected="at least one candidate causal root",
        detail="At least one causal root must be checked before planning a proof scan.",
    )
    _check(
        checks,
        name="usable_causal_root_exists",
        passed=bool(usable_roots),
        observed=usable_roots,
        expected="one usable root with all required 2025/2026 causal inputs",
        detail="A future bounded proof scan needs complete local causal parquet inputs for the uncovered markets.",
    )
    _check(
        checks,
        name="usable_causal_root_unambiguous",
        passed=len(usable_roots) <= 1,
        observed=usable_roots,
        expected="zero or one usable root",
        detail="Multiple usable roots require a human root-selection decision before any proof scan.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    if len(usable_roots) > 1:
        status = STATUS_AMBIGUOUS
    elif len(usable_roots) == 1 and not failures:
        status = STATUS_READY
    else:
        status = STATUS_MISSING

    return {
        "summary": {
            "stage": "phase2_local_trade_causal_input_reconciliation",
            "generated_at_utc": generated_at_utc or scope_gate.utc_now(),
            "status": status,
            "approved_scope": "promoted canonical broad_manifest_527_rebuild_v1 460-row Phase 2 only",
            "proof_years": list(PROOF_YEARS),
            "uncovered_market_count": len(uncovered_markets),
            "expected_causal_file_count": len(expected_pairs),
            "candidate_root_count": len(root_reports),
            "usable_root_count": len(usable_roots),
            "total_missing_file_count": sum(int(row["missing_file_count"]) for row in root_reports),
            "total_schema_failure_count": sum(int(row["schema_failure_count"]) for row in root_reports),
            "proof_gate_status": proof_report["summary"]["status"],
            "parquet_metadata_only": True,
            "parquet_rows_scanned": False,
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
        "expected_pairs": [{"market": market, "year": year} for market, year in expected_pairs],
        "candidate_roots": root_reports,
        "usable_roots": usable_roots,
    }


def render_console(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "phase2_local_trade_causal_input_reconciliation "
        f"status={summary['status']} "
        f"uncovered_markets={summary['uncovered_market_count']} "
        f"expected_causal_files={summary['expected_causal_file_count']} "
        f"candidate_roots={summary['candidate_root_count']} "
        f"usable_roots={summary['usable_root_count']} "
        f"missing_files={summary['total_missing_file_count']} "
        f"schema_failures={summary['total_schema_failure_count']} "
        f"failure_count={summary['failure_count']}",
    ]
    for check in report["checks"]:
        if check["status"] == "FAIL":
            lines.append(
                f"FAIL {check['name']}: observed={check['observed']!r} expected={check['expected']!r}"
            )
    for row in report["candidate_roots"]:
        lines.append(
            "ROOT {root} status={status} existing={existing}/{expected} "
            "missing={missing} unreadable={unreadable} schema_failures={schema_failures}".format(
                root=row["root"],
                status=row["status"],
                existing=row["existing_file_count"],
                expected=row["expected_file_count"],
                missing=row["missing_file_count"],
                unreadable=row["unreadable_file_count"],
                schema_failures=row["schema_failure_count"],
            )
        )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--data-manifest", default=str(scope_gate.DEFAULT_DATA_MANIFEST))
    parser.add_argument("--canonical-root", default=str(scope_gate.DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--reports-root", default=str(scope_gate.DEFAULT_REPORTS_ROOT))
    parser.add_argument("--phase2-manifest", default=str(scope_gate.DEFAULT_PHASE2_MANIFEST))
    parser.add_argument("--phase2-validation", default=str(scope_gate.DEFAULT_PHASE2_VALIDATION))
    parser.add_argument("--profile-config", default=str(scope_gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--build-script", default=str(scope_gate.DEFAULT_BUILD_SCRIPT))
    parser.add_argument("--local-trade-report", action="append", default=None)
    parser.add_argument("--candidate-root", action="append", default=None)
    parser.add_argument("--expected-count", type=int, default=scope_gate.EXPECTED_CANONICAL_COUNT)
    parser.add_argument("--json", action="store_true", help="Print the read-only reconciliation JSON to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    local_report_paths = [
        scope_gate.resolve_path(repo_root, path)
        for path in (args.local_trade_report or [str(proof_gate.DEFAULT_LOCAL_TRADE_REPORT)])
    ]
    candidate_roots = [
        scope_gate.resolve_path(repo_root, path)
        for path in [*(str(path) for path in DEFAULT_CANDIDATE_ROOTS), *(args.candidate_root or [])]
    ]
    report = evaluate_reconciliation(
        repo_root=repo_root,
        data_manifest_path=scope_gate.resolve_path(repo_root, args.data_manifest),
        canonical_root=scope_gate.resolve_path(repo_root, args.canonical_root),
        reports_root=scope_gate.resolve_path(repo_root, args.reports_root),
        phase2_manifest_path=scope_gate.resolve_path(repo_root, args.phase2_manifest),
        phase2_validation_path=scope_gate.resolve_path(repo_root, args.phase2_validation),
        profile_config_path=scope_gate.resolve_path(repo_root, args.profile_config),
        build_script_path=scope_gate.resolve_path(repo_root, args.build_script),
        local_report_paths=local_report_paths,
        candidate_roots=candidate_roots,
        expected_count=args.expected_count,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_console(report))
    return 0 if report["summary"]["status"] == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
