#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 2 active-scope reconciliation.

This command consumes existing local JSON/MD evidence only. It does not run
Phase 2 readiness/build, causal rebuilds, parquet audits, label/feature
rebuilds, data/model commands, WFA/modeling, predictions, Phase 8 refresh,
provider/network calls, promotion, artifact freeze, final holdout, paper/live,
cleanup, staging, commit, or push.
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
STAGE = "master_audit_phase2_active_scope_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE2_ACTIVE_SCOPE_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE2_ACTIVE_SCOPE_RECONCILIATION_REPORT_ONLY"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_MARKET_YEAR_COUNT = 8
EXPECTED_ACTIVE_PAIR_COUNT = 518
EXPECTED_TARGET_TIMING_ROWS = 2_837_374

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_phase2_active_scope_reconciliation_20260710"
)
REPORT_JSON = "master_audit_phase2_active_scope_reconciliation.json"
REPORT_MD = "master_audit_phase2_active_scope_reconciliation.md"

PHASE2_RECONCILIATION = Path(
    "reports/master_audit/master_audit_phase2_reconciliation_20260709/"
    "master_audit_phase2_reconciliation.json"
)
ACTIVE_CAUSAL_GATE_REPORT = Path(
    "reports/data_audit/current_state/active_root_causal_manifest_gate_20260705/"
    "active_causal_manifest_gate_report.json"
)
ACTIVE_CAUSAL_MANIFEST = Path(
    "reports/data_audit/current_state/active_root_causal_manifest_gate_20260705/"
    "causal_base_manifest.json"
)
READINESS_POST_EXCLUSIONS = Path(
    "reports/data_audit/current_state/"
    "phase2_readiness_post_historical_6m_tn_exclusions_20260706/"
    "active_root_raw_to_causal_readiness_post_historical_6m_tn_exclusions.json"
)
V2_LABEL_MANIFEST = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_active_tier1_core_manifest_for_phase4/"
    "label_manifest.json"
)
TARGET_TIMING = Path(
    "reports/model_trust_audit/target_timing_v2_tier1_core_20260709/"
    "target_timing_audit.json"
)
PHASE2_SPEC = Path("docs/phase2_causal_session_normalization_spec.md")

