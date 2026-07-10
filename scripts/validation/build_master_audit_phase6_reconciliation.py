#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 6 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run WFA,
combine predictions, generate predictions, read parquet, refresh Phase 8, call
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
STAGE = "master_audit_phase6_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY"

RUN_ID = "phase6_v2_apex_30m60m_20260709_tier1_core_report_only"
EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_PREDICTION_YEARS = (2024,)
EXPECTED_FOLD_COUNT = 48
EXPECTED_FEATURE_COUNT = 114
EXPECTED_MODEL_COUNT = 8

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_PHASE7 = Path(
    "reports/master_audit/master_audit_phase7_reconciliation_20260709/"
    "master_audit_phase7_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase6_reconciliation_20260709")
REPORT_JSON = "master_audit_phase6_reconciliation.json"
REPORT_MD = "master_audit_phase6_reconciliation.md"

PREFLIGHT_REPORT = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_runner_preflight/"
    "wfa_runner_preflight_report.json"
)
FEATURE_SET = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_runner_preflight/"
    "tier1_core_active_feature_set.json"
)
WFA_REPORT = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_report_only/"
    f"{RUN_ID}_wfa_report.json"
)
PREDICTIONS_MANIFEST = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_report_only/"
    f"{RUN_ID}_predictions_manifest.json"
)

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "phase7_reconciliation": DEFAULT_PHASE7,
    "preflight_report": PREFLIGHT_REPORT,
    "feature_set": FEATURE_SET,
    "wfa_report": WFA_REPORT,
    "predictions_manifest": PREDICTIONS_MANIFEST,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "data_model_commands_executed": False,
    "wfa_modeling_executed": False,
    "phase6_runner_executed": False,
    "combine_predictions_executed": False,
    "predictions_executed": False,
    "prediction_parquet_read_executed": False,
    "feature_parquet_read_executed": False,
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


