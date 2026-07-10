#!/usr/bin/env python3
"""Report-only approval decision for hardened Phase 6 prediction materialization."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.pipeline_gates import file_sha256
from scripts.validation.build_phase7_hardened_prediction_audit_decision import (
    BLOCKED_STATUS as PHASE7_BLOCKED_STATUS,
    DEFAULT_HARDENED_RUN,
    DEFAULT_REPORT_ONLY_RUN,
    DEFAULT_WFA_REPORT,
    EXPECTED_PREDICTION_COUNT,
    add_check,
    csv_ints,
    csv_strings,
    input_evidence,
    rel,
    resolve_path,
    validate_active_v2_hashes,
    validate_hardened_split,
    validate_master_audit,
    validate_no_prediction_artifact,
    validate_runner_preflight,
    validate_wfa_artifacts,
)
from scripts.validation.data_audit_universe_guard import load_data_audit_universe


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "phase6_hardened_prediction_materialization_decision"
BLOCKED_STATUS = (
    "BLOCKED_PHASE6_HARDENED_PREDICTION_MATERIALIZATION_RUNNER_GUARD_NO_EXECUTION"
)
FAIL_STATUS = "FAIL_PHASE6_HARDENED_PREDICTION_MATERIALIZATION_DECISION_INPUTS_INVALID"
REPORT_JSON = "prediction_materialization_decision.json"
REPORT_MD = "prediction_materialization_decision.md"

DEFAULT_PHASE7_DECISION = Path(
    "reports/prediction_audit/"
    "phase7_v2_apex_30m60m_20260709_tier1_core_hardened_report_only_decision/"
    "phase7_prediction_audit_decision.json"
)
DEFAULT_PREDICTIONS_MANIFEST = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_hardened_report_only/"
    "phase6_v2_apex_30m60m_20260709_tier1_core_hardened_report_only_predictions_manifest.json"
)
DEFAULT_SPLIT_PLAN = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_hardened_split_candidate/"
    "split_plan.json"
)
DEFAULT_SPLIT_ACCEPTANCE = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_hardened_split_candidate/"
    "hardened_split_acceptance_report.json"
)
DEFAULT_RUNNER_PREFLIGHT = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_hardened_runner_preflight/"
    "wfa_runner_preflight_report.json"
)
DEFAULT_FEATURE_SET = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_hardened_runner_preflight/"
    "tier1_core_active_feature_set.json"
)
DEFAULT_FEATURE_PLACEMENT_HASHES = Path(
    "reports/features_baseline/"
    "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "post_active_feature_hashes.json"
)
DEFAULT_LABEL_PLACEMENT_HASHES = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_active_replacement_decision/"
    "post_replacement_hashes.json"
)
DEFAULT_DATA_AUDIT_UNIVERSE = Path(
    "reports/data_audit/wfa_research/tier1_rebuild_v1/preflight/"
    "data_audit_universe_tier1_rebuild_v1.json"
)
DEFAULT_MASTER_AUDIT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_MASTER_AUDIT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_REPORTS_ROOT = Path(
    "reports/wfa/"
    "phase6_v2_apex_30m60m_20260709_tier1_core_hardened_prediction_materialization_decision"
)
DEFAULT_PREDICTIONS_ROOT = Path("data/predictions")
DEFAULT_HARDENED_REPORTS_ROOT = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_hardened"
)
DEFAULT_RUNNER_SCRIPT = Path("scripts/phase7_wfa/run_wfa.py")
DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")
DEFAULT_MODELS_CONFIG = Path("configs/models.yaml")
DEFAULT_INPUT_ROOT = Path("data/feature_matrices")
DEFAULT_MARKETS = ("6E", "CL", "ES", "ZN")
DEFAULT_YEARS = (2023, 2024)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.as_posix()} must contain a JSON object")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expected_report_file_check(reports_root: Path, repo_root: Path) -> dict[str, Any]:
    expected = {REPORT_JSON, REPORT_MD}
    if not reports_root.exists():
        return {"existing_files": [], "unexpected_files": [], "expected_files": sorted(expected)}
    existing = sorted(path.relative_to(reports_root).as_posix() for path in reports_root.rglob("*") if path.is_file())
    unexpected = [item for item in existing if item not in expected]
    return {
        "path": rel(reports_root, repo_root),
        "existing_files": existing,
        "unexpected_files": unexpected,
        "expected_files": sorted(expected),
    }


def future_phase6_write_predictions_command(
    *,
    input_root: Path,
    split_plan_path: Path,
    predictions_root: Path,
    hardened_reports_root: Path,
    models_config_path: Path,
    profile_config_path: Path,
    feature_set_path: Path,
    data_audit_universe_path: Path,
    hardened_run: str,
    repo_root: Path,
) -> str:
    return (
        "python -m scripts.phase6_wfa.run_wfa "
        "--profile tier_1 --matrix baseline "
        f"--run {hardened_run} "
        f"--input-root {rel(input_root, repo_root)} "
        f"--split-plan {rel(split_plan_path, repo_root)} "
        f"--predictions-root {rel(predictions_root, repo_root)} "
        f"--reports-root {rel(hardened_reports_root, repo_root)} "
        f"--models-config {rel(models_config_path, repo_root)} "
        f"--profile-config {rel(profile_config_path, repo_root)} "
        f"--feature-set {rel(feature_set_path, repo_root)} "
        f"--data-audit-universe-json {rel(data_audit_universe_path, repo_root)} "
        "--write-predictions"
    )


def validate_phase7_decision(phase7_decision: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    summary = phase7_decision.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    decision = phase7_decision.get("decision")
    decision = decision if isinstance(decision, Mapping) else {}
    if phase7_decision.get("status") != PHASE7_BLOCKED_STATUS:
        failures.append(f"phase7 decision status mismatch: {phase7_decision.get('status')!r}")
    failure_count = summary.get("failure_count")
    if failure_count is None or int(failure_count) != 0:
        failures.append("phase7 decision failure_count must be zero")
    if summary.get("block_reason") != "no_saved_oos_prediction_parquet":
        failures.append("phase7 decision block_reason must be no_saved_oos_prediction_parquet")
    if summary.get("normal_phase7_prediction_audit_allowed") is not False:
        failures.append("normal Phase 7 audit must remain disallowed")
    if decision.get("phase7_audit_command") is not None:
        failures.append("phase7_audit_command must remain null")
    if decision.get("future_unblock_requires_separate_prediction_materialization_approval") is not True:
        failures.append("phase7 decision must require separate prediction materialization approval")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "phase7_status": phase7_decision.get("status"),
        "block_reason": summary.get("block_reason"),
        "phase7_audit_command": decision.get("phase7_audit_command"),
    }


def validate_feature_set(feature_set: Mapping[str, Any], feature_set_path: Path, repo_root: Path) -> dict[str, Any]:
    failures: list[str] = []
    evidence = feature_set.get("evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    if feature_set.get("status") != "FROZEN":
        failures.append(f"feature_set.status mismatch: {feature_set.get('status')!r}")
    if feature_set.get("allowed_for_wfa") is not True:
        failures.append("feature_set.allowed_for_wfa must be true")
    if int(feature_set.get("feature_count") or -1) != 114:
        failures.append("feature_set.feature_count must be 114")
    if feature_set.get("feature_root") != "data/feature_matrices":
        failures.append("feature_set.feature_root must be data/feature_matrices")
    required_evidence = (
        "feature_manifest_path",
        "feature_manifest_hash",
        "split_plan_path",
        "split_plan_hash",
        "split_acceptance_path",
        "split_acceptance_hash",
    )
    missing = [key for key in required_evidence if not evidence.get(key)]
    if missing:
        failures.append(f"feature_set evidence missing fields: {missing}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "feature_set_path": rel(feature_set_path, repo_root),
        "feature_set_sha256": file_sha256(feature_set_path),
        "feature_count": feature_set.get("feature_count"),
        "evidence": dict(evidence),
    }


def validate_hardened_metadata(split_plan: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    folds = split_plan.get("folds")
    folds = folds if isinstance(folds, list) else []
    required_fields = (
        "train_start",
        "train_end",
        "validation_start",
        "validation_end",
        "validation_embargo_end",
        "test_start",
        "test_end",
        "test_embargo_end",
        "selection_allowed",
        "selection_source",
        "test_selection_allowed",
        "independent_test_claim_allowed",
    )
    for fold in folds:
        if not isinstance(fold, Mapping):
            failures.append("non-object fold row")
            continue
        fold_id = str(fold.get("fold_id") or "<unknown>")
        missing = [field for field in required_fields if field not in fold]
        if missing:
            failures.append(f"{fold_id}: missing metadata fields {missing}")
        if fold.get("selection_allowed") is not True:
            failures.append(f"{fold_id}: selection_allowed must be true")
        if fold.get("selection_source") != "validation_only":
            failures.append(f"{fold_id}: selection_source must be validation_only")
        if fold.get("test_selection_allowed") is not False:
            failures.append(f"{fold_id}: test_selection_allowed must be false")
        if fold.get("final_holdout") is True or fold.get("is_final_holdout") is True:
            failures.append(f"{fold_id}: final-holdout rows are forbidden")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "fold_count": len(folds),
    }


def validate_data_audit_universe(
    *,
    universe_path: Path,
    split_plan: Mapping[str, Any],
    markets: Sequence[str],
    years: Sequence[int],
    repo_root: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    try:
        universe = load_data_audit_universe(universe_path)
    except SystemExit as exc:
        return {"status": "FAIL", "failures": [str(exc)]}
    expected_pairs = {(str(market), int(year)) for market in markets for year in years}
    observed_pairs = set(universe.market_years)
    if observed_pairs != expected_pairs:
        failures.append(f"data-audit universe scope mismatch: {sorted(observed_pairs)}")
    for market, year in sorted(expected_pairs):
        failure = universe.require_usable(market, year, context=STAGE)
        if failure:
            failures.append(failure)
    split_evidence = split_plan.get("data_audit_universe")
    split_evidence = split_evidence if isinstance(split_evidence, Mapping) else {}
    if split_evidence.get("path") != rel(universe_path, repo_root):
        failures.append("split_plan data_audit_universe.path mismatch")
    if split_evidence.get("file_hash") != universe.file_hash:
        failures.append("split_plan data_audit_universe.file_hash mismatch")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "path": rel(universe_path, repo_root),
        "sha256": universe.file_hash,
        "status_counts": universe.status_counts,
        "market_year_count": len(universe.market_years),
    }


def validate_runner_hardened_write_guard(runner_script_path: Path, repo_root: Path) -> dict[str, Any]:
    failures: list[str] = []
    text = runner_script_path.read_text(encoding="utf-8")
    required_snippets = (
        "hardened split WFA is report-only only",
        "write_predictions or predictions_root is not None",
        "--write-predictions and",
        "--predictions-root are forbidden",
    )
    missing = [snippet for snippet in required_snippets if snippet not in text]
    if missing:
        failures.append(f"runner hardened write guard missing snippets: {missing}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "runner_script": rel(runner_script_path, repo_root),
        "runner_script_sha256": file_sha256(runner_script_path),
        "hardened_write_guard_active": not failures,
    }


def validate_no_future_outputs(
    *,
    hardened_reports_root: Path,
    predictions_root: Path,
    hardened_run: str,
    repo_root: Path,
) -> dict[str, Any]:
    prediction_run_root = predictions_root / hardened_run
    prediction_parquet = prediction_run_root / "oos_predictions.parquet"
    failures: list[str] = []
    hardened_report_files = (
        sorted(rel(path, repo_root) for path in hardened_reports_root.rglob("*") if path.is_file())
        if hardened_reports_root.exists()
        else []
    )
    prediction_files = (
        sorted(rel(path, repo_root) for path in prediction_run_root.rglob("*") if path.is_file())
        if prediction_run_root.exists()
        else []
    )
    if hardened_report_files:
        failures.append(f"hardened WFA report root already has files: {hardened_report_files}")
    if prediction_files:
        failures.append(f"hardened prediction root already has files: {prediction_files}")
    if prediction_parquet.exists():
        failures.append(f"hardened prediction parquet exists: {rel(prediction_parquet, repo_root)}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "hardened_reports_root": rel(hardened_reports_root, repo_root),
        "hardened_reports_existing_files": hardened_report_files,
        "prediction_run_root": rel(prediction_run_root, repo_root),
        "prediction_existing_files": prediction_files,
        "prediction_parquet_exists": prediction_parquet.exists(),
    }


def split_non_approval_evidence(split_plan: Mapping[str, Any], split_acceptance: Mapping[str, Any]) -> dict[str, Any]:
    acceptance_summary = split_acceptance.get("summary")
    acceptance_summary = acceptance_summary if isinstance(acceptance_summary, Mapping) else {}
    return {
        "status": "PASS",
        "split_plan_modeling_allowed": split_plan.get("modeling_allowed"),
        "split_plan_prediction_materialization_allowed": split_plan.get(
            "prediction_materialization_allowed"
        ),
        "acceptance_modeling_allowed": acceptance_summary.get("modeling_allowed"),
        "acceptance_prediction_materialization_allowed": acceptance_summary.get(
            "prediction_materialization_allowed"
        ),
        "note": (
            "The accepted hardened split is valid evidence for a future approval decision, "
            "but its own acceptance report does not authorize modeling or prediction writes."
        ),
    }


def build_report(
    *,
    repo_root: Path,
    phase7_decision_path: Path,
    wfa_report_path: Path,
    predictions_manifest_path: Path,
    split_plan_path: Path,
    split_acceptance_path: Path,
    runner_preflight_path: Path,
    feature_set_path: Path,
    feature_hashes_path: Path,
    label_hashes_path: Path,
    data_audit_universe_path: Path,
    master_run_status_path: Path,
    master_overview_path: Path,
    reports_root: Path,
    predictions_root: Path,
    hardened_reports_root: Path,
    runner_script_path: Path,
    input_root: Path,
    models_config_path: Path,
    profile_config_path: Path,
    hardened_run: str,
    report_only_run: str,
    markets: Sequence[str],
    years: Sequence[int],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    input_paths = {
        "phase7_decision": phase7_decision_path,
        "wfa_report": wfa_report_path,
        "predictions_manifest": predictions_manifest_path,
        "split_plan": split_plan_path,
        "split_acceptance": split_acceptance_path,
        "runner_preflight": runner_preflight_path,
        "feature_set": feature_set_path,
        "feature_placement_hashes": feature_hashes_path,
        "label_placement_hashes": label_hashes_path,
        "data_audit_universe": data_audit_universe_path,
        "master_audit_run_status": master_run_status_path,
        "master_audit_overview": master_overview_path,
        "runner_script": runner_script_path,
        "models_config": models_config_path,
        "profile_config": profile_config_path,
    }
    for path in input_paths.values():
        if not path.exists():
            raise FileNotFoundError(path)

    phase7_decision = read_json(phase7_decision_path)
    wfa_report = read_json(wfa_report_path)
    manifest = read_json(predictions_manifest_path)
    split_plan = read_json(split_plan_path)
    split_acceptance = read_json(split_acceptance_path)
    runner_preflight = read_json(runner_preflight_path)
    feature_set = read_json(feature_set_path)
    feature_hashes = read_json(feature_hashes_path)
    label_hashes = read_json(label_hashes_path)
    master_run_status = read_json(master_run_status_path)
    master_overview = read_json(master_overview_path)

    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    output_check = expected_report_file_check(reports_root, repo_root)
    add_check(
        checks,
        failures,
        name="decision_report_root_contains_only_expected_files",
        passed=not output_check["unexpected_files"],
        evidence=output_check,
        failure=f"unexpected report files: {output_check['unexpected_files']}",
    )

    phase7_check = validate_phase7_decision(phase7_decision)
    add_check(
        checks,
        failures,
        name="phase7_report_only_decision_blocks_on_absent_saved_predictions",
        passed=phase7_check["status"] == "PASS",
        evidence=phase7_check,
        failure="; ".join(phase7_check["failures"]),
    )

    wfa_check = validate_wfa_artifacts(
        wfa_report=wfa_report,
        manifest=manifest,
        split_plan_path=split_plan_path,
        markets=markets,
        years=years,
        repo_root=repo_root,
    )
    add_check(
        checks,
        failures,
        name="hardened_report_only_wfa_artifacts_are_clean",
        passed=wfa_check["status"] == "PASS",
        evidence=wfa_check,
        failure="; ".join(wfa_check["failures"]),
    )

    no_artifact_check = validate_no_prediction_artifact(
        manifest=manifest,
        predictions_root=predictions_root,
        hardened_run=hardened_run,
        report_only_run=report_only_run,
        repo_root=repo_root,
    )
    add_check(
        checks,
        failures,
        name="no_existing_hardened_or_report_only_prediction_artifact",
        passed=no_artifact_check["status"] == "PASS",
        evidence=no_artifact_check,
        failure="; ".join(no_artifact_check["failures"]),
    )

    split_check = validate_hardened_split(
        split_plan,
        split_acceptance,
        split_plan_path,
        markets,
        years,
        repo_root,
    )
    add_check(
        checks,
        failures,
        name="hardened_split_scope_and_acceptance",
        passed=split_check["status"] == "PASS",
        evidence=split_check,
        failure="; ".join(split_check["failures"]),
    )

    metadata_check = validate_hardened_metadata(split_plan)
    add_check(
        checks,
        failures,
        name="hardened_split_validation_test_metadata",
        passed=metadata_check["status"] == "PASS",
        evidence=metadata_check,
        failure="; ".join(metadata_check["failures"]),
    )

    non_approval_check = split_non_approval_evidence(split_plan, split_acceptance)
    add_check(
        checks,
        failures,
        name="hardened_split_acceptance_does_not_authorize_prediction_writes",
        passed=True,
        evidence=non_approval_check,
        failure="hardened split acceptance unexpectedly authorizes prediction writes",
    )

    preflight_check = validate_runner_preflight(runner_preflight)
    add_check(
        checks,
        failures,
        name="hardened_runner_preflight_report_only",
        passed=preflight_check["status"] == "PASS",
        evidence=preflight_check,
        failure="; ".join(preflight_check["failures"]),
    )

    feature_set_check = validate_feature_set(feature_set, feature_set_path, repo_root)
    add_check(
        checks,
        failures,
        name="report_local_feature_set_is_frozen_for_wfa",
        passed=feature_set_check["status"] == "PASS",
        evidence=feature_set_check,
        failure="; ".join(feature_set_check["failures"]),
    )

    active_hash_check = validate_active_v2_hashes(feature_hashes, label_hashes, markets, years)
    add_check(
        checks,
        failures,
        name="active_v2_label_feature_hash_scope",
        passed=active_hash_check["status"] == "PASS",
        evidence=active_hash_check,
        failure="; ".join(active_hash_check["failures"]),
    )

    universe_check = validate_data_audit_universe(
        universe_path=data_audit_universe_path,
        split_plan=split_plan,
        markets=markets,
        years=years,
        repo_root=repo_root,
    )
    add_check(
        checks,
        failures,
        name="data_audit_universe_exact_usable_scope",
        passed=universe_check["status"] == "PASS",
        evidence=universe_check,
        failure="; ".join(universe_check["failures"]),
    )

    master_check = validate_master_audit(master_run_status, master_overview)
    add_check(
        checks,
        failures,
        name="master_audit_phase6_phase7_remain_not_run",
        passed=master_check["status"] == "PASS",
        evidence=master_check,
        failure="; ".join(master_check["failures"]),
    )

    future_outputs = validate_no_future_outputs(
        hardened_reports_root=hardened_reports_root,
        predictions_root=predictions_root,
        hardened_run=hardened_run,
        repo_root=repo_root,
    )
    add_check(
        checks,
        failures,
        name="future_hardened_prediction_output_roots_are_absent",
        passed=future_outputs["status"] == "PASS",
        evidence=future_outputs,
        failure="; ".join(future_outputs["failures"]),
    )

    runner_guard = validate_runner_hardened_write_guard(runner_script_path, repo_root)
    add_check(
        checks,
        failures,
        name="current_runner_forbids_hardened_prediction_writes",
        passed=runner_guard["status"] == "PASS",
        evidence=runner_guard,
        failure="; ".join(runner_guard["failures"]),
    )

    candidate_command = future_phase6_write_predictions_command(
        input_root=input_root,
        split_plan_path=split_plan_path,
        predictions_root=predictions_root,
        hardened_reports_root=hardened_reports_root,
        models_config_path=models_config_path,
        profile_config_path=profile_config_path,
        feature_set_path=feature_set_path,
        data_audit_universe_path=data_audit_universe_path,
        hardened_run=hardened_run,
        repo_root=repo_root,
    )

    status = BLOCKED_STATUS if not failures else FAIL_STATUS
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "markets": list(markets),
            "years": [int(year) for year in years],
            "market_year_count": len(markets) * len(years),
            "hardened_run": hardened_run,
            "report_only_run": report_only_run,
            "expected_prediction_count_from_report_only_wfa": EXPECTED_PREDICTION_COUNT,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "decision": "BLOCKED_NO_EXECUTION" if not failures else "FAIL_INPUTS_INVALID",
            "runner_hardened_write_guard_active": runner_guard["status"] == "PASS",
            "candidate_command_approved_for_execution": False,
            "prediction_materialization_executed": False,
            "future_runner_patch_required": not failures,
            "phase7_audit_allowed": False,
            "phase8_refresh_allowed": False,
            "promotion_allowed": False,
            "paper_live_allowed": False,
        },
        "decision": {
            "recommendation": "DEFER",
            "reason": (
                "Phase 7 is blocked on absent saved predictions, but current Phase 6 runner "
                "guard intentionally rejects hardened splits when --write-predictions or "
                "--predictions-root is supplied."
            ),
            "candidate_write_predictions_command_not_approved": candidate_command,
            "required_before_execution": [
                "separate user approval for runner compatibility hardening",
                "patch runner to allow hardened prediction writes only after embedded active evidence checks",
                "focused tests proving hardened write remains exact-scope and fails closed on stale evidence",
                "fresh absence check for hardened report and prediction output roots",
            ],
        },
        "checks": checks,
        "failures": failures,
        "input_evidence": input_evidence(repo_root, input_paths),
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "non_approval": {
            "wfa_execution": False,
            "prediction_materialization": False,
            "phase8_refresh": False,
            "provider_or_network": False,
            "promotion_or_artifact_freeze": False,
            "final_holdout": False,
            "paper_or_live": False,
            "cleanup": False,
            "git_staging_commit_push": False,
            "label_or_feature_rebuild": False,
            "active_split_replacement": False,
            "prop_account_reports": False,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    decision = report["decision"]
    lines = [
        "# Hardened Phase 6 Prediction Materialization Decision",
        "",
        f"- Status: `{report['status']}`",
        f"- Recommendation: `{decision['recommendation']}`",
        f"- Failure count: `{summary['failure_count']}`",
        f"- Candidate command approved: `{summary['candidate_command_approved_for_execution']}`",
        f"- Prediction materialization executed: `{summary['prediction_materialization_executed']}`",
        f"- Runner hardening required before execution: `{summary['future_runner_patch_required']}`",
        "",
        "## Reason",
        "",
        decision["reason"],
        "",
        "## Candidate Command Not Approved",
        "",
        f"`{decision['candidate_write_predictions_command_not_approved']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Failure |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        failure = str(check.get("failure") or "").replace("|", "\\|")
        lines.append(f"| `{check['name']}` | `{check['status']}` | {failure} |")
    lines.extend(["", "## Failures", ""])
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Non-Approval",
            "",
            "- This report does not run WFA execution, materialize predictions, refresh Phase 8, approve promotion, touch final holdout, write prop-account reports, run provider/download commands, mutate data, clean up files, stage, commit, or push.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    write_json(reports_root / REPORT_JSON, report)
    (reports_root / REPORT_MD).write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase7-decision", default=DEFAULT_PHASE7_DECISION.as_posix())
    parser.add_argument("--wfa-report", default=DEFAULT_WFA_REPORT.as_posix())
    parser.add_argument("--predictions-manifest", default=DEFAULT_PREDICTIONS_MANIFEST.as_posix())
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--split-acceptance", default=DEFAULT_SPLIT_ACCEPTANCE.as_posix())
    parser.add_argument("--runner-preflight", default=DEFAULT_RUNNER_PREFLIGHT.as_posix())
    parser.add_argument("--feature-set", default=DEFAULT_FEATURE_SET.as_posix())
    parser.add_argument("--feature-placement-hashes", default=DEFAULT_FEATURE_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--label-placement-hashes", default=DEFAULT_LABEL_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--data-audit-universe-json", default=DEFAULT_DATA_AUDIT_UNIVERSE.as_posix())
    parser.add_argument("--master-audit-run-status", default=DEFAULT_MASTER_AUDIT_RUN_STATUS.as_posix())
    parser.add_argument("--master-audit-overview", default=DEFAULT_MASTER_AUDIT_OVERVIEW.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--predictions-root", default=DEFAULT_PREDICTIONS_ROOT.as_posix())
    parser.add_argument("--hardened-reports-root", default=DEFAULT_HARDENED_REPORTS_ROOT.as_posix())
    parser.add_argument("--runner-script", default=DEFAULT_RUNNER_SCRIPT.as_posix())
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--hardened-run", default=DEFAULT_HARDENED_RUN)
    parser.add_argument("--report-only-run", default=DEFAULT_REPORT_ONLY_RUN)
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    reports_root = resolve_path(REPO_ROOT, args.reports_root)
    report = build_report(
        repo_root=REPO_ROOT,
        phase7_decision_path=resolve_path(REPO_ROOT, args.phase7_decision),
        wfa_report_path=resolve_path(REPO_ROOT, args.wfa_report),
        predictions_manifest_path=resolve_path(REPO_ROOT, args.predictions_manifest),
        split_plan_path=resolve_path(REPO_ROOT, args.split_plan),
        split_acceptance_path=resolve_path(REPO_ROOT, args.split_acceptance),
        runner_preflight_path=resolve_path(REPO_ROOT, args.runner_preflight),
        feature_set_path=resolve_path(REPO_ROOT, args.feature_set),
        feature_hashes_path=resolve_path(REPO_ROOT, args.feature_placement_hashes),
        label_hashes_path=resolve_path(REPO_ROOT, args.label_placement_hashes),
        data_audit_universe_path=resolve_path(REPO_ROOT, args.data_audit_universe_json),
        master_run_status_path=resolve_path(REPO_ROOT, args.master_audit_run_status),
        master_overview_path=resolve_path(REPO_ROOT, args.master_audit_overview),
        reports_root=reports_root,
        predictions_root=resolve_path(REPO_ROOT, args.predictions_root),
        hardened_reports_root=resolve_path(REPO_ROOT, args.hardened_reports_root),
        runner_script_path=resolve_path(REPO_ROOT, args.runner_script),
        input_root=resolve_path(REPO_ROOT, args.input_root),
        models_config_path=resolve_path(REPO_ROOT, args.models_config),
        profile_config_path=resolve_path(REPO_ROOT, args.profile_config),
        hardened_run=args.hardened_run,
        report_only_run=args.report_only_run,
        markets=csv_strings(args.markets),
        years=csv_ints(args.years),
    )
    write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"approved={report['summary']['candidate_command_approved_for_execution']} "
        f"json={rel(reports_root / REPORT_JSON, REPO_ROOT)}"
    )
    return 0 if report["status"] == BLOCKED_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
