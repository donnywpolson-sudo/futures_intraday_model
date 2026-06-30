#!/usr/bin/env python3
"""Read-only authorization planner for missing Phase 2 causal proof inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import check_phase2_local_trade_ohlcv_gap_proof as proof_gate
from scripts.validation import reconcile_phase2_local_trade_causal_inputs as reconcile_gate


STATUS_NO_GO = "NO_GO_NEEDS_CAUSAL_INPUT_AUTHORIZATION"
STATUS_READY = "READY_USE_EXISTING_AUTHORIZED_ROOT"
STATUS_MULTIPLE = "HUMAN_DECISION_REQUIRED_MULTIPLE_ROOTS"

DEFAULT_QUARANTINE_ROOT = "data/causal_proof_candidates/local_trade_2025_2026_v1"


def _decision_status(reconciliation_status: str) -> str:
    if reconciliation_status == reconcile_gate.STATUS_READY:
        return STATUS_READY
    if reconciliation_status == reconcile_gate.STATUS_AMBIGUOUS:
        return STATUS_MULTIPLE
    return STATUS_NO_GO


def _future_creation_authorization(
    *,
    uncovered_markets: list[str],
    expected_file_count: int,
    quarantine_root: str,
) -> dict[str, Any]:
    return {
        "decision": "separate_human_authorization_required",
        "purpose": "obtain missing local causal proof inputs only",
        "output_root": quarantine_root,
        "markets": uncovered_markets,
        "years": list(reconcile_gate.PROOF_YEARS),
        "expected_output_files": expected_file_count,
        "must_be_generated_artifact": True,
        "must_not_refresh_phase2_reports": True,
        "must_not_promote_to_canonical": True,
        "must_not_run_modeling_wfa_metrics_predictions_or_execution": True,
    }


def evaluate_plan(
    *,
    repo_root: Path,
    data_manifest_path: Path,
    canonical_root: Path,
    reports_root: Path,
    phase2_manifest_path: Path,
    phase2_validation_path: Path,
    profile_config_path: Path,
    build_script_path: Path,
    local_report_paths: list[Path],
    candidate_roots: list[Path],
    quarantine_root: str = DEFAULT_QUARANTINE_ROOT,
    expected_count: int = scope_gate.EXPECTED_CANONICAL_COUNT,
    feature_cols: Iterable[str] | None = None,
    git_head: str | None = None,
    staged_names: list[str] | None = None,
    scoped_status_lines: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    reconciliation = reconcile_gate.evaluate_reconciliation(
        repo_root=repo_root,
        data_manifest_path=data_manifest_path,
        canonical_root=canonical_root,
        reports_root=reports_root,
        phase2_manifest_path=phase2_manifest_path,
        phase2_validation_path=phase2_validation_path,
        profile_config_path=profile_config_path,
        build_script_path=build_script_path,
        local_report_paths=local_report_paths,
        candidate_roots=candidate_roots,
        expected_count=expected_count,
        feature_cols=feature_cols,
        git_head=git_head,
        staged_names=staged_names,
        scoped_status_lines=scoped_status_lines,
        generated_at_utc=generated_at_utc,
    )
    status = _decision_status(str(reconciliation["summary"]["status"]))
    usable_roots = list(reconciliation.get("usable_roots", []))
    uncovered_markets = [str(market) for market in reconciliation.get("uncovered_markets", [])]
    expected_file_count = int(reconciliation["summary"]["expected_causal_file_count"])

    allowed_paths: list[dict[str, Any]] = [
        {
            "name": "keep_blocker_no_go",
            "status": "available",
            "detail": "Leave local trade/OHLCV proof no-go until causal inputs are obtained.",
        },
        {
            "name": "use_existing_local_candidate_root",
            "status": "available" if len(usable_roots) == 1 else "blocked",
            "usable_roots": usable_roots,
            "detail": "Allowed only when reconciliation finds exactly one usable existing local root.",
        },
        {
            "name": "authorize_future_bounded_causal_input_creation",
            "status": "requires_separate_approval",
            "authorization": _future_creation_authorization(
                uncovered_markets=uncovered_markets,
                expected_file_count=expected_file_count,
                quarantine_root=quarantine_root,
            ),
        },
    ]

    return {
        "summary": {
            "stage": "phase2_causal_proof_input_path_plan",
            "generated_at_utc": generated_at_utc or scope_gate.utc_now(),
            "status": status,
            "reconciliation_status": reconciliation["summary"]["status"],
            "approved_scope": "promoted canonical broad_manifest_527_rebuild_v1 460-row Phase 2 only",
            "uncovered_market_count": len(uncovered_markets),
            "expected_causal_file_count": expected_file_count,
            "usable_root_count": len(usable_roots),
            "candidate_root_count": int(reconciliation["summary"]["candidate_root_count"]),
            "default_quarantine_root": quarantine_root,
            "stdout_only": True,
            "provider_download_performed": False,
            "reports_refreshed": False,
            "data_mutation_performed": False,
            "broad_build_loop_runner_used": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "live_or_paper_execution_approved": False,
        },
        "allowed_paths": allowed_paths,
        "uncovered_markets": uncovered_markets,
        "usable_roots": usable_roots,
        "reconciliation": reconciliation,
    }


def render_console(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "phase2_causal_proof_input_path_plan "
        f"status={summary['status']} "
        f"reconciliation_status={summary['reconciliation_status']} "
        f"uncovered_markets={summary['uncovered_market_count']} "
        f"expected_causal_files={summary['expected_causal_file_count']} "
        f"candidate_roots={summary['candidate_root_count']} "
        f"usable_roots={summary['usable_root_count']}",
    ]
    for path in report["allowed_paths"]:
        lines.append(f"PATH {path['name']} status={path['status']}")
    if summary["status"] == STATUS_READY:
        lines.append(f"READY_ROOT {report['usable_roots'][0]}")
    elif summary["status"] == STATUS_MULTIPLE:
        lines.append(f"HUMAN_DECISION usable_roots={report['usable_roots']!r}")
    else:
        lines.append(
            "NEXT_AUTHORIZATION "
            f"output_root={summary['default_quarantine_root']} "
            f"expected_files={summary['expected_causal_file_count']}"
        )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--data-manifest", default=str(scope_gate.DEFAULT_DATA_MANIFEST))
    parser.add_argument("--canonical-root", default=str(scope_gate.DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--reports-root", default=str(scope_gate.DEFAULT_REPORTS_ROOT))
    parser.add_argument("--phase2-manifest", default=str(scope_gate.DEFAULT_PHASE2_MANIFEST))
    parser.add_argument("--phase2-validation", default=str(scope_gate.DEFAULT_PHASE2_VALIDATION))
    parser.add_argument("--profile-config", default=str(scope_gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--build-script", default=str(scope_gate.DEFAULT_BUILD_SCRIPT))
    parser.add_argument("--local-trade-report", action="append", default=None)
    parser.add_argument("--candidate-root", action="append", default=None)
    parser.add_argument("--quarantine-root", default=DEFAULT_QUARANTINE_ROOT)
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
    candidate_roots = [
        scope_gate.resolve_path(repo_root, path)
        for path in [*(str(path) for path in reconcile_gate.DEFAULT_CANDIDATE_ROOTS), *(args.candidate_root or [])]
    ]
    report = evaluate_plan(
        repo_root=repo_root,
        data_manifest_path=scope_gate.resolve_path(repo_root, args.data_manifest),
        canonical_root=scope_gate.resolve_path(repo_root, args.canonical_root),
        reports_root=scope_gate.resolve_path(repo_root, args.reports_root),
        phase2_manifest_path=scope_gate.resolve_path(repo_root, args.phase2_manifest),
        phase2_validation_path=scope_gate.resolve_path(repo_root, args.phase2_validation),
        profile_config_path=scope_gate.resolve_path(repo_root, args.profile_config),
        build_script_path=scope_gate.resolve_path(repo_root, args.build_script),
        local_report_paths=local_report_paths,
        candidate_roots=candidate_roots,
        quarantine_root=str(args.quarantine_root),
        expected_count=args.expected_count,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_console(report))
    return 0 if report["summary"]["status"] == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
