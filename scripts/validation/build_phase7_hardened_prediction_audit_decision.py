#!/usr/bin/env python3
"""Report-only Phase 7 decision for hardened WFA prediction artifacts."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.pipeline_gates import file_sha256


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "phase7_hardened_prediction_audit_decision"
BLOCKED_STATUS = "BLOCKED_PHASE7_PREDICTION_ARTIFACT_AUDIT_NO_SAVED_PREDICTIONS"
FAIL_STATUS = "FAIL_PHASE7_HARDENED_PREDICTION_AUDIT_DECISION_INPUTS_INVALID"
REPORT_JSON = "phase7_prediction_audit_decision.json"
REPORT_MD = "phase7_prediction_audit_decision.md"

DEFAULT_WFA_REPORT = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_hardened_report_only/"
    "phase6_v2_apex_30m60m_20260709_tier1_core_hardened_report_only_wfa_report.json"
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
DEFAULT_FEATURE_PLACEMENT_HASHES = Path(
    "reports/features_baseline/"
    "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "post_active_feature_hashes.json"
)
DEFAULT_LABEL_PLACEMENT_HASHES = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_active_replacement_decision/"
    "post_replacement_hashes.json"
)
DEFAULT_MASTER_AUDIT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_MASTER_AUDIT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_REPORTS_ROOT = Path(
    "reports/prediction_audit/"
    "phase7_v2_apex_30m60m_20260709_tier1_core_hardened_report_only_decision"
)
DEFAULT_PREDICTIONS_ROOT = Path("data/predictions")
DEFAULT_MARKETS = ("6E", "CL", "ES", "ZN")
DEFAULT_YEARS = (2023, 2024)
DEFAULT_HARDENED_RUN = "phase6_v2_apex_30m60m_20260709_tier1_core_hardened"
DEFAULT_REPORT_ONLY_RUN = "phase6_v2_apex_30m60m_20260709_tier1_core_hardened_report_only"
EXPECTED_PREDICTION_COUNT = 4_394_288
V2_LABEL_SEMANTICS_ID = "phase3_labels_v2_next_1m_open_30m_primary_60m_confirm_apex_aware"


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


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def int_value(value: Any, *, default: int = -1) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def records(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = report.get("records")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, Mapping)]


def input_evidence(repo_root: Path, paths: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for key, path in paths.items():
        evidence[key] = {
            "path": rel(path, repo_root),
            "exists": path.exists(),
            "sha256": file_sha256(path) if path.exists() else None,
        }
    return evidence


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


def find_audit_area(payload: Mapping[str, Any], area: str) -> Mapping[str, Any] | None:
    def walk(value: Any) -> Mapping[str, Any] | None:
        if isinstance(value, Mapping):
            if value.get("audit_area") == area:
                return value
            for child in value.values():
                result = walk(child)
                if result is not None:
                    return result
        elif isinstance(value, list):
            for child in value:
                result = walk(child)
                if result is not None:
                    return result
        return None

    return walk(payload)


def validate_wfa_artifacts(
    *,
    wfa_report: Mapping[str, Any],
    manifest: Mapping[str, Any],
    split_plan_path: Path,
    markets: Sequence[str],
    years: Sequence[int],
    repo_root: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    expected_markets = sorted(str(market) for market in markets)
    expected_years = sorted(int(year) for year in years)
    required_values = {
        "failure_count": 0,
        "warning_count": 0,
        "fold_count": len(expected_markets),
        "unfiltered_selectable_fold_count": len(expected_markets),
        "prediction_count": EXPECTED_PREDICTION_COUNT,
        "duplicate_prediction_count": 0,
    }
    for payload_name, payload in (("wfa_report", wfa_report), ("predictions_manifest", manifest)):
        for field, expected in required_values.items():
            if int_value(payload.get(field)) != expected:
                failures.append(f"{payload_name}.{field} expected {expected}, got {payload.get(field)!r}")
        for field in ("prediction_writes_enabled", "prediction_artifact_written"):
            if payload.get(field) is not False:
                failures.append(f"{payload_name}.{field} must be false")
        if payload.get("prediction_artifact_write_skipped") is not True:
            failures.append(f"{payload_name}.prediction_artifact_write_skipped must be true")
        if payload.get("artifact_evidence_ready") is not True:
            failures.append(f"{payload_name}.artifact_evidence_ready must be true")
        for field in ("output_root", "predictions_root", "prediction_path"):
            if payload.get(field) is not None:
                failures.append(f"{payload_name}.{field} must be null")
        if sorted(str(item) for item in payload.get("markets", [])) != expected_markets:
            failures.append(f"{payload_name}.markets scope mismatch")
        if sorted(int(item) for item in payload.get("years", [])) != expected_years:
            failures.append(f"{payload_name}.years scope mismatch")
        if sorted(str(item) for item in payload.get("prediction_markets", [])) != expected_markets:
            failures.append(f"{payload_name}.prediction_markets scope mismatch")
        if sorted(int(item) for item in payload.get("prediction_years", [])) != [2024]:
            failures.append(f"{payload_name}.prediction_years must be [2024]")

    for field in required_values:
        if wfa_report.get(field) != manifest.get(field):
            failures.append(f"wfa_report and manifest diverge for {field}")
    if manifest.get("split_plan_path") != rel(split_plan_path, repo_root):
        failures.append("predictions_manifest.split_plan_path mismatch")
    if manifest.get("split_plan_hash") != file_sha256(split_plan_path):
        failures.append("predictions_manifest.split_plan_hash mismatch")

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "wfa_report": {
            key: wfa_report.get(key)
            for key in [
                "failure_count",
                "warning_count",
                "fold_count",
                "prediction_count",
                "prediction_artifact_written",
                "prediction_path",
            ]
        },
        "predictions_manifest": {
            key: manifest.get(key)
            for key in [
                "failure_count",
                "warning_count",
                "fold_count",
                "prediction_count",
                "prediction_artifact_written",
                "prediction_path",
                "split_plan_path",
                "split_plan_hash",
            ]
        },
    }


def validate_no_prediction_artifact(
    *,
    manifest: Mapping[str, Any],
    predictions_root: Path,
    hardened_run: str,
    report_only_run: str,
    repo_root: Path,
) -> dict[str, Any]:
    scoped_roots = [
        predictions_root / hardened_run,
        predictions_root / report_only_run,
    ]
    scoped_parquets = [root / "oos_predictions.parquet" for root in scoped_roots]
    manifest_prediction_path = manifest.get("prediction_path")
    failures: list[str] = []
    if manifest.get("prediction_artifact_written") is not False:
        failures.append("manifest claims prediction_artifact_written is not false")
    if manifest_prediction_path is not None:
        failures.append(f"manifest prediction_path must be null, got {manifest_prediction_path!r}")
    existing_roots = [rel(path, repo_root) for path in scoped_roots if path.exists()]
    existing_parquets = [rel(path, repo_root) for path in scoped_parquets if path.exists()]
    if existing_roots:
        failures.append(f"scoped hardened prediction roots exist: {existing_roots}")
    if existing_parquets:
        failures.append(f"scoped hardened prediction parquet exists: {existing_parquets}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "manifest_prediction_path": manifest_prediction_path,
        "scoped_prediction_roots": [rel(path, repo_root) for path in scoped_roots],
        "existing_scoped_prediction_roots": existing_roots,
        "existing_scoped_prediction_parquets": existing_parquets,
    }


def validate_hardened_split(
    split_plan: Mapping[str, Any],
    split_acceptance: Mapping[str, Any],
    split_plan_path: Path,
    markets: Sequence[str],
    years: Sequence[int],
    repo_root: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    expected_markets = sorted(str(market) for market in markets)
    expected_years = sorted(int(year) for year in years)
    if split_plan.get("status") != "PASS_HARDENED_PHASE5_SPLIT_PLAN_BUILT_NO_MODELING":
        failures.append(f"split_plan.status mismatch: {split_plan.get('status')!r}")
    if split_plan.get("profile") != "tier_1" or split_plan.get("resolved_profile") != "tier_1_research":
        failures.append("split_plan profile/resolved_profile mismatch")
    if sorted(str(item) for item in split_plan.get("markets", [])) != expected_markets:
        failures.append("split_plan markets mismatch")
    if sorted(int(item) for item in split_plan.get("years", [])) != expected_years:
        failures.append("split_plan years mismatch")
    if int_value(split_plan.get("fold_count")) != len(expected_markets):
        failures.append("split_plan fold_count mismatch")
    if int_value(split_plan.get("failure_count"), default=0) != 0:
        failures.append("split_plan failure_count must be zero")
    if split_plan.get("modeling_allowed") is not False:
        failures.append("split_plan modeling_allowed must be false")
    if split_plan.get("prediction_materialization_allowed") is not False:
        failures.append("split_plan prediction_materialization_allowed must be false")

    folds = split_plan.get("folds")
    if not isinstance(folds, list) or len(folds) != len(expected_markets):
        failures.append("split_plan folds must contain one fold per market")
    else:
        for fold in folds:
            if not isinstance(fold, Mapping):
                failures.append("split_plan has invalid fold row")
                continue
            fold_id = str(fold.get("fold_id", "<unknown>"))
            if fold.get("split_group") != "hardened_research":
                failures.append(f"{fold_id}: split_group must be hardened_research")
            if fold.get("selection_source") != "validation_only":
                failures.append(f"{fold_id}: selection_source must be validation_only")
            if fold.get("test_selection_allowed") is not False:
                failures.append(f"{fold_id}: test_selection_allowed must be false")
            if fold.get("independent_test_claim_allowed") is not True:
                failures.append(f"{fold_id}: independent_test_claim_allowed must be true")
            if fold.get("final_holdout") is True or fold.get("is_final_holdout") is True:
                failures.append(f"{fold_id}: final_holdout must be false")

    summary = split_acceptance.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    evidence = split_acceptance.get("input_evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    if split_acceptance.get("status") != "PASS_HARDENED_PHASE5_SPLIT_PLAN_ACCEPTED_NO_MODELING":
        failures.append(f"split_acceptance.status mismatch: {split_acceptance.get('status')!r}")
    if int_value(summary.get("failure_count"), default=0) != 0:
        failures.append("split_acceptance summary failure_count must be zero")
    if summary.get("modeling_allowed") is not False:
        failures.append("split_acceptance summary modeling_allowed must be false")
    if summary.get("prediction_materialization_allowed") is not False:
        failures.append("split_acceptance summary prediction_materialization_allowed must be false")
    if evidence.get("split_plan") != rel(split_plan_path, repo_root):
        failures.append("split_acceptance input split_plan path mismatch")
    accepted_hash = evidence.get("split_plan_json_sha256") or evidence.get("split_plan_sha256")
    if accepted_hash is not None and accepted_hash != file_sha256(split_plan_path):
        failures.append("split_acceptance input split_plan hash mismatch")

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "split_plan_status": split_plan.get("status"),
        "split_acceptance_status": split_acceptance.get("status"),
        "fold_count": split_plan.get("fold_count"),
        "markets": split_plan.get("markets"),
        "years": split_plan.get("years"),
    }


def validate_runner_preflight(preflight: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    summary = preflight.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    if preflight.get("status") != "PASS_PHASE6_WFA_RUNNER_PREFLIGHT_READY_REPORT_ONLY":
        failures.append(f"preflight status mismatch: {preflight.get('status')!r}")
    if int_value(summary.get("failure_count"), default=0) != 0:
        failures.append("preflight summary failure_count must be zero")
    if int_value(summary.get("fold_count")) != 4:
        failures.append("preflight summary fold_count must be 4")
    if int_value(summary.get("feature_count")) != 114:
        failures.append("preflight summary feature_count must be 114")
    if int_value(summary.get("prediction_file_count"), default=0) != 0:
        failures.append("preflight scoped prediction_file_count must be zero")
    if summary.get("commands_executed") not in (0, None):
        failures.append("preflight commands_executed must be zero")
    if summary.get("model_training_performed") is not False:
        failures.append("preflight model_training_performed must be false")
    if summary.get("prediction_generation_performed") is not False:
        failures.append("preflight prediction_generation_performed must be false")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": dict(summary),
    }


def validate_active_v2_hashes(
    feature_hashes: Mapping[str, Any],
    label_hashes: Mapping[str, Any],
    markets: Sequence[str],
    years: Sequence[int],
) -> dict[str, Any]:
    failures: list[str] = []
    expected_pairs = {(str(market), int(year)) for market in markets for year in years}
    feature_records = records(feature_hashes)
    label_records = records(label_hashes)
    if feature_hashes.get("status") != "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM":
        failures.append(f"feature hash status mismatch: {feature_hashes.get('status')!r}")
    if label_hashes.get("status") != "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM":
        failures.append(f"label hash status mismatch: {label_hashes.get('status')!r}")
    if label_hashes.get("label_semantics_id") != V2_LABEL_SEMANTICS_ID:
        failures.append("label_semantics_id mismatch")
    if len(feature_records) != 12:
        failures.append(f"feature hash record count expected 12, got {len(feature_records)}")
    if len(label_records) != 8:
        failures.append(f"label hash record count expected 8, got {len(label_records)}")
    label_pairs = {
        (str(row.get("market")), int(row.get("year")))
        for row in label_records
        if row.get("market") is not None and row.get("year") is not None
    }
    if label_pairs != expected_pairs:
        failures.append(f"label hash scope mismatch: {sorted(label_pairs)}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "feature_status": feature_hashes.get("status"),
        "label_status": label_hashes.get("status"),
        "feature_record_count": len(feature_records),
        "label_record_count": len(label_records),
        "label_semantics_id": label_hashes.get("label_semantics_id"),
    }


def validate_master_audit(master_run_status: Mapping[str, Any], master_overview: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    phase6_run = find_audit_area(master_run_status, "Phase 6")
    phase7_run = find_audit_area(master_run_status, "Phase 7")
    phase6_overview = find_audit_area(master_overview, "Phase 6")
    phase7_overview = find_audit_area(master_overview, "Phase 7")
    if master_run_status.get("status") != "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY":
        failures.append("master run-status report status mismatch")
    if master_overview.get("status") != "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY":
        failures.append("master overview report status mismatch")
    for label, row in (
        ("run_status Phase 6", phase6_run),
        ("run_status Phase 7", phase7_run),
        ("overview Phase 6", phase6_overview),
        ("overview Phase 7", phase7_overview),
    ):
        if not isinstance(row, Mapping):
            failures.append(f"{label} row missing")
            continue
        if row.get("run_status") != "NOT_RUN":
            failures.append(f"{label} run_status must be NOT_RUN")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "phase6_run_status": dict(phase6_run) if isinstance(phase6_run, Mapping) else None,
        "phase7_run_status": dict(phase7_run) if isinstance(phase7_run, Mapping) else None,
        "phase6_overview_status": dict(phase6_overview) if isinstance(phase6_overview, Mapping) else None,
        "phase7_overview_status": dict(phase7_overview) if isinstance(phase7_overview, Mapping) else None,
    }


def build_report(
    *,
    repo_root: Path,
    wfa_report_path: Path,
    predictions_manifest_path: Path,
    split_plan_path: Path,
    split_acceptance_path: Path,
    runner_preflight_path: Path,
    feature_hashes_path: Path,
    label_hashes_path: Path,
    master_run_status_path: Path,
    master_overview_path: Path,
    reports_root: Path,
    predictions_root: Path,
    hardened_run: str,
    report_only_run: str,
    markets: Sequence[str],
    years: Sequence[int],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    input_paths = {
        "wfa_report": wfa_report_path,
        "predictions_manifest": predictions_manifest_path,
        "split_plan": split_plan_path,
        "split_acceptance": split_acceptance_path,
        "runner_preflight": runner_preflight_path,
        "feature_placement_hashes": feature_hashes_path,
        "label_placement_hashes": label_hashes_path,
        "master_audit_run_status": master_run_status_path,
        "master_audit_overview": master_overview_path,
    }
    for path in input_paths.values():
        if not path.exists():
            raise FileNotFoundError(path)

    wfa_report = read_json(wfa_report_path)
    manifest = read_json(predictions_manifest_path)
    split_plan = read_json(split_plan_path)
    split_acceptance = read_json(split_acceptance_path)
    runner_preflight = read_json(runner_preflight_path)
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
        name="report_root_contains_only_expected_decision_files",
        passed=not output_check["unexpected_files"],
        evidence=output_check,
        failure=f"unexpected report files: {output_check['unexpected_files']}",
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
        name="hardened_report_only_wfa_manifest_blocks_saved_artifact_audit",
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
        name="no_saved_hardened_prediction_parquet_exists",
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

    preflight_check = validate_runner_preflight(runner_preflight)
    add_check(
        checks,
        failures,
        name="hardened_runner_preflight_report_only",
        passed=preflight_check["status"] == "PASS",
        evidence=preflight_check,
        failure="; ".join(preflight_check["failures"]),
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

    master_check = validate_master_audit(master_run_status, master_overview)
    add_check(
        checks,
        failures,
        name="master_audit_phase6_phase7_remain_not_run",
        passed=master_check["status"] == "PASS",
        evidence=master_check,
        failure="; ".join(master_check["failures"]),
    )

    status = BLOCKED_STATUS if not failures else FAIL_STATUS
    payload: dict[str, Any] = {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "markets": list(markets),
            "years": [int(year) for year in years],
            "market_year_count": len(markets) * len(years),
            "hardened_run": hardened_run,
            "report_only_run": report_only_run,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "normal_phase7_prediction_audit_allowed": False,
            "normal_phase7_prediction_audit_blocked": True,
            "block_reason": "no_saved_oos_prediction_parquet",
            "prediction_materialization_allowed": False,
            "phase8_refresh_allowed": False,
            "promotion_allowed": False,
            "paper_live_allowed": False,
        },
        "decision": {
            "phase7_audit_command_approved": False,
            "phase7_audit_command": None,
            "phase7_audit_blocker": (
                "scripts.phase7_prediction_audit.audit_predictions requires a saved OOS "
                "prediction parquet plus its exact manifest; the hardened run is report-only "
                "and wrote no prediction parquet."
            ),
            "future_unblock_requires_separate_prediction_materialization_approval": True,
        },
        "checks": checks,
        "failures": failures,
        "input_evidence": input_evidence(repo_root, input_paths),
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "non_approval": {
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
    return payload


def write_report(payload: Mapping[str, Any], reports_root: Path) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    write_json(reports_root / REPORT_JSON, payload)
    summary = payload.get("summary", {})
    decision = payload.get("decision", {})
    checks = payload.get("checks", [])
    lines = [
        "# Hardened Phase 7 Prediction Audit Decision",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "This report is decision evidence only. It does not run Phase 7 audit, "
        "materialize predictions, evaluate Phase 8, promote, freeze, paper trade, or live trade.",
        "",
        "## Decision",
        "",
        f"- Normal Phase 7 audit allowed: `{summary.get('normal_phase7_prediction_audit_allowed')}`",
        f"- Block reason: `{summary.get('block_reason')}`",
        f"- Future unblock requires separate prediction materialization approval: "
        f"`{decision.get('future_unblock_requires_separate_prediction_materialization_approval')}`",
        "",
        "## Checks",
        "",
    ]
    for check in checks if isinstance(checks, list) else []:
        if isinstance(check, Mapping):
            lines.append(f"- `{check.get('name')}`: `{check.get('status')}`")
    failures = payload.get("failures", [])
    lines.extend(["", "## Failures", ""])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None.")
    (reports_root / REPORT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wfa-report", default=DEFAULT_WFA_REPORT.as_posix())
    parser.add_argument("--predictions-manifest", default=DEFAULT_PREDICTIONS_MANIFEST.as_posix())
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--split-acceptance", default=DEFAULT_SPLIT_ACCEPTANCE.as_posix())
    parser.add_argument("--runner-preflight", default=DEFAULT_RUNNER_PREFLIGHT.as_posix())
    parser.add_argument("--feature-placement-hashes", default=DEFAULT_FEATURE_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--label-placement-hashes", default=DEFAULT_LABEL_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--master-audit-run-status", default=DEFAULT_MASTER_AUDIT_RUN_STATUS.as_posix())
    parser.add_argument("--master-audit-overview", default=DEFAULT_MASTER_AUDIT_OVERVIEW.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--predictions-root", default=DEFAULT_PREDICTIONS_ROOT.as_posix())
    parser.add_argument("--hardened-run", default=DEFAULT_HARDENED_RUN)
    parser.add_argument("--report-only-run", default=DEFAULT_REPORT_ONLY_RUN)
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    payload = build_report(
        repo_root=REPO_ROOT,
        wfa_report_path=resolve_path(REPO_ROOT, args.wfa_report),
        predictions_manifest_path=resolve_path(REPO_ROOT, args.predictions_manifest),
        split_plan_path=resolve_path(REPO_ROOT, args.split_plan),
        split_acceptance_path=resolve_path(REPO_ROOT, args.split_acceptance),
        runner_preflight_path=resolve_path(REPO_ROOT, args.runner_preflight),
        feature_hashes_path=resolve_path(REPO_ROOT, args.feature_placement_hashes),
        label_hashes_path=resolve_path(REPO_ROOT, args.label_placement_hashes),
        master_run_status_path=resolve_path(REPO_ROOT, args.master_audit_run_status),
        master_overview_path=resolve_path(REPO_ROOT, args.master_audit_overview),
        reports_root=resolve_path(REPO_ROOT, args.reports_root),
        predictions_root=resolve_path(REPO_ROOT, args.predictions_root),
        hardened_run=args.hardened_run,
        report_only_run=args.report_only_run,
        markets=csv_strings(args.markets),
        years=csv_ints(args.years),
    )
    write_report(payload, resolve_path(REPO_ROOT, args.reports_root))
    print(
        payload["status"],
        "phase7 hardened prediction audit decision:",
        f"checks={payload['summary']['check_count']}",
        f"failures={payload['summary']['failure_count']}",
        f"summary={payload['outputs']['json']}",
    )
    return 1 if payload["summary"]["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
