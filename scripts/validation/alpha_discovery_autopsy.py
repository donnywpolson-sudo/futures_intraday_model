#!/usr/bin/env python3
"""Autopsy summaries for guarded Phase 9 alpha-discovery batches."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


SAFE_REPORT_STAMP = "FEASIBILITY ONLY - NOT MODEL-TRUST EVIDENCE - DO NOT RETUNE FROM THIS AUTOPSY"
AGGREGATE_BIAS_WARNING = (
    "Aggregate failure patterns are diagnostic only. They must not be used to create "
    "near-neighbor candidates without separate pre-registration and materially different rationale."
)
ALLOWED_NEXT_ACTIONS = {
    "STOP",
    "FIX_INPUTS",
    "REGISTER_NEW_MATERIAL_HYPOTHESIS",
    "PREPARE_SEPARATE_CONFIRMATION_PLAN",
    "RETRY_WITH_BOUNDED_INFRA_FIX",
}
FORBIDDEN_PHRASES = (
    "alpha ready",
    "tradeable",
    "tradable",
    "paper ready",
    "live ready",
    "production ready",
    "promotion ready",
    "approved for wfa",
    "approved for trading",
    "best failed",
    "near pass",
    "almost ready",
    "top failed",
    "promising failure",
)


class AutopsyError(RuntimeError):
    """Raised when autopsy generation would violate the reporting policy."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def validate_safe_text(text: str) -> None:
    lowered = text.lower()
    matches = [phrase for phrase in FORBIDDEN_PHRASES if phrase in lowered]
    if matches:
        raise AutopsyError(f"unsafe report wording detected: {matches}")


def _score(ok: bool) -> int:
    return 10 if ok else 0


def _decision_from_row(row: dict[str, Any]) -> tuple[str, str, str, bool]:
    status = str(row.get("status", "UNKNOWN"))
    runner_status = row.get("runner_status")
    result = row.get("result")
    failure = row.get("failure")

    if row.get("failure_bucket") == "infrastructure_timeout":
        return (
            "STOP_INFRASTRUCTURE_TIMEOUT",
            "infrastructure_timeout",
            "RETRY_WITH_BOUNDED_INFRA_FIX",
            True,
        )
    if status == "INFRASTRUCTURE_FAILURE":
        return ("STOP_INFRASTRUCTURE_FAILURE", "infrastructure_failure", "FIX_INPUTS", True)
    if status == "CANDIDATE_FAILED":
        return ("STOP_CANDIDATE_FAILURE", "candidate_failure", "FIX_INPUTS", True)
    if runner_status == "DISCOVERY_RUN_CANDIDATE_DISCOVERY_PASS":
        return ("DISCOVERY_PASS", "none", "PREPARE_SEPARATE_CONFIRMATION_PLAN", False)
    if runner_status == "DISCOVERY_RUN_CANDIDATE_STOPPED":
        return ("STOP_DISCOVERY", "candidate_stopped", "STOP", True)
    if runner_status == "DISCOVERY_RUN_REVIEW_REQUIRED":
        return ("REVIEW_REQUIRED", "missing_or_malformed_outputs", "FIX_INPUTS", True)
    if runner_status == "DISCOVERY_RUN_COMMAND_FAILED":
        return ("STOP_COMMAND_FAILED", "command_failure", "FIX_INPUTS", True)
    if runner_status == "PREFLIGHT_PASS":
        return ("PREFLIGHT_READY", "none", "STOP", True)
    if isinstance(result, dict) and result.get("status") == "PREFLIGHT_PASS":
        return ("PREFLIGHT_READY", "none", "STOP", True)
    if failure:
        return ("STOP_UNKNOWN_FAILURE", "candidate_failure", "FIX_INPUTS", True)
    return ("REVIEW_REQUIRED", "unknown", "FIX_INPUTS", True)


