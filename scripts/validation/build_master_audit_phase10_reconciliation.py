#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 10 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run
artifact freeze, phase audits, data/model commands, WFA/modeling, prediction
generation, Phase 8 refresh, provider calls, promotion, holdout, paper/live,
cleanup, staging, commit, or push.
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
STAGE = "master_audit_phase10_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE10_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE10_RECONCILIATION_REPORT_ONLY"

RUN_ID = "tier1_core_phase6_full_predictions_20260706"

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_PHASE1B = Path(
    "reports/master_audit/master_audit_phase1b_reconciliation_20260709/"
    "master_audit_phase1b_reconciliation.json"
)
DEFAULT_PHASE2 = Path(
    "reports/master_audit/master_audit_phase2_reconciliation_20260709/"
    "master_audit_phase2_reconciliation.json"
)
DEFAULT_PHASE3 = Path(
    "reports/master_audit/master_audit_phase3_reconciliation_20260709/"
    "master_audit_phase3_reconciliation.json"
)
DEFAULT_PHASE4 = Path(
    "reports/master_audit/master_audit_phase4_reconciliation_20260709/"
    "master_audit_phase4_reconciliation.json"
)
DEFAULT_PHASE5 = Path(
    "reports/master_audit/master_audit_phase5_reconciliation_20260709/"
    "master_audit_phase5_reconciliation.json"
)
DEFAULT_PHASE6 = Path(
    "reports/master_audit/master_audit_phase6_reconciliation_20260709/"
    "master_audit_phase6_reconciliation.json"
)
DEFAULT_PHASE7 = Path(
    "reports/master_audit/master_audit_phase7_reconciliation_20260709/"
    "master_audit_phase7_reconciliation.json"
)
DEFAULT_PHASE8 = Path(
    "reports/master_audit/master_audit_phase8_reconciliation_20260709/"
    "master_audit_phase8_reconciliation.json"
)
DEFAULT_PHASE9 = Path(
    "reports/master_audit/master_audit_phase9_reconciliation_20260709/"
    "master_audit_phase9_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase10_reconciliation_20260709")
REPORT_JSON = "master_audit_phase10_reconciliation.json"
REPORT_MD = "master_audit_phase10_reconciliation.md"

PHASE8_DECISION = Path(f"reports/phase8/{RUN_ID}/alpha_promotion_decision.json")
ALPHA_CLOSEOUT = Path(
    "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
    "alpha_evidence_completion_closeout.json"
)

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    "phase1b_reconciliation": DEFAULT_PHASE1B,
    "phase2_reconciliation": DEFAULT_PHASE2,
    "phase3_reconciliation": DEFAULT_PHASE3,
    "phase4_reconciliation": DEFAULT_PHASE4,
    "phase5_reconciliation": DEFAULT_PHASE5,
    "phase6_reconciliation": DEFAULT_PHASE6,
    "phase7_reconciliation": DEFAULT_PHASE7,
    "phase8_reconciliation": DEFAULT_PHASE8,
    "phase9_reconciliation": DEFAULT_PHASE9,
    "phase8_decision": PHASE8_DECISION,
    "alpha_closeout": ALPHA_CLOSEOUT,
}

