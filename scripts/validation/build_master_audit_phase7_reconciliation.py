#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 7 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not read the
prediction parquet, run Phase 7 audits, rebuild data, run WFA/modeling, generate
predictions, refresh Phase 8, call providers/network, promote, freeze, touch
holdout, paper/live, clean up files, stage, commit, or push.
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
STAGE = "master_audit_phase7_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY"

RUN_ID = "tier1_core_phase6_full_predictions_20260706"
EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_PREDICTION_YEARS = (2024,)
EXPECTED_FOLD_COUNT = 48

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase7_reconciliation_20260709")
REPORT_JSON = "master_audit_phase7_reconciliation.json"
REPORT_MD = "master_audit_phase7_reconciliation.md"

PREDICTION_AUDIT = Path(
    f"reports/prediction_audit/{RUN_ID}/prediction_audit_summary.json"
)
PREDICTIONS_MANIFEST = Path(
    f"reports/wfa/{RUN_ID}/{RUN_ID}_predictions_manifest.json"
)
WFA_REPORT = Path(f"reports/wfa/{RUN_ID}/{RUN_ID}_wfa_report.json")
PREDICTION_DIAGNOSTICS = Path(
    f"reports/prediction_diagnostics/{RUN_ID}/prediction_diagnostics_summary.json"
)
FAILURE_ANALYSIS = Path(f"reports/failure_analysis/{RUN_ID}/failure_analysis_summary.json")
STATISTICAL_VALIDITY = Path(
    f"reports/statistical_validity/{RUN_ID}/statistical_validity_summary.json"
)
PHASE8_DECISION = Path(f"reports/phase8/{RUN_ID}/alpha_promotion_decision.json")

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "prediction_audit": PREDICTION_AUDIT,
    "predictions_manifest": PREDICTIONS_MANIFEST,
    "wfa_report": WFA_REPORT,
    "prediction_diagnostics": PREDICTION_DIAGNOSTICS,
    "failure_analysis": FAILURE_ANALYSIS,
    "statistical_validity": STATISTICAL_VALIDITY,
    "phase8_decision": PHASE8_DECISION,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
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
    "prediction_parquet_read_executed": False,
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


def as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def list_as_set(value: Any) -> set[Any]:
    if isinstance(value, list):
        return set(value)
    if isinstance(value, tuple):
        return set(value)
    return set()


def numeric_equal(left: Any, right: Any) -> bool:
    left_int = as_int(left)
    right_int = as_int(right)
    return left_int is not None and right_int is not None and left_int == right_int


