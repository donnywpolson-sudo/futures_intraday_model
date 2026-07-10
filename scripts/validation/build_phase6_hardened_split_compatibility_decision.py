#!/usr/bin/env python3
"""Report-only Phase 6/7 compatibility decision for a hardened Phase 5 split."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.pipeline_gates import file_sha256
from scripts.validation.review_phase6_wfa_runner_preflight import (
    HARDENED_SPLIT_ACCEPTANCE_STATUS,
    HARDENED_SPLIT_STATUS,
    V2_FEATURE_PLACEMENT_STATUS,
    V2_LABEL_PLACEMENT_STATUS,
    V2_LABEL_SEMANTICS_ID,
    hardened_split_metadata_check,
    split_acceptance_binding,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "phase6_hardened_split_compatibility_decision"
PASS_STATUS = "PASS_PHASE6_HARDENED_SPLIT_PREFLIGHT_COMPATIBLE_NO_WFA_EXECUTION"
FAIL_STATUS = "FAIL_PHASE6_HARDENED_SPLIT_COMPATIBILITY_NO_WFA_EXECUTION"
REPORT_JSON = "hardened_split_compatibility_decision.json"
REPORT_MD = "hardened_split_compatibility_decision.md"

DEFAULT_SPLIT_PLAN = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_hardened_split_candidate/"
    "split_plan.json"
)
DEFAULT_SPLIT_ACCEPTANCE = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_hardened_split_candidate/"
    "hardened_split_acceptance_report.json"
)
DEFAULT_FEATURE_ROOT = Path("data/feature_matrices")
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
DEFAULT_MASTER_AUDIT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_MASTER_AUDIT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_REPORTS_ROOT = Path(
    "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_hardened_split_compatibility"
)
DEFAULT_MARKETS = ("6E", "CL", "ES", "ZN")
DEFAULT_YEARS = (2023, 2024)
DEFAULT_EXPECTED_PREDICTION_RUN = "phase6_v2_apex_30m60m_20260709_tier1_core_hardened"
DEFAULT_PREDICTIONS_ROOT = Path("data/predictions")


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


def csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def expected_pairs(markets: Sequence[str], years: Sequence[int]) -> list[tuple[str, int]]:
    return [(str(market), int(year)) for market in markets for year in years]


def int_value(value: Any, *, default: int = -1) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def record_check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    observed: Mapping[str, Any],
    expected: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": dict(observed),
            "expected": expected,
        }
    )
    if not passed:
        failures.append(f"{name}: {observed}")


def records_by_path(report: Mapping[str, Any], key: str) -> dict[str, Mapping[str, Any]]:
    records = report.get("records")
    if not isinstance(records, list):
        return {}
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        raw_path = record.get(key)
        if isinstance(raw_path, str) and raw_path:
            indexed[Path(raw_path).as_posix()] = record
    return indexed


def rows_by_audit_area(rows: Any) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    if not isinstance(rows, list):
        return indexed
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        area = row.get("audit_area")
        if isinstance(area, str) and area:
            indexed[area] = row
    return indexed


def validate_hardened_split_scope(
    split_plan: Mapping[str, Any],
    markets: Sequence[str],
    years: Sequence[int],
) -> dict[str, Any]:
    failures: list[str] = []
    observed_markets = sorted(str(item) for item in split_plan.get("markets", []))
    observed_years = sorted(int(item) for item in split_plan.get("years", []))
    expected_markets = sorted(str(item) for item in markets)
    expected_years = sorted(int(item) for item in years)
    if split_plan.get("status") != HARDENED_SPLIT_STATUS:
        failures.append(f"split status mismatch: {split_plan.get('status')}")
    if split_plan.get("profile") != "tier_1":
        failures.append(f"profile mismatch: {split_plan.get('profile')}")
    if split_plan.get("resolved_profile") != "tier_1_research":
        failures.append(f"resolved_profile mismatch: {split_plan.get('resolved_profile')}")
    if observed_markets != expected_markets:
        failures.append(f"markets mismatch: {observed_markets}")
    if observed_years != expected_years:
        failures.append(f"years mismatch: {observed_years}")
    if int_value(split_plan.get("fold_count")) != len(expected_markets):
        failures.append("fold_count must be one fold per market")
    if int_value(split_plan.get("failure_count"), default=0) != 0:
        failures.append("split failure_count must be zero")
    if split_plan.get("modeling_allowed") is not False:
        failures.append("split modeling_allowed must be false")
    if split_plan.get("prediction_materialization_allowed") is not False:
        failures.append("split prediction_materialization_allowed must be false")
    metadata = hardened_split_metadata_check(
        split_plan=split_plan,
        expected_markets=list(markets),
        expected_years=list(years),
    )
    if metadata.get("status") != "PASS":
        failures.extend(str(item) for item in metadata.get("failures", []))
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "markets": observed_markets,
        "years": observed_years,
        "fold_count": split_plan.get("fold_count"),
        "fold_count_by_market": split_plan.get("fold_count_by_market"),
        "metadata": metadata,
    }


def validate_feature_manifest(
    feature_manifest: Mapping[str, Any],
    feature_root: Path,
    markets: Sequence[str],
    years: Sequence[int],
    repo_root: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    outputs = feature_manifest.get("outputs")
    outputs = outputs if isinstance(outputs, list) else []
    observed_pairs = sorted(
        (str(row.get("market")), int(row.get("year")))
        for row in outputs
        if isinstance(row, Mapping) and row.get("market") is not None and row.get("year") is not None
    )
    expected = sorted(expected_pairs(markets, years))
    if feature_manifest.get("status") != "PASS":
        failures.append(f"status mismatch: {feature_manifest.get('status')}")
    if feature_manifest.get("profile") != "tier_1":
        failures.append(f"profile mismatch: {feature_manifest.get('profile')}")
    if feature_manifest.get("resolved_profile") != "tier_1_research":
        failures.append(f"resolved_profile mismatch: {feature_manifest.get('resolved_profile')}")
    if feature_manifest.get("output_root") != rel(feature_root, repo_root):
        failures.append(f"output_root mismatch: {feature_manifest.get('output_root')}")
    if int_value(feature_manifest.get("feature_count")) != 114:
        failures.append("feature_count must be 114")
    if int_value(feature_manifest.get("failure_count"), default=0) != 0:
        failures.append("failure_count must be zero")
    if int_value(feature_manifest.get("warning_count"), default=0) != 0:
        failures.append("warning_count must be zero")
    if observed_pairs != expected:
        failures.append(f"outputs scope mismatch: {observed_pairs}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "output_count": len(outputs),
        "feature_count": feature_manifest.get("feature_count"),
    }


def validate_active_hashes(
    *,
    split_plan: Mapping[str, Any],
    feature_hashes: Mapping[str, Any],
    label_hashes: Mapping[str, Any],
    feature_root: Path,
    markets: Sequence[str],
    years: Sequence[int],
    repo_root: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    split_hashes = split_plan.get("input_file_hashes")
    split_hashes = split_hashes if isinstance(split_hashes, Mapping) else {}
    feature_records = records_by_path(feature_hashes, "path")
    expected_files = [
        feature_root / market / f"{year}.parquet" for market, year in expected_pairs(markets, years)
    ]
    if feature_hashes.get("status") != V2_FEATURE_PLACEMENT_STATUS:
        failures.append(f"feature hash status mismatch: {feature_hashes.get('status')}")
    if feature_hashes.get("failures") not in ([], None):
        failures.append("feature hash report has failures")
    for path in expected_files:
        path_rel = rel(path, repo_root)
        if not path.is_file():
            failures.append(f"{path_rel}: missing active feature file")
            continue
        actual_hash = file_sha256(path)
        if split_hashes.get(path_rel) != actual_hash:
            failures.append(f"{path_rel}: split hash mismatch")
        record = feature_records.get(path_rel)
        if record is None:
            failures.append(f"{path_rel}: missing feature placement record")
            continue
        if record.get("sha256") != actual_hash or record.get("staged_sha256") != actual_hash:
            failures.append(f"{path_rel}: feature placement hash mismatch")
        if record.get("active_matches_staged") is not True:
            failures.append(f"{path_rel}: active_matches_staged is not true")

    label_records = label_hashes.get("records")
    label_records = label_records if isinstance(label_records, list) else []
    label_pairs = sorted(
        (str(row.get("market")), int(row.get("year")))
        for row in label_records
        if isinstance(row, Mapping) and row.get("market") is not None and row.get("year") is not None
    )
    if label_hashes.get("status") != V2_LABEL_PLACEMENT_STATUS:
        failures.append(f"label hash status mismatch: {label_hashes.get('status')}")
    if label_hashes.get("failures") not in ([], None):
        failures.append("label hash report has failures")
    if label_hashes.get("label_semantics_id") != V2_LABEL_SEMANTICS_ID:
        failures.append("label semantics id mismatch")
    if label_pairs != sorted(expected_pairs(markets, years)):
        failures.append(f"label pairs mismatch: {label_pairs}")
    for row in label_records:
        if not isinstance(row, Mapping):
            continue
        active_path_raw = row.get("active_path")
        active_path = resolve_path(repo_root, active_path_raw) if isinstance(active_path_raw, str) else None
        if active_path is None or not active_path.is_file():
            failures.append(f"{active_path_raw}: missing active label file")
            continue
        actual_hash = file_sha256(active_path)
        if row.get("active_sha256") != actual_hash or row.get("staged_sha256") != actual_hash:
            failures.append(f"{active_path_raw}: label placement hash mismatch")
        if row.get("active_matches_staged") is not True:
            failures.append(f"{active_path_raw}: label active_matches_staged is not true")

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "split_input_hash_count": len(split_hashes),
        "feature_record_count": len(feature_records),
        "label_record_count": len(label_records),
    }


def validate_master_audit_inputs(
    run_status: Mapping[str, Any],
    overview: Mapping[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    run_rows = rows_by_audit_area(run_status.get("run_status_table"))
    overview_sections = overview.get("overview_sections")
    overview_sections = overview_sections if isinstance(overview_sections, Mapping) else {}
    phase_status_summary = overview_sections.get("B_architecture_review", {}).get(
        "phase_status_summary", []
    )
    overview_rows = rows_by_audit_area(phase_status_summary)
    phase6_run = run_rows.get("Phase 6", {})
    phase7_run = run_rows.get("Phase 7", {})
    phase6_overview = overview_rows.get("Phase 6", {})
    phase7_overview = overview_rows.get("Phase 7", {})

    if run_status.get("status") != "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY":
        failures.append(f"run-status mismatch: {run_status.get('status')}")
    if overview.get("status") != "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY":
        failures.append(f"overview status mismatch: {overview.get('status')}")
    if run_status.get("failures") not in ([], None):
        failures.append("run-status report has failures")
    if overview.get("failures") not in ([], None):
        failures.append("overview report has failures")
    for name, row in (
        ("Phase 6 run-status", phase6_run),
        ("Phase 7 run-status", phase7_run),
        ("Phase 6 overview", phase6_overview),
        ("Phase 7 overview", phase7_overview),
    ):
        if row.get("run_status") != "NOT_RUN":
            failures.append(f"{name} must remain NOT_RUN")

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "phase6_run_status": dict(phase6_run),
        "phase7_run_status": dict(phase7_run),
        "phase6_overview_status": dict(phase6_overview),
        "phase7_overview_status": dict(phase7_overview),
    }


def prediction_scope_check(predictions_root: Path, expected_prediction_run: str, repo_root: Path) -> dict[str, Any]:
    scoped = predictions_root / expected_prediction_run
    files = [path for path in scoped.rglob("*") if path.is_file()] if scoped.exists() else []
    return {
        "status": "PASS" if not files else "FAIL",
        "predictions_root": rel(predictions_root, repo_root),
        "expected_prediction_run": expected_prediction_run,
        "scoped_predictions_root": rel(scoped, repo_root),
        "prediction_file_count": len(files),
        "phase7_decision": "DEFER_PHASE7_NO_HARDENED_PREDICTIONS" if not files else "BLOCKED_PREDICTION_COLLISION",
    }


def candidate_phase6_preflight_command(
    *,
    split_plan_path: Path,
    split_acceptance_path: Path,
    feature_root: Path,
    feature_manifest_path: Path,
    feature_hashes_path: Path,
    label_hashes_path: Path,
    expected_prediction_run: str,
    repo_root: Path,
) -> str:
    report_root = "reports/wfa/phase6_v2_apex_30m60m_20260709_tier1_core_hardened_runner_preflight"
    return (
        "python -m scripts.validation.review_phase6_wfa_runner_preflight "
        f"--split-plan {rel(split_plan_path, repo_root)} "
        f"--split-acceptance {rel(split_acceptance_path, repo_root)} "
        f"--feature-root {rel(feature_root, repo_root)} "
        f"--feature-manifest {rel(feature_manifest_path, repo_root)} "
        f"--feature-placement-hashes {rel(feature_hashes_path, repo_root)} "
        f"--label-placement-hashes {rel(label_hashes_path, repo_root)} "
        f"--report-root {report_root} "
        "--profile-config configs/alpha_tiered.yaml "
        "--models-config configs/models.yaml "
        "--expected-profile tier_1 "
        f"--expected-prediction-run {expected_prediction_run} "
        "--expected-markets 6E,CL,ES,ZN --expected-years 2023,2024"
    )


def build_report(
    *,
    repo_root: Path,
    split_plan_path: Path,
    split_acceptance_path: Path,
    feature_root: Path,
    feature_manifest_path: Path,
    feature_hashes_path: Path,
    label_hashes_path: Path,
    master_audit_run_status_path: Path,
    master_audit_overview_path: Path,
    reports_root: Path,
    predictions_root: Path,
    expected_prediction_run: str,
    markets: Sequence[str],
    years: Sequence[int],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    split_plan = read_json(split_plan_path)
    split_acceptance = read_json(split_acceptance_path)
    feature_manifest = read_json(feature_manifest_path)
    feature_hashes = read_json(feature_hashes_path)
    label_hashes = read_json(label_hashes_path)
    master_audit_run_status = read_json(master_audit_run_status_path)
    master_audit_overview = read_json(master_audit_overview_path)

    split_scope = validate_hardened_split_scope(split_plan, markets, years)
    record_check(
        checks,
        failures,
        name="hardened_split_exact_scope_and_metadata",
        passed=split_scope["status"] == "PASS",
        observed=split_scope,
        expected="PASS hardened split, exact 4 market folds, validation/test metadata, no modeling approval",
    )

    acceptance = split_acceptance_binding(
        split_plan=split_plan,
        split_acceptance=split_acceptance,
        split_plan_path=split_plan_path,
        repo_root=repo_root,
    )
    if split_acceptance.get("status") != HARDENED_SPLIT_ACCEPTANCE_STATUS:
        acceptance["failures"].append("split acceptance is not hardened acceptance status")
        acceptance["status"] = "FAIL"
    record_check(
        checks,
        failures,
        name="hardened_split_acceptance_bound_to_split",
        passed=acceptance["status"] == "PASS",
        observed=acceptance,
        expected="hardened acceptance PASS and bound to the supplied split plan path/hash",
    )

    manifest = validate_feature_manifest(feature_manifest, feature_root, markets, years, repo_root)
    record_check(
        checks,
        failures,
        name="active_feature_manifest_v2_scope",
        passed=manifest["status"] == "PASS",
        observed=manifest,
        expected="PASS tier_1/tier_1_research manifest with 8 outputs and 114 features",
    )

    active_hashes = validate_active_hashes(
        split_plan=split_plan,
        feature_hashes=feature_hashes,
        label_hashes=label_hashes,
        feature_root=feature_root,
        markets=markets,
        years=years,
        repo_root=repo_root,
    )
    record_check(
        checks,
        failures,
        name="active_v2_label_feature_hashes_match_hardened_split",
        passed=active_hashes["status"] == "PASS",
        observed=active_hashes,
        expected="active feature hashes match split input hashes and v2 label hashes match scope",
    )

    master_audit = validate_master_audit_inputs(master_audit_run_status, master_audit_overview)
    record_check(
        checks,
        failures,
        name="master_audit_phase6_phase7_remain_report_only_not_run",
        passed=master_audit["status"] == "PASS",
        observed=master_audit,
        expected="PASS master-audit run-status/overview inputs with Phase 6 and Phase 7 still NOT_RUN",
    )

    predictions = prediction_scope_check(predictions_root, expected_prediction_run, repo_root)
    record_check(
        checks,
        failures,
        name="no_hardened_phase6_predictions_exist_phase7_deferred",
        passed=predictions["status"] == "PASS",
        observed=predictions,
        expected="no scoped hardened Phase 6 prediction files exist; Phase 7 is deferred",
    )

    status = PASS_STATUS if not failures else FAIL_STATUS
    return {
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
            "phase6_preflight_compatible": status == PASS_STATUS,
            "phase7_decision": predictions["phase7_decision"],
            "wfa_execution_allowed": False,
            "prediction_materialization_allowed": False,
            "phase8_refresh_allowed": False,
        },
        "checks": checks,
        "failures": failures,
        "input_evidence": {
            "split_plan": rel(split_plan_path, repo_root),
            "split_plan_sha256": file_sha256(split_plan_path),
            "split_acceptance": rel(split_acceptance_path, repo_root),
            "split_acceptance_sha256": file_sha256(split_acceptance_path),
            "feature_manifest": rel(feature_manifest_path, repo_root),
            "feature_manifest_sha256": file_sha256(feature_manifest_path),
            "feature_placement_hashes": rel(feature_hashes_path, repo_root),
            "feature_placement_hashes_sha256": file_sha256(feature_hashes_path),
            "label_placement_hashes": rel(label_hashes_path, repo_root),
            "label_placement_hashes_sha256": file_sha256(label_hashes_path),
            "master_audit_run_status": rel(master_audit_run_status_path, repo_root),
            "master_audit_run_status_sha256": file_sha256(master_audit_run_status_path),
            "master_audit_overview": rel(master_audit_overview_path, repo_root),
            "master_audit_overview_sha256": file_sha256(master_audit_overview_path),
        },
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "candidate_phase6_preflight_command_not_approved": candidate_phase6_preflight_command(
            split_plan_path=split_plan_path,
            split_acceptance_path=split_acceptance_path,
            feature_root=feature_root,
            feature_manifest_path=feature_manifest_path,
            feature_hashes_path=feature_hashes_path,
            label_hashes_path=label_hashes_path,
            expected_prediction_run=expected_prediction_run,
            repo_root=repo_root,
        ),
        "non_approval": {
            "wfa_execution": False,
            "prediction_materialization": False,
            "phase8_refresh": False,
            "promotion_or_artifact_freeze": False,
            "final_holdout": False,
            "paper_or_live": False,
            "provider_or_network": False,
            "data_mutation": False,
            "label_or_feature_rebuild": False,
            "active_split_replacement": False,
            "cleanup": False,
            "git_staging_commit_push": False,
            "prop_account_reports": False,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Phase 6 Hardened-Split Compatibility Decision",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Phase 6 preflight compatible: `{summary['phase6_preflight_compatible']}`",
        f"- Phase 7 decision: `{summary['phase7_decision']}`",
        f"- WFA execution allowed: `{summary['wfa_execution_allowed']}`",
        f"- Prediction materialization allowed: `{summary['prediction_materialization_allowed']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['name']}` | `{check['status']}` |")
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in report["failures"]:
            lines.append(f"- {failure}")
    lines.extend(
        [
            "",
            "## Candidate Phase 6 Preflight Command",
            "",
            f"`{report['candidate_phase6_preflight_command_not_approved']}`",
            "",
            "This command is evidence only and is not approved by this decision report.",
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
    (reports_root / REPORT_JSON).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (reports_root / REPORT_MD).write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--split-plan", default=str(DEFAULT_SPLIT_PLAN))
    parser.add_argument("--split-acceptance", default=str(DEFAULT_SPLIT_ACCEPTANCE))
    parser.add_argument("--feature-root", default=str(DEFAULT_FEATURE_ROOT))
    parser.add_argument("--feature-manifest", default=str(DEFAULT_FEATURE_MANIFEST))
    parser.add_argument("--feature-placement-hashes", default=str(DEFAULT_FEATURE_PLACEMENT_HASHES))
    parser.add_argument("--label-placement-hashes", default=str(DEFAULT_LABEL_PLACEMENT_HASHES))
    parser.add_argument("--master-audit-run-status", default=str(DEFAULT_MASTER_AUDIT_RUN_STATUS))
    parser.add_argument("--master-audit-overview", default=str(DEFAULT_MASTER_AUDIT_OVERVIEW))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    parser.add_argument("--predictions-root", default=str(DEFAULT_PREDICTIONS_ROOT))
    parser.add_argument("--expected-prediction-run", default=DEFAULT_EXPECTED_PREDICTION_RUN)
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(
        repo_root=repo_root,
        split_plan_path=resolve_path(repo_root, args.split_plan),
        split_acceptance_path=resolve_path(repo_root, args.split_acceptance),
        feature_root=resolve_path(repo_root, args.feature_root),
        feature_manifest_path=resolve_path(repo_root, args.feature_manifest),
        feature_hashes_path=resolve_path(repo_root, args.feature_placement_hashes),
        label_hashes_path=resolve_path(repo_root, args.label_placement_hashes),
        master_audit_run_status_path=resolve_path(repo_root, args.master_audit_run_status),
        master_audit_overview_path=resolve_path(repo_root, args.master_audit_overview),
        reports_root=reports_root,
        predictions_root=resolve_path(repo_root, args.predictions_root),
        expected_prediction_run=str(args.expected_prediction_run),
        markets=csv_strings(args.markets),
        years=csv_ints(args.years),
    )
    write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"phase7={report['summary']['phase7_decision']} json={reports_root / REPORT_JSON}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
