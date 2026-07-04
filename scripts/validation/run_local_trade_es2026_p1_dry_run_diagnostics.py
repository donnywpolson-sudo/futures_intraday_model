#!/usr/bin/env python3
"""Run the approved ES 2026 P1 optional status/statistics dry-run diagnostics."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_es2026_p1_repair_plan as plan_gate


STAGE = "local_trade_es2026_p1_dry_run_diagnostics"
STATUS_DRY_RUN_READY = "DRY_RUN_READY_ES2026_P1_DRY_RUN_DIAGNOSTICS"
STATUS_EXECUTED = "EXECUTED_ES2026_P1_DRY_RUN_DIAGNOSTICS"
STATUS_NO_GO = "NO_GO_ES2026_P1_DRY_RUN_DIAGNOSTICS"
DECISION_DRY_RUN = "es2026_p1_dry_run_diagnostics_execution_dry_run_only"
DECISION_APPROVED = "human_approved_es2026_p1_dry_run_diagnostics_execution"
DECISION_BLOCKED = "es2026_p1_dry_run_diagnostics_blocked"
APPROVAL_TOKEN = "APPROVE_ES2026_P1_OPTIONAL_DRY_RUN_DIAGNOSTICS_V1"

TARGET_MARKET = plan_gate.TARGET_MARKET
TARGET_YEAR = plan_gate.TARGET_YEAR
TARGET_START = plan_gate.TARGET_START
TARGET_END = plan_gate.TARGET_END
TARGET_SCHEMAS = ("statistics", "status")

FALSE_APPROVAL_FLAGS = (
    "provider_download_approved",
    "cost_estimate_approved",
    "candidate_raw_write_approved",
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

FORBIDDEN_ARG_FLAGS = {
    "--estimate-cost",
    "--zero-cost-only",
    "--zero-cost-start-search",
    "--overwrite",
    "--convert-existing",
    "--convert-parquet",
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


def _git_ignored_generated_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    candidates = sorted({str(path) for path in paths if str(path)})
    if not candidates:
        return []
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=repo_root,
        input=("\n".join(candidates) + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "git check-ignore failed")
    stdout = result.stdout.decode("utf-8", errors="replace")
    return sorted(line.strip() for line in stdout.splitlines() if line.strip())


def _is_under_reports(repo_root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to((repo_root / "reports").resolve())
    except ValueError:
        return False
    return True


def _existing_tree_files(repo_root: Path, root: Path) -> list[str]:
    if not _is_under_reports(repo_root, root) or not root.exists():
        return []
    if root.is_file():
        return [rel(root, repo_root)]
    return sorted(rel(path, repo_root) for path in root.rglob("*") if path.is_file())


def _arg_value(argv: Sequence[str], flag: str) -> str | None:
    try:
        index = list(argv).index(flag)
    except ValueError:
        return None
    value_index = index + 1
    return str(argv[value_index]) if value_index < len(argv) else None


def _command_to_argv(command: str) -> list[str]:
    argv = shlex.split(command)
    if argv and argv[0] == "python":
        argv[0] = sys.executable
    return argv


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


def _dry_run_families(plan_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    families: list[dict[str, Any]] = []
    for item in plan_report.get("plan_items", []):
        if not isinstance(item, Mapping):
            continue
        for family in item.get("command_families", []):
            if (
                isinstance(family, Mapping)
                and family.get("command_family") == "phase1a_download_dry_run_only"
            ):
                families.append(dict(family))
    return sorted(families, key=lambda family: str(family.get("name")))


def _schema_for_family(family: Mapping[str, Any]) -> str:
    maximum_scope = family.get("maximum_scope")
    schemas = maximum_scope.get("schemas") if isinstance(maximum_scope, Mapping) else None
    if isinstance(schemas, list) and len(schemas) == 1:
        return str(schemas[0])
    argv = _command_to_argv(str(family.get("command", "")))
    return str(_arg_value(argv, "--schema") or "")


def _family_expected_paths(repo_root: Path, family: Mapping[str, Any]) -> list[Path]:
    paths = family.get("expected_generated_artifacts")
    if not isinstance(paths, list):
        return []
    return [resolve_path(repo_root, str(path)) for path in paths]


def _normalize_artifact_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _argv_bound_failures(argv: Sequence[str], schema: str) -> list[str]:
    failures: list[str] = []
    argv_set = set(argv)
    for forbidden in sorted(FORBIDDEN_ARG_FLAGS):
        if forbidden in argv_set:
            failures.append(f"forbidden argument present: {forbidden}")
    expected_values = {
        "--universe": "custom",
        "--symbols": TARGET_MARKET,
        "--schema": schema,
        "--start": TARGET_START,
        "--end": TARGET_END,
        "--mode": "download-dbn",
        "--chunk": "year",
        "--workers": "1",
    }
    for flag, expected in expected_values.items():
        observed = _arg_value(argv, flag)
        if observed != expected:
            failures.append(f"{flag}={observed!r} != {expected!r}")
    if "--dry-run" not in argv_set:
        failures.append("--dry-run missing")
    if _arg_value(argv, "--plan-out") is None:
        failures.append("--plan-out missing")
    return failures


def _validate_plan_output(path: Path, schema: str) -> list[str]:
    failures: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unreadable dry-run plan: {path.as_posix()}: {type(exc).__name__}: {exc}"]
    if not isinstance(payload, dict):
        return [f"dry-run plan is not a JSON object: {path.as_posix()}"]
    expected = {
        "run_kind": "dry_run",
        "mode": "download-dbn",
        "schema": schema,
        "start": TARGET_START,
        "end": TARGET_END,
        "universe": "custom",
        "product_count": 1,
        "task_count": 1,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            failures.append(f"{key}={payload.get(key)!r} != {expected_value!r}")
    if payload.get("products") != [TARGET_MARKET]:
        failures.append(f"products={payload.get('products')!r} != ['{TARGET_MARKET}']")
    if payload.get("schemas") != [schema]:
        failures.append(f"schemas={payload.get('schemas')!r} != [{schema!r}]")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1:
        failures.append(f"tasks length={0 if not isinstance(tasks, list) else len(tasks)} != 1")
        return failures
    task = tasks[0]
    if not isinstance(task, Mapping):
        return [*failures, "task row is not a JSON object"]
    task_expected = {
        "product": TARGET_MARKET,
        "year": TARGET_YEAR,
        "schema": schema,
        "start": TARGET_START,
        "end": TARGET_END,
    }
    for key, expected_value in task_expected.items():
        if task.get(key) != expected_value:
            failures.append(f"task.{key}={task.get(key)!r} != {expected_value!r}")
    return failures


def _recommended_next(status: str) -> str:
    if status == STATUS_EXECUTED:
        return (
            "Inspect the two ES 2026 optional status/statistics dry-run plans and approve or reject "
            "the next bounded candidate raw/enrichment diagnostic step."
        )
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 dry-run diagnostic checks, then rerun this guarded wrapper."
    return (
        "Approve or reject executing this guarded ES 2026 P1 optional status/statistics dry-run "
        f"diagnostic wrapper with approval token {APPROVAL_TOKEN}."
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
    execute: bool = False,
    approval_token: str | None = None,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    runner = command_runner or _default_command_runner
    plan = plan_gate.build_report(
        repo_root=repo_root,
        work_order_report=work_order_report,
        drilldown_report=drilldown_report,
        checkpoint_jsonl=checkpoint_jsonl,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_generated_paths,
    )
    plan_summary = plan["summary"]
    families = _dry_run_families(plan)
    schemas = sorted(_schema_for_family(family) for family in families)
    planned_paths = sorted(
        {
            rel(path, repo_root)
            for family in families
            for path in _family_expected_paths(repo_root, family)
        }
    )
    existing_before = [path for path in planned_paths if (repo_root / path).exists()]
    existing_tree_before = _existing_tree_files(repo_root, repair_reports_root)
    staged_count = int(plan_summary.get("staged_generated_path_count") or 0)
    ignored_planned_paths = (
        sorted(
            path
            for path in planned_paths
            if _normalize_artifact_path(path)
            in {_normalize_artifact_path(ignored_path) for ignored_path in ignored_generated_paths}
        )
        if ignored_generated_paths is not None
        else _git_ignored_generated_paths(repo_root, planned_paths)
    )
    unignored_planned_paths = sorted(set(planned_paths) - set(ignored_planned_paths))
    argv_failures = [
        {"schema": schema, "failures": failures}
        for schema, family in zip(schemas, families)
        if (failures := _argv_bound_failures(_command_to_argv(str(family.get("command", ""))), schema))
    ]

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="repair_plan_ready",
        passed=plan_summary.get("status") == plan_gate.STATUS_READY,
        observed=plan_summary.get("status"),
        expected=plan_gate.STATUS_READY,
        detail="Dry-run diagnostics must start from a ready ES 2026 P1 repair plan.",
    )
    _check(
        checks,
        name="execution_approval_token_present_when_execute",
        passed=(not execute) or approval_token == APPROVAL_TOKEN,
        observed="provided" if approval_token else None,
        expected=f"{APPROVAL_TOKEN} when --execute is used",
        detail="Generated dry-run plan files require explicit approval.",
    )
    _check(
        checks,
        name="exact_status_statistics_families_present",
        passed=schemas == sorted(TARGET_SCHEMAS) and len(families) == 2,
        observed=schemas,
        expected=sorted(TARGET_SCHEMAS),
        detail="This wrapper may only execute the ES 2026 status/statistics dry-run plan commands.",
    )
    _check(
        checks,
        name="bounded_phase1a_dry_run_argv_only",
        passed=not argv_failures,
        observed=argv_failures,
        expected="only Phase 1A download-dbn --dry-run argv for ES 2026 status/statistics",
        detail="The wrapper must not run provider downloads, cost estimates, or data mutation paths.",
    )
    _check(
        checks,
        name="expected_outputs_under_reports",
        passed=all(_is_under_reports(repo_root, repo_root / path) for path in planned_paths),
        observed=planned_paths,
        expected="all outputs under reports/**",
        detail="Generated dry-run diagnostics must stay under reports/.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_planned_paths and len(ignored_planned_paths) == len(planned_paths),
        observed=unignored_planned_paths,
        expected=[],
        detail="Generated dry-run diagnostics must be ignored by git before execution is allowed.",
    )
    _check(
        checks,
        name="planned_outputs_absent_before_execution",
        passed=not existing_before,
        observed=existing_before,
        expected=[],
        detail="The wrapper should not overwrite existing dry-run plan files.",
    )
    _check(
        checks,
        name="repair_reports_root_empty_before_execution",
        passed=not existing_tree_before,
        observed=existing_tree_before,
        expected=[],
        detail="The wrapper should not mix new diagnostics with stale files under the repair reports root.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=staged_count == 0,
        observed=staged_count,
        expected=0,
        detail="Generated data/** and reports/** artifacts must not be staged before dry-run diagnostics.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    command_results: list[dict[str, Any]] = []
    if execute and not failures:
        for schema, family in zip(schemas, families):
            argv = _command_to_argv(str(family["command"]))
            try:
                result = runner(argv, repo_root, int(family["timeout_seconds"]))
            except subprocess.TimeoutExpired as exc:
                command_results.append(
                    {
                        "schema": schema,
                        "returncode": None,
                        "timed_out": True,
                        "timeout_seconds": family["timeout_seconds"],
                        "stdout": exc.stdout,
                        "stderr": exc.stderr,
                        "argv": argv,
                    }
                )
                break
            command_results.append(
                {
                    "schema": schema,
                    "returncode": result.returncode,
                    "timed_out": False,
                    "timeout_seconds": family["timeout_seconds"],
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "argv": argv,
                }
            )
            if result.returncode != 0:
                break

    command_failures = [
        result
        for result in command_results
        if result.get("timed_out") or result.get("returncode") != 0
    ]
    existing_after = [path for path in planned_paths if (repo_root / path).exists()]
    unexpected_after = [
        path for path in _existing_tree_files(repo_root, repair_reports_root) if path not in planned_paths
    ]
    output_failures: list[dict[str, Any]] = []
    if execute and not command_failures:
        for schema, family in zip(schemas, families):
            for path in _family_expected_paths(repo_root, family):
                failures_for_path = (
                    _validate_plan_output(path, schema)
                    if path.exists()
                    else [f"missing dry-run plan: {rel(path, repo_root)}"]
                )
                if failures_for_path:
                    output_failures.append(
                        {
                            "schema": schema,
                            "path": rel(path, repo_root),
                            "failures": failures_for_path,
                        }
                    )
    post_execution_staged_paths = _git_staged_generated_paths(repo_root) if command_results else []

    if command_failures:
        _check(
            checks,
            name="dry_run_commands_completed",
            passed=False,
            observed=[
                {
                    "schema": result.get("schema"),
                    "returncode": result.get("returncode"),
                    "timed_out": result.get("timed_out"),
                }
                for result in command_failures
            ],
            expected="both dry-run commands return 0 without timeout",
            detail="Stop after the first dry-run timeout or nonzero exit.",
        )
    if output_failures:
        _check(
            checks,
            name="dry_run_plan_outputs_valid",
            passed=False,
            observed=output_failures,
            expected="two readable ES 2026 status/statistics dry-run plan JSON files",
            detail="Generated dry-run plans must prove exact ES 2026 status/statistics scope.",
        )
    if unexpected_after:
        _check(
            checks,
            name="unexpected_generated_outputs_absent",
            passed=False,
            observed=unexpected_after,
            expected=[],
            detail="Execution may only create the two bounded dry-run plan files.",
        )
    if post_execution_staged_paths:
        _check(
            checks,
            name="post_execution_staged_generated_artifacts_absent",
            passed=False,
            observed=post_execution_staged_paths,
            expected=[],
            detail="Generated data/** and reports/** artifacts must remain unstaged after dry-run diagnostics.",
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

    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": decision,
            "input_plan_status": plan_summary.get("status"),
            "execute_requested": execute,
            "approval_token_required": APPROVAL_TOKEN if execute else None,
            "dry_run_diagnostics_approved": bool(execute and not failures),
            "commands_planned": len(families),
            "commands_executed": len(command_results),
            "command_failure_count": len(command_failures),
            "output_failure_count": len(output_failures),
            "expected_generated_output_count": len(planned_paths),
            "ignored_expected_generated_output_count": len(ignored_planned_paths),
            "unignored_expected_generated_output_count": len(unignored_planned_paths),
            "generated_output_count": len(existing_after),
            "unexpected_generated_output_count": len(unexpected_after),
            "generated_report_written": bool(execute and existing_after),
            "staged_generated_path_count": max(staged_count, len(post_execution_staged_paths)),
            "post_execution_staged_generated_path_count": len(post_execution_staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "planned_commands": [
            {
                "schema": schema,
                "argv": _command_to_argv(str(family["command"])),
                "timeout_seconds": family["timeout_seconds"],
                "expected_generated_artifacts": [
                    rel(path, repo_root) for path in _family_expected_paths(repo_root, family)
                ],
            }
            for schema, family in zip(schemas, families)
        ],
        "command_results": command_results,
        "observed_generated_paths": existing_after,
        "unexpected_generated_paths": unexpected_after,
        "repair_plan_summary": plan_summary,
        "repair_plan_checks": plan.get("checks", []),
        "non_approval": {
            "scope": "ES 2026 P1 optional status/statistics dry-run diagnostics only",
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-order-report", default=str(plan_gate.DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--drilldown-report", default=str(plan_gate.DEFAULT_DRILLDOWN_REPORT))
    parser.add_argument("--checkpoint-jsonl", default=str(plan_gate.DEFAULT_CHECKPOINT_JSONL))
    parser.add_argument("--repair-reports-root", default=str(plan_gate.DEFAULT_REPAIR_REPORTS_ROOT))
    parser.add_argument("--candidate-raw-root", default=str(plan_gate.DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--output-root", default=str(plan_gate.DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token")
    return parser


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
            execute=args.execute,
            approval_token=args.approval_token,
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
        f"output_failures={summary['output_failure_count']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"ignored_expected_generated_outputs={summary['ignored_expected_generated_output_count']} "
        f"unignored_expected_generated_outputs={summary['unignored_expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"unexpected_generated_outputs={summary['unexpected_generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
