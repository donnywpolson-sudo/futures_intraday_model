#!/usr/bin/env python3
"""Build the Master Audit evidence inventory and run-status ledger.

This command is report-only. It inventories existing repo evidence and does not
execute any phase audit, data build, model run, WFA, prediction, promotion,
freeze, holdout, cleanup, staging, commit, push, provider, paper, or live action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_run_status"
PASS_STATUS = "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_RUN_STATUS_INVENTORY"

DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_run_status_20260709")
REPORT_JSON = "master_audit_run_status.json"
REPORT_MD = "master_audit_run_status.md"

EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)

REQUIRED_COORDINATION_FILES = (
    Path("MASTER_AUDIT.md"),
    Path("CODEX_HANDOFF.md"),
    Path("PROJECT_OUTLINE.md"),
)

EVIDENCE_PATHS = {
    "target_timing": Path(
        "reports/model_trust_audit/target_timing_v2_tier1_core_20260709/"
        "target_timing_audit.json"
    ),
    "feature_leakage": Path(
        "reports/model_trust_audit/final_feature_matrix_leakage_20260709/"
        "final_feature_matrix_leakage_audit.json"
    ),
    "wfa_split_contamination": Path(
        "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_contamination_audit/"
        "wfa_split_contamination_audit.json"
    ),
    "split_plan": Path("reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.json"),
    "feature_manifest": Path(
        "reports/features_baseline/"
        "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
        "baseline_feature_manifest.json"
    ),
    "phase8_decision": Path(
        "reports/phase8/tier1_core_phase6_full_predictions_20260706/"
        "alpha_promotion_decision.json"
    ),
    "statistical_validity": Path(
        "reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/"
        "statistical_validity_summary.json"
    ),
    "failure_analysis": Path(
        "reports/failure_analysis/tier1_core_phase6_full_predictions_20260706/"
        "failure_analysis_summary.json"
    ),
    "alpha_gap_matrix": Path(
        "reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/"
        "alpha_evidence_gap_matrix.json"
    ),
    "alpha_completion_closeout": Path(
        "reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/"
        "alpha_evidence_completion_closeout.json"
    ),
    "models_config": Path("configs/models.yaml"),
    "feature_cols": Path("data/feature_matrices/feature_cols.json"),
    "target_cols": Path("data/feature_matrices/target_cols.json"),
}

FORBIDDEN_ACTION_FLAGS = (
    "phase_audits_executed",
    "data_model_commands_executed",
    "wfa_modeling_executed",
    "predictions_executed",
    "phase8_refresh_executed",
    "provider_network_calls_executed",
    "promotion_executed",
    "freeze_executed",
    "holdout_executed",
    "paper_live_executed",
    "cleanup_executed",
    "staging_commit_push_executed",
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


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"missing: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"unreadable JSON {path.as_posix()}: {exc}"
    if not isinstance(payload, dict):
        return None, f"JSON is not an object: {path.as_posix()}"
    return payload, None


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    value: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def collect_git_status(repo_root: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:
        return {"status_lines": [], "error": str(exc), "returncode": None}
    return {
        "status_lines": [line for line in result.stdout.splitlines() if line.strip()],
        "error": result.stderr.strip() or None,
        "returncode": result.returncode,
    }


def build_dirty_path_map(status_lines: Sequence[str]) -> dict[str, str]:
    dirty: dict[str, str] = {}
    for line in status_lines:
        if len(line) < 4:
            continue
        marker = line[:2].strip() or line[:2]
        raw_path = line[3:].strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        dirty[raw_path.replace("\\", "/")] = marker
    return dirty


def path_dirty_marker(path: str, dirty_map: Mapping[str, str]) -> str | None:
    normalized = path.replace("\\", "/")
    return dirty_map.get(normalized)


def evidence_file(
    *,
    repo_root: Path,
    relative_path: str | Path,
    json_fields: Mapping[str, str] | None = None,
    dirty_map: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    path = resolve_path(repo_root, relative_path)
    path_rel = rel(path, repo_root)
    digest = sha256_file(path)
    payload: dict[str, Any] | None = None
    read_error: str | None = None
    extracted: dict[str, Any] = {}
    if path.suffix.lower() == ".json" and path.is_file():
        payload, read_error = read_json_object(path)
        if payload is not None and json_fields:
            extracted = {name: dotted_get(payload, source) for name, source in json_fields.items()}
    elif path.suffix.lower() == ".json" and not path.is_file():
        read_error = f"missing: {path_rel}"
    marker = path_dirty_marker(path_rel, dirty_map or {})
    state = "current"
    if digest is None:
        state = "missing"
    elif read_error:
        state = "unknown"
    elif marker:
        state = "unknown"
    return {
        "path": path_rel,
        "exists": digest is not None,
        "sha256": digest,
        "state": state,
        "git_status": marker,
        "read_error": read_error,
        "fields": extracted,
    }


def current_or_missing(evidence: Sequence[Mapping[str, Any]]) -> str:
    if not evidence:
        return "missing"
    if all(not item.get("exists") for item in evidence):
        return "missing"
    if any(item.get("read_error") for item in evidence):
        return "unknown"
    if any(item.get("git_status") for item in evidence):
        return "unknown"
    return "current"


def row(
    *,
    audit_area: str,
    run_status: str,
    evidence_state: str,
    accepted_evidence: Sequence[Mapping[str, Any]],
    scope: str,
    notes: Sequence[str],
    detail_status: str,
) -> dict[str, Any]:
    return {
        "audit_area": audit_area,
        "run_status": run_status,
        "detail_status": detail_status,
        "evidence_state": evidence_state,
        "accepted_evidence": list(accepted_evidence),
        "scope": scope,
        "notes": list(notes),
    }


def required_input_failures(repo_root: Path) -> list[str]:
    failures: list[str] = []
    for relative_path in REQUIRED_COORDINATION_FILES:
        path = resolve_path(repo_root, relative_path)
        if not path.is_file():
            failures.append(f"missing required coordination file: {relative_path.as_posix()}")
    return failures


def build_evidence_index(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    json_fields_by_key: dict[str, dict[str, str]] = {
        "target_timing": {
            "status": "status",
            "stage": "stage",
            "failure_count": "summary.failure_count",
            "warning_count": "summary.warning_count",
            "pair_count": "summary.pair_count",
            "row_count": "summary.row_count",
        },
        "feature_leakage": {
            "status": "status",
            "verdict": "verdict",
            "feature_cols_sha256": "source_evidence.feature_cols_sha256",
            "matrix_file_status_counts": "summary_counts.matrix_file_status_counts",
        },
        "wfa_split_contamination": {
            "status": "status",
            "classification": "summary.classification",
            "failure_count": "summary.failure_count",
            "warning_count": "summary.warning_count",
            "model_trust_ready": "summary.model_trust_ready",
            "valid_for_independent_holdout_claims": "summary.valid_for_independent_holdout_claims",
        },
        "split_plan": {
            "fold_count": "fold_count",
            "failure_count": "failure_count",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
        },
        "feature_manifest": {
            "status": "status",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
            "feature_count": "feature_count",
            "profile": "profile",
            "resolved_profile": "resolved_profile",
        },
        "phase8_decision": {
            "promoted": "promoted",
            "research_alpha_ready": "research_alpha_ready",
            "model_promotion_allowed": "model_promotion_allowed",
            "promotion_blocker_count": "promotion_gate.promotion_blocker_count",
        },
        "statistical_validity": {
            "status": "status",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "failure_analysis": {
            "status": "status",
            "failure_count": "failure_count",
            "warning_count": "warning_count",
        },
        "alpha_gap_matrix": {
            "status": "status",
            "verdict": "verdict",
            "alpha_evidence_ready": "alpha_evidence_ready",
            "blocker_count": "blockers",
            "bucket_status_counts": "bucket_status_counts",
        },
        "alpha_completion_closeout": {
            "status": "status",
            "verdict": "verdict",
            "future_modeling_allowed": "future_modeling_allowed",
            "promotion_allowed": "promotion_allowed",
            "modeling_pause_required": "modeling_pause_required",
            "terminal_fail_count": "terminal_fail_count",
            "missing_required_evidence_count": "missing_required_evidence_count",
        },
    }
    evidence: dict[str, dict[str, Any]] = {}
    for key, path in EVIDENCE_PATHS.items():
        evidence[key] = evidence_file(
            repo_root=repo_root,
            relative_path=path,
            json_fields=json_fields_by_key.get(key),
            dirty_map=dirty_map,
        )
    return evidence


def compact_evidence(*items: Mapping[str, Any]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for item in items:
        compacted.append(
            {
                "path": item.get("path"),
                "exists": item.get("exists"),
                "sha256": item.get("sha256"),
                "state": item.get("state"),
                "git_status": item.get("git_status"),
                "fields": item.get("fields", {}),
                "read_error": item.get("read_error"),
            }
        )
    return compacted


def load_json_payload(repo_root: Path, relative_path: str | Path) -> Mapping[str, Any] | None:
    payload, _ = read_json_object(resolve_path(repo_root, relative_path))
    return payload


def build_run_status_rows(
    *,
    repo_root: Path,
    evidence: Mapping[str, Mapping[str, Any]],
    dirty_map: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stale_or_unknown: list[dict[str, Any]] = []
    alpha_gap_payload = load_json_payload(repo_root, EVIDENCE_PATHS["alpha_gap_matrix"])
    closeout_payload = load_json_payload(repo_root, EVIDENCE_PATHS["alpha_completion_closeout"])
    alpha_source = dotted_get(alpha_gap_payload, "source_evidence")
    if isinstance(alpha_source, Mapping):
        for source_key, source in alpha_source.items():
            if not isinstance(source, Mapping):
                continue
            path_text = source.get("path")
            expected = source.get("sha256")
            if not isinstance(path_text, str) or not isinstance(expected, str):
                continue
            actual = sha256_file(resolve_path(repo_root, path_text))
            if actual is not None and actual != expected:
                stale_or_unknown.append(
                    {
                        "source": source_key,
                        "path": path_text,
                        "expected_sha256": expected,
                        "actual_sha256": actual,
                    }
                )
    closeout_source_matrix = dotted_get(closeout_payload, "source_matrix")
    if isinstance(closeout_source_matrix, Mapping):
        path_text = closeout_source_matrix.get("path")
        expected = closeout_source_matrix.get("sha256")
        if isinstance(path_text, str) and isinstance(expected, str):
            actual = sha256_file(resolve_path(repo_root, path_text))
            if actual is not None and actual != expected:
                stale_or_unknown.append(
                    {
                        "source": "alpha_completion_closeout.source_matrix",
                        "path": path_text,
                        "expected_sha256": expected,
                        "actual_sha256": actual,
                    }
                )

    phase3_evidence = compact_evidence(evidence["target_timing"])
    phase4_evidence = compact_evidence(evidence["feature_leakage"], evidence["feature_manifest"])
    phase5_evidence = compact_evidence(
        evidence["wfa_split_contamination"],
        evidence["split_plan"],
        evidence["feature_manifest"],
        evidence["models_config"],
    )
    phase8_evidence = compact_evidence(evidence["phase8_decision"])
    phase9_evidence = compact_evidence(
        evidence["statistical_validity"],
        evidence["failure_analysis"],
        evidence["alpha_gap_matrix"],
        evidence["alpha_completion_closeout"],
    )

    return [
        row(
            audit_area="Master Audit Evidence Inventory / Run-Status",
            run_status="RUN",
            detail_status="RUN_REPORT_ONLY_CURRENT_COMMAND",
            evidence_state="current",
            accepted_evidence=[],
            scope="repo coordination files and existing reports only",
            notes=[
                "This is the only audit command executed by this implementation.",
                "It creates a ledger before selecting any MASTER_AUDIT phase tab.",
            ],
        ),
        row(
            audit_area="Overview",
            run_status="NOT_RUN",
            detail_status="NOT_RUN_MASTER_AUDIT_TAB",
            evidence_state="missing",
            accepted_evidence=[],
            scope="no overview audit scope executed",
            notes=[
                "MASTER_AUDIT.md says imported tabs default to NOT_RUN until a bounded audit produces evidence.",
                "No direct overview audit artifact was accepted by this inventory.",
            ],
        ),
        row(
            audit_area="Phase 1A",
            run_status="NOT_RUN",
            detail_status="NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
            evidence_state="unknown",
            accepted_evidence=[],
            scope="provider/source acquisition audit not executed here",
            notes=["Existing data/provider artifacts were not scanned; provider/network calls are forbidden."],
        ),
        row(
            audit_area="Phase 1B",
            run_status="NOT_RUN",
            detail_status="NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
            evidence_state="unknown",
            accepted_evidence=[],
            scope="raw-to-normalized audit not executed here",
            notes=["No bounded Phase 1B master audit artifact was accepted by this inventory."],
        ),
        row(
            audit_area="Phase 2",
            run_status="NOT_RUN",
            detail_status="NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
            evidence_state="unknown",
            accepted_evidence=[],
            scope="causal base/session normalization audit not executed here",
            notes=["No causal/session phase audit was run or accepted by this inventory."],
        ),
        row(
            audit_area="Phase 3",
            run_status="RUN",
            detail_status="RUN_LIMITED_SCOPE_TARGET_TIMING_EVIDENCE",
            evidence_state="limited-scope",
            accepted_evidence=phase3_evidence,
            scope="active v2 Tier 1 core labels/features, 6E/CL/ES/ZN, 2023/2024",
            notes=[
                "Existing target timing report is accepted only as limited-scope evidence.",
                "This inventory did not rebuild labels or reread parquet data.",
            ],
        ),
        row(
            audit_area="Phase 4",
            run_status="RUN",
            detail_status="RUN_LIMITED_SCOPE_FEATURE_LEAKAGE_EVIDENCE",
            evidence_state="limited-scope",
            accepted_evidence=phase4_evidence,
            scope="active v2 Tier 1 core feature matrix leakage, 6E/CL/ES/ZN, 2023/2024",
            notes=[
                "Existing feature leakage report is limited to the completed-bar convention and active v2 Tier 1 core.",
                "Warnings inside source evidence remain warnings, not promotion evidence.",
            ],
        ),
        row(
            audit_area="Phase 5",
            run_status="RUN",
            detail_status="RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD",
            evidence_state="limited-scope",
            accepted_evidence=phase5_evidence,
            scope="active v2 Tier 1 core split contamination guard, 48 folds",
            notes=[
                "Existing WFA split-contamination guard is accepted for the limited purpose already decided.",
                "Classification remains same-fold rolling-retraining research only, not independent holdout evidence.",
                "Do not patch or rerun this guard unless separately approved.",
            ],
        ),
        row(
            audit_area="Phase 6",
            run_status="NOT_RUN",
            detail_status="NOT_RUN_PHASE6_MASTER_AUDIT_NOT_ACCEPTED",
            evidence_state="unknown",
            accepted_evidence=phase8_evidence,
            scope="phase6 WFA/modeling audit not executed here",
            notes=[
                "Phase 8 evidence references a Phase 6 prediction run, but this inventory does not accept that as a Phase 6 audit.",
                "WFA/modeling and predictions are forbidden in this scope.",
            ],
        ),
        row(
            audit_area="Phase 7",
            run_status="NOT_RUN",
            detail_status="NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
            evidence_state="missing",
            accepted_evidence=[],
            scope="post-WFA diagnostics/model selection audit not executed here",
            notes=["No bounded Phase 7 master audit artifact was accepted by this inventory."],
        ),
        row(
            audit_area="Phase 8",
            run_status="RUN",
            detail_status="RUN_FAILING_ALPHA_PROMOTION_EVIDENCE",
            evidence_state="current",
            accepted_evidence=phase8_evidence,
            scope="tier1_core_phase6_full_predictions_20260706 report evidence only",
            notes=[
                "Existing Phase 8 decision says promoted=false and model_promotion_allowed=false.",
                "No Phase 8 refresh, promotion, freeze, or paper/live action is authorized.",
            ],
        ),
        row(
            audit_area="Phase 9",
            run_status="RUN",
            detail_status="RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT",
            evidence_state="limited-scope",
            accepted_evidence=phase9_evidence,
            scope="tier1_core_phase6_full_predictions_20260706 statistical/failure/gap evidence",
            notes=[
                "Existing alpha evidence closeout says the current line is closed for alpha evidence.",
                "Missing/failed baseline, null, statistical-validity, and execution-realism evidence remain blockers.",
            ],
        ),
        row(
            audit_area="Phase 10",
            run_status="N/A",
            detail_status="N/A_NOT_APPROVED_ARTIFACT_FREEZE",
            evidence_state="missing",
            accepted_evidence=[],
            scope="artifact freeze",
            notes=["Artifact freeze is blocked unless explicit freeze approval exists."],
        ),
        row(
            audit_area="Phase 11",
            run_status="N/A",
            detail_status="N/A_NOT_APPROVED_FINAL_HOLDOUT",
            evidence_state="missing",
            accepted_evidence=[],
            scope="final holdout/forward guard",
            notes=["Final holdout is blocked unless explicit holdout approval exists."],
        ),
        row(
            audit_area="Research Factory",
            run_status="NOT_RUN",
            detail_status="NOT_RUN_NO_RESEARCH_FACTORY_EXECUTION_PERMISSION",
            evidence_state="missing",
            accepted_evidence=[],
            scope="capability review only",
            notes=["Self-running research factory execution is not approved."],
        ),
        row(
            audit_area="Research Readiness",
            run_status="NOT_RUN",
            detail_status="NOT_RUN_RESEARCH_READINESS_REVIEW_NOT_EXECUTED",
            evidence_state="missing",
            accepted_evidence=[],
            scope="research-only unless separately approved",
            notes=["Research-readiness review was not executed by this inventory."],
        ),
        row(
            audit_area="Production / Paper / Live",
            run_status="N/A",
            detail_status="N/A_NOT_APPROVED_NOT_IN_SCOPE",
            evidence_state="missing",
            accepted_evidence=[],
            scope="production, paper, and live trading",
            notes=["Production, paper, and live trading are not approved and remain out of scope."],
        ),
    ], stale_or_unknown


def status_counts(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get(key)) for item in rows).items()))


def coordination_inputs(repo_root: Path, dirty_map: Mapping[str, str]) -> list[dict[str, Any]]:
    return [
        evidence_file(repo_root=repo_root, relative_path=path, dirty_map=dirty_map)
        for path in REQUIRED_COORDINATION_FILES
    ]


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if git_status_lines is None:
        git_status = collect_git_status(repo_root)
        status_lines = list(git_status["status_lines"])
        git_error = git_status["error"]
        git_returncode = git_status["returncode"]
    else:
        status_lines = list(git_status_lines)
        git_error = None
        git_returncode = 0

    dirty_map = build_dirty_path_map(status_lines)
    failures = required_input_failures(repo_root)
    evidence = build_evidence_index(repo_root=repo_root, dirty_map=dirty_map)
    rows, stale_or_unknown = build_run_status_rows(
        repo_root=repo_root,
        evidence=evidence,
        dirty_map=dirty_map,
    )
    inputs = coordination_inputs(repo_root, dirty_map)
    for item in inputs:
        if item.get("read_error"):
            failures.append(str(item["read_error"]))

    output_rel = rel(reports_root, repo_root)
    forbidden_output_roots = ("data/", "configs/", "scripts/", "models/", "predictions/")
    if output_rel == "." or output_rel.startswith(forbidden_output_roots):
        failures.append(f"invalid report output root for report-only audit: {output_rel}")

    report_status = PASS_STATUS if not failures else FAIL_STATUS
    forbidden_actions = {name: False for name in FORBIDDEN_ACTION_FLAGS}
    summary = {
        "row_count": len(rows),
        "run_status_counts": status_counts(rows, "run_status"),
        "detail_status_counts": status_counts(rows, "detail_status"),
        "evidence_state_counts": status_counts(rows, "evidence_state"),
        "stale_or_unknown_source_hash_mismatch_count": len(stale_or_unknown),
        "dirty_worktree_entry_count": len(status_lines),
        "failure_count": len(failures),
        "phase_audits_executed": False,
        "data_model_commands_executed": False,
        "wfa_modeling_executed": False,
        "predictions_executed": False,
        "promotion_or_freeze_or_holdout_executed": False,
        "paper_or_live_executed": False,
        "provider_network_calls_executed": False,
        "cleanup_or_git_publication_executed": False,
        "current_split_classification": "same_fold_rolling_retraining_research_only",
        "current_line_classification": "closed_no_alpha_evidence",
    }
    return {
        "stage": STAGE,
        "status": report_status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "operation": "master_audit_evidence_inventory_run_status_only",
            "reports_root": output_rel,
            "markets_where_applicable": list(EXPECTED_MARKETS),
            "years_where_applicable": list(EXPECTED_YEARS),
            "phase_audit_scope": "none",
        },
        "summary": summary,
        "coordination_inputs": inputs,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "run_status_table": rows,
        "stale_or_unknown_source_hash_mismatches": stale_or_unknown,
        "non_approval": forbidden_actions,
        "duplicates_prevented": [
            {
                "area": "Phase 5 WFA split-contamination guard",
                "decision": "accept_existing_limited_evidence_do_not_patch_or_rerun",
                "evidence_path": EVIDENCE_PATHS["wfa_split_contamination"].as_posix(),
            }
        ],
        "pass_fail_criteria": {
            "pass": [
                "required coordination files are readable",
                "run-status rows are generated without executing phase/data/model commands",
                "forbidden action flags remain false",
                "missing phase evidence is classified as NOT_RUN or N/A instead of blocking inventory generation",
            ],
            "fail": [
                "MASTER_AUDIT.md, CODEX_HANDOFF.md, or PROJECT_OUTLINE.md is missing/unreadable",
                "requested output root points at protected data/config/script/model/prediction locations",
            ],
        },
        "recommended_next_action": (
            "Choose exactly one NOT_RUN or limited-scope MASTER_AUDIT area for a separately bounded "
            "plan-only audit before any execution."
        ),
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Run-Status Inventory",
        "",
        f"- Status: `{report['status']}`",
        f"- Rows: `{summary['row_count']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Dirty worktree entries recorded: `{summary['dirty_worktree_entry_count']}`",
        f"- Stale/unknown source hash mismatches: `{summary['stale_or_unknown_source_hash_mismatch_count']}`",
        f"- Phase audits executed: `{summary['phase_audits_executed']}`",
        f"- Data/model commands executed: `{summary['data_model_commands_executed']}`",
        f"- WFA/modeling executed: `{summary['wfa_modeling_executed']}`",
        f"- Predictions executed: `{summary['predictions_executed']}`",
        f"- Current split classification: `{summary['current_split_classification']}`",
        f"- Current line classification: `{summary['current_line_classification']}`",
        "",
        "## Run-Status Table",
        "",
        "| Audit Area | Run Status | Detail | Evidence State | Scope | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["run_status_table"]:
        notes = "<br>".join(str(note) for note in item.get("notes", []))
        lines.append(
            "| {area} | `{status}` | `{detail}` | `{state}` | {scope} | {notes} |".format(
                area=item["audit_area"],
                status=item["run_status"],
                detail=item["detail_status"],
                state=item["evidence_state"],
                scope=item["scope"],
                notes=notes,
            )
        )
    lines.extend(["", "## Evidence Files", ""])
    for item in report["run_status_table"]:
        evidence_items = item.get("accepted_evidence", [])
        if not evidence_items:
            continue
        lines.append(f"### {item['audit_area']}")
        for evidence in evidence_items:
            lines.append(
                "- `{path}` exists=`{exists}` state=`{state}` git=`{git}` sha256=`{sha}`".format(
                    path=evidence.get("path"),
                    exists=evidence.get("exists"),
                    state=evidence.get("state"),
                    git=evidence.get("git_status"),
                    sha=evidence.get("sha256"),
                )
            )
    mismatches = report.get("stale_or_unknown_source_hash_mismatches", [])
    lines.extend(["", "## Stale Or Unknown Source Hash Mismatches", ""])
    if mismatches:
        for mismatch in mismatches:
            lines.append(f"- `{mismatch.get('path')}` source=`{mismatch.get('source')}`")
    else:
        lines.append("- None detected by this small-file hash inventory.")
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This inventory did not run phase audits, rebuild data, rebuild labels/features, run WFA/modeling, write predictions, refresh Phase 8, call providers/network, approve promotion, freeze artifacts, touch holdout, paper trade, live trade, clean up files, stage, commit, or push.",
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
        f"rows={report['summary']['row_count']} json={rel(json_path, repo_root)} "
        f"md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
