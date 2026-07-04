#!/usr/bin/env python3
"""Build a console-only ES 2026 P1 repair plan."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.phase1_raw_contract import SUPPORTED_SCHEMAS
from scripts.phase2_causal_base import build_causal_base_data as phase2_causal_base
from scripts.validation import build_local_trade_es2026_p1_repair_proposal as proposal_gate


STAGE = "local_trade_es2026_p1_repair_plan"
STATUS_READY = "REVIEW_READY_ES2026_P1_REPAIR_PLAN"
STATUS_NO_GO = "NO_GO_ES2026_P1_REPAIR_PLAN"
DECISION_PLAN_ONLY = "es2026_p1_repair_plan_only_no_execution"
DECISION_BLOCKED = "es2026_p1_repair_plan_blocked"
PLAN_STATUS_APPROVAL_REQUIRED = "APPROVAL_REQUIRED_NOT_EXECUTED"

TARGET_MARKET = proposal_gate.TARGET_MARKET
TARGET_YEAR = proposal_gate.TARGET_YEAR
TARGET_START = "2026-01-01"
TARGET_END = "2026-06-13"

DEFAULT_WORK_ORDER_REPORT = proposal_gate.DEFAULT_WORK_ORDER_REPORT
DEFAULT_DRILLDOWN_REPORT = proposal_gate.DEFAULT_DRILLDOWN_REPORT
DEFAULT_CHECKPOINT_JSONL = proposal_gate.DEFAULT_REPORTS_ROOT / "phase2_readiness.progress.jsonl"
DEFAULT_REPAIR_REPORTS_ROOT = Path(
    "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2"
)
DEFAULT_CANDIDATE_RAW_ROOT = Path("data/raw_es2026_p1_repair_candidate")
DEFAULT_OUTPUT_ROOT = Path("data/causally_gated_normalized/local_trade_es2026_p1_candidate")
DEFAULT_PROFILE = "tier_3_forward"
DEFAULT_RAW_ALIGNMENT_REPORT = (
    DEFAULT_REPAIR_REPORTS_ROOT / "ES_2026_candidate_raw_dbn_alignment.json"
)

REQUIRED_PHASE1_SCHEMAS = ("ohlcv-1m", "status", "statistics")
REQUIRED_PHASE2_FLAGS = (
    "--readiness-only",
    "--market-year-include-list",
    "--readiness-json-out",
    "--readiness-md-out",
    "--readiness-checkpoint-jsonl",
    "--readiness-max-market-years",
    "--readiness-stop-after-blockers",
    "--readiness-progress",
)
REQUIRED_PROPOSAL_ACTIONS = (
    "repair_or_refresh_statistics_enrichment_evidence",
    "review_degraded_raw_quality_evidence",
    "keep_exclusion_diagnostic_only",
)

FALSE_APPROVAL_FLAGS = (
    "statistics_enrichment_repair_execution_approved",
    "raw_quality_repair_execution_approved",
    "candidate_raw_write_approved",
    "provider_download_approved",
    "readiness_rerun_approved",
    "accepted_warning_packet_approved",
    "exclusion_approved",
    "causal_base_repair_approved",
    "label_build_approved",
    "feature_matrix_build_approved",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "proof_scan_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "live_or_paper_execution_approved",
)

FORBIDDEN_PATTERNS = (
    "canonical_data_raw_overwrite_without_separate_approval",
    "provider_download_without_separate_approval",
    "accepted_warning_packet_without_separate_approval",
    "es2026_exclusion_without_separate_approval",
    "causal_base_parquet_writes",
    "labels_or_feature_matrices",
    "wfa_or_modeling",
    "metrics_or_predictions",
    "proof_scans",
    "live_or_paper_execution",
    "staging_commits_pushes",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return proposal_gate.rel(path, repo_root)


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


def _phase2_declared_flags() -> set[str]:
    parser = phase2_causal_base.build_arg_parser()
    flags: set[str] = set()
    for action in parser._actions:  # noqa: SLF001 - argparse exposes actions for introspection.
        flags.update(option for option in action.option_strings if option.startswith("--"))
    return flags


def _path_under(repo_root: Path, path: Path, root_name: str) -> bool:
    try:
        path.resolve().relative_to((repo_root / root_name).resolve())
    except ValueError:
        return False
    return True


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


def _expected_generated_under(repair_reports_root: Path, *parts: str) -> str:
    return (repair_reports_root.joinpath(*parts)).as_posix()


def _dry_run_plan_path(plan_out: Path) -> Path:
    return plan_out.with_name(f"{plan_out.stem}_dry_run{plan_out.suffix}")


def _phase1_dry_run_command(
    *,
    schema: str,
    repair_reports_root: Path,
) -> dict[str, Any]:
    schema_root = repair_reports_root / f"phase1a_{schema}"
    plan_out = schema_root / "databento_download_plan.json"
    dry_run_out = _dry_run_plan_path(plan_out)
    return {
        "name": f"dry_run_{schema}_archive_scope",
        "command_family": "phase1a_download_dry_run_only",
        "command": (
            "python -m scripts.phase1A_download.download_databento_raw "
            "--universe custom --symbols ES "
            f"--schema {schema} --start {TARGET_START} --end {TARGET_END} "
            "--dbn-root data/dbn --raw-root data/raw "
            f"--reports-root {schema_root.as_posix()} "
            "--chunk year --mode download-dbn --workers 1 --dry-run "
            f"--plan-out {plan_out.as_posix()}"
        ),
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "schemas": [schema],
            "network": False,
            "data_mutation": False,
        },
        "timeout_seconds": 180,
        "expected_generated_artifacts": [dry_run_out.as_posix()],
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
        "stop_condition": (
            "Stop if the plan includes any market other than ES, any year other than 2026, "
            "more than one task, provider/network execution, or staged generated artifacts."
        ),
        "approval_required_before_execution": True,
    }


def _candidate_convert_command(
    *,
    repair_reports_root: Path,
    candidate_raw_root: Path,
) -> dict[str, Any]:
    reports_root = repair_reports_root / "candidate_raw_conversion"
    return {
        "name": "candidate_raw_convert_with_required_optional_enrichment",
        "command_family": "phase1a_convert_existing_dbn_to_candidate_raw",
        "command": (
            "python -m scripts.phase1A_download.download_databento_raw "
            "--universe custom --symbols ES --schema ohlcv-1m "
            f"--start {TARGET_START} --end {TARGET_END} "
            "--dbn-root data/dbn/ohlcv_1m "
            f"--raw-root {candidate_raw_root.as_posix()} "
            f"--reports-root {reports_root.as_posix()} "
            "--chunk year --mode convert-parquet --workers 1 "
            "--include-optional-schemas status,statistics "
            "--optional-schema-policy require --optional-dbn-root data/dbn "
            "--offline-local-conditions"
        ),
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "schemas": ["ohlcv-1m", "definition", "status", "statistics"],
            "network": False,
            "canonical_raw_mutation": False,
            "candidate_raw_root": candidate_raw_root.as_posix(),
        },
        "timeout_seconds": 900,
        "expected_generated_artifacts": [
            (candidate_raw_root / "ES" / "2026.parquet").as_posix(),
            _expected_generated_under(reports_root, "databento_convert_results.json"),
            _expected_generated_under(reports_root, "raw_ingest_manifest.json"),
            _expected_generated_under(reports_root, "raw_parquet_manifest.json"),
        ],
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
        "stop_condition": (
            "Stop if optional status/statistics DBNs are missing, conversion touches canonical data/raw, "
            "the candidate output is not exactly ES 2026, or generated artifacts are staged."
        ),
        "approval_required_before_execution": True,
    }


def _optional_schema_audit_command(
    *,
    repair_reports_root: Path,
    candidate_raw_root: Path,
) -> dict[str, Any]:
    reports_root = repair_reports_root / "candidate_raw_optional_schema_audit"
    return {
        "name": "candidate_raw_optional_schema_audit",
        "command_family": "optional_enrichment_schema_audit",
        "command": (
            "python -m scripts.validation.audit_enriched_raw_optional_schemas "
            f"--raw-root {candidate_raw_root.as_posix()} --dbn-root data/dbn "
            f"--json-out {(reports_root / 'ES_2026_optional_schema_audit.json').as_posix()} "
            f"--md-out {(reports_root / 'ES_2026_optional_schema_audit.md').as_posix()}"
        ),
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "raw_root": candidate_raw_root.as_posix(),
            "requires_candidate_root_contains_only_target": True,
        },
        "timeout_seconds": 180,
        "expected_generated_artifacts": [
            (reports_root / "ES_2026_optional_schema_audit.json").as_posix(),
            (reports_root / "ES_2026_optional_schema_audit.md").as_posix(),
        ],
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
        "stop_condition": (
            "Stop unless the candidate raw root contains only ES 2026 and the audit returns PASS "
            "with optional status/statistics readiness PASS."
        ),
        "approval_required_before_execution": True,
    }


def _raw_quality_drilldown_command(
    *,
    checkpoint_jsonl: Path,
    repair_reports_root: Path,
    candidate_raw_root: Path,
) -> dict[str, Any]:
    json_out = repair_reports_root / "ES_2026_candidate_raw_quality_drilldown.json"
    return {
        "name": "candidate_raw_quality_drilldown",
        "command_family": "phase2_readiness_raw_drilldown",
        "command": (
            "python -m scripts.validation.drilldown_phase2_readiness_blockers "
            f"--checkpoint-jsonl {checkpoint_jsonl.as_posix()} "
            f"--raw-root {candidate_raw_root.as_posix()} --profile {DEFAULT_PROFILE} "
            "--markets ES --years 2026 --top-n 10 --max-selected-market-years 1 "
            f"--json-out {json_out.as_posix()}"
        ),
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "selected_market_year_limit": 1,
            "raw_root": candidate_raw_root.as_posix(),
        },
        "timeout_seconds": 180,
        "expected_generated_artifacts": [json_out.as_posix()],
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
        "stop_condition": (
            "Stop if selected scope is not exactly ES 2026, raw_read_status is not PASS, "
            "degraded evidence is unexplained, or generated artifacts are staged."
        ),
        "approval_required_before_execution": True,
    }


def _readiness_rerun_command(
    *,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    output_root: Path,
    raw_alignment_report: Path,
) -> dict[str, Any]:
    readiness_root = repair_reports_root / "candidate_readiness"
    include_list = readiness_root / "include_ES_2026.json"
    json_out = readiness_root / "phase2_readiness_summary.json"
    md_out = readiness_root / "phase2_readiness_summary.md"
    checkpoint = readiness_root / "phase2_readiness.progress.jsonl"
    return {
        "name": "candidate_readiness_only_rerun_after_repair",
        "command_family": "phase2_readiness_only_exact_scope",
        "command": (
            "python -m scripts.phase2_causal_base.build_causal_base_data "
            f"--readiness-only --profile {DEFAULT_PROFILE} "
            f"--raw-root {candidate_raw_root.as_posix()} "
            f"--output-root {output_root.as_posix()} "
            f"--reports-root {readiness_root.as_posix()} "
            f"--raw-alignment-report {raw_alignment_report.as_posix()} "
            f"--market-year-include-list {include_list.as_posix()} "
            f"--readiness-json-out {json_out.as_posix()} "
            f"--readiness-md-out {md_out.as_posix()} "
            f"--readiness-checkpoint-jsonl {checkpoint.as_posix()} "
            "--readiness-max-market-years 1 --readiness-stop-after-blockers 1 "
            "--readiness-progress"
        ),
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "selected_market_year_limit": 1,
            "raw_root": candidate_raw_root.as_posix(),
            "readiness_only": True,
            "causal_parquet_writes": False,
        },
        "timeout_seconds": 900,
        "expected_generated_artifacts": [
            include_list.as_posix(),
            json_out.as_posix(),
            md_out.as_posix(),
            checkpoint.as_posix(),
        ],
        "required_preconditions": [
            "candidate raw ES 2026 exists and passed optional schema audit",
            "exact-scope or otherwise approved raw-alignment evidence exists for the candidate raw root",
            "no ES 2026 exclusion or accepted-warning packet has been applied",
        ],
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
        "stop_condition": (
            "Stop after one ES 2026 readiness row. Proceed only if status is PASS, "
            "statistics/status enrichment gaps are zero, degraded threshold is not breached, "
            "and generated artifacts are unstaged."
        ),
        "approval_required_before_execution": True,
    }


def _reconfirm_command() -> dict[str, Any]:
    return {
        "name": "reconfirm_current_es2026_p1_proposal",
        "command_family": "console_only_proposal_gate",
        "command": "python -m scripts.validation.build_local_trade_es2026_p1_repair_proposal",
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "generated_outputs": 0,
        },
        "timeout_seconds": 180,
        "expected_generated_artifacts": [],
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
        "stop_condition": (
            "Stop if the proposal status is not REVIEW_READY_ES2026_P1_REPAIR_PROPOSAL "
            "or staged generated artifacts are detected."
        ),
        "approval_required_before_execution": True,
    }


def _plan_items(
    *,
    proposal_report: Mapping[str, Any],
    checkpoint_jsonl: Path,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    output_root: Path,
    raw_alignment_report: Path,
) -> list[dict[str, Any]]:
    proposal_items = proposal_report.get("proposal_items")
    if not isinstance(proposal_items, list):
        proposal_items = []
    source_evidence = proposal_report.get("source_evidence")
    if not isinstance(source_evidence, Mapping):
        source_evidence = {}
    return [
        {
            "action": "statistics_enrichment_repair_or_refresh_plan",
            "plan_status": PLAN_STATUS_APPROVAL_REQUIRED,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "source_evidence": source_evidence,
            "approved_direction": (
                "Repair or refresh statistics-enrichment evidence; do not accept missing/stale "
                "statistics metadata as model-ready evidence."
            ),
            "command_families": [
                _reconfirm_command(),
                _phase1_dry_run_command(schema="statistics", repair_reports_root=repair_reports_root),
                _phase1_dry_run_command(schema="status", repair_reports_root=repair_reports_root),
                _candidate_convert_command(
                    repair_reports_root=repair_reports_root,
                    candidate_raw_root=candidate_raw_root,
                ),
                _optional_schema_audit_command(
                    repair_reports_root=repair_reports_root,
                    candidate_raw_root=candidate_raw_root,
                ),
            ],
            "stop_condition_before_next_phase": (
                "Do not run readiness, causal-base repair/build, labels, or features until candidate "
                "raw ES 2026 exists and optional status/statistics audit evidence is PASS."
            ),
        },
        {
            "action": "degraded_raw_quality_review_plan",
            "plan_status": PLAN_STATUS_APPROVAL_REQUIRED,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "source_evidence": source_evidence,
            "approved_direction": (
                "Review degraded raw-quality evidence after any candidate statistics refresh; do not "
                "loosen thresholds or convert WARN to PASS without primary evidence."
            ),
            "command_families": [
                _raw_quality_drilldown_command(
                    checkpoint_jsonl=checkpoint_jsonl,
                    repair_reports_root=repair_reports_root,
                    candidate_raw_root=candidate_raw_root,
                ),
                _readiness_rerun_command(
                    repair_reports_root=repair_reports_root,
                    candidate_raw_root=candidate_raw_root,
                    output_root=output_root,
                    raw_alignment_report=raw_alignment_report,
                ),
            ],
            "stop_condition_before_next_phase": (
                "Do not promote ES 2026 into labels/features unless the exact-scope readiness-only "
                "rerun returns PASS with realistic warnings resolved or separately approved."
            ),
        },
        {
            "action": "keep_exclusion_diagnostic_only_plan",
            "plan_status": PLAN_STATUS_APPROVAL_REQUIRED,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "source_evidence": source_evidence,
            "approved_direction": (
                "Keep exclusion diagnostic-only unless a separate universe-change decision is approved."
            ),
            "command_families": [],
            "stop_condition_before_next_phase": (
                "Stop if any plan, script, or handoff proposes silently dropping ES 2026 to make "
                "baseline readiness pass."
            ),
        },
    ]


def _command_families(plan_items: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    families: list[Mapping[str, Any]] = []
    for item in plan_items:
        raw_families = item.get("command_families")
        if isinstance(raw_families, list):
            families.extend(family for family in raw_families if isinstance(family, Mapping))
    return families


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 repair-plan checks, then rerun this console-only gate."
    return (
        "Approve or reject bounded ES 2026 P1 repair-plan execution, starting with generated-report "
        "dry-runs/diagnostics only; do not run candidate raw writes, provider downloads, readiness reruns, "
        "causal-base builds, labels, or features without separate approval."
    )


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
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    proposal_report = proposal_gate.build_report(
        repo_root=repo_root,
        work_order_report=work_order_report,
        drilldown_report=drilldown_report,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_generated_paths,
    )
    proposal_summary = proposal_report["summary"]
    proposal_items = proposal_report.get("proposal_items")
    if not isinstance(proposal_items, list):
        proposal_items = []
    proposal_actions = sorted(
        str(item.get("action")) for item in proposal_items if isinstance(item, Mapping)
    )
    staged_count = int(proposal_summary.get("staged_generated_path_count") or 0)
    phase2_flags = _phase2_declared_flags()
    missing_phase2_flags = sorted(set(REQUIRED_PHASE2_FLAGS) - phase2_flags)
    missing_phase1_schemas = sorted(set(REQUIRED_PHASE1_SCHEMAS) - set(SUPPORTED_SCHEMAS))

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="proposal_gate_ready",
        passed=proposal_summary.get("status") == proposal_gate.STATUS_READY,
        observed=proposal_summary.get("status"),
        expected=proposal_gate.STATUS_READY,
        detail="Repair planning must start from the approved ES 2026 P1 proposal gate.",
    )
    _check(
        checks,
        name="approved_direction_actions_present",
        passed=set(REQUIRED_PROPOSAL_ACTIONS) <= set(proposal_actions),
        observed=proposal_actions,
        expected=list(REQUIRED_PROPOSAL_ACTIONS),
        detail="The plan must preserve the approved statistics, degraded-quality, and diagnostic-only directions.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=staged_count == 0,
        observed=staged_count,
        expected=0,
        detail="Generated data/** and reports/** artifacts must not be staged while planning repair.",
    )
    _check(
        checks,
        name="repair_reports_root_under_reports",
        passed=_path_under(repo_root, repair_reports_root, "reports"),
        observed=rel(repair_reports_root, repo_root),
        expected="reports/**",
        detail="Any later generated reports from the plan must stay under reports/.",
    )
    _check(
        checks,
        name="candidate_raw_root_under_data",
        passed=_path_under(repo_root, candidate_raw_root, "data"),
        observed=rel(candidate_raw_root, repo_root),
        expected="data/**",
        detail="Any later candidate raw output must stay under data/ and remain generated.",
    )
    _check(
        checks,
        name="phase1_supports_required_repair_schemas",
        passed=not missing_phase1_schemas,
        observed=missing_phase1_schemas,
        expected=[],
        detail="The Phase 1 raw contract must expose status/statistics schemas before planning enrichment repair.",
    )
    _check(
        checks,
        name="phase2_supports_exact_readiness_rerun",
        passed=not missing_phase2_flags,
        observed=missing_phase2_flags,
        expected=[],
        detail="Phase 2 readiness rerun must expose exact include-list and stop-after-blocker controls.",
    )
    _check(
        checks,
        name="repair_plan_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally exposes no generated report output arguments.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    plan_items = (
        _plan_items(
            proposal_report=proposal_report,
            checkpoint_jsonl=checkpoint_jsonl,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
        )
        if not failures
        else []
    )
    families = _command_families(plan_items)
    status = STATUS_NO_GO if failures else STATUS_READY
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_PLAN_ONLY,
            "input_work_order_report": rel(work_order_report, repo_root),
            "input_drilldown_report": rel(drilldown_report, repo_root),
            "input_checkpoint_jsonl": rel(checkpoint_jsonl, repo_root),
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "plan_item_count": len(plan_items),
            "command_family_count": len(families),
            "approval_required_command_family_count": sum(
                1 for family in families if family.get("approval_required_before_execution") is True
            ),
            "repair_reports_root": rel(repair_reports_root, repo_root),
            "candidate_raw_root": rel(candidate_raw_root, repo_root),
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": staged_count,
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "plan_items": plan_items,
        "proposal_summary": {
            "status": proposal_summary.get("status"),
            "proposal_item_count": proposal_summary.get("proposal_item_count"),
            "p1_work_order_count": proposal_summary.get("p1_work_order_count"),
            "failure_count": proposal_summary.get("failure_count"),
        },
        "non_approval": {
            "scope": "ES 2026 P1 repair plan only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-order-report", default=str(DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--drilldown-report", default=str(DEFAULT_DRILLDOWN_REPORT))
    parser.add_argument("--checkpoint-jsonl", default=str(DEFAULT_CHECKPOINT_JSONL))
    parser.add_argument("--repair-reports-root", default=str(DEFAULT_REPAIR_REPORTS_ROOT))
    parser.add_argument("--candidate-raw-root", default=str(DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(DEFAULT_RAW_ALIGNMENT_REPORT))
    parser.add_argument("--print-plan-json", action="store_true")
    return parser


def plan_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        summary = {}
    return {
        "stage": STAGE,
        "status": summary.get("status"),
        "market": summary.get("market"),
        "year": summary.get("year"),
        "recommended_next_action": summary.get("recommended_next_action"),
        "plan_item_count": summary.get("plan_item_count"),
        "command_family_count": summary.get("command_family_count"),
        "approval_required_command_family_count": summary.get(
            "approval_required_command_family_count"
        ),
        "repair_reports_root": summary.get("repair_reports_root"),
        "candidate_raw_root": summary.get("candidate_raw_root"),
        "plan_items": report.get("plan_items", []),
        "generated_artifact_hygiene": {
            "generated_output_count": summary.get("generated_output_count"),
            "staged_generated_path_count": summary.get("staged_generated_path_count"),
        },
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
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"plan_items={summary['plan_item_count']} "
        f"command_families={summary['command_family_count']} "
        f"approval_required_commands={summary['approval_required_command_family_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_plan_json:
        print(json.dumps(plan_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