EXPECTED_RECONCILIATION_STATUSES = {
    "phase1b_reconciliation": "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY",
    "phase2_reconciliation": "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY",
    "phase3_reconciliation": "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY",
    "phase4_reconciliation": "PASS_MASTER_AUDIT_PHASE4_RECONCILIATION_REPORT_ONLY",
    "phase5_reconciliation": "PASS_MASTER_AUDIT_PHASE5_RECONCILIATION_REPORT_ONLY",
    "phase6_reconciliation": "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY",
    "phase7_reconciliation": "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
    "phase8_reconciliation": "PASS_MASTER_AUDIT_PHASE8_RECONCILIATION_REPORT_ONLY",
    "phase9_reconciliation": "PASS_MASTER_AUDIT_PHASE9_RECONCILIATION_REPORT_ONLY",
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "artifact_freeze_command_executed": False,
    "artifact_freeze_manifest_written": False,
    "data_model_commands_executed": False,
    "dbn_read_executed": False,
    "raw_parquet_read_executed": False,
    "causal_parquet_read_executed": False,
    "label_parquet_read_executed": False,
    "feature_parquet_read_executed": False,
    "prediction_parquet_read_executed": False,
    "model_artifact_read_executed": False,
    "wfa_modeling_executed": False,
    "prediction_generation_executed": False,
    "prediction_materialization_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "freeze_executed": False,
    "holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "staging_commit_push_executed": False,
    "hardened_split_candidate_consumed": False,
    "hardened_phase6_materialization_path_consumed": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def row_by_area(run_status: Mapping[str, Any] | None, area: str) -> Mapping[str, Any] | None:
    rows = dotted_get(run_status, "run_status_table")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("audit_area") == area:
            return row
    return None


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
    json_fields: dict[str, dict[str, str]] = {
        "run_status": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
        },
        "overview": {"status": "status", "failure_count": "summary.failure_count"},
        "phase1b_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase2_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase3_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase4_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase5_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase5_master_audit_status": "summary.phase5_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase6_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase6_master_audit_status": "summary.phase6_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase7_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase7_master_audit_status": "summary.phase7_master_audit_status",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "phase8_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase8_master_audit_status": "summary.phase8_master_audit_status",
            "research_alpha_ready": "summary.research_alpha_ready",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "freeze_executed": "summary.freeze_executed",
        },
        "phase9_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase9_master_audit_status": "summary.phase9_master_audit_status",
            "alpha_closeout_verdict": "summary.alpha_closeout_verdict",
            "future_modeling_allowed": "summary.future_modeling_allowed",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "freeze_executed": "summary.freeze_executed",
        },
        "phase8_decision": {
            "run": "run",
            "promoted": "promoted",
            "research_alpha_ready": "research_alpha_ready",
            "model_promotion_allowed": "model_promotion_allowed",
            "promotion_blocker_count": "promotion_gate.promotion_blocker_count",
            "promotion_metric_gate_status": "promotion_metric_gate.status",
            "statistical_validity_gate_status": "statistical_validity_gate.status",
            "final_holdout_touched": "final_holdout_touched",
            "used_final_holdout_for_tuning": "used_final_holdout_for_tuning",
        },
        "alpha_closeout": {
            "status": "status",
            "verdict": "verdict",
            "run_id": "run_id",
            "terminal_fail_count": "terminal_fail_count",
            "missing_required_evidence_count": "missing_required_evidence_count",
            "modeling_pause_required": "modeling_pause_required",
            "future_modeling_allowed": "future_modeling_allowed",
            "future_evidence_work_allowed": "future_evidence_work_allowed",
            "promotion_allowed": "promotion_allowed",
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


def required_text_snippets(repo_root: Path, paths: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    expectations = {
        "master_audit": ("Phase 10", "Artifact freeze", "blocked unless explicit freeze approval"),
        "project_outline": (
            "Freeze approved research artifacts only after explicit approval",
            "scripts.artifact_freeze.freeze_research_artifacts",
        ),
    }
    results: dict[str, dict[str, Any]] = {}
    for name, snippets in expectations.items():
        path = resolve_path(repo_root, paths[name])
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            results[name] = {"path": paths[name].as_posix(), "error": str(exc), "missing": list(snippets)}
            continue
        missing = [snippet for snippet in snippets if snippet not in text]
        results[name] = {"path": paths[name].as_posix(), "error": None, "missing": missing}
    return results


def previous_reconciliation_statuses(
    payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for name in EXPECTED_RECONCILIATION_STATUSES:
        payload = payloads.get(name, {})
        statuses[name] = {
            "status": payload.get("status"),
            "failure_count": dotted_get(payload, "summary.failure_count"),
            "model_trust_ready": dotted_get(payload, "summary.model_trust_ready"),
            "promotion_allowed": dotted_get(payload, "summary.promotion_allowed"),
            "holdout_allowed": dotted_get(payload, "summary.holdout_allowed"),
            "paper_live_allowed": dotted_get(payload, "summary.paper_live_allowed"),
            "freeze_executed": dotted_get(payload, "summary.freeze_executed"),
        }
    return statuses


def non_approval_all_false(payload: Mapping[str, Any]) -> bool:
    non_approval = as_mapping(payload.get("non_approval"))
    return bool(non_approval) and all(value is False for value in non_approval.values())


def blocker_count(payload: Mapping[str, Any]) -> int:
    return len(as_list(payload.get("blockers")))


def build_checks(
    *,
    repo_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    output_rel: str,
    paths: Mapping[str, Path],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {str(item.get("path")) for item in evidence if item.get("exists")}
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required Phase 10 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 10 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    text_results = required_text_snippets(repo_root, paths)
    check(
        checks,
        failures,
        name="coordination_docs_preserve_phase10_freeze_policy",
        passed=all(not result["error"] and not result["missing"] for result in text_results.values()),
        failure="coordination docs no longer preserve the Phase 10 explicit-approval freeze policy",
        evidence=["MASTER_AUDIT.md", "PROJECT_OUTLINE.md"],
        details=text_results,
    )

    run_status = payloads.get("run_status")
    overview = payloads.get("overview")
    previous_statuses = previous_reconciliation_statuses(payloads)
    previous_status_pass = all(
        payloads.get(name, {}).get("status") == expected
        and dotted_get(payloads.get(name), "summary.failure_count") == 0
        and dotted_get(payloads.get(name), "summary.model_trust_ready") is False
        and dotted_get(payloads.get(name), "summary.promotion_allowed") is False
        and dotted_get(payloads.get(name), "summary.holdout_allowed") is False
        and dotted_get(payloads.get(name), "summary.paper_live_allowed") is False
        for name, expected in EXPECTED_RECONCILIATION_STATUSES.items()
    )
    check(
        checks,
        failures,
        name="master_audit_inputs_are_passed_report_only_blocking_evidence",
        passed=run_status is not None
        and overview is not None
        and run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and previous_status_pass,
        failure="run-status, overview, or Phase 1B-9 reconciliation inputs are not passed report-only blocking evidence",
        evidence=[
            DEFAULT_RUN_STATUS.as_posix(),
            DEFAULT_OVERVIEW.as_posix(),
            DEFAULT_PHASE1B.as_posix(),
            DEFAULT_PHASE2.as_posix(),
            DEFAULT_PHASE3.as_posix(),
            DEFAULT_PHASE4.as_posix(),
            DEFAULT_PHASE5.as_posix(),
            DEFAULT_PHASE6.as_posix(),
            DEFAULT_PHASE7.as_posix(),
            DEFAULT_PHASE8.as_posix(),
            DEFAULT_PHASE9.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "previous_reconciliation_statuses": previous_statuses,
        },
    )

    phase10_row = row_by_area(run_status, "Phase 10")
    check(
        checks,
        failures,
        name="phase10_ledger_row_is_not_approved_artifact_freeze",
        passed=phase10_row is not None
        and phase10_row.get("run_status") == "N/A"
        and phase10_row.get("detail_status") == "N/A_NOT_APPROVED_ARTIFACT_FREEZE"
        and phase10_row.get("evidence_state") == "missing"
        and as_list(phase10_row.get("accepted_evidence")) == [],
        failure="run-status Phase 10 row is not N/A_NOT_APPROVED_ARTIFACT_FREEZE/missing",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"phase10_row": dict(phase10_row or {})},
    )

    phase8 = payloads.get("phase8_decision", {})
    check(
        checks,
        failures,
        name="phase8_decision_preserves_freeze_blockers",
        passed=phase8.get("run") == RUN_ID
        and phase8.get("promoted") is False
        and phase8.get("research_alpha_ready") is False
        and phase8.get("model_promotion_allowed") is False
        and phase8.get("final_holdout_touched") is False
        and phase8.get("used_final_holdout_for_tuning") is False
        and dotted_get(phase8, "promotion_gate.promotion_blocker_count") == 30,
        failure="Phase 8 promotion evidence no longer preserves non-promoted freeze blockers",
        evidence=[PHASE8_DECISION.as_posix()],
        details={
            "run": phase8.get("run"),
            "promoted": phase8.get("promoted"),
            "research_alpha_ready": phase8.get("research_alpha_ready"),
            "model_promotion_allowed": phase8.get("model_promotion_allowed"),
            "final_holdout_touched": phase8.get("final_holdout_touched"),
            "used_final_holdout_for_tuning": phase8.get("used_final_holdout_for_tuning"),
            "promotion_blocker_count": dotted_get(
                phase8, "promotion_gate.promotion_blocker_count"
            ),
            "top_level_blocker_count": blocker_count(phase8),
        },
    )

    phase8_reconciliation = payloads.get("phase8_reconciliation", {})
    phase9_reconciliation = payloads.get("phase9_reconciliation", {})
    alpha_closeout = payloads.get("alpha_closeout", {})
    check(
        checks,
        failures,
        name="phase8_phase9_reconciliations_preserve_blocked_freeze_path",
        passed=dotted_get(phase8_reconciliation, "summary.phase8_master_audit_status")
        == "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE"
        and dotted_get(phase8_reconciliation, "summary.research_alpha_ready") is False
        and dotted_get(phase8_reconciliation, "summary.model_trust_ready") is False
        and dotted_get(phase8_reconciliation, "summary.promotion_allowed") is False
        and dotted_get(phase8_reconciliation, "summary.freeze_executed") is False
        and dotted_get(phase9_reconciliation, "summary.phase9_master_audit_status")
        == "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT"
        and dotted_get(phase9_reconciliation, "summary.alpha_evidence_ready") is False
        and dotted_get(phase9_reconciliation, "summary.future_modeling_allowed") is False
        and dotted_get(phase9_reconciliation, "summary.model_trust_ready") is False
        and dotted_get(phase9_reconciliation, "summary.promotion_allowed") is False
        and dotted_get(phase9_reconciliation, "summary.freeze_executed") is False,
        failure="Phase 8/9 reconciliations no longer preserve the blocked artifact-freeze path",
        evidence=[DEFAULT_PHASE8.as_posix(), DEFAULT_PHASE9.as_posix()],
        details={
            "phase8_summary": as_mapping(phase8_reconciliation.get("summary")),
            "phase9_summary": as_mapping(phase9_reconciliation.get("summary")),
        },
    )

    check(
        checks,
        failures,
        name="alpha_closeout_preserves_terminal_no_alpha_no_promotion",
        passed=alpha_closeout.get("status") == "PASS_REPORT_WRITTEN"
        and alpha_closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and alpha_closeout.get("run_id") == RUN_ID
        and alpha_closeout.get("terminal_fail_count") == 5
        and alpha_closeout.get("missing_required_evidence_count") == 11
        and alpha_closeout.get("modeling_pause_required") is True
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("future_evidence_work_allowed") is True
        and alpha_closeout.get("promotion_allowed") is False
        and non_approval_all_false(alpha_closeout),
        failure="alpha evidence closeout no longer preserves terminal no-alpha/no-promotion evidence",
        evidence=[ALPHA_CLOSEOUT.as_posix()],
        details={
            "status": alpha_closeout.get("status"),
            "verdict": alpha_closeout.get("verdict"),
            "run_id": alpha_closeout.get("run_id"),
            "terminal_fail_count": alpha_closeout.get("terminal_fail_count"),
            "missing_required_evidence_count": alpha_closeout.get(
                "missing_required_evidence_count"
            ),
            "modeling_pause_required": alpha_closeout.get("modeling_pause_required"),
            "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
            "future_evidence_work_allowed": alpha_closeout.get(
                "future_evidence_work_allowed"
            ),
            "promotion_allowed": alpha_closeout.get("promotion_allowed"),
            "non_approval": alpha_closeout.get("non_approval"),
        },
    )

    check(
        checks,
        failures,
        name="artifact_freeze_model_trust_promotion_holdout_paper_live_remain_blocked",
        passed=phase8.get("promoted") is False
        and phase8.get("research_alpha_ready") is False
        and phase8.get("model_promotion_allowed") is False
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("promotion_allowed") is False
        and all(row["model_trust_ready"] is False for row in previous_statuses.values())
        and all(row["promotion_allowed"] is False for row in previous_statuses.values())
        and all(row["holdout_allowed"] is False for row in previous_statuses.values())
        and all(row["paper_live_allowed"] is False for row in previous_statuses.values()),
        failure="artifact freeze, model-trust, promotion, holdout, or paper/live status was unexpectedly upgraded",
        evidence=[PHASE8_DECISION.as_posix(), ALPHA_CLOSEOUT.as_posix()],
        details={
            "phase8_promoted": phase8.get("promoted"),
            "phase8_research_alpha_ready": phase8.get("research_alpha_ready"),
            "phase8_model_promotion_allowed": phase8.get("model_promotion_allowed"),
            "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
            "promotion_allowed": alpha_closeout.get("promotion_allowed"),
            "previous_reconciliation_statuses": previous_statuses,
        },
    )

    check(
        checks,
        failures,
        name="upstream_non_approval_flags_preserve_no_freeze_execution",
        passed=non_approval_all_false(phase8_reconciliation)
        and non_approval_all_false(phase9_reconciliation)
        and non_approval_all_false(alpha_closeout),
        failure="upstream non-approval evidence contains an executed forbidden action",
        evidence=[DEFAULT_PHASE8.as_posix(), DEFAULT_PHASE9.as_posix(), ALPHA_CLOSEOUT.as_posix()],
        details={
            "phase8_non_approval": phase8_reconciliation.get("non_approval"),
            "phase9_non_approval": phase9_reconciliation.get("non_approval"),
            "alpha_closeout_non_approval": alpha_closeout.get("non_approval"),
        },
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "previous_reconciliation_statuses": previous_statuses,
        "phase10_row": dict(phase10_row or {}),
        "phase8_promoted": phase8.get("promoted"),
        "phase8_research_alpha_ready": phase8.get("research_alpha_ready"),
        "phase8_model_promotion_allowed": phase8.get("model_promotion_allowed"),
        "promotion_blocker_count": dotted_get(phase8, "promotion_gate.promotion_blocker_count"),
        "phase8_top_level_blocker_count": blocker_count(phase8),
        "alpha_closeout_verdict": alpha_closeout.get("verdict"),
        "terminal_fail_count": alpha_closeout.get("terminal_fail_count"),
        "missing_required_evidence_count": alpha_closeout.get(
            "missing_required_evidence_count"
        ),
        "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
        "promotion_allowed": alpha_closeout.get("promotion_allowed"),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "phase10-001-artifact-freeze-is-na-not-approved",
            "severity": "Info",
            "finding": "Phase 10 is reconciled as N/A because artifact freeze is not approved.",
            "verified_facts": [
                "phase10_master_audit_status=N/A_NOT_APPROVED_ARTIFACT_FREEZE",
                "freeze_executed=false",
                "artifact_freeze_ready=false",
            ],
            "limitation": "This is not a freeze audit pass and does not create a frozen manifest.",
            "evidence_paths": [DEFAULT_RUN_STATUS.as_posix(), "MASTER_AUDIT.md"],
        },
        {
            "finding_id": "phase10-002-phase8-blocks-freeze",
            "severity": "Critical",
            "finding": "Phase 8 promotion evidence remains negative and blocks artifact freeze.",
            "verified_facts": [
                f"promoted={derived.get('phase8_promoted')}",
                f"research_alpha_ready={derived.get('phase8_research_alpha_ready')}",
                f"model_promotion_allowed={derived.get('phase8_model_promotion_allowed')}",
                f"promotion_blocker_count={derived.get('promotion_blocker_count')}",
            ],
            "limitation": "Freeze requires a separately approved promoted research result.",
            "evidence_paths": [PHASE8_DECISION.as_posix(), DEFAULT_PHASE8.as_posix()],
        },
        {
            "finding_id": "phase10-003-phase9-closeout-blocks-freeze",
            "severity": "Critical",
            "finding": "Phase 9 alpha closeout remains terminal no-alpha evidence.",
            "verified_facts": [
                f"verdict={derived.get('alpha_closeout_verdict')}",
                f"terminal_fail_count={derived.get('terminal_fail_count')}",
                f"missing_required_evidence_count={derived.get('missing_required_evidence_count')}",
                f"future_modeling_allowed={derived.get('future_modeling_allowed')}",
            ],
            "limitation": "Future evidence work may be separate, but this line cannot be frozen.",
            "evidence_paths": [ALPHA_CLOSEOUT.as_posix(), DEFAULT_PHASE9.as_posix()],
        },
        {
            "finding_id": "phase10-004-full-phase10-acceptance-blocked",
            "severity": "Critical",
            "finding": "Full Phase 10 Master Audit acceptance remains blocked.",
            "verified_facts": [
                "phase10_full_master_audit_accepted=false",
                "artifact_freeze_allowed=false",
                "promotion_allowed=false",
                "holdout_allowed=false",
            ],
            "limitation": "Artifact hashes, immutable manifest, environment freeze, and reproduction evidence are not applicable until freeze approval exists.",
            "evidence_paths": ["MASTER_AUDIT.md", "PROJECT_OUTLINE.md"],
        },
    ]


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_input_overrides: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = resolve_path(repo_root, reports_root).resolve()
    paths = dict(REQUIRED_INPUTS)
    if required_input_overrides:
        paths.update(required_input_overrides)
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
        repo_root=repo_root,
        payloads=payloads,
        evidence=evidence,
        output_rel=output_rel,
        paths=paths,
    )
    failures = input_failures + check_failures
    findings = build_findings(derived)
    status = PASS_STATUS if not failures else FAIL_STATUS
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    phase10_classification = (
        "N/A_NOT_APPROVED_ARTIFACT_FREEZE"
        if status == PASS_STATUS
        else "FAILED_PHASE10_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase10_reconciliation_report_only",
            "phase": "Phase 10",
            "phase_name": "Artifact freeze readiness / N/A status",
            "run": RUN_ID,
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "parquet_read_scope": "none",
            "phase_command_scope": "none",
            "full_phase10_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase10_master_audit_status": phase10_classification,
            "phase10_full_master_audit_accepted": False,
            "artifact_freeze_ready": False,
            "artifact_freeze_allowed": False,
            "freeze_executed": False,
            "frozen_manifest_written": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
            "phase8_promoted": False,
            "phase8_research_alpha_ready": False,
            "phase8_model_promotion_allowed": False,
            "promotion_blocker_count": derived.get("promotion_blocker_count"),
            "phase8_top_level_blocker_count": derived.get("phase8_top_level_blocker_count"),
            "phase9_closeout_verdict": derived.get("alpha_closeout_verdict"),
            "terminal_fail_count": derived.get("terminal_fail_count"),
            "missing_required_evidence_count": derived.get(
                "missing_required_evidence_count"
            ),
            "future_modeling_allowed": False,
            "current_line_classification": dotted_get(
                payloads.get("run_status"), "summary.current_line_classification"
            ),
            "current_split_classification": dotted_get(
                payloads.get("run_status"), "summary.current_split_classification"
            ),
            **dict(NON_APPROVAL),
            "finding_counts_by_severity": finding_counts(findings),
        },
        "input_evidence": evidence,
        "previous_reconciliation_statuses": derived.get("previous_reconciliation_statuses", {}),
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
                "run-status Phase 10 row is exactly N/A_NOT_APPROVED_ARTIFACT_FREEZE",
                "Phase 1B/2/3/4/5/6/7/8/9 reconciliations are passed report-only blocking evidence",
                "Phase 8 decision remains promoted=false, research_alpha_ready=false, model_promotion_allowed=false, final_holdout_touched=false, and used_final_holdout_for_tuning=false",
                "Phase 9 closeout remains CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE with future_modeling_allowed=false and promotion_allowed=false",
                "report explicitly states Phase 10 is N/A/blocked, not executed, and not freeze-ready",
                "model-trust, promotion, holdout, paper/live, and full Phase 10 acceptance remain blocked",
                "all forbidden action flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "Phase 10 ledger is upgraded from N/A without explicit approved freeze evidence",
                "any upstream report upgrades model trust, promotion, holdout, or paper/live",
                "Phase 8 or Phase 9 blockers are absent or contradicted",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan only the Phase 11 report-only Master Audit reconciliation for final-holdout "
            "readiness/N/A status from existing JSON/MD evidence; do not run holdout, "
            "data/model, WFA, prediction, freeze, promotion, paper/live, provider, cleanup, "
            "staging, commit, or push commands."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 10 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 10 status: `{summary.get('phase10_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Artifact freeze ready: `{summary.get('artifact_freeze_ready')}`",
        f"- Artifact freeze allowed: `{summary.get('artifact_freeze_allowed')}`",
        f"- Freeze executed: `{summary.get('freeze_executed')}`",
        f"- Frozen manifest written: `{summary.get('frozen_manifest_written')}`",
        f"- Model-trust ready: `{summary.get('model_trust_ready')}`",
        f"- Promotion allowed: `{summary.get('promotion_allowed')}`",
        f"- Holdout allowed: `{summary.get('holdout_allowed')}`",
        f"- Paper/live allowed: `{summary.get('paper_live_allowed')}`",
        f"- Phase 8 promoted: `{summary.get('phase8_promoted')}`",
        f"- Phase 8 promotion blockers: `{summary.get('promotion_blocker_count')}`",
        f"- Phase 9 closeout verdict: `{summary.get('phase9_closeout_verdict')}`",
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
            "- This reconciliation did not run artifact freeze, phase audits, data/model commands, WFA/modeling, prediction generation/materialization, Phase 8 refresh, provider/network calls, promotion, holdout, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, or model artifacts, and it did not consume or advance the hardened split candidate or hardened Phase 6/7 materialization path.",
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
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(repo_root=repo_root, reports_root=reports_root)
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"phase10_status={report['summary']['phase10_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
