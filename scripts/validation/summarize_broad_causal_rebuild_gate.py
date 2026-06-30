#!/usr/bin/env python3
"""Summarize the report-only broad causal rebuild gate after source-hash resolution."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_ROOT = Path(
    "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628"
)
DEFAULT_PREBUILD_PLAN = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_prebuild_plan.json"
DEFAULT_READINESS = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_raw_source_readiness.json"
DEFAULT_POLICY_SELECTION = (
    REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_policy_selection.json"
)
DEFAULT_SOURCE_RESOLUTION = (
    REPO_ROOT
    / REVIEW_ROOT
    / "sr_parent_2020_source_download/source_hash_mismatch_resolution.json"
)
DEFAULT_JSON_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_gate_summary.json"
DEFAULT_MARKDOWN_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_gate_summary.md"

FUTURE_ROOT = "data/causal_base_candidates/broad_manifest_527_rebuild_v1"
OUTPUT_STAGE = "broad_causal_rebuild_gate_summary"
GATE_STATUS = "BLOCKED_NO_BUILD_APPROVAL"
GATE_DECISION = "broad_rebuild_blocked"
EXPECTED_ROW_COUNT = 527
EXPECTED_ACTION_REQUIRED = 461
EXPECTED_DEFERRED_POLICY_REVIEW = 66
EXPECTED_READY_INPUT_ONLY = 461
EXPECTED_SOURCE_REFERENCE_FAILURES = 0
EXPECTED_BLOCKED_PAIRS: frozenset[str] = frozenset()
RESOLVED_PAIRS = {"SR1:2020", "SR3:2020"}
SELECTED_OPTION = "continue_block_no_action"

PREBUILD_STAGE = "broad_causal_rebuild_prebuild_plan"
READINESS_STAGE = "broad_causal_raw_source_readiness"
POLICY_SELECTION_STAGE = "broad_causal_source_artifact_policy_selection"
SOURCE_RESOLUTION_STAGE = "sr_parent_2020_source_hash_mismatch_resolution"
SOURCE_RESOLUTION_STATUS = "RESOLVED_FOR_SOURCE_READINESS"
READINESS_SOURCE_FAILURE = "action_required_source_reference_failure"
READINESS_READY_STATUS = "READY_FOR_SEPARATE_BUILD_APPROVAL"

PREBUILD_FALSE_FLAGS = (
    "research_use_allowed",
    "broader_modeling_approved",
    "config_promotion_approved",
    "legacy_restore_approved",
)
READINESS_FALSE_FLAGS = (
    "data_mutation_performed",
    "build_approved",
    "broader_modeling_approved",
    "config_promotion_approved",
    "research_use_allowed",
)
POLICY_SELECTION_FALSE_FLAGS = (
    "data_mutation_performed",
    "build_approved",
    "restore_approved",
    "repair_approved",
    "exclusion_approved",
    "broader_modeling_approved",
    "config_promotion_approved",
    "research_use_allowed",
    "source_action_approved",
)

READINESS_EXPECTED_COUNTS = {
    "action_required_missing_raw": 0,
    "action_required_unreadable_raw": 0,
    "action_required_schema_or_metadata_failure": 0,
    "excluded_from_phase2_not_checked": 0,
}

NON_APPROVAL_TEXT = (
    "This report-only gate summary records that broad_manifest_527_rebuild_v1 "
    "has passed raw/source/hash input readiness but remains blocked until a separate "
    "broad build approval is recorded. It does not approve data mutation, source "
    "repair, source restore, exclusion execution, build execution, cleanup, metrics, "
    "predictions, config promotion, labels, features, WFA, broader modeling, "
    "production/live use, or model promotion."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _require_equal(actual: Any, expected: Any, label: str, failures: list[str]) -> None:
    if actual != expected:
        failures.append(f"{label}={actual!r}, expected {expected!r}")


def _require_false_flags(summary: dict[str, Any], flags: Iterable[str], failures: list[str]) -> None:
    for flag in flags:
        _require_equal(summary.get(flag), False, f"summary.{flag}", failures)


def _summary(payload: dict[str, Any], label: str) -> dict[str, Any]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError(f"{label} missing summary object")
    return summary


def _rows(payload: dict[str, Any], label: str) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"{label} missing rows list")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{label} rows must be JSON objects")
    return rows


def _row_map(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("pair")): row for row in rows}


def validate_prebuild_plan(
    prebuild: dict[str, Any],
    *,
    expected_rows: int,
    expected_action_required: int,
    expected_deferred_policy_review: int,
) -> list[dict[str, Any]]:
    summary = _summary(prebuild, "prebuild plan")
    counts = summary.get("status_counts")
    if not isinstance(counts, dict):
        raise ValueError("prebuild plan missing summary.status_counts object")

    failures: list[str] = []
    _require_equal(summary.get("stage"), PREBUILD_STAGE, "summary.stage", failures)
    _require_equal(summary.get("status"), "ACTION_REQUIRED", "summary.status", failures)
    _require_equal(summary.get("decision"), "rebuild_new_broad_root", "summary.decision", failures)
    _require_equal(summary.get("future_root"), FUTURE_ROOT, "summary.future_root", failures)
    _require_equal(summary.get("expected_rows"), expected_rows, "summary.expected_rows", failures)
    _require_equal(counts.get("ready_for_build"), 0, "summary.status_counts.ready_for_build", failures)
    _require_equal(
        counts.get("action_required"),
        expected_action_required,
        "summary.status_counts.action_required",
        failures,
    )
    _require_equal(
        counts.get("deferred_policy_review"),
        expected_deferred_policy_review,
        "summary.status_counts.deferred_policy_review",
        failures,
    )
    _require_equal(counts.get("excluded_from_phase2"), 0, "summary.status_counts.excluded_from_phase2", failures)
    _require_false_flags(summary, PREBUILD_FALSE_FLAGS, failures)

    rows = _rows(prebuild, "prebuild plan")
    _require_equal(len(rows), expected_rows, "rows.length", failures)
    if failures:
        raise ValueError("prebuild plan invariant failure: " + "; ".join(failures))
    return rows


def validate_readiness(
    readiness: dict[str, Any],
    *,
    expected_rows: int,
    expected_action_required: int,
    expected_deferred_policy_review: int,
    expected_ready_input_only: int,
    expected_source_reference_failures: int,
    expected_blocked_pairs: set[str],
) -> list[dict[str, Any]]:
    summary = _summary(readiness, "raw/source readiness")
    counts = summary.get("readiness_status_counts")
    if not isinstance(counts, dict):
        raise ValueError("raw/source readiness missing summary.readiness_status_counts object")

    failures: list[str] = []
    _require_equal(summary.get("stage"), READINESS_STAGE, "summary.stage", failures)
    _require_equal(summary.get("status"), READINESS_READY_STATUS, "summary.status", failures)
    _require_equal(summary.get("future_root"), FUTURE_ROOT, "summary.future_root", failures)
    _require_equal(summary.get("expected_rows"), expected_rows, "summary.expected_rows", failures)
    _require_equal(
        summary.get("checked_action_required_rows"),
        expected_action_required,
        "summary.checked_action_required_rows",
        failures,
    )
    _require_equal(
        summary.get("deferred_policy_review_rows"),
        expected_deferred_policy_review,
        "summary.deferred_policy_review_rows",
        failures,
    )
    _require_equal(
        counts.get("ready_for_build_input_only"),
        expected_ready_input_only,
        "summary.readiness_status_counts.ready_for_build_input_only",
        failures,
    )
    _require_equal(
        counts.get(READINESS_SOURCE_FAILURE),
        expected_source_reference_failures,
        f"summary.readiness_status_counts.{READINESS_SOURCE_FAILURE}",
        failures,
    )
    _require_equal(
        counts.get("deferred_policy_review_not_checked"),
        expected_deferred_policy_review,
        "summary.readiness_status_counts.deferred_policy_review_not_checked",
        failures,
    )
    for status, expected_count in READINESS_EXPECTED_COUNTS.items():
        _require_equal(counts.get(status), expected_count, f"summary.readiness_status_counts.{status}", failures)
    _require_false_flags(summary, READINESS_FALSE_FLAGS, failures)

    rows = _rows(readiness, "raw/source readiness")
    _require_equal(len(rows), expected_rows, "rows.length", failures)
    blocked_rows = [
        row for row in rows if str(row.get("readiness_status")) == READINESS_SOURCE_FAILURE
    ]
    blocked_pairs = {str(row.get("pair")) for row in blocked_rows}
    _require_equal(blocked_pairs, expected_blocked_pairs, "readiness blocked source pairs", failures)
    for row in blocked_rows:
        pair = str(row.get("pair"))
        _require_equal(row.get("prebuild_status"), "action_required", f"{pair}.prebuild_status", failures)
        _require_equal(row.get("raw_read_performed"), True, f"{pair}.raw_read_performed", failures)
        _require_equal(row.get("raw_path_present"), True, f"{pair}.raw_path_present", failures)
        _require_equal(row.get("source_reference_count"), 1, f"{pair}.source_reference_count", failures)
        references = row.get("source_references")
        if not isinstance(references, list) or len(references) != 1 or not isinstance(references[0], dict):
            failures.append(f"{pair}.source_references must contain exactly one object")
            continue
        reference = references[0]
        _require_equal(reference.get("source_present"), False, f"{pair}.source_present", failures)
        _require_equal(reference.get("actual_sha256"), None, f"{pair}.actual_sha256", failures)
        _require_equal(reference.get("hash_matches"), False, f"{pair}.hash_matches", failures)
        if not str(reference.get("source_file") or "").startswith("data/dbn_sr_parent_candidate/"):
            failures.append(f"{pair}.source_file is not a data/dbn_sr_parent_candidate path")
    if failures:
        raise ValueError("raw/source readiness invariant failure: " + "; ".join(failures))
    return rows


def validate_policy_selection(
    policy_selection: dict[str, Any],
    *,
    historical_pairs: set[str],
) -> list[dict[str, Any]]:
    summary = _summary(policy_selection, "policy selection")
    failures: list[str] = []
    _require_equal(summary.get("stage"), POLICY_SELECTION_STAGE, "summary.stage", failures)
    _require_equal(summary.get("status"), "ACTION_REQUIRED", "summary.status", failures)
    _require_equal(summary.get("selected_decision_option"), SELECTED_OPTION, "summary.selected_decision_option", failures)
    _require_equal(summary.get("human_decision_recorded"), True, "summary.human_decision_recorded", failures)
    _require_equal(summary.get("approved_action"), "none", "summary.approved_action", failures)
    _require_equal(summary.get("pair_count"), len(historical_pairs), "summary.pair_count", failures)
    _require_equal(set(summary.get("pairs", [])), historical_pairs, "summary.pairs", failures)
    _require_false_flags(summary, POLICY_SELECTION_FALSE_FLAGS, failures)

    rows = _rows(policy_selection, "policy selection")
    _require_equal(len(rows), len(historical_pairs), "rows.length", failures)
    row_pairs = {str(row.get("pair")) for row in rows}
    _require_equal(row_pairs, historical_pairs, "row.pairs", failures)
    for row in rows:
        pair = str(row.get("pair"))
        _require_equal(row.get("selected_decision_option"), SELECTED_OPTION, f"{pair}.selected_decision_option", failures)
        _require_equal(row.get("human_decision_recorded"), True, f"{pair}.human_decision_recorded", failures)
        _require_equal(row.get("approved_action"), "none", f"{pair}.approved_action", failures)
        _require_equal(row.get("policy_status"), "ACTION_REQUIRED", f"{pair}.policy_status", failures)
        _require_equal(
            row.get("input_disposition_status"),
            "blocked_missing_current_source_artifact",
            f"{pair}.input_disposition_status",
            failures,
        )
        _require_equal(row.get("source_file_present"), False, f"{pair}.source_file_present", failures)
    if failures:
        raise ValueError("policy selection invariant failure: " + "; ".join(failures))
    return rows


def validate_source_resolution(
    source_resolution: dict[str, Any],
    *,
    expected_ready_input_only: int,
    expected_source_reference_failures: int,
    expected_deferred_policy_review: int,
    resolved_pairs: set[str],
) -> list[dict[str, Any]]:
    failures: list[str] = []
    _require_equal(
        source_resolution.get("stage"),
        SOURCE_RESOLUTION_STAGE,
        "source_resolution.stage",
        failures,
    )
    _require_equal(
        source_resolution.get("status"),
        SOURCE_RESOLUTION_STATUS,
        "source_resolution.status",
        failures,
    )

    scope = source_resolution.get("scope")
    if not isinstance(scope, dict):
        failures.append("source_resolution.scope missing object")
    else:
        _require_equal(set(scope.get("rows", [])), resolved_pairs, "source_resolution.scope.rows", failures)

    post_repair = source_resolution.get("post_repair_readiness")
    if not isinstance(post_repair, dict):
        failures.append("source_resolution.post_repair_readiness missing object")
    else:
        _require_equal(
            post_repair.get("status"),
            READINESS_READY_STATUS,
            "source_resolution.post_repair_readiness.status",
            failures,
        )
        _require_equal(
            post_repair.get("ready_for_build_input_only"),
            expected_ready_input_only,
            "source_resolution.post_repair_readiness.ready_for_build_input_only",
            failures,
        )
        _require_equal(
            post_repair.get(READINESS_SOURCE_FAILURE),
            expected_source_reference_failures,
            f"source_resolution.post_repair_readiness.{READINESS_SOURCE_FAILURE}",
            failures,
        )
        _require_equal(
            post_repair.get("deferred_policy_review_not_checked"),
            expected_deferred_policy_review,
            "source_resolution.post_repair_readiness.deferred_policy_review_not_checked",
            failures,
        )
        for pair in sorted(resolved_pairs):
            _require_equal(
                post_repair.get(pair),
                "ready_for_build_input_only",
                f"source_resolution.post_repair_readiness.{pair}",
                failures,
            )

    approval_flags = source_resolution.get("approval_flags")
    if not isinstance(approval_flags, dict):
        failures.append("source_resolution.approval_flags missing object")
    else:
        _require_false_flags(
            approval_flags,
            (
                "build_approved",
                "broader_modeling_approved",
                "config_promotion_approved",
                "research_use_allowed",
                "wfa_modeling_approved",
                "metrics_approved",
            ),
            failures,
        )

    repairs = source_resolution.get("repairs")
    if not isinstance(repairs, list) or not all(isinstance(item, dict) for item in repairs):
        failures.append("source_resolution.repairs must be a list of objects")
        repairs = []
    repair_pairs = {str(item.get("pair")) for item in repairs}
    _require_equal(repair_pairs, resolved_pairs, "source_resolution.repairs.pairs", failures)
    for repair in repairs:
        pair = str(repair.get("pair"))
        if not str(repair.get("source_file") or "").startswith("data/dbn_sr_parent_candidate/"):
            failures.append(f"{pair}.source_file is not a data/dbn_sr_parent_candidate path")
        if not str(repair.get("raw_path") or "").startswith("data/raw/"):
            failures.append(f"{pair}.raw_path is not a data/raw path")
        for field in ("new_source_sha256", "new_raw_parquet_sha256"):
            value = str(repair.get(field) or "")
            if len(value) != 64:
                failures.append(f"{pair}.{field} is not a SHA256 hex string")

    if failures:
        raise ValueError("source resolution invariant failure: " + "; ".join(failures))
    return repairs


def _resolved_gate_rows(
    *,
    readiness_rows: list[dict[str, Any]],
    source_repairs: list[dict[str, Any]],
    resolved_pairs: set[str],
) -> list[dict[str, Any]]:
    readiness_by_pair = _row_map(readiness_rows)
    failures: list[str] = []
    output_rows: list[dict[str, Any]] = []
    for repair in sorted(source_repairs, key=lambda item: str(item.get("pair"))):
        pair = str(repair.get("pair"))
        if pair not in resolved_pairs:
            failures.append(f"{pair} is not an expected resolved pair")
            continue
        readiness_row = readiness_by_pair[pair]
        references = readiness_row.get("source_references")
        if not isinstance(references, list) or len(references) != 1 or not isinstance(references[0], dict):
            failures.append(f"{pair}.source_references must contain exactly one object")
            continue
        reference = references[0]
        _require_equal(readiness_row.get("readiness_status"), "ready_for_build_input_only", f"{pair}.readiness_status", failures)
        _require_equal(reference.get("source_present"), True, f"{pair}.source_present", failures)
        _require_equal(reference.get("hash_matches"), True, f"{pair}.hash_matches", failures)
        _require_equal(reference.get("source_file"), repair.get("source_file"), f"{pair}.source_file", failures)
        _require_equal(
            readiness_row.get("raw_parquet_row_count"),
            repair.get("row_count"),
            f"{pair}.row_count",
            failures,
        )
        _require_equal(
            readiness_row.get("raw_parquet_sha256"),
            repair.get("new_raw_parquet_sha256"),
            f"{pair}.raw_parquet_sha256",
            failures,
        )
        _require_equal(
            reference.get("actual_sha256"),
            repair.get("new_source_sha256"),
            f"{pair}.actual_sha256",
            failures,
        )
        output_rows.append(
            {
                "pair": pair,
                "market": readiness_row.get("market"),
                "year": readiness_row.get("year"),
                "planned_input_raw_path": readiness_row.get("planned_input_raw_path"),
                "planned_output_causal_path": readiness_row.get("planned_output_causal_path"),
                "raw_parquet_sha256": readiness_row.get("raw_parquet_sha256"),
                "raw_parquet_row_count": readiness_row.get("raw_parquet_row_count"),
                "source_file": reference.get("source_file"),
                "source_sha256": reference.get("actual_sha256"),
                "source_present": reference.get("source_present"),
                "hash_matches": reference.get("hash_matches"),
                "readiness_status": readiness_row.get("readiness_status"),
                "resolution_status": SOURCE_RESOLUTION_STATUS,
                "blockers": sorted(str(item) for item in readiness_row.get("blockers", [])),
            }
        )
    if failures:
        raise ValueError("cross-report resolved row invariant failure: " + "; ".join(failures))
    return output_rows


def build_report(
    *,
    repo_root: Path,
    prebuild_plan_path: Path,
    readiness_path: Path,
    policy_selection_path: Path,
    source_resolution_path: Path,
    generated_at_utc: str | None = None,
    expected_rows: int = EXPECTED_ROW_COUNT,
    expected_action_required: int = EXPECTED_ACTION_REQUIRED,
    expected_deferred_policy_review: int = EXPECTED_DEFERRED_POLICY_REVIEW,
    expected_ready_input_only: int = EXPECTED_READY_INPUT_ONLY,
    expected_source_reference_failures: int = EXPECTED_SOURCE_REFERENCE_FAILURES,
    expected_blocked_pairs: set[str] | frozenset[str] = EXPECTED_BLOCKED_PAIRS,
    resolved_pairs: set[str] = RESOLVED_PAIRS,
) -> dict[str, Any]:
    prebuild = read_json(prebuild_plan_path)
    readiness = read_json(readiness_path)
    policy_selection = read_json(policy_selection_path)
    source_resolution = read_json(source_resolution_path)

    prebuild_rows = validate_prebuild_plan(
        prebuild,
        expected_rows=expected_rows,
        expected_action_required=expected_action_required,
        expected_deferred_policy_review=expected_deferred_policy_review,
    )
    readiness_rows = validate_readiness(
        readiness,
        expected_rows=expected_rows,
        expected_action_required=expected_action_required,
        expected_deferred_policy_review=expected_deferred_policy_review,
        expected_ready_input_only=expected_ready_input_only,
        expected_source_reference_failures=expected_source_reference_failures,
        expected_blocked_pairs=set(expected_blocked_pairs),
    )
    selection_rows = validate_policy_selection(
        policy_selection,
        historical_pairs=resolved_pairs,
    )
    source_repairs = validate_source_resolution(
        source_resolution,
        expected_ready_input_only=expected_ready_input_only,
        expected_source_reference_failures=expected_source_reference_failures,
        expected_deferred_policy_review=expected_deferred_policy_review,
        resolved_pairs=resolved_pairs,
    )

    prebuild_summary = prebuild["summary"]
    readiness_summary = readiness["summary"]
    selection_summary = policy_selection["summary"]
    resolved_rows = _resolved_gate_rows(
        readiness_rows=readiness_rows,
        source_repairs=source_repairs,
        resolved_pairs=resolved_pairs,
    )
    prebuild_counts = dict(prebuild_summary["status_counts"])
    readiness_counts = dict(readiness_summary["readiness_status_counts"])

    return {
        "summary": {
            "stage": OUTPUT_STAGE,
            "status": GATE_STATUS,
            "gate_decision": GATE_DECISION,
            "block_reason": "raw_source_hash_readiness_passed_but_separate_broad_build_approval_missing",
            "future_root": FUTURE_ROOT,
            "expected_rows": expected_rows,
            "prebuild_action_required_rows": prebuild_counts["action_required"],
            "prebuild_deferred_policy_review_rows": prebuild_counts["deferred_policy_review"],
            "ready_for_build_rows": prebuild_counts["ready_for_build"],
            "raw_source_readiness_status": readiness_summary["status"],
            "input_only_ready_rows": readiness_counts["ready_for_build_input_only"],
            "blocked_source_artifact_rows": readiness_counts[READINESS_SOURCE_FAILURE],
            "blocked_pairs": [],
            "resolved_source_hash_pairs": [row["pair"] for row in resolved_rows],
            "historical_policy_selection": selection_summary["selected_decision_option"],
            "approved_action": selection_summary["approved_action"],
            "generated_at_utc": generated_at_utc or utc_now(),
            "data_access": "read_existing_report_artifacts_only",
            "data_mutation_performed": False,
            "build_approved": False,
            "restore_approved": False,
            "repair_approved": False,
            "exclusion_approved": False,
            "source_action_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
            "non_approval": NON_APPROVAL_TEXT,
        },
        "input_reports": {
            "prebuild_plan": rel(prebuild_plan_path, repo_root),
            "prebuild_plan_sha256": sha256_file(prebuild_plan_path),
            "raw_source_readiness": rel(readiness_path, repo_root),
            "raw_source_readiness_sha256": sha256_file(readiness_path),
            "policy_selection": rel(policy_selection_path, repo_root),
            "policy_selection_sha256": sha256_file(policy_selection_path),
            "source_hash_mismatch_resolution": rel(source_resolution_path, repo_root),
            "source_hash_mismatch_resolution_sha256": sha256_file(source_resolution_path),
        },
        "upstream_counts": {
            "prebuild_status_counts": prebuild_counts,
            "readiness_status_counts": readiness_counts,
            "policy_selection_pair_count": selection_summary["pair_count"],
            "source_resolution_pair_count": len(source_repairs),
            "prebuild_row_count": len(prebuild_rows),
        },
        "gate_requirements": {
            "required_historical_policy_selection": SELECTED_OPTION,
            "required_source_resolution_status": SOURCE_RESOLUTION_STATUS,
            "required_approved_action": "none",
            "required_blocked_pairs": sorted(expected_blocked_pairs),
            "required_resolved_source_hash_pairs": sorted(resolved_pairs),
            "required_ready_for_build_rows": 0,
            "required_blocked_source_artifact_rows": expected_source_reference_failures,
            "required_approval_flags": {
                "data_mutation_performed": False,
                "build_approved": False,
                "restore_approved": False,
                "repair_approved": False,
                "exclusion_approved": False,
                "source_action_approved": False,
                "broader_modeling_approved": False,
                "config_promotion_approved": False,
                "research_use_allowed": False,
            },
        },
        "resolved_source_hash_rows": resolved_rows,
        "blocked_rows": [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Broad Manifest 527 Rebuild Gate Summary",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: report-only broad_manifest_527_rebuild_v1 gate summary.",
        f"- Status: `{summary['status']}`.",
        f"- Gate decision: `{summary['gate_decision']}`.",
        f"- Block reason: `{summary['block_reason']}`.",
        f"- Future root: `{summary['future_root']}`.",
        f"- Expected rows: {summary['expected_rows']}.",
        f"- Ready-for-build rows: {summary['ready_for_build_rows']}.",
        f"- Raw/source readiness status: `{summary['raw_source_readiness_status']}`.",
        f"- Input-only ready rows: {summary['input_only_ready_rows']}.",
        f"- Blocked source-artifact rows: {summary['blocked_source_artifact_rows']}.",
        f"- Blocked pairs: `{', '.join(summary['blocked_pairs'])}`.",
        f"- Resolved source-hash pairs: `{', '.join(summary['resolved_source_hash_pairs'])}`.",
        f"- Historical policy selection: `{summary['historical_policy_selection']}`.",
        f"- Approved action: `{summary['approved_action']}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Non-Approval",
        "",
        f"- {summary['non_approval']}",
        "- `data_mutation_performed`: false.",
        "- `build_approved`: false.",
        "- `restore_approved`: false.",
        "- `repair_approved`: false.",
        "- `exclusion_approved`: false.",
        "- `source_action_approved`: false.",
        "- `broader_modeling_approved`: false.",
        "- `config_promotion_approved`: false.",
        "- `research_use_allowed`: false.",
        "",
        "## Upstream Counts",
        "",
        f"- Prebuild status counts: `{json.dumps(report['upstream_counts']['prebuild_status_counts'], sort_keys=True)}`.",
        f"- Readiness status counts: `{json.dumps(report['upstream_counts']['readiness_status_counts'], sort_keys=True)}`.",
        "",
        "## Resolved Source Hash Rows",
        "",
        "| pair | readiness status | source present | hash matches | resolution status | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["resolved_source_hash_rows"]:
        blockers = "; ".join(str(item) for item in row.get("blockers", []))
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['readiness_status']}` | "
            f"{str(row['source_present']).lower()} | "
            f"{str(row['hash_matches']).lower()} | "
            f"`{row['resolution_status']}` | "
            f"{blockers} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--prebuild-plan", default=str(DEFAULT_PREBUILD_PLAN))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--policy-selection", default=str(DEFAULT_POLICY_SELECTION))
    parser.add_argument("--source-resolution", default=str(DEFAULT_SOURCE_RESOLUTION))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    prebuild_plan = resolve_path(repo_root, args.prebuild_plan)
    readiness = resolve_path(repo_root, args.readiness)
    policy_selection = resolve_path(repo_root, args.policy_selection)
    source_resolution = resolve_path(repo_root, args.source_resolution)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        report = build_report(
            repo_root=repo_root,
            prebuild_plan_path=prebuild_plan,
            readiness_path=readiness,
            policy_selection_path=policy_selection,
            source_resolution_path=source_resolution,
        )
    except ValueError as exc:
        print(f"FAIL broad_causal_rebuild_gate_summary: {exc}")
        return 1
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "broad_causal_rebuild_gate_summary "
        f"status={summary['status']} "
        f"gate_decision={summary['gate_decision']} "
        f"ready_for_build_rows={summary['ready_for_build_rows']} "
        f"blocked_source_artifact_rows={summary['blocked_source_artifact_rows']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
