#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 1B broad reconciliation.

This command consumes existing local JSON/MD evidence only. It does not run
Phase 1B conversion, raw/DBN alignment audits, Phase 2 readiness/build,
data/model commands, WFA/modeling, predictions, Phase 8 refresh, provider or
network calls, promotion, freeze, holdout, paper/live, cleanup, staging,
commit, or push.
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
STAGE = "master_audit_phase1b_broad_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE1B_BROAD_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE1B_BROAD_RECONCILIATION_REPORT_ONLY"

EXPECTED_MARKETS = (
    "6A",
    "6B",
    "6C",
    "6E",
    "6J",
    "6M",
    "CL",
    "ES",
    "GC",
    "HE",
    "HG",
    "HO",
    "KE",
    "LE",
    "NG",
    "NQ",
    "RB",
    "RTY",
    "SI",
    "SR1",
    "SR3",
    "TN",
    "UB",
    "YM",
    "ZB",
    "ZC",
    "ZF",
    "ZL",
    "ZM",
    "ZN",
    "ZS",
    "ZT",
    "ZW",
)
EXPECTED_MARKET_COUNT = 33
EXPECTED_MARKET_YEAR_COUNT = 527
EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT = 6
EXPECTED_LEGACY_FULL_ALIGNMENT_SOURCE_HASH_MISMATCHES = 4
EXPECTED_REPAIR_MARKET_YEARS = frozenset(
    {
        ("KE", 2019),
        ("KE", 2021),
        ("KE", 2023),
        ("KE", 2024),
        ("SR1", 2020),
        ("SR3", 2020),
    }
)

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_phase1b_broad_reconciliation_20260710"
)
REPORT_JSON = "master_audit_phase1b_broad_reconciliation.json"
REPORT_MD = "master_audit_phase1b_broad_reconciliation.md"

PHASE1A_RECONCILIATION = Path(
    "reports/master_audit/master_audit_phase1a_reconciliation_20260710/"
    "master_audit_phase1a_reconciliation.json"
)
PHASE1AB_ROOT = Path(
    "reports/data_audit/current_state/"
    "phase1ab_33markets_2010_2026_post_status_placement_refresh_20260706_rerun1"
)
PHASE1AB_SUMMARY = PHASE1AB_ROOT / "phase1ab_post_status_placement_refresh_summary.json"
BROAD_ALIGNMENT = PHASE1AB_ROOT / "phase1b_raw_dbn_alignment.json"
REPAIR_MANIFEST = PHASE1AB_ROOT / "phase1ab_source_hash_repair_manifest_active_paths.json"
MARKET_ALIGNMENT_ROOT = PHASE1AB_ROOT / "phase1b_market_batches_expected_only"

