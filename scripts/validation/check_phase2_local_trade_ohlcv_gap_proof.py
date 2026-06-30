#!/usr/bin/env python3
"""Read-only local trade/OHLCV convention proof gate for Phase 2 460 scope."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import check_phase2_manifest_trust as trust_gate


STATUS_GO = "CONDITIONAL_GO_LOCAL_TRADE_CONVENTION_PROOF_460_ONLY"
STATUS_NO_GO = "NO_GO_LOCAL_TRADE_OHLCV_GAP_PROOF"
WARN_CONVENTION_ONLY = "WARN_CONVENTION_BACKED_NOT_DIRECT_HISTORICAL_PROOF"

DEFAULT_LOCAL_TRADE_REPORT = (
    REPO_ROOT
    / "reports/pipeline_audit/local_trade_ohlcv_gap_crosscheck_tier1_access_window_repaired_20250618_20260613.json"
)
EXPECTED_ACCESS_WINDOW = {
    "start": "2025-06-18T00:00:00Z",
    "end": "2026-06-13T00:00:00Z",
}
EXPECTED_DBN_ROOT = "data/dbn"
EXPECTED_RAW_ROOT = "data/raw"
ALLOWED_CONVENTION_CAUSAL_ROOTS = {"data/causally_gated_normalized"}
FAILED_CLASSIFICATIONS = {
    "trade_activity_inside_ohlcv_gap",
    "unverified_missing_trade_coverage",
    "unverified_unresolved_contract_context",
}
CAVEAT_TERMS = ("not direct", "outside the access window")


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


def _warn(
    warnings: list[dict[str, Any]],
    *,
    name: str,
    code: str,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    warnings.append(
        {
            "name": name,
            "code": code,
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _canonical_markets(manifest: dict[str, Any]) -> set[str]:
    markets: set[str] = set()
    outputs = manifest.get("outputs")
    if isinstance(outputs, list):
        for output in outputs:
            if isinstance(output, dict) and isinstance(output.get("market"), str):
                markets.add(str(output["market"]))
    return markets


def _report_market_years(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("market_years")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _report_markets(report: dict[str, Any]) -> set[str]:
    return {
        str(row["market"])
        for row in _report_market_years(report)
        if isinstance(row.get("market"), str)
    }


def _window_matches(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return value.get("start") == EXPECTED_ACCESS_WINDOW["start"] and value.get("end") == EXPECTED_ACCESS_WINDOW["end"]


def _has_required_caveat(report: dict[str, Any]) -> bool:
    caveat = str(report.get("caveat", "")).lower()
    return all(term in caveat for term in CAVEAT_TERMS)


def _summary_has_no_failed_unverified_minutes(report: dict[str, Any]) -> bool:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return _as_int(summary.get("failed_minutes")) == 0 and _as_int(summary.get("unverified_minutes")) == 0


def _bad_entry_summaries(report: dict[str, Any]) -> list[dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    for row in _report_market_years(report):
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        classifications = row.get("classification_counts") if isinstance(row.get("classification_counts"), dict) else {}
        failed_classifications = sorted(
            key
            for key, count in classifications.items()
            if _as_int(count) > 0 and str(key) in FAILED_CLASSIFICATIONS
        )
        if (
            row.get("status") != "PASS"
            or _as_int(summary.get("failed_minutes")) > 0
            or _as_int(summary.get("unverified_minutes")) > 0
            or failed_classifications
        ):
            bad.append(
                {
                    "market": row.get("market"),
                    "year": row.get("year"),
                    "status": row.get("status"),
                    "failed_minutes": summary.get("failed_minutes"),
                    "unverified_minutes": summary.get("unverified_minutes"),
                    "failed_classifications": failed_classifications,
                }
            )
    return bad


def _report_roots_match(report: dict[str, Any]) -> bool:
    return (
        report.get("dbn_root") == EXPECTED_DBN_ROOT
        and report.get("raw_root") == EXPECTED_RAW_ROOT
        and report.get("causal_root") in ALLOWED_CONVENTION_CAUSAL_ROOTS
    )


def _eligible_report(report: dict[str, Any]) -> bool:
    return (
        report.get("status") == "PASS"
        and not report.get("failures")
        and _window_matches(report.get("local_trades_schema_access"))
        and _window_matches(report.get("window"))
        and _report_roots_match(report)
        and _has_required_caveat(report)
        and _summary_has_no_failed_unverified_minutes(report)
        and not _bad_entry_summaries(report)
    )


def _report_path(path: Path, repo_root: Path) -> str:
    return scope_gate.rel(path, repo_root)


def evaluate_gap_proof(
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
    expected_count: int = scope_gate.EXPECTED_CANONICAL_COUNT,
    feature_cols: Iterable[str] | None = None,
    git_head: str | None = None,
    staged_names: list[str] | None = None,
    scoped_status_lines: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    phase2_manifest = scope_gate.read_json(phase2_manifest_path)
    trust_report = trust_gate.evaluate_trust(
        repo_root=repo_root,
        data_manifest_path=data_manifest_path,
        canonical_root=canonical_root,
        reports_root=reports_root,
        phase2_manifest_path=phase2_manifest_path,
        phase2_validation_path=phase2_validation_path,
        profile_config_path=profile_config_path,
        build_script_path=build_script_path,
        expected_count=expected_count,
        feature_cols=feature_cols,
        git_head=git_head,
        staged_names=staged_names,
        scoped_status_lines=scoped_status_lines,
        generated_at_utc=generated_at_utc,
    )
    canonical_markets = _canonical_markets(phase2_manifest)

    loaded_reports: list[tuple[Path, dict[str, Any]]] = []
    missing_reports: list[str] = []
    unreadable_reports: list[dict[str, str]] = []
    for path in local_report_paths:
        resolved = scope_gate.resolve_path(repo_root, path)
        if not resolved.exists():
            missing_reports.append(_report_path(resolved, repo_root))
            continue
        try:
            loaded_reports.append((resolved, _read_json(resolved)))
        except Exception as exc:
            unreadable_reports.append(
                {
                    "path": _report_path(resolved, repo_root),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    non_pass_reports = [
        {"path": _report_path(path, repo_root), "status": report.get("status")}
        for path, report in loaded_reports
        if report.get("status") != "PASS"
    ]
    reports_with_failures = [
        {"path": _report_path(path, repo_root), "failures": report.get("failures")}
        for path, report in loaded_reports
        if report.get("failures")
    ]
    bad_windows = [
        {
            "path": _report_path(path, repo_root),
            "window": report.get("window"),
            "local_trades_schema_access": report.get("local_trades_schema_access"),
        }
        for path, report in loaded_reports
        if not _window_matches(report.get("window"))
        or not _window_matches(report.get("local_trades_schema_access"))
    ]
    bad_roots = [
        {
            "path": _report_path(path, repo_root),
            "dbn_root": report.get("dbn_root"),
            "raw_root": report.get("raw_root"),
            "causal_root": report.get("causal_root"),
        }
        for path, report in loaded_reports
        if not _report_roots_match(report)
    ]
    missing_caveats = [
        _report_path(path, repo_root)
        for path, report in loaded_reports
        if not _has_required_caveat(report)
    ]
    bad_summary_reports = [
        {
            "path": _report_path(path, repo_root),
            "summary": report.get("summary"),
        }
        for path, report in loaded_reports
        if not _summary_has_no_failed_unverified_minutes(report)
    ]
    bad_entries = [
        {
            "path": _report_path(path, repo_root),
            "entries": _bad_entry_summaries(report)[:20],
        }
        for path, report in loaded_reports
        if _bad_entry_summaries(report)
    ]
    eligible_reports = [
        (path, report)
        for path, report in loaded_reports
        if _eligible_report(report)
    ]
    covered_markets: set[str] = set()
    for _, report in eligible_reports:
        covered_markets.update(_report_markets(report))
    missing_markets = sorted(canonical_markets - covered_markets)

    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    _check(
        checks,
        name="manifest_trust_gate_passed",
        passed=trust_report["summary"]["status"] == trust_gate.STATUS_GO,
        observed=trust_report["summary"]["status"],
        expected=trust_gate.STATUS_GO,
        detail="Local trade/OHLCV proof can only be evaluated against a trusted current 460-row baseline.",
    )
    _check(
        checks,
        name="local_trade_reports_present",
        passed=not missing_reports and not unreadable_reports and bool(loaded_reports),
        observed={"missing": missing_reports, "unreadable": unreadable_reports, "loaded": len(loaded_reports)},
        expected={"missing": [], "unreadable": [], "loaded": ">0"},
        detail="Selected local trade/OHLCV convention report files must be readable.",
    )
    _check(
        checks,
        name="local_trade_reports_status_pass",
        passed=not non_pass_reports,
        observed=non_pass_reports,
        expected=[],
        detail="Selected local trade/OHLCV reports must have status PASS.",
    )
    _check(
        checks,
        name="local_trade_reports_no_failures",
        passed=not reports_with_failures,
        observed=reports_with_failures,
        expected=[],
        detail="Selected local trade/OHLCV reports must not contain report-level failures.",
    )
    _check(
        checks,
        name="local_trade_access_window_matches",
        passed=not bad_windows,
        observed=bad_windows,
        expected=EXPECTED_ACCESS_WINDOW,
        detail="Evidence must use the configured local trades access window.",
    )
    _check(
        checks,
        name="local_trade_report_roots_expected",
        passed=not bad_roots,
        observed=bad_roots,
        expected={
            "dbn_root": EXPECTED_DBN_ROOT,
            "raw_root": EXPECTED_RAW_ROOT,
            "causal_root": sorted(ALLOWED_CONVENTION_CAUSAL_ROOTS),
        },
        detail="Convention evidence must come from the expected local trade proof roots.",
    )
    _check(
        checks,
        name="local_trade_caveat_preserves_non_direct_proof",
        passed=not missing_caveats,
        observed=missing_caveats,
        expected=f"caveat contains {CAVEAT_TERMS}",
        detail="Reports must explicitly say this is not direct trades proof outside the access window.",
    )
    _check(
        checks,
        name="local_trade_reports_no_failed_unverified_minutes",
        passed=not bad_summary_reports,
        observed=bad_summary_reports,
        expected=[],
        detail="Report summaries must not contain failed or unverified missing OHLCV minutes.",
    )
    _check(
        checks,
        name="local_trade_report_entries_pass",
        passed=not bad_entries,
        observed=bad_entries,
        expected=[],
        detail="Market-year rows must not contain failed status, failed minutes, unverified minutes, or failed classifications.",
    )
    _check(
        checks,
        name="canonical_markets_covered_by_convention_evidence",
        passed=not missing_markets,
        observed=missing_markets,
        expected=[],
        detail="Every canonical 460-scope market must be covered by eligible local trade/OHLCV convention evidence.",
    )
    _warn(
        warnings,
        name="proof_is_convention_backed",
        code=WARN_CONVENTION_ONLY,
        observed=EXPECTED_ACCESS_WINDOW,
        expected="do not claim direct historical trades proof for 2010-2024",
        detail="Local trades access-window evidence is convention-backed proof only for the 2010-2024 canonical scope.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_GO if not failures else STATUS_NO_GO
    return {
        "summary": {
            "stage": "phase2_local_trade_ohlcv_gap_proof",
            "generated_at_utc": generated_at_utc or scope_gate.utc_now(),
            "status": status,
            "approved_scope": "promoted canonical broad_manifest_527_rebuild_v1 460-row Phase 2 only",
            "expected_count": expected_count,
            "canonical_market_count": len(canonical_markets),
            "covered_market_count": len(covered_markets),
            "missing_market_count": len(missing_markets),
            "loaded_report_count": len(loaded_reports),
            "eligible_report_count": len(eligible_reports),
            "manifest_trust_status": trust_report["summary"]["status"],
            "direct_historical_trade_proof_claimed": False,
            "convention_backed_only": True,
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "data_mutation_performed": False,
            "reports_refreshed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "live_or_paper_execution_approved": False,
        },
        "checks": checks,
        "warnings": warnings,
        "local_report_paths": [_report_path(path, repo_root) for path, _ in loaded_reports],
        "eligible_report_paths": [_report_path(path, repo_root) for path, _ in eligible_reports],
        "canonical_markets": sorted(canonical_markets),
        "covered_markets": sorted(covered_markets),
        "missing_markets": missing_markets,
    }


def render_console(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "phase2_local_trade_ohlcv_gap_proof "
        f"status={summary['status']} "
        f"canonical_markets={summary['canonical_market_count']} "
        f"covered_markets={summary['covered_market_count']} "
        f"missing_markets={summary['missing_market_count']} "
        f"failure_count={summary['failure_count']} "
        f"warning_count={summary['warning_count']}",
    ]
    for check in report["checks"]:
        if check["status"] == "FAIL":
            lines.append(
                f"FAIL {check['name']}: observed={check['observed']!r} expected={check['expected']!r}"
            )
    for warning in report["warnings"]:
        lines.append(
            f"WARN {warning['name']} {warning['code']}: "
            f"observed={warning['observed']!r} expected={warning['expected']!r}"
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
    parser.add_argument("--expected-count", type=int, default=scope_gate.EXPECTED_CANONICAL_COUNT)
    parser.add_argument("--json", action="store_true", help="Print the read-only report JSON to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    local_report_paths = [
        scope_gate.resolve_path(repo_root, path)
        for path in (args.local_trade_report or [str(DEFAULT_LOCAL_TRADE_REPORT)])
    ]
    report = evaluate_gap_proof(
        repo_root=repo_root,
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
    return 0 if report["summary"]["status"] == STATUS_GO else 1


if __name__ == "__main__":
    raise SystemExit(main())
