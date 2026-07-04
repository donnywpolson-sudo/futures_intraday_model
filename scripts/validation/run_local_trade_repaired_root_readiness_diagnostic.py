#!/usr/bin/env python3
"""Run the approved repaired-root readiness diagnostic plan."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_repaired_root_readiness_diagnostic_plan as plan_gate


STAGE = "local_trade_repaired_root_readiness_diagnostic_execution"
STATUS_DRY_RUN_READY = "DRY_RUN_READY_REPAIRED_ROOT_READINESS_DIAGNOSTIC_EXECUTION"
STATUS_EXECUTED = "EXECUTED_REPAIRED_ROOT_READINESS_DIAGNOSTIC"
STATUS_NO_GO = "NO_GO_REPAIRED_ROOT_READINESS_DIAGNOSTIC_EXECUTION"
DECISION_DRY_RUN = "repaired_root_readiness_diagnostic_execution_dry_run_only"
DECISION_APPROVED = "human_approved_repaired_root_readiness_diagnostic_execution"
DECISION_BLOCKED = "repaired_root_readiness_diagnostic_execution_blocked"
APPROVAL_TOKEN = "APPROVE_REPAIRED_ROOT_READINESS_DIAGNOSTIC_V1"

FALSE_APPROVAL_FLAGS = (
    "accepted_warning_packet_approved",
    "causal_base_repair_approved",
    "label_build_approved",
    "feature_matrix_build_approved",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "canonical_promotion_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "live_or_paper_execution_approved",
)

FORBIDDEN_ARG_FLAGS = {
    "--allow-broad-build-after-readiness-pass",
    "--broad-build-approval-token",
    "--build-max-market-years",
    "--build-progress-checkpoint-jsonl",
    "--accepted-readiness-exceptions",
}


CommandRunner = Callable[[Sequence[str], Path, int], subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return plan_gate.rel(path, repo_root)


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


def _default_command_runner(
    argv: Sequence[str],
    cwd: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )


def _ensure_reports_path(repo_root: Path, path: Path) -> list[str]:
    try:
        path.resolve().relative_to((repo_root / "reports").resolve())
    except ValueError:
        return [f"path must be under reports/: {rel(path, repo_root)}"]
    return []


def _is_under_reports(repo_root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to((repo_root / "reports").resolve())
    except ValueError:
        return False
    return True


def _arg_value(argv: Sequence[str], flag: str) -> str | None:
    try:
        index = list(argv).index(flag)
    except ValueError:
        return None
    value_index = index + 1
    return str(argv[value_index]) if value_index < len(argv) else None


def _bounded_argv(
    *,
    group: Mapping[str, Any],
    raw_root: str,
    output_root: str,
    default_raw_alignment_report: str,
) -> list[str]:
    paths = group["planned_paths"]
    max_rows = int(group["market_year_count"])
    raw_alignment_report = str(group.get("raw_alignment_report") or default_raw_alignment_report)
    return [
        sys.executable,
        "-m",
        "scripts.phase2_causal_base.build_causal_base_data",
        "--readiness-only",
        "--profile",
        str(group["profile"]),
        "--raw-root",
        raw_root,
        "--output-root",
        output_root,
        "--reports-root",
        str(paths["reports_root"]),
        "--raw-alignment-report",
        raw_alignment_report,
        "--market-year-include-list",
        str(paths["include_list"]),
        "--readiness-json-out",
        str(paths["readiness_json"]),
        "--readiness-md-out",
        str(paths["readiness_markdown"]),
        "--readiness-checkpoint-jsonl",
        str(paths["readiness_checkpoint_jsonl"]),
        "--readiness-max-market-years",
        str(max_rows),
        "--readiness-stop-after-blockers",
        str(max_rows),
        "--readiness-progress",
    ]


def _argv_bound_failures(argv: Sequence[str]) -> list[str]:
    failures: list[str] = []
    argv_set = set(argv)
    if "--readiness-only" not in argv_set:
        failures.append("--readiness-only missing")
    for forbidden in sorted(FORBIDDEN_ARG_FLAGS):
        if forbidden in argv_set:
            failures.append(f"forbidden argument present: {forbidden}")
    if _arg_value(argv, "--build-max-market-years") is not None:
        failures.append("build mode limiter should never be present")
    return failures


def _planned_generated_paths(group: Mapping[str, Any]) -> list[str]:
    paths = group["planned_paths"]
    return [
        str(paths["include_list"]),
        str(paths["readiness_json"]),
        str(paths["readiness_markdown"]),
        str(paths["readiness_checkpoint_jsonl"]),
    ]


def _write_include_list(
    *,
    repo_root: Path,
    group: Mapping[str, Any],
) -> str:
    paths = group["planned_paths"]
    include_path = resolve_path(repo_root, str(paths["include_list"]))
    failures = _ensure_reports_path(repo_root, include_path)
    if failures:
        raise ValueError("; ".join(failures))
    include_path.parent.mkdir(parents=True, exist_ok=True)
    include_path.write_text(json.dumps(group["include_list_payload"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rel(include_path, repo_root)


def _existing_generated_paths(repo_root: Path, groups: Iterable[Mapping[str, Any]]) -> list[str]:
    existing: list[str] = []
    for group in groups:
        for path in _planned_generated_paths(group):
            resolved = resolve_path(repo_root, path)
            if resolved.exists():
                existing.append(rel(resolved, repo_root))
    return sorted(existing)


def _existing_tree_files(repo_root: Path, root: Path) -> list[str]:
    if not _is_under_reports(repo_root, root):
        return []
    if not root.exists():
        return []
    if root.is_file():
        return [rel(root, repo_root)]
    return sorted(rel(path, repo_root) for path in root.rglob("*") if path.is_file())


def _git_staged_generated_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "data", "reports"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --cached failed")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _post_command_artifact_failures(repo_root: Path, group: Mapping[str, Any]) -> list[str]:
    paths = group["planned_paths"]
    failures: list[str] = []
    include_path = resolve_path(repo_root, str(paths["include_list"]))
    readiness_json = resolve_path(repo_root, str(paths["readiness_json"]))
    readiness_markdown = resolve_path(repo_root, str(paths["readiness_markdown"]))
    checkpoint_jsonl = resolve_path(repo_root, str(paths["readiness_checkpoint_jsonl"]))

    for label, path in [
        ("include list", include_path),
        ("readiness JSON", readiness_json),
        ("readiness markdown", readiness_markdown),
        ("readiness checkpoint JSONL", checkpoint_jsonl),
    ]:
        if not path.exists():
            failures.append(f"missing {label}: {rel(path, repo_root)}")

    if readiness_json.exists():
        payload = _read_json_object(readiness_json)
        if payload is None:
            failures.append(f"unreadable readiness JSON: {rel(readiness_json, repo_root)}")
        else:
            expected_count = int(group["market_year_count"])
            if payload.get("status") != "PASS":
                failures.append(f"readiness JSON status is not PASS: {payload.get('status')}")
            if payload.get("selected_market_year_count") != expected_count:
                failures.append(
                    "unexpected selected_market_year_count: "
                    f"{payload.get('selected_market_year_count')} != {expected_count}"
                )

    for label, path in [
        ("readiness markdown", readiness_markdown),
        ("readiness checkpoint JSONL", checkpoint_jsonl),
    ]:
        if path.exists():
            try:
                if not path.read_text(encoding="utf-8").strip():
                    failures.append(f"empty {label}: {rel(path, repo_root)}")
            except OSError:
                failures.append(f"unreadable {label}: {rel(path, repo_root)}")

    return failures


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    diagnostic_reports_root: Path,
    execute: bool = False,
    approval_token: str | None = None,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    expected_eligible_market_count: int = plan_gate.resolver_gate.DEFAULT_EXPECTED_ELIGIBLE_MARKETS,
    expected_proof_status_market_year_count: int = plan_gate.resolver_gate.DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
    raw_root: str = plan_gate.DEFAULT_RAW_ROOT,
    output_root: str = plan_gate.DEFAULT_OUTPUT_ROOT,
    raw_alignment_report: str = plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT,
    raw_alignment_report_overrides: Mapping[str, str] | None = None,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    runner = command_runner or _default_command_runner
    plan = plan_gate.build_report(
        repo_root=repo_root,
        proposal_path=proposal_path,
        diagnostic_reports_root=diagnostic_reports_root,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_generated_paths,
        expected_eligible_market_count=expected_eligible_market_count,
        expected_proof_status_market_year_count=expected_proof_status_market_year_count,
        raw_root=raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        raw_alignment_report_overrides=raw_alignment_report_overrides,
    )
    plan_summary = plan["summary"]
    groups = [group for group in plan.get("diagnostic_groups", []) if isinstance(group, Mapping)]
    existing_before = _existing_generated_paths(repo_root, groups)
    existing_tree_before = _existing_tree_files(repo_root, diagnostic_reports_root)

    argv_by_group = [
        _bounded_argv(
            group=group,
            raw_root=raw_root,
            output_root=output_root,
            default_raw_alignment_report=raw_alignment_report,
        )
        for group in groups
    ]
    argv_failures = [
        {"year": group.get("year"), "failures": failures}
        for group, argv in zip(groups, argv_by_group)
        if (failures := _argv_bound_failures(argv))
    ]

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="diagnostic_plan_ready",
        passed=plan_summary.get("status") == plan_gate.STATUS_READY,
        observed=plan_summary.get("status"),
        expected=plan_gate.STATUS_READY,
        detail="Execution can only use a ready repaired-root diagnostic plan.",
    )
    _check(
        checks,
        name="execution_approval_token_present_when_execute",
        passed=(not execute) or approval_token == APPROVAL_TOKEN,
        observed="provided" if approval_token else None,
        expected=f"{APPROVAL_TOKEN} when --execute is used",
        detail="Generated diagnostic artifacts and readiness commands require explicit approval.",
    )
    _check(
        checks,
        name="planned_generated_outputs_absent_before_execution",
        passed=not existing_before,
        observed=existing_before,
        expected=[],
        detail="The diagnostic runner should not overwrite prior generated diagnostic outputs.",
    )
    _check(
        checks,
        name="diagnostic_reports_root_empty_before_execution",
        passed=not existing_tree_before,
        observed=existing_tree_before,
        expected=[],
        detail="The diagnostic runner should not mix new diagnostics with stale files under the reports root.",
    )
    _check(
        checks,
        name="bounded_phase2_readiness_argv_only",
        passed=not argv_failures and bool(argv_by_group),
        observed=argv_failures,
        expected="only Phase 2 --readiness-only argv without forbidden build flags",
        detail="Execution must be bounded to readiness diagnostics, never causal-base build mode.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    command_results: list[dict[str, Any]] = []
    written_include_lists: list[str] = []
    timed_out = False
    if execute and not failures:
        for group, argv in zip(groups, argv_by_group):
            written_include_lists.append(_write_include_list(repo_root=repo_root, group=group))
            try:
                result = runner(argv, repo_root, int(group["timeout_seconds"]))
            except subprocess.TimeoutExpired as exc:
                command_results.append(
                    {
                        "year": group.get("year"),
                        "returncode": None,
                        "timed_out": True,
                        "timeout_seconds": group.get("timeout_seconds"),
                        "stdout": exc.stdout,
                        "stderr": exc.stderr,
                        "argv": list(argv),
                    }
                )
                timed_out = True
                break
            command_results.append(
                {
                    "year": group.get("year"),
                    "returncode": result.returncode,
                    "timed_out": False,
                    "timeout_seconds": group.get("timeout_seconds"),
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "argv": list(argv),
                }
            )
            if result.returncode != 0:
                break
            artifact_failures = _post_command_artifact_failures(repo_root, group)
            if artifact_failures:
                command_results[-1]["artifact_failures"] = artifact_failures
                break

    command_failures = [
        result
        for result in command_results
        if result.get("timed_out") or result.get("returncode") not in (0, None)
    ]
    artifact_failures = [
        result
        for result in command_results
        if result.get("artifact_failures")
    ]
    existing_after = _existing_generated_paths(repo_root, groups)
    planned_after = sorted({path for group in groups for path in _planned_generated_paths(group)})
    unexpected_tree_after = [
        path
        for path in _existing_tree_files(repo_root, diagnostic_reports_root)
        if path not in planned_after
    ]
    post_execution_staged_paths = _git_staged_generated_paths(repo_root) if command_results else []
    if command_failures:
        _check(
            checks,
            name="readiness_commands_completed",
            passed=False,
            observed=[
                {
                    "year": result.get("year"),
                    "returncode": result.get("returncode"),
                    "timed_out": result.get("timed_out"),
                }
                for result in command_failures
            ],
            expected="all approved readiness commands return 0 without timeout",
            detail="Stop after the first readiness timeout or nonzero exit.",
        )
        failures = [check for check in checks if check["status"] == "FAIL"]
    if artifact_failures:
        _check(
            checks,
            name="readiness_artifacts_present_and_readable",
            passed=False,
            observed=[
                {
                    "year": result.get("year"),
                    "artifact_failures": result.get("artifact_failures"),
                }
                for result in artifact_failures
            ],
            expected="include list plus PASS readiness JSON/markdown/checkpoint with expected selected count",
            detail="Stop after a readiness command returns success without readable expected artifacts.",
        )
        failures = [check for check in checks if check["status"] == "FAIL"]
    if unexpected_tree_after:
        _check(
            checks,
            name="unexpected_diagnostic_reports_absent",
            passed=False,
            observed=unexpected_tree_after,
            expected=[],
            detail="Execution may only create the bounded include-list and readiness report artifacts.",
        )
        failures = [check for check in checks if check["status"] == "FAIL"]
    if post_execution_staged_paths:
        _check(
            checks,
            name="post_execution_staged_generated_artifacts_absent",
            passed=False,
            observed=post_execution_staged_paths,
            expected=[],
            detail="Generated data/** and reports/** artifacts must remain unstaged after diagnostic execution.",
        )
        failures = [check for check in checks if check["status"] == "FAIL"]

    if failures:
        status = STATUS_NO_GO
        decision = DECISION_BLOCKED
    elif execute:
        status = STATUS_EXECUTED
        decision = DECISION_APPROVED
    else:
        status = STATUS_DRY_RUN_READY
        decision = DECISION_DRY_RUN

    approval_flags = {flag: False for flag in FALSE_APPROVAL_FLAGS}
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": decision,
            "input_proposal": plan_summary.get("input_proposal"),
            "input_plan_status": plan_summary.get("status"),
            "execute_requested": execute,
            "approval_token_required": APPROVAL_TOKEN if execute else None,
            "readiness_diagnostic_approved": bool(execute and not failures),
            "diagnostic_group_count": len(groups),
            "diagnostic_market_year_count": plan_summary.get("diagnostic_market_year_count"),
            "raw_alignment_report_count": plan_summary.get("raw_alignment_report_count"),
            "raw_alignment_report_override_count": plan_summary.get("raw_alignment_report_override_count"),
            "raw_alignment_reports": plan_summary.get("raw_alignment_reports"),
            "commands_planned": len(argv_by_group),
            "commands_executed": len(command_results),
            "command_failure_count": len(command_failures),
            "artifact_failure_count": len(artifact_failures),
            "timed_out": timed_out,
            "include_list_files_written": len(written_include_lists),
            "readiness_reports_written": bool(execute and not failures),
            "expected_generated_output_count": sum(len(_planned_generated_paths(group)) for group in groups),
            "observed_generated_output_count": len(existing_after),
            "unexpected_generated_output_count": len(unexpected_tree_after),
            "generated_report_written": bool(execute and existing_after),
            "generated_output_count": len(existing_after),
            "staged_generated_path_count": max(
                int(plan_summary.get("staged_generated_path_count") or 0),
                len(post_execution_staged_paths),
            ),
            "post_execution_staged_generated_path_count": len(post_execution_staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": (
                "Inspect the generated readiness reports and rerun baseline readiness/resolver; do not run "
                "causal-base builds, labels, or features without separate approval."
                if status == STATUS_EXECUTED
                else "Approve or reject executing this bounded repaired-root readiness diagnostic wrapper."
            ),
            **approval_flags,
        },
        "checks": checks,
        "planned_commands": [
            {
                "year": group.get("year"),
                "markets": group.get("markets"),
                "raw_alignment_report": group.get("raw_alignment_report"),
                "argv": list(argv),
                "timeout_seconds": group.get("timeout_seconds"),
                "planned_generated_paths": _planned_generated_paths(group),
            }
            for group, argv in zip(groups, argv_by_group)
        ],
        "command_results": command_results,
        "written_include_lists": written_include_lists,
        "observed_generated_paths": existing_after,
        "diagnostic_plan_summary": plan_summary,
        "diagnostic_plan_checks": plan.get("checks", []),
        "non_approval": {
            "scope": "repaired-root readiness diagnostic execution wrapper only",
            **approval_flags,
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--proposal", default=str(plan_gate.DEFAULT_PROPOSAL))
    parser.add_argument("--diagnostic-reports-root", default=str(plan_gate.DEFAULT_DIAGNOSTIC_REPORTS_ROOT))
    parser.add_argument("--raw-root", default=plan_gate.DEFAULT_RAW_ROOT)
    parser.add_argument("--output-root", default=plan_gate.DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--raw-alignment-report", default=plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT)
    parser.add_argument(
        "--raw-alignment-report-for",
        action="append",
        default=[],
        help="Per-group override in profile:year=path format; repeat for multiple diagnostic groups.",
    )
    parser.add_argument("--expected-eligible-market-count", type=int, default=plan_gate.resolver_gate.DEFAULT_EXPECTED_ELIGIBLE_MARKETS)
    parser.add_argument(
        "--expected-proof-status-market-year-count",
        type=int,
        default=plan_gate.resolver_gate.DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
    )
    parser.add_argument("--execute", action="store_true", help="Write include lists and run approved readiness commands.")
    parser.add_argument("--approval-token", help="Required exact token when --execute is used.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    proposal_path = resolve_path(repo_root, args.proposal)
    reports_root = resolve_path(repo_root, args.diagnostic_reports_root)
    try:
        raw_alignment_report_overrides = plan_gate.parse_raw_alignment_report_overrides(
            args.raw_alignment_report_for
        )
        report = build_report(
            repo_root=repo_root,
            proposal_path=proposal_path,
            diagnostic_reports_root=reports_root,
            execute=args.execute,
            approval_token=args.approval_token,
            expected_eligible_market_count=args.expected_eligible_market_count,
            expected_proof_status_market_year_count=args.expected_proof_status_market_year_count,
            raw_root=str(args.raw_root),
            output_root=str(args.output_root),
            raw_alignment_report=str(args.raw_alignment_report),
            raw_alignment_report_overrides=raw_alignment_report_overrides,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"execute_requested={summary['execute_requested']} "
        f"commands_planned={summary['commands_planned']} "
        f"commands_executed={summary['commands_executed']} "
        f"command_failures={summary['command_failure_count']} "
        f"artifact_failures={summary['artifact_failure_count']} "
        f"unexpected_generated_outputs={summary['unexpected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"post_execution_staged_generated_paths={summary['post_execution_staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
