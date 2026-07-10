#!/usr/bin/env python3
"""Build the report-only Master Audit closeout/readiness rollup.

This command consumes existing JSON/MD repo evidence only. It does not run phase
audits, data/model commands, WFA/modeling, predictions, Phase 8 refresh,
provider calls, promotion, freeze, holdout, paper/live, cleanup, staging,
commit, or push.
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
STAGE = "master_audit_closeout"
PASS_STATUS = "PASS_MASTER_AUDIT_CLOSEOUT_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_CLOSEOUT_REPORT_ONLY"

RUN_ID = "tier1_core_phase6_full_predictions_20260706"

DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_closeout_20260709")
REPORT_JSON = "master_audit_closeout.json"
REPORT_MD = "master_audit_closeout.md"

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
PHASE8_DECISION = Path(f"reports/phase8/{RUN_ID}/alpha_promotion_decision.json")
ALPHA_CLOSEOUT = Path(
    "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
    "alpha_evidence_completion_closeout.json"
)

PHASE_INPUTS = {
    "phase1b_reconciliation": Path(
        "reports/master_audit/master_audit_phase1b_reconciliation_20260709/"
        "master_audit_phase1b_reconciliation.json"
    ),
    **{
        f"phase{phase}_reconciliation": Path(
            f"reports/master_audit/master_audit_phase{phase}_reconciliation_20260709/"
            f"master_audit_phase{phase}_reconciliation.json"
        )
        for phase in range(2, 12)
    },
}

EXPECTED_PHASE_STATUSES = {
    "phase1b_reconciliation": "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY",
    **{
        f"phase{phase}_reconciliation": (
            f"PASS_MASTER_AUDIT_PHASE{phase}_RECONCILIATION_REPORT_ONLY"
        )
        for phase in range(2, 12)
    },
}

REQUIRED_INPUTS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "run_status": DEFAULT_RUN_STATUS,
    "overview": DEFAULT_OVERVIEW,
    **PHASE_INPUTS,
    "phase8_decision": PHASE8_DECISION,
    "alpha_closeout": ALPHA_CLOSEOUT,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
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
    "artifact_freeze_command_executed": False,
    "artifact_freeze_manifest_written": False,
    "freeze_executed": False,
    "final_holdout_guard_executed": False,
    "final_holdout_report_written": False,
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


def non_approval_all_false(payload: Mapping[str, Any]) -> bool:
    non_approval = as_mapping(payload.get("non_approval"))
    return bool(non_approval) and all(value is False for value in non_approval.values())


def blocker_count(payload: Mapping[str, Any]) -> int:
    return len(as_list(payload.get("blockers")))


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
        "overview": {
            "status": "status",
            "failure_count": "summary.failure_count",
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
            "promotion_allowed": "promotion_allowed",
        },
    }
    for name in PHASE_INPUTS:
        json_fields[name] = {
            "status": "status",
            "failure_count": "summary.failure_count",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "holdout_allowed": "summary.holdout_allowed",
            "paper_live_allowed": "summary.paper_live_allowed",
        }
    json_fields["phase8_reconciliation"].update(
        {
            "phase8_master_audit_status": "summary.phase8_master_audit_status",
            "research_alpha_ready": "summary.research_alpha_ready",
        }
    )
    json_fields["phase9_reconciliation"].update(
        {
            "phase9_master_audit_status": "summary.phase9_master_audit_status",
            "alpha_closeout_verdict": "summary.alpha_closeout_verdict",
            "future_modeling_allowed": "summary.future_modeling_allowed",
        }
    )
    json_fields["phase10_reconciliation"].update(
        {
            "phase10_master_audit_status": "summary.phase10_master_audit_status",
            "artifact_freeze_ready": "summary.artifact_freeze_ready",
            "frozen_manifest_written": "summary.frozen_manifest_written",
        }
    )
    json_fields["phase11_reconciliation"].update(
        {
            "phase11_master_audit_status": "summary.phase11_master_audit_status",
            "final_holdout_ready": "summary.final_holdout_ready",
            "final_holdout_allowed": "summary.final_holdout_allowed",
            "final_holdout_executed": "summary.final_holdout_executed",
        }
    )
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
            "Phase 10",
            "Phase 11",
            "Research Readiness",
            "paper/live",
        ),
        "project_outline": (
            "Phase 11 cannot run until Phase 10 writes a frozen manifest",
            "This repository must not make live-trading or paper-trading readiness claims",
        ),
        "codex_handoff": ("Master Audit closeout/readiness rollup",),
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


def phase_statuses(payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for name in EXPECTED_PHASE_STATUSES:
        payload = payloads.get(name, {})
        holdout_allowed = dotted_get(payload, "summary.holdout_allowed")
        if holdout_allowed is None and name == "phase11_reconciliation":
            holdout_allowed = dotted_get(payload, "summary.final_holdout_allowed")
        statuses[name] = {
            "status": payload.get("status"),
            "failure_count": dotted_get(payload, "summary.failure_count"),
            "model_trust_ready": dotted_get(payload, "summary.model_trust_ready"),
            "promotion_allowed": dotted_get(payload, "summary.promotion_allowed"),
            "holdout_allowed": holdout_allowed,
            "paper_live_allowed": dotted_get(payload, "summary.paper_live_allowed"),
            "freeze_executed": dotted_get(payload, "summary.freeze_executed"),
            "holdout_executed": dotted_get(payload, "summary.holdout_executed"),
        }
    return statuses


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
        failure=f"missing required Master Audit closeout inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Master Audit closeout: {output_rel}",
        details={"reports_root": output_rel},
    )

    text_results = required_text_snippets(repo_root, paths)
    check(
        checks,
        failures,
        name="coordination_docs_preserve_closeout_policy",
        passed=all(not result["error"] and not result["missing"] for result in text_results.values()),
        failure="coordination docs no longer preserve Master Audit closeout/readiness policy",
        evidence=["MASTER_AUDIT.md", "PROJECT_OUTLINE.md", "CODEX_HANDOFF.md"],
        details=text_results,
    )

    run_status = payloads.get("run_status", {})
    overview = payloads.get("overview", {})
    statuses = phase_statuses(payloads)
    phase_reports_pass = all(
        payloads.get(name, {}).get("status") == expected
        and dotted_get(payloads.get(name), "summary.failure_count") == 0
        and dotted_get(payloads.get(name), "summary.model_trust_ready") is False
        and dotted_get(payloads.get(name), "summary.promotion_allowed") is False
        and statuses[name]["holdout_allowed"] is False
        and dotted_get(payloads.get(name), "summary.paper_live_allowed") is False
        for name, expected in EXPECTED_PHASE_STATUSES.items()
    )
    check(
        checks,
        failures,
        name="phase_reconciliations_pass_report_only_and_block_readiness",
        passed=run_status.get("status") == "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
        and overview.get("status") == "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
        and phase_reports_pass,
        failure="run-status, overview, or Phase 1B-11 reconciliation reports are not passed report-only blocking evidence",
        evidence=[DEFAULT_RUN_STATUS.as_posix(), DEFAULT_OVERVIEW.as_posix(), *[p.as_posix() for p in PHASE_INPUTS.values()]],
        details={"run_status": run_status.get("status"), "overview": overview.get("status"), "phase_statuses": statuses},
    )

    ledger_expectations = {
        "Research Factory": ("NOT_RUN", "NOT_RUN_NO_RESEARCH_FACTORY_EXECUTION_PERMISSION"),
        "Research Readiness": ("NOT_RUN", "NOT_RUN_RESEARCH_READINESS_REVIEW_NOT_EXECUTED"),
        "Production / Paper / Live": ("N/A", "N/A_NOT_APPROVED_NOT_IN_SCOPE"),
        "Phase 10": ("N/A", "N/A_NOT_APPROVED_ARTIFACT_FREEZE"),
        "Phase 11": ("N/A", "N/A_NOT_APPROVED_FINAL_HOLDOUT"),
    }
    ledger_rows = {
        area: dict(row_by_area(run_status, area) or {})
        for area in ledger_expectations
    }
    ledger_pass = all(
        ledger_rows[area].get("run_status") == expected[0]
        and ledger_rows[area].get("detail_status") == expected[1]
        for area, expected in ledger_expectations.items()
    )
    check(
        checks,
        failures,
        name="non_phase_readiness_ledger_remains_not_run_or_na",
        passed=ledger_pass,
        failure="Research readiness, research factory, production/paper/live, Phase 10, or Phase 11 ledger rows were unexpectedly upgraded",
        evidence=[DEFAULT_RUN_STATUS.as_posix()],
        details={"ledger_rows": ledger_rows},
    )

    phase8_recon = payloads.get("phase8_reconciliation", {})
    phase9_recon = payloads.get("phase9_reconciliation", {})
    phase10 = payloads.get("phase10_reconciliation", {})
    phase11 = payloads.get("phase11_reconciliation", {})
    phase8_decision = payloads.get("phase8_decision", {})
    alpha_closeout = payloads.get("alpha_closeout", {})
    check(
        checks,
        failures,
        name="phase8_phase9_current_line_closed_no_alpha",
        passed=dotted_get(phase8_recon, "summary.phase8_master_audit_status")
        == "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE"
        and dotted_get(phase8_recon, "summary.research_alpha_ready") is False
        and phase8_decision.get("run") == RUN_ID
        and phase8_decision.get("promoted") is False
        and phase8_decision.get("research_alpha_ready") is False
        and phase8_decision.get("model_promotion_allowed") is False
        and phase8_decision.get("final_holdout_touched") is False
        and phase8_decision.get("used_final_holdout_for_tuning") is False
        and dotted_get(phase8_decision, "promotion_gate.promotion_blocker_count") == 30
        and blocker_count(phase8_decision) == 30
        and dotted_get(phase9_recon, "summary.phase9_master_audit_status")
        == "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT"
        and dotted_get(phase9_recon, "summary.alpha_closeout_verdict")
        == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and alpha_closeout.get("status") == "PASS_REPORT_WRITTEN"
        and alpha_closeout.get("verdict") == "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
        and alpha_closeout.get("run_id") == RUN_ID
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("promotion_allowed") is False,
        failure="Phase 8/9 evidence no longer preserves closed no-alpha/no-promotion status",
        evidence=[
            PHASE_INPUTS["phase8_reconciliation"].as_posix(),
            PHASE_INPUTS["phase9_reconciliation"].as_posix(),
            PHASE8_DECISION.as_posix(),
            ALPHA_CLOSEOUT.as_posix(),
        ],
        details={
            "phase8_reconciliation_summary": phase8_recon.get("summary"),
            "phase9_reconciliation_summary": phase9_recon.get("summary"),
            "phase8_decision": {
                "promoted": phase8_decision.get("promoted"),
                "research_alpha_ready": phase8_decision.get("research_alpha_ready"),
                "model_promotion_allowed": phase8_decision.get("model_promotion_allowed"),
                "final_holdout_touched": phase8_decision.get("final_holdout_touched"),
                "used_final_holdout_for_tuning": phase8_decision.get("used_final_holdout_for_tuning"),
            },
            "alpha_closeout": {
                "status": alpha_closeout.get("status"),
                "verdict": alpha_closeout.get("verdict"),
                "future_modeling_allowed": alpha_closeout.get("future_modeling_allowed"),
                "promotion_allowed": alpha_closeout.get("promotion_allowed"),
            },
        },
    )

    check(
        checks,
        failures,
        name="phase10_phase11_freeze_holdout_remain_na",
        passed=dotted_get(phase10, "summary.phase10_master_audit_status")
        == "N/A_NOT_APPROVED_ARTIFACT_FREEZE"
        and dotted_get(phase10, "summary.artifact_freeze_ready") is False
        and dotted_get(phase10, "summary.artifact_freeze_allowed") is False
        and dotted_get(phase10, "summary.freeze_executed") is False
        and dotted_get(phase10, "summary.frozen_manifest_written") is False
        and dotted_get(phase11, "summary.phase11_master_audit_status")
        == "N/A_NOT_APPROVED_FINAL_HOLDOUT"
        and dotted_get(phase11, "summary.final_holdout_ready") is False
        and dotted_get(phase11, "summary.final_holdout_allowed") is False
        and dotted_get(phase11, "summary.final_holdout_executed") is False
        and dotted_get(phase11, "summary.current_frozen_manifest_accepted") is False,
        failure="Phase 10/11 evidence no longer preserves freeze/holdout N/A blocked status",
        evidence=[
            PHASE_INPUTS["phase10_reconciliation"].as_posix(),
            PHASE_INPUTS["phase11_reconciliation"].as_posix(),
        ],
        details={
            "phase10_summary": phase10.get("summary"),
            "phase11_summary": phase11.get("summary"),
        },
    )

    no_ready_upgrades = all(
        row["model_trust_ready"] is False
        and row["promotion_allowed"] is False
        and row["holdout_allowed"] is False
        and row["paper_live_allowed"] is False
        for row in statuses.values()
    )
    check(
        checks,
        failures,
        name="model_trust_promotion_freeze_holdout_paper_live_blocked",
        passed=no_ready_upgrades
        and alpha_closeout.get("future_modeling_allowed") is False
        and alpha_closeout.get("promotion_allowed") is False
        and phase8_decision.get("model_promotion_allowed") is False
        and dotted_get(phase10, "summary.artifact_freeze_ready") is False
        and dotted_get(phase11, "summary.final_holdout_ready") is False,
        failure="model-trust, promotion, freeze, holdout, or paper/live state was unexpectedly upgraded",
        evidence=[
            PHASE8_DECISION.as_posix(),
            ALPHA_CLOSEOUT.as_posix(),
            PHASE_INPUTS["phase10_reconciliation"].as_posix(),
            PHASE_INPUTS["phase11_reconciliation"].as_posix(),
        ],
        details={"phase_statuses": statuses},
    )

    upstream_non_approval = [
        payloads.get("phase8_reconciliation", {}),
        payloads.get("phase9_reconciliation", {}),
        payloads.get("phase10_reconciliation", {}),
        payloads.get("phase11_reconciliation", {}),
        payloads.get("alpha_closeout", {}),
    ]
    check(
        checks,
        failures,
        name="non_approval_flags_preserve_no_forbidden_execution",
        passed=all(non_approval_all_false(payload) for payload in upstream_non_approval),
        failure="upstream non-approval evidence contains an executed forbidden action",
        evidence=[
            PHASE_INPUTS["phase8_reconciliation"].as_posix(),
            PHASE_INPUTS["phase9_reconciliation"].as_posix(),
            PHASE_INPUTS["phase10_reconciliation"].as_posix(),
            PHASE_INPUTS["phase11_reconciliation"].as_posix(),
            ALPHA_CLOSEOUT.as_posix(),
        ],
        details={
            "phase8_non_approval": payloads.get("phase8_reconciliation", {}).get("non_approval"),
            "phase9_non_approval": payloads.get("phase9_reconciliation", {}).get("non_approval"),
            "phase10_non_approval": payloads.get("phase10_reconciliation", {}).get("non_approval"),
            "phase11_non_approval": payloads.get("phase11_reconciliation", {}).get("non_approval"),
            "alpha_closeout_non_approval": payloads.get("alpha_closeout", {}).get("non_approval"),
        },
    )

    for item in evidence:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "phase_statuses": statuses,
        "ledger_rows": ledger_rows,
        "current_line_classification": dotted_get(run_status, "summary.current_line_classification"),
        "current_split_classification": dotted_get(run_status, "summary.current_split_classification"),
        "phase8_master_audit_status": dotted_get(phase8_recon, "summary.phase8_master_audit_status"),
        "phase9_master_audit_status": dotted_get(phase9_recon, "summary.phase9_master_audit_status"),
        "phase10_master_audit_status": dotted_get(phase10, "summary.phase10_master_audit_status"),
        "phase11_master_audit_status": dotted_get(phase11, "summary.phase11_master_audit_status"),
        "promotion_blocker_count": dotted_get(phase8_decision, "promotion_gate.promotion_blocker_count"),
        "alpha_closeout_verdict": alpha_closeout.get("verdict"),
        "terminal_fail_count": alpha_closeout.get("terminal_fail_count"),
        "missing_required_evidence_count": alpha_closeout.get("missing_required_evidence_count"),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "closeout-001-current-line-closed",
            "severity": "Critical",
            "finding": "Current Tier 1 line remains closed for alpha/model-trust evidence.",
            "verified_facts": [
                f"current_line_classification={derived.get('current_line_classification')}",
                f"phase8_status={derived.get('phase8_master_audit_status')}",
                f"phase9_verdict={derived.get('alpha_closeout_verdict')}",
            ],
            "classification": "blocked_not_model_trust_ready",
            "evidence_paths": [PHASE8_DECISION.as_posix(), ALPHA_CLOSEOUT.as_posix()],
        },
        {
            "finding_id": "closeout-002-split-research-only",
            "severity": "Critical",
            "finding": "Current split remains same-fold rolling-retraining research evidence only.",
            "verified_facts": [
                f"current_split_classification={derived.get('current_split_classification')}",
            ],
            "classification": "not_independent_holdout_evidence",
            "evidence_paths": [DEFAULT_RUN_STATUS.as_posix(), PHASE_INPUTS["phase5_reconciliation"].as_posix()],
        },
        {
            "finding_id": "closeout-003-freeze-and-holdout-na",
            "severity": "Critical",
            "finding": "Artifact freeze and final holdout remain N/A/not approved.",
            "verified_facts": [
                f"phase10_status={derived.get('phase10_master_audit_status')}",
                f"phase11_status={derived.get('phase11_master_audit_status')}",
            ],
            "classification": "freeze_holdout_blocked",
            "evidence_paths": [
                PHASE_INPUTS["phase10_reconciliation"].as_posix(),
                PHASE_INPUTS["phase11_reconciliation"].as_posix(),
            ],
        },
        {
            "finding_id": "closeout-004-research-readiness-not-run",
            "severity": "High",
            "finding": "Research Readiness and Research Factory ledger areas remain NOT_RUN.",
            "verified_facts": [
                "Research Readiness detail_status=NOT_RUN_RESEARCH_READINESS_REVIEW_NOT_EXECUTED",
                "Research Factory detail_status=NOT_RUN_NO_RESEARCH_FACTORY_EXECUTION_PERMISSION",
            ],
            "classification": "readiness_closeout_blocked",
            "evidence_paths": [DEFAULT_RUN_STATUS.as_posix()],
        },
        {
            "finding_id": "closeout-005-paper-live-na",
            "severity": "Critical",
            "finding": "Production, paper, and live readiness remain N/A/not in scope.",
            "verified_facts": [
                "Production / Paper / Live detail_status=N/A_NOT_APPROVED_NOT_IN_SCOPE",
            ],
            "classification": "paper_live_blocked",
            "evidence_paths": [DEFAULT_RUN_STATUS.as_posix(), "PROJECT_OUTLINE.md"],
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
    closeout_classification = (
        "REPORT_ONLY_CLOSEOUT_BLOCKED_NOT_READY"
        if status == PASS_STATUS
        else "FAILED_MASTER_AUDIT_CLOSEOUT"
    )
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_closeout_report_only",
            "reports_root": output_rel,
            "run": RUN_ID,
            "evidence_mode": "existing_json_md_repo_evidence_only",
            "parquet_read_scope": "none",
            "phase_command_scope": "none",
            "full_master_audit_acceptance": False,
        },
        "summary": {
            "failure_count": len(failures),
            "check_count": len(checks),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "closeout_classification": closeout_classification,
            "master_audit_report_only_closeout_complete": status == PASS_STATUS,
            "full_master_audit_accepted": False,
            "current_line_classification": derived.get("current_line_classification"),
            "current_split_classification": derived.get("current_split_classification"),
            "phase8_master_audit_status": derived.get("phase8_master_audit_status"),
            "phase9_master_audit_status": derived.get("phase9_master_audit_status"),
            "phase10_master_audit_status": derived.get("phase10_master_audit_status"),
            "phase11_master_audit_status": derived.get("phase11_master_audit_status"),
            "alpha_closeout_verdict": derived.get("alpha_closeout_verdict"),
            "promotion_blocker_count": derived.get("promotion_blocker_count"),
            "terminal_fail_count": derived.get("terminal_fail_count"),
            "missing_required_evidence_count": derived.get("missing_required_evidence_count"),
            "research_readiness_ready": False,
            "research_factory_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "artifact_freeze_ready": False,
            "final_holdout_ready": False,
            "paper_live_ready": False,
            "production_ready": False,
            "independent_holdout_evidence_ready": False,
            **dict(NON_APPROVAL),
            "finding_counts_by_severity": finding_counts(findings),
        },
        "input_evidence": evidence,
        "phase_reconciliation_statuses": derived.get("phase_statuses", {}),
        "readiness_ledger_rows": derived.get("ledger_rows", {}),
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
                "Phase 1B-11 reconciliation reports are report-only PASS with zero failures",
                "Phase 8 remains failing/no-promotion and did not touch final holdout",
                "Phase 9 remains CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
                "Phase 10 remains N/A_NOT_APPROVED_ARTIFACT_FREEZE",
                "Phase 11 remains N/A_NOT_APPROVED_FINAL_HOLDOUT",
                "Research Readiness and Research Factory remain NOT_RUN",
                "Production / Paper / Live remains N/A_NOT_APPROVED_NOT_IN_SCOPE",
                "all blocked readiness and forbidden execution flags remain false",
            ],
            "fail": [
                "missing/unreadable required input",
                "any Phase 1B-11 reconciliation report is missing, failing, or upgraded",
                "any model-trust, promotion, freeze, holdout, paper/live, or production readiness flag is upgraded",
                "Phase 8, Phase 9, Phase 10, or Phase 11 blockers are absent or contradicted",
                "any forbidden execution flag is true",
                "output root is outside the approved reports tree",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Stop Master Audit implementation for this current line unless a separate bounded "
            "evidence-work item is approved; model-trust, promotion, freeze, holdout, paper/live, "
            "and production remain blocked."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Closeout",
        "",
        f"- Status: `{report['status']}`",
        f"- Closeout classification: `{summary.get('closeout_classification')}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Checks: `{summary.get('passed_check_count')}` passed, `{summary.get('failed_check_count')}` failed",
        f"- Current line: `{summary.get('current_line_classification')}`",
        f"- Current split: `{summary.get('current_split_classification')}`",
        f"- Model-trust ready: `{summary.get('model_trust_ready')}`",
        f"- Promotion allowed: `{summary.get('promotion_allowed')}`",
        f"- Artifact freeze ready: `{summary.get('artifact_freeze_ready')}`",
        f"- Final holdout ready: `{summary.get('final_holdout_ready')}`",
        f"- Paper/live ready: `{summary.get('paper_live_ready')}`",
        f"- Production ready: `{summary.get('production_ready')}`",
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
    lines.extend(["", "## Readiness Ledger Rows", ""])
    for area, row in report.get("readiness_ledger_rows", {}).items():
        lines.append(
            f"- `{area}` run_status=`{row.get('run_status')}` detail_status=`{row.get('detail_status')}`"
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
            "- This closeout did not run phase audits, data/model commands, WFA/modeling, prediction generation/materialization, Phase 8 refresh, provider/network calls, promotion, artifact freeze, final-holdout guard, paper/live, cleanup, staging, commit, or push. It did not read DBN, raw parquet, causal parquet, label parquet, feature parquet, prediction parquet, model artifacts, or frozen artifact payloads, and it did not consume or advance the hardened split candidate or hardened Phase 6/7 materialization path.",
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
        f"closeout={report['summary']['closeout_classification']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