def _candidate_record(row: dict[str, Any]) -> dict[str, Any]:
    decision, failure_bucket, allowed_next_action, derived_blocked = _decision_from_row(row)
    if allowed_next_action not in ALLOWED_NEXT_ACTIONS:
        raise AutopsyError(f"invalid allowed_next_action: {allowed_next_action}")
    candidate_id = str(row.get("candidate_id", "unknown"))
    run_name = str(row.get("run_name") or candidate_id)
    config_path = str(row.get("config", ""))
    stop_reason = row.get("failure") or failure_bucket
    ready = decision in {"PREFLIGHT_READY", "DISCOVERY_PASS"}
    evidence_complete = decision not in {"REVIEW_REQUIRED"}
    return {
        "candidate_id": candidate_id,
        "run_name": run_name,
        "config_path": config_path,
        "registry_status": row.get("registry_status"),
        "latest_trial_status": row.get("latest_trial_status"),
        "target_family": row.get("target_family"),
        "decision": decision,
        "failure_bucket": failure_bucket,
        "stop_reason": stop_reason,
        "input_readiness_score": _score(ready),
        "class_balance_score": 0,
        "duplicate_overlap_score": 0,
        "fold_stability_score": 0,
        "net_direction_score": 0,
        "prediction_dispersion_score": 0,
        "evidence_completeness_score": _score(evidence_complete),
        "allowed_next_action": allowed_next_action,
        "derived_followup_blocked": derived_blocked,
    }


def build_autopsy(
    *,
    batch_id: str,
    queue_result: dict[str, Any],
    generation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = queue_result.get("results", [])
    if not isinstance(rows, list):
        raise AutopsyError("queue_result results must be a list")
    candidates = [_candidate_record(row) for row in rows if isinstance(row, dict)]
    candidates.sort(key=lambda item: (str(item["candidate_id"]), str(item["run_name"])))
    decision_counts = Counter(str(item["decision"]) for item in candidates)
    failure_counts = Counter(str(item["failure_bucket"]) for item in candidates)
    payload = {
        "schema_version": 1,
        "batch_id": batch_id,
        "report_stamp": SAFE_REPORT_STAMP,
        "status": "AUTOPSY_COMPLETE",
        "candidate_count": len(candidates),
        "generation": generation_result or {},
        "queue_status": queue_result.get("status"),
        "decision_counts": dict(sorted(decision_counts.items())),
        "failure_bucket_counts": dict(sorted(failure_counts.items())),
        "aggregate_bias_warning": AGGREGATE_BIAS_WARNING,
        "statistical_validity_boundary": (
            "This result is not model-trust evidence. Statistical-validity gates remain "
            "separate and are not run by this wizard."
        ),
        "candidates": candidates,
    }
    validate_safe_text(json.dumps(payload, sort_keys=True))
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Phase 9 Alpha Discovery Autopsy: {payload['batch_id']}",
        "",
        SAFE_REPORT_STAMP,
        "",
        str(payload["statistical_validity_boundary"]),
        "",
        str(payload["aggregate_bias_warning"]),
        "",
        "## Batch Counts",
        "",
    ]
    for key, value in payload["decision_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Failure Buckets", ""])
    for key, value in payload["failure_bucket_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Candidates", ""])
    for item in payload["candidates"]:
        lines.append(
            f"- {item['candidate_id']}: {item['decision']} "
            f"({item['failure_bucket']}), next={item['allowed_next_action']}"
        )
    text = "\n".join(lines) + "\n"
    validate_safe_text(text)
    return text


def write_autopsy(
    *,
    root: Path,
    batch_id: str,
    queue_result: dict[str, Any],
    generation_result: dict[str, Any] | None = None,
    report_root: Path | None = None,
) -> dict[str, Any]:
    base = report_root or root / "reports" / "pipeline_audit" / "alpha_discovery_autopsy" / batch_id
    base.mkdir(parents=True, exist_ok=False)
    payload = build_autopsy(
        batch_id=batch_id,
        queue_result=queue_result,
        generation_result=generation_result,
    )
    json_path = base / "autopsy.json"
    md_path = base / "autopsy.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {
        "status": "AUTOPSY_WRITTEN",
        "json_path": _relative(root, json_path),
        "md_path": _relative(root, md_path),
        "candidate_count": payload["candidate_count"],
    }