def check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    failure: str,
    evidence: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
    fail_report: bool = True,
) -> None:
    status = "PASS" if passed else ("WARN" if not fail_report else "FAIL")
    checks.append(
        {
            "name": name,
            "status": status,
            "failure": None if passed else failure,
            "evidence": list(evidence),
            "details": dict(details or {}),
            "fail_report": fail_report,
        }
    )
    if not passed and fail_report:
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
            "phase7_run_status": "run_status_table",
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
            "failure_count": "summary.failure_count",
        },
        "overview": {
            "status": "status",
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
            "failure_count": "summary.failure_count",
        },
        "prediction_audit": {
            "status": "status",
            "run": "run",
            "phase7_prediction_audit_ready": "phase7_prediction_audit_ready",
            "prediction_count": "prediction_count",
            "target_count": "target_count",
            "failure_count": "failure_count",
            "prediction_path": "prediction_path",
            "predictions_manifest_path": "predictions_manifest_path",
        },
        "predictions_manifest": {
            "run": "run",
            "prediction_count": "prediction_count",
            "duplicate_prediction_count": "duplicate_prediction_count",
            "prediction_path": "prediction_path",
            "prediction_artifact_written": "prediction_artifact_written",
            "prediction_writes_enabled": "prediction_writes_enabled",
            "artifact_evidence_ready": "artifact_evidence_ready",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "wfa_report": {
            "run": "run",
            "fold_count": "fold_count",
            "prediction_count": "prediction_count",
            "duplicate_prediction_count": "duplicate_prediction_count",
            "prediction_artifact_written": "prediction_artifact_written",
            "prediction_writes_enabled": "prediction_writes_enabled",
            "artifact_evidence_ready": "artifact_evidence_ready",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "prediction_diagnostics": {
            "status": "status",
            "run": "run",
            "prediction_count": "prediction_count",
            "target_count": "target_count",
            "failure_count": "failure_count",
            "failure_labels": "failure_labels",
        },
        "failure_analysis": {
            "status": "status",
            "run": "run",
            "prediction_count": "prediction_count",
            "policy_row_count": "policy_row_count",
            "failure_count": "failure_count",
            "model_promotion_allowed": "model_promotion_allowed",
        },
        "statistical_validity": {
            "status": "status",
            "run": "run",
            "prediction_count": "prediction_count",
            "policy_trade_count": "policy_trade_count",
            "failure_count": "failure_count",
            "model_promotion_allowed": "model_promotion_allowed",
        },
        "phase8_decision": {
            "run": "run",
            "promoted": "promoted",
            "research_alpha_ready": "research_alpha_ready",
            "model_promotion_allowed": "model_promotion_allowed",
            "final_holdout_touched": "final_holdout_touched",
            "used_final_holdout_for_tuning": "used_final_holdout_for_tuning",
            "promotion_metric_gate_status": "promotion_metric_gate.status",
            "statistical_validity_gate_status": "statistical_validity_gate.status",
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


def phase7_row(run_status: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    rows = dotted_get(run_status, "run_status_table")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("audit_area") == "Phase 7":
            return row
    return None


def source_hash_reconciliation(
    *,
    repo_root: Path,
    prediction_audit: Mapping[str, Any],
    predictions_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    audit_hashes = prediction_audit.get("input_file_hashes")
    manifest_output_hashes = predictions_manifest.get("output_file_hashes")
    audit_hashes = audit_hashes if isinstance(audit_hashes, Mapping) else {}
    manifest_output_hashes = (
        manifest_output_hashes if isinstance(manifest_output_hashes, Mapping) else {}
    )
    prediction_path = as_str(prediction_audit.get("prediction_path")) or as_str(
        predictions_manifest.get("prediction_path")
    )
    manifest_path = as_str(prediction_audit.get("predictions_manifest_path")) or PREDICTIONS_MANIFEST.as_posix()
    manifest_sha256 = inventory.sha256_file(resolve_path(repo_root, manifest_path))
    audit_manifest_sha256 = audit_hashes.get(manifest_path)
    if audit_manifest_sha256 is None:
        audit_manifest_sha256 = audit_hashes.get(manifest_path.replace("\\", "/"))
    audit_prediction_sha256 = audit_hashes.get(prediction_path) if prediction_path else None
    manifest_prediction_sha256 = (
        manifest_output_hashes.get(prediction_path) if prediction_path else None
    )
    return {
        "prediction_path": prediction_path,
        "predictions_manifest_path": manifest_path,
        "manifest_file_sha256": manifest_sha256,
        "audit_recorded_manifest_sha256": audit_manifest_sha256,
        "audit_recorded_prediction_sha256": audit_prediction_sha256,
        "manifest_recorded_prediction_sha256": manifest_prediction_sha256,
        "manifest_hash_matches_prediction_audit": (
            manifest_sha256 is not None
            and audit_manifest_sha256 is not None
            and manifest_sha256 == audit_manifest_sha256
        ),
        "prediction_hash_matches_manifest": (
            audit_prediction_sha256 is not None
            and manifest_prediction_sha256 is not None
            and audit_prediction_sha256 == manifest_prediction_sha256
        ),
    }


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    prediction_audit = payloads.get("prediction_audit", {})
    diagnostics = payloads.get("prediction_diagnostics", {})
    failure_analysis = payloads.get("failure_analysis", {})
    statistical_validity = payloads.get("statistical_validity", {})
    phase8 = payloads.get("phase8_decision", {})
    failure_classifications = failure_analysis.get("failure_classifications")
    if not isinstance(failure_classifications, list):
        failure_classifications = []
    return [
        {
            "finding_id": "phase7-001-public-artifact-audit-reconciled",
            "severity": "Info",
            "finding": "Existing public Phase 7 prediction artifact audit is accepted for limited report-only evidence.",
            "verified_facts": [
                f"prediction_audit.status={prediction_audit.get('status')}",
                f"phase7_prediction_audit_ready={prediction_audit.get('phase7_prediction_audit_ready')}",
                f"prediction_count={prediction_audit.get('prediction_count')}",
                f"target_count={prediction_audit.get('target_count')}",
                f"failure_count={prediction_audit.get('failure_count')}",
            ],
            "inference": (
                "The Master Audit Phase 7 row can be reconciled from NOT_RUN to "
                "RUN_LIMITED_SCOPE_PREDICTION_ARTIFACT_RECONCILIATION for this run."
            ),
            "limitation": "This does not rerun Phase 7, reread prediction parquet, or prove economic alpha.",
            "evidence_paths": [PREDICTION_AUDIT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        },
        {
            "finding_id": "phase7-002-weak-signal-diagnostic",
            "severity": "High",
            "finding": "Prediction diagnostics preserve a weak-signal label.",
            "verified_facts": [
                f"prediction_diagnostics.status={diagnostics.get('status')}",
                f"failure_labels={diagnostics.get('failure_labels')}",
            ],
            "inference": "Structural artifact integrity is not the same as model-trust or alpha readiness.",
            "limitation": "Weak-signal classification is diagnostic evidence, not a Phase 7 report-generation failure.",
            "evidence_paths": [PREDICTION_DIAGNOSTICS.as_posix()],
        },
        {
            "finding_id": "phase7-003-economic-and-statistical-blockers-remain",
            "severity": "Critical",
            "finding": "Downstream economic and statistical evidence remains blocking.",
            "verified_facts": [
                f"failure_analysis.status={failure_analysis.get('status')}",
                f"failure_classifications={failure_classifications}",
                f"statistical_validity.status={statistical_validity.get('status')}",
                f"statistical_validity.failure_count={statistical_validity.get('failure_count')}",
            ],
            "inference": "The run remains unsuitable for model-trust, promotion, holdout, paper, or live claims.",
            "limitation": "This reconciliation only reports the existing blockers; it does not refresh Phase 8 or diagnostics.",
            "evidence_paths": [FAILURE_ANALYSIS.as_posix(), STATISTICAL_VALIDITY.as_posix()],
        },
        {
            "finding_id": "phase7-004-promotion-still-blocked",
            "severity": "Critical",
            "finding": "Phase 8 promotion and model-trust remain explicitly blocked.",
            "verified_facts": [
                f"promoted={phase8.get('promoted')}",
                f"research_alpha_ready={phase8.get('research_alpha_ready')}",
                f"model_promotion_allowed={phase8.get('model_promotion_allowed')}",
                f"final_holdout_touched={phase8.get('final_holdout_touched')}",
                f"used_final_holdout_for_tuning={phase8.get('used_final_holdout_for_tuning')}",
            ],
            "inference": "Accepting Phase 7 as limited evidence must not advance Phase 8, freeze, holdout, paper, or live work.",
            "limitation": "Any future promotion claim requires a separate approved evidence path.",
            "evidence_paths": [PHASE8_DECISION.as_posix()],
        },
    ]


def build_checks(
    *,
    repo_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    output_rel: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    evidence_by_path = {item.get("path"): item for item in evidence}
    required_paths = {path.as_posix() for path in REQUIRED_INPUTS.values()}
    present_paths = {str(item.get("path")) for item in evidence if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required Phase 7 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 7 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    phase7 = phase7_row(run_status)
    check(
        checks,
        failures,
        name="run_status_and_overview_are_passed_inputs",
        passed=run_status is not None
        and overview is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY",
        failure="run-status or overview input is not a passed report-only input",
        evidence=[DEFAULT_RUN_STATUS.as_posix(), DEFAULT_OVERVIEW.as_posix()],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "pre_existing_phase7_row": dict(phase7 or {}),
        },
    )
    check(
        checks,
        failures,
        name="phase7_previously_not_run_only_due_missing_master_audit_artifact",
        passed=phase7 is not None
        and phase7.get("run_status") == "NOT_RUN"
        and phase7.get("detail_status") == "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
        failure="run-status Phase 7 row does not match the expected pre-reconciliation NOT_RUN state",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"pre_existing_phase7_row": dict(phase7 or {})},
    )

    prediction_audit = payloads.get("prediction_audit", {})
    manifest = payloads.get("predictions_manifest", {})
    wfa_report = payloads.get("wfa_report", {})
    diagnostics = payloads.get("prediction_diagnostics", {})
    failure_analysis = payloads.get("failure_analysis", {})
    statistical_validity = payloads.get("statistical_validity", {})
    phase8 = payloads.get("phase8_decision", {})

    prediction_count = prediction_audit.get("prediction_count")
    target_count = prediction_audit.get("target_count")
    prediction_path = as_str(prediction_audit.get("prediction_path")) or as_str(
        manifest.get("prediction_path")
    )
    manifest_path = as_str(prediction_audit.get("predictions_manifest_path")) or PREDICTIONS_MANIFEST.as_posix()

    check(
        checks,
        failures,
        name="public_phase7_prediction_audit_passed",
        passed=prediction_audit.get("status") == "PASS"
        and as_bool(prediction_audit.get("phase7_prediction_audit_ready")) is True
        and prediction_audit.get("run") == RUN_ID
        and as_int(prediction_count) is not None
        and as_int(prediction_count) > 0
        and as_int(target_count) is not None
        and as_int(target_count) > 0
        and prediction_audit.get("failure_count") == 0,
        failure="public Phase 7 prediction audit is not passed and ready",
        evidence=[PREDICTION_AUDIT.as_posix()],
        details={
            "status": prediction_audit.get("status"),
            "phase7_prediction_audit_ready": prediction_audit.get("phase7_prediction_audit_ready"),
            "run": prediction_audit.get("run"),
            "prediction_count": prediction_count,
            "target_count": target_count,
            "failure_count": prediction_audit.get("failure_count"),
        },
    )

    scope = prediction_audit.get("scope")
    scope = scope if isinstance(scope, Mapping) else {}
    check(
        checks,
        failures,
        name="phase7_scope_matches_tier1_core_run",
        passed=list_as_set(scope.get("markets")) == set(EXPECTED_MARKETS)
        and list_as_set(scope.get("prediction_markets")) == set(EXPECTED_MARKETS)
        and list_as_set(scope.get("years")) == set(EXPECTED_YEARS)
        and list_as_set(scope.get("prediction_years")) == set(EXPECTED_PREDICTION_YEARS)
        and scope.get("fold_count") == EXPECTED_FOLD_COUNT,
        failure="Phase 7 prediction audit scope does not match expected Tier 1 core run",
        evidence=[PREDICTION_AUDIT.as_posix()],
        details={
            "markets": scope.get("markets"),
            "years": scope.get("years"),
            "prediction_markets": scope.get("prediction_markets"),
            "prediction_years": scope.get("prediction_years"),
            "fold_count": scope.get("fold_count"),
        },
    )

    check(
        checks,
        failures,
        name="manifest_and_wfa_artifact_evidence_match_phase7_counts",
        passed=manifest.get("run") == RUN_ID
        and wfa_report.get("run") == RUN_ID
        and numeric_equal(manifest.get("prediction_count"), prediction_count)
        and numeric_equal(wfa_report.get("prediction_count"), prediction_count)
        and manifest.get("duplicate_prediction_count") == 0
        and wfa_report.get("duplicate_prediction_count") == 0
        and wfa_report.get("fold_count") == EXPECTED_FOLD_COUNT
        and manifest.get("failure_count") == 0
        and wfa_report.get("failure_count") == 0,
        failure="Phase 6 manifest/WFA report do not reconcile with Phase 7 prediction audit counts",
        evidence=[PREDICTIONS_MANIFEST.as_posix(), WFA_REPORT.as_posix()],
        details={
            "manifest_prediction_count": manifest.get("prediction_count"),
            "wfa_prediction_count": wfa_report.get("prediction_count"),
            "manifest_duplicate_prediction_count": manifest.get("duplicate_prediction_count"),
            "wfa_duplicate_prediction_count": wfa_report.get("duplicate_prediction_count"),
            "wfa_fold_count": wfa_report.get("fold_count"),
            "manifest_failure_count": manifest.get("failure_count"),
            "wfa_failure_count": wfa_report.get("failure_count"),
        },
    )

    check(
        checks,
        failures,
        name="prediction_artifact_written_but_not_reread",
        passed=manifest.get("prediction_artifact_written") is True
        and manifest.get("prediction_writes_enabled") is True
        and manifest.get("artifact_evidence_ready") is True
        and wfa_report.get("prediction_artifact_written") is True
        and wfa_report.get("prediction_writes_enabled") is True
        and wfa_report.get("artifact_evidence_ready") is True
        and as_str(manifest.get("prediction_path")) == prediction_path
        and prediction_path is not None,
        failure="prediction artifact metadata is not ready or path-consistent",
        evidence=[PREDICTIONS_MANIFEST.as_posix(), WFA_REPORT.as_posix()],
        details={
            "prediction_path": prediction_path,
            "manifest_prediction_path": manifest.get("prediction_path"),
            "manifest_artifact_evidence_ready": manifest.get("artifact_evidence_ready"),
            "wfa_artifact_evidence_ready": wfa_report.get("artifact_evidence_ready"),
        },
    )

    hash_reconciliation = source_hash_reconciliation(
        repo_root=repo_root,
        prediction_audit=prediction_audit,
        predictions_manifest=manifest,
    )
    check(
        checks,
        failures,
        name="json_recorded_hashes_reconcile_without_parquet_read",
        passed=hash_reconciliation["manifest_hash_matches_prediction_audit"]
        and hash_reconciliation["prediction_hash_matches_manifest"],
        failure="Phase 7 JSON-recorded input/output hashes do not reconcile",
        evidence=[PREDICTION_AUDIT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        details=hash_reconciliation,
    )
    check(
        checks,
        failures,
        name="phase7_uses_public_prediction_audit_not_internal_wfa_phase",
        passed=manifest_path == PREDICTIONS_MANIFEST.as_posix()
        and prediction_path == as_str(manifest.get("prediction_path")),
        failure="Phase 7 reconciliation is not anchored to the public prediction audit and manifest",
        evidence=[PREDICTION_AUDIT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        details={"prediction_path": prediction_path, "manifest_path": manifest_path},
    )

    check(
        checks,
        failures,
        name="supporting_prediction_diagnostics_preserved",
        passed=diagnostics.get("status") == "PREDICTION_DIAGNOSTICS_READY"
        and diagnostics.get("run") == RUN_ID
        and numeric_equal(diagnostics.get("prediction_count"), prediction_count),
        failure="prediction diagnostics are missing, wrong-run, or count-mismatched",
        evidence=[PREDICTION_DIAGNOSTICS.as_posix()],
        details={
            "status": diagnostics.get("status"),
            "failure_labels": diagnostics.get("failure_labels"),
            "prediction_count": diagnostics.get("prediction_count"),
        },
    )
    check(
        checks,
        failures,
        name="weak_signal_is_reported_not_promoted",
        passed="weak_signal" in (diagnostics.get("failure_labels") or []),
        failure="prediction diagnostics no longer preserve the expected weak_signal label",
        evidence=[PREDICTION_DIAGNOSTICS.as_posix()],
        details={"failure_labels": diagnostics.get("failure_labels")},
        fail_report=False,
    )

    check(
        checks,
        failures,
        name="downstream_diagnostics_preserve_blockers",
        passed=failure_analysis.get("status") == "PASS"
        and statistical_validity.get("status") == "FAIL"
        and as_int(statistical_validity.get("failure_count")) is not None
        and as_int(statistical_validity.get("failure_count")) > 0,
        failure="downstream diagnostic blocker evidence is missing or inconsistent",
        evidence=[FAILURE_ANALYSIS.as_posix(), STATISTICAL_VALIDITY.as_posix()],
        details={
            "failure_analysis_status": failure_analysis.get("status"),
            "statistical_validity_status": statistical_validity.get("status"),
            "statistical_validity_failure_count": statistical_validity.get("failure_count"),
        },
    )

    check(
        checks,
        failures,
        name="phase8_non_approval_preserved",
        passed=phase8.get("run") == RUN_ID
        and phase8.get("promoted") is False
        and phase8.get("research_alpha_ready") is False
        and phase8.get("model_promotion_allowed") is False
        and phase8.get("final_holdout_touched") is False
        and phase8.get("used_final_holdout_for_tuning") is False,
        failure="Phase 8 non-approval flags are not preserved",
        evidence=[PHASE8_DECISION.as_posix()],
        details={
            "promoted": phase8.get("promoted"),
            "research_alpha_ready": phase8.get("research_alpha_ready"),
            "model_promotion_allowed": phase8.get("model_promotion_allowed"),
            "final_holdout_touched": phase8.get("final_holdout_touched"),
            "used_final_holdout_for_tuning": phase8.get("used_final_holdout_for_tuning"),
        },
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))
        if item.get("path") in required_paths:
            evidence_by_path[str(item.get("path"))] = item

    return checks, failures, {
        "prediction_count": prediction_count,
        "target_count": target_count,
        "prediction_path": prediction_path,
        "predictions_manifest_path": manifest_path,
        "json_hash_reconciliation": hash_reconciliation,
    }


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    run_status_path: Path = DEFAULT_RUN_STATUS,
    overview_path: Path = DEFAULT_OVERVIEW,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_inputs: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = resolve_path(repo_root, reports_root).resolve()
    paths = dict(REQUIRED_INPUTS)
    paths["run_status"] = run_status_path
    paths["overview"] = overview_path
    if required_inputs:
        paths.update(required_inputs)

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
    )
    failures = input_failures + check_failures
    findings = build_findings(payloads)
    status = PASS_STATUS if not failures else FAIL_STATUS
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    warn_checks = sum(1 for item in checks if item["status"] == "WARN")
    phase7_classification = (
        "RUN_LIMITED_SCOPE_PREDICTION_ARTIFACT_RECONCILIATION"
        if status == PASS_STATUS
        else "FAILED_PHASE7_RECONCILIATION"
    )

    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase7_reconciliation_report_only",
            "phase": "Phase 7",
            "phase_name": "Public prediction artifact audit",
            "run": RUN_ID,
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "prediction_parquet_read_scope": "none",
            "phase_command_scope": "none",
            "data_model_command_scope": "none",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "fold_count": EXPECTED_FOLD_COUNT,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "warn_check_count": warn_checks,
            "phase7_master_audit_status": phase7_classification,
            "phase7_artifact_integrity_ready": status == PASS_STATUS,
            "prediction_count": derived.get("prediction_count"),
            "target_count": derived.get("target_count"),
            "prediction_path": derived.get("prediction_path"),
            "predictions_manifest_path": derived.get("predictions_manifest_path"),
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
            "phase_audits_executed": False,
            "data_model_commands_executed": False,
            "wfa_modeling_executed": False,
            "predictions_executed": False,
            "phase8_refresh_executed": False,
            "provider_network_calls_executed": False,
            "prediction_parquet_read_executed": False,
            "finding_counts_by_severity": finding_counts(findings),
        },
        "input_evidence": evidence,
        "checks": checks,
        "findings": findings,
        "json_hash_reconciliation": derived.get("json_hash_reconciliation", {}),
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required coordination and report JSON inputs are readable",
                "run-status and overview inputs are passed report-only evidence",
                "pre-existing Phase 7 ledger row is NOT_RUN only because no Master Audit reconciliation artifact existed",
                "public Phase 7 prediction audit status is PASS, ready=true, failure_count=0, and run/scope/counts match",
                "Phase 6 prediction manifest and WFA report reconcile run id, counts, duplicate count, artifact flags, and 48 folds",
                "JSON-recorded manifest/prediction hashes reconcile without reading prediction parquet",
                "supporting diagnostics and Phase 8 non-approval blockers are preserved",
                "all forbidden action flags remain false",
            ],
            "fail": [
                "missing or unreadable required input",
                "output root points at protected data/config/script/model/prediction locations",
                "Phase 7 prediction audit is missing, not PASS, not ready, wrong-run, or has failures",
                "manifest/WFA counts, duplicate counts, artifact flags, or fold count mismatch",
                "JSON-recorded hashes are stale or inconsistent",
                "Phase 8 promotion, model-trust, final-holdout, paper/live, or tuning flags are not blocked",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan exactly one next Master Audit area from the updated evidence state, "
            "preferably Phase 6 report-only reconciliation or an upstream Phase 1B/2 report-only reconciliation; "
            "do not run data/model/WFA/prediction/Phase 8 commands without a separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 7 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 7 status: `{summary.get('phase7_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed, `{summary.get('warn_check_count')}` warn",
        f"- Prediction count: `{summary.get('prediction_count')}`",
        f"- Target count: `{summary.get('target_count')}`",
        f"- Model-trust ready: `{summary.get('model_trust_ready')}`",
        f"- Promotion allowed: `{summary.get('promotion_allowed')}`",
        f"- Prediction parquet read: `{summary.get('prediction_parquet_read_executed')}`",
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
            "- This reconciliation did not run phase audits, rebuild data, rebuild labels/features, run WFA/modeling, generate predictions, read prediction parquet, refresh Phase 8, call providers/network, approve promotion, freeze artifacts, touch holdout, paper trade, live trade, clean up files, stage, commit, or push.",
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
    parser.add_argument("--run-status", default=DEFAULT_RUN_STATUS.as_posix())
    parser.add_argument("--overview", default=DEFAULT_OVERVIEW.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(
        repo_root=repo_root,
        reports_root=reports_root,
        run_status_path=Path(args.run_status),
        overview_path=Path(args.overview),
    )
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"phase7_status={report['summary']['phase7_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