REQUIRED_BASE_INPUTS = {
    "phase1a_reconciliation": PHASE1A_RECONCILIATION,
    "phase1ab_summary": PHASE1AB_SUMMARY,
    "legacy_full_alignment": BROAD_ALIGNMENT,
    "active_path_repair_manifest": REPAIR_MANIFEST,
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


def input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields = {
        "phase1a_reconciliation": {
            "status": "status",
            "phase1a_source_lineage_ready": "summary.phase1a_source_lineage_ready",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase1ab_summary": {
            "status": "status",
            "phase1b_status": "phase1b.status",
            "phase1b_mode": "phase1b.mode",
            "market_reports": "phase1b.summary_counts.market_reports",
            "pass_market_reports": "phase1b.summary_counts.pass_market_reports",
            "fail_market_reports": "phase1b.summary_counts.fail_market_reports",
            "missing_report_count": "phase1b.summary_counts.missing_report_count",
            "expected_market_year_count": (
                "phase1b.summary_counts.expected_market_year_count"
            ),
            "raw_market_year_count": "phase1b.summary_counts.raw_market_year_count",
            "needs_phase1b_conversion_count": (
                "phase1b.summary_counts.needs_phase1b_conversion_count"
            ),
            "source_hash_mismatch_count": (
                "phase1b.summary_counts.source_hash_mismatch_count"
            ),
            "accepted_repair_source_count": (
                "phase1b.summary_counts.accepted_repair_source_count"
            ),
        },
        "legacy_full_alignment": {
            "status": "status",
            "expected_market_year_count": "expected_market_year_count",
            "raw_market_year_count": "raw_market_year_count",
            "source_hash_mismatch_count": "source_hash_mismatch_count",
            "repair_manifest_status": "repair_manifest_status",
            "repair_manifest_failure_count": "repair_manifest_failure_count",
        },
        "active_path_repair_manifest": {
            "status": "status",
            "repair_count": "strict_limits.repair_count",
            "not_a_general_hash_bypass": "strict_limits.not_a_general_hash_bypass",
        },
    }
    for market in EXPECTED_MARKETS:
        json_fields[f"{market}_alignment"] = {
            "status": "status",
            "expected_only": "expected_only",
            "expected_market_year_count": "expected_market_year_count",
            "raw_market_year_count": "raw_market_year_count",
            "needs_phase1b_conversion_count": "needs_phase1b_conversion_count",
            "raw_only_count": "raw_only_count",
            "invalid_manifest_count": "invalid_manifest_count",
            "source_hash_mismatch_count": "source_hash_mismatch_count",
            "definition_join_mismatch_count": "definition_join_mismatch_count",
            "raw_schema_failure_count": "raw_schema_failure_count",
            "required_schema_exception_failure_count": (
                "required_schema_exception_failure_count"
            ),
            "accepted_repair_source_count": "accepted_repair_source_count",
            "repair_manifest_failure_count": "repair_manifest_failure_count",
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
    for name, relative_path in paths.items():
        if Path(relative_path).suffix.lower() != ".json":
            continue
        payload, error = read_json_object(resolve_path(repo_root, relative_path))
        if error:
            failures.append(f"required JSON input unavailable: {relative_path.as_posix()} ({error})")
        elif payload is not None:
            payloads[name] = payload
    return payloads, failures


def summary_counts(payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    counts = dotted_get(payloads.get("phase1ab_summary"), "phase1b.summary_counts")
    return dict(counts) if isinstance(counts, Mapping) else {}


def summary_market_reports(payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = dotted_get(payloads.get("phase1ab_summary"), "phase1b.market_reports")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


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


def repair_market_years(payload: Mapping[str, Any] | None) -> set[tuple[str, int]]:
    rows = dotted_get(payload, "strict_limits.allowed_market_years")
    if not isinstance(rows, list):
        return set()
    result: set[tuple[str, int]] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        market = row.get("market")
        year = row.get("year")
        if isinstance(market, str) and isinstance(year, int):
            result.add((market, year))
    return result


def approvals_all_false(payload: Mapping[str, Any] | None) -> bool:
    approvals = dotted_get(payload, "approvals")
    return isinstance(approvals, Mapping) and all(value is False for value in approvals.values())


def market_alignment_pass(
    payload: Mapping[str, Any] | None,
    market: str,
    expected_count: int | None,
) -> tuple[bool, dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return False, {"market": market, "reason": "payload missing"}
    details = {
        "market": market,
        "status": payload.get("status"),
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
        "missing_status_dbn_count": payload.get("missing_status_dbn_count"),
        "missing_statistics_dbn_count": payload.get("missing_statistics_dbn_count"),
        "needs_phase1b_conversion_count": payload.get("needs_phase1b_conversion_count"),
        "raw_only_count": payload.get("raw_only_count"),
        "invalid_manifest_count": payload.get("invalid_manifest_count"),
        "source_hash_mismatch_count": payload.get("source_hash_mismatch_count"),
        "definition_join_status": payload.get("definition_join_status"),
        "definition_join_mismatch_count": payload.get("definition_join_mismatch_count"),
        "raw_schema_failure_count": payload.get("raw_schema_failure_count"),
        "required_schema_exception_failure_count": payload.get(
            "required_schema_exception_failure_count"
        ),
        "accepted_repair_source_count": payload.get("accepted_repair_source_count"),
        "repair_manifest_status": payload.get("repair_manifest_status"),
        "repair_manifest_failure_count": payload.get("repair_manifest_failure_count"),
        "failures_count": len(as_list(payload.get("failures"))),
        "expected_summary_count": expected_count,
    }
    zero_fields = (
        "missing_raw_count",
        "missing_ohlcv_dbn_count",
        "missing_definition_dbn_count",
        "missing_status_dbn_count",
        "missing_statistics_dbn_count",
        "needs_phase1b_conversion_count",
        "raw_only_count",
        "invalid_manifest_count",
        "source_hash_mismatch_count",
        "definition_join_mismatch_count",
        "raw_schema_failure_count",
        "required_schema_exception_failure_count",
        "repair_manifest_failure_count",
    )
    passed = (
        payload.get("status") == "PASS"
        and payload.get("expected_only") is True
        and payload.get("market_year_include_list_applied") is True
        and payload.get("expected_market_year_count") == payload.get("raw_market_year_count")
        and (expected_count is None or payload.get("expected_market_year_count") == expected_count)
        and all(payload.get(field) == 0 for field in zero_fields)
        and payload.get("definition_join_status") == "checked"
        and payload.get("repair_manifest_status") == "PASS"
        and len(as_list(payload.get("failures"))) == 0
    )
    return passed, details


def check_phase1ab_summary(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    summary = payloads.get("phase1ab_summary")
    phase1b = dotted_get(summary, "phase1b")
    phase1b = phase1b if isinstance(phase1b, Mapping) else {}
    counts = summary_counts(payloads)
    expected_counts = {
        "market_reports": EXPECTED_MARKET_COUNT,
        "missing_report_count": 0,
        "pass_market_reports": EXPECTED_MARKET_COUNT,
        "fail_market_reports": 0,
        "expected_market_year_count": EXPECTED_MARKET_YEAR_COUNT,
        "raw_market_year_count": EXPECTED_MARKET_YEAR_COUNT,
        "missing_status_dbn_count": 0,
        "missing_statistics_dbn_count": 0,
        "needs_phase1b_conversion_count": 0,
        "raw_only_count": 0,
        "invalid_manifest_count": 0,
        "source_hash_mismatch_count": 0,
        "definition_join_mismatch_count": 0,
        "raw_schema_failure_count": 0,
        "required_schema_exception_failure_count": 0,
        "accepted_repair_source_count": EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT,
        "repair_manifest_failure_count": 0,
    }
    count_mismatches = {
        key: {"expected": expected, "actual": counts.get(key)}
        for key, expected in expected_counts.items()
        if counts.get(key) != expected
    }
    passed = (
        summary is not None
        and summary.get("status") == "PASS"
        and phase1b.get("status") == "PASS"
        and phase1b.get("mode") == "one_market_batches_expected_only"
        and phase1b.get("repair_manifest") == REPAIR_MANIFEST.as_posix()
        and not count_mismatches
    )
    check(
        checks,
        failures,
        name="phase1ab_summary_broad_expected_only_pass",
        passed=passed,
        failure="Phase 1AB 33-market expected-only Phase 1B summary is not an exact PASS",
        evidence=[PHASE1AB_SUMMARY.as_posix()],
        details={
            "summary_status": None if summary is None else summary.get("status"),
            "phase1b_status": phase1b.get("status"),
            "phase1b_mode": phase1b.get("mode"),
            "repair_manifest": phase1b.get("repair_manifest"),
            "count_mismatches": count_mismatches,
            "counts": counts,
        },
    )
    return counts


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
        failure=f"missing required Phase 1B broad reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel.startswith("reports/master_audit/") and not output_rel.endswith("/"),
        failure=f"invalid report output root for broad Phase 1B reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    phase1a = payloads.get("phase1a_reconciliation")
    check(
        checks,
        failures,
        name="phase1a_upstream_source_lineage_pass",
        passed=phase1a is not None
        and phase1a.get("status") == "PASS_MASTER_AUDIT_PHASE1A_RECONCILIATION_REPORT_ONLY"
        and dotted_get(phase1a, "summary.phase1a_source_lineage_ready") is True
        and dotted_get(phase1a, "summary.model_trust_ready") is False
        and dotted_get(phase1a, "summary.promotion_allowed") is False,
        failure="upstream Phase 1A source-lineage reconciliation is not passed report-only evidence",
        evidence=[PHASE1A_RECONCILIATION.as_posix()],
        details={
            "status": None if phase1a is None else phase1a.get("status"),
            "phase1a_source_lineage_ready": dotted_get(
                phase1a, "summary.phase1a_source_lineage_ready"
            ),
        },
    )

    counts = check_phase1ab_summary(checks, failures, payloads=payloads)

    market_reports = summary_market_reports(payloads)
    market_report_by_market = {
        str(item.get("market")): item for item in market_reports if item.get("market") is not None
    }
    expected_market_set = set(EXPECTED_MARKETS)
    summary_market_set = set(market_report_by_market)
    check(
        checks,
        failures,
        name="summary_market_reports_cover_exact_33_markets",
        passed=summary_market_set == expected_market_set and len(market_reports) == EXPECTED_MARKET_COUNT,
        failure="Phase 1AB summary market reports do not cover the exact expected 33 markets",
        evidence=[PHASE1AB_SUMMARY.as_posix()],
        details={
            "missing_markets": sorted(expected_market_set - summary_market_set),
            "extra_markets": sorted(summary_market_set - expected_market_set),
            "market_report_count": len(market_reports),
        },
    )

    repair_manifest = payloads.get("active_path_repair_manifest")
    repair_pairs = repair_market_years(repair_manifest)
    check(
        checks,
        failures,
        name="active_path_repair_manifest_exact_pass",
        passed=repair_manifest is not None
        and repair_manifest.get("status") == "PASS"
        and dotted_get(repair_manifest, "strict_limits.repair_count")
        == EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT
        and dotted_get(repair_manifest, "strict_limits.not_a_general_hash_bypass") is True
        and repair_pairs == EXPECTED_REPAIR_MARKET_YEARS
        and len(as_list(repair_manifest.get("repairs"))) == EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT
        and approvals_all_false(repair_manifest),
        failure="active-path source-hash repair manifest is not exact scoped PASS evidence",
        evidence=[REPAIR_MANIFEST.as_posix()],
        details={
            "status": None if repair_manifest is None else repair_manifest.get("status"),
            "repair_count": dotted_get(repair_manifest, "strict_limits.repair_count"),
            "not_a_general_hash_bypass": dotted_get(
                repair_manifest, "strict_limits.not_a_general_hash_bypass"
            ),
            "repair_pairs": sorted(f"{market}:{year}" for market, year in repair_pairs),
            "approvals_all_false": approvals_all_false(repair_manifest),
        },
    )

    legacy = payloads.get("legacy_full_alignment")
    legacy_superseded = (
        legacy is not None
        and legacy.get("status") == "FAIL"
        and legacy.get("expected_market_year_count") == EXPECTED_MARKET_YEAR_COUNT
        and legacy.get("raw_market_year_count") == EXPECTED_MARKET_YEAR_COUNT
        and legacy.get("source_hash_mismatch_count")
        == EXPECTED_LEGACY_FULL_ALIGNMENT_SOURCE_HASH_MISMATCHES
        and legacy.get("raw_schema_failure_count") == 0
        and legacy.get("definition_join_status") == "checked"
        and legacy.get("definition_join_mismatch_count") == 0
        and legacy.get("invalid_manifest_count") == 0
        and legacy.get("repair_manifest_status") == "PASS"
        and legacy.get("repair_manifest_failure_count") == 0
        and counts.get("source_hash_mismatch_count") == 0
        and counts.get("accepted_repair_source_count") == EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT
    )
    check(
        checks,
        failures,
        name="legacy_full_alignment_failure_superseded_not_ignored",
        passed=legacy_superseded,
        failure="legacy full-profile Phase 1B alignment failure is not superseded by corrected expected-only evidence",
        evidence=[BROAD_ALIGNMENT.as_posix(), PHASE1AB_SUMMARY.as_posix(), REPAIR_MANIFEST.as_posix()],
        details={
            "legacy_status": None if legacy is None else legacy.get("status"),
            "legacy_source_hash_mismatch_count": None
            if legacy is None
            else legacy.get("source_hash_mismatch_count"),
            "summary_source_hash_mismatch_count": counts.get("source_hash_mismatch_count"),
            "summary_accepted_repair_source_count": counts.get("accepted_repair_source_count"),
        },
    )

    market_details: list[dict[str, Any]] = []
    include_details: list[dict[str, Any]] = []
    alignment_expected_sum = 0
    alignment_raw_sum = 0
    alignment_accepted_repair_sum = 0
    for market in EXPECTED_MARKETS:
        summary_row = market_report_by_market.get(market, {})
        expected_count = summary_row.get("expected_market_year_count")
        expected_count = expected_count if isinstance(expected_count, int) else None
        alignment = payloads.get(f"{market}_alignment")
        passed, details = market_alignment_pass(alignment, market, expected_count)
        market_details.append(details)
        if isinstance(alignment, Mapping):
            alignment_expected_sum += int(alignment.get("expected_market_year_count") or 0)
            alignment_raw_sum += int(alignment.get("raw_market_year_count") or 0)
            alignment_accepted_repair_sum += int(alignment.get("accepted_repair_source_count") or 0)
        check(
            checks,
            failures,
            name=f"{market}_broad_expected_only_alignment_passes",
            passed=passed,
            failure=f"{market} expected-only Phase 1B alignment report does not pass broad checks",
            evidence=[market_alignment_path(market).as_posix()],
            details=details,
        )

        include_payload = payloads.get(f"{market}_include")
        include_pairs = include_market_years(include_payload)
        include_detail = {
            "market": market,
            "include_count": len(include_pairs),
            "expected_summary_count": expected_count,
            "only_this_market": all(pair[0] == market for pair in include_pairs),
        }
        include_details.append(include_detail)
        check(
            checks,
            failures,
            name=f"{market}_include_matches_expected_market_year_count",
            passed=expected_count is not None
            and len(include_pairs) == expected_count
            and include_detail["only_this_market"],
            failure=f"{market} include-list does not match expected market-year count",
            evidence=[market_include_path(market).as_posix()],
            details=include_detail,
        )

    check(
        checks,
        failures,
        name="market_batch_sums_match_527_expected_and_raw_market_years",
        passed=alignment_expected_sum == EXPECTED_MARKET_YEAR_COUNT
        and alignment_raw_sum == EXPECTED_MARKET_YEAR_COUNT
        and alignment_accepted_repair_sum == EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT,
        failure="market batch totals do not match broad Phase 1B expected/raw/repair counts",
        evidence=[market_alignment_path(market).as_posix() for market in EXPECTED_MARKETS],
        details={
            "alignment_expected_sum": alignment_expected_sum,
            "alignment_raw_sum": alignment_raw_sum,
            "alignment_accepted_repair_sum": alignment_accepted_repair_sum,
        },
    )

    check(
        checks,
        failures,
        name="non_approval_flags_all_false",
        passed=all(value is False for value in NON_APPROVAL.values()),
        failure="one or more broad Phase 1B reconciliation non-approval flags is true",
        details={"non_approval": dict(NON_APPROVAL)},
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "counts": counts,
        "market_alignment_details": market_details,
        "include_details": include_details,
        "legacy_full_alignment_status": None if legacy is None else legacy.get("status"),
        "legacy_full_alignment_source_hash_mismatch_count": None
        if legacy is None
        else legacy.get("source_hash_mismatch_count"),
        "legacy_full_alignment_context": (
            "SUPERSEDED_BY_CORRECTED_EXPECTED_ONLY_BATCHES"
            if legacy_superseded and not failures
            else "UNRESOLVED"
        ),
        "repair_pairs": sorted(f"{market}:{year}" for market, year in repair_pairs),
        "alignment_expected_sum": alignment_expected_sum,
        "alignment_raw_sum": alignment_raw_sum,
        "alignment_accepted_repair_sum": alignment_accepted_repair_sum,
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    counts = derived.get("counts")
    counts = counts if isinstance(counts, Mapping) else {}
    return [
        {
            "finding_id": "phase1b-broad-001-row-parity-conversion-accepted",
            "severity": "Info",
            "finding": (
                "Broad Phase 1B raw row-parity/conversion evidence is accepted as "
                "report-only local evidence for the 33-market expected-only scope."
            ),
            "verified_facts": [
                f"market_reports={counts.get('market_reports')}",
                f"expected_market_year_count={counts.get('expected_market_year_count')}",
                f"raw_market_year_count={counts.get('raw_market_year_count')}",
                f"needs_phase1b_conversion_count={counts.get('needs_phase1b_conversion_count')}",
            ],
            "limitation": "This does not run conversion or a new raw/DBN alignment audit.",
            "evidence_paths": [PHASE1AB_SUMMARY.as_posix()],
        },
        {
            "finding_id": "phase1b-broad-002-legacy-full-alignment-superseded",
            "severity": "High",
            "finding": (
                "The older full-profile Phase 1B alignment FAIL is preserved as "
                "superseded context, not ignored."
            ),
            "verified_facts": [
                f"legacy_full_alignment_status={derived.get('legacy_full_alignment_status')}",
                "legacy_full_alignment_context="
                f"{derived.get('legacy_full_alignment_context')}",
                "legacy_full_alignment_source_hash_mismatch_count="
                f"{derived.get('legacy_full_alignment_source_hash_mismatch_count')}",
            ],
            "limitation": "The acceptance relies on the corrected expected-only market batches and scoped repair manifest.",
            "evidence_paths": [BROAD_ALIGNMENT.as_posix(), REPAIR_MANIFEST.as_posix()],
        },
        {
            "finding_id": "phase1b-broad-003-repair-scope-is-not-general-bypass",
            "severity": "High",
            "finding": "Accepted source-hash repairs are limited to six explicit market-years.",
            "verified_facts": [
                "repair_pairs=" + ",".join(str(item) for item in derived.get("repair_pairs", [])),
                f"accepted_repair_source_count={counts.get('accepted_repair_source_count')}",
            ],
            "limitation": "This does not approve a general source-hash bypass.",
            "evidence_paths": [REPAIR_MANIFEST.as_posix()],
        },
        {
            "finding_id": "phase1b-broad-004-no-downstream-actions-authorized",
            "severity": "Info",
            "finding": "Phase 2, model trust, promotion, holdout, paper/live, and production remain blocked.",
            "verified_facts": ["All non-approval flags in this report are false."],
            "limitation": "This report only remediates the raw_row_parity_and_conversion evidence gap.",
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
    evidence = input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    output_rel = rel(reports_root, repo_root)
    checks, check_failures, derived = build_checks(
        payloads=payloads,
        evidence=evidence,
        output_rel=output_rel,
    )
    failures = input_failures + check_failures
    status = PASS_STATUS if not failures else FAIL_STATUS
    findings = build_findings(derived)
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    counts = derived.get("counts")
    counts = counts if isinstance(counts, Mapping) else {}
    phase1b_classification = (
        "RUN_BROAD_PHASE1B_RAW_ROW_PARITY_CONVERSION_RECONCILIATION"
        if status == PASS_STATUS
        else "FAILED_BROAD_PHASE1B_RAW_ROW_PARITY_CONVERSION_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase1b_broad_reconciliation_report_only",
            "phase": "Phase 1B",
            "phase_name": "raw row-parity and conversion evidence",
            "reports_root": output_rel,
            "accepted_scope": "33-market 2010-2026 expected-only current horizon ending 2026-06-13",
            "evidence_root": PHASE1AB_ROOT.as_posix(),
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "market_count": EXPECTED_MARKET_COUNT,
            "market_year_count": EXPECTED_MARKET_YEAR_COUNT,
            "data_model_scope": "none",
            "provider_scope": "none",
            "allowed_inputs": [rel(resolve_path(repo_root, path), repo_root) for path in paths.values()],
        },
        "summary": {
            "status": status,
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase1b_master_audit_status": phase1b_classification,
            "raw_row_parity_and_conversion_ready": status == PASS_STATUS,
            "broad_phase1b_accepted": status == PASS_STATUS,
            "market_report_count": counts.get("market_reports"),
            "pass_market_reports": counts.get("pass_market_reports"),
            "fail_market_reports": counts.get("fail_market_reports"),
            "missing_report_count": counts.get("missing_report_count"),
            "expected_market_year_count": counts.get("expected_market_year_count"),
            "raw_market_year_count": counts.get("raw_market_year_count"),
            "needs_phase1b_conversion_count": counts.get("needs_phase1b_conversion_count"),
            "raw_only_count": counts.get("raw_only_count"),
            "invalid_manifest_count": counts.get("invalid_manifest_count"),
            "source_hash_mismatch_count": counts.get("source_hash_mismatch_count"),
            "definition_join_mismatch_count": counts.get("definition_join_mismatch_count"),
            "raw_schema_failure_count": counts.get("raw_schema_failure_count"),
            "required_schema_exception_failure_count": counts.get(
                "required_schema_exception_failure_count"
            ),
            "accepted_repair_source_count": counts.get("accepted_repair_source_count"),
            "repair_manifest_failure_count": counts.get("repair_manifest_failure_count"),
            "legacy_full_alignment_status": derived.get("legacy_full_alignment_status"),
            "legacy_full_alignment_source_hash_mismatch_count": derived.get(
                "legacy_full_alignment_source_hash_mismatch_count"
            ),
            "legacy_full_alignment_context": derived.get("legacy_full_alignment_context"),
            "phase2_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
            **dict(NON_APPROVAL),
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
            "finding_counts": finding_counts(findings),
        },
        "input_evidence": evidence,
        "checks": checks,
        "findings": findings,
        "market_alignment_details": derived.get("market_alignment_details", []),
        "include_list_details": derived.get("include_details", []),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "upstream Phase 1A reconciliation is passed report-only source-lineage evidence",
                "Phase 1AB summary reports PASS for 33 expected-only one-market batches",
                "33 market reports are present and PASS",
                "expected/raw market-year counts are both 527",
                "conversion-needed, raw-only, invalid-manifest, source-hash, definition-join, raw-schema, and required-exception failures are all zero",
                "accepted repair sources are exactly the six active-path approved market-years",
                "legacy full-profile alignment FAIL is preserved as superseded context",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "any summary count mismatch",
                "any market batch not PASS",
                "any missing include-list or market-year count mismatch",
                "active-path repair manifest is missing, broad, or not PASS",
                "legacy full alignment failure is not explicitly superseded by corrected expected-only evidence",
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
            "Plan Phase 2 causal/session active-scope evidence remediation only; do not run "
            "Phase 2 readiness/build or any data/model command without separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Phase 1B Broad Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 1B status: `{summary['phase1b_master_audit_status']}`",
        f"- Raw row-parity/conversion ready: `{summary['raw_row_parity_and_conversion_ready']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Market reports: `{summary['market_report_count']}`",
        f"- Passed market reports: `{summary['pass_market_reports']}`",
        f"- Failed market reports: `{summary['fail_market_reports']}`",
        f"- Missing market reports: `{summary['missing_report_count']}`",
        f"- Expected market-years: `{summary['expected_market_year_count']}`",
        f"- Raw market-years: `{summary['raw_market_year_count']}`",
        f"- Needs conversion: `{summary['needs_phase1b_conversion_count']}`",
        f"- Raw-only: `{summary['raw_only_count']}`",
        f"- Invalid manifests: `{summary['invalid_manifest_count']}`",
        f"- Source hash mismatches: `{summary['source_hash_mismatch_count']}`",
        f"- Definition join mismatches: `{summary['definition_join_mismatch_count']}`",
        f"- Raw schema failures: `{summary['raw_schema_failure_count']}`",
        f"- Required-schema exception failures: `{summary['required_schema_exception_failure_count']}`",
        f"- Accepted repair sources: `{summary['accepted_repair_source_count']}`",
        f"- Legacy full alignment status: `{summary['legacy_full_alignment_status']}`",
        f"- Legacy full alignment context: `{summary['legacy_full_alignment_context']}`",
        f"- Phase 2 accepted: `{summary['phase2_accepted']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Failure |",
        "| --- | --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(
            "| `{name}` | `{status}` | {failure} |".format(
                name=item["name"],
                status=item["status"],
                failure=item.get("failure") or "",
            )
        )
    lines.extend(["", "## Findings", ""])
    for item in report["findings"]:
        lines.append(
            "- `{severity}` `{finding_id}`: {finding}".format(
                severity=item["severity"],
                finding_id=item["finding_id"],
                finding=item["finding"],
            )
        )
    lines.extend(["", "## Market Evidence", ""])
    for item in report["market_alignment_details"]:
        lines.append(
            f"- `{item.get('market')}` status=`{item.get('status')}` "
            f"expected={item.get('expected_market_year_count')} "
            f"raw={item.get('raw_market_year_count')} "
            f"needs_conversion={item.get('needs_phase1b_conversion_count')} "
            f"source_hash_mismatches={item.get('source_hash_mismatch_count')}"
        )
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This reconciliation did not run Phase 1B conversion, raw/DBN alignment audits, Phase 2 readiness/build, data/model commands, WFA/modeling, predictions, Phase 8 refresh, provider/network calls, promotion, freeze, holdout, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, feature parquet, or prediction parquet.",
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
        f"raw_row_parity_and_conversion_ready="
        f"{report['summary']['raw_row_parity_and_conversion_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
