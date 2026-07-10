#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 4 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run
Phase 4 feature builds, rerun feature leakage audits, build labels, build
causal data, read parquet, run WFA/modeling, generate predictions, refresh
Phase 8, call providers/network, promote, freeze, touch holdout, paper/live,
clean up files, stage, commit, or push.
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
STAGE = "master_audit_phase4_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE4_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE4_RECONCILIATION_REPORT_ONLY"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_MARKET_YEAR_COUNT = 8
EXPECTED_FEATURE_COUNT = 114
EXPECTED_TARGET_COUNT = 97
EXPECTED_FEATURE_MATRIX_COLUMNS = 342
EXPECTED_LEAKAGE_VERDICT = "PASS_NO_FEATURE_LEAKAGE_FOUND_UNDER_COMPLETED_BAR_CONVENTION"
EXPECTED_FEATURE_PLACEMENT_STATUS = "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM"
EXPECTED_LEAKAGE_DEDUCTIONS = (
    "proof depends on completed-current-bar prediction convention",
    "per-feature source chains are static code inspection plus conservative timestamp assignment, not per-cell replay",
)
REQUIRED_FEATURE_AUDIT_FIELDS = (
    "feature",
    "family",
    "source_column_artifact",
    "availability_timestamp",
    "lookback_window",
    "economic_rationale",
    "leakage_risk",
    "train_only_transform_status",
    "drift_decay_check_status",
)

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
DEFAULT_PHASE2 = Path(
    "reports/master_audit/master_audit_phase2_reconciliation_20260709/"
    "master_audit_phase2_reconciliation.json"
)
DEFAULT_PHASE3 = Path(
    "reports/master_audit/master_audit_phase3_reconciliation_20260709/"
    "master_audit_phase3_reconciliation.json"
)
DEFAULT_PHASE6 = Path(
    "reports/master_audit/master_audit_phase6_reconciliation_20260709/"
    "master_audit_phase6_reconciliation.json"
)
DEFAULT_PHASE7 = Path(
    "reports/master_audit/master_audit_phase7_reconciliation_20260709/"
    "master_audit_phase7_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase4_reconciliation_20260709")
REPORT_JSON = "master_audit_phase4_reconciliation.json"
REPORT_MD = "master_audit_phase4_reconciliation.md"

ACTIVE_LABEL_MANIFEST = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_active_tier1_core_manifest_for_phase4/"
    "label_manifest.json"
)
FEATURE_MANIFEST = Path(
    "reports/features_baseline/phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "baseline_feature_manifest.json"
)
ACTIVE_FEATURE_PLACEMENT = Path(
    "reports/features_baseline/phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "post_active_feature_hashes.json"
)
FEATURE_LEAKAGE_AUDIT = Path(
    "reports/model_trust_audit/final_feature_matrix_leakage_20260709/"
    "final_feature_matrix_leakage_audit.json"
)
FEATURE_COLS = Path("data/feature_matrices/feature_cols.json")
TARGET_COLS = Path("data/feature_matrices/target_cols.json")

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "phase1b_reconciliation": DEFAULT_PHASE1B,
    "phase2_reconciliation": DEFAULT_PHASE2,
    "phase3_reconciliation": DEFAULT_PHASE3,
    "phase6_reconciliation": DEFAULT_PHASE6,
    "phase7_reconciliation": DEFAULT_PHASE7,
    "active_label_manifest": ACTIVE_LABEL_MANIFEST,
    "feature_manifest": FEATURE_MANIFEST,
    "active_feature_placement": ACTIVE_FEATURE_PLACEMENT,
    "feature_leakage_audit": FEATURE_LEAKAGE_AUDIT,
    "feature_cols": FEATURE_COLS,
    "target_cols": TARGET_COLS,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase4_feature_build_executed": False,
    "feature_leakage_audit_rerun_executed": False,
    "phase3_label_build_executed": False,
    "phase2_build_or_readiness_executed": False,
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


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def list_as_set(value: Any) -> set[Any]:
    return set(as_list(value))


def expected_pairs() -> list[tuple[str, int]]:
    return [(market, year) for market in EXPECTED_MARKETS for year in EXPECTED_YEARS]


def active_label_path(market: str, year: int) -> str:
    return f"data/labeled/{market}/{year}.parquet"


def feature_matrix_path(market: str, year: int) -> str:
    return f"data/feature_matrices/{market}/{year}.parquet"


