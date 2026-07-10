#!/usr/bin/env python3
"""Build the report-only Research Factory / Research Readiness evidence map.

This command inventories existing repo evidence only. It does not run phase
audits, data/model commands, WFA/modeling, predictions, Phase 8 refresh,
provider calls, promotion, freeze, holdout, paper/live, cleanup, staging,
commit, or push.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_closeout as closeout
from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_research_factory_readiness"
PASS_STATUS = "PASS_MASTER_AUDIT_RESEARCH_FACTORY_READINESS_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_RESEARCH_FACTORY_READINESS_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_research_factory_readiness_20260710"
)
REPORT_JSON = "master_audit_research_factory_readiness.json"
REPORT_MD = "master_audit_research_factory_readiness.md"

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_OVERVIEW = Path(
    "reports/master_audit/master_audit_overview_20260709/master_audit_overview.json"
)
DEFAULT_CLOSEOUT = Path(
    "reports/master_audit/master_audit_closeout_20260709/master_audit_closeout.json"
)
DEFAULT_GAP_REMEDIATION = Path(
    "reports/master_audit/master_audit_gap_remediation_20260710/"
    "master_audit_gap_remediation_evidence_map.json"
)

REQUIRED_DOCS = {
    "master_audit": Path("MASTER_AUDIT.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
}

PHASE_RECONCILIATION_REPORTS = {
    "phase1b_reconciliation_json": Path(
        "reports/master_audit/master_audit_phase1b_reconciliation_20260709/"
        "master_audit_phase1b_reconciliation.json"
    ),
    "phase1b_reconciliation_md": Path(
        "reports/master_audit/master_audit_phase1b_reconciliation_20260709/"
        "master_audit_phase1b_reconciliation.md"
    ),
    **{
        f"phase{phase}_reconciliation_json": Path(
            f"reports/master_audit/master_audit_phase{phase}_reconciliation_20260709/"
            f"master_audit_phase{phase}_reconciliation.json"
        )
        for phase in range(2, 12)
    },
    **{
        f"phase{phase}_reconciliation_md": Path(
            f"reports/master_audit/master_audit_phase{phase}_reconciliation_20260709/"
            f"master_audit_phase{phase}_reconciliation.md"
        )
        for phase in range(2, 12)
    },
}

LIFECYCLE_DEFAULTS = [
    (
        "audit",
        "Partially Automated",
        "Inferred",
        [
            "reports/master_audit/master_audit_run_status_20260709/"
            "master_audit_run_status.json",
            "scripts/validation/build_master_audit_*.py",
        ],
        ["Research Factory audit row remains NOT_RUN."],
        ["phase_audits_executed"],
        "Report-only audit scaffolding exists, but full Research Factory audit execution is not accepted.",
    ),
    (
        "generate_data",
        "Missing",
        "Not established",
        [],
        ["Phase 1A/1B direct Master Audit evidence is NOT_RUN or unknown."],
        ["provider_network_calls_executed", "data_model_commands_executed"],
        "No provider/source acquisition or raw conversion execution is accepted by this evidence map.",
    ),
    (
        "generate_labels",
        "Partially Automated",
        "Inferred",
        ["Phase 3 row in run-status ledger is limited-scope evidence."],
        ["No full label-generation Research Factory evidence."],
        ["data_model_commands_executed"],
        "Limited target-timing evidence exists, but label generation is not Factory-ready evidence.",
    ),
    (
        "generate_features",
        "Partially Automated",
        "Inferred",
        ["Phase 4 row in run-status ledger is limited-scope evidence."],
        ["No full feature-generation Research Factory evidence."],
        ["data_model_commands_executed"],
        "Limited feature-leakage evidence exists, not full automated feature-factory proof.",
    ),
    (
        "create_wfa_splits",
        "Partially Automated",
        "Inferred",
        ["Phase 5 row in run-status ledger is limited-scope evidence."],
        ["Current split remains same-fold rolling-retraining research-only evidence."],
        ["wfa_modeling_executed"],
        "Split planning evidence exists but does not establish independent holdout readiness.",
    ),
    (
        "train",
        "Missing",
        "Not established",
        [],
        ["Phase 6 direct Master Audit evidence is NOT_RUN/unknown."],
        ["wfa_modeling_executed"],
        "No accepted training execution evidence is available for this map.",
    ),
    (
        "predict",
        "Missing",
        "Not established",
        [],
        ["Prediction materialization is not approved and Phase 7 direct evidence is missing."],
        ["prediction_generation_executed", "prediction_materialization_executed"],
        "No accepted prediction artifact evidence is available for this map.",
    ),
    (
        "evaluate",
        "Partially Automated",
        "Verified",
        ["Phase 8 row in run-status ledger is current failing promotion evidence."],
        ["Evaluation rejects promotion and does not establish model trust."],
        ["phase8_refresh_executed", "promotion_executed"],
        "Accepted evaluation evidence is blocking evidence, not readiness evidence.",
    ),
    (
        "stress_test",
        "Partially Automated",
        "Inferred",
        ["Phase 9 row in run-status ledger is limited-scope alpha evidence closeout."],
        ["Missing/failed baseline, null, statistical-validity, and execution-realism blockers remain."],
        ["wfa_modeling_executed", "prediction_materialization_executed"],
        "Stress/diagnostic evidence exists only as limited-scope closeout evidence.",
    ),
    (
        "score",
        "Partially Automated",
        "Verified",
        ["Current line classification is closed_no_alpha_evidence."],
        ["No score supports promotion, freeze, holdout, paper/live, or production readiness."],
        ["promotion_executed"],
        "The current score is a blocking score for alpha/model-trust use.",
    ),
    (
        "promote_reject",
        "Partially Automated",
        "Verified",
        ["Closeout summary has promotion_allowed=false and model_trust_ready=false."],
        ["Promotion path is blocked; reject/block is the only accepted outcome."],
        ["promotion_executed", "artifact_freeze_command_executed", "final_holdout_guard_executed"],
        "Reject/block evidence is accepted; promotion remains disallowed.",
    ),
]

SCORE_COMPONENTS = (
    "platform_integrity",
    "data_integrity",
    "leakage_control",
    "statistical_validity",
    "governance",
    "research_automation",
    "operational_resilience",
)

NON_APPROVAL = dict(closeout.NON_APPROVAL)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return closeout.read_json_object(path)


def dotted_get(payload: Mapping[str, Any], dotted: str, default: Any = None) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def collect_source_surface(repo_root: Path) -> dict[str, Any]:
    builder_paths = sorted(
        rel(path, repo_root)
        for path in (repo_root / "scripts" / "validation").glob("build_master_audit_*.py")
        if path.is_file()
    )
    test_paths = sorted(
        rel(path, repo_root)
        for path in (repo_root / "tests" / "validation").glob("test_build_master_audit_*.py")
        if path.is_file()
    )
    return {
        "builder_paths": builder_paths,
        "test_paths": test_paths,
        "builder_count": len(builder_paths),
        "test_count": len(test_paths),
        "new_builder_present": (
            "scripts/validation/build_master_audit_research_factory_readiness.py"
            in builder_paths
        ),
        "new_test_present": (
            "tests/validation/test_build_master_audit_research_factory_readiness.py"
            in test_paths
        ),
    }


def build_input_paths(
    *,
    run_status: Path,
    overview: Path,
    closeout_path: Path,
) -> dict[str, Path]:
    return {
        **REQUIRED_DOCS,
        "run_status": run_status,
        "overview": overview,
        "closeout": closeout_path,
        **PHASE_RECONCILIATION_REPORTS,
    }


def build_input_evidence(
    *,
    repo_root: Path,
    paths: Mapping[str, Path],
    dirty_map: Mapping[str, str],
) -> list[dict[str, Any]]:
    json_fields = {
        "run_status": {
            "status": "status",
            "dirty_worktree_entry_count": "summary.dirty_worktree_entry_count",
            "stale_or_unknown_source_hash_mismatch_count": (
                "summary.stale_or_unknown_source_hash_mismatch_count"
            ),
            "current_line_classification": "summary.current_line_classification",
            "current_split_classification": "summary.current_split_classification",
        },
        "overview": {
            "status": "status",
            "failure_count": "summary.failure_count",
        },
        "closeout": {
            "status": "status",
            "closeout_classification": "summary.closeout_classification",
            "research_factory_ready": "summary.research_factory_ready",
            "research_readiness_ready": "summary.research_readiness_ready",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "paper_live_ready": "summary.paper_live_ready",
            "production_ready": "summary.production_ready",
        },
    }
    for name in PHASE_RECONCILIATION_REPORTS:
        if name.endswith("_json"):
            json_fields[name] = {
                "status": "status",
                "failure_count": "summary.failure_count",
            }
    return [
        inventory.evidence_file(
            repo_root=repo_root,
            relative_path=path,
            json_fields=json_fields.get(name),
            dirty_map=dirty_map,
        )
        for name, path in paths.items()
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


def load_optional_payload(
    *,
    repo_root: Path,
    path: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    resolved = resolve_path(repo_root, path)
    if not resolved.exists():
        return None, None
    payload, error = read_json_object(resolved)
    if error:
        return None, f"optional JSON input unavailable: {path.as_posix()} ({error})"
    return payload, None


def run_status_row(run_status: Mapping[str, Any], audit_area: str) -> dict[str, Any]:
    for row in as_list(run_status.get("run_status_table")):
        if isinstance(row, Mapping) and row.get("audit_area") == audit_area:
            return dict(row)
    return {}


def non_approval_all_false(payload: Mapping[str, Any]) -> bool:
    non_approval = payload.get("non_approval")
    return isinstance(non_approval, Mapping) and all(value is False for value in non_approval.values())


def gap_area_score_eligible(
    gap_payload: Mapping[str, Any],
    area: str,
) -> bool:
    gap_maps = gap_payload.get("gap_maps")
    if not isinstance(gap_maps, Mapping):
        return False
    area_map = gap_maps.get(area)
    if not isinstance(area_map, Mapping):
        return False
    if area_map.get("status") != "PASS" or area_map.get("score_eligible") is not True:
        return False
    checks = as_list(area_map.get("checks"))
    if not checks:
        return False
    for check in checks:
        if not isinstance(check, Mapping):
            return False
        if check.get("status") != "PASS":
            return False
        hashes = check.get("source_hashes")
        if not isinstance(hashes, Mapping) or not hashes:
            return False
        if any(not value for value in hashes.values()):
            return False
    return True


def gap_remediation_summary(gap_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not gap_payload:
        return {
            "available": False,
            "path": None,
            "gap_area_statuses": {},
            "score_eligible_areas": [],
        }
    gap_maps = gap_payload.get("gap_maps")
    area_statuses: dict[str, Any] = {}
    score_eligible: list[str] = []
    if isinstance(gap_maps, Mapping):
        for area, area_map in gap_maps.items():
            if isinstance(area_map, Mapping):
                area_statuses[str(area)] = area_map.get("status")
                if gap_area_score_eligible(gap_payload, str(area)):
                    score_eligible.append(str(area))
    outputs = gap_payload.get("outputs")
    path = outputs.get("json") if isinstance(outputs, Mapping) else None
    return {
        "available": True,
        "path": path,
        "gap_area_statuses": area_statuses,
        "score_eligible_areas": sorted(score_eligible),
    }


def current_git_status(
    *,
    repo_root: Path,
    git_status_lines: Sequence[str] | None,
) -> dict[str, Any]:
    if git_status_lines is not None:
        return {"returncode": 0, "error": None, "short_lines": list(git_status_lines)}
    status = inventory.collect_git_status(repo_root)
    return {
        "returncode": status["returncode"],
        "error": status["error"],
        "short_lines": list(status["status_lines"]),
    }


def stale_evidence_notes(
    *,
    run_status: Mapping[str, Any],
    git_status: Mapping[str, Any],
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    summary = run_status.get("summary", {}) if isinstance(run_status.get("summary"), Mapping) else {}
    embedded_dirty_count = summary.get("dirty_worktree_entry_count")
    embedded_mismatch_count = summary.get("stale_or_unknown_source_hash_mismatch_count")
    fresh_lines = as_list(git_status.get("short_lines"))
    if embedded_dirty_count and not fresh_lines:
        notes.append(
            {
                "code": "STALE_EMBEDDED_LEDGER_STATE_SUPERSEDED_FOR_WORKTREE_CLEANLINESS_ONLY",
                "claim_label": "Verified",
                "source": "run_status.summary.dirty_worktree_entry_count",
                "embedded_value": embedded_dirty_count,
                "fresh_git_status_short_count": len(fresh_lines),
                "interpretation": (
                    "Fresh git status is clean, so the embedded dirty count is historical only."
                ),
                "required_refresh": (
                    "Rerun upstream report-only inventory before using old hashes for "
                    "stale-sensitive model-trust claims."
                ),
            }
        )
    if embedded_mismatch_count:
        notes.append(
            {
                "code": "STALE_EMBEDDED_LEDGER_STATE_SUPERSEDED_FOR_WORKTREE_CLEANLINESS_ONLY",
                "claim_label": "Not established",
                "source": "run_status.summary.stale_or_unknown_source_hash_mismatch_count",
                "embedded_value": embedded_mismatch_count,
                "fresh_git_status_short_count": len(fresh_lines),
                "interpretation": (
                    "The old source-hash mismatch note is preserved but not upgraded to current."
                ),
                "required_refresh": "Rerun the upstream report-only source-hash ledger if needed.",
            }
        )
    return notes


def build_lifecycle_stages() -> list[dict[str, Any]]:
    return [
        {
            "stage": stage,
            "classification": classification,
            "claim_label": claim_label,
            "accepted_evidence": list(accepted_evidence),
            "missing_evidence": list(missing_evidence),
            "blocked_actions": list(blocked_actions),
            "interpretation": interpretation,
        }
        for (
            stage,
            classification,
            claim_label,
            accepted_evidence,
            missing_evidence,
            blocked_actions,
            interpretation,
        ) in LIFECYCLE_DEFAULTS
    ]


def readiness_scores(
    *,
    payloads: Mapping[str, Mapping[str, Any]],
    source_surface: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    criteria: list[str] = []
    total = 0
    if all(payloads.get(name) for name in ("run_status", "overview", "closeout")):
        total += 5
        criteria.append("core_reports_present_and_parse")

    upstream_payloads = [
        payload
        for name, payload in payloads.items()
        if name.endswith("_reconciliation_json") or name in {"overview", "closeout"}
    ]
    if upstream_payloads and all(non_approval_all_false(payload) for payload in upstream_payloads):
        total += 5
        criteria.append("non_approval_flags_preserve_no_forbidden_execution")

    run_status = payloads.get("run_status", {})
    phase3 = run_status_row(run_status, "Phase 3")
    phase4 = run_status_row(run_status, "Phase 4")
    if (
        phase3.get("run_status") == "RUN"
        and phase3.get("evidence_state") == "limited-scope"
        and phase4.get("run_status") == "RUN"
        and phase4.get("evidence_state") == "limited-scope"
    ):
        total += 5
        criteria.append("phase3_phase4_limited_scope_only")

    if source_surface.get("builder_count", 0) > 0 and source_surface.get("test_count", 0) > 0:
        total += 5
        criteria.append("master_audit_builder_and_test_surfaces_exist")

    gap_payload = payloads.get("gap_remediation", {})
    for area in ("data_integrity", "statistical_validity", "operational_resilience"):
        if gap_area_score_eligible(gap_payload, area):
            total += 5
            criteria.append(f"{area}_gap_remediation_pass")

    component_scores = {
        "platform_integrity": 5 if "core_reports_present_and_parse" in criteria else 0,
        "data_integrity": (
            5 if "data_integrity_gap_remediation_pass" in criteria else 0
        ),
        "leakage_control": 5 if "phase3_phase4_limited_scope_only" in criteria else 0,
        "statistical_validity": (
            5 if "statistical_validity_gap_remediation_pass" in criteria else 0
        ),
        "governance": 5 if "non_approval_flags_preserve_no_forbidden_execution" in criteria else 0,
        "research_automation": (
            5 if "master_audit_builder_and_test_surfaces_exist" in criteria else 0
        ),
        "operational_resilience": (
            5 if "operational_resilience_gap_remediation_pass" in criteria else 0
        ),
        "total": total,
    }
    return component_scores, criteria


def build_research_readiness(
    *,
    payloads: Mapping[str, Mapping[str, Any]],
    source_surface: Mapping[str, Any],
) -> dict[str, Any]:
    scores, criteria = readiness_scores(payloads=payloads, source_surface=source_surface)
    run_status = payloads.get("run_status", {})
    return {
        "score_interpretation": "Not Ready",
        "scores": scores,
        "score_criteria_met": criteria,
        "claim_labels": {
            "overall": "Verified" if scores["total"] == 20 else "Not established",
            "production_paper_live": "Not established",
            "promotion_freeze_holdout": "Not established",
        },
        "phase_gaps": [
            {
                "audit_area": area,
                "run_status": run_status_row(run_status, area).get("run_status", "MISSING"),
                "evidence_state": run_status_row(run_status, area).get(
                    "evidence_state", "missing"
                ),
                "claim_label": "Not established",
            }
            for area in ("Overview", "Phase 1A", "Phase 1B", "Phase 2", "Phase 6", "Phase 7")
        ],
        "blocked_readiness_categories": {
            "production": "N/A - not approved / not in scope",
            "paper_live": "N/A - not approved / not in scope",
            "promotion": "N/A - not approved / not in scope",
            "artifact_freeze": "N/A - not approved / not in scope",
            "final_holdout": "N/A - not approved / not in scope",
            "provider_network": "N/A - not approved / not in scope",
            "trading_readiness": "N/A - not approved / not in scope",
        },
        "gap_remediation": gap_remediation_summary(payloads.get("gap_remediation")),
    }


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


def build_checks(
    *,
    paths: Mapping[str, Path],
    payloads: Mapping[str, Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    output_rel: str,
    source_surface: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
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
        failure=f"missing required Research Factory/Readiness inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )

    protected_roots = ("data/", "configs/", "models/", "predictions/")
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel != "." and not output_rel.startswith(protected_roots),
        failure=f"invalid report output root for Research Factory/Readiness: {output_rel}",
        details={"reports_root": output_rel},
    )

    check(
        checks,
        failures,
        name="core_reports_parse",
        passed=all(payloads.get(name) for name in ("run_status", "overview", "closeout")),
        failure="run-status, overview, or closeout JSON did not parse",
        evidence=[
            paths["run_status"].as_posix(),
            paths["overview"].as_posix(),
            paths["closeout"].as_posix(),
        ],
    )

    upstream_payloads = [
        payload
        for name, payload in payloads.items()
        if name.endswith("_reconciliation_json") or name in {"overview", "closeout"}
    ]
    check(
        checks,
        failures,
        name="non_approval_flags_preserve_no_forbidden_execution",
        passed=bool(upstream_payloads)
        and all(non_approval_all_false(payload) for payload in upstream_payloads),
        failure="upstream report non_approval flags do not preserve no-forbidden-execution",
    )

    run_status = payloads.get("run_status", {})
    expected_rows = {
        "Research Factory": ("NOT_RUN", "NOT_RUN_NO_RESEARCH_FACTORY_EXECUTION_PERMISSION"),
        "Research Readiness": ("NOT_RUN", "NOT_RUN_RESEARCH_READINESS_REVIEW_NOT_EXECUTED"),
        "Production / Paper / Live": ("N/A", "N/A_NOT_APPROVED_NOT_IN_SCOPE"),
        "Phase 10": ("N/A", "N/A_NOT_APPROVED_ARTIFACT_FREEZE"),
        "Phase 11": ("N/A", "N/A_NOT_APPROVED_FINAL_HOLDOUT"),
    }
    row_details = {}
    for area, expected in expected_rows.items():
        row = run_status_row(run_status, area)
        row_details[area] = {
            "actual": [row.get("run_status"), row.get("detail_status")],
            "expected": list(expected),
        }
    check(
        checks,
        failures,
        name="readiness_ledger_rows_remain_not_run_or_na",
        passed=all(tuple(details["actual"]) == tuple(details["expected"]) for details in row_details.values()),
        failure="Research Factory/Readiness or non-approved ledger rows changed from NOT_RUN/N/A",
        details=row_details,
    )

    phase3 = run_status_row(run_status, "Phase 3")
    phase4 = run_status_row(run_status, "Phase 4")
    check(
        checks,
        failures,
        name="phase3_phase4_limited_scope_only",
        passed=phase3.get("evidence_state") == "limited-scope"
        and phase4.get("evidence_state") == "limited-scope",
        failure="Phase 3/4 are not accepted as limited-scope-only evidence",
        details={"phase3": phase3, "phase4": phase4},
    )

    check(
        checks,
        failures,
        name="source_surface_present",
        passed=source_surface.get("builder_count", 0) > 0 and source_surface.get("test_count", 0) > 0,
        failure="Master Audit builder/test source surface is missing",
        details=source_surface,
    )
    return checks, failures


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    run_status_path: Path = DEFAULT_RUN_STATUS,
    overview_path: Path = DEFAULT_OVERVIEW,
    closeout_path: Path = DEFAULT_CLOSEOUT,
    gap_remediation_path: Path = DEFAULT_GAP_REMEDIATION,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    git_status = current_git_status(repo_root=repo_root, git_status_lines=git_status_lines)
    status_lines = list(git_status["short_lines"])
    dirty_map = inventory.build_dirty_path_map(status_lines)
    input_paths = build_input_paths(
        run_status=run_status_path,
        overview=overview_path,
        closeout_path=closeout_path,
    )
    evidence = build_input_evidence(repo_root=repo_root, paths=input_paths, dirty_map=dirty_map)
    gap_evidence = inventory.evidence_file(
        repo_root=repo_root,
        relative_path=gap_remediation_path,
        json_fields={
            "status": "status",
            "data_integrity_status": "summary.gap_area_statuses.data_integrity",
            "statistical_validity_status": (
                "summary.gap_area_statuses.statistical_validity"
            ),
            "operational_resilience_status": (
                "summary.gap_area_statuses.operational_resilience"
            ),
        },
        dirty_map=dirty_map,
    )
    if gap_evidence.get("exists"):
        evidence.append(gap_evidence)
    payloads, load_failures = load_payloads(repo_root=repo_root, paths=input_paths)
    gap_payload, gap_error = load_optional_payload(
        repo_root=repo_root,
        path=gap_remediation_path,
    )
    if gap_payload is not None:
        payloads["gap_remediation"] = gap_payload
    if gap_error:
        load_failures.append(gap_error)
    source_surface = collect_source_surface(repo_root)
    output_rel = rel(reports_root, repo_root)
    checks, check_failures = build_checks(
        paths=input_paths,
        payloads=payloads,
        evidence=evidence,
        output_rel=output_rel,
        source_surface=source_surface,
    )
    failures = [*load_failures, *check_failures]
    scores, score_criteria = readiness_scores(payloads=payloads, source_surface=source_surface)
    stale_notes = stale_evidence_notes(
        run_status=payloads.get("run_status", {}),
        git_status=git_status,
    )
    report_status = PASS_STATUS if not failures else FAIL_STATUS
    return {
        "status": report_status,
        "stage": STAGE,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "operation": "master_audit_research_factory_readiness_evidence_map_only",
            "reports_root": output_rel,
            "phase_audit_scope": "none",
            "data_model_scope": "none",
            "allowed_inputs": [
                "coordination docs",
                "existing Master Audit JSON/MD reports",
                "Master Audit builder/test source filenames",
                "current git status --short",
                "optional Master Audit gap remediation evidence map",
            ],
        },
        "input_evidence": evidence,
        "checks": checks,
        "summary": {
            "failure_count": len(failures),
            "readiness_score": scores["total"],
            "readiness_interpretation": "Not Ready",
            "research_factory_ready": False,
            "research_readiness_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "artifact_freeze_ready": False,
            "final_holdout_ready": False,
            "paper_live_ready": False,
            "production_ready": False,
            "current_git_status_short_count": len(status_lines),
            "embedded_dirty_worktree_entry_count": dotted_get(
                payloads.get("run_status", {}), "summary.dirty_worktree_entry_count"
            ),
            "score_criteria_met": score_criteria,
        },
        "research_factory": {
            "maturity_level": "Level 1 - Pipeline Research",
            "factory_score": scores["total"],
            "score_interpretation": "Not Ready",
            "lifecycle_stages": build_lifecycle_stages(),
            "source_surface": source_surface,
        },
        "research_readiness": build_research_readiness(
            payloads=payloads,
            source_surface=source_surface,
        ),
        "stale_evidence": stale_notes,
        "non_approval": dict(NON_APPROVAL),
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "failures": failures,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Research Factory / Research Readiness Evidence Map",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Readiness score: `{summary['readiness_score']}/100`",
        f"- Readiness interpretation: `{summary['readiness_interpretation']}`",
        f"- Research Factory ready: `{summary['research_factory_ready']}`",
        f"- Research Readiness ready: `{summary['research_readiness_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        f"- Paper/live ready: `{summary['paper_live_ready']}`",
        f"- Production ready: `{summary['production_ready']}`",
        "",
        "## Research Factory Lifecycle",
        "",
        "| Stage | Classification | Claim | Interpretation |",
        "| --- | --- | --- | --- |",
    ]
    for row in report["research_factory"]["lifecycle_stages"]:
        lines.append(
            "| `{stage}` | {classification} | {claim_label} | {interpretation} |".format(
                stage=row["stage"],
                classification=row["classification"],
                claim_label=row["claim_label"],
                interpretation=row["interpretation"],
            )
        )
    lines.extend(
        [
            "",
            "## Research Readiness Scores",
            "",
            "| Area | Score |",
            "| --- | --- |",
        ]
    )
    for key, value in report["research_readiness"]["scores"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Stale Evidence", ""])
    stale = report.get("stale_evidence", [])
    if stale:
        for item in stale:
            lines.append(
                "- `{code}` source=`{source}` embedded=`{embedded}` fresh_git_status_short_count=`{fresh}`".format(
                    code=item.get("code"),
                    source=item.get("source"),
                    embedded=item.get("embedded_value"),
                    fresh=item.get("fresh_git_status_short_count"),
                )
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This evidence map did not run phase audits, data/model commands, WFA/modeling, prediction generation or materialization, Phase 8 refresh, provider/network calls, promotion, artifact freeze, final holdout, paper/live, production checks, cleanup, staging, commit, or push.",
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
    parser.add_argument("--run-status", default=DEFAULT_RUN_STATUS.as_posix())
    parser.add_argument("--overview", default=DEFAULT_OVERVIEW.as_posix())
    parser.add_argument("--closeout", default=DEFAULT_CLOSEOUT.as_posix())
    parser.add_argument("--gap-remediation", default=DEFAULT_GAP_REMEDIATION.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(
        repo_root=repo_root,
        reports_root=reports_root,
        run_status_path=Path(args.run_status),
        overview_path=Path(args.overview),
        closeout_path=Path(args.closeout),
        gap_remediation_path=Path(args.gap_remediation),
    )
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"readiness_score={report['summary']['readiness_score']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
