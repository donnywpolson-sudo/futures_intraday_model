#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 11 reconciliation.

This command consumes existing JSON/MD repo evidence only. It does not run the
final-holdout guard, artifact freeze, phase audits, data/model commands,
WFA/modeling, prediction generation, Phase 8 refresh, provider calls,
promotion, paper/live, cleanup, staging, commit, or push.
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
STAGE = "master_audit_phase11_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE11_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE11_RECONCILIATION_REPORT_ONLY"

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
DEFAULT_PHASE10 = Path(
    "reports/master_audit/master_audit_phase10_reconciliation_20260709/"
    "master_audit_phase10_reconciliation.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase11_reconciliation_20260709")
REPORT_JSON = "master_audit_phase11_reconciliation.json"
REPORT_MD = "master_audit_phase11_reconciliation.md"

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
    "phase10_reconciliation": DEFAULT_PHASE10,
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
    "phase10_reconciliation": "PASS_MASTER_AUDIT_PHASE10_RECONCILIATION_REPORT_ONLY",
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "final_holdout_guard_executed": False,
    "final_holdout_report_written": False,
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
    "final_holdout_executed": False,
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
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        },
        "phase2_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        },
        "phase3_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        },
        "phase4_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        },
        "phase5_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        },
        "phase6_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        },
        "phase7_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        },
        "phase8_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase8_master_audit_status": "summary.phase8_master_audit_status",
            "research_alpha_ready": "summary.research_alpha_ready",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
            "holdout_executed": "summary.holdout_executed",
        },
        "phase9_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase9_master_audit_status": "summary.phase9_master_audit_status",
            "alpha_closeout_verdict": "summary.alpha_closeout_verdict",
            "future_modeling_allowed": "summary.future_modeling_allowed",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
            "holdout_executed": "summary.holdout_executed",
        },
        "phase10_reconciliation": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "phase10_master_audit_status": "summary.phase10_master_audit_status",
            "artifact_freeze_ready": "summary.artifact_freeze_ready",
            "artifact_freeze_allowed": "summary.artifact_freeze_allowed",
            "freeze_executed": "summary.freeze_executed",
            "frozen_manifest_written": "summary.frozen_manifest_written",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        },
        "phase8_decision": {
            "run": "run",
            "promoted": "promoted",
            "research_alpha_ready": "research_alpha_ready",
            "model_promotion_allowed": "model_promotion_allowed",
            "promotion_blocker_count": "promotion_gate.promotion_blocker_count",
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
        "master_audit": (
            "Phase 11",
            "Final holdout/forward guard",
            "blocked unless explicit holdout approval",
        ),
        "project_outline": (
            "Phase 11 cannot run until Phase 10 writes a frozen manifest",
            "scripts.final_holdout.guard_final_holdout",
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
            "holdout_executed": dotted_get(payload, "summary.holdout_executed"),
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
        failure=f"missing required Phase 11 reconciliation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Phase 11 reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )

    text_results = required_text_snippets(repo_root, paths)
    check(
        checks,
        failures,
        name="coordination_docs_preserve_phase11_holdout_policy",
        passed=all(not result["error"] and not result["missing"] for result in text_results.values()),
        failure="coordination docs no longer preserve the Phase 11 holdout approval policy",
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
        failure="run-status, overview, or Phase 1B-10 reconciliation inputs are not passed report-only blocking evidence",
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
            DEFAULT_PHASE10.as_posix(),
        ],
        details={
            "run_status": None if run_status is None else run_status.get("status"),
            "overview": None if overview is None else overview.get("status"),
            "previous_reconciliation_statuses": previous_statuses,
        },
    )

    phase11_row = row_by_area(run_status, "Phase 11")
    check(
        checks,
        failures,
        name="phase11_ledger_row_is_not_approved_final_holdout",
        passed=phase11_row is not None
        and phase11_row.get("run_status") == "N/A"
        and phase11_row.get("detail_status") == "N/A_NOT_APPROVED_FINAL_HOLDOUT"
        and phase11_row.get("evidence_state") == "missing"
        and as_list(phase11_row.get("accepted_evidence")) == [],
        failure="run-status Phase 11 row is not N/A_NOT_APPROVED_FINAL_HOLDOUT/missing",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"phase11_row": dict(phase11_row or {})},
    )

    phase10 = payloads.get("phase10_reconciliation", {})
    check(
        checks,
        failures,
        name="phase10_freeze_reconciliation_blocks_final_holdout",
        passed=phase10.get("status") == "PASS_MASTER_AUDIT_PHASE10_RECONCILIATION_REPORT_ONLY"
        and dotted_get(phase10, "summary.phase10_master_audit_status")
        == "N/A_NOT_APPROVED_ARTIFACT_FREEZE"
        and dotted_get(phase10, "summary.artifact_freeze_ready") is False
        and dotted_get(phase10, "summary.artifact_freeze_allowed") is False
        and dotted_get(phase10, "summary.freeze_executed") is False
        and dotted_get(phase10, "summary.frozen_manifest_written") is False
        and dotted_get(phase10, "summary.holdout_allowed") is False
        and dotted_get(phase10, "summary.paper_live_allowed") is False,
        failure="Phase 10 reconciliation no longer blocks final holdout through missing artifact freeze",
        evidence=[DEFAULT_PHASE10.as_posix()],
        details={"phase10_summary": as_mapping(phase10.get("summary"))},
    )

    phase8 = payloads.get("phase8_decision", {})
    check(
        checks,
        failures,
        name="phase8_decision_preserves_no_holdout_touch",
        passed=phase8.get("run") == RUN_ID
        and phase8.get("promoted") is False
        and phase8.get("research_alpha_ready") is False
        and phase8.get("model_promotion_allowed") is False
        and phase8.get("final_holdout_touched") is False
        and phase8.get("used_final_holdout_for_tuning") is False
        and dotted_get(phase8, "promotion_gate.promotion_blocker_count") == 30,
        failure="Phase 8 promotion evidence no longer preserves no-final-holdout-touch blockers",
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
        name="phase8_phase9_phase10_reconciliations_preserve_blocked_holdout_path",
        passed=dotted_get(phase8_reconciliation, "summary.phase8_master_audit_status")
        == "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE"
        and dotted_get(phase8_reconciliation, "summary.model_trust_ready") is False
        and dotted_get(phase8_reconciliation, "summary.promotion_allowed") is False
        and dotted_get(phase8_reconciliation, "summary.holdout_allowed") is False
        and dotted_get(phase8_reconciliation, "summary.holdout_executed") is False
        and dotted_get(phase9_reconciliation, "summary.phase9_master_audit_status")
        == "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT"
        and dotted_get(phase9_reconciliation, "summary.future_modeling_allowed") is False
        and dotted_get(phase9_reconciliation, "summary.model_trust_ready") is False
        and dotted_get(phase9_reconciliation, "summary.promotion_allowed") is False
        and dotted_get(phase9_reconciliation, "summary.holdout_allowed") is False
        and dotted_get(phase9_reconciliation, "summary.holdout_executed") is False
        and dotted_get(phase10, "summary.phase10_master_audit_status")
        == "N/A_NOT_APPROVED_ARTIFACT_FREEZE"
        and dotted_get(phase10, "summary.holdout_allowed") is False,
        failure="Phase 8/9/10 reconciliations no longer preserve the blocked final-holdout path",
        evidence=[DEFAULT_PHASE8.as_posix(), DEFAULT_PHASE9.as_posix(), DEFAULT_PHASE10.as_posix()],
        details={
            "phase8_summary": as_mapping(phase8_reconciliation.get("summary")),
            "phase9_summary": as_mapping(phase9_reconciliation.get("summary")),
            "phase10_summary": as_mapping(phase10.get("summary")),
        },
    )

    check(
        checks,
        failures,
        name="alpha_closeout_preserves_terminal_no_alpha_no_holdout",
        passed=alpha_closeout.get("status") == "PASS_REPORT_WRITTEN"
        and alpha_closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and alpha_closeout.get("run_id") == RUN_ID
        and alpha_closeout.get("terminal_fail_count") == 5
        and alpha_closeout.get("missing_required_evidence_count") == 11
        and alpha_closeout.get("modeling_pause_required") is True
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("promotion_allowed") is False
        and non_approval_all_false(alpha_closeout),
        failure="alpha evidence closeout no longer preserves terminal no-alpha/no-holdout evidence",
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
            "promotion_allowed": alpha_closeout.get("promotion_allowed"),
            "non_approval": alpha_closeout.get("non_approval"),
        },
    )

    check(
        checks,
        failures,
        name="model_trust_promotion_holdout_paper_live_remain_blocked",
        passed=phase8.get("promoted") is False
        and phase8.get("research_alpha_ready") is False
        and phase8.get("model_promotion_allowed") is False
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("promotion_allowed") is False
        and dotted_get(phase10, "summary.artifact_freeze_ready") is False
        and all(row["model_trust_ready"] is False for row in previous_statuses.values())
        and all(row["promotion_allowed"] is False for row in previous_statuses.values())
        and all(row["holdout_allowed"] is False for row in previous_statuses.values())
        and all(row["paper_live_allowed"] is False for row in previous_statuses.values()),
        failure="model-trust, promotion, holdout, or paper/live status was unexpectedly upgraded",
        evidence=[PHASE8_DECISION.as_posix(), ALPHA_CLOSEOUT.as_posix(), DEFAULT_PHASE10.as_posix()],
        details={
            "phase8_promoted": phase8.get("promoted"),
            "phase8_research_alpha_ready": phase8.get("research_alpha_ready"),
            "phase8_model_promotion_allowed": phase8.get("model_promotion_allowed"),
            "phase10_artifact_freeze_ready": dotted_get(
                phase10, "summary.artifact_freeze_ready"
            ),
            "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
            "promotion_allowed": alpha_closeout.get("promotion_allowed"),
            "previous_reconciliation_statuses": previous_statuses,
        },
    )

    check(
        checks,
        failures,
        name="upstream_non_approval_flags_preserve_no_holdout_execution",
        passed=non_approval_all_false(phase8_reconciliation)
        and non_approval_all_false(phase9_reconciliation)
        and non_approval_all_false(phase10)
        and non_approval_all_false(alpha_closeout),
        failure="upstream non-approval evidence contains an executed forbidden action",
        evidence=[
            DEFAULT_PHASE8.as_posix(),
            DEFAULT_PHASE9.as_posix(),
            DEFAULT_PHASE10.as_posix(),
            ALPHA_CLOSEOUT.as_posix(),
        ],
        details={
            "phase8_non_approval": phase8_reconciliation.get("non_approval"),
            "phase9_non_approval": phase9_reconciliation.get("non_approval"),
            "phase10_non_approval": phase10.get("non_approval"),
            "alpha_closeout_non_approval": alpha_closeout.get("non_approval"),
        },
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "previous_reconciliation_statuses": previous_statuses,
        "phase11_row": dict(phase11_row or {}),
        "phase10_status": dotted_get(phase10, "summary.phase10_master_audit_status"),
        "artifact_freeze_ready": dotted_get(phase10, "summary.artifact_freeze_ready"),
        "frozen_manifest_written": dotted_get(phase10, "summary.frozen_manifest_written"),
        "phase8_promoted": phase8.get("promoted"),
        "phase8_research_alpha_ready": phase8.get("research_alpha_ready"),
        "phase8_model_promotion_allowed": phase8.get("model_promotion_allowed"),
        "phase8_final_holdout_touched": phase8.get("final_holdout_touched"),
        "phase8_used_final_holdout_for_tuning": phase8.get("used_final_holdout_for_tuning"),
        "promotion_blocker_count": dotted_get(phase8, "promotion_gate.promotion_blocker_count"),
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
            "finding_id": "phase11-001-final-holdout-is-na-not-approved",
            "severity": "Info",
            "finding": "Phase 11 is reconciled as N/A because final holdout is not approved.",
            "verified_facts": [
                "phase11_master_audit_status=N/A_NOT_APPROVED_FINAL_HOLDOUT",
                "final_holdout_ready=false",
                "final_holdout_executed=false",
            ],
            "limitation": "This is not a final-holdout audit pass and does not run or approve holdout.",
            "evidence_paths": [DEFAULT_RUN_STATUS.as_posix(), "MASTER_AUDIT.md"],
        },
        {
            "finding_id": "phase11-002-phase10-freeze-blocks-holdout",
            "severity": "Critical",
            "finding": "Phase 10 artifact freeze remains N/A and blocks final holdout.",
            "verified_facts": [
                f"phase10_status={derived.get('phase10_status')}",
                f"artifact_freeze_ready={derived.get('artifact_freeze_ready')}",
                f"frozen_manifest_written={derived.get('frozen_manifest_written')}",
            ],
            "limitation": "Historical archive manifests are not current active-line freeze approval.",
            "evidence_paths": [DEFAULT_PHASE10.as_posix(), "PROJECT_OUTLINE.md"],
        },
        {
            "finding_id": "phase11-003-phase8-phase9-block-holdout",
            "severity": "Critical",
            "finding": "Phase 8/9 promotion and alpha evidence remain negative and block final holdout.",
            "verified_facts": [
                f"promoted={derived.get('phase8_promoted')}",
                f"model_promotion_allowed={derived.get('phase8_model_promotion_allowed')}",
                f"phase9_verdict={derived.get('alpha_closeout_verdict')}",
                f"promotion_allowed={derived.get('promotion_allowed')}",
            ],
            "limitation": "Final holdout cannot be used to rescue or tune a closed line.",
            "evidence_paths": [PHASE8_DECISION.as_posix(), ALPHA_CLOSEOUT.as_posix()],
        },
        {
            "finding_id": "phase11-004-full-phase11-acceptance-blocked",
            "severity": "Critical",
            "finding": "Full Phase 11 Master Audit acceptance remains blocked.",
            "verified_facts": [
                "phase11_full_master_audit_accepted=false",
                "current_frozen_manifest_accepted=false",
                "holdout_allowed=false",
                "paper_live_allowed=false",
            ],
            "limitation": "Frozen-artifact lineage, holdout guard report, and forward evidence are not applicable until explicit approvals exist.",
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
    phase11_classification = (
        "N/A_NOT_APPROVED_FINAL_HOLDOUT"
        if status == PASS_STATUS
        else "FAILED_PHASE11_RECONCILIATION"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase11_reconciliation_report_only",
            "phase": "Phase 11",
            "phase_name": "Final holdout readiness / N/A status",
            "run": RUN_ID,
            "reports_root": output_rel,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "parquet_read_scope": "none",
            "phase_command_scope": "none",
            "full_phase11_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase11_master_audit_status": phase11_classification,
            "phase11_full_master_audit_accepted": False,
            "final_holdout_ready": False,
            "final_holdout_allowed": False,
            "final_holdout_executed": False,
            "holdout_executed": False,
            "artifact_freeze_ready": False,
            "frozen_manifest_required": True,
            "current_frozen_manifest_accepted": False,
            "frozen_manifest_written": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_allowed": False,
            "phase10_master_audit_status": derived.get("phase10_status"),
            "phase8_promoted": False,
            "phase8_research_alpha_ready": False,
            "phase8_model_promotion_allowed": False,
            "phase8_final_holdout_touched": False,
            "phase8_used_final_holdout_for_tuning": False,
            "promotion_blocker_count": derived.get("promotion_blocker_count"),
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
                "run-status Phase 11 row is exactly N/A_NOT_APPROVED_FINAL_HOLDOUT",
                "Phase 1B/2/3/4/5/6/7/8/9/10 reconciliations are passed report-only blocking evidence",
                "Phase 10 remains N/A_NOT_APPROVED_ARTIFACT_FREEZE with artifact_freeze_ready=false and frozen_manifest_written=false",
                "Phase 8 decision remains promoted=false, model_promotion_allowed=false, final_holdout_touched=false, and used_final_holdout_for_tuning=false",
                "Phase 9 closeout remains CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE with future_modeling_allowed=false and promotion_allowed=false",
                "report explicitly states Phase 11 is N/A/blocked, not executed, and not holdout-ready",
                "model-trust, promotion, holdout, paper/live, and full Phase 11 acceptance remain blocked",
                "all forbidden action flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "Phase 11 ledger is upgraded from N/A without explicit approved final-holdout evidence",
                "Phase 10 is upgraded to freeze-ready or frozen-manifest-written without separate approval",
                "any upstream report upgrades model trust, promotion, holdout, paper/live, or final-holdout status",
                "Phase 8, Phase 9, or Phase 10 blockers are absent or contradicted",
                "any forbidden action flag is true",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan only the next bounded Master Audit closeout/readiness area from existing "
            "JSON/MD evidence; do not run holdout, data/model, WFA, prediction, freeze, "
            "promotion, paper/live, provider, cleanup, staging, commit, or push commands."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Phase 11 Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 11 status: `{summary.get('phase11_master_audit_status')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Final holdout ready: `{summary.get('final_holdout_ready')}`",
        f"- Final holdout allowed: `{summary.get('final_holdout_allowed')}`",
        f"- Final holdout executed: `{summary.get('final_holdout_executed')}`",
        f"- Artifact freeze ready: `{summary.get('artifact_freeze_ready')}`",
        f"- Current frozen manifest accepted: `{summary.get('current_frozen_manifest_accepted')}`",
        f"- Model-trust ready: `{summary.get('model_trust_ready')}`",
        f"- Promotion allowed: `{summary.get('promotion_allowed')}`",
        f"- Paper/live allowed: `{summary.get('paper_live_allowed')}`",
        f"- Phase 10 status: `{summary.get('phase10_master_audit_status')}`",
        f"- Phase 8 final holdout touched: `{summary.get('phase8_final_holdout_touched')}`",
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
            "- This reconciliation did not run the final-holdout guard, artifact freeze, phase audits, data/model commands, WFA/modeling, prediction generation/materialization, Phase 8 refresh, provider/network calls, promotion, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, model artifacts, or frozen artifact payloads, and it did not consume or advance the hardened split candidate or hardened Phase 6/7 materialization path.",
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
        f"phase11_status={report['summary']['phase11_master_audit_status']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