def file_hashes(payload: Mapping[str, Any] | None, key: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    hashes = payload.get(key)
    return hashes if isinstance(hashes, Mapping) else {}


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


def load_json_list(path: Path) -> tuple[list[str], str | None]:
    if not path.is_file():
        return [], f"missing: {path.as_posix()}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], f"unreadable JSON {path.as_posix()}: {exc}"
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return [], f"JSON is not a string list: {path.as_posix()}"
    return value, None


def registry_evidence_file(
    *,
    repo_root: Path,
    relative_path: str | Path,
    dirty_map: Mapping[str, str],
) -> dict[str, Any]:
    path = resolve_path(repo_root, relative_path)
    path_rel = rel(path, repo_root)
    digest = inventory.sha256_file(path)
    marker = inventory.path_dirty_marker(path_rel, dirty_map)
    read_error: str | None = None
    extracted: dict[str, Any] = {}
    if digest is None:
        read_error = f"missing: {path_rel}"
        state = "missing"
    else:
        values, error = load_json_list(path)
        read_error = error
        extracted = {"count": len(values)}
        state = "unknown" if error or marker else "current"
    return {
        "path": path_rel,
        "exists": digest is not None,
        "sha256": digest,
        "state": state,
        "git_status": marker,
        "read_error": read_error,
        "fields": extracted,
    }


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
            "model_trust_ready": "summary.model_trust_ready",
        },
        "phase2_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase2_master_audit_status": "summary.phase2_master_audit_status",
            "phase2_full_master_audit_accepted": "summary.phase2_full_master_audit_accepted",
            "model_trust_ready": "summary.model_trust_ready",
        },
        "phase3_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase3_master_audit_status": "summary.phase3_master_audit_status",
            "active_feature_hash_match_count": "summary.active_feature_hash_match_count",
            "target_feature_intersection_count": "summary.target_feature_intersection_count",
        },
        "phase6_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase6_master_audit_status": "summary.phase6_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
        },
        "phase7_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase7_master_audit_status": "summary.phase7_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
        },
        "active_label_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "input_root": "input_root",
            "output_root": "output_root",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "feature_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "input_root": "input_root",
            "output_root": "output_root",
            "feature_count": "feature_count",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
            "label_gate_status": "label_manifest_gate.status",
            "feature_audit_gate_status": "feature_audit_gate.status",
            "feature_audit_record_count": "feature_audit_gate.audit_record_count",
        },
        "active_feature_placement": {
            "status": "status",
        },
        "feature_leakage_audit": {
            "status": "status",
            "verdict": "verdict",
            "diagnostic_only": "diagnostic_only",
            "feature_count": "feature_count",
            "target_column_count": "target_column_count",
            "matrix_file_status_counts": "summary_counts.matrix_file_status_counts",
            "leakage_finding_status_counts": "summary_counts.leakage_finding_status_counts",
        },
    }
    result: list[dict[str, Any]] = []
    for name, relative_path in paths.items():
        if name in {"feature_cols", "target_cols"}:
            result.append(
                registry_evidence_file(
                    repo_root=repo_root,
                    relative_path=relative_path,
                    dirty_map=dirty_map,
                )
            )
            continue
        result.append(
            inventory.evidence_file(
                repo_root=repo_root,
                relative_path=relative_path,
                json_fields=json_fields.get(name),
                dirty_map=dirty_map,
            )
        )
    return result


