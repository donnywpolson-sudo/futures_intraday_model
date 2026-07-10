#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 3 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run
Phase 3 label builds, rerun target timing audits, run Phase 2 readiness/build,
read parquet, run WFA/modeling, generate predictions, refresh Phase 8, call
providers/network, promote, freeze, touch holdout, paper/live, clean up files,
stage, commit, or push.
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
STAGE = "master_audit_phase3_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_MARKET_YEAR_COUNT = 8
EXPECTED_LABEL_SEMANTICS_ID = "phase3_labels_v2_next_1m_open_30m_primary_60m_confirm_apex_aware"
EXPECTED_FEATURE_COUNT = 114
EXPECTED_TARGET_COUNT = 97
KNOWN_TIMING_WARNING = (
    "WARN_COMPLETED_BAR_CONVENTION_ASSUMED: audit proves timing only if feature row ts means "
    "completed one-minute bar availability, not bar-open availability."
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
DEFAULT_PHASE6 = Path(
    "reports/master_audit/master_audit_phase6_reconciliation_20260709/"
    "master_audit_phase6_reconciliation.json"
)
DEFAULT_PHASE7 = Path(
    "reports/master_audit/master_audit_phase7_reconciliation_20260709/"
    "master_audit_phase7_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase3_reconciliation_20260709")
REPORT_JSON = "master_audit_phase3_reconciliation.json"
REPORT_MD = "master_audit_phase3_reconciliation.md"

STAGED_LABEL_MANIFEST = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_tier1_core/label_manifest.json"
)
STAGED_LABEL_REPORT = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_tier1_core/label_report.json"
)
ACTIVE_REPLACEMENT_HASHES = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_active_replacement_decision/"
    "post_replacement_hashes.json"
)
ACTIVE_LABEL_MANIFEST = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_active_tier1_core_manifest_for_phase4/"
    "label_manifest.json"
)
TARGET_TIMING_AUDIT = Path(
    "reports/model_trust_audit/target_timing_v2_tier1_core_20260709/"
    "target_timing_audit.json"
)
FEATURE_MANIFEST = Path(
    "reports/features_baseline/phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "baseline_feature_manifest.json"
)
TARGET_COLS = Path("data/feature_matrices/target_cols.json")
FEATURE_COLS = Path("data/feature_matrices/feature_cols.json")

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "phase1b_reconciliation": DEFAULT_PHASE1B,
    "phase2_reconciliation": DEFAULT_PHASE2,
    "phase6_reconciliation": DEFAULT_PHASE6,
    "phase7_reconciliation": DEFAULT_PHASE7,
    "staged_label_manifest": STAGED_LABEL_MANIFEST,
    "staged_label_report": STAGED_LABEL_REPORT,
    "active_replacement_hashes": ACTIVE_REPLACEMENT_HASHES,
    "active_label_manifest": ACTIVE_LABEL_MANIFEST,
    "target_timing_audit": TARGET_TIMING_AUDIT,
    "feature_manifest": FEATURE_MANIFEST,
    "target_cols": TARGET_COLS,
    "feature_cols": FEATURE_COLS,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase3_label_build_executed": False,
    "target_timing_audit_rerun_executed": False,
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


def as_sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def as_string_list(value: Any) -> list[str]:
    return [item for item in as_sequence(value) if isinstance(item, str)]


def expected_pairs() -> list[tuple[str, int]]:
    return [(market, year) for market in EXPECTED_MARKETS for year in EXPECTED_YEARS]


def staged_label_path(market: str, year: int) -> str:
    return (
        "data/labeled_rebuild_staging/phase3_v2_apex_30m60m_20260709_tier1_core/"
        f"{market}/{year}.parquet"
    )


def active_label_path(market: str, year: int) -> str:
    return f"data/labeled/{market}/{year}.parquet"


