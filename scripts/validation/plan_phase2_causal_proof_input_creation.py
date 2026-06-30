#!/usr/bin/env python3
"""Read-only plan for bounded Phase 2 causal proof input creation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import check_phase2_local_trade_ohlcv_gap_proof as proof_gate
from scripts.validation import plan_phase2_causal_proof_input_path as path_gate
from scripts.validation import reconcile_phase2_local_trade_causal_inputs as reconcile_gate


STATUS_READY = "READY_FOR_SEPARATE_BOUNDED_CAUSAL_INPUT_CREATION_APPROVAL"
STATUS_BLOCKED = "NO_GO_CAUSAL_INPUT_CREATION_PLAN_BLOCKED"

DEFAULT_OUTPUT_ROOT = "data/causal_proof_candidates/local_trade_2025_2026_v1"
DEFAULT_REPORTS_ROOT = "reports/pipeline_audit/causal_proof_candidates/local_trade_2025_2026_v1"
INCLUDE_LIST_NAME = "market_year_include_list.json"
CHECKPOINT_NAME = "build_progress_checkpoint.jsonl"
EXCLUDED_RUNNER_TERMS = (
    "build_broad_manifest_527_rebuild.py",
    "monitor_broad_manifest_527_rebuild.py",
    "run_broad_manifest_527_step_loop.py",
    "run_broad_manifest_527_step_loop.ps1",
    "run_broad_manifest_source_gap_fail_closed_loop.py",
)


def _has_files(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file():
        return True
    return any(child.is_file() for child in path.rglob("*"))


def _include_rows(markets: list[str]) -> list[dict[str, Any]]:
    return [
        {"market": market, "year": year}
        for market in sorted(markets)
        for year in reconcile_gate.PROOF_YEARS
    ]


def _win_path(path: str) -> str:
    return path.replace("/", "\\")


def _build_command(
    *,
    include_list_path: str,
    output_root: str,
    reports_root: str,
    checkpoint_path: str,
    expected_count: int,
) -> list[str]:
    return [
        "python",
        "scripts\\phase2_causal_base\\build_causal_base_data.py",
        "--profile",
        "all_raw",
        "--raw-root",
        "data\\raw",
        "--output-root",
        _win_path(output_root),
        "--reports-root",
        _win_path(reports_root),
        "--profile-config",
        "configs\\alpha_tiered.yaml",
        "--session-config",
        "configs\\market_sessions.yaml",
        "--raw-alignment-report",
        "reports\\raw_ingest\\raw_dbn_alignment.json",
        "--market-year-include-list",
        _win_path(include_list_path),
        "--build-max-market-years",
        str(expected_count),
        "--build-progress-checkpoint-jsonl",
        _win_path(checkpoint_path),
    ]


def _command_text(command: list[str]) -> str:
    return " ".join(command)


def evaluate_plan(
    *,
    repo_root: Path,
    output_root: Path,
    reports_root: Path,
    data_manifest_path: Path,
    canonical_root: Path,
    phase2_reports_root: Path,
    phase2_manifest_path: Path,
    phase2_validation_path: Path,
    profile_config_path: Path,
    build_script_path: Path,
    local_report_paths: list[Path],
    expected_count: int = scope_gate.EXPECTED_CANONICAL_COUNT,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    path_plan = path_gate.evaluate_plan(
        repo_root=repo_root,
        data_manifest_path=data_manifest_path,
        canonical_root=canonical_root,
        reports_root=phase2_reports_root,
        phase2_manifest_path=phase2_manifest_path,
        phase2_validation_path=phase2_validation_path,
        profile_config_path=profile_config_path,
        build_script_path=build_script_path,
        local_report_paths=local_report_paths,
        candidate_roots=[
            scope_gate.resolve_path(repo_root, root)
            for root in reconcile_gate.DEFAULT_CANDIDATE_ROOTS
        ],
        expected_count=expected_count,
    )
    uncovered_markets = [str(market) for market in path_plan.get("uncovered_markets", [])]
    rows = _include_rows(uncovered_markets)
    include_list_path = reports_root / INCLUDE_LIST_NAME
    checkpoint_path = reports_root / CHECKPOINT_NAME
    output_root_rel = scope_gate.rel(output_root, repo_root)
    reports_root_rel = scope_gate.rel(reports_root, repo_root)
    include_list_rel = scope_gate.rel(include_list_path, repo_root)
    checkpoint_rel = scope_gate.rel(checkpoint_path, repo_root)
    command = _build_command(
        include_list_path=include_list_rel,
        output_root=output_root_rel,
        reports_root=reports_root_rel,
        checkpoint_path=checkpoint_rel,
        expected_count=len(rows),
    )
    command_text = _command_text(command)

    checks = [
        {
            "name": "path_plan_requires_causal_input_authorization",
            "status": "PASS"
            if path_plan["summary"]["status"] == path_gate.STATUS_NO_GO
            else "FAIL",
            "observed": path_plan["summary"]["status"],
            "expected": path_gate.STATUS_NO_GO,
            "detail": "Creation planning is valid only when existing roots are not usable.",
        },
        {
            "name": "include_list_expected_count",
            "status": "PASS" if len(rows) == 58 else "FAIL",
            "observed": len(rows),
            "expected": 58,
            "detail": "Bounded creation scope must be exactly 29 uncovered markets x 2025/2026.",
        },
        {
            "name": "output_root_is_quarantine_noncanonical",
            "status": "PASS"
            if output_root_rel == DEFAULT_OUTPUT_ROOT
            and output_root_rel != scope_gate.CANONICAL_ROOT_REL
            else "FAIL",
            "observed": output_root_rel,
            "expected": DEFAULT_OUTPUT_ROOT,
            "detail": "Future outputs must be generated proof candidates, not canonical Phase 2 data.",
        },
        {
            "name": "reports_root_is_noncanonical",
            "status": "PASS"
            if reports_root_rel == DEFAULT_REPORTS_ROOT
            and reports_root_rel != scope_gate.REPORTS_ROOT_REL
            else "FAIL",
            "observed": reports_root_rel,
            "expected": DEFAULT_REPORTS_ROOT,
            "detail": "Future reports/checkpoints must not refresh promoted Phase 2 reports.",
        },
        {
            "name": "output_root_empty_or_absent",
            "status": "PASS" if not _has_files(output_root) else "FAIL",
            "observed": scope_gate.rel(output_root, repo_root) if _has_files(output_root) else "empty_or_absent",
            "expected": "empty_or_absent",
            "detail": "Future mutation run must not overwrite existing output artifacts.",
        },
        {
            "name": "reports_root_empty_or_absent",
            "status": "PASS" if not _has_files(reports_root) else "FAIL",
            "observed": scope_gate.rel(reports_root, repo_root) if _has_files(reports_root) else "empty_or_absent",
            "expected": "empty_or_absent",
            "detail": "Future mutation run must not overwrite existing report/checkpoint artifacts.",
        },
        {
            "name": "command_excludes_broad_build_loop_files",
            "status": "PASS"
            if not any(term in command_text for term in EXCLUDED_RUNNER_TERMS)
            else "FAIL",
            "observed": command_text,
            "expected": "no broad build/loop runner file",
            "detail": "Future command must use the committed causal builder directly.",
        },
    ]
    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_READY if not failures else STATUS_BLOCKED
    return {
        "summary": {
            "stage": "phase2_causal_proof_input_creation_plan",
            "generated_at_utc": generated_at_utc or scope_gate.utc_now(),
            "status": status,
            "approved_scope": "29 uncovered canonical markets x 2025/2026 proof inputs only",
            "uncovered_market_count": len(uncovered_markets),
            "include_row_count": len(rows),
            "expected_output_files": len(rows),
            "output_root": output_root_rel,
            "reports_root": reports_root_rel,
            "include_list_path": include_list_rel,
            "checkpoint_path": checkpoint_rel,
            "stdout_only": True,
            "provider_download_performed": False,
            "reports_refreshed": False,
            "data_mutation_performed": False,
            "broad_build_loop_runner_used": False,
            "canonical_promotion_approved": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "live_or_paper_execution_approved": False,
            "failure_count": len(failures),
        },
        "checks": checks,
        "uncovered_markets": uncovered_markets,
        "include_list_rows": rows,
        "command": command,
        "command_text": command_text,
        "stop_conditions": [
            "Do not run without separate explicit approval for a generated-artifact mutation run.",
            "Stop if output or reports root contains existing files.",
            "Stop if resolved include list is not exactly 58 market-year rows.",
            "Do not refresh promoted Phase 2 reports or promote outputs to canonical.",
            "Do not run broad build/loop files, modeling, WFA, metrics, predictions, cleanup, labels, feature matrices, or live/paper execution.",
        ],
        "path_plan": path_plan,
    }


def render_console(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "phase2_causal_proof_input_creation_plan "
        f"status={summary['status']} "
        f"include_rows={summary['include_row_count']} "
        f"output_root={summary['output_root']} "
        f"reports_root={summary['reports_root']} "
        f"failure_count={summary['failure_count']}",
    ]
    for check in report["checks"]:
        if check["status"] == "FAIL":
            lines.append(
                f"FAIL {check['name']}: observed={check['observed']!r} expected={check['expected']!r}"
            )
    lines.append(f"INCLUDE_LIST_PATH {summary['include_list_path']}")
    lines.append(f"COMMAND_TEMPLATE {report['command_text']}")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT)
    parser.add_argument("--data-manifest", default=str(scope_gate.DEFAULT_DATA_MANIFEST))
    parser.add_argument("--canonical-root", default=str(scope_gate.DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--phase2-reports-root", default=str(scope_gate.DEFAULT_REPORTS_ROOT))
    parser.add_argument("--phase2-manifest", default=str(scope_gate.DEFAULT_PHASE2_MANIFEST))
    parser.add_argument("--phase2-validation", default=str(scope_gate.DEFAULT_PHASE2_VALIDATION))
    parser.add_argument("--profile-config", default=str(scope_gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--build-script", default=str(scope_gate.DEFAULT_BUILD_SCRIPT))
    parser.add_argument("--local-trade-report", action="append", default=None)
    parser.add_argument("--expected-count", type=int, default=scope_gate.EXPECTED_CANONICAL_COUNT)
    parser.add_argument("--json", action="store_true", help="Print the read-only plan JSON to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    local_report_paths = [
        scope_gate.resolve_path(repo_root, path)
        for path in (args.local_trade_report or [str(proof_gate.DEFAULT_LOCAL_TRADE_REPORT)])
    ]
    report = evaluate_plan(
        repo_root=repo_root,
        output_root=scope_gate.resolve_path(repo_root, args.output_root),
        reports_root=scope_gate.resolve_path(repo_root, args.reports_root),
        data_manifest_path=scope_gate.resolve_path(repo_root, args.data_manifest),
        canonical_root=scope_gate.resolve_path(repo_root, args.canonical_root),
        phase2_reports_root=scope_gate.resolve_path(repo_root, args.phase2_reports_root),
        phase2_manifest_path=scope_gate.resolve_path(repo_root, args.phase2_manifest),
        phase2_validation_path=scope_gate.resolve_path(repo_root, args.phase2_validation),
        profile_config_path=scope_gate.resolve_path(repo_root, args.profile_config),
        build_script_path=scope_gate.resolve_path(repo_root, args.build_script),
        local_report_paths=local_report_paths,
        expected_count=args.expected_count,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_console(report))
    return 0 if report["summary"]["status"] == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