def load_payloads(
    *,
    repo_root: Path,
    paths: Mapping[str, Path],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    payloads: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, path in paths.items():
        if name in {"feature_cols", "target_cols"}:
            continue
        resolved = resolve_path(repo_root, path)
        if resolved.suffix.lower() != ".json":
            continue
        payload, error = read_json_object(resolved)
        if error:
            failures.append(f"required JSON input unavailable: {path.as_posix()} ({error})")
        elif payload is not None:
            payloads[name] = payload
    return payloads, failures


def scoped_outputs(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = None if not isinstance(payload, Mapping) else payload.get("outputs")
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


def output_by_pair(payload: Mapping[str, Any] | None) -> dict[tuple[str, int], Mapping[str, Any]]:
    return {
        (str(row.get("market")), as_int(row.get("year")) or -1): row
        for row in scoped_outputs(payload)
    }


def registry_payload(feature_manifest: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return as_mapping(None if not isinstance(feature_manifest, Mapping) else feature_manifest.get("registry"))


def feature_audit_records(feature_manifest: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    records = registry_payload(feature_manifest).get("feature_audit")
    return [record for record in as_list(records) if isinstance(record, Mapping)]


def feature_hash_comparisons(
    *,
    feature_manifest: Mapping[str, Any] | None,
    placement: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    output_hashes = file_hashes(feature_manifest, "output_file_hashes")
    records = as_list(None if not isinstance(placement, Mapping) else placement.get("records"))
    placement_by_path = {
        str(record.get("path")): record for record in records if isinstance(record, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        path = feature_matrix_path(market, year)
        record = placement_by_path.get(path, {})
        manifest_hash = output_hashes.get(path)
        placement_hash = record.get("sha256") if isinstance(record, Mapping) else None
        staged_hash = record.get("staged_sha256") if isinstance(record, Mapping) else None
        rows.append(
            {
                "market": market,
                "year": year,
                "path": path,
                "manifest_output_hash": manifest_hash,
                "placement_sha256": placement_hash,
                "placement_staged_sha256": staged_hash,
                "active_matches_staged": record.get("active_matches_staged")
                if isinstance(record, Mapping)
                else None,
                "backup_matches_pre_active": record.get("backup_matches_pre_active")
                if isinstance(record, Mapping)
                else None,
                "rows": record.get("rows") if isinstance(record, Mapping) else None,
                "columns": record.get("columns") if isinstance(record, Mapping) else None,
                "matches": (
                    manifest_hash is not None
                    and placement_hash == manifest_hash
                    and staged_hash == manifest_hash
                    and record.get("active_matches_staged") is True
                    and record.get("backup_matches_pre_active") is True
                )
                if isinstance(record, Mapping)
                else False,
            }
        )
    return rows


def active_label_to_feature_hash_comparisons(
    *,
    active_label_manifest: Mapping[str, Any] | None,
    feature_manifest: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    active_hashes = file_hashes(active_label_manifest, "output_file_hashes")
    feature_hashes = file_hashes(feature_manifest, "input_file_hashes")
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        path = active_label_path(market, year)
        active_hash = active_hashes.get(path)
        feature_hash = feature_hashes.get(path)
        rows.append(
            {
                "market": market,
                "year": year,
                "path": path,
                "active_label_hash": active_hash,
                "feature_input_hash": feature_hash,
                "matches": active_hash is not None and active_hash == feature_hash,
            }
        )
    return rows


def row_count_comparisons(
    *,
    active_label_manifest: Mapping[str, Any] | None,
    feature_manifest: Mapping[str, Any] | None,
    placement: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    label_rows = output_by_pair(active_label_manifest)
    feature_rows = output_by_pair(feature_manifest)
    placement_records = as_list(None if not isinstance(placement, Mapping) else placement.get("records"))
    placement_by_path = {
        str(record.get("path")): record for record in placement_records if isinstance(record, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        label_row = label_rows.get((market, year), {})
        feature_row = feature_rows.get((market, year), {})
        placement_row = placement_by_path.get(feature_matrix_path(market, year), {})
        label_output_rows = as_int(label_row.get("output_rows")) if isinstance(label_row, Mapping) else None
        feature_output_rows = (
            as_int(feature_row.get("output_rows")) if isinstance(feature_row, Mapping) else None
        )
        feature_input_rows = (
            as_int(feature_row.get("input_rows")) if isinstance(feature_row, Mapping) else None
        )
        placement_rows = (
            as_int(placement_row.get("rows")) if isinstance(placement_row, Mapping) else None
        )
        placement_columns = (
            as_int(placement_row.get("columns")) if isinstance(placement_row, Mapping) else None
        )
        rows.append(
            {
                "market": market,
                "year": year,
                "label_output_rows": label_output_rows,
                "feature_input_rows": feature_input_rows,
                "feature_output_rows": feature_output_rows,
                "placement_rows": placement_rows,
                "placement_columns": placement_columns,
                "matches": (
                    label_output_rows is not None
                    and label_output_rows == feature_input_rows
                    and feature_input_rows == feature_output_rows
                    and feature_output_rows == placement_rows
                    and placement_columns == EXPECTED_FEATURE_MATRIX_COLUMNS
                ),
            }
        )
    return rows


def leakage_deductions(leakage: Mapping[str, Any] | None) -> list[str]:
    score = None if not isinstance(leakage, Mapping) else leakage.get("confidence_score")
    deductions = as_mapping(score).get("deductions")
    reasons: list[str] = []
    for item in as_list(deductions):
        if isinstance(item, Mapping) and isinstance(item.get("reason"), str):
            reasons.append(item["reason"])
    return reasons


def non_approval_all_false(flags: Mapping[str, Any]) -> bool:
    return bool(flags) and all(value is False for value in flags.values())


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
        failure=f"missing required Phase 4 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 4 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    phase1b = payloads.get("phase1b_reconciliation")
    phase2 = payloads.get("phase2_reconciliation")
    phase3 = payloads.get("phase3_reconciliation")
    phase6 = payloads.get("phase6_reconciliation")
    phase7 = payloads.get("phase7_reconciliation")
    phase4_row = row_by_area(run_status, "Phase 4")
    check(
        checks,
        failures,
        name="master_audit_inputs_are_passed_report_only_evidence",
        passed=run_status is not None
        and overview is not None
        and phase1b is not None
        and phase2 is not None
        and phase3 is not None
        and phase6 is not None
        and phase7 is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and phase1b.get("status") == "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"
        and phase2.get("status") == "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY"
        and phase3.get("status") == "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY"
        and phase6.get("status") == "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY"
        and phase7.get("status") == "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        failure="run-status, overview, or prior/downstream reconciliation input is not passed report-only evidence",
        evidence=[
            DEFAULT_RUN_STATUS.as_posix(),
            DEFAULT_OVERVIEW.as_posix(),
            DEFAULT_PHASE1B.as_posix(),
            DEFAULT_PHASE2.as_posix(),
            DEFAULT_PHASE3.as_posix(),
            DEFAULT_PHASE6.as_posix(),
            DEFAULT_PHASE7.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "phase1b": None if phase1b is None else phase1b.get("status"),
            "phase2": None if phase2 is None else phase2.get("status"),
            "phase3": None if phase3 is None else phase3.get("status"),
            "phase6": None if phase6 is None else phase6.get("status"),
            "phase7": None if phase7 is None else phase7.get("status"),
        },
    )
    check(
        checks,
        failures,
        name="phase4_preexisting_ledger_is_limited_scope_run",
        passed=phase4_row is not None
        and phase4_row.get("run_status") == "RUN"
        and phase4_row.get("detail_status") == "RUN_LIMITED_SCOPE_FEATURE_LEAKAGE_EVIDENCE"
        and phase4_row.get("evidence_state") == "limited-scope",
        failure="run-status Phase 4 row is not the expected limited-scope feature leakage evidence",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"pre_existing_phase4_row": dict(phase4_row or {})},
    )
    check(
        checks,
        failures,
        name="phase3_upstream_lineage_supports_phase4_inputs",
        passed=phase3 is not None
        and dotted_get(phase3, "summary.phase3_limited_label_timing_hash_lineage_ready") is True
        and dotted_get(phase3, "summary.phase3_full_master_audit_accepted") is False
        and dotted_get(phase3, "summary.active_feature_hash_match_count")
        == EXPECTED_MARKET_YEAR_COUNT
        and dotted_get(phase3, "summary.target_feature_intersection_count") == 0
        and dotted_get(phase3, "summary.model_trust_ready") is False,
        failure="Phase 3 reconciliation does not preserve the required limited upstream Phase 4 support",
        evidence=[DEFAULT_PHASE3.as_posix()],
        details={
            "phase3_status": None if phase3 is None else phase3.get("status"),
            "phase3_summary": dict(as_mapping(None if phase3 is None else phase3.get("summary"))),
        },
    )

    active_label_manifest = payloads.get("active_label_manifest")
    feature_manifest = payloads.get("feature_manifest")
    placement = payloads.get("active_feature_placement")
    leakage = payloads.get("feature_leakage_audit")
    label_gate = as_mapping(None if feature_manifest is None else feature_manifest.get("label_manifest_gate"))
    feature_gate = as_mapping(None if feature_manifest is None else feature_manifest.get("feature_audit_gate"))
    feature_inputs = file_hashes(feature_manifest, "input_file_hashes")
    feature_outputs = file_hashes(feature_manifest, "output_file_hashes")
    scoped_feature_outputs = scoped_outputs(feature_manifest)
    check(
        checks,
        failures,
        name="feature_manifest_scope_and_gates_pass",
        passed=feature_manifest is not None
        and feature_manifest.get("status") == "PASS"
        and feature_manifest.get("profile") == "tier_1"
        and feature_manifest.get("resolved_profile") == "tier_1_research"
        and feature_manifest.get("input_root") == "data/labeled"
        and feature_manifest.get("output_root") == "data/feature_matrices"
        and list_as_set(feature_manifest.get("markets")) == set(EXPECTED_MARKETS)
        and list_as_set(feature_manifest.get("years")) == set(EXPECTED_YEARS)
        and feature_manifest.get("feature_count") == EXPECTED_FEATURE_COUNT
        and feature_manifest.get("failure_count") == 0
        and feature_manifest.get("warning_count") == 0
        and len(feature_inputs) == EXPECTED_MARKET_YEAR_COUNT
        and len(feature_outputs) == EXPECTED_MARKET_YEAR_COUNT
        and len(scoped_feature_outputs) == EXPECTED_MARKET_YEAR_COUNT
        and label_gate.get("status") == "PASS"
        and label_gate.get("manifest_path") == ACTIVE_LABEL_MANIFEST.as_posix()
        and feature_gate.get("status") == "PASS"
        and feature_gate.get("audit_record_count") == EXPECTED_FEATURE_COUNT
        and feature_gate.get("feature_count") == EXPECTED_FEATURE_COUNT
        and feature_gate.get("failure_count") == 0,
        failure="Phase 4 feature manifest scope, counts, hashes, or gates are invalid",
        evidence=[FEATURE_MANIFEST.as_posix(), ACTIVE_LABEL_MANIFEST.as_posix()],
        details={
            "feature_status": None if feature_manifest is None else feature_manifest.get("status"),
            "profile": None if feature_manifest is None else feature_manifest.get("profile"),
            "resolved_profile": None if feature_manifest is None else feature_manifest.get("resolved_profile"),
            "feature_count": None if feature_manifest is None else feature_manifest.get("feature_count"),
            "input_hash_count": len(feature_inputs),
            "output_hash_count": len(feature_outputs),
            "scoped_output_count": len(scoped_feature_outputs),
            "label_manifest_gate": dict(label_gate),
            "feature_audit_gate": dict(feature_gate),
        },
    )

    active_label_hashes = active_label_to_feature_hash_comparisons(
        active_label_manifest=active_label_manifest,
        feature_manifest=feature_manifest,
    )
    active_feature_hash_match_count = sum(1 for row in active_label_hashes if row["matches"])
    check(
        checks,
        failures,
        name="feature_manifest_consumes_active_label_hashes",
        passed=active_label_manifest is not None
        and active_label_manifest.get("status") == "PASS"
        and active_feature_hash_match_count == EXPECTED_MARKET_YEAR_COUNT,
        failure="Phase 4 feature manifest input hashes do not match active Phase 3 label outputs",
        evidence=[ACTIVE_LABEL_MANIFEST.as_posix(), FEATURE_MANIFEST.as_posix()],
        details={
            "active_feature_hash_match_count": active_feature_hash_match_count,
            "comparisons": active_label_hashes,
        },
    )

    row_counts = row_count_comparisons(
        active_label_manifest=active_label_manifest,
        feature_manifest=feature_manifest,
        placement=placement,
    )
    row_count_match_count = sum(1 for row in row_counts if row["matches"])
    check(
        checks,
        failures,
        name="feature_matrix_rows_match_label_rows_from_json",
        passed=row_count_match_count == EXPECTED_MARKET_YEAR_COUNT,
        failure="Phase 4 feature matrix row counts do not reconcile to label rows and placement rows",
        evidence=[ACTIVE_LABEL_MANIFEST.as_posix(), FEATURE_MANIFEST.as_posix(), ACTIVE_FEATURE_PLACEMENT.as_posix()],
        details={"row_count_match_count": row_count_match_count, "comparisons": row_counts},
    )

    placement_records = as_list(None if placement is None else placement.get("records"))
    feature_hash_rows = feature_hash_comparisons(feature_manifest=feature_manifest, placement=placement)
    feature_hash_match_count = sum(1 for row in feature_hash_rows if row["matches"])
    check(
        checks,
        failures,
        name="active_feature_placement_hashes_match_manifest",
        passed=placement is not None
        and placement.get("status") == EXPECTED_FEATURE_PLACEMENT_STATUS
        and as_list(placement.get("failures")) == []
        and len(placement_records) == 12
        and feature_hash_match_count == EXPECTED_MARKET_YEAR_COUNT,
        failure="active feature placement hashes do not match the Phase 4 feature manifest output hashes",
        evidence=[ACTIVE_FEATURE_PLACEMENT.as_posix(), FEATURE_MANIFEST.as_posix()],
        details={
            "placement_status": None if placement is None else placement.get("status"),
            "placement_record_count": len(placement_records),
            "feature_hash_match_count": feature_hash_match_count,
            "comparisons": feature_hash_rows,
        },
    )

    feature_cols, feature_cols_error = load_json_list(resolve_path(repo_root, FEATURE_COLS))
    target_cols, target_cols_error = load_json_list(resolve_path(repo_root, TARGET_COLS))
    registry = registry_payload(feature_manifest)
    manifest_feature_cols = [
        item for item in as_list(registry.get("feature_cols")) if isinstance(item, str)
    ]
    manifest_target_cols = [
        item for item in as_list(registry.get("target_cols")) if isinstance(item, str)
    ]
    duplicate_features = sorted(
        feature for feature, count in Counter(feature_cols).items() if count > 1
    )
    target_feature_intersection = sorted(set(feature_cols) & set(target_cols))
    manifest_registry_errors = []
    if manifest_feature_cols != feature_cols:
        manifest_registry_errors.append("feature_cols_json_does_not_match_manifest_registry")
    if manifest_target_cols != target_cols:
        manifest_registry_errors.append("target_cols_json_does_not_match_manifest_registry")
    check(
        checks,
        failures,
        name="feature_target_registry_boundary_preserved",
        passed=feature_cols_error is None
        and target_cols_error is None
        and len(feature_cols) == EXPECTED_FEATURE_COUNT
        and len(target_cols) == EXPECTED_TARGET_COUNT
        and not duplicate_features
        and not target_feature_intersection
        and not manifest_registry_errors
        and as_list(None if feature_manifest is None else feature_manifest.get("forbidden_feature_leakage_failures"))
        == [],
        failure="feature/target registry boundary or forbidden leakage registry evidence is invalid",
        evidence=[FEATURE_COLS.as_posix(), TARGET_COLS.as_posix(), FEATURE_MANIFEST.as_posix()],
        details={
            "feature_cols_error": feature_cols_error,
            "target_cols_error": target_cols_error,
            "feature_count": len(feature_cols),
            "target_count": len(target_cols),
            "duplicate_feature_count": len(duplicate_features),
            "duplicate_features": duplicate_features,
            "target_feature_intersection_count": len(target_feature_intersection),
            "target_feature_intersection": target_feature_intersection,
            "manifest_registry_errors": manifest_registry_errors,
            "forbidden_feature_leakage_failures": as_list(
                None if feature_manifest is None else feature_manifest.get("forbidden_feature_leakage_failures")
            ),
        },
    )

    audit_records = feature_audit_records(feature_manifest)
    audit_features = [record.get("feature") for record in audit_records if isinstance(record.get("feature"), str)]
    audit_feature_set = set(audit_features)
    missing_audit_features = sorted(set(feature_cols) - audit_feature_set)
    extra_audit_features = sorted(audit_feature_set - set(feature_cols))
    missing_required_fields = []
    drift_review_count = 0
    deterministic_transform_count = 0
    for record in audit_records:
        feature_name = record.get("feature")
        missing = [
            field
            for field in REQUIRED_FEATURE_AUDIT_FIELDS
            if not isinstance(record.get(field), str) or not str(record.get(field)).strip()
        ]
        if missing:
            missing_required_fields.append({"feature": feature_name, "missing_fields": missing})
        drift_status = str(record.get("drift_decay_check_status", ""))
        transform_status = str(record.get("train_only_transform_status", ""))
        if "pre_promotion" in drift_status or "pre-promotion" in drift_status:
            drift_review_count += 1
        if "deterministic causal transforms" in transform_status:
            deterministic_transform_count += 1
    check(
        checks,
        failures,
        name="feature_audit_records_cover_registry_with_required_fields",
        passed=len(audit_records) == EXPECTED_FEATURE_COUNT
        and set(feature_gate.get("required_fields", [])) == set(REQUIRED_FEATURE_AUDIT_FIELDS)
        and not missing_audit_features
        and not extra_audit_features
        and not missing_required_fields
        and drift_review_count == EXPECTED_FEATURE_COUNT
        and deterministic_transform_count == EXPECTED_FEATURE_COUNT,
        failure="Phase 4 feature audit records do not cover all features with required leakage/transform/stability fields",
        evidence=[FEATURE_MANIFEST.as_posix()],
        details={
            "audit_record_count": len(audit_records),
            "required_fields": list(feature_gate.get("required_fields", [])),
            "missing_audit_features": missing_audit_features,
            "extra_audit_features": extra_audit_features,
            "missing_required_fields": missing_required_fields,
            "drift_review_count": drift_review_count,
            "deterministic_transform_count": deterministic_transform_count,
        },
    )

    summary_counts = as_mapping(None if leakage is None else leakage.get("summary_counts"))
    leakage_non_approval = as_mapping(None if leakage is None else leakage.get("non_approval"))
    deductions = leakage_deductions(leakage)
    required_removals = as_list(None if leakage is None else leakage.get("required_feature_removals"))
    check(
        checks,
        failures,
        name="feature_leakage_audit_passed_with_limitations_preserved",
        passed=leakage is not None
        and leakage.get("status") == "PASS"
        and leakage.get("verdict") == EXPECTED_LEAKAGE_VERDICT
        and leakage.get("diagnostic_only") is True
        and leakage.get("feature_count") == EXPECTED_FEATURE_COUNT
        and leakage.get("target_column_count") == EXPECTED_TARGET_COUNT
        and required_removals == []
        and dotted_get(summary_counts, "matrix_file_status_counts.PASS") == EXPECTED_MARKET_YEAR_COUNT
        and dotted_get(summary_counts, "leakage_finding_status_counts.WARN") == 1
        and dotted_get(summary_counts, "embedding_finding_severity_counts.WARN") == 132
        and dotted_get(summary_counts, "feature_risk_class_counts.low") == 71
        and dotted_get(summary_counts, "feature_risk_class_counts.medium") == 43
        and set(EXPECTED_LEAKAGE_DEDUCTIONS).issubset(set(deductions))
        and non_approval_all_false(leakage_non_approval),
        failure="final feature leakage audit is not PASS with diagnostic-only completed-bar limitations preserved",
        evidence=[FEATURE_LEAKAGE_AUDIT.as_posix()],
        details={
            "status": None if leakage is None else leakage.get("status"),
            "verdict": None if leakage is None else leakage.get("verdict"),
            "diagnostic_only": None if leakage is None else leakage.get("diagnostic_only"),
            "required_feature_removals_count": len(required_removals),
            "summary_counts": dict(summary_counts),
            "deductions": deductions,
            "non_approval": dict(leakage_non_approval),
        },
    )

    downstream_blockers = {
        "phase2_full_master_audit_accepted": dotted_get(
            phase2, "summary.phase2_full_master_audit_accepted"
        ),
        "phase3_full_master_audit_accepted": dotted_get(
            phase3, "summary.phase3_full_master_audit_accepted"
        ),
        "phase6_model_trust_ready": dotted_get(phase6, "summary.model_trust_ready"),
        "phase7_model_trust_ready": dotted_get(phase7, "summary.model_trust_ready"),
        "phase7_promotion_allowed": dotted_get(phase7, "summary.promotion_allowed"),
    }
    check(
        checks,
        failures,
        name="full_acceptance_and_downstream_trust_remain_blocked",
        passed=downstream_blockers["phase2_full_master_audit_accepted"] is False
        and downstream_blockers["phase3_full_master_audit_accepted"] is False
        and downstream_blockers["phase6_model_trust_ready"] is False
        and downstream_blockers["phase7_model_trust_ready"] is False
        and downstream_blockers["phase7_promotion_allowed"] is False,
        failure="upstream/downstream reports unexpectedly upgrade full acceptance, model trust, or promotion",
        evidence=[DEFAULT_PHASE2.as_posix(), DEFAULT_PHASE3.as_posix(), DEFAULT_PHASE6.as_posix(), DEFAULT_PHASE7.as_posix()],
        details=downstream_blockers,
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "active_feature_hash_match_count": active_feature_hash_match_count,
        "active_feature_hash_comparisons": active_label_hashes,
        "feature_hash_match_count": feature_hash_match_count,
        "feature_hash_comparisons": feature_hash_rows,
        "row_count_match_count": row_count_match_count,
        "row_count_comparisons": row_counts,
        "feature_count": len(feature_cols),
        "target_count": len(target_cols),
        "target_feature_intersection_count": len(target_feature_intersection),
        "feature_audit_record_count": len(audit_records),
        "required_feature_removals_count": len(required_removals),
        "leakage_verdict": None if leakage is None else leakage.get("verdict"),
        "leakage_diagnostic_only": None if leakage is None else leakage.get("diagnostic_only"),
        "leakage_confidence_score": dotted_get(leakage, "confidence_score.score"),
        "leakage_deductions": deductions,
        "leakage_summary_counts": dict(summary_counts),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "phase4-001-active-feature-hash-lineage-accepted-limited",
            "severity": "Info",
            "finding": "Scoped active v2 Phase 4 feature matrix hash-lineage evidence is accepted for 6E/CL/ES/ZN 2023/2024 only.",
            "verified_facts": [
                f"active_feature_hash_match_count={derived.get('active_feature_hash_match_count')}",
                f"feature_hash_match_count={derived.get('feature_hash_match_count')}",
                f"row_count_match_count={derived.get('row_count_match_count')}",
            ],
            "limitation": "This is a report-only reconciliation and does not read feature parquet.",
            "evidence_paths": [
                ACTIVE_LABEL_MANIFEST.as_posix(),
                FEATURE_MANIFEST.as_posix(),
                ACTIVE_FEATURE_PLACEMENT.as_posix(),
            ],
        },
        {
            "finding_id": "phase4-002-feature-registry-and-audit-records-preserved",
            "severity": "Info",
            "finding": "Feature and target registries remain disjoint, and each feature has the required audit metadata.",
            "verified_facts": [
                f"feature_count={derived.get('feature_count')}",
                f"target_count={derived.get('target_count')}",
                f"target_feature_intersection_count={derived.get('target_feature_intersection_count')}",
                f"feature_audit_record_count={derived.get('feature_audit_record_count')}",
            ],
            "limitation": "Drift/decay evidence is registered for pre-promotion review, not accepted as completed model-trust evidence.",
            "evidence_paths": [FEATURE_MANIFEST.as_posix(), FEATURE_COLS.as_posix(), TARGET_COLS.as_posix()],
        },
        {
            "finding_id": "phase4-003-leakage-audit-pass-diagnostic-only",
            "severity": "Medium",
            "finding": "The existing feature leakage audit passes only under the completed-bar convention and remains diagnostic-only.",
            "verified_facts": [
                f"leakage_verdict={derived.get('leakage_verdict')}",
                f"leakage_diagnostic_only={derived.get('leakage_diagnostic_only')}",
                f"required_feature_removals_count={derived.get('required_feature_removals_count')}",
                f"leakage_confidence_score={derived.get('leakage_confidence_score')}",
            ],
            "limitation": "The leakage report is static/diagnostic evidence, not per-cell replay or promotion evidence.",
            "evidence_paths": [FEATURE_LEAKAGE_AUDIT.as_posix()],
        },
        {
            "finding_id": "phase4-004-full-phase4-and-model-trust-remain-blocked",
            "severity": "Critical",
            "finding": "Full Phase 4 Master Audit acceptance, model trust, promotion, holdout, and paper/live remain blocked.",
            "verified_facts": ["All non-approval flags in this report are false."],
            "limitation": "A separate bounded phase audit would be required for full acceptance or promotion claims.",
            "evidence_paths": [DEFAULT_RUN_STATUS.as_posix()],
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
    phase4_classification = (
        "RUN_LIMITED_SCOPE_PHASE4_ACTIVE_FEATURE_LEAKAGE_HASH_LINEAGE_RECONCILIATION"
        if status == PASS_STATUS
        else "FAILED_PHASE4_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase4_reconciliation_report_only",
            "phase": "Phase 4",
            "phase_name": "Feature matrix, feature lineage, feature registry, and target leakage",
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "parquet_read_scope": "none",
            "phase_command_scope": "none",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "market_year_count": EXPECTED_MARKET_YEAR_COUNT,
            "full_phase4_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase4_master_audit_status": phase4_classification,
            "phase4_limited_feature_leakage_hash_lineage_ready": status == PASS_STATUS,
            "phase4_full_master_audit_accepted": False,
            "phase4_feature_build_accepted": False,
            "feature_leakage_audit_accepted_as_full_proof": False,
            "completed_bar_diagnostic_only_leakage_limitation_preserved": status == PASS_STATUS,
            "active_feature_hash_match_count": derived.get("active_feature_hash_match_count"),
            "feature_hash_match_count": derived.get("feature_hash_match_count"),
            "row_count_match_count": derived.get("row_count_match_count"),
            "feature_count": derived.get("feature_count"),
            "target_count": derived.get("target_count"),
            "target_feature_intersection_count": derived.get("target_feature_intersection_count"),
            "feature_audit_record_count": derived.get("feature_audit_record_count"),
            "required_feature_removals_count": derived.get("required_feature_removals_count"),
            "leakage_verdict": derived.get("leakage_verdict"),
            "leakage_diagnostic_only": derived.get("leakage_diagnostic_only"),
            "leakage_confidence_score": derived.get("leakage_confidence_score"),
            "leakage_deductions": derived.get("leakage_deductions"),
            "leakage_summary_counts": derived.get("leakage_summary_counts"),
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
        "active_feature_hash_comparisons": derived.get("active_feature_hash_comparisons", []),
        "feature_hash_comparisons": derived.get("feature_hash_comparisons", []),
        "row_count_comparisons": derived.get("row_count_comparisons", []),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required JSON/MD evidence and registry JSON lists are readable",
                "run-status, overview, and Phase 1B/2/3/6/7 reconciliation inputs are passed report-only evidence",
                "pre-existing Phase 4 ledger row is RUN_LIMITED_SCOPE_FEATURE_LEAKAGE_EVIDENCE",
                "Phase 3 upstream reconciliation proves limited active label-to-feature hash support",
                "feature manifest is exact-scope PASS with 114 features, 8 inputs, 8 outputs, and passed label/feature audit gates",
                "feature manifest input hashes match active label manifest output hashes for all 8 market-years",
                "feature output hashes match active placement hashes for all 8 market-years",
                "feature row counts reconcile to label rows and placement rows from JSON evidence for all 8 market-years",
                "feature/target registries contain 114/97 columns, no duplicate features, and zero target-feature intersection",
                "all 114 feature audit records have required fields and preserve train-only transform and drift/decay limitations",
                "feature leakage audit is PASS, diagnostic-only, completed-bar-limited, and has zero required feature removals",
                "model trust, promotion, holdout, and paper/live remain blocked",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "scope/profile/market/year mismatch",
                "feature count not 114 or target count not 97",
                "duplicate feature names or nonzero feature/target intersection",
                "feature manifest, active placement, or leakage audit not PASS",
                "feature manifest hash mismatch against active label manifest or placement hashes",
                "feature row-count mismatch against active label or placement JSON evidence",
                "missing feature audit records or missing required audit fields",
                "required feature removals present",
                "completed-bar/diagnostic-only limitation omitted or upgraded into full proof",
                "full Phase 4 acceptance, model trust, promotion, holdout, or paper/live readiness is upgraded",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan exactly one next bounded Master Audit area from the updated Phase 1B/2/3/4/6/7 "
            "report-only evidence; do not run data/model/phase commands without separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 4 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 4 status: `{summary.get('phase4_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Active label to feature hash matches: `{summary.get('active_feature_hash_match_count')}`",
        f"- Feature placement hash matches: `{summary.get('feature_hash_match_count')}`",
        f"- Row-count matches: `{summary.get('row_count_match_count')}`",
        f"- Feature count: `{summary.get('feature_count')}`",
        f"- Target count: `{summary.get('target_count')}`",
        f"- Target/feature intersection count: `{summary.get('target_feature_intersection_count')}`",
        f"- Required feature removals: `{summary.get('required_feature_removals_count')}`",
        f"- Leakage diagnostic-only: `{summary.get('leakage_diagnostic_only')}`",
        f"- Full Phase 4 Master Audit accepted: `{summary.get('phase4_full_master_audit_accepted')}`",
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
    lines.extend(["", "## Hash Lineage", ""])
    for item in report.get("active_feature_hash_comparisons", []):
        lines.append(f"- `{item.get('path')}` active_label_matches_feature_input=`{item.get('matches')}`")
    for item in report.get("feature_hash_comparisons", []):
        lines.append(f"- `{item.get('path')}` manifest_matches_active_placement=`{item.get('matches')}`")
    lines.extend(["", "## Row Counts", ""])
    for item in report.get("row_count_comparisons", []):
        lines.append(
            "- `{market}` `{year}` rows_match=`{matches}` label=`{label}` feature=`{feature}` placement=`{placement}` columns=`{columns}`".format(
                market=item.get("market"),
                year=item.get("year"),
                matches=item.get("matches"),
                label=item.get("label_output_rows"),
                feature=item.get("feature_output_rows"),
                placement=item.get("placement_rows"),
                columns=item.get("placement_columns"),
            )
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
            "- This reconciliation did not run Phase 4 feature build, rerun feature leakage audit, run Phase 3 label build, run Phase 2 build/readiness, run Phase 1B conversion, run phase audits, run WFA/modeling, generate predictions, refresh Phase 8, call providers/network, approve promotion, freeze artifacts, touch holdout, paper trade, live trade, clean up files, stage, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, or model artifacts.",
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
        f"phase4_status={report['summary']['phase4_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
