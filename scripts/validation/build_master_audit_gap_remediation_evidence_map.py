#!/usr/bin/env python3
"""Build a fail-closed Master Audit gap remediation evidence map.

This command inventories existing local evidence only. It does not run phase
audits, data/model commands, WFA/modeling, prediction generation, Phase 8
refresh, provider calls, promotion, freeze, holdout, paper/live, cleanup,
staging, commit, or push.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_closeout as closeout
from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_gap_remediation_evidence_map"
PASS_STATUS = "PASS_MASTER_AUDIT_GAP_REMEDIATION_EVIDENCE_MAP_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_GAP_REMEDIATION_EVIDENCE_MAP_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_gap_remediation_20260710")
REPORT_JSON = "master_audit_gap_remediation_evidence_map.json"
REPORT_MD = "master_audit_gap_remediation_evidence_map.md"

GAP_AREAS = ("data_integrity", "statistical_validity", "operational_resilience")

SOURCE_PATHS = {
    "phase1a_reconciliation": Path(
        "reports/master_audit/master_audit_phase1a_reconciliation_20260710/"
        "master_audit_phase1a_reconciliation.json"
    ),
    "master_readiness": Path(
        "reports/master_audit/master_audit_research_factory_readiness_20260710/"
        "master_audit_research_factory_readiness.json"
    ),
    "run_status": Path(
        "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
    ),
    "phase1b_reconciliation": Path(
        "reports/master_audit/master_audit_phase1b_reconciliation_20260709/"
        "master_audit_phase1b_reconciliation.json"
    ),
    "phase1b_broad_reconciliation": Path(
        "reports/master_audit/master_audit_phase1b_broad_reconciliation_20260710/"
        "master_audit_phase1b_broad_reconciliation.json"
    ),
    "phase2_reconciliation": Path(
        "reports/master_audit/master_audit_phase2_reconciliation_20260709/"
        "master_audit_phase2_reconciliation.json"
    ),
    "phase2_active_scope_reconciliation": Path(
        "reports/master_audit/master_audit_phase2_active_scope_reconciliation_20260710/"
        "master_audit_phase2_active_scope_reconciliation.json"
    ),
    "target_timing": Path(
        "reports/model_trust_audit/target_timing_v2_tier1_core_20260709/"
        "target_timing_audit.json"
    ),
    "statistical_validity": Path(
        "reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/"
        "statistical_validity_summary.json"
    ),
    "alpha_gap_matrix": Path(
        "reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/"
        "alpha_evidence_gap_matrix.json"
    ),
    "alpha_completion_closeout": Path(
        "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
        "alpha_evidence_completion_closeout.json"
    ),
    "execution_realism": Path(
        "reports/execution_realism/tier1_core_phase6_full_predictions_20260706/"
        "execution_realism_summary.json"
    ),
    "adversarial_audit": Path("docs/adversarial_current_project_evidence_gate_audit_20260709.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
}

JSON_FIELDS = {
    "phase1a_reconciliation": {
        "status": "status",
        "phase1a_source_lineage_ready": "summary.phase1a_source_lineage_ready",
        "archive_coverage_status": "summary.archive_coverage_status",
        "expected_archive_count": "summary.expected_archive_count",
        "missing_archive_count": "summary.missing_archive_count",
        "missing_manifest_count": "summary.missing_manifest_count",
        "invalid_manifest_count": "summary.invalid_manifest_count",
        "registry_validation_failure_count": "summary.registry_validation_failure_count",
        "original_delivery_reproducibility_ready": (
            "summary.original_delivery_reproducibility_ready"
        ),
        "model_trust_ready": "summary.model_trust_ready",
        "promotion_allowed": "summary.promotion_allowed",
    },
    "master_readiness": {
        "status": "status",
        "readiness_score": "summary.readiness_score",
        "data_integrity_score": "research_readiness.scores.data_integrity",
        "statistical_validity_score": "research_readiness.scores.statistical_validity",
        "operational_resilience_score": "research_readiness.scores.operational_resilience",
        "model_trust_ready": "summary.model_trust_ready",
        "paper_live_ready": "summary.paper_live_ready",
        "promotion_allowed": "summary.promotion_allowed",
    },
    "run_status": {
        "status": "status",
        "current_line_classification": "summary.current_line_classification",
        "current_split_classification": "summary.current_split_classification",
    },
    "phase1b_reconciliation": {
        "status": "status",
        "broad_phase1b_accepted": "summary.broad_phase1b_accepted",
        "broad_phase1b_alignment_status": "summary.broad_phase1b_alignment_status",
        "phase1b_limited_scope_ready": "summary.phase1b_limited_scope_ready",
        "raw_dbn_alignment_audit_executed": "summary.raw_dbn_alignment_audit_executed",
    },
    "phase1b_broad_reconciliation": {
        "status": "status",
        "raw_row_parity_and_conversion_ready": (
            "summary.raw_row_parity_and_conversion_ready"
        ),
        "broad_phase1b_accepted": "summary.broad_phase1b_accepted",
        "market_report_count": "summary.market_report_count",
        "pass_market_reports": "summary.pass_market_reports",
        "fail_market_reports": "summary.fail_market_reports",
        "missing_report_count": "summary.missing_report_count",
        "expected_market_year_count": "summary.expected_market_year_count",
        "raw_market_year_count": "summary.raw_market_year_count",
        "needs_phase1b_conversion_count": "summary.needs_phase1b_conversion_count",
        "raw_only_count": "summary.raw_only_count",
        "invalid_manifest_count": "summary.invalid_manifest_count",
        "source_hash_mismatch_count": "summary.source_hash_mismatch_count",
        "definition_join_mismatch_count": "summary.definition_join_mismatch_count",
        "raw_schema_failure_count": "summary.raw_schema_failure_count",
        "required_schema_exception_failure_count": (
            "summary.required_schema_exception_failure_count"
        ),
        "accepted_repair_source_count": "summary.accepted_repair_source_count",
        "legacy_full_alignment_context": "summary.legacy_full_alignment_context",
        "raw_dbn_alignment_audit_executed": "summary.raw_dbn_alignment_audit_executed",
        "phase1b_conversion_executed": "summary.phase1b_conversion_executed",
        "phase2_accepted": "summary.phase2_accepted",
        "model_trust_ready": "summary.model_trust_ready",
        "promotion_allowed": "summary.promotion_allowed",
    },
    "phase2_reconciliation": {
        "status": "status",
        "phase2_full_master_audit_accepted": "summary.phase2_full_master_audit_accepted",
        "phase2_limited_active_hash_lineage_ready": (
            "summary.phase2_limited_active_hash_lineage_ready"
        ),
        "phase2_session_normalization_audit_accepted": (
            "summary.phase2_session_normalization_audit_accepted"
        ),
        "readiness_status": "summary.readiness_status",
    },
    "phase2_active_scope_reconciliation": {
        "status": "status",
        "causal_session_active_scope_ready": (
            "summary.causal_session_active_scope_ready"
        ),
        "phase2_active_scope_ready": "summary.phase2_active_scope_ready",
        "active_scoped_output_count": "summary.active_scoped_output_count",
        "active_hash_match_count": "summary.active_hash_match_count",
        "phase2_full_master_audit_accepted": (
            "summary.phase2_full_master_audit_accepted"
        ),
        "phase2_session_normalization_audit_accepted": (
            "summary.phase2_session_normalization_audit_accepted"
        ),
        "phase2_build_or_readiness_accepted": (
            "summary.phase2_build_or_readiness_accepted"
        ),
        "audit_phase2_causal_session_normalization_executed": (
            "summary.audit_phase2_causal_session_normalization_executed"
        ),
        "phase2_readiness_or_build_executed": (
            "summary.phase2_readiness_or_build_executed"
        ),
        "causal_rebuild_executed": "summary.causal_rebuild_executed",
        "parquet_audit_executed": "summary.parquet_audit_executed",
        "causal_parquet_read_executed": "summary.causal_parquet_read_executed",
        "readiness_status": "summary.readiness_status",
        "readiness_severe_blocker_count": "summary.readiness_severe_blocker_count",
        "scoped_raw_without_causal_count": "summary.scoped_raw_without_causal_count",
        "target_timing_status": "summary.target_timing_status",
        "target_timing_pair_count": "summary.target_timing_pair_count",
        "target_timing_row_count": "summary.target_timing_row_count",
        "target_timing_row_key_mismatches": (
            "summary.target_timing_row_key_mismatches"
        ),
        "target_timing_entry_30m_not_after_ts": (
            "summary.target_timing_entry_30m_not_after_ts"
        ),
        "target_timing_entry_60m_not_after_ts": (
            "summary.target_timing_entry_60m_not_after_ts"
        ),
        "target_timing_exit_30m_offset_mismatches": (
            "summary.target_timing_exit_30m_offset_mismatches"
        ),
        "target_timing_exit_60m_offset_mismatches": (
            "summary.target_timing_exit_60m_offset_mismatches"
        ),
        "target_timing_same_session_30m_violations": (
            "summary.target_timing_same_session_30m_violations"
        ),
        "target_timing_same_session_60m_violations": (
            "summary.target_timing_same_session_60m_violations"
        ),
        "completed_bar_convention_assumed": (
            "summary.completed_bar_convention_assumed"
        ),
        "model_trust_ready": "summary.model_trust_ready",
        "promotion_allowed": "summary.promotion_allowed",
        "paper_live_allowed": "summary.paper_live_allowed",
        "production_ready": "summary.production_ready",
    },
    "target_timing": {
        "status": "status",
        "failure_count": "summary.failure_count",
        "warning_count": "summary.warning_count",
    },
    "statistical_validity": {
        "status": "status",
        "statistical_validity_ready": "statistical_validity_ready",
        "failure_count": "failure_count",
    },
    "alpha_gap_matrix": {
        "status": "status",
        "verdict": "verdict",
        "alpha_evidence_ready": "alpha_evidence_ready",
    },
    "alpha_completion_closeout": {
        "status": "status",
        "verdict": "verdict",
        "future_evidence_work_allowed": "future_evidence_work_allowed",
        "future_modeling_allowed": "future_modeling_allowed",
        "promotion_allowed": "promotion_allowed",
    },
    "execution_realism": {
        "status": "status",
        "gate_status": "execution_realism_gate.status",
        "execution_realism_ready": "execution_realism_gate.execution_realism_ready",
        "failure_count": "execution_realism_gate.failure_count",
    },
}

CHECK_SPECS = [
    {
        "area": "data_integrity",
        "check_id": "source_acquisition_lineage",
        "name": "Accepted provider/source acquisition lineage",
        "source_keys": ["phase1a_reconciliation"],
        "pass_when": "phase1a_source_lineage_ready",
        "pass_rationale": (
            "Reviewed PASS: Phase 1A source-lineage reconciliation passed report-only "
            "using existing registry and archive-coverage evidence. Original-delivery "
            "reproducibility remains a caveat, not a model-trust upgrade."
        ),
        "rationale": (
            "Reviewed FAIL: the Master Audit evidence map reports Phase 1A as NOT_RUN/"
            "unknown, so accepted provider/source acquisition lineage is not established."
        ),
    },
    {
        "area": "data_integrity",
        "check_id": "raw_row_parity_and_conversion",
        "name": "Raw DBN/raw parquet row parity and conversion evidence",
        "source_keys": ["phase1b_broad_reconciliation", "phase1b_reconciliation", "run_status"],
        "pass_when": "phase1b_broad_raw_parity_ready",
        "pass_rationale": (
            "Reviewed PASS: broad Phase 1B raw row-parity/conversion reconciliation "
            "passed report-only using existing 33-market expected-only evidence. The "
            "older full-profile alignment FAIL is preserved as superseded context; "
            "Phase 2, model trust, and promotion remain blocked."
        ),
        "rationale": (
            "Reviewed FAIL: Phase 1B evidence is limited-scope report-only evidence; "
            "broad Phase 1B acceptance is false and raw DBN alignment execution was not run."
        ),
    },
    {
        "area": "data_integrity",
        "check_id": "causal_session_active_scope",
        "name": "Causal/session normalization and active scope lineage",
        "source_keys": [
            "phase2_active_scope_reconciliation",
            "phase2_reconciliation",
            "target_timing",
        ],
        "pass_when": "phase2_active_scope_ready",
        "pass_rationale": (
            "Reviewed PASS: Phase 2 active-scope causal/session reconciliation "
            "passed report-only using existing active manifests, active-to-label hash "
            "lineage, readiness caveats, and target-timing evidence for 6E/CL/ES/ZN "
            "2023/2024. Full Phase 2 Master Audit acceptance, model trust, and "
            "promotion remain blocked."
        ),
        "rationale": (
            "Reviewed FAIL: Phase 2 has limited active hash-lineage evidence only; full "
            "Master Audit acceptance and session-normalization acceptance remain false."
        ),
    },
    {
        "area": "statistical_validity",
        "check_id": "locked_oos_and_baseline_comparability",
        "name": "Locked OOS eligibility and baseline comparability",
        "source_keys": ["alpha_gap_matrix", "alpha_completion_closeout", "run_status"],
        "rationale": (
            "Reviewed FAIL: current split evidence is same-fold rolling-retraining "
            "research-only, and baseline/null blockers remain in the alpha evidence closeout."
        ),
    },
    {
        "area": "statistical_validity",
        "check_id": "trial_ledger_and_overfit_accounting",
        "name": "Trial ledger, PBO, Deflated Sharpe, and multiple-testing accounting",
        "source_keys": ["statistical_validity", "alpha_gap_matrix", "adversarial_audit"],
        "rationale": (
            "Reviewed FAIL: local statistical-validity evidence reports missing trial/search "
            "path evidence for PBO, Deflated Sharpe, and multiple-testing acceptance."
        ),
    },
    {
        "area": "statistical_validity",
        "check_id": "stability_regime_concept_drift",
        "name": "Parameter stability, regime breakdown, and concept-drift evidence",
        "source_keys": ["statistical_validity", "project_outline", "adversarial_audit"],
        "rationale": (
            "Reviewed FAIL: required regime/stability/concept-drift evidence is not "
            "accepted for model-trust or promotion claims."
        ),
    },
    {
        "area": "operational_resilience",
        "check_id": "execution_realism_fail_closed",
        "name": "Execution realism, partial fills, rejects, liquidity, slippage, and delay",
        "source_keys": ["execution_realism", "adversarial_audit"],
        "rationale": (
            "Reviewed FAIL: the execution-realism intake reports all four required "
            "categories as reviewed FAIL and execution_realism_ready=false."
        ),
    },
    {
        "area": "operational_resilience",
        "check_id": "paper_live_controls_and_broker_state",
        "name": "Paper/live controls, broker order state, and reconciliation",
        "source_keys": ["project_outline", "adversarial_audit", "alpha_completion_closeout"],
        "rationale": (
            "Reviewed FAIL: broker/order-ID, cancel-replace, partial-fill/reject, stale "
            "prediction, reconciliation, and paper/live runbook evidence is not accepted."
        ),
    },
    {
        "area": "operational_resilience",
        "check_id": "monitoring_rollback_kill_switches",
        "name": "Monitoring, rollback, kill switches, and operational incident controls",
        "source_keys": ["project_outline", "master_readiness"],
        "rationale": (
            "Reviewed FAIL: production and paper/live readiness remain false, and required "
            "monitoring, rollback, kill-switch, and incident-control evidence is missing."
        ),
    },
]

NON_APPROVAL = dict(closeout.NON_APPROVAL)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def build_input_evidence(
    *,
    repo_root: Path,
    source_paths: Mapping[str, Path],
    dirty_map: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    return {
        key: inventory.evidence_file(
            repo_root=repo_root,
            relative_path=path,
            json_fields=JSON_FIELDS.get(key),
            dirty_map=dirty_map,
        )
        for key, path in source_paths.items()
    }


def _source_hashes(
    source_keys: Sequence[str],
    source_evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key in source_keys:
        evidence = source_evidence.get(key, {})
        path = evidence.get("path")
        digest = evidence.get("sha256")
        if path and digest:
            hashes[str(path)] = str(digest)
    return hashes


def _missing_sources(
    source_keys: Sequence[str],
    source_evidence: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    missing: list[str] = []
    for key in source_keys:
        evidence = source_evidence.get(key, {})
        if not evidence.get("exists") or evidence.get("read_error"):
            missing.append(str(evidence.get("path") or key))
    return missing


def _phase1a_source_lineage_ready(
    source_evidence: Mapping[str, Mapping[str, Any]],
) -> bool:
    evidence = source_evidence.get("phase1a_reconciliation", {})
    fields = evidence.get("fields")
    if not isinstance(fields, Mapping):
        return False
    return (
        fields.get("status") == "PASS_MASTER_AUDIT_PHASE1A_RECONCILIATION_REPORT_ONLY"
        and fields.get("phase1a_source_lineage_ready") is True
        and fields.get("archive_coverage_status") == "PASS"
        and fields.get("expected_archive_count") == 2108
        and fields.get("missing_archive_count") == 0
        and fields.get("missing_manifest_count") == 0
        and fields.get("invalid_manifest_count") == 0
        and fields.get("registry_validation_failure_count") == 0
        and fields.get("model_trust_ready") is False
        and fields.get("promotion_allowed") is False
    )


def _phase1b_broad_raw_parity_ready(
    source_evidence: Mapping[str, Mapping[str, Any]],
) -> bool:
    evidence = source_evidence.get("phase1b_broad_reconciliation", {})
    fields = evidence.get("fields")
    if not isinstance(fields, Mapping):
        return False
    return (
        fields.get("status") == "PASS_MASTER_AUDIT_PHASE1B_BROAD_RECONCILIATION_REPORT_ONLY"
        and fields.get("raw_row_parity_and_conversion_ready") is True
        and fields.get("broad_phase1b_accepted") is True
        and fields.get("market_report_count") == 33
        and fields.get("pass_market_reports") == 33
        and fields.get("fail_market_reports") == 0
        and fields.get("missing_report_count") == 0
        and fields.get("expected_market_year_count") == 527
        and fields.get("raw_market_year_count") == 527
        and fields.get("needs_phase1b_conversion_count") == 0
        and fields.get("raw_only_count") == 0
        and fields.get("invalid_manifest_count") == 0
        and fields.get("source_hash_mismatch_count") == 0
        and fields.get("definition_join_mismatch_count") == 0
        and fields.get("raw_schema_failure_count") == 0
        and fields.get("required_schema_exception_failure_count") == 0
        and fields.get("accepted_repair_source_count") == 6
        and fields.get("legacy_full_alignment_context")
        == "SUPERSEDED_BY_CORRECTED_EXPECTED_ONLY_BATCHES"
        and fields.get("raw_dbn_alignment_audit_executed") is False
        and fields.get("phase1b_conversion_executed") is False
        and fields.get("phase2_accepted") is False
        and fields.get("model_trust_ready") is False
        and fields.get("promotion_allowed") is False
    )


def _phase2_active_scope_ready(
    source_evidence: Mapping[str, Mapping[str, Any]],
) -> bool:
    evidence = source_evidence.get("phase2_active_scope_reconciliation", {})
    fields = evidence.get("fields")
    if not isinstance(fields, Mapping):
        return False
    return (
        fields.get("status")
        == "PASS_MASTER_AUDIT_PHASE2_ACTIVE_SCOPE_RECONCILIATION_REPORT_ONLY"
        and fields.get("causal_session_active_scope_ready") is True
        and fields.get("phase2_active_scope_ready") is True
        and fields.get("active_scoped_output_count") == 8
        and fields.get("active_hash_match_count") == 8
        and fields.get("phase2_full_master_audit_accepted") is False
        and fields.get("phase2_session_normalization_audit_accepted") is False
        and fields.get("phase2_build_or_readiness_accepted") is False
        and fields.get("audit_phase2_causal_session_normalization_executed") is False
        and fields.get("phase2_readiness_or_build_executed") is False
        and fields.get("causal_rebuild_executed") is False
        and fields.get("parquet_audit_executed") is False
        and fields.get("causal_parquet_read_executed") is False
        and fields.get("readiness_status") == "WARN"
        and fields.get("readiness_severe_blocker_count") == 0
        and fields.get("scoped_raw_without_causal_count") == 0
        and fields.get("target_timing_status") == "PASS_TARGET_TIMING_AUDIT"
        and fields.get("target_timing_pair_count") == 8
        and fields.get("target_timing_row_count") == 2_837_374
        and fields.get("target_timing_row_key_mismatches") == 0
        and fields.get("target_timing_entry_30m_not_after_ts") == 0
        and fields.get("target_timing_entry_60m_not_after_ts") == 0
        and fields.get("target_timing_exit_30m_offset_mismatches") == 0
        and fields.get("target_timing_exit_60m_offset_mismatches") == 0
        and fields.get("target_timing_same_session_30m_violations") == 0
        and fields.get("target_timing_same_session_60m_violations") == 0
        and fields.get("completed_bar_convention_assumed") is True
        and fields.get("model_trust_ready") is False
        and fields.get("promotion_allowed") is False
        and fields.get("paper_live_allowed") is False
        and fields.get("production_ready") is False
    )


def _spec_passes(
    spec: Mapping[str, Any],
    source_evidence: Mapping[str, Mapping[str, Any]],
) -> bool:
    if spec.get("pass_when") == "phase1a_source_lineage_ready":
        return _phase1a_source_lineage_ready(source_evidence)
    if spec.get("pass_when") == "phase1b_broad_raw_parity_ready":
        return _phase1b_broad_raw_parity_ready(source_evidence)
    if spec.get("pass_when") == "phase2_active_scope_ready":
        return _phase2_active_scope_ready(source_evidence)
    return False


def build_gap_checks(
    *,
    source_evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    checks_by_area = {area: [] for area in GAP_AREAS}
    for spec in CHECK_SPECS:
        source_keys = list(spec["source_keys"])
        missing = _missing_sources(source_keys, source_evidence)
        source_hashes = _source_hashes(source_keys, source_evidence)
        passed = not missing and _spec_passes(spec, source_evidence)
        status = "PASS" if passed else "MISSING_EVIDENCE" if missing else "FAIL"
        reason = (
            f"source evidence missing or unreadable: {missing}"
            if missing
            else str(spec.get("pass_rationale") if passed else spec["rationale"])
        )
        check = {
            "check_id": spec["check_id"],
            "name": spec["name"],
            "status": status,
            "review_status": "PASS" if passed else "FAIL",
            "review_rationale": reason,
            "evidence_paths": [
                str(source_evidence[key]["path"])
                for key in source_keys
                if source_evidence.get(key, {}).get("path")
            ],
            "source_hashes": source_hashes,
            "source_keys": source_keys,
            "score_eligible": False,
        }
        checks_by_area[str(spec["area"])].append(check)
    return checks_by_area


def _area_status(checks: Sequence[Mapping[str, Any]]) -> str:
    statuses = {str(check.get("status")) for check in checks}
    if "MISSING_EVIDENCE" in statuses:
        return "MISSING_EVIDENCE"
    if "FAIL" in statuses:
        return "FAIL"
    return "PASS" if checks else "MISSING_EVIDENCE"


def build_gap_maps(
    *,
    source_evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    checks_by_area = build_gap_checks(source_evidence=source_evidence)
    maps: dict[str, dict[str, Any]] = {}
    for area in GAP_AREAS:
        checks = checks_by_area[area]
        status = _area_status(checks)
        maps[area] = {
            "status": status,
            "ready": status == "PASS",
            "score_eligible": False,
            "score_contribution": 0,
            "checks": checks,
            "failure_count": sum(1 for check in checks if check["status"] != "PASS"),
            "accepted_evidence": [],
            "accepted_check_ids": [
                str(check["check_id"]) for check in checks if check["status"] == "PASS"
            ],
            "missing_evidence": [
                check["name"] for check in checks if check["status"] != "PASS"
            ],
        }
    return maps


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    source_paths: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    paths = dict(source_paths or SOURCE_PATHS)
    if git_status_lines is None:
        git_status = inventory.collect_git_status(repo_root)
        status_lines = list(git_status["status_lines"])
        git_status_error = git_status["error"]
    else:
        status_lines = list(git_status_lines)
        git_status_error = None
    dirty_map = inventory.build_dirty_path_map(status_lines)
    source_evidence = build_input_evidence(
        repo_root=repo_root,
        source_paths=paths,
        dirty_map=dirty_map,
    )
    gap_maps = build_gap_maps(source_evidence=source_evidence)
    output_rel = rel(reports_root, repo_root)
    failures: list[str] = []
    if output_rel == "." or output_rel.startswith(("data/", "configs/", "models/", "predictions/")):
        failures.append(f"invalid report output root for gap remediation map: {output_rel}")
    report_status = PASS_STATUS if not failures else FAIL_STATUS
    return {
        "status": report_status,
        "stage": STAGE,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "operation": "master_audit_gap_remediation_evidence_map_only",
            "reports_root": output_rel,
            "gap_areas": list(GAP_AREAS),
            "data_model_scope": "none",
            "phase_audit_scope": "none",
            "allowed_inputs": [
                "existing local repo evidence",
                "current git status --short",
            ],
        },
        "summary": {
            "failure_count": len(failures),
            "gap_area_statuses": {
                area: gap_maps[area]["status"] for area in GAP_AREAS
            },
            "gap_area_score_contributions": {
                area: gap_maps[area]["score_contribution"] for area in GAP_AREAS
            },
            "any_gap_area_pass": any(gap_maps[area]["status"] == "PASS" for area in GAP_AREAS),
            "data_integrity_ready": gap_maps["data_integrity"]["status"] == "PASS",
            "statistical_validity_ready": False,
            "operational_resilience_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_status_error,
        },
        "source_evidence": source_evidence,
        "gap_maps": gap_maps,
        "non_approval": dict(NON_APPROVAL),
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "failures": failures,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Gap Remediation Evidence Map",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Data integrity: `{summary['gap_area_statuses']['data_integrity']}`",
        f"- Statistical validity: `{summary['gap_area_statuses']['statistical_validity']}`",
        f"- Operational resilience: `{summary['gap_area_statuses']['operational_resilience']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        f"- Paper/live ready: `{summary['paper_live_ready']}`",
        "",
        "## Gap Checks",
        "",
    ]
    for area, gap_map in report["gap_maps"].items():
        lines.extend([f"### `{area}`", ""])
        for check in gap_map["checks"]:
            lines.append(
                "- `{check_id}`: `{status}` - {reason}".format(
                    check_id=check["check_id"],
                    status=check["status"],
                    reason=check["review_rationale"],
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Non-Execution Statement",
            "",
            "- This evidence map did not run phase audits, data/model commands, WFA/modeling, prediction generation or materialization, Phase 8 refresh, provider/network calls, promotion, artifact freeze, final holdout, paper/live, production checks, cleanup, staging, commit, or push.",
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
        f"gap_statuses={report['summary']['gap_area_statuses']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