REQUIRED_INPUTS = {
    "phase2_reconciliation": PHASE2_RECONCILIATION,
    "active_causal_gate_report": ACTIVE_CAUSAL_GATE_REPORT,
    "active_causal_manifest": ACTIVE_CAUSAL_MANIFEST,
    "readiness_post_exclusions": READINESS_POST_EXCLUSIONS,
    "v2_label_manifest": V2_LABEL_MANIFEST,
    "target_timing": TARGET_TIMING,
    "phase2_spec": PHASE2_SPEC,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase2_readiness_or_build_executed": False,
    "causal_rebuild_executed": False,
    "audit_phase2_causal_session_normalization_executed": False,
    "parquet_audit_executed": False,
    "dbn_read_executed": False,
    "raw_parquet_read_executed": False,
    "causal_parquet_read_executed": False,
    "label_parquet_read_executed": False,
    "feature_parquet_read_executed": False,
    "prediction_parquet_read_executed": False,
    "label_feature_rebuild_executed": False,
    "data_model_commands_executed": False,
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


def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def expected_pairs() -> list[tuple[str, int]]:
    return [(market, year) for market in EXPECTED_MARKETS for year in EXPECTED_YEARS]


def causal_path(market: str, year: int) -> str:
    return f"data/causally_gated_normalized/{market}/{year}.parquet"


def output_hashes(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    hashes = payload.get("output_file_hashes")
    return hashes if isinstance(hashes, Mapping) else {}


def input_hashes(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    hashes = payload.get("input_file_hashes")
    return hashes if isinstance(hashes, Mapping) else {}


def scoped_outputs(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("outputs")
    if not isinstance(rows, list):
        return []
    pair_set = set(expected_pairs())
    scoped: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        pair = (row.get("market"), as_int(row.get("year")))
        if pair in pair_set:
            scoped.append(row)
    return scoped


def scoped_raw_without_causal(readiness: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows = as_list(None if not isinstance(readiness, Mapping) else readiness.get("raw_without_causal"))
    pair_set = set(expected_pairs())
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        pair = (row.get("market"), as_int(row.get("year")))
        if pair in pair_set:
            result.append(dict(row))
    return result


def active_label_hash_comparison(
    *,
    active_manifest: Mapping[str, Any] | None,
    label_manifest: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    active_hashes = output_hashes(active_manifest)
    label_hashes = input_hashes(label_manifest)
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        path = causal_path(market, year)
        active_hash = active_hashes.get(path)
        label_hash = label_hashes.get(path)
        rows.append(
            {
                "market": market,
                "year": year,
                "path": path,
                "active_hash": active_hash,
                "label_input_hash": label_hash,
                "matches": active_hash is not None and active_hash == label_hash,
            }
        )
    return rows


def text_contains(path: Path, terms: Sequence[str]) -> dict[str, bool]:
    try:
        text = path.read_text(encoding="utf-8").lower()
    except Exception:
        return {term: False for term in terms}
    return {term: term.lower() in text for term in terms}


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
    json_fields: dict[str, dict[str, str]] = {
        "phase2_reconciliation": {
            "status": "status",
            "phase2_limited_active_hash_lineage_ready": (
                "summary.phase2_limited_active_hash_lineage_ready"
            ),
            "active_scoped_output_count": "summary.active_scoped_output_count",
            "active_hash_match_count": "summary.active_hash_match_count",
            "phase2_full_master_audit_accepted": (
                "summary.phase2_full_master_audit_accepted"
            ),
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "active_causal_gate_report": {
            "status": "status",
            "manifest_status": "summary.manifest_status",
            "gate_check_status": "summary.gate_check_status",
            "active_causal_pair_count": "summary.active_causal_pair_count",
            "provider_network_calls": "summary.provider_network_calls",
            "data_mutation_performed": "summary.data_mutation_performed",
        },
        "active_causal_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "output_root": "output_root",
            "output_count": "summary.output_count",
            "fail_count": "summary.fail_count",
            "warn_count": "summary.warn_count",
            "active_causal_pair_count": "summary.active_causal_pair_count",
        },
        "readiness_post_exclusions": {
            "status": "summary.status",
            "severe_blocker_count": "summary.severe_blocker_count",
            "raw_without_causal_count": "summary.raw_without_causal_count",
            "local_trade_gap_gate_status_counts": (
                "summary.local_trade_gap_gate_status_counts"
            ),
        },
        "v2_label_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "input_root": "input_root",
            "output_root": "output_root",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
            "causal_base_manifest_gate_status": "causal_base_manifest_gate.status",
            "causal_base_manifest_gate_path": "causal_base_manifest_gate.manifest_path",
        },
        "target_timing": {
            "status": "status",
            "summary_status": "summary.status",
            "failure_count": "summary.failure_count",
            "warning_count": "summary.warning_count",
            "pair_count": "summary.pair_count",
            "row_count": "summary.row_count",
            "row_key_mismatches": "summary.row_key_mismatches",
        },
    }
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


def build_checks(
    *,
    repo_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    output_rel: str,
    paths: Mapping[str, Path],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {str(item.get("path")) for item in evidence if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required Phase 2 active-scope inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel.startswith("reports/master_audit/") and not output_rel.endswith("/"),
        failure=f"invalid report output root for Phase 2 active-scope reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    phase2_report = payloads.get("phase2_reconciliation")
    check(
        checks,
        failures,
        name="existing_phase2_reconciliation_passed_limited_active_scope",
        passed=phase2_report is not None
        and phase2_report.get("status") == "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY"
        and dotted_get(phase2_report, "summary.phase2_limited_active_hash_lineage_ready") is True
        and dotted_get(phase2_report, "summary.active_scoped_output_count")
        == EXPECTED_MARKET_YEAR_COUNT
        and dotted_get(phase2_report, "summary.active_hash_match_count")
        == EXPECTED_MARKET_YEAR_COUNT
        and dotted_get(phase2_report, "summary.phase2_full_master_audit_accepted") is False
        and dotted_get(phase2_report, "summary.phase2_session_normalization_audit_accepted")
        is False
        and dotted_get(phase2_report, "summary.phase2_build_or_readiness_accepted") is False
        and dotted_get(phase2_report, "summary.audit_phase2_causal_session_normalization_executed")
        is False
        and dotted_get(phase2_report, "summary.phase2_build_or_readiness_executed") is False
        and dotted_get(phase2_report, "summary.causal_parquet_read_executed") is False
        and dotted_get(phase2_report, "summary.model_trust_ready") is False
        and dotted_get(phase2_report, "summary.promotion_allowed") is False,
        failure="existing Phase 2 reconciliation is not passed limited active-scope evidence",
        evidence=[PHASE2_RECONCILIATION.as_posix()],
        details={
            "status": None if phase2_report is None else phase2_report.get("status"),
            "active_scoped_output_count": dotted_get(
                phase2_report, "summary.active_scoped_output_count"
            ),
            "active_hash_match_count": dotted_get(
                phase2_report, "summary.active_hash_match_count"
            ),
            "phase2_full_master_audit_accepted": dotted_get(
                phase2_report, "summary.phase2_full_master_audit_accepted"
            ),
            "phase2_session_normalization_audit_accepted": dotted_get(
                phase2_report, "summary.phase2_session_normalization_audit_accepted"
            ),
        },
    )

    gate = payloads.get("active_causal_gate_report")
    gate_summary = gate.get("summary") if isinstance(gate, Mapping) else {}
    gate_summary = gate_summary if isinstance(gate_summary, Mapping) else {}
    gate_forbidden_flags = {
        key: gate_summary.get(key)
        for key in (
            "provider_network_calls",
            "data_mutation_performed",
            "cleanup_archive_execution_performed",
            "sidecar_canonicalization_performed",
            "label_writes_performed",
            "feature_wfa_prediction_modeling_performed",
            "commit_push_paper_live_performed",
        )
    }
    check(
        checks,
        failures,
        name="active_causal_manifest_gate_passed_no_execution",
        passed=gate is not None
        and gate.get("status") == "PASS_MANIFEST_GATE_READY_NO_EXECUTION"
        and gate_summary.get("status") == "PASS_MANIFEST_GATE_READY_NO_EXECUTION"
        and gate_summary.get("manifest_status") == "PASS"
        and gate_summary.get("gate_check_status") == "PASS"
        and gate_summary.get("active_causal_pair_count") == EXPECTED_ACTIVE_PAIR_COUNT
        and gate_summary.get("output_count") == EXPECTED_ACTIVE_PAIR_COUNT
        and gate_summary.get("manifest_failure_count") == 0
        and gate_summary.get("manifest_warning_count") == 0
        and gate_summary.get("gate_failure_count") == 0
        and all(value is False for value in gate_forbidden_flags.values()),
        failure="active causal manifest gate is not passed no-execution evidence",
        evidence=[ACTIVE_CAUSAL_GATE_REPORT.as_posix()],
        details={
            "status": None if gate is None else gate.get("status"),
            "summary": dict(gate_summary),
            "forbidden_flags": gate_forbidden_flags,
        },
    )

    active_manifest = payloads.get("active_causal_manifest")
    active_summary = active_manifest.get("summary") if isinstance(active_manifest, Mapping) else {}
    active_summary = active_summary if isinstance(active_summary, Mapping) else {}
    scoped_active = scoped_outputs(active_manifest)
    scoped_pair_set = {
        (str(row.get("market")), as_int(row.get("year"))) for row in scoped_active
    }
    expected_pair_set = set(expected_pairs())
    scoped_failures = [
        dict(row)
        for row in scoped_active
        if row.get("status") != "PASS"
        or row.get("failure_count") != 0
        or row.get("warning_count") != 0
        or row.get("output_path") != causal_path(str(row.get("market")), int(row.get("year")))
    ]
    check(
        checks,
        failures,
        name="active_causal_manifest_exact_active_scope_pass",
        passed=active_manifest is not None
        and active_manifest.get("status") == "PASS"
        and active_manifest.get("profile") == "all_causal"
        and active_manifest.get("resolved_profile") == "all_causal"
        and active_manifest.get("output_root") == "data/causally_gated_normalized"
        and active_summary.get("output_count") == EXPECTED_ACTIVE_PAIR_COUNT
        and active_summary.get("active_causal_pair_count") == EXPECTED_ACTIVE_PAIR_COUNT
        and active_summary.get("fail_count") == 0
        and active_summary.get("warn_count") == 0
        and len(output_hashes(active_manifest)) == EXPECTED_ACTIVE_PAIR_COUNT
        and len(scoped_active) == EXPECTED_MARKET_YEAR_COUNT
        and scoped_pair_set == expected_pair_set
        and not scoped_failures,
        failure="active causal manifest does not prove exact active 6E/CL/ES/ZN 2023/2024 scope",
        evidence=[ACTIVE_CAUSAL_MANIFEST.as_posix()],
        details={
            "status": None if active_manifest is None else active_manifest.get("status"),
            "summary": dict(active_summary),
            "scoped_output_count": len(scoped_active),
            "scoped_pairs": sorted(f"{market}:{year}" for market, year in scoped_pair_set),
            "scoped_failures": scoped_failures,
        },
    )

    label_manifest = payloads.get("v2_label_manifest")
    label_gate = (
        label_manifest.get("causal_base_manifest_gate")
        if isinstance(label_manifest, Mapping)
        else {}
    )
    label_gate = label_gate if isinstance(label_gate, Mapping) else {}
    hash_comparisons = active_label_hash_comparison(
        active_manifest=active_manifest,
        label_manifest=label_manifest,
    )
    active_hash_match_count = sum(1 for row in hash_comparisons if row["matches"])
    check(
        checks,
        failures,
        name="v2_label_manifest_consumes_active_causal_manifest",
        passed=label_manifest is not None
        and label_manifest.get("status") == "PASS"
        and label_manifest.get("profile") == "tier_1"
        and label_manifest.get("resolved_profile") == "tier_1_research"
        and label_manifest.get("input_root") == "data/causally_gated_normalized"
        and label_manifest.get("output_root") == "data/labeled"
        and label_manifest.get("failure_count") == 0
        and label_manifest.get("warning_count") == 0
        and label_gate.get("status") == "PASS"
        and label_gate.get("manifest_path") == ACTIVE_CAUSAL_MANIFEST.as_posix()
        and label_gate.get("expected_market_year_count") == EXPECTED_MARKET_YEAR_COUNT,
        failure="v2 label manifest does not consume the active causal manifest gate",
        evidence=[V2_LABEL_MANIFEST.as_posix()],
        details={
            "label_status": None if label_manifest is None else label_manifest.get("status"),
            "label_gate": dict(label_gate),
        },
    )
    check(
        checks,
        failures,
        name="active_to_label_hashes_match_for_all_scoped_outputs",
        passed=active_hash_match_count == EXPECTED_MARKET_YEAR_COUNT,
        failure="active causal output hashes do not match label manifest input hashes for all scoped outputs",
        evidence=[ACTIVE_CAUSAL_MANIFEST.as_posix(), V2_LABEL_MANIFEST.as_posix()],
        details={
            "match_count": active_hash_match_count,
            "expected_count": EXPECTED_MARKET_YEAR_COUNT,
            "comparisons": hash_comparisons,
        },
    )

    readiness = payloads.get("readiness_post_exclusions")
    readiness_summary = readiness.get("summary") if isinstance(readiness, Mapping) else {}
    readiness_summary = readiness_summary if isinstance(readiness_summary, Mapping) else {}
    scoped_raw_missing = scoped_raw_without_causal(readiness)
    local_trade_counts = readiness_summary.get("local_trade_gap_gate_status_counts")
    local_trade_counts = local_trade_counts if isinstance(local_trade_counts, Mapping) else {}
    check(
        checks,
        failures,
        name="readiness_warn_preserved_without_active_scope_blocker",
        passed=readiness_summary.get("status") == "WARN"
        and readiness_summary.get("severe_blocker_count") == 0
        and scoped_raw_missing == []
        and readiness_summary.get("causal_rebuild_approved") is False
        and readiness_summary.get("data_mutation_performed") is False
        and readiness_summary.get("labels_features_wfa_predictions_modeling_approved") is False
        and readiness_summary.get("provider_network_calls") is False
        and local_trade_counts.get("NOT_RUN") is not None
        and local_trade_counts.get("SKIPPED") is not None,
        failure="readiness evidence is not WARN with zero active-scope blocker and false action flags",
        evidence=[READINESS_POST_EXCLUSIONS.as_posix()],
        details={
            "readiness_status": readiness_summary.get("status"),
            "severe_blocker_count": readiness_summary.get("severe_blocker_count"),
            "raw_without_causal_count": readiness_summary.get("raw_without_causal_count"),
            "scoped_raw_without_causal": scoped_raw_missing,
            "local_trade_gap_gate_status_counts": dict(local_trade_counts),
        },
    )

    target_timing = payloads.get("target_timing")
    target_summary = target_timing.get("summary") if isinstance(target_timing, Mapping) else {}
    target_summary = target_summary if isinstance(target_summary, Mapping) else {}
    check(
        checks,
        failures,
        name="target_timing_passes_active_scope",
        passed=target_timing is not None
        and target_timing.get("status") == "PASS_TARGET_TIMING_AUDIT"
        and target_summary.get("status") == "PASS_TARGET_TIMING_AUDIT"
        and target_summary.get("failure_count") == 0
        and target_summary.get("warning_count") == 1
        and target_summary.get("pair_count") == EXPECTED_MARKET_YEAR_COUNT
        and target_summary.get("row_count") == EXPECTED_TARGET_TIMING_ROWS
        and target_summary.get("row_key_mismatches") == 0
        and target_summary.get("entry_30m_not_after_ts") == 0
        and target_summary.get("entry_60m_not_after_ts") == 0
        and target_summary.get("exit_30m_offset_mismatches") == 0
        and target_summary.get("exit_60m_offset_mismatches") == 0
        and target_summary.get("same_session_30m_violations") == 0
        and target_summary.get("same_session_60m_violations") == 0
        and target_summary.get("completed_bar_convention_assumed") is True
        and target_summary.get("commands_executed") == 0
        and target_summary.get("data_model_or_prediction_mutation") is False,
        failure="target timing audit is not passed for active-scope causal/session evidence",
        evidence=[TARGET_TIMING.as_posix()],
        details=dict(target_summary),
    )

    spec_terms = text_contains(
        resolve_path(repo_root, PHASE2_SPEC),
        (
            "bar_available_ts",
            "phase2_ready",
            "causal_valid",
            "raw_row_present",
            "source_path",
            "source_file_hash",
            "source_row_number",
        ),
    )
    missing_terms = sorted(term for term, present in spec_terms.items() if not present)
    check(
        checks,
        failures,
        name="phase2_session_normalization_spec_contains_required_contract_terms",
        passed=not missing_terms,
        failure=f"Phase 2 session-normalization spec missing terms: {missing_terms}",
        evidence=[PHASE2_SPEC.as_posix()],
        details={"term_presence": spec_terms},
    )

    check(
        checks,
        failures,
        name="non_approval_flags_all_false",
        passed=all(value is False for value in NON_APPROVAL.values()),
        failure="one or more Phase 2 active-scope non-approval flags is true",
        details={"non_approval": dict(NON_APPROVAL)},
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "active_scoped_output_count": len(scoped_active),
        "active_hash_match_count": active_hash_match_count,
        "active_vs_label_hash_comparisons": hash_comparisons,
        "readiness_status": readiness_summary.get("status"),
        "readiness_severe_blocker_count": readiness_summary.get("severe_blocker_count"),
        "readiness_raw_without_causal_count": readiness_summary.get("raw_without_causal_count"),
        "scoped_raw_without_causal_count": len(scoped_raw_missing),
        "local_trade_gap_gate_status_counts": dict(local_trade_counts),
        "target_timing_status": target_summary.get("status"),
        "target_timing_pair_count": target_summary.get("pair_count"),
        "target_timing_row_count": target_summary.get("row_count"),
        "target_timing_row_key_mismatches": target_summary.get("row_key_mismatches"),
        "target_timing_entry_30m_not_after_ts": target_summary.get("entry_30m_not_after_ts"),
        "target_timing_entry_60m_not_after_ts": target_summary.get("entry_60m_not_after_ts"),
        "target_timing_exit_30m_offset_mismatches": target_summary.get(
            "exit_30m_offset_mismatches"
        ),
        "target_timing_exit_60m_offset_mismatches": target_summary.get(
            "exit_60m_offset_mismatches"
        ),
        "target_timing_same_session_30m_violations": target_summary.get(
            "same_session_30m_violations"
        ),
        "target_timing_same_session_60m_violations": target_summary.get(
            "same_session_60m_violations"
        ),
        "completed_bar_convention_assumed": target_summary.get(
            "completed_bar_convention_assumed"
        ),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "phase2-active-001-causal-session-active-scope-accepted",
            "severity": "Info",
            "finding": (
                "Active-scope causal/session evidence is accepted for "
                "6E/CL/ES/ZN 2023/2024 only."
            ),
            "verified_facts": [
                f"active_scoped_output_count={derived.get('active_scoped_output_count')}",
                f"active_hash_match_count={derived.get('active_hash_match_count')}",
                f"target_timing_pair_count={derived.get('target_timing_pair_count')}",
                f"target_timing_row_count={derived.get('target_timing_row_count')}",
            ],
            "limitation": "This is not full Phase 2 Master Audit acceptance.",
            "evidence_paths": [
                PHASE2_RECONCILIATION.as_posix(),
                ACTIVE_CAUSAL_MANIFEST.as_posix(),
                V2_LABEL_MANIFEST.as_posix(),
                TARGET_TIMING.as_posix(),
            ],
        },
        {
            "finding_id": "phase2-active-002-readiness-warn-caveats-preserved",
            "severity": "High",
            "finding": (
                "Broad Phase 2 readiness remains WARN while the active 2023/2024 "
                "Tier 1 core scope has no raw-without-causal blocker."
            ),
            "verified_facts": [
                f"readiness_status={derived.get('readiness_status')}",
                f"readiness_severe_blocker_count={derived.get('readiness_severe_blocker_count')}",
                f"scoped_raw_without_causal_count={derived.get('scoped_raw_without_causal_count')}",
                "local_trade_gap_gate_status_counts="
                f"{derived.get('local_trade_gap_gate_status_counts')}",
            ],
            "limitation": (
                "Unresolved 2025/2026 raw-without-causal rows and local-trade "
                "gap NOT_RUN/SKIPPED evidence remain caveats."
            ),
            "evidence_paths": [READINESS_POST_EXCLUSIONS.as_posix()],
        },
        {
            "finding_id": "phase2-active-003-session-normalization-audit-not-executed",
            "severity": "High",
            "finding": (
                "Full generated session-normalization audit execution remains false; "
                "this report accepts existing active-scope manifests, hash lineage, "
                "readiness caveats, and target-timing evidence only."
            ),
            "verified_facts": [
                "phase2_full_master_audit_accepted=false",
                "phase2_session_normalization_audit_accepted=false",
                "audit_phase2_causal_session_normalization_executed=false",
            ],
            "limitation": "No parquet audit or causal/session rebuild was run.",
            "evidence_paths": [PHASE2_SPEC.as_posix(), PHASE2_RECONCILIATION.as_posix()],
        },
        {
            "finding_id": "phase2-active-004-no-model-or-promotion-upgrade",
            "severity": "Info",
            "finding": (
                "Model trust, promotion, paper/live, final holdout, and production "
                "readiness remain false."
            ),
            "verified_facts": ["All non-approval flags in this report are false."],
            "limitation": "This report remediates only causal_session_active_scope.",
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
    paths = dict(REQUIRED_INPUTS)
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
        repo_root=repo_root,
        payloads=payloads,
        evidence=evidence,
        output_rel=output_rel,
        paths=paths,
    )
    failures = input_failures + check_failures
    status = PASS_STATUS if not failures else FAIL_STATUS
    findings = build_findings(derived)
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    phase2_classification = (
        "RUN_ACTIVE_SCOPE_PHASE2_CAUSAL_SESSION_RECONCILIATION"
        if status == PASS_STATUS
        else "FAILED_ACTIVE_SCOPE_PHASE2_CAUSAL_SESSION_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase2_active_scope_reconciliation_report_only",
            "phase": "Phase 2",
            "phase_name": "causal/session active-scope evidence",
            "reports_root": output_rel,
            "accepted_scope": "6E/CL/ES/ZN 2023/2024 active Tier 1 core only",
            "evidence_mode": "existing_local_json_md_repo_evidence_only",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "market_year_count": EXPECTED_MARKET_YEAR_COUNT,
            "data_model_scope": "none",
            "provider_scope": "none",
            "allowed_inputs": [
                rel(resolve_path(repo_root, path), repo_root) for path in paths.values()
            ],
            "full_phase2_master_audit_acceptance": False,
        },
        "summary": {
            "status": status,
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase2_master_audit_status": phase2_classification,
            "causal_session_active_scope_ready": status == PASS_STATUS,
            "phase2_active_scope_ready": status == PASS_STATUS,
            "phase2_limited_active_hash_lineage_ready": status == PASS_STATUS,
            "phase2_full_master_audit_accepted": False,
            "phase2_session_normalization_audit_accepted": False,
            "phase2_build_or_readiness_accepted": False,
            "session_normalization_audit_execution_accepted": False,
            "active_scoped_output_count": derived.get("active_scoped_output_count"),
            "active_hash_match_count": derived.get("active_hash_match_count"),
            "active_causal_manifest_status": dotted_get(
                payloads.get("active_causal_manifest"), "status"
            ),
            "active_causal_pair_count": dotted_get(
                payloads.get("active_causal_manifest"), "summary.active_causal_pair_count"
            ),
            "readiness_status": derived.get("readiness_status"),
            "readiness_severe_blocker_count": derived.get("readiness_severe_blocker_count"),
            "readiness_raw_without_causal_count": derived.get(
                "readiness_raw_without_causal_count"
            ),
            "scoped_raw_without_causal_count": derived.get(
                "scoped_raw_without_causal_count"
            ),
            "local_trade_gap_gate_status_counts": derived.get(
                "local_trade_gap_gate_status_counts"
            ),
            "target_timing_status": derived.get("target_timing_status"),
            "target_timing_pair_count": derived.get("target_timing_pair_count"),
            "target_timing_row_count": derived.get("target_timing_row_count"),
            "target_timing_row_key_mismatches": derived.get(
                "target_timing_row_key_mismatches"
            ),
            "target_timing_entry_30m_not_after_ts": derived.get(
                "target_timing_entry_30m_not_after_ts"
            ),
            "target_timing_entry_60m_not_after_ts": derived.get(
                "target_timing_entry_60m_not_after_ts"
            ),
            "target_timing_exit_30m_offset_mismatches": derived.get(
                "target_timing_exit_30m_offset_mismatches"
            ),
            "target_timing_exit_60m_offset_mismatches": derived.get(
                "target_timing_exit_60m_offset_mismatches"
            ),
            "target_timing_same_session_30m_violations": derived.get(
                "target_timing_same_session_30m_violations"
            ),
            "target_timing_same_session_60m_violations": derived.get(
                "target_timing_same_session_60m_violations"
            ),
            "completed_bar_convention_assumed": derived.get(
                "completed_bar_convention_assumed"
            ),
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
            "statistical_validity_ready": False,
            "operational_resilience_ready": False,
            **dict(NON_APPROVAL),
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
            "finding_counts": finding_counts(findings),
        },
        "input_evidence": evidence,
        "checks": checks,
        "findings": findings,
        "active_vs_label_hash_comparisons": derived.get(
            "active_vs_label_hash_comparisons", []
        ),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "existing Phase 2 reconciliation is passed limited active-scope evidence",
                "active causal manifest gate is PASS_MANIFEST_GATE_READY_NO_EXECUTION",
                "active causal manifest is PASS for exactly 6E/CL/ES/ZN 2023/2024",
                "v2 label manifest consumes the active causal manifest gate",
                "active causal output hashes match label manifest input hashes for all 8 scoped market-years",
                "readiness remains WARN with severe blockers 0 and scoped raw-without-causal 0",
                "target timing audit is PASS over the exact active scope and preserves completed-bar caveat",
                "full Phase 2 Master Audit acceptance remains false",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "active manifest or label hash mismatch",
                "target timing failure or nonzero timing mismatch",
                "scoped 2023/2024 raw-without-causal blocker",
                "severe readiness blocker",
                "full Phase 2/model-trust/promotion/paper-live/production upgrade",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Rerun the Master Audit gap remediation evidence map against this report-only "
            "Phase 2 active-scope reconciliation; do not run Phase 2 readiness/build, "
            "causal rebuilds, parquet audits, data/model commands, or promotion work."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Phase 2 Active-Scope Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 2 status: `{summary['phase2_master_audit_status']}`",
        f"- Causal/session active-scope ready: `{summary['causal_session_active_scope_ready']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Active scoped outputs: `{summary['active_scoped_output_count']}`",
        f"- Active-to-label hash matches: `{summary['active_hash_match_count']}`",
        f"- Readiness status: `{summary['readiness_status']}`",
        f"- Scoped raw-without-causal count: `{summary['scoped_raw_without_causal_count']}`",
        f"- Target timing status: `{summary['target_timing_status']}`",
        f"- Target timing rows: `{summary['target_timing_row_count']}`",
        f"- Completed-bar convention assumed: `{summary['completed_bar_convention_assumed']}`",
        f"- Full Phase 2 Master Audit accepted: `{summary['phase2_full_master_audit_accepted']}`",
        f"- Session-normalization audit accepted: `{summary['phase2_session_normalization_audit_accepted']}`",
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
    lines.extend(["", "## Active Hash Lineage", ""])
    for item in report.get("active_vs_label_hash_comparisons", []):
        lines.append(
            f"- `{item.get('path')}` active_matches_label=`{item.get('matches')}`"
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
            "- This reconciliation did not run Phase 2 readiness/build, causal rebuilds, parquet audits, label/feature rebuilds, data/model commands, WFA/modeling, predictions, Phase 8 refresh, provider/network calls, promotion, artifact freeze, final holdout, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, or model artifacts.",
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
        f"causal_session_active_scope_ready="
        f"{report['summary']['causal_session_active_scope_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
