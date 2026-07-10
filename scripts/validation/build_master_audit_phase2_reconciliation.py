#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 2 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run
Phase 2 build/readiness, audit Phase 2 causal/session normalization, convert
raw data, read parquet, run WFA/modeling, generate predictions, refresh Phase 8,
call providers/network, promote, freeze, touch holdout, paper/live, clean up
files, stage, commit, or push.
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
STAGE = "master_audit_phase2_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_MARKET_YEAR_COUNT = 8

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_PHASE1B = Path(
    "reports/master_audit/master_audit_phase1b_reconciliation_20260709/"
    "master_audit_phase1b_reconciliation.json"
)
DEFAULT_PHASE6 = Path(
    "reports/master_audit/master_audit_phase6_reconciliation_20260709/"
    "master_audit_phase6_reconciliation.json"
)
DEFAULT_PHASE7 = Path(
    "reports/master_audit/master_audit_phase7_reconciliation_20260709/"
    "master_audit_phase7_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase2_reconciliation_20260709")
REPORT_JSON = "master_audit_phase2_reconciliation.json"
REPORT_MD = "master_audit_phase2_reconciliation.md"

PHASE2_SPEC = Path("docs/phase2_causal_session_normalization_spec.md")
LEGACY_CAUSAL_MANIFEST = Path("reports/causal_base/causal_base_manifest.json")
LEGACY_CAUSAL_VALIDATION = Path("reports/causal_base/causal_base_validation.json")
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

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "phase2_spec": PHASE2_SPEC,
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "phase1b_reconciliation": DEFAULT_PHASE1B,
    "phase6_reconciliation": DEFAULT_PHASE6,
    "phase7_reconciliation": DEFAULT_PHASE7,
    "legacy_causal_manifest": LEGACY_CAUSAL_MANIFEST,
    "legacy_causal_validation": LEGACY_CAUSAL_VALIDATION,
    "active_causal_gate_report": ACTIVE_CAUSAL_GATE_REPORT,
    "active_causal_manifest": ACTIVE_CAUSAL_MANIFEST,
    "readiness_post_exclusions": READINESS_POST_EXCLUSIONS,
    "v2_label_manifest": V2_LABEL_MANIFEST,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase2_build_or_readiness_executed": False,
    "audit_phase2_causal_session_normalization_executed": False,
    "phase1b_conversion_executed": False,
    "data_model_commands_executed": False,
    "dbn_read_executed": False,
    "raw_parquet_read_executed": False,
    "causal_parquet_read_executed": False,
    "label_parquet_read_executed": False,
    "feature_parquet_read_executed": False,
    "prediction_parquet_read_executed": False,
    "model_artifact_read_executed": False,
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
    "hardened_split_candidate_consumed": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


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
        rows = payload.get("files")
    if not isinstance(rows, list):
        return []
    pairs = set(expected_pairs())
    scoped: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        pair = (row.get("market"), as_int(row.get("year")))
        if pair in pairs:
            scoped.append(row)
    return scoped


def text_contains(path: Path, terms: Sequence[str]) -> dict[str, bool]:
    try:
        text = path.read_text(encoding="utf-8").lower()
    except Exception:
        return {term: False for term in terms}
    return {term: term.lower() in text for term in terms}


