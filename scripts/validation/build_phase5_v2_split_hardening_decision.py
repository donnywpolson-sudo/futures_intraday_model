#!/usr/bin/env python3
"""Report-only Phase 5 split-hardening decision for active v2 Tier 1 core."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scripts.validation.model_registry import resolve_purge_bars, validate_purge_policy


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "phase5_v2_split_hardening_decision"
PASS_STATUS = "PASS_SPLIT_HARDENING_DESIGN_FEASIBLE_NO_SPLIT_BUILD"
FAIL_STATUS = "FAIL_SPLIT_HARDENING_DECISION_BLOCKED_NO_SPLIT_BUILD"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_FEATURE_COUNT = 114
EXPECTED_FOLD_COUNT = 48
EXPECTED_RESOLVED_PURGE_BARS = 61
EXPECTED_TARGET_HORIZON_BARS = 30
EXPECTED_TREND_HORIZON_BARS = 60
EXPECTED_LABEL_SEMANTICS_ID = (
    "phase3_labels_v2_next_1m_open_30m_primary_60m_confirm_apex_aware"
)

DEFAULT_SPLIT_PLAN = Path("reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.json")
DEFAULT_SPLIT_ACCEPTANCE = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan_acceptance_report.json"
)
DEFAULT_CONTAMINATION_AUDIT = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_contamination_audit/"
    "wfa_split_contamination_audit.json"
)
DEFAULT_FEATURE_MANIFEST = Path(
    "reports/features_baseline/"
    "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "baseline_feature_manifest.json"
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
DEFAULT_MODELS_CONFIG = Path("configs/models.yaml")
DEFAULT_REPORTS_ROOT = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_split_hardening_decision"
)

REPORT_JSON = "split_hardening_decision.json"
REPORT_MD = "split_hardening_decision.md"


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


def read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"{path.as_posix()}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"{path.as_posix()}: expected JSON object"
    return payload, None


def read_yaml_object(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {}, f"{path.as_posix()}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"{path.as_posix()}: expected YAML object"
    return payload, None


def parse_csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def int_field(mapping: Mapping[str, Any], key: str, *, default: int = -1) -> int:
    value = mapping.get(key, default)
    if value is None:
        return default
    return int(value)


def expected_pairs(markets: Sequence[str], years: Sequence[int]) -> list[tuple[str, int]]:
    return [(market, int(year)) for market in markets for year in years]


def record_check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def validate_scope(markets: Sequence[str], years: Sequence[int]) -> dict[str, Any]:
    observed_markets = sorted(str(market) for market in markets)
    observed_years = sorted(int(year) for year in years)
    expected_markets = sorted(EXPECTED_MARKETS)
    expected_years = sorted(EXPECTED_YEARS)
    failures: list[str] = []
    if observed_markets != expected_markets:
        failures.append(f"markets must be {expected_markets}, got {observed_markets}")
    if observed_years != expected_years:
        failures.append(f"years must be {expected_years}, got {observed_years}")
    if len(expected_pairs(markets, years)) != 8:
        failures.append("scope must resolve to exactly 8 market-years")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "markets": observed_markets,
        "years": observed_years,
        "market_year_count": len(expected_pairs(markets, years)),
    }


def validate_split_plan(
    split_plan: Mapping[str, Any],
    *,
    markets: Sequence[str],
    years: Sequence[int],
) -> dict[str, Any]:
    failures: list[str] = []
    observed_markets = sorted(str(item) for item in split_plan.get("markets", []))
    observed_years = sorted(int(item) for item in split_plan.get("years", []))
    if split_plan.get("profile") != "tier_1":
        failures.append(f"profile must be tier_1, got {split_plan.get('profile')}")
    if split_plan.get("resolved_profile") != "tier_1_research":
        failures.append(
            f"resolved_profile must be tier_1_research, got {split_plan.get('resolved_profile')}"
        )
    if split_plan.get("input_root") != "data/feature_matrices":
        failures.append(f"input_root must be data/feature_matrices, got {split_plan.get('input_root')}")
    if observed_markets != sorted(markets):
        failures.append(f"split markets mismatch: {observed_markets}")
    if observed_years != sorted(int(year) for year in years):
        failures.append(f"split years mismatch: {observed_years}")
    if int(split_plan.get("fold_count") or -1) != EXPECTED_FOLD_COUNT:
        failures.append(f"fold_count must be {EXPECTED_FOLD_COUNT}")
    if int(split_plan.get("failure_count") or 0) != 0:
        failures.append("split_plan failure_count must be zero")
    purge_policy = split_plan.get("purge_policy")
    purge_policy = purge_policy if isinstance(purge_policy, Mapping) else {}
    for key in ("purge_bars", "resolved_purge_bars", "embargo_bars"):
        if int(purge_policy.get(key) or -1) < EXPECTED_RESOLVED_PURGE_BARS:
            failures.append(f"split purge_policy {key} must be at least {EXPECTED_RESOLVED_PURGE_BARS}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "fold_count": split_plan.get("fold_count"),
        "failure_count": split_plan.get("failure_count"),
        "purge_policy": dict(purge_policy),
    }


def validate_split_acceptance(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    summary = acceptance.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    if acceptance.get("status") != "PASS_PHASE5_SPLIT_PLAN_ACCEPTED_REPORT_ONLY":
        failures.append(f"acceptance status mismatch: {acceptance.get('status')}")
    if int_field(summary, "failure_count") != 0:
        failures.append("acceptance failure_count must be zero")
    if int_field(summary, "warning_count") != 0:
        failures.append("acceptance warning_count must be zero")
    if int_field(summary, "fold_count") != EXPECTED_FOLD_COUNT:
        failures.append(f"acceptance fold_count must be {EXPECTED_FOLD_COUNT}")
    if int_field(summary, "prediction_file_count") != 0:
        failures.append("acceptance prediction_file_count must be zero")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": dict(summary),
    }


def validate_contamination_audit(contamination: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings = contamination.get("warnings")
    warnings = warnings if isinstance(warnings, list) else []
    joined_warnings = "\n".join(str(item) for item in warnings)
    summary = contamination.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    if contamination.get("status") != "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD":
        failures.append(f"contamination status mismatch: {contamination.get('status')}")
    if int_field(summary, "failure_count") != 0:
        failures.append("contamination failure_count must be zero")
    if summary.get("valid_for_independent_holdout_claims") is not False:
        failures.append("current split must not be classified as independent holdout")
    if summary.get("valid_for_same_fold_rolling_retraining_research_evidence") is not True:
        failures.append("current split must remain valid for same-fold rolling research evidence")
    if summary.get("classification") != "same_fold_rolling_retraining_research_only":
        failures.append(f"unexpected contamination classification: {summary.get('classification')}")
    for expected_warning in (
        "WARN_EXPECTED_ROLLING_RETRAINING_REUSE",
        "WARN_ROLLING_RETRAINING_PRIOR_EMBARGO_REUSE",
        "WARN_NO_INNER_VALIDATION_WINDOW",
    ):
        if expected_warning not in joined_warnings:
            failures.append(f"missing expected warning: {expected_warning}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": dict(summary),
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def validate_feature_manifest(feature_manifest: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    outputs = feature_manifest.get("outputs")
    outputs = outputs if isinstance(outputs, list) else []
    if feature_manifest.get("status") != "PASS":
        failures.append(f"feature manifest status must be PASS, got {feature_manifest.get('status')}")
    if int(feature_manifest.get("failure_count") or 0) != 0:
        failures.append("feature manifest failure_count must be zero")
    if int(feature_manifest.get("warning_count") or 0) != 0:
        failures.append("feature manifest warning_count must be zero")
    if feature_manifest.get("profile") != "tier_1":
        failures.append(f"feature manifest profile mismatch: {feature_manifest.get('profile')}")
    if feature_manifest.get("resolved_profile") != "tier_1_research":
        failures.append(
            f"feature manifest resolved_profile mismatch: {feature_manifest.get('resolved_profile')}"
        )
    if feature_manifest.get("output_root") != "data/feature_matrices":
        failures.append(f"feature manifest output_root mismatch: {feature_manifest.get('output_root')}")
    if int(feature_manifest.get("feature_count") or -1) != EXPECTED_FEATURE_COUNT:
        failures.append(f"feature_count must be {EXPECTED_FEATURE_COUNT}")
    if len(outputs) != 8:
        failures.append(f"feature manifest must contain 8 outputs, got {len(outputs)}")
    output_failures = [
        f"{item.get('market')}:{item.get('year')}"
        for item in outputs
        if isinstance(item, Mapping) and item.get("status") != "PASS"
    ]
    if output_failures:
        failures.append(f"feature manifest output failures: {output_failures}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "feature_count": feature_manifest.get("feature_count"),
        "output_count": len(outputs),
    }


def validate_hash_evidence(
    *,
    split_plan: Mapping[str, Any],
    feature_hash_report: Mapping[str, Any],
    label_hash_report: Mapping[str, Any],
    markets: Sequence[str],
    years: Sequence[int],
) -> dict[str, Any]:
    failures: list[str] = []
    expected_feature_paths = [f"data/feature_matrices/{market}/{year}.parquet" for market, year in expected_pairs(markets, years)]
    expected_label_paths = [f"data/labeled/{market}/{year}.parquet" for market, year in expected_pairs(markets, years)]

    feature_records = feature_hash_report.get("records")
    feature_records = feature_records if isinstance(feature_records, list) else []
    feature_paths = sorted(str(item.get("path")) for item in feature_records if isinstance(item, Mapping))
    if feature_hash_report.get("active_root") != "data/feature_matrices":
        failures.append("feature hash report active_root mismatch")
    if feature_hash_report.get("failures") not in ([], None):
        failures.append("feature hash report contains failures")
    feature_market_year_paths = sorted(path for path in feature_paths if path.endswith(".parquet"))
    supplemental_feature_paths = sorted(path for path in feature_paths if not path.endswith(".parquet"))
    if sorted(expected_feature_paths) != feature_market_year_paths:
        failures.append(f"feature market-year hash paths mismatch: {feature_market_year_paths}")
    if any(not item.get("active_matches_staged") for item in feature_records if isinstance(item, Mapping)):
        failures.append("feature hash report has active_matches_staged != true")

    label_records = label_hash_report.get("records")
    label_records = label_records if isinstance(label_records, list) else []
    label_paths = sorted(str(item.get("active_path")) for item in label_records if isinstance(item, Mapping))
    if label_hash_report.get("active_root") != "data/labeled":
        failures.append("label hash report active_root mismatch")
    if label_hash_report.get("failures") not in ([], None):
        failures.append("label hash report contains failures")
    if label_hash_report.get("label_semantics_id") != EXPECTED_LABEL_SEMANTICS_ID:
        failures.append("label semantics id mismatch")
    if sorted(expected_label_paths) != label_paths:
        failures.append(f"label hash paths mismatch: {label_paths}")
    if any(not item.get("active_matches_staged") for item in label_records if isinstance(item, Mapping)):
        failures.append("label hash report has active_matches_staged != true")

    split_input_hashes = split_plan.get("input_file_hashes")
    split_input_hashes = split_input_hashes if isinstance(split_input_hashes, Mapping) else {}
    feature_tree_hashes = feature_hash_report.get("active_tree_hashes_after")
    feature_tree_hashes = feature_tree_hashes if isinstance(feature_tree_hashes, Mapping) else {}
    hash_mismatches = [
        path
        for path in expected_feature_paths
        if split_input_hashes.get(path) != feature_tree_hashes.get(path)
    ]
    if hash_mismatches:
        failures.append(f"split input hashes differ from active feature hashes: {hash_mismatches}")

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "feature_record_count": len(feature_records),
        "feature_market_year_record_count": len(feature_market_year_paths),
        "supplemental_feature_record_count": len(supplemental_feature_paths),
        "label_record_count": len(label_records),
        "split_feature_hash_mismatch_count": len(hash_mismatches),
    }


def validate_models_config(models_config: Mapping[str, Any]) -> dict[str, Any]:
    failures = validate_purge_policy(dict(models_config))
    purge = models_config.get("purge")
    purge = purge if isinstance(purge, Mapping) else {}
    try:
        resolved = resolve_purge_bars(dict(purge))
    except Exception as exc:
        resolved = None
        failures.append(f"cannot resolve purge bars: {exc}")
    if int(purge.get("target_horizon_bars") or -1) != EXPECTED_TARGET_HORIZON_BARS:
        failures.append(f"target_horizon_bars must be {EXPECTED_TARGET_HORIZON_BARS}")
    if int(purge.get("trend_horizon_bars") or -1) != EXPECTED_TREND_HORIZON_BARS:
        failures.append(f"trend_horizon_bars must be {EXPECTED_TREND_HORIZON_BARS}")
    if resolved != EXPECTED_RESOLVED_PURGE_BARS:
        failures.append(f"resolved purge must be {EXPECTED_RESOLVED_PURGE_BARS}, got {resolved}")
    policy = models_config.get("policy")
    policy = policy if isinstance(policy, Mapping) else {}
    if policy.get("random_splits_allowed") is not False:
        failures.append("random_splits_allowed must be false")
    if policy.get("final_holdout_tuning_allowed") is not False:
        failures.append("final_holdout_tuning_allowed must be false")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "resolved_purge_bars": resolved,
        "purge": dict(purge),
    }


def validate_output_scope(*, reports_root: Path, split_plan_path: Path) -> dict[str, Any]:
    failures: list[str] = []
    overlaps_accepted_split_root = reports_root.resolve() == split_plan_path.parent.resolve()
    if overlaps_accepted_split_root:
        failures.append("reports_root must not be the accepted Phase 5 split root")
    existing_split_outputs = (
        sorted(path.name for path in reports_root.glob("split_plan.*")) if reports_root.exists() else []
    )
    if existing_split_outputs:
        failures.append(f"reports_root already contains split-plan outputs: {existing_split_outputs}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "reports_root": reports_root.as_posix(),
        "overlaps_accepted_split_root": overlaps_accepted_split_root,
        "existing_split_outputs": existing_split_outputs,
    }


def hardened_design_recommendation() -> dict[str, Any]:
    return {
        "type": "fixed_train_validation_test_hardened_rebuild_path",
        "scope": {
            "markets": list(EXPECTED_MARKETS),
            "years": list(EXPECTED_YEARS),
            "market_year_count": 8,
        },
        "required_controls": [
            "fixed train/validation/test separation",
            "inner validation window present before test scoring",
            "no later-fold training on prior OOS rows",
            "no later-fold training on prior embargo rows",
            "61-bar purge between train, validation, and test boundaries",
            "61-bar embargo after validation/test blocks",
            "no 2025/2026 rows",
            "no final-holdout rows",
        ],
        "non_approval": "This recommendation is evidence only and does not authorize split generation.",
    }


def build_report(
    *,
    repo_root: Path,
    split_plan_path: Path,
    split_acceptance_path: Path,
    contamination_audit_path: Path,
    feature_manifest_path: Path,
    feature_placement_hashes_path: Path,
    label_placement_hashes_path: Path,
    models_config_path: Path,
    reports_root: Path,
    markets: Sequence[str],
    years: Sequence[int],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    scope = validate_scope(markets, years)
    record_check(
        checks,
        name="exact_active_v2_tier1_core_scope",
        passed=scope["status"] == "PASS",
        observed={key: scope[key] for key in ("markets", "years", "market_year_count")},
        expected={
            "markets": sorted(EXPECTED_MARKETS),
            "years": sorted(EXPECTED_YEARS),
            "market_year_count": 8,
        },
        detail="The decision gate may inspect only the active v2 Tier 1 core scope.",
    )

    split_plan, split_plan_error = read_json_object(split_plan_path)
    acceptance, acceptance_error = read_json_object(split_acceptance_path)
    contamination, contamination_error = read_json_object(contamination_audit_path)
    feature_manifest, feature_manifest_error = read_json_object(feature_manifest_path)
    feature_hashes, feature_hash_error = read_json_object(feature_placement_hashes_path)
    label_hashes, label_hash_error = read_json_object(label_placement_hashes_path)
    models_config, models_config_error = read_yaml_object(models_config_path)
    read_failures = [
        error
        for error in (
            split_plan_error,
            acceptance_error,
            contamination_error,
            feature_manifest_error,
            feature_hash_error,
            label_hash_error,
            models_config_error,
        )
        if error
    ]
    record_check(
        checks,
        name="required_evidence_files_readable",
        passed=not read_failures,
        observed=read_failures,
        expected=[],
        detail="All accepted split, contamination, active placement, and models evidence must be readable.",
    )

    split_plan_check = validate_split_plan(split_plan, markets=markets, years=years)
    record_check(
        checks,
        name="accepted_split_plan_scope_and_purge",
        passed=split_plan_check["status"] == "PASS",
        observed=split_plan_check,
        expected="PASS split plan with exact scope, 48 folds, zero failures, and 61-bar purge/embargo",
        detail="The current split can only be assessed if its accepted evidence is intact.",
    )

    split_acceptance_check = validate_split_acceptance(acceptance)
    record_check(
        checks,
        name="split_acceptance_report_pass_no_predictions",
        passed=split_acceptance_check["status"] == "PASS",
        observed=split_acceptance_check,
        expected="PASS_PHASE5_SPLIT_PLAN_ACCEPTED_REPORT_ONLY with zero prediction files",
        detail="The decision gate must not start from stale or prediction-bearing split evidence.",
    )

    contamination_check = validate_contamination_audit(contamination)
    record_check(
        checks,
        name="contamination_audit_research_only_classification",
        passed=contamination_check["status"] == "PASS",
        observed=contamination_check,
        expected="PASS contamination audit with independent holdout disallowed and reuse warnings present",
        detail="The current split must remain classified as research-only before any hardening decision.",
    )

    feature_manifest_check = validate_feature_manifest(feature_manifest)
    record_check(
        checks,
        name="active_feature_manifest_pass_scope",
        passed=feature_manifest_check["status"] == "PASS",
        observed=feature_manifest_check,
        expected="PASS feature manifest for tier_1/tier_1_research, data/feature_matrices, 8 outputs, 114 features",
        detail="The hardening decision is only valid for the active v2 feature placement evidence.",
    )

    hash_check = validate_hash_evidence(
        split_plan=split_plan,
        feature_hash_report=feature_hashes,
        label_hash_report=label_hashes,
        markets=markets,
        years=years,
    )
    record_check(
        checks,
        name="active_label_feature_hash_evidence_present",
        passed=hash_check["status"] == "PASS",
        observed=hash_check,
        expected="8 active label records, 8 active feature records, and split input hashes matching active features",
        detail="The decision gate must prove it is looking at the active v2 label/feature files.",
    )

    models_check = validate_models_config(models_config)
    record_check(
        checks,
        name="models_purge_policy_covers_30m60m",
        passed=models_check["status"] == "PASS",
        observed=models_check,
        expected="30m primary, 60m robustness, resolved 61-bar purge, random/final-holdout tuning disabled",
        detail="Split hardening must preserve the v2 30m/60m purge contract.",
    )

    output_scope_check = validate_output_scope(reports_root=reports_root, split_plan_path=split_plan_path)
    record_check(
        checks,
        name="report_only_output_scope_no_split_plan_outputs",
        passed=output_scope_check["status"] == "PASS",
        observed=output_scope_check,
        expected="reports_root separate from accepted Phase 5 root and no split_plan.* files present",
        detail="This command may write only split_hardening_decision JSON/MD.",
    )

    failures = [
        f"{check['name']}: {check['observed']}"
        for check in checks
        if check["status"] == "FAIL"
    ]
    feasible = not failures
    status = PASS_STATUS if feasible else FAIL_STATUS
    report = {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "markets": list(markets),
            "years": [int(year) for year in years],
            "market_year_count": len(expected_pairs(markets, years)),
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "current_split_allowed_use": "same_fold_rolling_retraining_research_only",
            "current_split_independent_holdout_allowed": False,
            "prediction_materialization_allowed": False,
            "phase8_refresh_allowed": False,
            "hardened_split_generation_allowed": False,
            "hardened_split_design_feasible": feasible,
            "split_plan_generated": False,
            "commands_executed": 0,
        },
        "checks": checks,
        "failures": failures,
        "hardened_design_recommendation": hardened_design_recommendation() if feasible else None,
        "input_evidence": {
            "split_plan": rel(split_plan_path, repo_root),
            "split_acceptance": rel(split_acceptance_path, repo_root),
            "contamination_audit": rel(contamination_audit_path, repo_root),
            "feature_manifest": rel(feature_manifest_path, repo_root),
            "feature_placement_hashes": rel(feature_placement_hashes_path, repo_root),
            "label_placement_hashes": rel(label_placement_hashes_path, repo_root),
            "models_config": rel(models_config_path, repo_root),
        },
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "non_approval": {
            "hardened_split_generation": False,
            "prediction_materialization": False,
            "phase8_refresh": False,
            "promotion_or_artifact_freeze": False,
            "final_holdout": False,
            "paper_or_live": False,
            "provider_or_network": False,
            "data_mutation": False,
            "label_or_feature_rebuild": False,
            "cleanup": False,
            "git_staging_commit_push": False,
            "prop_account_reports": False,
        },
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Phase 5 v2 Split-Hardening Decision",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Current split allowed use: `{summary['current_split_allowed_use']}`",
        f"- Independent holdout allowed: `{summary['current_split_independent_holdout_allowed']}`",
        f"- Hardened split design feasible: `{summary['hardened_split_design_feasible']}`",
        f"- Hardened split generation allowed: `{summary['hardened_split_generation_allowed']}`",
        f"- Split plan generated: `{summary['split_plan_generated']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['name']}` | `{check['status']}` |")
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(["", "## Hardened Design Recommendation", ""])
    recommendation = report.get("hardened_design_recommendation")
    if recommendation:
        lines.append("- Feasible as a separately approved design/build path only.")
        for control in recommendation["required_controls"]:
            lines.append(f"- {control}")
    else:
        lines.append("- Not exposed because the decision gate failed closed.")
    lines.extend(
        [
            "",
            "## Non-Approval",
            "",
            "- This report does not build a hardened split, create split plans, materialize predictions, refresh Phase 8, approve promotion, touch final holdout, write prop-account reports, run provider/download commands, mutate data, clean up files, stage, commit, or push.",
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
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--split-acceptance", default=DEFAULT_SPLIT_ACCEPTANCE.as_posix())
    parser.add_argument("--contamination-audit", default=DEFAULT_CONTAMINATION_AUDIT.as_posix())
    parser.add_argument("--feature-manifest", default=DEFAULT_FEATURE_MANIFEST.as_posix())
    parser.add_argument("--feature-placement-hashes", default=DEFAULT_FEATURE_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--label-placement-hashes", default=DEFAULT_LABEL_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--markets", default=",".join(EXPECTED_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in EXPECTED_YEARS))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(
        repo_root=repo_root,
        split_plan_path=resolve_path(repo_root, args.split_plan),
        split_acceptance_path=resolve_path(repo_root, args.split_acceptance),
        contamination_audit_path=resolve_path(repo_root, args.contamination_audit),
        feature_manifest_path=resolve_path(repo_root, args.feature_manifest),
        feature_placement_hashes_path=resolve_path(repo_root, args.feature_placement_hashes),
        label_placement_hashes_path=resolve_path(repo_root, args.label_placement_hashes),
        models_config_path=resolve_path(repo_root, args.models_config),
        reports_root=reports_root,
        markets=parse_csv_strings(args.markets),
        years=parse_csv_ints(args.years),
    )
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"hardened_split_design_feasible={report['summary']['hardened_split_design_feasible']} "
        f"split_plan_generated={report['summary']['split_plan_generated']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