def list_as_set(value: Any) -> set[Any]:
    return set(as_list(value))


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
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
            "failure_count": "summary.failure_count",
        },
        "overview": {
            "status": "status",
            "failure_count": "summary.failure_count",
        },
        "phase7_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase7_master_audit_status": "summary.phase7_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "preflight_report": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "warning_count": "summary.warning_count",
            "fold_count": "summary.fold_count",
            "feature_count": "summary.feature_count",
            "model_count": "summary.model_count",
            "commands_executed": "summary.commands_executed",
        },
        "wfa_report": {
            "run": "run",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "fold_count": "fold_count",
            "prediction_count": "prediction_count",
            "duplicate_prediction_count": "duplicate_prediction_count",
            "prediction_writes_enabled": "prediction_writes_enabled",
            "prediction_artifact_written": "prediction_artifact_written",
            "artifact_evidence_ready": "artifact_evidence_ready",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "predictions_manifest": {
            "run": "run",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
            "fold_count": "fold_count",
            "prediction_count": "prediction_count",
            "duplicate_prediction_count": "duplicate_prediction_count",
            "prediction_writes_enabled": "prediction_writes_enabled",
            "prediction_artifact_written": "prediction_artifact_written",
            "artifact_evidence_ready": "artifact_evidence_ready",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
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


def row_by_area(run_status: Mapping[str, Any] | None, area: str) -> Mapping[str, Any] | None:
    rows = dotted_get(run_status, "run_status_table")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("audit_area") == area:
            return row
    return None


def empty_sequence(value: Any) -> bool:
    return value in (None, False) or value == [] or value == {}


def model_risk_gate_ready_but_not_trust(gate: Mapping[str, Any] | None) -> bool:
    if not isinstance(gate, Mapping):
        return False
    calibration = gate.get("calibration")
    calibration = calibration if isinstance(calibration, Mapping) else {}
    hyperparameter_budget = gate.get("hyperparameter_budget")
    hyperparameter_budget = (
        hyperparameter_budget if isinstance(hyperparameter_budget, Mapping) else {}
    )
    seed_policy = gate.get("seed_policy")
    seed_policy = seed_policy if isinstance(seed_policy, Mapping) else {}
    return (
        gate.get("status") == "PASS_METADATA_READY"
        and gate.get("model_risk_metadata_ready") is True
        and gate.get("model_trust_ready") is False
        and gate.get("failure_count") == 0
        and calibration.get("calibration_id") == "no_calibration"
        and calibration.get("test_fold_fit_allowed") is False
        and calibration.get("final_holdout_fit_allowed") is False
        and hyperparameter_budget.get("hyperparameter_tuning_allowed_initially") is False
        and seed_policy.get("random_splits_allowed") is False
    )


def input_hash_key_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:
    hashes = manifest.get("input_file_hashes")
    hashes = hashes if isinstance(hashes, Mapping) else {}
    feature_paths = [
        key for key in hashes if str(key).startswith("data/feature_matrices/") and str(key).endswith(".parquet")
    ]
    return {
        "input_hash_key_count": len(hashes),
        "feature_matrix_hash_key_count": len(feature_paths),
        "has_split_plan_hash": "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.json"
        in hashes,
        "has_feature_set_hash": FEATURE_SET.as_posix() in hashes,
        "has_models_config_hash": "configs/models.yaml" in hashes,
    }


def build_checks(
    *,
    payloads: Mapping[str, Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    output_rel: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in REQUIRED_INPUTS.values()}
    present_paths = {str(item.get("path")) for item in evidence if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required Phase 6 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 6 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    phase7 = payloads.get("phase7_reconciliation")
    phase6_row = row_by_area(run_status, "Phase 6")
    check(
        checks,
        failures,
        name="master_audit_inputs_are_passed_report_only_evidence",
        passed=run_status is not None
        and overview is not None
        and phase7 is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and phase7.get("status") == "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        failure="run-status, overview, or Phase 7 reconciliation input is not passed report-only evidence",
        evidence=[DEFAULT_RUN_STATUS.as_posix(), DEFAULT_OVERVIEW.as_posix(), DEFAULT_PHASE7.as_posix()],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "phase7": None if phase7 is None else phase7.get("status"),
        },
    )
    check(
        checks,
        failures,
        name="phase6_previously_not_accepted_in_master_audit_ledger",
        passed=phase6_row is not None
        and phase6_row.get("run_status") == "NOT_RUN"
        and phase6_row.get("detail_status") == "NOT_RUN_PHASE6_MASTER_AUDIT_NOT_ACCEPTED",
        failure="run-status Phase 6 row does not match expected pre-reconciliation NOT_RUN state",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"pre_existing_phase6_row": dict(phase6_row or {})},
    )

    preflight = payloads.get("preflight_report", {})
    preflight_summary = preflight.get("summary")
    preflight_summary = preflight_summary if isinstance(preflight_summary, Mapping) else {}
    preflight_scope = preflight.get("scope")
    preflight_scope = preflight_scope if isinstance(preflight_scope, Mapping) else {}
    check(
        checks,
        failures,
        name="phase6_runner_preflight_passed_report_only",
        passed=preflight.get("status") == "PASS_PHASE6_WFA_RUNNER_PREFLIGHT_READY_REPORT_ONLY"
        and preflight_summary.get("commands_executed") == 0
        and preflight_summary.get("model_training_performed") is False
        and preflight_summary.get("prediction_generation_performed") is False
        and preflight_summary.get("fold_count") == EXPECTED_FOLD_COUNT
        and preflight_summary.get("feature_count") == EXPECTED_FEATURE_COUNT
        and preflight_summary.get("model_count") == EXPECTED_MODEL_COUNT
        and preflight_summary.get("prediction_file_count") == 0
        and preflight_summary.get("failure_count") == 0
        and preflight_summary.get("warning_count") == 0,
        failure="Phase 6 runner preflight is missing, failing, or not report-only",
        evidence=[PREFLIGHT_REPORT.as_posix()],
        details={"status": preflight.get("status"), "summary": dict(preflight_summary)},
    )
    check(
        checks,
        failures,
        name="phase6_preflight_scope_matches_active_v2_core",
        passed=preflight_scope.get("profile") == "tier_1"
        and preflight_scope.get("resolved_profile") == "tier_1_research"
        and list_as_set(preflight_scope.get("markets")) == set(EXPECTED_MARKETS)
        and list_as_set(preflight_scope.get("years")) == set(EXPECTED_YEARS)
        and preflight_scope.get("split_plan") == "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.json",
        failure="Phase 6 preflight scope does not match active v2 Tier 1 core",
        evidence=[PREFLIGHT_REPORT.as_posix()],
        details={"scope": dict(preflight_scope)},
    )

    wfa_report = payloads.get("wfa_report", {})
    manifest = payloads.get("predictions_manifest", {})
    prediction_count = manifest.get("prediction_count")
    check(
        checks,
        failures,
        name="wfa_report_and_manifest_scope_match",
        passed=wfa_report.get("run") == RUN_ID
        and manifest.get("run") == RUN_ID
        and wfa_report.get("profile") == "tier_1"
        and manifest.get("profile") == "tier_1"
        and wfa_report.get("resolved_profile") == "tier_1_research"
        and manifest.get("resolved_profile") == "tier_1_research"
        and list_as_set(manifest.get("markets")) == set(EXPECTED_MARKETS)
        and list_as_set(manifest.get("years")) == set(EXPECTED_YEARS)
        and list_as_set(manifest.get("prediction_markets")) == set(EXPECTED_MARKETS)
        and list_as_set(manifest.get("prediction_years")) == set(EXPECTED_PREDICTION_YEARS),
        failure="Phase 6 WFA report/manifest scope does not match active v2 Tier 1 core",
        evidence=[WFA_REPORT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        details={
            "wfa_run": wfa_report.get("run"),
            "manifest_run": manifest.get("run"),
            "markets": manifest.get("markets"),
            "years": manifest.get("years"),
            "prediction_markets": manifest.get("prediction_markets"),
            "prediction_years": manifest.get("prediction_years"),
        },
    )
    check(
        checks,
        failures,
        name="wfa_report_and_manifest_counts_match",
        passed=wfa_report.get("fold_count") == EXPECTED_FOLD_COUNT
        and manifest.get("fold_count") == EXPECTED_FOLD_COUNT
        and wfa_report.get("unfiltered_selectable_fold_count") == EXPECTED_FOLD_COUNT
        and manifest.get("unfiltered_selectable_fold_count") == EXPECTED_FOLD_COUNT
        and numeric_equal(wfa_report.get("prediction_count"), prediction_count)
        and as_int(prediction_count) is not None
        and as_int(prediction_count) > 0
        and wfa_report.get("duplicate_prediction_count") == 0
        and manifest.get("duplicate_prediction_count") == 0
        and wfa_report.get("failure_count") == 0
        and manifest.get("failure_count") == 0
        and wfa_report.get("warning_count") == 0
        and manifest.get("warning_count") == 0,
        failure="Phase 6 WFA report/manifest counts, warnings, failures, or duplicate counts mismatch",
        evidence=[WFA_REPORT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        details={
            "wfa_prediction_count": wfa_report.get("prediction_count"),
            "manifest_prediction_count": manifest.get("prediction_count"),
            "wfa_fold_count": wfa_report.get("fold_count"),
            "manifest_fold_count": manifest.get("fold_count"),
            "wfa_failure_count": wfa_report.get("failure_count"),
            "manifest_failure_count": manifest.get("failure_count"),
        },
    )
    check(
        checks,
        failures,
        name="prediction_writes_disabled_and_no_artifact_paths",
        passed=wfa_report.get("prediction_writes_enabled") is False
        and manifest.get("prediction_writes_enabled") is False
        and wfa_report.get("prediction_artifact_written") is False
        and manifest.get("prediction_artifact_written") is False
        and wfa_report.get("prediction_artifact_write_skipped") is True
        and manifest.get("prediction_artifact_write_skipped") is True
        and wfa_report.get("prediction_path") is None
        and manifest.get("prediction_path") is None
        and wfa_report.get("output_root") is None
        and manifest.get("output_root") is None
        and wfa_report.get("predictions_root") is None
        and manifest.get("predictions_root") is None
        and wfa_report.get("artifact_evidence_ready") is True
        and manifest.get("artifact_evidence_ready") is True
        and empty_sequence(wfa_report.get("artifact_evidence_failures"))
        and empty_sequence(manifest.get("artifact_evidence_failures"))
        and empty_sequence(manifest.get("output_file_hashes")),
        failure="Phase 6 report-only evidence contains prediction writes or artifact paths",
        evidence=[WFA_REPORT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        details={
            "wfa_prediction_path": wfa_report.get("prediction_path"),
            "manifest_prediction_path": manifest.get("prediction_path"),
            "wfa_prediction_artifact_written": wfa_report.get("prediction_artifact_written"),
            "manifest_prediction_artifact_written": manifest.get("prediction_artifact_written"),
            "manifest_output_file_hashes": manifest.get("output_file_hashes"),
        },
    )

    manifest_hash_summary = input_hash_key_summary(manifest)
    check(
        checks,
        failures,
        name="manifest_records_expected_input_hash_keys",
        passed=manifest_hash_summary["feature_matrix_hash_key_count"] == 8
        and manifest_hash_summary["has_split_plan_hash"]
        and manifest_hash_summary["has_feature_set_hash"]
        and manifest_hash_summary["has_models_config_hash"],
        failure="Phase 6 manifest is missing expected input-hash evidence keys",
        evidence=[PREDICTIONS_MANIFEST.as_posix()],
        details=manifest_hash_summary,
    )

    manifest_gate = manifest.get("model_risk_gate")
    manifest_gate = manifest_gate if isinstance(manifest_gate, Mapping) else {}
    wfa_gate = wfa_report.get("model_risk_gate")
    wfa_gate = wfa_gate if isinstance(wfa_gate, Mapping) else {}
    check(
        checks,
        failures,
        name="model_risk_metadata_ready_but_not_model_trust",
        passed=model_risk_gate_ready_but_not_trust(manifest_gate)
        and model_risk_gate_ready_but_not_trust(wfa_gate),
        failure="Phase 6 model-risk metadata is not ready or improperly upgraded to model trust",
        evidence=[WFA_REPORT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        details={
            "manifest_model_risk_gate": dict(manifest_gate),
            "wfa_model_risk_gate": dict(wfa_gate),
        },
    )
    check(
        checks,
        failures,
        name="model_and_target_sets_are_expected",
        passed=len(as_list(manifest.get("model_ids"))) == EXPECTED_MODEL_COUNT
        and len(as_list(manifest.get("target_names"))) == EXPECTED_MODEL_COUNT
        and len(as_list(wfa_report.get("models"))) == EXPECTED_MODEL_COUNT,
        failure="Phase 6 model/target set does not contain the expected eight baseline models",
        evidence=[WFA_REPORT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        details={
            "model_ids": manifest.get("model_ids"),
            "target_names": manifest.get("target_names"),
            "wfa_models_count": len(as_list(wfa_report.get("models"))),
        },
    )

    phase7 = payloads.get("phase7_reconciliation", {})
    check(
        checks,
        failures,
        name="downstream_phase7_reconciliation_preserves_non_approval",
        passed=phase7.get("status") == "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY"
        and dotted_get(phase7, "summary.model_trust_ready") is False
        and dotted_get(phase7, "summary.promotion_allowed") is False
        and dotted_get(phase7, "summary.prediction_parquet_read_executed") is False,
        failure="Phase 7 downstream reconciliation does not preserve non-approval flags",
        evidence=[DEFAULT_PHASE7.as_posix()],
        details={
            "phase7_status": phase7.get("status"),
            "model_trust_ready": dotted_get(phase7, "summary.model_trust_ready"),
            "promotion_allowed": dotted_get(phase7, "summary.promotion_allowed"),
        },
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    return checks, failures, {
        "prediction_count": prediction_count,
        "model_count": len(as_list(manifest.get("model_ids"))),
        "target_count": len(as_list(manifest.get("target_names"))),
        "manifest_input_hash_summary": manifest_hash_summary,
    }


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    manifest = payloads.get("predictions_manifest", {})
    wfa_report = payloads.get("wfa_report", {})
    model_gate = manifest.get("model_risk_gate")
    model_gate = model_gate if isinstance(model_gate, Mapping) else {}
    return [
        {
            "finding_id": "phase6-001-report-only-wfa-evidence-reconciled",
            "severity": "Info",
            "finding": "Existing active v2 Phase 6 report-only WFA evidence is accepted for limited Master Audit evidence.",
            "verified_facts": [
                f"run={manifest.get('run')}",
                f"fold_count={manifest.get('fold_count')}",
                f"prediction_count={manifest.get('prediction_count')}",
                f"failure_count={manifest.get('failure_count')}",
                f"warning_count={manifest.get('warning_count')}",
            ],
            "limitation": "This is in-memory report-only WFA evidence, not prediction materialization or model-trust evidence.",
            "evidence_paths": [WFA_REPORT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        },
        {
            "finding_id": "phase6-002-prediction-writes-disabled",
            "severity": "Info",
            "finding": "Prediction writes were disabled and no prediction artifact path/root is present.",
            "verified_facts": [
                f"prediction_writes_enabled={manifest.get('prediction_writes_enabled')}",
                f"prediction_artifact_written={manifest.get('prediction_artifact_written')}",
                f"prediction_path={manifest.get('prediction_path')}",
                f"output_root={manifest.get('output_root')}",
                f"predictions_root={manifest.get('predictions_root')}",
            ],
            "limitation": "Phase 7 prediction-artifact evidence belongs to a different historical run, not this report-only Phase 6 run.",
            "evidence_paths": [PREDICTIONS_MANIFEST.as_posix()],
        },
        {
            "finding_id": "phase6-003-model-risk-gate-not-trust",
            "severity": "Critical",
            "finding": "Model-risk metadata is ready, but model-trust remains explicitly false.",
            "verified_facts": [
                f"model_risk_gate.status={model_gate.get('status')}",
                f"model_trust_ready={model_gate.get('model_trust_ready')}",
                f"calibration={dotted_get(model_gate, 'calibration.calibration_id')}",
                f"hyperparameter_tuning_allowed_initially={dotted_get(model_gate, 'hyperparameter_budget.hyperparameter_tuning_allowed_initially')}",
            ],
            "limitation": "Feature-importance stability and downstream economics/statistics remain outside this Phase 6 reconciliation.",
            "evidence_paths": [WFA_REPORT.as_posix(), PREDICTIONS_MANIFEST.as_posix()],
        },
        {
            "finding_id": "phase6-004-source-hash-caveat",
            "severity": "Medium",
            "finding": "Dirty worktree/config caveats remain; this report accepts recorded evidence, not current runnable equivalence.",
            "verified_facts": [
                "The WFA manifest records input_file_hashes for feature matrices, split plan, feature set, and configs/models.yaml.",
                "The current worktree has dirty config/source files recorded by git status.",
            ],
            "limitation": "This command does not hash or read non-JSON/YAML/parquet inputs and does not upgrade the run to current runnable evidence.",
            "evidence_paths": [PREDICTIONS_MANIFEST.as_posix()],
        },
    ]


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    run_status_path: Path = DEFAULT_RUN_STATUS,
    overview_path: Path = DEFAULT_OVERVIEW,
    phase7_path: Path = DEFAULT_PHASE7,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_inputs: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = resolve_path(repo_root, reports_root).resolve()
    paths = dict(REQUIRED_INPUTS)
    paths["run_status"] = run_status_path
    paths["overview"] = overview_path
    paths["phase7_reconciliation"] = phase7_path
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
        payloads=payloads,
        evidence=evidence,
        output_rel=output_rel,
    )
    failures = input_failures + check_failures
    findings = build_findings(payloads)
    status = PASS_STATUS if not failures else FAIL_STATUS
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    phase6_classification = (
        "RUN_LIMITED_SCOPE_PHASE6_REPORT_ONLY_WFA_RECONCILIATION"
        if status == PASS_STATUS
        else "FAILED_PHASE6_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase6_reconciliation_report_only",
            "phase": "Phase 6",
            "phase_name": "WFA training and OOS prediction generation",
            "run": RUN_ID,
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "wfa_runner_scope": "none",
            "prediction_generation_scope": "none",
            "parquet_read_scope": "none",
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "fold_count": EXPECTED_FOLD_COUNT,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase6_master_audit_status": phase6_classification,
            "phase6_report_only_artifact_integrity_ready": status == PASS_STATUS,
            "prediction_count": derived.get("prediction_count"),
            "model_count": derived.get("model_count"),
            "target_count": derived.get("target_count"),
            "manifest_input_hash_summary": derived.get("manifest_input_hash_summary"),
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
            "phase6_runner_executed": False,
            "combine_predictions_executed": False,
            "predictions_executed": False,
            "prediction_parquet_read_executed": False,
            "feature_parquet_read_executed": False,
            "phase8_refresh_executed": False,
            "provider_network_calls_executed": False,
            "hardened_split_candidate_consumed": False,
            "finding_counts_by_severity": finding_counts(findings),
        },
        "input_evidence": evidence,
        "checks": checks,
        "findings": findings,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "pass_fail_criteria": {
            "pass": [
                "required JSON/MD evidence is readable",
                "run-status, overview, and Phase 7 reconciliation are passed report-only inputs",
                "pre-existing Phase 6 ledger row is NOT_RUN_PHASE6_MASTER_AUDIT_NOT_ACCEPTED",
                "runner preflight is PASS and records no commands/modeling/prediction generation",
                "WFA report and manifest match run, scope, counts, duplicate count, warning count, and failure count",
                "prediction writes are disabled and no prediction path/root/output hashes exist",
                "model-risk metadata is ready but model_trust_ready remains false",
                "all forbidden action flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "wrong run/scope/fold count",
                "WFA report/manifest mismatch",
                "any Phase 6 failure or warning",
                "prediction artifact written or prediction output path/root present",
                "model-risk metadata missing or improperly upgraded to trust evidence",
                "any WFA/modeling/prediction/parquet/Phase 8/promotion/holdout/paper/live flag true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan exactly one next Master Audit area, preferably upstream Phase 1B or Phase 2 "
            "report-only reconciliation; do not run data/model/WFA/prediction/Phase 8 commands "
            "without a separate bounded approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 6 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 6 status: `{summary.get('phase6_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Prediction count: `{summary.get('prediction_count')}`",
        f"- Model count: `{summary.get('model_count')}`",
        f"- Target count: `{summary.get('target_count')}`",
        f"- Model-trust ready: `{summary.get('model_trust_ready')}`",
        f"- Promotion allowed: `{summary.get('promotion_allowed')}`",
        f"- WFA/modeling executed: `{summary.get('wfa_modeling_executed')}`",
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
            "- This reconciliation did not run phase audits, Phase 6 runner commands, combine predictions, rebuild data, rebuild labels/features, run WFA/modeling, generate predictions, read parquet, refresh Phase 8, call providers/network, approve promotion, freeze artifacts, touch holdout, paper trade, live trade, clean up files, stage, commit, or push.",
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
    parser.add_argument("--phase7-reconciliation", default=DEFAULT_PHASE7.as_posix())
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
        phase7_path=Path(args.phase7_reconciliation),
    )
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"phase6_status={report['summary']['phase6_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
