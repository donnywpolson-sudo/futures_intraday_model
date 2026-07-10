#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 5 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not rebuild
labels, features, or splits; rerun the split-contamination guard; run WFA,
modeling, Phase 6, predictions, Phase 8; call providers/network; promote,
freeze, touch holdout, paper/live, clean up files, stage, commit, or push.
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
STAGE = "master_audit_phase5_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE5_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE5_RECONCILIATION_REPORT_ONLY"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_MARKET_YEAR_COUNT = 8
EXPECTED_FOLD_COUNT = 48
EXPECTED_FOLDS_PER_MARKET = 12
EXPECTED_FEATURE_COUNT = 114
EXPECTED_MIN_PURGE_EMBARGO_BARS = 61
EXPECTED_SPLIT_CLASSIFICATION = "same_fold_rolling_retraining_research_only"
EXPECTED_CONTAMINATION_STATUS = "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD"

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
DEFAULT_PHASE4 = Path(
    "reports/master_audit/master_audit_phase4_reconciliation_20260709/"
    "master_audit_phase4_reconciliation.json"
)
DEFAULT_PHASE6 = Path(
    "reports/master_audit/master_audit_phase6_reconciliation_20260709/"
    "master_audit_phase6_reconciliation.json"
)
DEFAULT_PHASE7 = Path(
    "reports/master_audit/master_audit_phase7_reconciliation_20260709/"
    "master_audit_phase7_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase5_reconciliation_20260709")
REPORT_JSON = "master_audit_phase5_reconciliation.json"
REPORT_MD = "master_audit_phase5_reconciliation.md"

