#!/usr/bin/env python3
"""Build the report-only Master Audit Overview.

This command consumes existing repo evidence only. It does not run phase audits,
data/model commands, WFA/modeling, predictions, Phase 8 refresh, provider calls,
promotion, freeze, holdout, paper/live, cleanup, staging, commit, or push.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_overview"
PASS_STATUS = "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_OVERVIEW_REPORT_ONLY"

DEFAULT_RUN_STATUS = Path(
    "reports/master_audit/master_audit_run_status_20260709/master_audit_run_status.json"
)
DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_overview_20260709")
REPORT_JSON = "master_audit_overview.json"
REPORT_MD = "master_audit_overview.md"

REQUIRED_INPUTS = (
    Path("MASTER_AUDIT.md"),
    Path("CODEX_HANDOFF.md"),
    Path("PROJECT_OUTLINE.md"),
    DEFAULT_RUN_STATUS,
)

OVERVIEW_SECTION_KEYS = (
    "A_executive_summary",
    "B_architecture_review",
    "C_missing_controls",
    "D_risk_assessment",
    "E_automation_assessment",
    "F_governance_assessment",
    "G_recommended_improvements",
    "H_readiness_score",
)

NON_APPROVAL = {
    "phase_audits_executed": False,
    "data_model_commands_executed": False,
    "wfa_modeling_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "freeze_executed": False,
    "holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "staging_commit_push_executed": False,
}


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def required_input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    run_status_path: Path,
) -> list[dict[str, Any]]:
    return [
        inventory.evidence_file(repo_root=repo_root, relative_path="MASTER_AUDIT.md", dirty_map=dirty_map),
        inventory.evidence_file(repo_root=repo_root, relative_path="CODEX_HANDOFF.md", dirty_map=dirty_map),
        inventory.evidence_file(repo_root=repo_root, relative_path="PROJECT_OUTLINE.md", dirty_map=dirty_map),
        inventory.evidence_file(repo_root=repo_root, relative_path=run_status_path, dirty_map=dirty_map),
    ]


def row_by_area(run_status: Mapping[str, Any], area: str) -> Mapping[str, Any] | None:
    rows = run_status.get("run_status_table", [])
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("audit_area") == area:
            return row
    return None


def evidence_paths(row: Mapping[str, Any] | None) -> list[str]:
    if not row:
        return []
    evidence = row.get("accepted_evidence", [])
    if not isinstance(evidence, list):
        return []
    return [
        str(item.get("path"))
        for item in evidence
        if isinstance(item, Mapping) and item.get("path")
    ]


def score_overview_coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [
        row
        for row in rows
        if row.get("audit_area") != "Master Audit Evidence Inventory / Run-Status"
        and row.get("run_status") != "N/A"
    ]
    score_units = 0.0
    scored_rows: list[dict[str, Any]] = []
    for row in eligible:
        value = 0.0
        if row.get("run_status") == "RUN" and row.get("evidence_state") == "current":
            value = 1.0
        elif row.get("run_status") == "RUN" and row.get("evidence_state") == "limited-scope":
            value = 0.5
        elif row.get("run_status") == "RUN":
            value = 0.25
        score_units += value
        scored_rows.append(
            {
                "audit_area": row.get("audit_area"),
                "run_status": row.get("run_status"),
                "evidence_state": row.get("evidence_state"),
                "score_units": value,
            }
        )
    denominator = len(eligible) or 1
    return {
        "score": round((score_units / denominator) * 100),
        "score_units": score_units,
        "eligible_area_count": len(eligible),
        "scored_rows": scored_rows,
        "method": (
            "Excludes N/A and inventory rows. RUN/current=1, RUN/limited-scope=0.5, "
            "other RUN=0.25, NOT_RUN=0."
        ),
    }


def finding(
    *,
    finding_id: str,
    severity: str,
    title: str,
    verified_facts: Sequence[str],
    inference: str,
    assumption: str,
    evidence_paths_: Sequence[str],
    what_could_be_wrong_or_stale: str,
    impact: str,
    remediation: str,
    retest_required: str,
) -> dict[str, Any]:
    return {
        "finding_id": finding_id,
        "severity": severity,
        "finding": title,
        "verified_facts": list(verified_facts),
        "inference": inference,
        "assumption": assumption,
        "evidence_paths": list(evidence_paths_),
        "what_could_be_wrong_or_stale": what_could_be_wrong_or_stale,
        "impact": impact,
        "remediation": remediation,
        "retest_required": retest_required,
    }


def build_findings(run_status: Mapping[str, Any], run_status_path: str) -> list[dict[str, Any]]:
    rows = run_status.get("run_status_table", [])
    rows = rows if isinstance(rows, list) else []
    phase5 = row_by_area(run_status, "Phase 5")
    phase8 = row_by_area(run_status, "Phase 8")
    phase9 = row_by_area(run_status, "Phase 9")
    phase6 = row_by_area(run_status, "Phase 6")
    phase7 = row_by_area(run_status, "Phase 7")
    production = row_by_area(run_status, "Production / Paper / Live")
    mismatches = run_status.get("stale_or_unknown_source_hash_mismatches", [])
    if not isinstance(mismatches, list):
        mismatches = []

    return [
        finding(
            finding_id="overview-001-current-line-closed",
            severity="Critical",
            title="Current Tier 1 line is closed for alpha/model-trust evidence.",
            verified_facts=[
                f"run-status current_line_classification={run_status.get('summary', {}).get('current_line_classification')}",
                "Phase 8 evidence reports promoted=false and model_promotion_allowed=false.",
                "Phase 9 closeout reports future_modeling_allowed=false and promotion_allowed=false.",
            ],
            inference="The current Tier 1 line should not advance to modeling, Phase 8 refresh, promotion, freeze, holdout, paper, or live work.",
            assumption="The run-status ledger correctly reflects accepted local evidence at the time it was generated.",
            evidence_paths_=[run_status_path, *evidence_paths(phase8), *evidence_paths(phase9)],
            what_could_be_wrong_or_stale="Dirty configs or later unrecorded artifacts could change source hashes, but that would require a separate evidence refresh.",
            impact="Blocks model-trust, promotion, artifact-freeze, holdout, paper, and live claims for the current line.",
            remediation="Select a separate bounded evidence-work item or a new predeclared hypothesis path; do not rescue-tune this line.",
            retest_required="A future run-status refresh plus the relevant bounded phase/evidence audit.",
        ),
        finding(
            finding_id="overview-002-split-research-only",
            severity="Critical",
            title="Current accepted split evidence is research-only, not independent holdout evidence.",
            verified_facts=[
                f"run-status current_split_classification={run_status.get('summary', {}).get('current_split_classification')}",
                "Phase 5 detail status is RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD.",
            ],
            inference="Metrics from the current split cannot support independent holdout or model-trust claims.",
            assumption="The accepted WFA split-contamination guard is complete for its limited purpose and should not be rerun without approval.",
            evidence_paths_=[run_status_path, *evidence_paths(phase5)],
            what_could_be_wrong_or_stale="A future hardened split could supersede this, but no hardened split generation is approved here.",
            impact="Blocks independent holdout, artifact-freeze, final-holdout, promotion, paper, and live claims.",
            remediation="Plan a separate hardened split-builder or validation/test/embargo hardening decision before any model-trust use.",
            retest_required="A bounded hardened split audit/report, then a new run-status inventory.",
        ),
        finding(
            finding_id="overview-003-phase6-phase7-master-audit-gaps",
            severity="High",
            title="Phase 6 and Phase 7 are not accepted as MASTER_AUDIT phase evidence.",
            verified_facts=[
                f"Phase 6 detail_status={phase6.get('detail_status') if phase6 else None}",
                f"Phase 7 detail_status={phase7.get('detail_status') if phase7 else None}",
            ],
            inference="Existing prediction and WFA artifacts may exist, but the overview cannot treat them as completed phase audits.",
            assumption="The next useful report-only phase audit should reconcile existing artifacts without rerunning WFA or predictions.",
            evidence_paths_=[run_status_path, *evidence_paths(phase6), *evidence_paths(phase7)],
            what_could_be_wrong_or_stale="There may be existing Phase 6/7 reports outside the run-status ledger that were not accepted.",
            impact="Blocks end-to-end lineage and reproducibility claims from training through prediction audit.",
            remediation="Run a separately approved report-only Phase 6 or Phase 7 evidence reconciliation audit.",
            retest_required="Targeted report-only tests and generated JSON/MD for the selected phase audit.",
        ),
        finding(
            finding_id="overview-004-upstream-master-audit-gaps",
            severity="High",
            title="Phase 1A, Phase 1B, and Phase 2 remain NOT_RUN in the Master Audit ledger.",
            verified_facts=[
                "Phase 1A, Phase 1B, and Phase 2 rows are NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE.",
            ],
            inference="Upstream provider/raw/causal lineage is not yet represented as Master Audit evidence, even if repo-local hardening exists.",
            assumption="Existing upstream reports should be inventoried before any broad rebuild or provider action.",
            evidence_paths_=[run_status_path],
            what_could_be_wrong_or_stale="Current upstream artifacts may be valid, but this overview did not scan data/raw/dbn/causal roots.",
            impact="Limits whole-platform reproducibility and lineage confidence.",
            remediation="Plan one bounded upstream evidence audit, starting with report-only Phase 1B or Phase 2 reconciliation.",
            retest_required="A targeted upstream phase audit report and refreshed run-status ledger.",
        ),
        finding(
            finding_id="overview-005-dirty-config-hash-caveats",
            severity="Medium",
            title="Dirty config source hashes make some existing evidence stale or unknown.",
            verified_facts=[
                f"stale_or_unknown_source_hash_mismatch_count={len(mismatches)}",
                "Known mismatched paths include configs/models.yaml and configs/alpha_tiered.yaml when present in the run-status ledger.",
            ],
            inference="Config-dependent evidence should not be upgraded to current model-trust evidence without reconciliation.",
            assumption="The dirty worktree reflects user or other-session work and should be preserved.",
            evidence_paths_=[run_status_path],
            what_could_be_wrong_or_stale="If the config edits are intentional and already validated elsewhere, this overview still needs refreshed source hashes to accept them as current.",
            impact="Blocks stale-sensitive model-trust and reproducibility claims.",
            remediation="Do a separate config/source-hash reconciliation or rerun the affected report-only evidence matrix after approval.",
            retest_required="Run-status refresh and targeted config-dependent evidence tests.",
        ),
        finding(
            finding_id="overview-006-production-paper-live-na",
            severity="Critical",
            title="Production, paper, live, freeze, and holdout scopes are not approved.",
            verified_facts=[
                f"Production row detail_status={production.get('detail_status') if production else None}",
                "Phase 10 and Phase 11 rows are N/A_NOT_APPROVED.",
            ],
            inference="No trading-readiness language or external execution recommendation is warranted.",
            assumption="PROJECT_OUTLINE.md Production Deferral Gate remains authoritative.",
            evidence_paths_=[run_status_path, "PROJECT_OUTLINE.md"],
            what_could_be_wrong_or_stale="A future explicit approval could create these gates, but this run has no such approval.",
            impact="Blocks promotion, freeze, holdout, paper, live, broker, and production-readiness claims.",
            remediation="Leave these scopes N/A until a separate approved runbook, validation suite, and evidence manifest exist.",
            retest_required="Separate production/paper/live gate evidence, not this overview.",
        ),
    ]


def lifecycle_diagrams() -> dict[str, str]:
    return {
        "research_lifecycle": (
            "Phase 1A provider acquisition -> Phase 1B raw conversion -> Phase 2 causal/session "
            "normalization -> Phase 3 labels -> Phase 4 features -> Phase 5 WFA split planning -> "
            "Phase 6 WFA/predictions -> Phase 7 prediction audit -> Phase 8 evaluation/promotion gate -> "
            "Phase 9 diagnostics/research harnesses -> Phase 10 freeze -> Phase 11 holdout -> Production deferred"
        ),
        "data_lifecycle": (
            "DBN/ZST source archives -> raw parquet -> causally gated normalized parquet -> labeled parquet -> "
            "feature matrices -> split plans -> WFA reports/prediction manifests -> Phase 8/9 reports"
        ),
        "artifact_lineage": (
            "run-status ledger -> accepted report JSON/MD + hashes -> scoped findings; handoff and MASTER_AUDIT "
            "are coordination/prompt inputs, not proof by themselves"
        ),
    }


def build_overview_sections(
    *,
    run_status: Mapping[str, Any],
    run_status_path: str,
) -> dict[str, Any]:
    rows = run_status.get("run_status_table", [])
    rows = rows if isinstance(rows, list) else []
    findings = build_findings(run_status, run_status_path)
    coverage_score = score_overview_coverage([row for row in rows if isinstance(row, Mapping)])
    run_counts = run_status.get("summary", {}).get("run_status_counts", {})
    evidence_counts = run_status.get("summary", {}).get("evidence_state_counts", {})
    stale_count = run_status.get("summary", {}).get("stale_or_unknown_source_hash_mismatch_count")
    missing_rows = [
        {
            "audit_area": row.get("audit_area"),
            "detail_status": row.get("detail_status"),
            "scope": row.get("scope"),
        }
        for row in rows
        if isinstance(row, Mapping) and row.get("run_status") == "NOT_RUN"
    ]
    na_rows = [
        {
            "audit_area": row.get("audit_area"),
            "detail_status": row.get("detail_status"),
            "scope": row.get("scope"),
        }
        for row in rows
        if isinstance(row, Mapping) and row.get("run_status") == "N/A"
    ]
    return {
        "A_executive_summary": {
            "verdict": "BLOCKED_FOR_MODEL_TRUST_AND_TRADING_USE",
            "verified_facts": [
                f"run_status_counts={run_counts}",
                f"evidence_state_counts={evidence_counts}",
                f"stale_or_unknown_source_hash_mismatch_count={stale_count}",
                "Current Tier 1 line is closed for alpha evidence.",
                "Current split is same-fold rolling-retraining research evidence only.",
            ],
            "inference": (
                "The repo has useful limited-scope research-process evidence, but not enough accepted "
                "Master Audit coverage for model-trust, promotion, holdout, paper, or live claims."
            ),
        },
        "B_architecture_review": {
            "diagrams": lifecycle_diagrams(),
            "phase_status_summary": [
                {
                    "audit_area": row.get("audit_area"),
                    "run_status": row.get("run_status"),
                    "detail_status": row.get("detail_status"),
                    "evidence_state": row.get("evidence_state"),
                    "scope": row.get("scope"),
                }
                for row in rows
                if isinstance(row, Mapping)
            ],
        },
        "C_missing_controls": {
            "not_run_rows": missing_rows,
            "not_approved_rows": na_rows,
            "stale_or_unknown_source_hash_mismatches": run_status.get(
                "stale_or_unknown_source_hash_mismatches", []
            ),
            "missing_control_summary": [
                "Overview tab was NOT_RUN before this report.",
                "Phase 1A/1B/2 upstream Master Audit evidence is not accepted yet.",
                "Phase 6/7 Master Audit evidence is not accepted yet.",
                "Freeze, holdout, paper, live, and production scopes are N/A.",
            ],
        },
        "D_risk_assessment": {
            "findings": findings,
            "largest_risks": [
                "Current line has no accepted alpha/model-trust evidence.",
                "Current split cannot support independent holdout claims.",
                "Upstream and prediction-lineage phase audits are incomplete.",
                "Dirty config hashes create stale/unknown evidence caveats.",
                "Production/paper/live controls are absent and explicitly not approved.",
            ],
        },
        "E_automation_assessment": {
            "existing_automation": [
                "Run-status inventory builder exists and preserves NOT_RUN/N/A/limited-scope labels.",
                "Report-only target timing, feature leakage, split-contamination, alpha-gap, and closeout evidence exists.",
                "Coordination-doc checker exists and passed in prior run.",
            ],
            "automation_gaps": [
                "No accepted overview audit existed before this command.",
                "No direct Phase 1A/1B/2 Master Audit reconciliation report is accepted.",
                "No direct Phase 6/7 Master Audit reconciliation report is accepted.",
                "No approved production/paper/live validation suite exists.",
            ],
        },
        "F_governance_assessment": {
            "source_of_truth": [
                "PROJECT_OUTLINE.md is workflow authority.",
                "AGENTS.md is durable repo guidance.",
                "CODEX_HANDOFF.md is mutable state and must be reconciled against evidence.",
                "MASTER_AUDIT.md is a prompt library, not proof or execution authorization.",
            ],
            "governance_risks": [
                "Dirty worktree requires preserving user/other-session changes.",
                "Generated reports must not be treated as current if source hashes mismatch.",
                "N/A production/freeze/holdout scopes must stay blocked until explicitly approved.",
            ],
        },
        "G_recommended_improvements": [
            {
                "rank": 1,
                "recommendation": "Plan a report-only Phase 6 or Phase 7 Master Audit reconciliation next.",
                "reason": "These are NOT_RUN but existing artifacts likely allow a bounded evidence reconciliation without WFA/modeling.",
            },
            {
                "rank": 2,
                "recommendation": "Plan one upstream report-only audit for Phase 1B or Phase 2.",
                "reason": "Upstream lineage is a major platform blind spot in the Master Audit ledger.",
            },
            {
                "rank": 3,
                "recommendation": "Reconcile dirty config hashes before relying on config-dependent evidence.",
                "reason": "Current run-status reports stale/unknown source-hash mismatches for config inputs.",
            },
            {
                "rank": 4,
                "recommendation": "Leave Phase 10, Phase 11, and paper/live N/A.",
                "reason": "Current evidence does not authorize promotion, freeze, holdout, paper, or live work.",
            },
        ],
        "H_readiness_score": {
            "overview_audit_coverage_score": coverage_score,
            "model_trust_readiness_score": {
                "score": 0,
                "scale": "0-100",
                "reason": "Current Tier 1 line is closed for alpha evidence and promotion_allowed=false.",
            },
            "paper_live_readiness_score": {
                "score": 0,
                "scale": "0-100",
                "reason": "Production/paper/live is N/A_NOT_APPROVED_NOT_IN_SCOPE.",
            },
        },
    }


def validate_run_status(run_status: Mapping[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if run_status is None:
        return ["run-status JSON is missing or unreadable"]
    if run_status.get("status") != "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY":
        failures.append(f"unexpected run-status status: {run_status.get('status')}")
    rows = run_status.get("run_status_table")
    if not isinstance(rows, list) or not rows:
        failures.append("run-status table is missing or empty")
    summary = run_status.get("summary")
    if not isinstance(summary, Mapping):
        failures.append("run-status summary is missing")
    else:
        for key in (
            "phase_audits_executed",
            "data_model_commands_executed",
            "wfa_modeling_executed",
            "predictions_executed",
            "provider_network_calls_executed",
        ):
            if summary.get(key) is not False:
                failures.append(f"run-status summary {key} must be false")
    return failures


def build_report(
    *,
    repo_root: Path,
    run_status_path: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = reports_root.resolve()
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

    run_status_payload, run_status_error = read_json_object(run_status_path)
    failures = validate_run_status(run_status_payload)
    if run_status_error:
        failures.append(run_status_error)

    input_evidence = required_input_evidence(
        repo_root=repo_root,
        dirty_map=dirty_map,
        run_status_path=run_status_path,
    )
    for evidence in input_evidence:
        if not evidence.get("exists") or evidence.get("read_error"):
            failures.append(f"required input unavailable: {evidence.get('path')}")

    output_rel = rel(reports_root, repo_root)
    if output_rel == "." or output_rel.startswith(("data/", "configs/", "scripts/", "models/", "predictions/")):
        failures.append(f"invalid report output root for overview report: {output_rel}")

    sections = (
        build_overview_sections(
            run_status=run_status_payload or {},
            run_status_path=rel(run_status_path, repo_root),
        )
        if run_status_payload is not None
        else {key: {} for key in OVERVIEW_SECTION_KEYS}
    )
    missing_sections = [key for key in OVERVIEW_SECTION_KEYS if key not in sections]
    if missing_sections:
        failures.append(f"overview sections missing: {missing_sections}")

    status = PASS_STATUS if not failures else FAIL_STATUS
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_overview_report_only",
            "reports_root": output_rel,
            "run_status_path": rel(run_status_path, repo_root),
            "evidence_mode": "existing_repo_evidence_only",
            "phase_audit_scope": "none",
            "data_model_command_scope": "none",
        },
        "summary": {
            "failure_count": len(failures),
            "overview_sections_present": sorted(sections.keys()),
            "run_status_counts": inventory.dotted_get(run_status_payload, "summary.run_status_counts"),
            "evidence_state_counts": inventory.dotted_get(run_status_payload, "summary.evidence_state_counts"),
            "current_line_classification": inventory.dotted_get(
                run_status_payload, "summary.current_line_classification"
            ),
            "current_split_classification": inventory.dotted_get(
                run_status_payload, "summary.current_split_classification"
            ),
            "phase_audits_executed": False,
            "data_model_commands_executed": False,
            "wfa_modeling_executed": False,
            "predictions_executed": False,
            "phase8_refresh_executed": False,
            "provider_network_calls_executed": False,
            "promotion_or_freeze_or_holdout_executed": False,
            "paper_or_live_executed": False,
            "cleanup_or_git_publication_executed": False,
        },
        "input_evidence": input_evidence,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "overview_sections": sections,
        "non_approval": dict(NON_APPROVAL),
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan a report-only Phase 6 or Phase 7 Master Audit reconciliation, or choose an upstream "
            "Phase 1B/2 audit, before running any phase/data/model command."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    sections = report.get("overview_sections", {})
    summary = report.get("summary", {})
    lines = [
        "# Master Audit Overview",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Current line: `{summary.get('current_line_classification')}`",
        f"- Current split: `{summary.get('current_split_classification')}`",
        f"- Phase audits executed: `{summary.get('phase_audits_executed')}`",
        f"- Data/model commands executed: `{summary.get('data_model_commands_executed')}`",
        "",
    ]
    ordered_titles = {
        "A_executive_summary": "A. Executive Summary",
        "B_architecture_review": "B. Architecture Review",
        "C_missing_controls": "C. Missing Controls",
        "D_risk_assessment": "D. Risk Assessment",
        "E_automation_assessment": "E. Automation Assessment",
        "F_governance_assessment": "F. Governance Assessment",
        "G_recommended_improvements": "G. Recommended Improvements",
        "H_readiness_score": "H. Readiness Score",
    }
    for key, title in ordered_titles.items():
        lines.extend([f"## {title}", ""])
        value = sections.get(key, {})
        if key == "D_risk_assessment":
            for finding_item in value.get("findings", []):
                lines.append(
                    f"- `{finding_item['severity']}` `{finding_item['finding_id']}`: "
                    f"{finding_item['finding']}"
                )
        elif key == "G_recommended_improvements":
            for item in value:
                lines.append(f"- {item['rank']}. {item['recommendation']} Reason: {item['reason']}")
        elif key == "H_readiness_score":
            coverage = value.get("overview_audit_coverage_score", {})
            lines.append(f"- Overview audit coverage score: `{coverage.get('score')}/100`")
            lines.append(
                "- Model-trust readiness score: "
                f"`{value.get('model_trust_readiness_score', {}).get('score')}/100`"
            )
            lines.append(
                "- Paper/live readiness score: "
                f"`{value.get('paper_live_readiness_score', {}).get('score')}/100`"
            )
        else:
            rendered = json.dumps(value, indent=2, sort_keys=True)
            lines.append("```json")
            lines.append(rendered)
            lines.append("```")
        lines.append("")
    lines.extend(["## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This overview did not run phase audits, rebuild data, rebuild labels/features, run WFA/modeling, write predictions, refresh Phase 8, call providers/network, approve promotion, freeze artifacts, touch holdout, paper trade, live trade, clean up files, stage, commit, or push.",
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
    parser.add_argument("--run-status", default=DEFAULT_RUN_STATUS.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    run_status_path = resolve_path(repo_root, args.run_status)
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(
        repo_root=repo_root,
        run_status_path=run_status_path,
        reports_root=reports_root,
    )
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
