#!/usr/bin/env python3
"""Report-only Phase 6 WFA runner preflight for active Tier 1 core features."""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from scripts.pipeline_gates import file_sha256
from scripts.profile_scope import load_profile_scope
from scripts.validation.data_audit_universe_guard import (
    data_audit_evidence_matches,
    load_data_audit_universe,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "phase6_wfa_runner_preflight"
PASS_STATUS = "PASS_PHASE6_WFA_RUNNER_PREFLIGHT_READY_REPORT_ONLY"
FAIL_STATUS = "FAIL_PHASE6_WFA_RUNNER_PREFLIGHT"
DEFAULT_SPLIT_PLAN = Path("reports/wfa/tier1_core_phase5_split_plan_20260706/split_plan.json")
DEFAULT_SPLIT_ACCEPTANCE = Path(
    "reports/wfa/tier1_core_phase5_split_plan_20260706/split_plan_acceptance_report.json"
)
DEFAULT_FEATURE_ROOT = Path("data/feature_matrices")
DEFAULT_FEATURE_MANIFEST = Path(
    "reports/data_audit/current_state/"
    "tier1_core_phase4_self_reference_cleanup_active_placement_20260706/"
    "active_feature_manifest.json"
)
DEFAULT_REPORT_ROOT = Path("reports/wfa/tier1_core_phase6_wfa_runner_preflight_20260706")
DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")
DEFAULT_MODELS_CONFIG = Path("configs/models.yaml")
DEFAULT_PREDICTIONS_ROOT = Path("data/predictions")
EXPECTED_PROFILE = "tier_1_core"
EXPECTED_RESOLVED_PROFILE = "tier_1_research"
EXPECTED_MARKETS = ["ES", "CL", "ZN", "6E"]
EXPECTED_YEARS = [2023, 2024]
FEATURE_SET_FILENAME = "tier1_core_active_feature_set.json"

REQUIRED_PHASE6_FLAGS = {
    "--profile",
    "--matrix",
    "--run",
    "--input-root",
    "--split-plan",
    "--predictions-root",
    "--reports-root",
    "--models-config",
    "--profile-config",
    "--feature-cols",
    "--feature-set",
    "--max-folds",
    "--markets",
    "--fold-shard-count",
    "--fold-shard-index",
    "--data-audit-universe-json",
    "--write-predictions",
    "--no-predictions",
    "--report-only",
}

NO_MUTATION_TEXT = (
    "Report-only Phase 6/WFA runner preflight. It imports and inspects the runner surface "
    "but does not call run_wfa, fit models, score folds, write predictions, call providers, "
    "replace data, stage, commit, push, paper trade, or live trade."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.as_posix()} must contain a JSON object")
    return payload


def read_json_list(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"{path.as_posix()} must contain a JSON string list")
    return list(payload)


def count_files(root: Path) -> int:
    if not root.exists():
        return 0
    if root.is_file():
        return 1
    return sum(1 for path in root.rglob("*") if path.is_file())


def add_check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    evidence: Mapping[str, Any],
    failure: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "evidence": dict(evidence),
            "failure": None if passed else failure,
        }
    )
    if not passed:
        failures.append(f"{name}: {failure}")


def sorted_pairs(markets: Iterable[str], years: Iterable[int]) -> list[dict[str, Any]]:
    return [
        {"market": market, "year": int(year)}
        for market in sorted(str(item) for item in markets)
        for year in sorted(int(item) for item in years)
    ]


def phase6_module() -> Any:
    return importlib.import_module("scripts.phase6_wfa.run_wfa")


def phase7_internal_module() -> Any:
    return importlib.import_module("scripts.phase7_wfa.run_wfa")


def phase6_cli_flags(module: Any) -> set[str]:
    parser = module.build_arg_parser()
    flags: set[str] = set()
    for action in parser._actions:
        flags.update(option for option in action.option_strings if option.startswith("--"))
    return flags


def phase6_required_columns(module: Any, feature_cols: list[str], model_specs: list[Any]) -> list[str]:
    return list(module._required_source_columns(feature_cols, model_specs))


def parquet_schema(path: Path) -> set[str]:
    return set(pq.read_schema(path).names)


