#!/usr/bin/env python3
"""Report-only active Tier 1 Phase 5 WFA split-readiness review."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "tier1_core_phase5_wfa_preflight"
EXPECTED_MARKETS = ["ES", "CL", "ZN", "6E"]
EXPECTED_YEARS = [2023, 2024]
EXPECTED_MARKET_YEAR_COUNT = len(EXPECTED_MARKETS) * len(EXPECTED_YEARS)
EXPECTED_FEATURE_COUNT = 114
REQUIRED_WFA_COLUMNS = [
    "ts",
    "market",
    "year",
    "training_row_valid",
    "target_valid",
    "feature_input_valid",
]
DEFAULT_REPORT_ROOT = (
    REPO_ROOT / "reports/data_audit/current_state/tier1_core_phase5_wfa_preflight_20260706"
)
DEFAULT_FEATURE_ROOT = REPO_ROOT / "data/feature_matrices"
DEFAULT_PREDICTIONS_ROOT = REPO_ROOT / "data/predictions"
DEFAULT_PLACEMENT_REPORT = (
    REPO_ROOT
    / "reports/data_audit/current_state/"
    "tier1_core_phase4_self_reference_cleanup_active_placement_20260706/"
    "active_placement_report.json"
)
DEFAULT_FEATURE_MANIFEST = (
    REPO_ROOT
    / "reports/data_audit/current_state/"
    "tier1_core_phase4_self_reference_cleanup_active_placement_20260706/"
    "active_feature_manifest.json"
)
DEFAULT_LABEL_MANIFEST = (
    REPO_ROOT
    / "reports/data_audit/current_state/tier1_core_phase34_active_placement_20260706/"
    "active_label_manifest.json"
)
DEFAULT_PROFILE_CONFIG = REPO_ROOT / "configs/alpha_tiered.yaml"
DEFAULT_MODELS_CONFIG = REPO_ROOT / "configs/models.yaml"

NO_MUTATION_TEXT = (
    "Report-only Phase 5 WFA preflight. No split_plan.csv/json, WFA/model training, "
    "prediction generation, provider calls, data replacement, cleanup, staging, commit, "
    "push, paper, or live work is approved or performed."
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


def read_json_list(path: Path) -> list[Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.as_posix()} must contain a JSON list")
    return payload


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.as_posix()} must contain a YAML mapping")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def status_from_failures(failures: list[str], warnings: list[str]) -> str:
    if failures:
        return "FAIL_PHASE5_WFA_PREFLIGHT"
    if warnings:
        return "WARN_PHASE5_WFA_PREFLIGHT_READY_WITH_WARNINGS"
    return "PASS_PHASE5_WFA_PREFLIGHT_READY"


def _as_set(values: Iterable[Any]) -> set[Any]:
    return set(values)


def validate_scope(scope: dict[str, Any], failures: list[str]) -> None:
    if _as_set(scope.get("markets", [])) != set(EXPECTED_MARKETS):
        failures.append(f"placement scope markets mismatch: {scope.get('markets')}")
    if _as_set(scope.get("years", [])) != set(EXPECTED_YEARS):
        failures.append(f"placement scope years mismatch: {scope.get('years')}")
    if int(scope.get("market_year_count") or 0) != EXPECTED_MARKET_YEAR_COUNT:
        failures.append(f"placement scope market_year_count mismatch: {scope.get('market_year_count')}")
    if scope.get("profile_alias") != "tier_1_core":
        failures.append(f"placement scope profile_alias mismatch: {scope.get('profile_alias')}")
    if scope.get("resolved_profile") != "tier_1_research":
        failures.append(f"placement scope resolved_profile mismatch: {scope.get('resolved_profile')}")


def sidecar_paths(feature_root: Path) -> list[Path]:
    return [
        feature_root / "feature_cols.json",
        feature_root / "target_cols.json",
        feature_root / "metadata_cols.json",
        feature_root / "excluded_cols.json",
    ]


def expected_feature_paths(feature_root: Path) -> list[Path]:
    return [feature_root / market / f"{year}.parquet" for market in EXPECTED_MARKETS for year in EXPECTED_YEARS]


def validate_placement_hashes(
    *,
    repo_root: Path,
    placement_report: dict[str, Any],
    feature_root: Path,
    failures: list[str],
) -> list[dict[str, Any]]:
    placement_rows = placement_report.get("placement_rows")
    if not isinstance(placement_rows, list):
        failures.append("placement report has no placement_rows list")
        return []

    expected_rels = {rel(path, repo_root) for path in expected_feature_paths(feature_root) + sidecar_paths(feature_root)}
    placement_by_dest = {
        str(row.get("destination")): row for row in placement_rows if isinstance(row, dict) and row.get("destination")
    }
    missing = sorted(expected_rels - set(placement_by_dest))
    extra = sorted(set(placement_by_dest) - expected_rels)
    if missing:
        failures.append("placement rows missing active destinations: " + ",".join(missing))
    if extra:
        failures.append("placement rows include unexpected destinations: " + ",".join(extra))

    rows: list[dict[str, Any]] = []
    for expected_rel in sorted(expected_rels):
        destination = repo_root / expected_rel
        row = placement_by_dest.get(expected_rel, {})
        expected_sha = str(row.get("destination_sha256") or "")
        status = str(row.get("status") or "")
        exists = destination.is_file()
        actual_sha = sha256_file(destination) if exists else None
        hash_match = bool(expected_sha and actual_sha == expected_sha)
        if status != "PLACED_HASH_MATCH":
            failures.append(f"{expected_rel} placement status is {status!r}")
        if not exists:
            failures.append(f"{expected_rel} is missing from active feature root")
        elif not hash_match:
            failures.append(f"{expected_rel} sha256 mismatch")
        rows.append(
            {
                "path": expected_rel,
                "kind": row.get("kind"),
                "status": status,
                "exists": exists,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "hash_match": hash_match,
            }
        )
    return rows


def validate_feature_manifest(
    feature_manifest: dict[str, Any],
    feature_root: Path,
    repo_root: Path,
    failures: list[str],
) -> dict[str, Any]:
    feature_audit_gate = feature_manifest.get("feature_audit_gate")
    if not isinstance(feature_audit_gate, dict):
        feature_audit_gate = {}
    forbidden_failures = feature_manifest.get("forbidden_feature_leakage_failures")
    if not isinstance(forbidden_failures, list):
        forbidden_failures = []
    feature_cols = read_json_list(feature_root / "feature_cols.json")
    target_cols = read_json_list(feature_root / "target_cols.json")
    metadata_cols = read_json_list(feature_root / "metadata_cols.json")

    checks = {
        "status": feature_manifest.get("status"),
        "failure_count": feature_manifest.get("failure_count"),
        "warning_count": feature_manifest.get("warning_count"),
        "feature_count": feature_manifest.get("feature_count"),
        "feature_audit_gate_status": feature_audit_gate.get("status"),
        "feature_audit_gate_failure_count": feature_audit_gate.get("failure_count"),
        "forbidden_feature_leakage_failure_count": len(forbidden_failures),
        "output_root": feature_manifest.get("output_root"),
        "markets": feature_manifest.get("markets"),
        "years": feature_manifest.get("years"),
        "feature_cols_count": len(feature_cols),
        "target_cols_count": len(target_cols),
        "metadata_cols": metadata_cols,
    }

    if checks["status"] != "PASS":
        failures.append(f"active feature manifest status is {checks['status']!r}")
    if int(checks["failure_count"] or 0) != 0:
        failures.append(f"active feature manifest failure_count is {checks['failure_count']}")
    if int(checks["feature_count"] or 0) != EXPECTED_FEATURE_COUNT:
        failures.append(f"active feature manifest feature_count is {checks['feature_count']}")
    if checks["feature_audit_gate_status"] != "PASS":
        failures.append(f"active feature audit gate status is {checks['feature_audit_gate_status']!r}")
    if int(checks["feature_audit_gate_failure_count"] or 0) != 0:
        failures.append("active feature audit gate has failures")
    if forbidden_failures:
        failures.append("active feature manifest has forbidden leakage failures")
    if resolve_path(repo_root, str(checks["output_root"])) != feature_root:
        failures.append(f"active feature manifest output_root mismatch: {checks['output_root']}")
    if _as_set(checks["markets"] or []) != set(sorted(EXPECTED_MARKETS)):
        failures.append(f"active feature manifest markets mismatch: {checks['markets']}")
    if _as_set(checks["years"] or []) != set(EXPECTED_YEARS):
        failures.append(f"active feature manifest years mismatch: {checks['years']}")
    if len(feature_cols) != EXPECTED_FEATURE_COUNT:
        failures.append(f"active feature sidecar feature count is {len(feature_cols)}")
    if any(str(col).startswith("target_") for col in feature_cols):
        failures.append("active feature columns include target_ prefixed columns")
    missing_metadata = sorted(set(REQUIRED_WFA_COLUMNS) - set(metadata_cols))
    if missing_metadata:
        failures.append("active feature metadata sidecar missing WFA columns: " + ",".join(missing_metadata))

    return checks


def validate_label_manifest(label_manifest: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    input_selection = label_manifest.get("input_selection")
    if not isinstance(input_selection, dict):
        input_selection = {}
    summary = label_manifest.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    causal_gate = label_manifest.get("causal_base_manifest_gate")
    if not isinstance(causal_gate, dict):
        causal_gate = {}

    checks = {
        "status": label_manifest.get("status"),
        "selected_input_count": input_selection.get("selected_input_count"),
        "markets": input_selection.get("selected_markets") or label_manifest.get("markets"),
        "years": input_selection.get("selected_years") or label_manifest.get("years"),
        "file_count": summary.get("file_count"),
        "fail_count": summary.get("fail_count"),
        "warn_count": summary.get("warn_count"),
        "target_valid_rows": summary.get("target_valid_rows"),
        "causal_base_manifest_gate_status": causal_gate.get("status"),
    }
    if checks["status"] != "PASS":
        failures.append(f"active label manifest status is {checks['status']!r}")
    if int(checks["selected_input_count"] or 0) != EXPECTED_MARKET_YEAR_COUNT:
        failures.append(f"active label manifest selected_input_count is {checks['selected_input_count']}")
    if int(checks["file_count"] or 0) != EXPECTED_MARKET_YEAR_COUNT:
        failures.append(f"active label manifest file_count is {checks['file_count']}")
    if int(checks["fail_count"] or 0) != 0:
        failures.append("active label manifest has failures")
    if checks["causal_base_manifest_gate_status"] != "PASS":
        failures.append(f"active label causal gate status is {checks['causal_base_manifest_gate_status']!r}")
    if _as_set(checks["markets"] or []) != set(sorted(EXPECTED_MARKETS)):
        failures.append(f"active label manifest markets mismatch: {checks['markets']}")
    if _as_set(checks["years"] or []) != set(EXPECTED_YEARS):
        failures.append(f"active label manifest years mismatch: {checks['years']}")
    return checks


def validate_profile_config(profile_config: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    aliases = profile_config.get("aliases")
    profiles = profile_config.get("profiles")
    defaults = profile_config.get("profile_defaults")
    if not isinstance(aliases, dict) or not isinstance(profiles, dict) or not isinstance(defaults, dict):
        failures.append("profile config is missing aliases/profiles/profile_defaults mappings")
        return {}
    resolved = aliases.get("tier_1_core")
    profile = profiles.get(resolved)
    if not isinstance(profile, dict):
        failures.append("tier_1_core alias does not resolve to a profile mapping")
        return {"alias": "tier_1_core", "resolved_profile": resolved}
    settings_name = profile.get("settings_profile")
    settings = defaults.get(settings_name)
    if not isinstance(settings, dict):
        failures.append(f"tier_1_core settings_profile missing: {settings_name}")
        settings = {}
    checks = {
        "alias": "tier_1_core",
        "resolved_profile": resolved,
        "intent": profile.get("intent"),
        "requirement_set": profile.get("requirement_set"),
        "settings_profile": settings_name,
        "markets": profile.get("markets"),
        "years": profile.get("years"),
        "train_days": settings.get("train_days"),
        "test_days": settings.get("test_days"),
        "step_days": settings.get("step_days"),
        "forbid_research_use": bool(profile.get("forbid_research_use", False)),
    }
    if resolved != "tier_1_research":
        failures.append(f"tier_1_core resolved profile mismatch: {resolved}")
    if _as_set(checks["markets"] or []) != set(EXPECTED_MARKETS):
        failures.append(f"tier_1_core profile markets mismatch: {checks['markets']}")
    if _as_set(checks["years"] or []) != set(EXPECTED_YEARS):
        failures.append(f"tier_1_core profile years mismatch: {checks['years']}")
    if checks["train_days"] != 365 or checks["test_days"] != 30 or checks["step_days"] != 30:
        failures.append("tier_1_core WFA window settings are not 365/30/30")
    if checks["forbid_research_use"]:
        failures.append("tier_1_core research profile unexpectedly forbids research use")
    return checks


def validate_models_config(models_config: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    policy = models_config.get("policy")
    purge = models_config.get("purge")
    reports = models_config.get("model_selection_reports")
    if not isinstance(policy, dict):
        policy = {}
        failures.append("models config policy mapping missing")
    if not isinstance(purge, dict):
        purge = {}
        failures.append("models config purge mapping missing")
    if not isinstance(reports, dict):
        reports = {}
    checks = {
        "random_splits_allowed": policy.get("random_splits_allowed"),
        "final_holdout_tuning_allowed": policy.get("final_holdout_tuning_allowed"),
        "purge_bars": purge.get("purge_bars"),
        "resolved_purge_bars": purge.get("resolved_purge_bars"),
        "entry_lag_bars": purge.get("entry_lag_bars"),
        "target_horizon_bars": purge.get("target_horizon_bars"),
        "final_holdout_excluded_from_selection": reports.get("final_holdout_excluded_from_selection"),
    }
    if checks["random_splits_allowed"] is not False:
        failures.append("models config allows random splits or omits the guard")
    if checks["final_holdout_tuning_allowed"] is not False:
        failures.append("models config allows final holdout tuning or omits the guard")
    if checks["purge_bars"] != "auto" or int(checks["resolved_purge_bars"] or 0) != 31:
        failures.append("models config purge policy is not auto/31")
    if checks["final_holdout_excluded_from_selection"] is not True:
        failures.append("models config does not exclude final holdout from selection")
    return checks


def bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].fillna(False).astype(bool)


def inspect_feature_parquet(path: Path, market: str, year: int, failures: list[str]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "market": market,
        "year": year,
        "path": None,
        "exists": path.is_file(),
        "schema_columns": None,
        "missing_required_columns": [],
        "row_count": 0,
        "training_row_valid_rows": 0,
        "target_valid_rows": 0,
        "feature_input_valid_rows": 0,
        "wfa_eligible_rows": 0,
        "min_ts": None,
        "max_ts": None,
        "duration_days": None,
        "status": "FAIL",
    }
    if not path.is_file():
        failures.append(f"feature parquet missing: {path.as_posix()}")
        return row

    row["path"] = path.as_posix()
    try:
        parquet_file = pq.ParquetFile(path)
        schema_cols = list(parquet_file.schema_arrow.names)
        row["schema_columns"] = len(schema_cols)
        row["row_count"] = int(parquet_file.metadata.num_rows)
    except Exception as exc:  # noqa: BLE001 - report must fail closed.
        failures.append(f"cannot read feature parquet metadata {path.as_posix()}: {exc}")
        return row

    missing = sorted(set(REQUIRED_WFA_COLUMNS) - set(schema_cols))
    row["missing_required_columns"] = missing
    if missing:
        failures.append(f"{path.as_posix()} missing WFA columns: {','.join(missing)}")
        return row

    try:
        frame = pd.read_parquet(path, columns=REQUIRED_WFA_COLUMNS)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"cannot read WFA preflight columns {path.as_posix()}: {exc}")
        return row

    timestamps = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    valid_ts = timestamps.dropna()
    if valid_ts.empty:
        failures.append(f"{path.as_posix()} has no valid timestamps")
        return row
    market_values = sorted(set(str(value) for value in frame["market"].dropna().unique()))
    year_values = sorted(set(int(value) for value in frame["year"].dropna().unique()))
    if market_values != [market]:
        failures.append(f"{path.as_posix()} market column mismatch: {market_values}")
    if year_values != [year]:
        failures.append(f"{path.as_posix()} year column mismatch: {year_values}")
    training_valid = bool_series(frame, "training_row_valid")
    target_valid = bool_series(frame, "target_valid")
    feature_input_valid = bool_series(frame, "feature_input_valid")
    eligible = training_valid & target_valid & feature_input_valid
    row.update(
        {
            "training_row_valid_rows": int(training_valid.sum()),
            "target_valid_rows": int(target_valid.sum()),
            "feature_input_valid_rows": int(feature_input_valid.sum()),
            "wfa_eligible_rows": int(eligible.sum()),
            "min_ts": valid_ts.min().isoformat(),
            "max_ts": valid_ts.max().isoformat(),
            "duration_days": round((valid_ts.max() - valid_ts.min()).total_seconds() / 86400, 6),
            "status": "PASS",
        }
    )
    if int(row["wfa_eligible_rows"]) <= 0:
        failures.append(f"{path.as_posix()} has no WFA-eligible rows")
    return row


def inspect_feature_files(feature_root: Path, failures: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for market in EXPECTED_MARKETS:
        for year in EXPECTED_YEARS:
            rows.append(inspect_feature_parquet(feature_root / market / f"{year}.parquet", market, year, failures))
    return rows


def count_prediction_files(predictions_root: Path) -> int:
    if not predictions_root.exists():
        return 0
    return sum(1 for path in predictions_root.rglob("*") if path.is_file())


def build_report(
    *,
    repo_root: Path,
    feature_root: Path,
    predictions_root: Path,
    placement_report_path: Path,
    feature_manifest_path: Path,
    label_manifest_path: Path,
    profile_config_path: Path,
    models_config_path: Path,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []

    placement_report = read_json(placement_report_path)
    feature_manifest = read_json(feature_manifest_path)
    label_manifest = read_json(label_manifest_path)
    profile_config = read_yaml(profile_config_path)
    models_config = read_yaml(models_config_path)

    if placement_report.get("status") != "PASS_TIER1_CORE_PHASE4_SELF_REFERENCE_CLEANUP_ACTIVE_PLACEMENT":
        failures.append(f"placement report status is {placement_report.get('status')!r}")
    active_counts = placement_report.get("active_counts")
    if not isinstance(active_counts, dict):
        active_counts = {}
        failures.append("placement report active_counts missing")
    if int(active_counts.get("feature_parquets_present") or 0) != EXPECTED_MARKET_YEAR_COUNT:
        failures.append("placement report feature parquet count mismatch")
    if int(active_counts.get("sidecars_present") or 0) != 4:
        failures.append("placement report sidecar count mismatch")
    if active_counts.get("removed_features_present_in_active_feature_cols"):
        failures.append("removed self-reference features remain active")
    scope = placement_report.get("scope")
    if not isinstance(scope, dict):
        scope = {}
        failures.append("placement report scope missing")
    validate_scope(scope, failures)

    placement_hash_rows = validate_placement_hashes(
        repo_root=repo_root,
        placement_report=placement_report,
        feature_root=feature_root,
        failures=failures,
    )
    feature_manifest_checks = validate_feature_manifest(feature_manifest, feature_root, repo_root, failures)
    label_manifest_checks = validate_label_manifest(label_manifest, failures)
    profile_checks = validate_profile_config(profile_config, failures)
    models_checks = validate_models_config(models_config, failures)
    feature_file_rows = inspect_feature_files(feature_root, failures)

    prediction_file_count = count_prediction_files(predictions_root)
    if prediction_file_count:
        failures.append(f"predictions root is not empty: {prediction_file_count} files")

    total_rows = sum(int(row.get("row_count") or 0) for row in feature_file_rows)
    total_eligible = sum(int(row.get("wfa_eligible_rows") or 0) for row in feature_file_rows)
    if total_eligible <= 0:
        failures.append("no WFA-eligible rows across active Tier 1 feature files")

    non_approval = {
        "split_plan_generated": False,
        "wfa_model_training": False,
        "prediction_generation": False,
        "provider_calls": False,
        "data_replacement": False,
        "cleanup_archive": False,
        "staging_commit_push": False,
        "paper_or_live_work": False,
    }
    status = status_from_failures(failures, warnings)
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "profile_alias": "tier_1_core",
            "resolved_profile": "tier_1_research",
            "markets": EXPECTED_MARKETS,
            "years": EXPECTED_YEARS,
            "market_year_count": EXPECTED_MARKET_YEAR_COUNT,
        },
        "summary": {
            "feature_parquet_count": len(feature_file_rows),
            "feature_sidecar_count": len(sidecar_paths(feature_root)),
            "active_feature_count": feature_manifest_checks.get("feature_count"),
            "total_feature_rows": total_rows,
            "total_wfa_eligible_rows": total_eligible,
            "prediction_file_count": prediction_file_count,
            "failure_count": len(failures),
            "warning_count": len(warnings),
        },
        "checks": {
            "placement_status": placement_report.get("status"),
            "placement_active_counts": active_counts,
            "feature_manifest": feature_manifest_checks,
            "label_manifest": label_manifest_checks,
            "profile": profile_checks,
            "models_policy": models_checks,
        },
        "feature_files": feature_file_rows,
        "placement_hashes": placement_hash_rows,
        "failures": failures,
        "warnings": warnings,
        "input_evidence": {
            "placement_report": rel(placement_report_path, repo_root),
            "placement_report_sha256": sha256_file(placement_report_path),
            "active_feature_manifest": rel(feature_manifest_path, repo_root),
            "active_feature_manifest_sha256": sha256_file(feature_manifest_path),
            "active_label_manifest": rel(label_manifest_path, repo_root),
            "active_label_manifest_sha256": sha256_file(label_manifest_path),
            "profile_config": rel(profile_config_path, repo_root),
            "profile_config_sha256": sha256_file(profile_config_path),
            "models_config": rel(models_config_path, repo_root),
            "models_config_sha256": sha256_file(models_config_path),
            "feature_root": rel(feature_root, repo_root),
            "predictions_root": rel(predictions_root, repo_root),
        },
        "data_access": "read_existing_json_yaml_and_scoped_feature_parquet_columns_plus_sha256_hashes",
        "non_approval": non_approval,
        "non_approval_text": NO_MUTATION_TEXT,
        "recommended_next_action": (
            "If this report status is PASS, the next separately approved bounded step is Phase 5 "
            "split-plan generation for ES,CL,ZN,6E years 2023,2024 using active data/feature_matrices "
            "and the current active feature manifest; still no model training, predictions, promotion, "
            "paper, or live work."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Tier 1 Phase 5 WFA Preflight",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated at UTC: `{report['generated_at_utc']}`",
        f"- Scope: `{','.join(report['scope']['markets'])}` `{','.join(str(y) for y in report['scope']['years'])}`",
        f"- Active features: `{report['summary']['active_feature_count']}`",
        f"- Feature files: `{report['summary']['feature_parquet_count']}`",
        f"- WFA-eligible rows: `{report['summary']['total_wfa_eligible_rows']}`",
        f"- Prediction files: `{report['summary']['prediction_file_count']}`",
        "",
        "## Evidence",
        "",
    ]
    for key, value in report["input_evidence"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Feature Files",
            "",
            "| market | year | rows | eligible rows | min ts | max ts | status |",
            "| --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in report["feature_files"]:
        lines.append(
            f"| `{row['market']}` | {row['year']} | {row['row_count']} | "
            f"{row['wfa_eligible_rows']} | `{row['min_ts']}` | `{row['max_ts']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Failures", ""])
    lines.extend(f"- {failure}" for failure in report["failures"]) if report["failures"] else lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report["warnings"]) if report["warnings"] else lines.append("- None")
    lines.extend(
        [
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


def write_report(report: dict[str, Any], report_root: Path) -> tuple[Path, Path]:
    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / "phase5_wfa_preflight_report.json"
    md_path = report_root / "phase5_wfa_preflight_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--feature-root", default=str(DEFAULT_FEATURE_ROOT))
    parser.add_argument("--predictions-root", default=str(DEFAULT_PREDICTIONS_ROOT))
    parser.add_argument("--placement-report", default=str(DEFAULT_PLACEMENT_REPORT))
    parser.add_argument("--feature-manifest", default=str(DEFAULT_FEATURE_MANIFEST))
    parser.add_argument("--label-manifest", default=str(DEFAULT_LABEL_MANIFEST))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--models-config", default=str(DEFAULT_MODELS_CONFIG))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    report_root = resolve_path(repo_root, args.report_root)
    report = build_report(
        repo_root=repo_root,
        feature_root=resolve_path(repo_root, args.feature_root),
        predictions_root=resolve_path(repo_root, args.predictions_root),
        placement_report_path=resolve_path(repo_root, args.placement_report),
        feature_manifest_path=resolve_path(repo_root, args.feature_manifest),
        label_manifest_path=resolve_path(repo_root, args.label_manifest),
        profile_config_path=resolve_path(repo_root, args.profile_config),
        models_config_path=resolve_path(repo_root, args.models_config),
    )
    json_path, md_path = write_report(report, report_root)
    print(
        f"{STAGE} status={report['status']} failures={len(report['failures'])} "
        f"warnings={len(report['warnings'])} eligible_rows={report['summary']['total_wfa_eligible_rows']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 1 if report["status"].startswith("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