SPLIT_PLAN = Path("reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.json")
CONTAMINATION_AUDIT = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_contamination_audit/"
    "wfa_split_contamination_audit.json"
)
FEATURE_MANIFEST = Path(
    "reports/features_baseline/phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "baseline_feature_manifest.json"
)
FEATURE_PLACEMENT_HASHES = Path(
    "reports/features_baseline/phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "post_active_feature_hashes.json"
)
MODELS_CONFIG = Path("configs/models.yaml")

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "phase1b_reconciliation": DEFAULT_PHASE1B,
    "phase2_reconciliation": DEFAULT_PHASE2,
    "phase3_reconciliation": DEFAULT_PHASE3,
    "phase4_reconciliation": DEFAULT_PHASE4,
    "phase6_reconciliation": DEFAULT_PHASE6,
    "phase7_reconciliation": DEFAULT_PHASE7,
    "split_plan": SPLIT_PLAN,
    "contamination_audit": CONTAMINATION_AUDIT,
    "feature_manifest": FEATURE_MANIFEST,
    "feature_placement_hashes": FEATURE_PLACEMENT_HASHES,
    "models_config": MODELS_CONFIG,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase5_split_build_executed": False,
    "split_contamination_guard_rerun_executed": False,
    "label_rebuild_executed": False,
    "feature_rebuild_executed": False,
    "data_model_commands_executed": False,
    "dbn_read_executed": False,
    "raw_parquet_read_executed": False,
    "causal_parquet_read_executed": False,
    "label_parquet_read_executed": False,
    "feature_parquet_read_executed": False,
    "prediction_parquet_read_executed": False,
    "model_artifact_read_executed": False,
    "wfa_modeling_executed": False,
    "phase6_runner_executed": False,
    "prediction_materialization_executed": False,
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
    "hardened_phase6_materialization_path_consumed": False,
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
            "model_trust_ready": "summary.model_trust_ready",
        },
        "phase3_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase3_master_audit_status": "summary.phase3_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
        },
        "phase4_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase4_master_audit_status": "summary.phase4_master_audit_status",
            "phase4_full_master_audit_accepted": "summary.phase4_full_master_audit_accepted",
            "model_trust_ready": "summary.model_trust_ready",
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
            "promotion_allowed": "summary.promotion_allowed",
        },
        "split_plan": {
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "input_root": "input_root",
            "fold_count": "fold_count",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "contamination_audit": {
            "status": "status",
            "classification": "summary.classification",
            "failure_count": "summary.failure_count",
            "warning_count": "summary.warning_count",
            "model_trust_ready": "summary.model_trust_ready",
            "valid_for_independent_holdout_claims": "summary.valid_for_independent_holdout_claims",
        },
        "feature_manifest": {
            "status": "status",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "feature_count": "feature_count",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "feature_placement_hashes": {"status": "status"},
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


def fold_rows(split_plan: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = None if not isinstance(split_plan, Mapping) else split_plan.get("folds")
    return [row for row in as_list(rows) if isinstance(row, Mapping)]


def split_hash_comparisons(
    *,
    split_plan: Mapping[str, Any] | None,
    feature_manifest: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    split_hashes = file_hashes(split_plan, "input_file_hashes")
    feature_hashes = file_hashes(feature_manifest, "output_file_hashes")
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        path = feature_matrix_path(market, year)
        split_hash = split_hashes.get(path)
        feature_hash = feature_hashes.get(path)
        rows.append(
            {
                "market": market,
                "year": year,
                "path": path,
                "split_input_hash": split_hash,
                "feature_manifest_output_hash": feature_hash,
                "matches": split_hash is not None and split_hash == feature_hash,
            }
        )
    return rows


def placement_hash_comparisons(
    *,
    split_plan: Mapping[str, Any] | None,
    placement: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    split_hashes = file_hashes(split_plan, "input_file_hashes")
    records = as_list(None if not isinstance(placement, Mapping) else placement.get("records"))
    placement_by_path = {
        str(record.get("path")): record for record in records if isinstance(record, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for market, year in expected_pairs():
        path = feature_matrix_path(market, year)
        record = placement_by_path.get(path, {})
        placement_hash = record.get("sha256") if isinstance(record, Mapping) else None
        split_hash = split_hashes.get(path)
        rows.append(
            {
                "market": market,
                "year": year,
                "path": path,
                "split_input_hash": split_hash,
                "placement_sha256": placement_hash,
                "active_matches_staged": record.get("active_matches_staged")
                if isinstance(record, Mapping)
                else None,
                "matches": (
                    split_hash is not None
                    and placement_hash == split_hash
                    and record.get("active_matches_staged") is True
                )
                if isinstance(record, Mapping)
                else False,
            }
        )
    return rows


def fold_scope_summary(folds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    market_counts = dict(Counter(str(row.get("market")) for row in folds))
    split_group_counts = dict(Counter(str(row.get("split_group")) for row in folds))
    years = sorted({as_int(row.get("year")) for row in folds if as_int(row.get("year")) is not None})
    final_holdout_count = sum(
        1 for row in folds if row.get("is_final_holdout") is True or row.get("final_holdout") is True
    )
    selection_false_count = sum(1 for row in folds if row.get("selection_allowed") is not True)
    train_or_test_empty_count = sum(
        1
        for row in folds
        if (as_int(row.get("train_rows_after_purge")) or 0) <= 0
        or (as_int(row.get("test_rows")) or 0) <= 0
    )
    min_purge = min((as_int(row.get("purge_bars")) or 0 for row in folds), default=0)
    min_resolved_purge = min(
        (as_int(row.get("resolved_purge_bars")) or 0 for row in folds), default=0
    )
    min_embargo = min((as_int(row.get("embargo_bars")) or 0 for row in folds), default=0)
    chronological_failures = []
    for row in folds:
        purged_end = str(row.get("purged_train_end") or "")
        test_start = str(row.get("test_start") or "")
        test_end = str(row.get("test_end") or "")
        if not purged_end or not test_start or not test_end or not (purged_end < test_start <= test_end):
            chronological_failures.append(
                {
                    "fold_id": row.get("fold_id"),
                    "purged_train_end": row.get("purged_train_end"),
                    "test_start": row.get("test_start"),
                    "test_end": row.get("test_end"),
                }
            )
    return {
        "fold_count": len(folds),
        "market_counts": market_counts,
        "split_group_counts": split_group_counts,
        "years": years,
        "final_holdout_count": final_holdout_count,
        "selection_false_count": selection_false_count,
        "train_or_test_empty_count": train_or_test_empty_count,
        "min_purge_bars": min_purge,
        "min_resolved_purge_bars": min_resolved_purge,
        "min_embargo_bars": min_embargo,
        "chronological_failure_count": len(chronological_failures),
        "chronological_failures": chronological_failures[:10],
    }


def contamination_warnings(payload: Mapping[str, Any] | None) -> list[str]:
    return [item for item in as_list(None if not isinstance(payload, Mapping) else payload.get("warnings")) if isinstance(item, str)]


def contamination_summary(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return as_mapping(None if not isinstance(payload, Mapping) else payload.get("summary"))


def check_models_config_caveat(
    evidence: Sequence[Mapping[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    item = next((row for row in evidence if row.get("path") == MODELS_CONFIG.as_posix()), {})
    return item.get("exists") is True, {
        "path": item.get("path"),
        "sha256": item.get("sha256"),
        "state": item.get("state"),
        "git_status": item.get("git_status"),
        "caveat": "configs/models.yaml is recorded as current workspace context only; dirty state is not runnable-equivalence proof.",
    }


def build_checks(
    *,
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
        failure=f"missing required Phase 5 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 5 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    phase1b = payloads.get("phase1b_reconciliation")
    phase2 = payloads.get("phase2_reconciliation")
    phase3 = payloads.get("phase3_reconciliation")
    phase4 = payloads.get("phase4_reconciliation")
    phase6 = payloads.get("phase6_reconciliation")
    phase7 = payloads.get("phase7_reconciliation")
    phase5_row = row_by_area(run_status, "Phase 5")
    check(
        checks,
        failures,
        name="master_audit_inputs_are_passed_report_only_evidence",
        passed=run_status is not None
        and overview is not None
        and phase1b is not None
        and phase2 is not None
        and phase3 is not None
        and phase4 is not None
        and phase6 is not None
        and phase7 is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and phase1b.get("status") == "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"
        and phase2.get("status") == "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY"
        and phase3.get("status") == "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY"
        and phase4.get("status") == "PASS_MASTER_AUDIT_PHASE4_RECONCILIATION_REPORT_ONLY"
        and phase6.get("status") == "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY"
        and phase7.get("status") == "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        failure="run-status, overview, or Phase 1B/2/3/4/6/7 input is not passed report-only evidence",
        evidence=[
            DEFAULT_RUN_STATUS.as_posix(),
            DEFAULT_OVERVIEW.as_posix(),
            DEFAULT_PHASE1B.as_posix(),
            DEFAULT_PHASE2.as_posix(),
            DEFAULT_PHASE3.as_posix(),
            DEFAULT_PHASE4.as_posix(),
            DEFAULT_PHASE6.as_posix(),
            DEFAULT_PHASE7.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "phase1b": None if phase1b is None else phase1b.get("status"),
            "phase2": None if phase2 is None else phase2.get("status"),
            "phase3": None if phase3 is None else phase3.get("status"),
            "phase4": None if phase4 is None else phase4.get("status"),
            "phase6": None if phase6 is None else phase6.get("status"),
            "phase7": None if phase7 is None else phase7.get("status"),
        },
    )
    check(
        checks,
        failures,
        name="phase5_ledger_is_limited_split_guard",
        passed=phase5_row is not None
        and phase5_row.get("run_status") == "RUN"
        and phase5_row.get("detail_status") == "RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD"
        and phase5_row.get("evidence_state") == "limited-scope",
        failure="run-status Phase 5 row is not the expected limited split-contamination guard state",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"pre_existing_phase5_row": dict(phase5_row or {})},
    )

    split_plan = payloads.get("split_plan")
    contamination = payloads.get("contamination_audit")
    feature_manifest = payloads.get("feature_manifest")
    placement = payloads.get("feature_placement_hashes")
    folds = fold_rows(split_plan)
    fold_summary = fold_scope_summary(folds)
    check(
        checks,
        failures,
        name="split_plan_scope_and_fold_structure_valid",
        passed=split_plan is not None
        and split_plan.get("profile") == "tier_1"
        and split_plan.get("resolved_profile") == "tier_1_research"
        and split_plan.get("input_root") == "data/feature_matrices"
        and split_plan.get("fold_count") == EXPECTED_FOLD_COUNT
        and list_as_set(split_plan.get("markets")) == set(EXPECTED_MARKETS)
        and list_as_set(split_plan.get("years")) == set(EXPECTED_YEARS)
        and split_plan.get("failure_count") == 0
        and split_plan.get("warning_count") == 0
        and fold_summary["fold_count"] == EXPECTED_FOLD_COUNT
        and fold_summary["market_counts"] == {
            market: EXPECTED_FOLDS_PER_MARKET for market in EXPECTED_MARKETS
        }
        and fold_summary["split_group_counts"] == {"research": EXPECTED_FOLD_COUNT}
        and fold_summary["years"] == [2024]
        and fold_summary["final_holdout_count"] == 0
        and fold_summary["selection_false_count"] == 0
        and fold_summary["train_or_test_empty_count"] == 0
        and fold_summary["chronological_failure_count"] == 0
        and fold_summary["min_purge_bars"] >= EXPECTED_MIN_PURGE_EMBARGO_BARS
        and fold_summary["min_resolved_purge_bars"] >= EXPECTED_MIN_PURGE_EMBARGO_BARS
        and fold_summary["min_embargo_bars"] >= EXPECTED_MIN_PURGE_EMBARGO_BARS,
        failure="Phase 5 split plan scope, fold counts, chronology, or purge/embargo evidence is invalid",
        evidence=[SPLIT_PLAN.as_posix()],
        details={
            "profile": None if split_plan is None else split_plan.get("profile"),
            "resolved_profile": None if split_plan is None else split_plan.get("resolved_profile"),
            "markets": None if split_plan is None else split_plan.get("markets"),
            "years": None if split_plan is None else split_plan.get("years"),
            "fold_summary": fold_summary,
        },
    )

    feature_match_rows = split_hash_comparisons(
        split_plan=split_plan,
        feature_manifest=feature_manifest,
    )
    feature_match_count = sum(1 for row in feature_match_rows if row["matches"])
    placement_match_rows = placement_hash_comparisons(split_plan=split_plan, placement=placement)
    placement_match_count = sum(1 for row in placement_match_rows if row["matches"])
    feature_gate = as_mapping(None if split_plan is None else split_plan.get("feature_manifest_gate"))
    check(
        checks,
        failures,
        name="split_plan_feature_hashes_match_active_phase4_evidence",
        passed=feature_manifest is not None
        and feature_manifest.get("status") == "PASS"
        and feature_manifest.get("feature_count") == EXPECTED_FEATURE_COUNT
        and feature_match_count == EXPECTED_MARKET_YEAR_COUNT
        and placement_match_count == EXPECTED_MARKET_YEAR_COUNT
        and feature_gate.get("status") == "PASS",
        failure="Phase 5 split plan input hashes do not match active Phase 4 feature manifest/placement evidence",
        evidence=[SPLIT_PLAN.as_posix(), FEATURE_MANIFEST.as_posix(), FEATURE_PLACEMENT_HASHES.as_posix()],
        details={
            "feature_manifest_status": None if feature_manifest is None else feature_manifest.get("status"),
            "feature_count": None if feature_manifest is None else feature_manifest.get("feature_count"),
            "feature_gate": dict(feature_gate),
            "feature_match_count": feature_match_count,
            "feature_comparisons": feature_match_rows,
            "placement_match_count": placement_match_count,
            "placement_comparisons": placement_match_rows,
        },
    )

    contamination_scope = as_mapping(None if contamination is None else contamination.get("scope"))
    contamination_summary_map = contamination_summary(contamination)
    warnings = contamination_warnings(contamination)
    check(
        checks,
        failures,
        name="split_contamination_guard_reconciles_research_only",
        passed=contamination is not None
        and contamination.get("status") == EXPECTED_CONTAMINATION_STATUS
        and contamination_summary_map.get("failure_count") == 0
        and contamination_summary_map.get("warning_count") == 2
        and contamination_summary_map.get("fold_count") == EXPECTED_FOLD_COUNT
        and contamination_summary_map.get("market_year_count") == EXPECTED_MARKET_YEAR_COUNT
        and contamination_summary_map.get("classification") == EXPECTED_SPLIT_CLASSIFICATION
        and contamination_summary_map.get("valid_for_same_fold_rolling_retraining_research_evidence")
        is True
        and contamination_summary_map.get("valid_for_independent_holdout_claims") is False
        and contamination_summary_map.get("model_trust_ready") is False
        and any("WARN_EXPECTED_ROLLING_RETRAINING_REUSE" in warning for warning in warnings)
        and any("WARN_NO_INNER_VALIDATION_WINDOW" in warning for warning in warnings),
        failure="split-contamination guard is not PASS research-only evidence with preserved warnings",
        evidence=[CONTAMINATION_AUDIT.as_posix()],
        details={
            "status": None if contamination is None else contamination.get("status"),
            "summary": dict(contamination_summary_map),
            "scope": dict(contamination_scope),
            "warnings": warnings,
        },
    )

    models_config_present, models_config_caveat = check_models_config_caveat(evidence)
    check(
        checks,
        failures,
        name="dirty_models_config_is_caveat_not_runnable_proof",
        passed=models_config_present,
        failure="configs/models.yaml evidence is missing; dirty-config caveat cannot be recorded",
        evidence=[MODELS_CONFIG.as_posix()],
        details=models_config_caveat,
    )

    blocker_details = {
        "phase4_full_master_audit_accepted": dotted_get(
            phase4, "summary.phase4_full_master_audit_accepted"
        ),
        "phase4_model_trust_ready": dotted_get(phase4, "summary.model_trust_ready"),
        "phase6_model_trust_ready": dotted_get(phase6, "summary.model_trust_ready"),
        "phase7_model_trust_ready": dotted_get(phase7, "summary.model_trust_ready"),
        "phase7_promotion_allowed": dotted_get(phase7, "summary.promotion_allowed"),
    }
    check(
        checks,
        failures,
        name="independent_holdout_and_model_trust_remain_blocked",
        passed=blocker_details["phase4_full_master_audit_accepted"] is False
        and blocker_details["phase4_model_trust_ready"] is False
        and blocker_details["phase6_model_trust_ready"] is False
        and blocker_details["phase7_model_trust_ready"] is False
        and blocker_details["phase7_promotion_allowed"] is False,
        failure="upstream/downstream reports unexpectedly upgrade full acceptance, model trust, or promotion",
        evidence=[DEFAULT_PHASE4.as_posix(), DEFAULT_PHASE6.as_posix(), DEFAULT_PHASE7.as_posix()],
        details=blocker_details,
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "fold_count": len(folds),
        "fold_summary": fold_summary,
        "feature_hash_match_count": feature_match_count,
        "feature_hash_comparisons": feature_match_rows,
        "placement_hash_match_count": placement_match_count,
        "placement_hash_comparisons": placement_match_rows,
        "classification": contamination_summary_map.get("classification"),
        "contamination_warning_count": contamination_summary_map.get("warning_count"),
        "contamination_warnings": warnings,
        "models_config_caveat": models_config_caveat,
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "phase5-001-limited-split-plan-reconciled",
            "severity": "Info",
            "finding": "Scoped active v2 Phase 5 split-plan evidence is accepted for 6E/CL/ES/ZN 2023/2024 only.",
            "verified_facts": [
                f"fold_count={derived.get('fold_count')}",
                f"feature_hash_match_count={derived.get('feature_hash_match_count')}",
                f"placement_hash_match_count={derived.get('placement_hash_match_count')}",
            ],
            "limitation": "This is report-only split evidence and does not rebuild splits or read feature parquet.",
            "evidence_paths": [SPLIT_PLAN.as_posix(), FEATURE_MANIFEST.as_posix()],
        },
        {
            "finding_id": "phase5-002-contamination-guard-research-only",
            "severity": "High",
            "finding": "The split-contamination guard passes only as same-fold rolling-retraining research evidence.",
            "verified_facts": [
                f"classification={derived.get('classification')}",
                f"contamination_warning_count={derived.get('contamination_warning_count')}",
            ],
            "limitation": "Independent holdout, model-trust, promotion, holdout, and paper/live claims remain blocked.",
            "evidence_paths": [CONTAMINATION_AUDIT.as_posix()],
        },
        {
            "finding_id": "phase5-003-models-config-dirty-caveat",
            "severity": "Medium",
            "finding": "configs/models.yaml is dirty in the worktree and is treated as a runnable-equivalence caveat.",
            "verified_facts": [str(derived.get("models_config_caveat"))],
            "limitation": "Recorded split evidence remains accepted, but current runnable equivalence is not proven by this report.",
            "evidence_paths": [MODELS_CONFIG.as_posix()],
        },
        {
            "finding_id": "phase5-004-full-phase5-and-model-trust-remain-blocked",
            "severity": "Critical",
            "finding": "Full Phase 5 Master Audit acceptance, model trust, promotion, holdout, and paper/live remain blocked.",
            "verified_facts": ["All non-approval flags in this report are false."],
            "limitation": "A separate bounded split hardening or validation path would be required for stronger claims.",
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
    phase5_classification = (
        "RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD"
        if status == PASS_STATUS
        else "FAILED_PHASE5_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase5_reconciliation_report_only",
            "phase": "Phase 5",
            "phase_name": "WFA split planning and split-contamination evidence",
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "parquet_read_scope": "none",
            "phase_command_scope": "none",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "fold_count": EXPECTED_FOLD_COUNT,
            "full_phase5_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase5_master_audit_status": phase5_classification,
            "phase5_limited_split_research_evidence_ready": status == PASS_STATUS,
            "phase5_full_master_audit_accepted": False,
            "split_plan_accepted_as_current_runnable_proof": False,
            "classification": derived.get("classification"),
            "valid_for_same_fold_rolling_retraining_research_evidence": status == PASS_STATUS,
            "valid_for_independent_holdout_claims": False,
            "fold_count": derived.get("fold_count"),
            "fold_summary": derived.get("fold_summary"),
            "feature_hash_match_count": derived.get("feature_hash_match_count"),
            "placement_hash_match_count": derived.get("placement_hash_match_count"),
            "contamination_warning_count": derived.get("contamination_warning_count"),
            "contamination_warnings": derived.get("contamination_warnings"),
            "models_config_caveat": derived.get("models_config_caveat"),
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
        "feature_hash_comparisons": derived.get("feature_hash_comparisons", []),
        "placement_hash_comparisons": derived.get("placement_hash_comparisons", []),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required JSON/MD evidence and configs/models.yaml are readable/hashable",
                "run-status, overview, and Phase 1B/2/3/4/6/7 reconciliation inputs are passed report-only evidence",
                "Phase 5 ledger row is RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD",
                "split plan exact scope is 6E/CL/ES/ZN 2023/2024 with 48 research folds and no final-holdout folds",
                "split plan has zero failures/warnings and purge/resolved-purge/embargo bars at least 61",
                "split plan input feature hashes match active Phase 4 feature manifest and placement hash evidence for all 8 market-years",
                "split-contamination audit is PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD with failure_count 0 and warning_count 2",
                "classification remains same_fold_rolling_retraining_research_only",
                "independent holdout, model trust, promotion, holdout, and paper/live remain blocked",
                "dirty configs/models.yaml is preserved as a caveat rather than runnable proof",
                "all non-approval flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "scope/profile/market/year/fold-count mismatch",
                "split plan warnings/failures, final-holdout folds, empty train/test folds, chronology failures, or insufficient purge/embargo",
                "feature hash mismatch against active Phase 4 evidence",
                "contamination audit not PASS research-only evidence",
                "classification changes away from same-fold rolling-retraining research-only",
                "independent holdout, model-trust, promotion, holdout, or paper/live readiness is upgraded",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan exactly one next bounded Master Audit area from the updated Phase 1B/2/3/4/5/6/7 "
            "report-only evidence; do not run data/model/phase commands without separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 5 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 5 status: `{summary.get('phase5_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Classification: `{summary.get('classification')}`",
        f"- Fold count: `{summary.get('fold_count')}`",
        f"- Feature hash matches: `{summary.get('feature_hash_match_count')}`",
        f"- Placement hash matches: `{summary.get('placement_hash_match_count')}`",
        f"- Contamination warning count: `{summary.get('contamination_warning_count')}`",
        f"- Independent holdout claims valid: `{summary.get('valid_for_independent_holdout_claims')}`",
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
    lines.extend(["", "## Feature Hashes", ""])
    for item in report.get("feature_hash_comparisons", []):
        lines.append(f"- `{item.get('path')}` split_matches_feature_manifest=`{item.get('matches')}`")
    for item in report.get("placement_hash_comparisons", []):
        lines.append(f"- `{item.get('path')}` split_matches_active_placement=`{item.get('matches')}`")
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
            "- This reconciliation did not rebuild labels/features/splits, rerun the split-contamination guard, run WFA/modeling, run the Phase 6 runner, materialize predictions, run Phase 8, call providers/network, approve promotion, freeze artifacts, touch holdout, paper trade, live trade, clean up files, stage, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, or model artifacts, and it did not consume or advance the hardened split candidate or hardened Phase 6 materialization path.",
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
        f"phase5_status={report['summary']['phase5_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