def file_hashes(payload: Mapping[str, Any] | None, key: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    hashes = payload.get(key)
    return hashes if isinstance(hashes, Mapping) else {}


def label_semantics(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    semantics = payload.get("label_semantics")
    return semantics if isinstance(semantics, Mapping) else {}


def row_by_area(run_status: Mapping[str, Any] | None, area: str) -> Mapping[str, Any] | None:
    rows = dotted_get(run_status, "run_status_table")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("audit_area") == area:
            return row
    return None


def text_contains(path: Path, terms: Sequence[str]) -> dict[str, bool]:
    try:
        text = path.read_text(encoding="utf-8").lower()
    except Exception:
        return {term: False for term in terms}
    normalized = " ".join(text.split())
    return {term: " ".join(term.lower().split()) in normalized for term in terms}


def scoped_outputs(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("outputs")
    if not isinstance(rows, list):
        rows = payload.get("files")
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
        },
        "phase2_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase2_master_audit_status": "summary.phase2_master_audit_status",
            "phase2_full_master_audit_accepted": "summary.phase2_full_master_audit_accepted",
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
        "staged_label_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "input_root": "input_root",
            "output_root": "output_root",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
            "label_semantics_id": "label_semantics.label_semantics_id",
        },
        "staged_label_report": {
            "status": "status",
            "file_count": "summary.file_count",
            "pass_count": "summary.pass_count",
            "warn_count": "summary.warn_count",
            "fail_count": "summary.fail_count",
            "target_valid_rows": "summary.target_valid_rows",
            "target_invalid_rows": "summary.target_invalid_rows",
        },
        "active_replacement_hashes": {
            "status": "status",
            "label_semantics_id": "label_semantics_id",
            "file_count": "scope.file_count",
        },
        "active_label_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "input_root": "input_root",
            "output_root": "output_root",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
            "label_semantics_id": "label_semantics.label_semantics_id",
            "causal_gate_status": "causal_base_manifest_gate.status",
        },
        "target_timing_audit": {
            "status": "status",
            "summary_status": "summary.status",
            "failure_count": "summary.failure_count",
            "warning_count": "summary.warning_count",
            "pair_count": "summary.pair_count",
            "row_key_mismatches": "summary.row_key_mismatches",
        },
        "feature_manifest": {
            "status": "status",
            "input_root": "input_root",
            "output_root": "output_root",
            "feature_count": "feature_count",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
            "label_gate_status": "label_manifest_gate.status",
        },
    }
    result: list[dict[str, Any]] = []
    for name, relative_path in paths.items():
        if name in {"target_cols", "feature_cols"}:
            result.append(registry_evidence_file(repo_root=repo_root, relative_path=relative_path, dirty_map=dirty_map))
        else:
            result.append(
                inventory.evidence_file(
                    repo_root=repo_root,
                    relative_path=relative_path,
                    json_fields=json_fields.get(name),
                    dirty_map=dirty_map,
                )
            )
    return result


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


