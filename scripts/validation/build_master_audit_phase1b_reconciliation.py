#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 1B reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run
Phase 1B conversion, raw/DBN alignment audits, Phase 2 readiness/build, WFA,
modeling, predictions, parquet reads, provider/network calls, promotion,
freeze, holdout, paper/live, cleanup, staging, commit, or push.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_phase1b_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_MARKET_YEAR_COUNT = 8

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_PHASE6 = Path(
    "reports/master_audit/master_audit_phase6_reconciliation_20260709/"
    "master_audit_phase6_reconciliation.json"
)
DEFAULT_PHASE7 = Path(
    "reports/master_audit/master_audit_phase7_reconciliation_20260709/"
    "master_audit_phase7_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase1b_reconciliation_20260709")
REPORT_JSON = "master_audit_phase1b_reconciliation.json"
REPORT_MD = "master_audit_phase1b_reconciliation.md"

PHASE1AB_ROOT = Path(
    "reports/data_audit/current_state/"
    "phase1ab_33markets_2010_2026_post_status_placement_refresh_20260706_rerun1"
)
PHASE1AB_SUMMARY = PHASE1AB_ROOT / "phase1ab_post_status_placement_refresh_summary.json"
BROAD_ALIGNMENT = PHASE1AB_ROOT / "phase1b_raw_dbn_alignment.json"
MARKET_ALIGNMENT_ROOT = PHASE1AB_ROOT / "phase1b_market_batches_expected_only"

REQUIRED_BASE_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "phase6_reconciliation": DEFAULT_PHASE6,
    "phase7_reconciliation": DEFAULT_PHASE7,
    "phase1ab_summary": PHASE1AB_SUMMARY,
    "broad_alignment": BROAD_ALIGNMENT,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase1b_conversion_executed": False,
    "raw_dbn_alignment_audit_executed": False,
    "phase2_readiness_or_build_executed": False,
    "data_model_commands_executed": False,
    "dbn_read_executed": False,
    "raw_parquet_read_executed": False,
    "causal_parquet_read_executed": False,
    "feature_parquet_read_executed": False,
    "prediction_parquet_read_executed": False,
    "wfa_modeling_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "freeze_executed": False,
    "holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "staging_commit_push_executed": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def market_alignment_path(market: str) -> Path:
    return MARKET_ALIGNMENT_ROOT / f"{market}_alignment.json"


def market_include_path(market: str) -> Path:
    return MARKET_ALIGNMENT_ROOT / f"{market}_include.json"


def required_inputs() -> dict[str, Path]:
    paths = dict(REQUIRED_BASE_INPUTS)
    for market in EXPECTED_MARKETS:
        paths[f"{market}_alignment"] = market_alignment_path(market)
        paths[f"{market}_include"] = market_include_path(market)
    return paths


def check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    failure: str,
    evidence: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "failure": None if passed else failure,
            "evidence": list(evidence),
            "details": dict(details or {}),
        }
    )
    if not passed:
        failures.append(failure)


def required_input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields = {
        "run_status": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
        },
        "overview": {"status": "status", "failure_count": "summary.failure_count"},
        "phase6_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase6_master_audit_status": "summary.phase6_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase7_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase7_master_audit_status": "summary.phase7_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase1ab_summary": {
            "status": "status",
            "phase1b_status": "phase1b.status",
            "phase1b_mode": "phase1b.mode",
            "fail_market_reports": "phase1b.summary_counts.fail_market_reports",
            "missing_report_count": "phase1b.summary_counts.missing_report_count",
        },
        "broad_alignment": {"status": "status"},
    }
    for market in EXPECTED_MARKETS:
        json_fields[f"{market}_alignment"] = {
            "status": "status",
            "expected_only": "expected_only",
            "expected_market_year_count": "expected_market_year_count",
            "raw_market_year_count": "raw_market_year_count",
            "source_hash_mismatch_count": "source_hash_mismatch_count",
            "raw_schema_failure_count": "raw_schema_failure_count",
            "definition_join_mismatch_count": "definition_join_mismatch_count",
        }
        json_fields[f"{market}_include"] = {"market": "market", "source": "source"}
    return [
        inventory.evidence_file(
            repo_root=repo_root,
            relative_path=relative_path,
            json_fields=json_fields.get(name),
            dirty_map=dirty_map,
        )
        for name, relative_path in paths.items()
    ]