def feature_set_payload(
    *,
    repo_root: Path,
    feature_root: Path,
    feature_manifest_path: Path,
    split_plan_path: Path,
    split_acceptance_path: Path,
    features: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "feature_set_id": "tier1_core_active_phase6_preflight_114_features",
        "status": "FROZEN",
        "allowed_for_wfa": True,
        "matrix": "baseline",
        "feature_root": rel(feature_root, repo_root),
        "feature_cols_path": rel(feature_root / "feature_cols.json", repo_root),
        "feature_count": len(features),
        "features": features,
        "source": "Report-only Phase 6 WFA runner preflight over accepted active Tier 1 core Phase 4/5 evidence.",
        "usage": "WFA research only; not production, paper, or live trading approval.",
        "evidence": {
            "feature_manifest_path": rel(feature_manifest_path, repo_root),
            "feature_manifest_hash": file_sha256(feature_manifest_path),
            "split_plan_path": rel(split_plan_path, repo_root),
            "split_plan_hash": file_sha256(split_plan_path),
            "split_acceptance_path": rel(split_acceptance_path, repo_root),
            "split_acceptance_hash": file_sha256(split_acceptance_path),
        },
    }


def write_feature_set_manifest(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_generated_scope(
    *,
    report_root: Path,
    allowed_paths: set[Path],
    repo_root: Path,
) -> tuple[list[str], dict[str, Any]]:
    if not report_root.exists():
        return [f"report root missing: {rel(report_root, repo_root)}"], {"existing_files": []}
    existing = {path.resolve() for path in report_root.rglob("*") if path.is_file()}
    allowed = {path.resolve() for path in allowed_paths}
    unexpected = sorted(rel(path, repo_root) for path in existing - allowed)
    return (
        [f"unexpected files under Phase 6 preflight report root: {unexpected}"]
        if unexpected
        else [],
        {
            "report_root": rel(report_root, repo_root),
            "existing_files": sorted(rel(path, repo_root) for path in existing),
            "allowed_files": sorted(rel(path, repo_root) for path in allowed),
            "unexpected_files": unexpected,
        },
    )


def build_report(
    *,
    repo_root: Path,
    split_plan_path: Path,
    split_acceptance_path: Path,
    feature_root: Path,
    feature_manifest_path: Path,
    feature_set_path: Path,
    json_out: Path,
    md_out: Path,
    profile_config_path: Path,
    models_config_path: Path,
    predictions_root: Path,
    expected_profile: str,
    expected_resolved_profile: str,
    expected_markets: list[str],
    expected_years: list[int],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []

    wrapper_module = phase6_module()
    internal_module = phase7_internal_module()
    split_plan = read_json(split_plan_path)
    split_acceptance = read_json(split_acceptance_path)
    feature_manifest = read_json(feature_manifest_path)
    feature_cols = read_json_list(feature_root / "feature_cols.json")
    target_cols = read_json_list(feature_root / "target_cols.json")
    feature_set = read_json(feature_set_path)

    wrapper_ok = callable(getattr(wrapper_module, "main", None)) and callable(
        getattr(wrapper_module, "run_wfa", None)
    )
    add_check(
        checks,
        failures,
        name="phase6_wrapper_surface_importable",
        passed=wrapper_ok,
        evidence={
            "module": "scripts.phase6_wfa.run_wfa",
            "main_callable": callable(getattr(wrapper_module, "main", None)),
            "run_wfa_callable": callable(getattr(wrapper_module, "run_wfa", None)),
        },
        failure="Phase 6 wrapper surface is not importable/callable",
    )

    flags = phase6_cli_flags(wrapper_module)
    missing_flags = sorted(REQUIRED_PHASE6_FLAGS - flags)
    add_check(
        checks,
        failures,
        name="phase6_cli_has_required_preflight_controls",
        passed=not missing_flags,
        evidence={"observed_flags": sorted(flags), "missing_flags": missing_flags},
        failure=f"Phase 6 CLI missing required controls: {missing_flags}",
    )

    plan = load_profile_scope(expected_profile, profile_config_path)
    scope_ok = (
        plan.requested_profile == expected_profile
        and plan.resolved_profile == expected_resolved_profile
        and sorted(plan.markets) == sorted(expected_markets)
        and sorted(plan.years) == sorted(expected_years)
    )
    add_check(
        checks,
        failures,
        name="profile_scope_matches_objective",
        passed=scope_ok,
        evidence={
            "requested_profile": plan.requested_profile,
            "resolved_profile": plan.resolved_profile,
            "markets": plan.markets,
            "years": plan.years,
        },
        failure="profile scope does not match active Tier 1 core objective",
    )

    split_scope_failure: str | None = None
    try:
        internal_module._validate_split_plan_scope(
            split_manifest=split_plan,
            plan=plan,
            profile_config=profile_config_path,
            models_config=models_config_path,
        )
    except SystemExit as exc:
        split_scope_failure = str(exc)
    split_hash_matches_acceptance = (
        split_acceptance.get("status") == "PASS_PHASE5_SPLIT_PLAN_ACCEPTED_REPORT_ONLY"
        and split_acceptance.get("input_evidence", {}).get("split_plan_json_sha256")
        == file_sha256(split_plan_path)
    )
    add_check(
        checks,
        failures,
        name="accepted_split_plan_bound_to_phase6_scope",
        passed=(
            split_scope_failure is None
            and split_hash_matches_acceptance
            and split_plan.get("input_root") == rel(feature_root, repo_root)
            and int(split_plan.get("failure_count") or 0) == 0
            and int(split_plan.get("fold_count") or 0) > 0
        ),
        evidence={
            "split_plan": rel(split_plan_path, repo_root),
            "split_hash_matches_acceptance": split_hash_matches_acceptance,
            "split_scope_failure": split_scope_failure,
            "input_root": split_plan.get("input_root"),
            "fold_count": split_plan.get("fold_count"),
            "failure_count": split_plan.get("failure_count"),
        },
        failure="accepted split plan is not bound to current Phase 6 profile/config/input root",
    )

    universe_evidence = split_plan.get("data_audit_universe")
    universe = None
    universe_failures: list[str] = []
    if isinstance(universe_evidence, Mapping):
        universe_path = resolve_path(repo_root, str(universe_evidence.get("path") or ""))
        try:
            universe = load_data_audit_universe(universe_path)
        except SystemExit as exc:
            universe_failures.append(str(exc))
    else:
        universe_path = Path("")
        universe_failures.append("split plan missing data_audit_universe evidence")
    if universe is not None:
        for pair in sorted_pairs(expected_markets, expected_years):
            failure = universe.require_usable(
                str(pair["market"]),
                int(pair["year"]),
                context="Phase 6 runner preflight",
            )
            if failure:
                universe_failures.append(failure)
    add_check(
        checks,
        failures,
        name="split_plan_data_audit_universe_binding",
        passed=(
            universe is not None
            and data_audit_evidence_matches(universe_evidence, universe)
            and not universe_failures
        ),
        evidence={
            "path": rel(universe_path, repo_root) if universe_path else None,
            "evidence_matches_split_plan": (
                data_audit_evidence_matches(universe_evidence, universe)
                if universe is not None
                else False
            ),
            "status_counts": universe.status_counts if universe is not None else None,
            "failures": universe_failures,
        },
        failure="data-audit universe is missing, stale, or not usable for all market-years",
    )

    registry = feature_manifest.get("registry")
    registry = registry if isinstance(registry, Mapping) else {}
    manifest_feature_cols = list(registry.get("feature_cols") or [])
    manifest_target_cols = list(registry.get("target_cols") or [])
    forbidden = wrapper_module.forbidden_feature_columns(feature_cols)
    duplicate_features = sorted({item for item in feature_cols if feature_cols.count(item) > 1})
    add_check(
        checks,
        failures,
        name="active_feature_column_registry_114_clean_features",
        passed=(
            len(feature_cols) == int(feature_manifest.get("feature_count") or -1)
            and feature_cols == manifest_feature_cols
            and target_cols == manifest_target_cols
            and not forbidden
            and not duplicate_features
            and feature_manifest.get("feature_audit_gate", {}).get("status") == "PASS"
            and int(feature_manifest.get("failure_count") or 0) == 0
        ),
        evidence={
            "feature_cols_path": rel(feature_root / "feature_cols.json", repo_root),
            "feature_count": len(feature_cols),
            "manifest_feature_count": feature_manifest.get("feature_count"),
            "target_count": len(target_cols),
            "forbidden_features": forbidden,
            "duplicate_features": duplicate_features,
            "feature_audit_gate": feature_manifest.get("feature_audit_gate", {}).get("status"),
        },
        failure="active feature columns do not match manifest registry or contain forbidden/duplicate columns",
    )

    feature_gate = split_plan.get("feature_manifest_gate")
    feature_gate = feature_gate if isinstance(feature_gate, Mapping) else {}
    manifest_hash_matches = (
        feature_gate.get("manifest_path") == rel(feature_manifest_path, repo_root)
        and feature_gate.get("manifest_hash") == file_sha256(feature_manifest_path)
        and feature_gate.get("expected_output_root") == rel(feature_root, repo_root)
        and feature_gate.get("expected_resolved_profile") == expected_resolved_profile
    )
    add_check(
        checks,
        failures,
        name="split_plan_feature_manifest_gate_binding",
        passed=feature_gate.get("status") == "PASS" and manifest_hash_matches,
        evidence={
            "status": feature_gate.get("status"),
            "manifest_path": feature_gate.get("manifest_path"),
            "hash_matches": manifest_hash_matches,
            "expected_output_root": feature_gate.get("expected_output_root"),
            "expected_resolved_profile": feature_gate.get("expected_resolved_profile"),
        },
        failure="split-plan feature manifest gate is missing, failed, stale, or wrong-root",
    )

    split_hashes = split_plan.get("input_file_hashes")
    split_hashes = split_hashes if isinstance(split_hashes, Mapping) else {}
    manifest_hashes = feature_manifest.get("output_hashes")
    manifest_hashes = manifest_hashes if isinstance(manifest_hashes, Mapping) else {}
    expected_files = [
        feature_root / str(pair["market"]) / f"{int(pair['year'])}.parquet"
        for pair in sorted_pairs(expected_markets, expected_years)
    ]
    file_failures: list[str] = []
    for path in expected_files:
        path_rel = rel(path, repo_root)
        if not path.is_file():
            file_failures.append(f"{path_rel}: missing")
            continue
        observed_hash = file_sha256(path)
        if split_hashes.get(path_rel) != observed_hash:
            file_failures.append(f"{path_rel}: split-plan input hash mismatch")
        if manifest_hashes.get(path_rel) != observed_hash:
            file_failures.append(f"{path_rel}: feature-manifest output hash mismatch")
    add_check(
        checks,
        failures,
        name="active_feature_files_match_split_and_manifest_hashes",
        passed=not file_failures and len(split_hashes) == len(expected_files),
        evidence={
            "expected_file_count": len(expected_files),
            "split_input_hash_count": len(split_hashes),
            "manifest_output_hash_count": len(manifest_hashes),
            "hash_failures": file_failures,
        },
        failure="active feature parquet hashes do not match split-plan and feature-manifest evidence",
    )

    try:
        feature_set_spec = wrapper_module.load_feature_set(feature_set_path)
        feature_set_failure = None
    except SystemExit as exc:
        feature_set_spec = None
        feature_set_failure = str(exc)
    feature_set_features = feature_set_spec.feature_cols if feature_set_spec is not None else []
    add_check(
        checks,
        failures,
        name="report_local_feature_set_manifest_loads_for_phase6",
        passed=feature_set_spec is not None and feature_set_features == feature_cols,
        evidence={
            "feature_set_path": rel(feature_set_path, repo_root),
            "status": feature_set.get("status"),
            "allowed_for_wfa": feature_set.get("allowed_for_wfa"),
            "feature_count": feature_set.get("feature_count"),
            "feature_cols_path": feature_set.get("feature_cols_path"),
            "loader_failure": feature_set_failure,
        },
        failure="report-local feature-set manifest is not accepted by the Phase 6 loader",
    )

    try:
        model_specs, model_config = wrapper_module.load_model_specs(models_config_path)
        model_failure = None
    except SystemExit as exc:
        model_specs = []
        model_config = {}
        model_failure = str(exc)
    model_targets = [spec.target for spec in model_specs]
    missing_model_targets = sorted(set(model_targets) - set(target_cols))
    add_check(
        checks,
        failures,
        name="models_config_policy_and_targets_preflight",
        passed=model_failure is None and bool(model_specs) and not missing_model_targets,
        evidence={
            "models_config": rel(models_config_path, repo_root),
            "model_count": len(model_specs),
            "model_ids": [spec.model_id for spec in model_specs],
            "model_targets": model_targets,
            "missing_model_targets": missing_model_targets,
            "model_failure": model_failure,
            "policy": model_config.get("policy") if isinstance(model_config, Mapping) else None,
        },
        failure="models config policy failed or enabled model targets are missing from active target registry",
    )

    required_columns = phase6_required_columns(internal_module, feature_cols, model_specs)
    schema_failures: list[str] = []
    schema_summary: list[dict[str, Any]] = []
    for path in expected_files:
        path_rel = rel(path, repo_root)
        if not path.is_file():
            continue
        available = parquet_schema(path)
        missing = sorted(column for column in required_columns if column not in available)
        if missing:
            schema_failures.append(f"{path_rel}: missing {missing}")
        schema_summary.append(
            {
                "path": path_rel,
                "column_count": len(available),
                "required_missing_count": len(missing),
            }
        )
    add_check(
        checks,
        failures,
        name="active_feature_matrix_schemas_cover_phase6_required_columns",
        passed=not schema_failures and len(schema_summary) == len(expected_files),
        evidence={
            "required_column_count": len(required_columns),
            "schema_summary": schema_summary,
            "schema_failures": schema_failures[:20],
        },
        failure="one or more active feature matrices lack columns required by Phase 6 source loading",
    )

    report_root = json_out.parent
    scope_failures, scope_evidence = validate_generated_scope(
        report_root=report_root,
        allowed_paths={json_out, md_out, feature_set_path},
        repo_root=repo_root,
    )
    prediction_file_count = count_files(predictions_root)
    add_check(
        checks,
        failures,
        name="generated_artifact_scope_and_no_prediction_writes",
        passed=not scope_failures and prediction_file_count == 0,
        evidence={**scope_evidence, "prediction_file_count": prediction_file_count},
        failure="; ".join(scope_failures) or "prediction files are present",
    )

    add_check(
        checks,
        failures,
        name="wfa_runner_not_executed_by_preflight",
        passed=True,
        evidence={
            "commands_executed": 0,
            "run_wfa_called": False,
            "model_training_performed": False,
            "prediction_generation_performed": False,
        },
        failure="preflight executed WFA/model training or prediction generation",
    )

    status = PASS_STATUS if not failures else FAIL_STATUS
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "profile": expected_profile,
            "resolved_profile": expected_resolved_profile,
            "markets": expected_markets,
            "years": expected_years,
            "market_year_count": len(expected_markets) * len(expected_years),
            "feature_root": rel(feature_root, repo_root),
            "split_plan": rel(split_plan_path, repo_root),
        },
        "summary": {
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "fold_count": split_plan.get("fold_count"),
            "feature_count": len(feature_cols),
            "model_count": len(model_specs),
            "feature_file_count": len(expected_files),
            "prediction_file_count": prediction_file_count,
            "commands_executed": 0,
            "model_training_performed": False,
            "prediction_generation_performed": False,
        },
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "input_evidence": {
            "split_plan": rel(split_plan_path, repo_root),
            "split_plan_sha256": file_sha256(split_plan_path),
            "split_acceptance_report": rel(split_acceptance_path, repo_root),
            "split_acceptance_report_sha256": file_sha256(split_acceptance_path),
            "feature_manifest": rel(feature_manifest_path, repo_root),
            "feature_manifest_sha256": file_sha256(feature_manifest_path),
            "feature_set_manifest": rel(feature_set_path, repo_root),
            "feature_set_manifest_sha256": file_sha256(feature_set_path),
            "models_config": rel(models_config_path, repo_root),
            "models_config_sha256": file_sha256(models_config_path),
            "profile_config": rel(profile_config_path, repo_root),
            "profile_config_sha256": file_sha256(profile_config_path),
            "predictions_root": rel(predictions_root, repo_root),
        },
        "candidate_phase6_command_not_approved": (
            "python -m scripts.phase6_wfa.run_wfa "
            f"--profile {expected_profile} --matrix baseline --run tier1_core_phase6_candidate "
            f"--input-root {rel(feature_root, repo_root)} "
            f"--split-plan {rel(split_plan_path, repo_root)} "
            f"--reports-root reports/wfa/tier1_core_phase6_candidate "
            f"--models-config {rel(models_config_path, repo_root)} "
            f"--profile-config {rel(profile_config_path, repo_root)} "
            f"--feature-set {rel(feature_set_path, repo_root)} "
            f"--data-audit-universe-json {rel(universe_path, repo_root) if universe_path else '<missing>'} "
            "--report-only"
        ),
        "non_approval": {
            "wfa_runner_execution": False,
            "wfa_model_training": False,
            "prediction_generation": False,
            "provider_calls": False,
            "data_replacement": False,
            "cleanup_archive": False,
            "staging_commit_push": False,
            "paper_or_live_work": False,
        },
        "non_approval_text": NO_MUTATION_TEXT,
        "recommended_next_action": (
            "If this preflight remains PASS, the next separate decision is whether to approve "
            "a bounded Phase 6 runner execution. This report does not approve that execution."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 6 WFA Runner Preflight",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated at UTC: `{report['generated_at_utc']}`",
        f"- Feature count: `{report['summary']['feature_count']}`",
        f"- Fold count: `{report['summary']['fold_count']}`",
        f"- Model count: `{report['summary']['model_count']}`",
        f"- Prediction files: `{report['summary']['prediction_file_count']}`",
        f"- Commands executed: `{report['summary']['commands_executed']}`",
        f"- Model training performed: `{report['summary']['model_training_performed']}`",
        f"- Prediction generation performed: `{report['summary']['prediction_generation_performed']}`",
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
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Candidate Command Not Approved",
            "",
            f"`{report['candidate_phase6_command_not_approved']}`",
            "",
            "## Non-Approval",
            "",
            f"- {report['non_approval_text']}",
            "",
            "## Recommended Next Action",
            "",
            f"- {report['recommended_next_action']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], json_out: Path, md_out: Path) -> tuple[Path, Path]:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(report), encoding="utf-8")
    return json_out, md_out


def csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--split-plan", default=str(DEFAULT_SPLIT_PLAN))
    parser.add_argument("--split-acceptance", default=str(DEFAULT_SPLIT_ACCEPTANCE))
    parser.add_argument("--feature-root", default=str(DEFAULT_FEATURE_ROOT))
    parser.add_argument("--feature-manifest", default=str(DEFAULT_FEATURE_MANIFEST))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--md-out", default=None)
    parser.add_argument("--feature-set-out", default=None)
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--models-config", default=str(DEFAULT_MODELS_CONFIG))
    parser.add_argument("--predictions-root", default=str(DEFAULT_PREDICTIONS_ROOT))
    parser.add_argument("--expected-profile", default=EXPECTED_PROFILE)
    parser.add_argument("--expected-resolved-profile", default=EXPECTED_RESOLVED_PROFILE)
    parser.add_argument("--expected-markets", default=",".join(EXPECTED_MARKETS))
    parser.add_argument("--expected-years", default=",".join(str(year) for year in EXPECTED_YEARS))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    split_plan_path = resolve_path(repo_root, args.split_plan)
    split_acceptance_path = resolve_path(repo_root, args.split_acceptance)
    feature_root = resolve_path(repo_root, args.feature_root)
    feature_manifest_path = resolve_path(repo_root, args.feature_manifest)
    report_root = resolve_path(repo_root, args.report_root)
    json_out = resolve_path(repo_root, args.json_out or report_root / "wfa_runner_preflight_report.json")
    md_out = resolve_path(repo_root, args.md_out or report_root / "wfa_runner_preflight_report.md")
    feature_set_path = resolve_path(
        repo_root,
        args.feature_set_out or report_root / FEATURE_SET_FILENAME,
    )

    features = read_json_list(feature_root / "feature_cols.json")
    feature_set = feature_set_payload(
        repo_root=repo_root,
        feature_root=feature_root,
        feature_manifest_path=feature_manifest_path,
        split_plan_path=split_plan_path,
        split_acceptance_path=split_acceptance_path,
        features=features,
    )
    write_feature_set_manifest(feature_set_path, feature_set)

    report = build_report(
        repo_root=repo_root,
        split_plan_path=split_plan_path,
        split_acceptance_path=split_acceptance_path,
        feature_root=feature_root,
        feature_manifest_path=feature_manifest_path,
        feature_set_path=feature_set_path,
        json_out=json_out,
        md_out=md_out,
        profile_config_path=resolve_path(repo_root, args.profile_config),
        models_config_path=resolve_path(repo_root, args.models_config),
        predictions_root=resolve_path(repo_root, args.predictions_root),
        expected_profile=str(args.expected_profile),
        expected_resolved_profile=str(args.expected_resolved_profile),
        expected_markets=csv_strings(args.expected_markets),
        expected_years=csv_ints(args.expected_years),
    )
    json_path, md_path = write_report(report, json_out, md_out)
    print(
        f"{STAGE} status={report['status']} failures={len(report['failures'])} "
        f"features={report['summary']['feature_count']} folds={report['summary']['fold_count']} "
        f"models={report['summary']['model_count']} predictions={report['summary']['prediction_file_count']} "
        f"commands_executed={report['summary']['commands_executed']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)} "
        f"feature_set={rel(feature_set_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