def load_payloads(
    *,
    repo_root: Path,
    paths: Mapping[str, Path],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    payloads: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, path in paths.items():
        if name in {"target_cols", "feature_cols"}:
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


def staged_to_active_hash_comparisons(
    staged_manifest: Mapping[str, Any] | None,
    active_manifest: Mapping[str, Any] | None,
    replacement_hashes: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    staged_hashes = file_hashes(staged_manifest, "output_file_hashes")
    active_hashes = file_hashes(active_manifest, "output_file_hashes")
    replacement_records = {
        (row.get("market"), as_int(row.get("year"))): row
        for row in as_sequence(None if not isinstance(replacement_hashes, Mapping) else replacement_hashes.get("records"))
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        staged_path = staged_label_path(market, year)
        active_path = active_label_path(market, year)
        record = replacement_records.get((market, year), {})
        staged_hash = staged_hashes.get(staged_path)
        active_hash = active_hashes.get(active_path)
        record_staged = record.get("staged_sha256") if isinstance(record, Mapping) else None
        record_active = record.get("active_sha256") if isinstance(record, Mapping) else None
        rows.append(
            {
                "market": market,
                "year": year,
                "staged_path": staged_path,
                "active_path": active_path,
                "staged_manifest_hash": staged_hash,
                "active_manifest_hash": active_hash,
                "replacement_staged_hash": record_staged,
                "replacement_active_hash": record_active,
                "replacement_active_matches_staged": (
                    record.get("active_matches_staged") if isinstance(record, Mapping) else None
                ),
                "matches": (
                    staged_hash is not None
                    and active_hash == staged_hash
                    and record_staged == staged_hash
                    and record_active == active_hash
                    and record.get("active_matches_staged") is True
                )
                if isinstance(record, Mapping)
                else False,
            }
        )
    return rows


def active_to_feature_hash_comparisons(
    active_manifest: Mapping[str, Any] | None,
    feature_manifest: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    active_hashes = file_hashes(active_manifest, "output_file_hashes")
    feature_input_hashes = file_hashes(feature_manifest, "input_file_hashes")
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        path = active_label_path(market, year)
        active_hash = active_hashes.get(path)
        feature_hash = feature_input_hashes.get(path)
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
        failure=f"missing required Phase 3 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 3 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    phase1b = payloads.get("phase1b_reconciliation")
    phase2 = payloads.get("phase2_reconciliation")
    phase6 = payloads.get("phase6_reconciliation")
    phase7 = payloads.get("phase7_reconciliation")
    phase3_row = row_by_area(run_status, "Phase 3")
    check(
        checks,
        failures,
        name="master_audit_inputs_are_passed_report_only_evidence",
        passed=run_status is not None
        and overview is not None
        and phase1b is not None
        and phase2 is not None
        and phase6 is not None
        and phase7 is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and phase1b.get("status") == "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"
        and phase2.get("status") == "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY"
        and phase6.get("status") == "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY"
        and phase7.get("status") == "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        failure="run-status, overview, Phase 1B, Phase 2, Phase 6, or Phase 7 input is not passed report-only evidence",
        evidence=[
            DEFAULT_RUN_STATUS.as_posix(),
            DEFAULT_OVERVIEW.as_posix(),
            DEFAULT_PHASE1B.as_posix(),
            DEFAULT_PHASE2.as_posix(),
            DEFAULT_PHASE6.as_posix(),
            DEFAULT_PHASE7.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "phase1b": None if phase1b is None else phase1b.get("status"),
            "phase2": None if phase2 is None else phase2.get("status"),
            "phase6": None if phase6 is None else phase6.get("status"),
            "phase7": None if phase7 is None else phase7.get("status"),
        },
    )
    check(
        checks,
        failures,
        name="phase3_limited_scope_run_status_preserved",
        passed=phase3_row is not None
        and phase3_row.get("run_status") == "RUN"
        and phase3_row.get("detail_status") == "RUN_LIMITED_SCOPE_TARGET_TIMING_EVIDENCE"
        and phase3_row.get("evidence_state") == "limited-scope",
        failure="run-status Phase 3 row does not preserve limited-scope target timing evidence",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"pre_existing_phase3_row": dict(phase3_row or {})},
    )
    check(
        checks,
        failures,
        name="phase2_prerequisite_is_limited_not_full_acceptance",
        passed=phase2 is not None
        and dotted_get(phase2, "summary.phase2_limited_active_hash_lineage_ready") is True
        and dotted_get(phase2, "summary.phase2_full_master_audit_accepted") is False
        and dotted_get(phase2, "summary.model_trust_ready") is False,
        failure="Phase 2 prerequisite is not limited hash-lineage evidence with full acceptance false",
        evidence=[DEFAULT_PHASE2.as_posix()],
        details={
            "phase2_limited_active_hash_lineage_ready": dotted_get(
                phase2, "summary.phase2_limited_active_hash_lineage_ready"
            ),
            "phase2_full_master_audit_accepted": dotted_get(
                phase2, "summary.phase2_full_master_audit_accepted"
            ),
            "model_trust_ready": dotted_get(phase2, "summary.model_trust_ready"),
        },
    )

    master_terms = text_contains(
        resolve_path(repo_root, Path("MASTER_AUDIT.md")),
        (
            "label timing",
            "label horizons",
            "invalid row rules",
            "cost assumptions",
            "label realizability",
            "label stability",
            "signal_timestamp < execution_timestamp < label_start < label_end",
        ),
    )
    outline_terms = text_contains(
        resolve_path(repo_root, Path("PROJECT_OUTLINE.md")),
        (
            EXPECTED_LABEL_SEMANTICS_ID,
            "30m primary horizon",
            "60m robustness horizon",
            "target columns",
            "diagnostic only",
            "target, label, or forward-return columns can enter feature registries",
        ),
    )
    missing_terms = sorted(
        [f"MASTER_AUDIT.md:{term}" for term, present in master_terms.items() if not present]
        + [f"PROJECT_OUTLINE.md:{term}" for term, present in outline_terms.items() if not present]
    )
    check(
        checks,
        failures,
        name="phase3_contract_terms_present",
        passed=not missing_terms,
        failure=f"Phase 3 contract terms missing from documentation: {missing_terms}",
        evidence=["MASTER_AUDIT.md", "PROJECT_OUTLINE.md"],
        details={"missing_terms": missing_terms},
    )

    staged_manifest = payloads.get("staged_label_manifest")
    staged_report = payloads.get("staged_label_report")
    active_replacement = payloads.get("active_replacement_hashes")
    active_manifest = payloads.get("active_label_manifest")
    timing = payloads.get("target_timing_audit")
    feature_manifest = payloads.get("feature_manifest")

    staged_semantics = label_semantics(staged_manifest)
    staged_input_hashes = file_hashes(staged_manifest, "input_file_hashes")
    staged_output_hashes = file_hashes(staged_manifest, "output_file_hashes")
    staged_scoped = scoped_outputs(staged_manifest)
    check(
        checks,
        failures,
        name="staged_label_manifest_exact_scope_pass",
        passed=staged_manifest is not None
        and staged_manifest.get("status") == "PASS"
        and set(staged_manifest.get("markets", [])) == set(EXPECTED_MARKETS)
        and set(staged_manifest.get("years", [])) == set(EXPECTED_YEARS)
        and staged_manifest.get("failure_count") == 0
        and staged_manifest.get("warning_count") == 0
        and staged_manifest.get("input_root") == "data/causally_gated_normalized"
        and staged_manifest.get("output_root")
        == "data/labeled_rebuild_staging/phase3_v2_apex_30m60m_20260709_tier1_core"
        and staged_semantics.get("label_semantics_id") == EXPECTED_LABEL_SEMANTICS_ID
        and len(staged_input_hashes) == EXPECTED_MARKET_YEAR_COUNT
        and len(staged_output_hashes) == EXPECTED_MARKET_YEAR_COUNT
        and len(staged_scoped) == EXPECTED_MARKET_YEAR_COUNT,
        failure="staged Phase 3 label manifest is not exact-scope PASS evidence",
        evidence=[STAGED_LABEL_MANIFEST.as_posix()],
        details={
            "status": None if staged_manifest is None else staged_manifest.get("status"),
            "label_semantics_id": staged_semantics.get("label_semantics_id"),
            "input_hash_count": len(staged_input_hashes),
            "output_hash_count": len(staged_output_hashes),
            "scoped_output_count": len(staged_scoped),
        },
    )

    report_summary = staged_report.get("summary") if isinstance(staged_report, Mapping) else {}
    report_summary = report_summary if isinstance(report_summary, Mapping) else {}
    invalid_reasons = report_summary.get("invalid_reason_counts")
    invalid_reasons = invalid_reasons if isinstance(invalid_reasons, Mapping) else {}
    check(
        checks,
        failures,
        name="label_report_row_counts_and_invalid_reasons_pass",
        passed=staged_report is not None
        and staged_report.get("status") == "PASS"
        and report_summary.get("file_count") == EXPECTED_MARKET_YEAR_COUNT
        and report_summary.get("pass_count") == EXPECTED_MARKET_YEAR_COUNT
        and report_summary.get("warn_count") == 0
        and report_summary.get("fail_count") == 0
        and as_int(report_summary.get("input_rows")) == as_int(report_summary.get("output_rows"))
        and as_int(report_summary.get("target_valid_rows")) is not None
        and as_int(report_summary.get("target_valid_rows")) > 0
        and as_int(report_summary.get("target_invalid_rows")) is not None
        and len(invalid_reasons) > 0
        and report_summary.get("roll_protection_unavailable_files") == 0
        and report_summary.get("roll_detection_unavailable_rows") == 0,
        failure="Phase 3 label report row counts or invalid-reason evidence is not PASS",
        evidence=[STAGED_LABEL_REPORT.as_posix()],
        details=dict(report_summary),
    )

    active_semantics = label_semantics(active_manifest)
    active_input_hashes = file_hashes(active_manifest, "input_file_hashes")
    active_output_hashes = file_hashes(active_manifest, "output_file_hashes")
    active_scoped = scoped_outputs(active_manifest)
    active_gate = active_manifest.get("causal_base_manifest_gate") if isinstance(active_manifest, Mapping) else {}
    check(
        checks,
        failures,
        name="active_label_manifest_exact_scope_pass",
        passed=active_manifest is not None
        and active_manifest.get("status") == "PASS"
        and active_manifest.get("profile") == "tier_1"
        and active_manifest.get("resolved_profile") == "tier_1_research"
        and active_manifest.get("input_root") == "data/causally_gated_normalized"
        and active_manifest.get("output_root") == "data/labeled"
        and set(active_manifest.get("markets", [])) == set(EXPECTED_MARKETS)
        and set(active_manifest.get("years", [])) == set(EXPECTED_YEARS)
        and active_manifest.get("failure_count") == 0
        and active_manifest.get("warning_count") == 0
        and active_semantics.get("label_semantics_id") == EXPECTED_LABEL_SEMANTICS_ID
        and len(active_input_hashes) == EXPECTED_MARKET_YEAR_COUNT
        and len(active_output_hashes) == EXPECTED_MARKET_YEAR_COUNT
        and len(active_scoped) == EXPECTED_MARKET_YEAR_COUNT
        and isinstance(active_gate, Mapping)
        and active_gate.get("status") == "PASS",
        failure="active Phase 3 label manifest is not exact-scope PASS evidence",
        evidence=[ACTIVE_LABEL_MANIFEST.as_posix()],
        details={
            "status": None if active_manifest is None else active_manifest.get("status"),
            "label_semantics_id": active_semantics.get("label_semantics_id"),
            "input_hash_count": len(active_input_hashes),
            "output_hash_count": len(active_output_hashes),
            "scoped_output_count": len(active_scoped),
            "causal_gate_status": active_gate.get("status") if isinstance(active_gate, Mapping) else None,
        },
    )

    replacement_records = as_sequence(
        None if not isinstance(active_replacement, Mapping) else active_replacement.get("records")
    )
    replacement_record_count = sum(1 for row in replacement_records if isinstance(row, Mapping))
    replacement_all_match = all(
        isinstance(row, Mapping)
        and row.get("active_matches_staged") is True
        and row.get("backup_matches_pre_active") is True
        for row in replacement_records
    )
    check(
        checks,
        failures,
        name="active_replacement_hashes_pass",
        passed=active_replacement is not None
        and active_replacement.get("status") == "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM"
        and active_replacement.get("label_semantics_id") == EXPECTED_LABEL_SEMANTICS_ID
        and dotted_get(active_replacement, "scope.file_count") == EXPECTED_MARKET_YEAR_COUNT
        and as_sequence(active_replacement.get("failures")) == []
        and replacement_record_count == EXPECTED_MARKET_YEAR_COUNT
        and replacement_all_match,
        failure="active replacement post-hash evidence is not PASS for all scoped labels",
        evidence=[ACTIVE_REPLACEMENT_HASHES.as_posix()],
        details={
            "status": None if active_replacement is None else active_replacement.get("status"),
            "record_count": replacement_record_count,
            "replacement_all_match": replacement_all_match,
        },
    )

    staged_active = staged_to_active_hash_comparisons(
        staged_manifest=staged_manifest,
        active_manifest=active_manifest,
        replacement_hashes=active_replacement,
    )
    staged_active_match_count = sum(1 for row in staged_active if row["matches"])
    check(
        checks,
        failures,
        name="staged_active_label_hash_lineage_matches",
        passed=staged_active_match_count == EXPECTED_MARKET_YEAR_COUNT,
        failure="staged-to-active label hash lineage does not match for all scoped files",
        evidence=[STAGED_LABEL_MANIFEST.as_posix(), ACTIVE_LABEL_MANIFEST.as_posix(), ACTIVE_REPLACEMENT_HASHES.as_posix()],
        details={
            "match_count": staged_active_match_count,
            "expected_count": EXPECTED_MARKET_YEAR_COUNT,
            "comparisons": staged_active,
        },
    )

    timing_summary = timing.get("summary") if isinstance(timing, Mapping) else {}
    timing_summary = timing_summary if isinstance(timing_summary, Mapping) else {}
    timing_warnings = as_string_list(None if not isinstance(timing, Mapping) else timing.get("warnings"))
    check(
        checks,
        failures,
        name="target_timing_audit_pass_with_known_warning_only",
        passed=timing is not None
        and timing.get("status") == "PASS_TARGET_TIMING_AUDIT"
        and timing_summary.get("status") == "PASS_TARGET_TIMING_AUDIT"
        and timing_summary.get("failure_count") == 0
        and timing_summary.get("pair_count") == EXPECTED_MARKET_YEAR_COUNT
        and timing_summary.get("row_key_mismatches") == 0
        and timing_summary.get("entry_30m_not_after_ts") == 0
        and timing_summary.get("entry_60m_not_after_ts") == 0
        and timing_summary.get("exit_30m_offset_mismatches") == 0
        and timing_summary.get("exit_60m_offset_mismatches") == 0
        and timing_summary.get("same_session_30m_violations") == 0
        and timing_summary.get("same_session_60m_violations") == 0
        and timing_summary.get("warning_count") == 1
        and timing_warnings == [KNOWN_TIMING_WARNING]
        and timing_summary.get("completed_bar_convention_assumed") is True
        and timing_summary.get("data_model_or_prediction_mutation") is False
        and timing_summary.get("commands_executed") == 0,
        failure="target timing audit is not PASS with only the known completed-bar convention warning",
        evidence=[TARGET_TIMING_AUDIT.as_posix()],
        details={
            "summary": dict(timing_summary),
            "warnings": timing_warnings,
        },
    )

    feature_gate = feature_manifest.get("label_manifest_gate") if isinstance(feature_manifest, Mapping) else {}
    feature_input_hashes = file_hashes(feature_manifest, "input_file_hashes")
    feature_output_hashes = file_hashes(feature_manifest, "output_file_hashes")
    active_feature = active_to_feature_hash_comparisons(
        active_manifest=active_manifest,
        feature_manifest=feature_manifest,
    )
    active_feature_match_count = sum(1 for row in active_feature if row["matches"])
    check(
        checks,
        failures,
        name="phase4_feature_manifest_consumes_active_labels",
        passed=feature_manifest is not None
        and feature_manifest.get("status") == "PASS"
        and feature_manifest.get("input_root") == "data/labeled"
        and feature_manifest.get("output_root") == "data/feature_matrices"
        and feature_manifest.get("feature_count") == EXPECTED_FEATURE_COUNT
        and feature_manifest.get("failure_count") == 0
        and feature_manifest.get("warning_count") == 0
        and len(feature_input_hashes) == EXPECTED_MARKET_YEAR_COUNT
        and len(feature_output_hashes) == EXPECTED_MARKET_YEAR_COUNT
        and isinstance(feature_gate, Mapping)
        and feature_gate.get("status") == "PASS"
        and feature_gate.get("manifest_path") == ACTIVE_LABEL_MANIFEST.as_posix()
        and active_feature_match_count == EXPECTED_MARKET_YEAR_COUNT,
        failure="Phase 4 feature manifest does not consume the exact active Phase 3 label hashes",
        evidence=[FEATURE_MANIFEST.as_posix(), ACTIVE_LABEL_MANIFEST.as_posix()],
        details={
            "feature_status": None if feature_manifest is None else feature_manifest.get("status"),
            "feature_count": None if feature_manifest is None else feature_manifest.get("feature_count"),
            "label_gate": dict(feature_gate) if isinstance(feature_gate, Mapping) else feature_gate,
            "active_feature_match_count": active_feature_match_count,
            "comparisons": active_feature,
        },
    )

    target_cols, target_error = load_json_list(resolve_path(repo_root, TARGET_COLS))
    feature_cols, feature_error = load_json_list(resolve_path(repo_root, FEATURE_COLS))
    registry_errors = [error for error in (target_error, feature_error) if error]
    target_feature_intersection = sorted(set(target_cols) & set(feature_cols))
    required_targets = {
        "target_ret_ticks_30m",
        "target_ret_ticks_60m",
        "target_exit_ts_30m",
        "target_exit_ts_60m",
        "target_30m_valid",
        "target_60m_valid",
        "diagnostic_ret_ticks_15m",
    }
    missing_targets = sorted(required_targets - set(target_cols))
    diagnostic_text = active_semantics.get("diagnostic_ret_ticks_15m")
    check(
        checks,
        failures,
        name="target_feature_registry_boundary_preserved",
        passed=not registry_errors
        and len(target_cols) == EXPECTED_TARGET_COUNT
        and len(feature_cols) == EXPECTED_FEATURE_COUNT
        and not target_feature_intersection
        and not missing_targets
        and isinstance(diagnostic_text, str)
        and "optional diagnostic only" in diagnostic_text,
        failure="target/feature registry boundary or diagnostic 15m semantics are invalid",
        evidence=[TARGET_COLS.as_posix(), FEATURE_COLS.as_posix(), ACTIVE_LABEL_MANIFEST.as_posix()],
        details={
            "registry_errors": registry_errors,
            "target_count": len(target_cols),
            "feature_count": len(feature_cols),
            "intersection_count": len(target_feature_intersection),
            "intersection": target_feature_intersection,
            "missing_targets": missing_targets,
            "diagnostic_ret_ticks_15m": diagnostic_text,
        },
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "staged_active_hash_match_count": staged_active_match_count,
        "staged_active_hash_comparisons": staged_active,
        "active_feature_hash_match_count": active_feature_match_count,
        "active_feature_hash_comparisons": active_feature,
        "target_feature_intersection_count": len(target_feature_intersection),
        "target_count": len(target_cols),
        "feature_count": len(feature_cols),
        "target_valid_rows": timing_summary.get("valid_30m_rows")
        or report_summary.get("target_valid_rows"),
        "label_report_target_valid_rows": report_summary.get("target_valid_rows"),
        "label_report_target_invalid_rows": report_summary.get("target_invalid_rows"),
        "timing_warning_count": timing_summary.get("warning_count"),
        "timing_warnings": timing_warnings,
        "invalid_reason_counts": dict(invalid_reasons),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "phase3-001-active-v2-label-lineage-accepted-limited",
            "severity": "Info",
            "finding": "Scoped active v2 Phase 3 label/hash-lineage evidence is accepted for 6E/CL/ES/ZN 2023/2024 only.",
            "verified_facts": [
                f"staged_active_hash_match_count={derived.get('staged_active_hash_match_count')}",
                f"active_feature_hash_match_count={derived.get('active_feature_hash_match_count')}",
                f"label_report_target_valid_rows={derived.get('label_report_target_valid_rows')}",
            ],
            "limitation": "This is not a full Phase 3 Master Audit and does not read label parquet.",
            "evidence_paths": [
                STAGED_LABEL_MANIFEST.as_posix(),
                ACTIVE_LABEL_MANIFEST.as_posix(),
                ACTIVE_REPLACEMENT_HASHES.as_posix(),
                FEATURE_MANIFEST.as_posix(),
            ],
        },
        {
            "finding_id": "phase3-002-target-timing-pass-with-completed-bar-caveat",
            "severity": "Medium",
            "finding": "Target timing evidence passes with the known completed-bar convention warning preserved.",
            "verified_facts": [
                f"timing_warning_count={derived.get('timing_warning_count')}",
                f"timing_warnings={derived.get('timing_warnings')}",
            ],
            "limitation": "Timing evidence is valid only under completed one-minute bar availability semantics.",
            "evidence_paths": [TARGET_TIMING_AUDIT.as_posix()],
        },
        {
            "finding_id": "phase3-003-target-feature-boundary-preserved",
            "severity": "Info",
            "finding": "Target and feature registries remain disjoint, and 15m labels remain diagnostic only.",
            "verified_facts": [
                f"target_count={derived.get('target_count')}",
                f"feature_count={derived.get('feature_count')}",
                f"target_feature_intersection_count={derived.get('target_feature_intersection_count')}",
            ],
            "limitation": "This checks JSON registries only; it does not inspect parquet columns.",
            "evidence_paths": [TARGET_COLS.as_posix(), FEATURE_COLS.as_posix()],
        },
        {
            "finding_id": "phase3-004-full-phase3-and-model-trust-remain-blocked",
            "severity": "Critical",
            "finding": "Full Phase 3 Master Audit acceptance, model trust, promotion, holdout, and paper/live remain blocked.",
            "verified_facts": ["All non-approval flags in this report are false."],
            "limitation": "A separate bounded phase audit would be required for full acceptance.",
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
    phase3_classification = (
        "RUN_LIMITED_SCOPE_PHASE3_ACTIVE_LABEL_TIMING_HASH_LINEAGE_RECONCILIATION"
        if status == PASS_STATUS
        else "FAILED_PHASE3_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase3_reconciliation_report_only",
            "phase": "Phase 3",
            "phase_name": "Labels and targets",
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "market_year_count": EXPECTED_MARKET_YEAR_COUNT,
            "label_semantics_id": EXPECTED_LABEL_SEMANTICS_ID,
            "full_phase3_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase3_master_audit_status": phase3_classification,
            "phase3_limited_label_timing_hash_lineage_ready": status == PASS_STATUS,
            "phase3_full_master_audit_accepted": False,
            "phase3_label_build_accepted": False,
            "target_timing_warning_preserved": derived.get("timing_warnings") == [KNOWN_TIMING_WARNING],
            "completed_bar_timing_warning": KNOWN_TIMING_WARNING,
            "staged_active_hash_match_count": derived.get("staged_active_hash_match_count"),
            "active_feature_hash_match_count": derived.get("active_feature_hash_match_count"),
            "target_feature_intersection_count": derived.get("target_feature_intersection_count"),
            "target_count": derived.get("target_count"),
            "feature_count": derived.get("feature_count"),
            "label_report_target_valid_rows": derived.get("label_report_target_valid_rows"),
            "label_report_target_invalid_rows": derived.get("label_report_target_invalid_rows"),
            "timing_warning_count": derived.get("timing_warning_count"),
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
        "staged_active_hash_comparisons": derived.get("staged_active_hash_comparisons", []),
        "active_feature_hash_comparisons": derived.get("active_feature_hash_comparisons", []),
        "invalid_reason_counts": derived.get("invalid_reason_counts", {}),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required JSON/MD evidence is readable",
                "run-status, overview, Phase 1B, Phase 2, Phase 6, and Phase 7 reconciliation reports are passed report-only inputs",
                "pre-existing Phase 3 ledger row is RUN_LIMITED_SCOPE_TARGET_TIMING_EVIDENCE",
                "Phase 2 prerequisite remains limited hash-lineage evidence with full acceptance false",
                "staged and active label manifests are exact-scope PASS with expected label semantics id",
                "label report has 8 pass files, 0 warnings/failures, consistent row counts, and invalid-reason counts",
                "active replacement hashes prove 8/8 active labels match staged labels",
                "target timing audit is PASS with only the known completed-bar convention warning",
                "Phase 4 feature manifest consumes 8/8 active label hashes",
                "target and feature registries have zero intersection and 15m labels remain diagnostic only",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "scope is not exactly 6E/CL/ES/ZN 2023/2024",
                "label semantics id is missing or changed",
                "any active/staged/feature label hash mismatch",
                "label report warnings, failures, row-count mismatch, or missing invalid-reason evidence",
                "target timing failures, row-key mismatches, 30m/60m violations, or unexpected warnings",
                "target columns intersect feature columns",
                "diagnostic 15m labels are treated as primary acceptance evidence",
                "full Phase 3/model-trust/promotion/holdout/paper/live readiness is upgraded",
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
            "run-status and Phase 1B/2/3/6/7 evidence; do not run data/model/phase commands without "
            "separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 3 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 3 status: `{summary.get('phase3_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Staged/active hash matches: `{summary.get('staged_active_hash_match_count')}`",
        f"- Active/feature hash matches: `{summary.get('active_feature_hash_match_count')}`",
        f"- Target/feature intersection count: `{summary.get('target_feature_intersection_count')}`",
        f"- Target timing warning preserved: `{summary.get('target_timing_warning_preserved')}`",
        f"- Full Phase 3 Master Audit accepted: `{summary.get('phase3_full_master_audit_accepted')}`",
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
    for item in report.get("staged_active_hash_comparisons", []):
        lines.append(f"- `{item.get('active_path')}` staged_matches_active=`{item.get('matches')}`")
    for item in report.get("active_feature_hash_comparisons", []):
        lines.append(f"- `{item.get('path')}` active_matches_feature_input=`{item.get('matches')}`")
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
            "- This reconciliation did not run Phase 3 label build, target timing audit rerun, Phase 2 build/readiness, Phase 1B conversion, phase audits, WFA/modeling, predictions, Phase 8, provider/network calls, promotion, freeze, holdout, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, or model artifacts.",
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
        f"phase3_status={report['summary']['phase3_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