def load_payloads(
    *,
    repo_root: Path,
    paths: Mapping[str, Path],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    payloads: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, path in paths.items():
        resolved = resolve_path(repo_root, path)
        if resolved.suffix.lower() != ".json":
            continue
        payload, error = read_json_object(resolved)
        if error:
            failures.append(f"required JSON input unavailable: {path.as_posix()} ({error})")
        elif payload is not None:
            payloads[name] = payload
    return payloads, failures


def row_by_area(run_status: Mapping[str, Any] | None, area: str) -> Mapping[str, Any] | None:
    rows = dotted_get(run_status, "run_status_table")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("audit_area") == area:
            return row
    return None


def include_market_years(payload: Mapping[str, Any] | None) -> set[tuple[str, int]]:
    if not isinstance(payload, Mapping):
        return set()
    rows = payload.get("market_years")
    if not isinstance(rows, list):
        rows = [payload]
    result: set[tuple[str, int]] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        market = row.get("market")
        year = row.get("year")
        if isinstance(market, str) and isinstance(year, int):
            result.add((market, year))
    return result


def scoped_raw_metric_years(payload: Mapping[str, Any] | None) -> set[int]:
    if not isinstance(payload, Mapping):
        return set()
    rows = payload.get("raw_file_metrics")
    if not isinstance(rows, list):
        return set()
    years: set[int] = set()
    for row in rows:
        if isinstance(row, Mapping) and isinstance(row.get("year"), int):
            years.add(row["year"])
    return years


def market_alignment_pass(payload: Mapping[str, Any] | None, market: str) -> tuple[bool, dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return False, {"market": market, "reason": "payload missing"}
    details = {
        "market": market,
        "status": payload.get("status"),
        "profile": payload.get("profile"),
        "resolved_profile": payload.get("resolved_profile"),
        "expected_only": payload.get("expected_only"),
        "market_year_include_list_applied": payload.get("market_year_include_list_applied"),
        "expected_market_year_count": payload.get("expected_market_year_count"),
        "raw_market_year_count": payload.get("raw_market_year_count"),
        "ohlcv_dbn_market_year_count": payload.get("ohlcv_dbn_market_year_count"),
        "definition_dbn_market_year_count": payload.get("definition_dbn_market_year_count"),
        "status_dbn_market_year_count": payload.get("status_dbn_market_year_count"),
        "statistics_dbn_market_year_count": payload.get("statistics_dbn_market_year_count"),
        "missing_raw_count": payload.get("missing_raw_count"),
        "missing_ohlcv_dbn_count": payload.get("missing_ohlcv_dbn_count"),
        "missing_definition_dbn_count": payload.get("missing_definition_dbn_count"),
        "source_hash_mismatch_count": payload.get("source_hash_mismatch_count"),
        "raw_schema_failure_count": payload.get("raw_schema_failure_count"),
        "definition_join_status": payload.get("definition_join_status"),
        "definition_join_mismatch_count": payload.get("definition_join_mismatch_count"),
        "invalid_manifest_count": payload.get("invalid_manifest_count"),
        "repair_manifest_status": payload.get("repair_manifest_status"),
        "repair_manifest_failure_count": payload.get("repair_manifest_failure_count"),
        "failures_count": len(as_list(payload.get("failures"))),
        "scoped_raw_metric_years": sorted(scoped_raw_metric_years(payload) & set(EXPECTED_YEARS)),
    }
    passed = (
        payload.get("status") == "PASS"
        and payload.get("expected_only") is True
        and payload.get("market_year_include_list_applied") is True
        and payload.get("missing_raw_count") == 0
        and payload.get("missing_ohlcv_dbn_count") == 0
        and payload.get("missing_definition_dbn_count") == 0
        and payload.get("source_hash_mismatch_count") == 0
        and payload.get("raw_schema_failure_count") == 0
        and payload.get("definition_join_status") == "checked"
        and payload.get("definition_join_mismatch_count") == 0
        and payload.get("invalid_manifest_count") == 0
        and payload.get("repair_manifest_status") == "PASS"
        and payload.get("repair_manifest_failure_count") == 0
        and len(as_list(payload.get("failures"))) == 0
    )
    return passed, details


def build_checks(
    *,
    payloads: Mapping[str, Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    output_rel: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    paths = required_inputs()
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {str(item.get("path")) for item in evidence if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required Phase 1B reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 1B reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    phase6 = payloads.get("phase6_reconciliation")
    phase7 = payloads.get("phase7_reconciliation")
    phase1b_row = row_by_area(run_status, "Phase 1B")
    check(
        checks,
        failures,
        name="master_audit_inputs_are_passed_report_only_evidence",
        passed=run_status is not None
        and overview is not None
        and phase6 is not None
        and phase7 is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and phase6.get("status") == "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY"
        and phase7.get("status") == "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        failure="run-status, overview, Phase 6, or Phase 7 input is not passed report-only evidence",
        evidence=[
            DEFAULT_RUN_STATUS.as_posix(),
            DEFAULT_OVERVIEW.as_posix(),
            DEFAULT_PHASE6.as_posix(),
            DEFAULT_PHASE7.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "phase6": None if phase6 is None else phase6.get("status"),
            "phase7": None if phase7 is None else phase7.get("status"),
        },
    )
    check(
        checks,
        failures,
        name="phase1b_previously_not_accepted_in_master_audit_ledger",
        passed=phase1b_row is not None
        and phase1b_row.get("run_status") == "NOT_RUN"
        and phase1b_row.get("detail_status") == "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
        failure="run-status Phase 1B row does not match expected pre-reconciliation NOT_RUN state",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"pre_existing_phase1b_row": dict(phase1b_row or {})},
    )

    summary = payloads.get("phase1ab_summary", {})
    phase1b = summary.get("phase1b")
    phase1b = phase1b if isinstance(phase1b, Mapping) else {}
    counts = phase1b.get("summary_counts")
    counts = counts if isinstance(counts, Mapping) else {}
    check(
        checks,
        failures,
        name="phase1ab_summary_scoped_market_batches_pass",
        passed=summary.get("status") == "PASS"
        and phase1b.get("status") == "PASS"
        and phase1b.get("mode") == "one_market_batches_expected_only"
        and counts.get("missing_report_count") == 0
        and counts.get("fail_market_reports") == 0
        and counts.get("pass_market_reports", 0) >= len(EXPECTED_MARKETS),
        failure="Phase 1AB scoped market-batch summary is not PASS",
        evidence=[PHASE1AB_SUMMARY.as_posix()],
        details={"summary_status": summary.get("status"), "phase1b": dict(phase1b)},
    )

    broad = payloads.get("broad_alignment", {})
    check(
        checks,
        failures,
        name="broad_phase1b_failure_preserved",
        passed=broad.get("status") == "FAIL",
        failure="broad Phase 1B alignment status is not preserved as FAIL",
        evidence=[BROAD_ALIGNMENT.as_posix()],
        details={"broad_status": broad.get("status")},
    )

    market_details: list[dict[str, Any]] = []
    include_details: list[dict[str, Any]] = []
    scoped_pairs: set[tuple[str, int]] = set()
    for market in EXPECTED_MARKETS:
        alignment = payloads.get(f"{market}_alignment")
        passed, details = market_alignment_pass(alignment, market)
        market_details.append(details)
        check(
            checks,
            failures,
            name=f"{market}_alignment_report_passes_scoped_phase1b_checks",
            passed=passed,
            failure=f"{market} Phase 1B alignment report does not pass scoped checks",
            evidence=[market_alignment_path(market).as_posix()],
            details=details,
        )
        include_payload = payloads.get(f"{market}_include")
        include_pairs = include_market_years(include_payload)
        scoped_for_market = {(market, year) for year in EXPECTED_YEARS}
        scoped_pairs.update(include_pairs & scoped_for_market)
        include_detail = {
            "market": market,
            "contains_2023_2024": scoped_for_market.issubset(include_pairs),
            "include_count": len(include_pairs),
            "scoped_pairs_present": sorted([f"{m}:{y}" for m, y in include_pairs & scoped_for_market]),
        }
        include_details.append(include_detail)
        check(
            checks,
            failures,
            name=f"{market}_include_contains_2023_2024",
            passed=scoped_for_market.issubset(include_pairs),
            failure=f"{market} include-list does not contain both 2023 and 2024",
            evidence=[market_include_path(market).as_posix()],
            details=include_detail,
        )

    check(
        checks,
        failures,
        name="scoped_market_year_count_is_exactly_8",
        passed=len(scoped_pairs) == EXPECTED_MARKET_YEAR_COUNT,
        failure=f"scoped Phase 1B market-year count is not {EXPECTED_MARKET_YEAR_COUNT}",
        evidence=[market_include_path(market).as_posix() for market in EXPECTED_MARKETS],
        details={"scoped_pairs": sorted([f"{market}:{year}" for market, year in scoped_pairs])},
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    return checks, failures, {
        "market_alignment_details": market_details,
        "include_details": include_details,
        "scoped_market_year_count": len(scoped_pairs),
        "broad_phase1b_alignment_status": broad.get("status"),
    }


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(payloads: Mapping[str, Mapping[str, Any]], derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "phase1b-001-scoped-active-v2-raw-dbn-evidence-accepted",
            "severity": "Info",
            "finding": "Scoped active v2 Phase 1B raw/DBN evidence is accepted for 6E/CL/ES/ZN 2023/2024 only.",
            "verified_facts": [
                f"scoped_market_year_count={derived.get('scoped_market_year_count')}",
                "Each scoped market alignment report is PASS.",
                "Each scoped market include-list contains 2023 and 2024.",
            ],
            "limitation": "This is not a broad Phase 1B pass and does not run conversion or alignment audits.",
            "evidence_paths": [
                market_alignment_path(market).as_posix() for market in EXPECTED_MARKETS
            ],
        },
        {
            "finding_id": "phase1b-002-broad-phase1b-fail-preserved",
            "severity": "Critical",
            "finding": "Broad Phase 1B alignment remains FAIL and is not upgraded by this reconciliation.",
            "verified_facts": [
                f"broad_phase1b_alignment_status={derived.get('broad_phase1b_alignment_status')}",
            ],
            "limitation": "Any broader Phase 1B claim requires a separate bounded evidence decision.",
            "evidence_paths": [BROAD_ALIGNMENT.as_posix()],
        },
        {
            "finding_id": "phase1b-003-phase2-remains-blocked",
            "severity": "Critical",
            "finding": "Phase 2 remains not accepted by this Phase 1B reconciliation.",
            "verified_facts": [
                "Run-status ledger still records Phase 2 as NOT_RUN in the input evidence.",
            ],
            "limitation": "A separate Phase 2 report-only reconciliation is required before accepting causal/session evidence.",
            "evidence_paths": [DEFAULT_RUN_STATUS.as_posix()],
        },
        {
            "finding_id": "phase1b-004-no-data-or-provider-actions",
            "severity": "Info",
            "finding": "No conversion, alignment audit, provider, parquet read, cleanup, or publication action is authorized.",
            "verified_facts": [
                "All non-approval flags in this report are false.",
            ],
            "limitation": "The report is a ledger reconciliation over existing JSON/MD evidence.",
            "evidence_paths": [],
        },
    ]


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_input_overrides: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = resolve_path(repo_root, reports_root).resolve()
    paths = required_inputs()
    if required_input_overrides:
        paths.update(required_input_overrides)
    if git_status_lines is None:
        git_status = inventory.collect_git_status(repo_root)
        status_lines = list(git_status["status_lines"])
        git_error = git_status["error"]
        git_returncode = git_status["returncode"]
    else:
        status_lines = list(git_status_lines)
        git_error = None
        git_returncode = 0
    dirty_map = inventory.build_dirty_path_map(status_lines)
    output_rel = rel(reports_root, repo_root)
    evidence = required_input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    checks, check_failures, derived = build_checks(
        payloads=payloads,
        evidence=evidence,
        output_rel=output_rel,
    )
    failures = input_failures + check_failures
    findings = build_findings(payloads, derived)
    status = PASS_STATUS if not failures else FAIL_STATUS
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    phase1b_classification = (
        "RUN_LIMITED_SCOPE_PHASE1B_RAW_DBN_RECONCILIATION"
        if status == PASS_STATUS
        else "FAILED_PHASE1B_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase1b_reconciliation_report_only",
            "phase": "Phase 1B",
            "phase_name": "DBN-to-raw conversion plus immediate raw/DBN validation",
            "reports_root": output_rel,
            "evidence_root": PHASE1AB_ROOT.as_posix(),
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "market_year_count": EXPECTED_MARKET_YEAR_COUNT,
            "broad_phase1b_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase1b_master_audit_status": phase1b_classification,
            "phase1b_limited_scope_ready": status == PASS_STATUS,
            "broad_phase1b_alignment_status": derived.get("broad_phase1b_alignment_status"),
            "broad_phase1b_accepted": False,
            "scoped_market_year_count": derived.get("scoped_market_year_count"),
            "current_line_classification": dotted_get(
                payloads.get("run_status"), "summary.current_line_classification"
            ),
            "current_split_classification": dotted_get(
                payloads.get("run_status"), "summary.current_split_classification"
            ),
            "phase2_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
            **dict(NON_APPROVAL),
            "finding_counts_by_severity": finding_counts(findings),
        },
        "input_evidence": evidence,
        "checks": checks,
        "findings": findings,
        "scoped_market_alignment_details": derived.get("market_alignment_details", []),
        "include_list_details": derived.get("include_details", []),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required JSON/MD evidence is readable",
                "run-status, overview, Phase 6, and Phase 7 reconciliation reports are passed report-only inputs",
                "pre-existing Phase 1B ledger row is NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
                "Phase1AB summary reports PASS scoped one-market expected-only batches",
                "broad phase1b_raw_dbn_alignment.json remains recorded as FAIL",
                "6E/CL/ES/ZN alignment reports pass scoped raw/DBN checks",
                "6E/CL/ES/ZN include-lists contain 2023 and 2024",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "any scoped market alignment report not PASS",
                "any missing raw/DBN, source-hash, schema, definition, manifest, or repair-manifest failure",
                "any scoped include-list missing 2023 or 2024",
                "broad Phase 1B is claimed as accepted",
                "Phase 2/model-trust/promotion/holdout/paper/live is upgraded",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan a Phase 2 report-only Master Audit reconciliation for the same active v2 "
            "6E/CL/ES/ZN 2023/2024 scope; do not run Phase 2 readiness/build or data/model commands "
            "without separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 1B Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 1B status: `{summary.get('phase1b_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Scoped market-years: `{summary.get('scoped_market_year_count')}`",
        f"- Broad Phase 1B alignment status: `{summary.get('broad_phase1b_alignment_status')}`",
        f"- Broad Phase 1B accepted: `{summary.get('broad_phase1b_accepted')}`",
        f"- Phase 2 accepted: `{summary.get('phase2_accepted')}`",
        f"- Model-trust ready: `{summary.get('model_trust_ready')}`",
        f"- Promotion allowed: `{summary.get('promotion_allowed')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Failure |",
        "| --- | --- | --- |",
    ]
    for item in report.get("checks", []):
        lines.append(
            f"| {item.get('name')} | `{item.get('status')}` | {item.get('failure') or ''} |"
        )
    lines.extend(["", "## Findings", ""])
    for item in report.get("findings", []):
        lines.append(
            f"- `{item.get('severity')}` `{item.get('finding_id')}`: {item.get('finding')}"
        )
    lines.extend(["", "## Scoped Market Evidence", ""])
    for item in report.get("scoped_market_alignment_details", []):
        lines.append(
            f"- `{item.get('market')}` status=`{item.get('status')}` "
            f"expected={item.get('expected_market_year_count')} raw={item.get('raw_market_year_count')} "
            f"source_hash_mismatches={item.get('source_hash_mismatch_count')}"
        )
    lines.extend(["", "## Evidence Inputs", ""])
    for item in report.get("input_evidence", []):
        lines.append(
            "- `{path}` exists=`{exists}` state=`{state}` git=`{git}` sha256=`{sha}`".format(
                path=item.get("path"),
                exists=item.get("exists"),
                state=item.get("state"),
                git=item.get("git_status"),
                sha=item.get("sha256"),
            )
        )
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This reconciliation did not run Phase 1B conversion, raw/DBN alignment audits, Phase 2 readiness/build, data/model commands, WFA/modeling, predictions, Phase 8, provider/network calls, promotion, freeze, holdout, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, feature parquet, or prediction parquet.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / REPORT_JSON
    md_path = reports_root / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(repo_root=repo_root, reports_root=reports_root)
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"phase1b_status={report['summary']['phase1b_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