def row_by_area(run_status: Mapping[str, Any] | None, area: str) -> Mapping[str, Any] | None:
    rows = dotted_get(run_status, "run_status_table")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("audit_area") == area:
            return row
    return None


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
    json_fields: dict[str, dict[str, str]] = {
        "run_status": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
        },
        "overview": {"status": "status", "failure_count": "summary.failure_count"},
        "phase1b_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase1b_master_audit_status": "summary.phase1b_master_audit_status",
            "phase2_accepted": "summary.phase2_accepted",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
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
        "legacy_causal_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "warning_count": "warning_count",
            "failure_count": "failure_count",
            "selected_input_count": "selected_input_count",
            "output_root": "output_root",
        },
        "legacy_causal_validation": {
            "status": "status",
            "profile": "profile",
            "warning_count": "warning_count",
            "failure_count": "failure_count",
        },
        "active_causal_gate_report": {
            "status": "status",
            "manifest_status": "summary.manifest_status",
            "gate_check_status": "summary.gate_check_status",
            "active_causal_pair_count": "summary.active_causal_pair_count",
            "raw_to_causal_status": "summary.raw_to_causal_status",
            "provider_network_calls": "summary.provider_network_calls",
            "data_mutation_performed": "summary.data_mutation_performed",
        },
        "active_causal_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "output_count": "summary.output_count",
            "fail_count": "summary.fail_count",
            "warn_count": "summary.warn_count",
            "output_root": "output_root",
        },
        "readiness_post_exclusions": {
            "status": "summary.status",
            "severe_blocker_count": "summary.severe_blocker_count",
            "raw_without_causal_count": "summary.raw_without_causal_count",
            "local_trade_gap_gate_status_counts": "summary.local_trade_gap_gate_status_counts",
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


def scoped_hash_comparison(
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


def legacy_hash_comparison(
    *,
    legacy_manifest: Mapping[str, Any] | None,
    active_manifest: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    legacy_hashes = output_hashes(legacy_manifest)
    active_hashes = output_hashes(active_manifest)
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        path = causal_path(market, year)
        legacy_hash = legacy_hashes.get(path)
        active_hash = active_hashes.get(path)
        rows.append(
            {
                "market": market,
                "year": year,
                "path": path,
                "legacy_hash": legacy_hash,
                "active_hash": active_hash,
                "matches": legacy_hash is not None and legacy_hash == active_hash,
                "legacy_missing": legacy_hash is None,
                "active_missing": active_hash is None,
            }
        )
    return rows


def scoped_raw_without_causal(readiness: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows = as_list(None if not isinstance(readiness, Mapping) else readiness.get("raw_without_causal"))
    result: list[dict[str, Any]] = []
    pair_set = set(expected_pairs())
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        market = row.get("market")
        year = as_int(row.get("year"))
        if (market, year) in pair_set:
            result.append(dict(row))
    return result


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
        failure=f"missing required Phase 2 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 2 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    phase1b = payloads.get("phase1b_reconciliation")
    phase6 = payloads.get("phase6_reconciliation")
    phase7 = payloads.get("phase7_reconciliation")
    phase2_row = row_by_area(run_status, "Phase 2")
    check(
        checks,
        failures,
        name="master_audit_inputs_are_passed_report_only_evidence",
        passed=run_status is not None
        and overview is not None
        and phase1b is not None
        and phase6 is not None
        and phase7 is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and phase1b.get("status") == "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"
        and phase6.get("status") == "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY"
        and phase7.get("status") == "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        failure="run-status, overview, Phase 1B, Phase 6, or Phase 7 input is not passed report-only evidence",
        evidence=[
            DEFAULT_RUN_STATUS.as_posix(),
            DEFAULT_OVERVIEW.as_posix(),
            DEFAULT_PHASE1B.as_posix(),
            DEFAULT_PHASE6.as_posix(),
            DEFAULT_PHASE7.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "phase1b": None if phase1b is None else phase1b.get("status"),
            "phase6": None if phase6 is None else phase6.get("status"),
            "phase7": None if phase7 is None else phase7.get("status"),
        },
    )
    check(
        checks,
        failures,
        name="phase2_previously_not_accepted_in_master_audit_ledger",
        passed=phase2_row is not None
        and phase2_row.get("run_status") == "NOT_RUN"
        and phase2_row.get("detail_status") == "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
        failure="run-status Phase 2 row does not match expected pre-reconciliation NOT_RUN state",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"pre_existing_phase2_row": dict(phase2_row or {})},
    )
    check(
        checks,
        failures,
        name="phase1b_did_not_accept_phase2_or_model_trust",
        passed=phase1b is not None
        and dotted_get(phase1b, "summary.phase2_accepted") is False
        and dotted_get(phase1b, "summary.model_trust_ready") is False
        and dotted_get(phase1b, "summary.promotion_allowed") is False,
        failure="Phase 1B reconciliation unexpectedly accepted Phase 2 or model trust",
        evidence=[DEFAULT_PHASE1B.as_posix()],
        details={
            "phase2_accepted": dotted_get(phase1b, "summary.phase2_accepted"),
            "model_trust_ready": dotted_get(phase1b, "summary.model_trust_ready"),
            "promotion_allowed": dotted_get(phase1b, "summary.promotion_allowed"),
        },
    )

    master_terms = text_contains(
        resolve_path(repo_root, Path("MASTER_AUDIT.md")),
        (
            "session normalization",
            "missing-data markers",
            "indicator warmup",
            "bar_available_ts",
            "invalid-row",
            "row counts",
            "source_timestamp <= prediction_timestamp",
        ),
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
    missing_terms = sorted(
        [f"MASTER_AUDIT.md:{term}" for term, present in master_terms.items() if not present]
        + [f"{PHASE2_SPEC.as_posix()}:{term}" for term, present in spec_terms.items() if not present]
    )
    check(
        checks,
        failures,
        name="phase2_contract_terms_present",
        passed=not missing_terms,
        failure=f"Phase 2 contract terms missing from documentation: {missing_terms}",
        evidence=["MASTER_AUDIT.md", PHASE2_SPEC.as_posix()],
        details={"missing_terms": missing_terms},
    )

    active_gate = payloads.get("active_causal_gate_report")
    active_manifest = payloads.get("active_causal_manifest")
    label_manifest = payloads.get("v2_label_manifest")
    legacy_manifest = payloads.get("legacy_causal_manifest")
    legacy_validation = payloads.get("legacy_causal_validation")
    readiness = payloads.get("readiness_post_exclusions")

    check(
        checks,
        failures,
        name="active_causal_manifest_gate_passes_report_only",
        passed=active_gate is not None
        and active_gate.get("status") == "PASS_MANIFEST_GATE_READY_NO_EXECUTION"
        and dotted_get(active_gate, "summary.manifest_status") == "PASS"
        and dotted_get(active_gate, "summary.gate_check_status") == "PASS"
        and as_bool(dotted_get(active_gate, "summary.provider_network_calls")) is False
        and as_bool(dotted_get(active_gate, "summary.data_mutation_performed")) is False
        and as_bool(dotted_get(active_gate, "summary.feature_wfa_prediction_modeling_performed"))
        is False,
        failure="active causal manifest gate is not passed report-only evidence",
        evidence=[ACTIVE_CAUSAL_GATE_REPORT.as_posix()],
        details={
            "status": None if active_gate is None else active_gate.get("status"),
            "manifest_status": dotted_get(active_gate, "summary.manifest_status"),
            "gate_check_status": dotted_get(active_gate, "summary.gate_check_status"),
            "provider_network_calls": dotted_get(active_gate, "summary.provider_network_calls"),
            "data_mutation_performed": dotted_get(active_gate, "summary.data_mutation_performed"),
            "feature_wfa_prediction_modeling_performed": dotted_get(
                active_gate, "summary.feature_wfa_prediction_modeling_performed"
            ),
        },
    )

    scoped_active = scoped_outputs(active_manifest)
    scoped_active_pairs = {(row.get("market"), as_int(row.get("year"))) for row in scoped_active}
    active_rows_ready = all(
        row.get("status") == "PASS"
        and row.get("failure_count") == 0
        and row.get("warning_count") == 0
        and row.get("output_path") == causal_path(str(row.get("market")), int(row.get("year")))
        for row in scoped_active
        if as_int(row.get("year")) is not None
    )
    check(
        checks,
        failures,
        name="active_causal_manifest_scoped_outputs_are_exact_pass",
        passed=active_manifest is not None
        and active_manifest.get("status") == "PASS"
        and active_manifest.get("profile") == "all_causal"
        and active_manifest.get("output_root") == "data/causally_gated_normalized"
        and len(scoped_active) == EXPECTED_MARKET_YEAR_COUNT
        and scoped_active_pairs == set(expected_pairs())
        and active_rows_ready,
        failure="active causal manifest does not contain exact PASS scoped outputs",
        evidence=[ACTIVE_CAUSAL_MANIFEST.as_posix()],
        details={
            "status": None if active_manifest is None else active_manifest.get("status"),
            "profile": None if active_manifest is None else active_manifest.get("profile"),
            "output_root": None if active_manifest is None else active_manifest.get("output_root"),
            "scoped_output_count": len(scoped_active),
            "scoped_pairs": sorted([f"{market}:{year}" for market, year in scoped_active_pairs]),
        },
    )

    active_vs_label = scoped_hash_comparison(
        active_manifest=active_manifest,
        label_manifest=label_manifest,
    )
    active_hash_match_count = sum(1 for row in active_vs_label if row["matches"])
    label_gate = label_manifest.get("causal_base_manifest_gate") if isinstance(label_manifest, Mapping) else {}
    check(
        checks,
        failures,
        name="v2_label_manifest_consumes_active_causal_manifest_gate",
        passed=label_manifest is not None
        and label_manifest.get("status") == "PASS"
        and label_manifest.get("input_root") == "data/causally_gated_normalized"
        and set(label_manifest.get("markets", [])) == set(EXPECTED_MARKETS)
        and set(label_manifest.get("years", [])) == set(EXPECTED_YEARS)
        and label_manifest.get("failure_count") == 0
        and label_manifest.get("warning_count") == 0
        and isinstance(label_gate, Mapping)
        and label_gate.get("status") == "PASS"
        and label_gate.get("manifest_path") == ACTIVE_CAUSAL_MANIFEST.as_posix()
        and label_gate.get("expected_market_year_count") == EXPECTED_MARKET_YEAR_COUNT,
        failure="v2 label manifest does not consume the expected active causal manifest gate",
        evidence=[V2_LABEL_MANIFEST.as_posix(), ACTIVE_CAUSAL_MANIFEST.as_posix()],
        details={
            "label_status": None if label_manifest is None else label_manifest.get("status"),
            "label_input_root": None if label_manifest is None else label_manifest.get("input_root"),
            "label_gate": dict(label_gate) if isinstance(label_gate, Mapping) else label_gate,
        },
    )
    check(
        checks,
        failures,
        name="active_causal_hashes_match_v2_label_inputs",
        passed=active_hash_match_count == EXPECTED_MARKET_YEAR_COUNT,
        failure="active causal manifest hashes do not match v2 label manifest input hashes",
        evidence=[ACTIVE_CAUSAL_MANIFEST.as_posix(), V2_LABEL_MANIFEST.as_posix()],
        details={
            "match_count": active_hash_match_count,
            "expected_count": EXPECTED_MARKET_YEAR_COUNT,
            "comparisons": active_vs_label,
        },
    )

    legacy_vs_active = legacy_hash_comparison(
        legacy_manifest=legacy_manifest,
        active_manifest=active_manifest,
    )
    legacy_hash_mismatch_count = sum(
        1 for row in legacy_vs_active if row["legacy_hash"] and row["active_hash"] and not row["matches"]
    )
    legacy_hash_match_count = sum(1 for row in legacy_vs_active if row["matches"])
    legacy_scoped = scoped_outputs(legacy_manifest)
    legacy_validation_scoped = scoped_outputs(legacy_validation)
    check(
        checks,
        failures,
        name="legacy_reports_causal_base_classified_stale_historical",
        passed=legacy_manifest is not None
        and legacy_validation is not None
        and legacy_manifest.get("status") == "WARN"
        and legacy_validation.get("status") == "WARN"
        and len(legacy_scoped) == EXPECTED_MARKET_YEAR_COUNT
        and len(legacy_validation_scoped) == EXPECTED_MARKET_YEAR_COUNT
        and legacy_hash_mismatch_count == EXPECTED_MARKET_YEAR_COUNT
        and legacy_hash_match_count == 0,
        failure="legacy reports/causal_base evidence is not classified as stale historical hash evidence",
        evidence=[LEGACY_CAUSAL_MANIFEST.as_posix(), LEGACY_CAUSAL_VALIDATION.as_posix()],
        details={
            "legacy_manifest_status": None if legacy_manifest is None else legacy_manifest.get("status"),
            "legacy_validation_status": None if legacy_validation is None else legacy_validation.get("status"),
            "legacy_scoped_output_count": len(legacy_scoped),
            "legacy_validation_scoped_output_count": len(legacy_validation_scoped),
            "hash_match_count": legacy_hash_match_count,
            "hash_mismatch_count": legacy_hash_mismatch_count,
            "comparisons": legacy_vs_active,
        },
    )

    scoped_raw_missing = scoped_raw_without_causal(readiness)
    readiness_summary = readiness.get("summary") if isinstance(readiness, Mapping) else {}
    readiness_summary = readiness_summary if isinstance(readiness_summary, Mapping) else {}
    check(
        checks,
        failures,
        name="broad_phase2_readiness_warn_preserved_without_scoped_2023_2024_blocker",
        passed=readiness_summary.get("status") == "WARN"
        and readiness_summary.get("severe_blocker_count") == 0
        and scoped_raw_missing == []
        and readiness_summary.get("causal_rebuild_approved") is False
        and readiness_summary.get("data_mutation_performed") is False
        and readiness_summary.get("labels_features_wfa_predictions_modeling_approved") is False,
        failure="Phase 2 readiness evidence is not preserved as broad WARN without scoped 2023/2024 blocker",
        evidence=[READINESS_POST_EXCLUSIONS.as_posix()],
        details={
            "readiness_status": readiness_summary.get("status"),
            "severe_blocker_count": readiness_summary.get("severe_blocker_count"),
            "raw_without_causal_count": readiness_summary.get("raw_without_causal_count"),
            "scoped_raw_without_causal": scoped_raw_missing,
            "local_trade_gap_gate_status_counts": readiness_summary.get(
                "local_trade_gap_gate_status_counts"
            ),
        },
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "active_hash_match_count": active_hash_match_count,
        "active_vs_label_hash_comparisons": active_vs_label,
        "legacy_hash_match_count": legacy_hash_match_count,
        "legacy_hash_mismatch_count": legacy_hash_mismatch_count,
        "legacy_vs_active_hash_comparisons": legacy_vs_active,
        "active_scoped_output_count": len(scoped_active),
        "readiness_status": readiness_summary.get("status"),
        "readiness_severe_blocker_count": readiness_summary.get("severe_blocker_count"),
        "readiness_raw_without_causal_count": readiness_summary.get("raw_without_causal_count"),
        "scoped_raw_without_causal_count": len(scoped_raw_missing),
        "local_trade_gap_gate_status_counts": readiness_summary.get(
            "local_trade_gap_gate_status_counts"
        ),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "phase2-001-active-v2-causal-hash-lineage-accepted-limited",
            "severity": "Info",
            "finding": "Scoped active v2 Phase 2 causal hash-lineage evidence is accepted for 6E/CL/ES/ZN 2023/2024 only.",
            "verified_facts": [
                f"active_scoped_output_count={derived.get('active_scoped_output_count')}",
                f"active_hash_match_count={derived.get('active_hash_match_count')}",
                "The v2 Phase 3 label manifest input hashes match the active causal manifest output hashes.",
            ],
            "limitation": "This is not a full Phase 2 session-normalization audit and does not read parquet.",
            "evidence_paths": [ACTIVE_CAUSAL_MANIFEST.as_posix(), V2_LABEL_MANIFEST.as_posix()],
        },
        {
            "finding_id": "phase2-002-legacy-causal-base-evidence-is-stale",
            "severity": "High",
            "finding": "The legacy reports/causal_base manifest and validation are historical and stale for the active v2 causal files.",
            "verified_facts": [
                f"legacy_hash_mismatch_count={derived.get('legacy_hash_mismatch_count')}",
                f"legacy_hash_match_count={derived.get('legacy_hash_match_count')}",
            ],
            "limitation": "Legacy WARN reports cannot be used as current Phase 2 proof for the active v2 line.",
            "evidence_paths": [LEGACY_CAUSAL_MANIFEST.as_posix(), LEGACY_CAUSAL_VALIDATION.as_posix()],
        },
        {
            "finding_id": "phase2-003-broad-phase2-remains-not-fully-accepted",
            "severity": "Critical",
            "finding": "Broad/full Phase 2 Master Audit acceptance remains false.",
            "verified_facts": [
                f"readiness_status={derived.get('readiness_status')}",
                f"readiness_severe_blocker_count={derived.get('readiness_severe_blocker_count')}",
                f"scoped_raw_without_causal_count={derived.get('scoped_raw_without_causal_count')}",
                f"local_trade_gap_gate_status_counts={derived.get('local_trade_gap_gate_status_counts')}",
            ],
            "limitation": "A separate bounded Phase 2 audit would be required for full causal/session-normalization acceptance.",
            "evidence_paths": [READINESS_POST_EXCLUSIONS.as_posix(), DEFAULT_RUN_STATUS.as_posix()],
        },
        {
            "finding_id": "phase2-004-no-data-model-or-promotion-actions",
            "severity": "Info",
            "finding": "No Phase 2 build/readiness, parquet read, WFA/modeling, prediction, Phase 8, promotion, holdout, paper/live, cleanup, staging, commit, or push action is authorized.",
            "verified_facts": ["All non-approval flags in this report are false."],
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
    output_rel = rel(reports_root, repo_root)
    evidence = required_input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    checks, check_failures, derived = build_checks(
        repo_root=repo_root,
        payloads=payloads,
        evidence=evidence,
        output_rel=output_rel,
        paths=paths,
    )
    failures = input_failures + check_failures
    findings = build_findings(derived)
    status = PASS_STATUS if not failures else FAIL_STATUS
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    phase2_classification = (
        "RUN_LIMITED_SCOPE_PHASE2_ACTIVE_CAUSAL_HASH_LINEAGE_RECONCILIATION"
        if status == PASS_STATUS
        else "FAILED_PHASE2_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase2_reconciliation_report_only",
            "phase": "Phase 2",
            "phase_name": "Causal/session-normalized base data and readiness",
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "market_year_count": EXPECTED_MARKET_YEAR_COUNT,
            "active_causal_manifest": ACTIVE_CAUSAL_MANIFEST.as_posix(),
            "legacy_causal_manifest": LEGACY_CAUSAL_MANIFEST.as_posix(),
            "full_phase2_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase2_master_audit_status": phase2_classification,
            "phase2_limited_active_hash_lineage_ready": status == PASS_STATUS,
            "phase2_full_master_audit_accepted": False,
            "phase2_session_normalization_audit_accepted": False,
            "phase2_build_or_readiness_accepted": False,
            "legacy_causal_base_classification": "STALE_HISTORICAL_EVIDENCE_HASH_MISMATCH",
            "active_scoped_output_count": derived.get("active_scoped_output_count"),
            "active_hash_match_count": derived.get("active_hash_match_count"),
            "legacy_hash_match_count": derived.get("legacy_hash_match_count"),
            "legacy_hash_mismatch_count": derived.get("legacy_hash_mismatch_count"),
            "readiness_status": derived.get("readiness_status"),
            "readiness_severe_blocker_count": derived.get("readiness_severe_blocker_count"),
            "readiness_raw_without_causal_count": derived.get("readiness_raw_without_causal_count"),
            "scoped_raw_without_causal_count": derived.get("scoped_raw_without_causal_count"),
            "local_trade_gap_gate_status_counts": derived.get("local_trade_gap_gate_status_counts"),
            "current_line_classification": dotted_get(
                payloads.get("run_status"), "summary.current_line_classification"
            ),
            "current_split_classification": dotted_get(
                payloads.get("run_status"), "summary.current_split_classification"
            ),
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
        "active_vs_label_hash_comparisons": derived.get("active_vs_label_hash_comparisons", []),
        "legacy_vs_active_hash_comparisons": derived.get("legacy_vs_active_hash_comparisons", []),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required JSON/MD evidence is readable",
                "run-status, overview, Phase 1B, Phase 6, and Phase 7 reconciliation reports are passed report-only inputs",
                "pre-existing Phase 2 ledger row is NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
                "Phase 2 contract terms are present in MASTER_AUDIT.md and the Phase 2 spec",
                "active causal manifest gate is PASS_MANIFEST_GATE_READY_NO_EXECUTION",
                "active causal manifest contains exact PASS outputs for 6E/CL/ES/ZN 2023/2024",
                "v2 Phase 3 label manifest consumes the active causal manifest gate",
                "active causal output hashes match v2 label manifest input hashes for all 8 market-years",
                "legacy reports/causal_base hashes are classified as stale historical evidence",
                "broad readiness remains WARN without scoped 2023/2024 raw-without-causal blockers",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "active/label hash mismatch for any scoped causal file",
                "legacy reports/causal_base evidence is treated as current active proof",
                "scoped raw-without-causal blocker appears for 6E/CL/ES/ZN 2023/2024",
                "full Phase 2 Master Audit, model-trust, promotion, holdout, or paper/live readiness is upgraded",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan exactly one next bounded Master Audit report-only reconciliation area from the updated "
            "run-status and Phase 1B/2/6/7 evidence; do not run data/model/phase commands without "
            "separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 2 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 2 status: `{summary.get('phase2_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Active hash matches: `{summary.get('active_hash_match_count')}`",
        f"- Legacy hash mismatches: `{summary.get('legacy_hash_mismatch_count')}`",
        f"- Legacy causal base classification: `{summary.get('legacy_causal_base_classification')}`",
        f"- Full Phase 2 Master Audit accepted: `{summary.get('phase2_full_master_audit_accepted')}`",
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
    lines.extend(["", "## Active Hash Lineage", ""])
    for item in report.get("active_vs_label_hash_comparisons", []):
        lines.append(
            f"- `{item.get('path')}` active_matches_label=`{item.get('matches')}`"
        )
    lines.extend(["", "## Legacy Staleness", ""])
    for item in report.get("legacy_vs_active_hash_comparisons", []):
        lines.append(
            f"- `{item.get('path')}` legacy_matches_active=`{item.get('matches')}`"
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
            "- This reconciliation did not run Phase 2 build/readiness, audit_phase2_causal_session_normalization, Phase 1B conversion, phase audits, WFA/modeling, predictions, Phase 8, provider/network calls, promotion, freeze, holdout, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, or model artifacts.",
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
        f"phase2_status={report['summary']['phase2_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
