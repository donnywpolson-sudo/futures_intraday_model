#!/usr/bin/env python3
"""Summarize the ES 2026 P1 gate chain and current approval boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_es2026_p1_candidate_conversion_plan as conversion_plan  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_candidate_conversion_review as conversion_review  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_plan as readiness_plan  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_review as readiness_review  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_dry_run_review as dry_run_review  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_feature_gate as downstream_feature_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_label_gate as downstream_label_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_metrics_gate as downstream_metrics_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_metrics_review as downstream_metrics_review_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_model_gate as downstream_model_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_wfa_split_gate as downstream_wfa_split_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_optional_archive_availability as availability_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402
from scripts.validation import build_local_trade_optional_archive_inventory as optional_inventory_gate  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_candidate_conversion as conversion_runner  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_candidate_readiness as readiness_runner  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_dry_run_diagnostics as dry_run_runner  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_feature_build as downstream_feature_runner  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_label_build as downstream_label_runner  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_metrics_build as downstream_metrics_runner  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_model_build as downstream_model_runner  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_wfa_split_build as downstream_wfa_split_runner  # noqa: E402


STAGE = "local_trade_es2026_p1_workflow_status"
STATUS_ACTION_REQUIRED = "ACTION_REQUIRED_ES2026_P1_WORKFLOW_STATUS"
STATUS_REVIEW_READY = "REVIEW_READY_ES2026_P1_WORKFLOW_STATUS"
STATUS_NO_GO = "NO_GO_ES2026_P1_WORKFLOW_STATUS"
DECISION_STATUS_ONLY = "es2026_p1_workflow_status_only_no_execution"
DECISION_BLOCKED = "es2026_p1_workflow_status_blocked"

TARGET_MARKET = repair_plan_gate.TARGET_MARKET
TARGET_YEAR = repair_plan_gate.TARGET_YEAR
FALSE_APPROVAL_FLAGS = tuple(
    dict.fromkeys(
        (
            *downstream_metrics_gate.FALSE_APPROVAL_FLAGS,
            "promotion_or_freeze_approved",
        )
    )
)
DEFAULT_OPTIONAL_DBN_ROOT = optional_inventory_gate.DEFAULT_DBN_ROOT

DRY_RUN_APPROVAL_COMMAND = (
    "python -m scripts.validation.run_local_trade_es2026_p1_dry_run_diagnostics "
    "--execute --approval-token "
    f"{dry_run_runner.APPROVAL_TOKEN}"
)
CANDIDATE_CONVERSION_APPROVAL_COMMAND = (
    "python -m scripts.validation.run_local_trade_es2026_p1_candidate_conversion "
    "--execute --approval-token "
    f"{conversion_runner.APPROVAL_TOKEN}"
)
CANDIDATE_READINESS_APPROVAL_COMMAND = (
    "python -m scripts.validation.run_local_trade_es2026_p1_candidate_readiness "
    "--execute --approval-token "
    f"{readiness_runner.APPROVAL_TOKEN}"
)
DOWNSTREAM_LABEL_APPROVAL_COMMAND = (
    "python -m scripts.validation.run_local_trade_es2026_p1_downstream_label_build "
    "--execute --approval-token "
    f"{downstream_label_runner.APPROVAL_TOKEN}"
)
DOWNSTREAM_FEATURE_APPROVAL_COMMAND = (
    "python -m scripts.validation.run_local_trade_es2026_p1_downstream_feature_build "
    "--execute --approval-token "
    f"{downstream_feature_runner.APPROVAL_TOKEN}"
)
DOWNSTREAM_WFA_SPLIT_APPROVAL_COMMAND = (
    "python -m scripts.validation.run_local_trade_es2026_p1_downstream_wfa_split_build "
    "--execute --approval-token "
    f"{downstream_wfa_split_runner.APPROVAL_TOKEN}"
)
DOWNSTREAM_MODEL_APPROVAL_COMMAND = (
    "python -m scripts.validation.run_local_trade_es2026_p1_downstream_model_build "
    "--execute --approval-token "
    f"{downstream_model_runner.APPROVAL_TOKEN}"
)
DOWNSTREAM_METRICS_APPROVAL_COMMAND = (
    "python -m scripts.validation.run_local_trade_es2026_p1_downstream_metrics_build "
    "--execute --approval-token "
    f"{downstream_metrics_runner.APPROVAL_TOKEN}"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return repair_plan_gate.rel(path, repo_root)


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


def _git_staged_generated_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "data", "reports"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --cached failed")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _check(
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


def _summary(report: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = report.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _summary_count(summary: Mapping[str, Any], names: Iterable[str]) -> int:
    for name in names:
        value = summary.get(name)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _gate_record(name: str, report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "gate": name,
        "stage": summary.get("stage"),
        "status": summary.get("status"),
        "failure_count": summary.get("failure_count"),
        "market_count": summary.get("market_count"),
        "ready_market_count": summary.get("ready_market_count"),
        "invalid_archive_count": summary.get("invalid_archive_count"),
        "expected_output_count": _summary_count(
            summary,
            (
                "expected_generated_output_count",
                "expected_candidate_output_count",
                "expected_readiness_output_count",
                "planned_generated_artifact_count",
            ),
        ),
        "ignored_expected_output_count": _summary_count(
            summary,
            (
                "ignored_expected_generated_output_count",
                "ignored_expected_candidate_output_count",
                "ignored_expected_readiness_output_count",
                "ignored_planned_generated_artifact_count",
                "ignored_plan_count",
            ),
        ),
        "unignored_expected_output_count": _summary_count(
            summary,
            (
                "unignored_expected_generated_output_count",
                "unignored_expected_candidate_output_count",
                "unignored_expected_readiness_output_count",
                "unignored_planned_generated_artifact_count",
                "unignored_plan_count",
            ),
        ),
        "existing_expected_output_count": _summary_count(
            summary,
            (
                "existing_expected_generated_output_count",
                "existing_expected_candidate_output_count",
                "existing_expected_readiness_output_count",
            ),
        ),
        "generated_output_count": summary.get("generated_output_count"),
        "staged_generated_path_count": summary.get("staged_generated_path_count"),
        "recommended_next_action": summary.get("recommended_next_action"),
    }


def _expected_outputs_already_exist(summary: Mapping[str, Any]) -> bool:
    expected = _summary_count(
        summary,
        (
            "expected_generated_output_count",
            "expected_candidate_output_count",
            "expected_readiness_output_count",
        ),
    )
    existing = _summary_count(
        summary,
        (
            "existing_expected_generated_output_count",
            "existing_expected_candidate_output_count",
            "existing_expected_readiness_output_count",
        ),
    )
    return expected > 0 and existing >= expected


def _planned_command_records(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    records = [
        command for command in report.get("planned_commands", []) if isinstance(command, Mapping)
    ]
    single = report.get("planned_command")
    if isinstance(single, Mapping):
        records.append(single)
    return records


def _dry_run_expected_artifacts(report: Mapping[str, Any]) -> list[str]:
    artifacts: list[str] = []
    for command in _planned_command_records(report):
        raw_paths = command.get("expected_generated_artifacts")
        if isinstance(raw_paths, list):
            artifacts.extend(str(path) for path in raw_paths)
    return sorted(set(artifacts))


def _dry_run_bounded_plan(report: Mapping[str, Any]) -> dict[str, Any]:
    commands = _planned_command_records(report)
    schemas = sorted({str(command.get("schema")) for command in commands if command.get("schema")})
    timeouts = sorted(
        {
            int(command["timeout_seconds"])
            for command in commands
            if command.get("timeout_seconds") is not None
        }
    )
    return {
        "command_family": "phase1a_download_dry_run_only",
        "command_count": len(commands),
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "schemas": schemas,
            "start": repair_plan_gate.TARGET_START,
            "end": repair_plan_gate.TARGET_END,
            "network": False,
            "data_mutation": False,
        },
        "timeout_seconds_per_command": timeouts[0] if len(timeouts) == 1 else None,
        "timeout_seconds_values": timeouts,
        "expected_generated_artifacts": _dry_run_expected_artifacts(report),
        "forbidden_patterns": list(repair_plan_gate.FORBIDDEN_PATTERNS),
        "forbidden_argument_flags": sorted(dry_run_runner.FORBIDDEN_ARG_FLAGS),
        "stop_condition": (
            "Stop unless both generated dry-run plans are exactly ES 2026 status/statistics, "
            "all expected generated artifacts are ignored and unstaged, and no provider download, "
            "cost-estimate, data-mutation, or non-dry-run path is invoked."
        ),
    }


def _availability_expected_artifacts(report: Mapping[str, Any]) -> list[str]:
    paths = report.get("planned_generated_artifacts")
    if not isinstance(paths, list):
        return []
    return sorted(str(path) for path in paths if str(path))


def _availability_bounded_plan(report: Mapping[str, Any]) -> dict[str, Any]:
    items = [
        item for item in report.get("availability_items", []) if isinstance(item, Mapping)
    ]
    schemas = sorted({str(item.get("schema")) for item in items if item.get("schema")})
    archive_paths = sorted(str(item.get("archive_path")) for item in items if item.get("archive_path"))
    manifest_paths = sorted(str(item.get("manifest_path")) for item in items if item.get("manifest_path"))
    return {
        "command_family": "optional_archive_acquisition_or_provider_cost_diagnostic",
        "command_count": 0,
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "schemas": schemas,
            "planned_archive_paths": archive_paths,
            "planned_manifest_paths": manifest_paths,
            "network": "separate_approval_required",
            "data_mutation": "separate_approval_required",
        },
        "timeout_seconds_per_command": 180,
        "timeout_seconds_values": [180],
        "expected_generated_artifacts": _availability_expected_artifacts(report),
        "forbidden_patterns": list(repair_plan_gate.FORBIDDEN_PATTERNS),
        "forbidden_argument_flags": sorted(dry_run_runner.FORBIDDEN_ARG_FLAGS),
        "stop_condition": (
            "Stop unless the decision is limited to ES 2026 status/statistics optional archives, "
            "all planned archive and manifest outputs are ignored and unstaged, and no provider "
            "download, cost estimate, candidate raw conversion, readiness rerun, causal build, "
            "labels/features, WFA/modeling, proof scan, staging, commit, push, or live/paper path "
            "runs without separate approval."
        ),
    }


def _planned_command_bounded_plan(
    report: Mapping[str, Any],
    *,
    maximum_scope: Mapping[str, Any],
    stop_condition: str,
) -> dict[str, Any]:
    commands = _planned_command_records(report)
    command_families = sorted(
        {str(command.get("command_family")) for command in commands if command.get("command_family")}
    )
    timeouts = sorted(
        {
            int(command["timeout_seconds"])
            for command in commands
            if command.get("timeout_seconds") is not None
        }
    )
    return {
        "command_family": ",".join(command_families),
        "command_count": len(commands),
        "maximum_scope": dict(maximum_scope),
        "timeout_seconds_per_command": timeouts[0] if len(timeouts) == 1 else None,
        "timeout_seconds_values": timeouts,
        "expected_generated_artifacts": _dry_run_expected_artifacts(report),
        "forbidden_patterns": list(repair_plan_gate.FORBIDDEN_PATTERNS),
        "stop_condition": stop_condition,
    }


def _boundary_requires_bounded_plan(boundary: Mapping[str, Any]) -> bool:
    return bool(
        boundary.get("approval_token")
        or boundary.get("recommended_command")
        or boundary.get("expected_generated_artifacts")
    )


def _bounded_plan_missing_fields(boundary: Mapping[str, Any]) -> list[str]:
    if not _boundary_requires_bounded_plan(boundary):
        return []
    plan = boundary.get("bounded_plan")
    if not isinstance(plan, Mapping) or not plan:
        return ["bounded_plan"]
    missing: list[str] = []
    for field in (
        "command_family",
        "maximum_scope",
        "expected_generated_artifacts",
        "forbidden_patterns",
        "stop_condition",
    ):
        if not plan.get(field):
            missing.append(field)
    if plan.get("timeout_seconds_per_command") is None and not plan.get("timeout_seconds_values"):
        missing.append("timeout_seconds")
    boundary_artifacts = sorted(str(path) for path in boundary.get("expected_generated_artifacts") or [])
    plan_artifacts = sorted(str(path) for path in plan.get("expected_generated_artifacts") or [])
    if boundary_artifacts and plan_artifacts != boundary_artifacts:
        missing.append("expected_generated_artifacts_match")
    return missing


def _normalize_artifact_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _boundary_artifact_counts(
    *,
    expected_artifacts: list[str],
    current_gate_record: Mapping[str, Any],
    ignored_generated_paths: list[str] | None,
) -> tuple[int, int, int]:
    expected = sorted({_normalize_artifact_path(path) for path in expected_artifacts if str(path)})
    if not expected:
        return 0, 0, 0
    if ignored_generated_paths is not None:
        ignored = {_normalize_artifact_path(path) for path in ignored_generated_paths if str(path)}
        ignored_expected = sorted(set(expected) & ignored)
        unignored_expected = sorted(set(expected) - ignored)
        return len(expected), len(ignored_expected), len(unignored_expected)
    return (
        len(expected),
        int(current_gate_record.get("ignored_expected_output_count") or 0),
        int(current_gate_record.get("unignored_expected_output_count") or 0),
    )


def _approval_boundary(
    *,
    gate: str,
    stage: str,
    status: str,
    action_kind: str,
    recommended_action: str,
    command: str | None = None,
    approval_token: str | None = None,
    expected_artifacts: list[str] | None = None,
    bounded_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "gate": gate,
        "stage": stage,
        "status": status,
        "next_action_kind": action_kind,
        "human_approval_required": True,
        "approval_token": approval_token,
        "recommended_command": command,
        "expected_generated_artifacts": expected_artifacts or [],
        "bounded_plan": dict(bounded_plan or {}),
        "recommended_action": recommended_action,
    }


def _no_go_boundary(*, gate: str, report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "gate": gate,
        "stage": summary.get("stage"),
        "status": summary.get("status"),
        "next_action_kind": "fix_or_repair_gate",
        "human_approval_required": False,
        "approval_token": None,
        "recommended_command": None,
        "expected_generated_artifacts": [],
        "recommended_action": summary.get("recommended_next_action"),
    }


def _common_kwargs(
    *,
    repo_root: Path,
    work_order_report: Path,
    drilldown_report: Path,
    checkpoint_jsonl: Path,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    output_root: Path,
    raw_alignment_report: Path,
    generated_at_utc: str | None,
    staged_paths: list[str],
    ignored_paths: list[str] | None,
) -> dict[str, Any]:
    kwargs = {
        "repo_root": repo_root,
        "work_order_report": work_order_report,
        "drilldown_report": drilldown_report,
        "checkpoint_jsonl": checkpoint_jsonl,
        "repair_reports_root": repair_reports_root,
        "candidate_raw_root": candidate_raw_root,
        "output_root": output_root,
        "raw_alignment_report": raw_alignment_report,
        "generated_at_utc": generated_at_utc,
        "staged_generated_paths": staged_paths,
    }
    if ignored_paths is not None:
        kwargs["ignored_generated_paths"] = ignored_paths
    return kwargs


def _recommended_next(boundary: Mapping[str, Any], status: str) -> str:
    if status == STATUS_REVIEW_READY:
        return (
            "Review whether ES 2026 candidate readiness evidence justifies a separate bounded "
            "causal-base repair/build proposal; do not build causal data, labels, features, "
            "WFA, proof scans, or promotions without approval."
        )
    if boundary.get("recommended_command"):
        return str(boundary["recommended_command"])
    action = boundary.get("recommended_action")
    return str(action) if action else "Resolve the current ES 2026 P1 workflow gate before continuing."


def _optional_inventory_evidence(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "stage": summary.get("stage"),
        "status": summary.get("status"),
        "year": summary.get("year"),
        "start": summary.get("start"),
        "end": summary.get("end"),
        "schemas": summary.get("schemas"),
        "market_count": summary.get("market_count"),
        "expected_market_count": summary.get("expected_market_count"),
        "ready_market_count": summary.get("ready_market_count"),
        "invalid_market_count": summary.get("invalid_market_count"),
        "archive_count": summary.get("archive_count"),
        "invalid_archive_count": summary.get("invalid_archive_count"),
        "generated_output_count": summary.get("generated_output_count"),
        "staged_generated_path_count": summary.get("staged_generated_path_count"),
        "failure_count": summary.get("failure_count"),
    }


def build_report(
    *,
    repo_root: Path,
    work_order_report: Path,
    drilldown_report: Path,
    checkpoint_jsonl: Path,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    output_root: Path,
    raw_alignment_report: Path,
    optional_dbn_root: Path | None = None,
    optional_archive_inventory_report: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    gates: list[dict[str, Any]] = []
    boundary: dict[str, Any] | None = None
    status = STATUS_ACTION_REQUIRED

    optional_inventory = optional_archive_inventory_report or optional_inventory_gate.build_report(
        repo_root=repo_root,
        dbn_root=optional_dbn_root or resolve_path(repo_root, DEFAULT_OPTIONAL_DBN_ROOT),
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_paths,
    )
    optional_inventory_evidence = _optional_inventory_evidence(optional_inventory)
    gates.append(_gate_record("optional_archive_inventory", optional_inventory))

    common_kwargs = _common_kwargs(
        repo_root=repo_root,
        work_order_report=work_order_report,
        drilldown_report=drilldown_report,
        checkpoint_jsonl=checkpoint_jsonl,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc=generated_at_utc,
        staged_paths=staged_paths,
        ignored_paths=None,
    )

    repair_plan = repair_plan_gate.build_report(**common_kwargs)
    gates.append(_gate_record("repair_plan", repair_plan))
    if _summary(repair_plan).get("status") != repair_plan_gate.STATUS_READY:
        status = STATUS_NO_GO
        boundary = _no_go_boundary(gate="repair_plan", report=repair_plan)

    dry_run = dry_run_runner.build_report(
        **_common_kwargs(
            repo_root=repo_root,
            work_order_report=work_order_report,
            drilldown_report=drilldown_report,
            checkpoint_jsonl=checkpoint_jsonl,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
            generated_at_utc=generated_at_utc,
            staged_paths=staged_paths,
            ignored_paths=ignored_generated_paths,
        ),
        execute=False,
    )
    gates.append(_gate_record("dry_run_diagnostics_execution", dry_run))
    dry_review = dry_run_review.build_report(
        repo_root=repo_root,
        repair_reports_root=repair_reports_root,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_paths,
    )
    gates.append(_gate_record("dry_run_review", dry_review))
    if boundary is None and _summary(dry_review).get("status") != dry_run_review.STATUS_READY:
        if _summary(dry_run).get("status") == dry_run_runner.STATUS_DRY_RUN_READY:
            boundary = _approval_boundary(
                gate="dry_run_diagnostics_execution",
                stage=dry_run_runner.STAGE,
                status=dry_run_runner.STATUS_DRY_RUN_READY,
                action_kind="approve_bounded_generated_dry_run_plans",
                recommended_action=(
                    "Approve or reject bounded ES 2026 P1 optional status/statistics dry-run "
                    "diagnostic wrapper execution only."
                ),
                command=DRY_RUN_APPROVAL_COMMAND,
                approval_token=dry_run_runner.APPROVAL_TOKEN,
                expected_artifacts=_dry_run_expected_artifacts(dry_run),
                bounded_plan=_dry_run_bounded_plan(dry_run),
            )
        else:
            status = STATUS_NO_GO
            boundary = _no_go_boundary(gate="dry_run_diagnostics_execution", report=dry_run)

    availability = availability_gate.build_report(
        repo_root=repo_root,
        repair_reports_root=repair_reports_root,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_paths,
    )
    gates.append(_gate_record("optional_archive_availability", availability))
    availability_summary = _summary(availability)
    if boundary is None:
        if availability_summary.get("status") != availability_gate.STATUS_READY:
            status = STATUS_NO_GO
            boundary = _no_go_boundary(gate="optional_archive_availability", report=availability)
        elif availability_summary.get("all_optional_archives_reusable") is not True:
            boundary = _approval_boundary(
                gate="optional_archive_availability",
                stage=availability_gate.STAGE,
                status=availability_gate.STATUS_READY,
                action_kind="approve_optional_archive_acquisition_or_cost_diagnostic",
                recommended_action=availability_summary.get("recommended_next_action", ""),
                expected_artifacts=_availability_expected_artifacts(availability),
                bounded_plan=_availability_bounded_plan(availability),
            )

    conversion_plan_report = conversion_plan.build_report(
        **_common_kwargs(
            repo_root=repo_root,
            work_order_report=work_order_report,
            drilldown_report=drilldown_report,
            checkpoint_jsonl=checkpoint_jsonl,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
            generated_at_utc=generated_at_utc,
            staged_paths=staged_paths,
            ignored_paths=ignored_generated_paths,
        )
    )
    gates.append(_gate_record("candidate_conversion_plan", conversion_plan_report))
    conversion_runner_report = conversion_runner.build_report(
        **_common_kwargs(
            repo_root=repo_root,
            work_order_report=work_order_report,
            drilldown_report=drilldown_report,
            checkpoint_jsonl=checkpoint_jsonl,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
            generated_at_utc=generated_at_utc,
            staged_paths=staged_paths,
            ignored_paths=ignored_generated_paths,
        ),
        execute=False,
    )
    gates.append(_gate_record("candidate_conversion_execution", conversion_runner_report))
    conversion_review_report = conversion_review.build_report(
        **_common_kwargs(
            repo_root=repo_root,
            work_order_report=work_order_report,
            drilldown_report=drilldown_report,
            checkpoint_jsonl=checkpoint_jsonl,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
            generated_at_utc=generated_at_utc,
            staged_paths=staged_paths,
            ignored_paths=ignored_generated_paths,
        )
    )
    gates.append(_gate_record("candidate_conversion_review", conversion_review_report))
    if boundary is None and _summary(conversion_review_report).get("status") != conversion_review.STATUS_READY:
        if _summary(conversion_plan_report).get("status") != conversion_plan.STATUS_READY:
            status = STATUS_NO_GO
            boundary = _no_go_boundary(gate="candidate_conversion_plan", report=conversion_plan_report)
        elif _summary(conversion_runner_report).get("status") == conversion_runner.STATUS_DRY_RUN_READY:
            boundary = _approval_boundary(
                gate="candidate_conversion_execution",
                stage=conversion_runner.STAGE,
                status=conversion_runner.STATUS_DRY_RUN_READY,
                action_kind="approve_bounded_candidate_raw_conversion",
                recommended_action=_summary(conversion_runner_report).get("recommended_next_action", ""),
                command=CANDIDATE_CONVERSION_APPROVAL_COMMAND,
                approval_token=conversion_runner.APPROVAL_TOKEN,
                expected_artifacts=_dry_run_expected_artifacts(conversion_runner_report),
                bounded_plan=_planned_command_bounded_plan(
                    conversion_runner_report,
                    maximum_scope={
                        "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
                        "schemas": ["ohlcv-1m", "status", "statistics"],
                        "network": False,
                        "data_mutation": True,
                    },
                    stop_condition=(
                        "Stop unless candidate conversion produces only the planned ES 2026 candidate "
                        "raw and optional schema audit outputs, all generated artifacts remain ignored "
                        "and unstaged, and no readiness rerun, causal build, labels/features, "
                        "WFA/modeling, proof scan, staging, commit, push, or live/paper path runs."
                    ),
                ),
            )
        else:
            status = STATUS_NO_GO
            boundary = _no_go_boundary(gate="candidate_conversion_execution", report=conversion_runner_report)

    readiness_plan_report = readiness_plan.build_report(
        **_common_kwargs(
            repo_root=repo_root,
            work_order_report=work_order_report,
            drilldown_report=drilldown_report,
            checkpoint_jsonl=checkpoint_jsonl,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
            generated_at_utc=generated_at_utc,
            staged_paths=staged_paths,
            ignored_paths=ignored_generated_paths,
        )
    )
    gates.append(_gate_record("candidate_readiness_plan", readiness_plan_report))
    readiness_runner_report = readiness_runner.build_report(
        **_common_kwargs(
            repo_root=repo_root,
            work_order_report=work_order_report,
            drilldown_report=drilldown_report,
            checkpoint_jsonl=checkpoint_jsonl,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
            generated_at_utc=generated_at_utc,
            staged_paths=staged_paths,
            ignored_paths=ignored_generated_paths,
        ),
        execute=False,
    )
    gates.append(_gate_record("candidate_readiness_execution", readiness_runner_report))
    readiness_review_report = readiness_review.build_report(
        **_common_kwargs(
            repo_root=repo_root,
            work_order_report=work_order_report,
            drilldown_report=drilldown_report,
            checkpoint_jsonl=checkpoint_jsonl,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
            generated_at_utc=generated_at_utc,
            staged_paths=staged_paths,
            ignored_paths=ignored_generated_paths,
        )
    )
    gates.append(_gate_record("candidate_readiness_review", readiness_review_report))
    if boundary is None and _summary(readiness_review_report).get("status") != readiness_review.STATUS_READY:
        if _summary(readiness_plan_report).get("status") != readiness_plan.STATUS_READY:
            status = STATUS_NO_GO
            boundary = _no_go_boundary(gate="candidate_readiness_plan", report=readiness_plan_report)
        elif _summary(readiness_runner_report).get("status") == readiness_runner.STATUS_DRY_RUN_READY:
            boundary = _approval_boundary(
                gate="candidate_readiness_execution",
                stage=readiness_runner.STAGE,
                status=readiness_runner.STATUS_DRY_RUN_READY,
                action_kind="approve_bounded_candidate_readiness_diagnostics",
                recommended_action=_summary(readiness_runner_report).get("recommended_next_action", ""),
                command=CANDIDATE_READINESS_APPROVAL_COMMAND,
                approval_token=readiness_runner.APPROVAL_TOKEN,
                expected_artifacts=_dry_run_expected_artifacts(readiness_runner_report),
                bounded_plan=_planned_command_bounded_plan(
                    readiness_runner_report,
                    maximum_scope={
                        "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
                        "profile": repair_plan_gate.DEFAULT_PROFILE,
                        "network": False,
                        "data_mutation": False,
                    },
                    stop_condition=(
                        "Stop unless candidate readiness diagnostics produce only the planned ES 2026 "
                        "raw-quality, raw-alignment, include-list, and readiness-only outputs, all "
                        "generated artifacts remain ignored and unstaged, and no causal build, "
                        "accepted-warning packet, exclusion, labels/features, WFA/modeling, proof scan, "
                        "staging, commit, push, or live/paper path runs."
                    ),
                ),
            )
        else:
            status = STATUS_NO_GO
            boundary = _no_go_boundary(gate="candidate_readiness_execution", report=readiness_runner_report)

    label_candidate_causal_root = resolve_path(
        repo_root,
        downstream_label_gate.DEFAULT_CANDIDATE_CAUSAL_ROOT,
    )
    label_output_root = resolve_path(repo_root, downstream_label_gate.DEFAULT_LABEL_OUTPUT_ROOT)
    label_reports_root = resolve_path(repo_root, downstream_label_gate.DEFAULT_LABEL_REPORTS_ROOT)
    label_build_reports_root = resolve_path(
        repo_root,
        downstream_label_gate.DEFAULT_BUILD_REPORTS_ROOT,
    )
    label_profile_config = resolve_path(repo_root, downstream_label_gate.DEFAULT_PROFILE_CONFIG)
    label_costs_config = resolve_path(repo_root, downstream_label_gate.DEFAULT_COSTS_CONFIG)
    label_script = resolve_path(repo_root, downstream_label_gate.DEFAULT_LABEL_SCRIPT)
    if boundary is None:
        label_runner_report = downstream_label_runner.build_report(
            repo_root=repo_root,
            candidate_causal_root=label_candidate_causal_root,
            label_output_root=label_output_root,
            label_reports_root=label_reports_root,
            build_reports_root=label_build_reports_root,
            profile_config=label_profile_config,
            costs_config=label_costs_config,
            label_script=label_script,
            execute=False,
            generated_at_utc=generated_at_utc,
            staged_generated_paths=staged_paths,
            ignored_generated_paths=ignored_generated_paths,
        )
        gates.append(_gate_record("downstream_label_build_execution", label_runner_report))
        label_runner_summary = _summary(label_runner_report)
        if label_runner_summary.get("status") == downstream_label_runner.STATUS_DRY_RUN_READY:
            boundary = _approval_boundary(
                gate="downstream_label_build_execution",
                stage=downstream_label_runner.STAGE,
                status=downstream_label_runner.STATUS_DRY_RUN_READY,
                action_kind="approve_bounded_downstream_label_build",
                recommended_action=label_runner_summary.get("recommended_next_action", ""),
                command=DOWNSTREAM_LABEL_APPROVAL_COMMAND,
                approval_token=downstream_label_runner.APPROVAL_TOKEN,
                expected_artifacts=_dry_run_expected_artifacts(label_runner_report),
                bounded_plan=_planned_command_bounded_plan(
                    label_runner_report,
                    maximum_scope={
                        "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
                        "profile": repair_plan_gate.DEFAULT_PROFILE,
                        "input_root": rel(label_candidate_causal_root, repo_root),
                        "output_root": rel(label_output_root, repo_root),
                        "reports_root": rel(label_reports_root, repo_root),
                        "causal_base_manifest": rel(
                            label_build_reports_root / "causal_base_manifest.json",
                            repo_root,
                        ),
                        "network": False,
                        "data_mutation": True,
                        "canonical_data_mutation": False,
                    },
                    stop_condition=(
                        "Stop unless Phase 3 label build produces only the planned ES 2026 "
                        "label parquet and label reports, all generated artifacts remain "
                        "ignored and unstaged, and no feature build, WFA/modeling, proof scan, "
                        "staging, commit, push, or live/paper path runs."
                    ),
                ),
            )
        elif not _expected_outputs_already_exist(label_runner_summary):
            status = STATUS_NO_GO
            boundary = _no_go_boundary(
                gate="downstream_label_build_execution",
                report=label_runner_report,
            )
        else:
            feature_output_root = resolve_path(
                repo_root,
                downstream_feature_gate.DEFAULT_FEATURE_OUTPUT_ROOT,
            )
            feature_reports_root = resolve_path(
                repo_root,
                downstream_feature_gate.DEFAULT_FEATURE_REPORTS_ROOT,
            )
            feature_script = resolve_path(
                repo_root,
                downstream_feature_gate.DEFAULT_FEATURE_SCRIPT,
            )
            feature_runner_report = downstream_feature_runner.build_report(
                repo_root=repo_root,
                label_output_root=label_output_root,
                label_reports_root=label_reports_root,
                feature_output_root=feature_output_root,
                feature_reports_root=feature_reports_root,
                profile_config=label_profile_config,
                costs_config=label_costs_config,
                feature_script=feature_script,
                execute=False,
                generated_at_utc=generated_at_utc,
                staged_generated_paths=staged_paths,
                ignored_generated_paths=ignored_generated_paths,
            )
            gates.append(_gate_record("downstream_feature_build_execution", feature_runner_report))
            feature_runner_summary = _summary(feature_runner_report)
            if feature_runner_summary.get("status") == downstream_feature_runner.STATUS_DRY_RUN_READY:
                boundary = _approval_boundary(
                    gate="downstream_feature_build_execution",
                    stage=downstream_feature_runner.STAGE,
                    status=downstream_feature_runner.STATUS_DRY_RUN_READY,
                    action_kind="approve_bounded_downstream_feature_build",
                    recommended_action=feature_runner_summary.get("recommended_next_action", ""),
                    command=DOWNSTREAM_FEATURE_APPROVAL_COMMAND,
                    approval_token=downstream_feature_runner.APPROVAL_TOKEN,
                    expected_artifacts=_dry_run_expected_artifacts(feature_runner_report),
                    bounded_plan=_planned_command_bounded_plan(
                        feature_runner_report,
                        maximum_scope={
                            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
                            "profile": repair_plan_gate.DEFAULT_PROFILE,
                            "input_root": rel(label_output_root, repo_root),
                            "output_root": rel(feature_output_root, repo_root),
                            "reports_root": rel(feature_reports_root, repo_root),
                            "label_manifest": rel(
                                label_reports_root / "label_manifest.json",
                                repo_root,
                            ),
                            "network": False,
                            "data_mutation": True,
                            "canonical_data_mutation": False,
                        },
                        stop_condition=(
                            "Stop unless Phase 4 feature build produces only the planned ES 2026 "
                            "feature matrix, registries, and feature reports, all generated artifacts "
                            "remain ignored and unstaged, and no WFA/modeling, proof scan, staging, "
                            "commit, push, or live/paper path runs."
                        ),
                    ),
                )
            else:
                wfa_reports_root = resolve_path(
                    repo_root,
                    downstream_wfa_split_gate.DEFAULT_WFA_REPORTS_ROOT,
                )
                wfa_script = resolve_path(
                    repo_root,
                    downstream_wfa_split_gate.DEFAULT_WFA_SCRIPT,
                )
                wfa_runner_report = downstream_wfa_split_runner.build_report(
                    repo_root=repo_root,
                    label_output_root=label_output_root,
                    label_reports_root=label_reports_root,
                    feature_output_root=feature_output_root,
                    feature_reports_root=feature_reports_root,
                    wfa_reports_root=wfa_reports_root,
                    profile_config=label_profile_config,
                    models_config=resolve_path(
                        repo_root,
                        downstream_wfa_split_gate.DEFAULT_MODELS_CONFIG,
                    ),
                    wfa_script=wfa_script,
                    generated_at_utc=generated_at_utc,
                    staged_generated_paths=staged_paths,
                    ignored_generated_paths=ignored_generated_paths,
                )
                gates.append(_gate_record("downstream_wfa_split_build_execution", wfa_runner_report))
                wfa_runner_summary = _summary(wfa_runner_report)
                if (
                    wfa_runner_summary.get("status")
                    == downstream_wfa_split_runner.STATUS_DRY_RUN_READY
                ):
                    boundary = _approval_boundary(
                        gate="downstream_wfa_split_build_execution",
                        stage=downstream_wfa_split_runner.STAGE,
                        status=downstream_wfa_split_runner.STATUS_DRY_RUN_READY,
                        action_kind="approve_bounded_downstream_wfa_split_build",
                        recommended_action=wfa_runner_summary.get("recommended_next_action", ""),
                        command=DOWNSTREAM_WFA_SPLIT_APPROVAL_COMMAND,
                        approval_token=downstream_wfa_split_runner.APPROVAL_TOKEN,
                        expected_artifacts=_dry_run_expected_artifacts(wfa_runner_report),
                        bounded_plan=_planned_command_bounded_plan(
                            wfa_runner_report,
                            maximum_scope={
                                "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
                                "profile": downstream_wfa_split_gate.TARGET_PROFILE,
                                "input_root": rel(feature_output_root, repo_root),
                                "reports_root": rel(wfa_reports_root, repo_root),
                                "feature_manifest": rel(
                                    feature_reports_root / "baseline_feature_manifest.json",
                                    repo_root,
                                ),
                                "network": False,
                                "data_mutation": False,
                                "reports_mutation": True,
                                "modeling": False,
                            },
                            stop_condition=(
                                "Stop unless Phase 5 WFA split build produces only the planned "
                                "ES 2026 split_plan.csv and split_plan.json reports, all generated "
                                "artifacts remain ignored and unstaged, and no model training, "
                                "selection, metrics, predictions, proof scan, staging, commit, push, "
                                "or live/paper path runs."
                            ),
                        ),
                    )
                else:
                    if _expected_outputs_already_exist(wfa_runner_summary):
                        predictions_root = resolve_path(
                            repo_root,
                            downstream_model_gate.DEFAULT_PREDICTIONS_ROOT,
                        )
                        model_reports_root = resolve_path(
                            repo_root,
                            downstream_model_gate.DEFAULT_MODEL_REPORTS_ROOT,
                        )
                        model_runner_report = downstream_model_runner.build_report(
                            repo_root=repo_root,
                            profile=downstream_model_gate.DEFAULT_PROFILE,
                            matrix=downstream_model_gate.DEFAULT_MATRIX,
                            run=downstream_model_gate.DEFAULT_RUN,
                            feature_output_root=feature_output_root,
                            feature_reports_root=feature_reports_root,
                            wfa_split_reports_root=wfa_reports_root,
                            predictions_root=predictions_root,
                            model_reports_root=model_reports_root,
                            profile_config=label_profile_config,
                            models_config=resolve_path(
                                repo_root,
                                downstream_model_gate.DEFAULT_MODELS_CONFIG,
                            ),
                            phase6_script=resolve_path(
                                repo_root,
                                downstream_model_gate.DEFAULT_PHASE6_SCRIPT,
                            ),
                            max_folds=downstream_model_gate.DEFAULT_MAX_FOLDS,
                            execute=False,
                            generated_at_utc=generated_at_utc,
                            staged_generated_paths=staged_paths,
                            ignored_generated_paths=ignored_generated_paths,
                        )
                        gates.append(
                            _gate_record("downstream_model_build_execution", model_runner_report)
                        )
                        model_runner_summary = _summary(model_runner_report)
                        if (
                            model_runner_summary.get("status")
                            == downstream_model_runner.STATUS_DRY_RUN_READY
                        ):
                            boundary = _approval_boundary(
                                gate="downstream_model_build_execution",
                                stage=downstream_model_runner.STAGE,
                                status=downstream_model_runner.STATUS_DRY_RUN_READY,
                                action_kind="approve_bounded_downstream_model_build",
                                recommended_action=model_runner_summary.get(
                                    "recommended_next_action",
                                    "",
                                ),
                                command=DOWNSTREAM_MODEL_APPROVAL_COMMAND,
                                approval_token=downstream_model_runner.APPROVAL_TOKEN,
                                expected_artifacts=_dry_run_expected_artifacts(
                                    model_runner_report
                                ),
                                bounded_plan=_planned_command_bounded_plan(
                                    model_runner_report,
                                    maximum_scope={
                                        "market_years": [
                                            {"market": TARGET_MARKET, "year": TARGET_YEAR}
                                        ],
                                        "profile": downstream_model_gate.DEFAULT_PROFILE,
                                        "matrix": downstream_model_gate.DEFAULT_MATRIX,
                                        "run": downstream_model_gate.DEFAULT_RUN,
                                        "input_root": rel(feature_output_root, repo_root),
                                        "split_plan": rel(
                                            wfa_reports_root / "split_plan.json",
                                            repo_root,
                                        ),
                                        "predictions_root": rel(predictions_root, repo_root),
                                        "reports_root": rel(model_reports_root, repo_root),
                                        "network": False,
                                        "data_mutation": True,
                                        "reports_mutation": True,
                                        "model_training": True,
                                        "prediction_write": True,
                                        "model_selection": False,
                                    },
                                    stop_condition=(
                                        "Stop unless Phase 6 model smoke produces only the planned "
                                        "ES 2026 prediction parquet, prediction manifest, and WFA "
                                        "report, all generated artifacts remain ignored and unstaged, "
                                        "and no metrics, model selection, proof scan, staging, commit, "
                                        "push, or live/paper path runs."
                                    ),
                                ),
                            )
                        elif _expected_outputs_already_exist(model_runner_summary):
                            metrics_root = resolve_path(
                                repo_root,
                                downstream_metrics_gate.DEFAULT_METRICS_ROOT,
                            )
                            model_selection_root = resolve_path(
                                repo_root,
                                downstream_metrics_gate.DEFAULT_MODEL_SELECTION_ROOT,
                            )
                            phase8_root = resolve_path(
                                repo_root,
                                downstream_metrics_gate.DEFAULT_PHASE8_ROOT,
                            )
                            metrics_runner_report = downstream_metrics_runner.build_report(
                                repo_root=repo_root,
                                profile=downstream_metrics_gate.DEFAULT_PROFILE,
                                matrix=downstream_metrics_gate.DEFAULT_MATRIX,
                                run=downstream_metrics_gate.DEFAULT_RUN,
                                feature_output_root=feature_output_root,
                                feature_reports_root=feature_reports_root,
                                wfa_split_reports_root=wfa_reports_root,
                                predictions_root=predictions_root,
                                model_reports_root=model_reports_root,
                                metrics_root=metrics_root,
                                model_selection_root=model_selection_root,
                                phase8_root=phase8_root,
                                profile_config=label_profile_config,
                                models_config=resolve_path(
                                    repo_root,
                                    downstream_metrics_gate.DEFAULT_MODELS_CONFIG,
                                ),
                                costs_config=resolve_path(
                                    repo_root,
                                    downstream_metrics_gate.DEFAULT_COSTS_CONFIG,
                                ),
                                phase8_script=resolve_path(
                                    repo_root,
                                    downstream_metrics_gate.DEFAULT_PHASE8_SCRIPT,
                                ),
                                max_folds=downstream_metrics_gate.DEFAULT_MAX_FOLDS,
                                execute=False,
                                generated_at_utc=generated_at_utc,
                                staged_generated_paths=staged_paths,
                                ignored_generated_paths=ignored_generated_paths,
                            )
                            gates.append(
                                _gate_record(
                                    "downstream_metrics_build_execution",
                                    metrics_runner_report,
                                )
                            )
                            metrics_runner_summary = _summary(metrics_runner_report)
                            if (
                                metrics_runner_summary.get("status")
                                == downstream_metrics_runner.STATUS_DRY_RUN_READY
                            ):
                                boundary = _approval_boundary(
                                    gate="downstream_metrics_build_execution",
                                    stage=downstream_metrics_runner.STAGE,
                                    status=downstream_metrics_runner.STATUS_DRY_RUN_READY,
                                    action_kind="approve_bounded_downstream_metrics_build",
                                    recommended_action=metrics_runner_summary.get(
                                        "recommended_next_action",
                                        "",
                                    ),
                                    command=DOWNSTREAM_METRICS_APPROVAL_COMMAND,
                                    approval_token=downstream_metrics_runner.APPROVAL_TOKEN,
                                    expected_artifacts=_dry_run_expected_artifacts(
                                        metrics_runner_report
                                    ),
                                    bounded_plan=_planned_command_bounded_plan(
                                        metrics_runner_report,
                                    maximum_scope={
                                        "market_years": [
                                            {"market": TARGET_MARKET, "year": TARGET_YEAR}
                                        ],
                                        "profile": downstream_metrics_gate.DEFAULT_PROFILE,
                                        "matrix": downstream_metrics_gate.DEFAULT_MATRIX,
                                        "run": downstream_metrics_gate.DEFAULT_RUN,
                                        "predictions": rel(
                                                predictions_root
                                                / downstream_metrics_gate.DEFAULT_RUN
                                                / "oos_predictions.parquet",
                                                repo_root,
                                            ),
                                            "predictions_manifest": rel(
                                                model_reports_root
                                                / f"{downstream_metrics_gate.DEFAULT_RUN}_predictions_manifest.json",
                                                repo_root,
                                            ),
                                            "metrics_root": rel(metrics_root, repo_root),
                                            "model_selection_root": rel(
                                                model_selection_root,
                                                repo_root,
                                            ),
                                            "phase8_root": rel(phase8_root, repo_root),
                                            "network": False,
                                            "data_mutation": False,
                                            "reports_mutation": True,
                                            "model_training": False,
                                            "promotion_or_freeze": False,
                                            "live_or_paper_execution": False,
                                        },
                                        stop_condition=(
                                            "Stop unless Phase 8 metrics/model-selection produces "
                                            "only the planned ES 2026 diagnostics outputs, all "
                                            "generated artifacts remain ignored and unstaged, and no "
                                            "model promotion, artifact freeze, proof scan, staging, "
                                            "commit, push, or live/paper path runs."
                                        ),
                                    ),
                                )
                            elif _expected_outputs_already_exist(metrics_runner_summary):
                                metrics_review_report = downstream_metrics_review_gate.build_report(
                                    repo_root=repo_root,
                                    profile=downstream_metrics_gate.DEFAULT_PROFILE,
                                    matrix=downstream_metrics_gate.DEFAULT_MATRIX,
                                    run=downstream_metrics_gate.DEFAULT_RUN,
                                    feature_output_root=feature_output_root,
                                    wfa_split_reports_root=wfa_reports_root,
                                    predictions_root=predictions_root,
                                    model_reports_root=model_reports_root,
                                    metrics_root=metrics_root,
                                    model_selection_root=model_selection_root,
                                    phase8_root=phase8_root,
                                    profile_config=label_profile_config,
                                    models_config=resolve_path(
                                        repo_root,
                                        downstream_metrics_gate.DEFAULT_MODELS_CONFIG,
                                    ),
                                    costs_config=resolve_path(
                                        repo_root,
                                        downstream_metrics_gate.DEFAULT_COSTS_CONFIG,
                                    ),
                                    max_folds=downstream_metrics_gate.DEFAULT_MAX_FOLDS,
                                    generated_at_utc=generated_at_utc,
                                    staged_generated_paths=staged_paths,
                                    ignored_generated_paths=ignored_generated_paths,
                                )
                                gates.append(
                                    _gate_record(
                                        "downstream_metrics_review",
                                        metrics_review_report,
                                    )
                                )
                                metrics_review_summary = _summary(metrics_review_report)
                                if (
                                    metrics_review_summary.get("status")
                                    == downstream_metrics_review_gate.STATUS_READY
                                ):
                                    boundary = _approval_boundary(
                                        gate="downstream_metrics_review",
                                        stage=downstream_metrics_review_gate.STAGE,
                                        status=downstream_metrics_review_gate.STATUS_READY,
                                        action_kind=(
                                            "review_downstream_metrics_before_separate_"
                                            "promotion_or_proof_decision"
                                        ),
                                        recommended_action=metrics_review_summary.get(
                                            "recommended_next_action",
                                            "",
                                        ),
                                    )
                                    boundary["non_approval"] = dict(
                                        metrics_review_report.get("non_approval", {})
                                    )
                                else:
                                    status = STATUS_NO_GO
                                    boundary = _no_go_boundary(
                                        gate="downstream_metrics_review",
                                        report=metrics_review_report,
                                    )
                            else:
                                status = STATUS_NO_GO
                                boundary = _no_go_boundary(
                                    gate="downstream_metrics_build_execution",
                                    report=metrics_runner_report,
                                )
                        else:
                            status = STATUS_NO_GO
                            boundary = _no_go_boundary(
                                gate="downstream_model_build_execution",
                                report=model_runner_report,
                            )
                    else:
                        status = STATUS_NO_GO
                        boundary = _no_go_boundary(
                            gate="downstream_wfa_split_build_execution",
                            report=wfa_runner_report,
                        )

    if boundary is None:
        status = STATUS_REVIEW_READY
        boundary = {
            "gate": "candidate_readiness_review",
            "stage": readiness_review.STAGE,
            "status": readiness_review.STATUS_READY,
            "next_action_kind": "separate_causal_base_repair_proposal_decision",
            "human_approval_required": True,
            "approval_token": None,
            "recommended_command": None,
            "expected_generated_artifacts": [],
            "recommended_action": _recommended_next({}, STATUS_REVIEW_READY),
        }

    current_gate_record = next(
        (gate for gate in gates if gate.get("gate") == boundary.get("gate")),
        {},
    )
    boundary["execution_approval_required"] = _boundary_requires_bounded_plan(boundary)
    boundary_expected_artifacts = boundary.get("expected_generated_artifacts") or []
    boundary_expected_count, boundary_ignored_count, boundary_unignored_count = _boundary_artifact_counts(
        expected_artifacts=boundary_expected_artifacts,
        current_gate_record=current_gate_record,
        ignored_generated_paths=ignored_generated_paths,
    )
    boundary_bounded_plan_missing = _bounded_plan_missing_fields(boundary)

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while checking workflow status.",
    )
    _check(
        checks,
        name="workflow_boundary_identified",
        passed=bool(boundary),
        observed=boundary,
        expected="one current gate or approval boundary",
        detail="The status gate should identify the next bounded ES 2026 P1 action.",
    )
    _check(
        checks,
        name="approval_boundary_expected_outputs_ignored",
        passed=not boundary_expected_artifacts
        or (boundary_ignored_count == boundary_expected_count and boundary_unignored_count == 0),
        observed={
            "expected": boundary_expected_count,
            "ignored": boundary_ignored_count,
            "unignored": boundary_unignored_count,
        },
        expected="all expected approval-boundary outputs ignored, with zero unignored outputs",
        detail="Generated artifacts for the current approval boundary must be ignored before status can proceed.",
    )
    _check(
        checks,
        name="approval_boundary_bounded_plan_complete",
        passed=not boundary_bounded_plan_missing,
        observed=boundary_bounded_plan_missing,
        expected=(
            "command family, exact scope, timeout, expected artifacts, forbidden patterns, "
            "and stop condition when approval can generate artifacts"
        ),
        detail="Artifact-generating approval boundaries must expose a complete bounded plan packet.",
    )
    _check(
        checks,
        name="workflow_status_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally exposes no generated report output arguments.",
    )
    failures = [check for check in checks if check["status"] == "FAIL"]
    if failures and status != STATUS_NO_GO:
        status = STATUS_NO_GO

    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if status == STATUS_NO_GO else DECISION_STATUS_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "optional_archive_inventory_status": optional_inventory_evidence["status"],
            "optional_archive_inventory_market_count": optional_inventory_evidence["market_count"],
            "optional_archive_inventory_ready_market_count": optional_inventory_evidence[
                "ready_market_count"
            ],
            "optional_archive_inventory_invalid_archive_count": optional_inventory_evidence[
                "invalid_archive_count"
            ],
            "current_gate": boundary.get("gate"),
            "current_gate_status": boundary.get("status"),
            "next_action_kind": boundary.get("next_action_kind"),
            "human_approval_required": boundary.get("human_approval_required"),
            "execution_approval_required": _boundary_requires_bounded_plan(boundary),
            "approval_token": boundary.get("approval_token"),
            "expected_generated_output_count": boundary_expected_count,
            "ignored_expected_generated_output_count": boundary_ignored_count,
            "unignored_expected_generated_output_count": boundary_unignored_count,
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures) if status != STATUS_NO_GO else max(1, len(failures)),
            "recommended_next_action": _recommended_next(boundary, status),
            **_approval_flags(),
        },
        "checks": checks,
        "gate_summaries": gates,
        "current_boundary": boundary,
        "supporting_evidence": {
            "optional_archive_inventory": optional_inventory_evidence,
        },
        "non_approval": {
            "scope": "ES 2026 P1 workflow status only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-order-report", default=str(repair_plan_gate.DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--drilldown-report", default=str(repair_plan_gate.DEFAULT_DRILLDOWN_REPORT))
    parser.add_argument("--checkpoint-jsonl", default=str(repair_plan_gate.DEFAULT_CHECKPOINT_JSONL))
    parser.add_argument("--repair-reports-root", default=str(repair_plan_gate.DEFAULT_REPAIR_REPORTS_ROOT))
    parser.add_argument("--candidate-raw-root", default=str(repair_plan_gate.DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--output-root", default=str(repair_plan_gate.DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(repair_plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT))
    parser.add_argument(
        "--print-boundary-json",
        action="store_true",
        help="Print the current approval boundary packet to stdout after the default status line.",
    )
    return parser


def boundary_approval_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = report["summary"]
    boundary = report["current_boundary"]
    return {
        "stage": STAGE,
        "status": summary["status"],
        "market": summary["market"],
        "year": summary["year"],
        "current_gate": summary["current_gate"],
        "current_gate_status": summary["current_gate_status"],
        "next_action_kind": summary["next_action_kind"],
        "human_approval_required": summary["human_approval_required"],
        "execution_approval_required": summary["execution_approval_required"],
        "approval_token": summary["approval_token"],
        "recommended_command": boundary.get("recommended_command"),
        "recommended_action": boundary.get("recommended_action"),
        "expected_generated_artifacts": boundary.get("expected_generated_artifacts", []),
        "generated_artifact_hygiene": {
            "expected_generated_output_count": summary["expected_generated_output_count"],
            "ignored_expected_generated_output_count": summary[
                "ignored_expected_generated_output_count"
            ],
            "unignored_expected_generated_output_count": summary[
                "unignored_expected_generated_output_count"
            ],
            "generated_output_count": summary["generated_output_count"],
            "staged_generated_path_count": summary["staged_generated_path_count"],
        },
        "supporting_evidence": report.get("supporting_evidence", {}),
        "bounded_plan": boundary.get("bounded_plan", {}),
        "non_approval": boundary.get("non_approval", report.get("non_approval", {})),
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            work_order_report=resolve_path(repo_root, args.work_order_report),
            drilldown_report=resolve_path(repo_root, args.drilldown_report),
            checkpoint_jsonl=resolve_path(repo_root, args.checkpoint_jsonl),
            repair_reports_root=resolve_path(repo_root, args.repair_reports_root),
            candidate_raw_root=resolve_path(repo_root, args.candidate_raw_root),
            output_root=resolve_path(repo_root, args.output_root),
            raw_alignment_report=resolve_path(repo_root, args.raw_alignment_report),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"optional_inventory_status={summary['optional_archive_inventory_status']} "
        f"optional_inventory_ready_markets={summary['optional_archive_inventory_ready_market_count']} "
        f"optional_inventory_invalid_archives={summary['optional_archive_inventory_invalid_archive_count']} "
        f"current_gate={summary['current_gate']} "
        f"current_gate_status={summary['current_gate_status']} "
        f"next_action_kind={summary['next_action_kind']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"ignored_expected_generated_outputs={summary['ignored_expected_generated_output_count']} "
        f"unignored_expected_generated_outputs={summary['unignored_expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_boundary_json:
        print(json.dumps(boundary_approval_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
