#!/usr/bin/env python3
"""Run the approved ES 2026 P1 candidate raw conversion and audit."""

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

from scripts.validation import build_local_trade_es2026_p1_candidate_conversion_plan as plan_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_candidate_conversion_execution"
STATUS_DRY_RUN_READY = "DRY_RUN_READY_ES2026_P1_CANDIDATE_CONVERSION_EXECUTION"
STATUS_EXECUTED = "EXECUTED_ES2026_P1_CANDIDATE_CONVERSION"
STATUS_NO_GO = "NO_GO_ES2026_P1_CANDIDATE_CONVERSION_EXECUTION"
DECISION_DRY_RUN = "es2026_p1_candidate_conversion_execution_dry_run_only"
DECISION_APPROVED = "human_approved_es2026_p1_candidate_conversion_execution"
DECISION_BLOCKED = "es2026_p1_candidate_conversion_execution_blocked"
APPROVAL_TOKEN = "APPROVE_ES2026_P1_CANDIDATE_CONVERSION_V1"

TARGET_MARKET = plan_gate.TARGET_MARKET
TARGET_YEAR = plan_gate.TARGET_YEAR
REQUIRED_COMMAND_NAMES = plan_gate.REQUIRED_COMMAND_NAMES
FALSE_APPROVAL_FLAGS = plan_gate.FALSE_APPROVAL_FLAGS


CommandRunner = Callable[[Sequence[str], Path, int], subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return plan_gate.rel(path, repo_root)


def _normalize_artifact_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _filter_ignored_expected_paths(expected_paths: Iterable[str], ignored_paths: Iterable[str]) -> list[str]:
    ignored = {_normalize_artifact_path(path) for path in ignored_paths}
    return sorted(path for path in expected_paths if _normalize_artifact_path(path) in ignored)


def _approval_flags(*, executed: bool) -> dict[str, bool]:
    flags = {flag: False for flag in FALSE_APPROVAL_FLAGS}
    if executed:
        flags["statistics_enrichment_repair_execution_approved"] = True
        flags["candidate_raw_write_approved"] = True
        flags["data_mutation_performed"] = True
    return flags


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


def _path_under(repo_root: Path, path: Path, prefix: str) -> bool:
    try:
        path.resolve().relative_to((repo_root / prefix).resolve())
    except ValueError:
        return False
    return True


def _existing_tree_files(repo_root: Path, root: Path, prefix: str) -> list[str]:
    if not _path_under(repo_root, root, prefix) or not root.exists():
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


def _expected_paths(repo_root: Path, family: Mapping[str, Any]) -> list[Path]:
    paths = family.get("expected_generated_artifacts")
    if not isinstance(paths, list):
        return []
    return [resolve_path(repo_root, str(path)) for path in paths]


def _planned_paths(repo_root: Path, families: Iterable[Mapping[str, Any]]) -> list[Path]:
    paths: list[Path] = []
    for family in families:
        paths.extend(_expected_paths(repo_root, family))
    return sorted(paths, key=lambda path: path.as_posix())


def _ignored_generated_paths(repo_root: Path, paths: Iterable[Path]) -> list[str]:
    return plan_gate._ignored_generated_paths(repo_root, [rel(path, repo_root) for path in paths])  # noqa: SLF001


def _command_bound_failures(argv: Sequence[str], family: Mapping[str, Any]) -> list[str]:
    name = str(family.get("name"))
    failures: list[str] = []
    argv_set = set(argv)
    if "--estimate-cost" in argv_set or "--zero-cost-only" in argv_set:
        failures.append("provider cost-estimate flag present")
    if "--overwrite" in argv_set:
        failures.append("overwrite flag present")
    if name == "candidate_raw_convert_with_required_optional_enrichment":
        expected_values = {
            "--universe": "custom",
            "--symbols": TARGET_MARKET,
            "--schema": "ohlcv-1m",
            "--start": repair_plan_gate.TARGET_START,
            "--end": repair_plan_gate.TARGET_END,
            "--dbn-root": "data/dbn/ohlcv_1m",
            "--mode": "convert-parquet",
            "--chunk": "year",
            "--workers": "1",
            "--include-optional-schemas": "status,statistics",
            "--optional-schema-policy": "require",
            "--optional-dbn-root": "data/dbn",
        }
        for flag, expected in expected_values.items():
            observed = _arg_value(argv, flag)
            if observed != expected:
                failures.append(f"{flag}={observed!r} != {expected!r}")
        if "--offline-local-conditions" not in argv_set:
            failures.append("--offline-local-conditions missing")
        if "--dry-run" in argv_set:
            failures.append("--dry-run present on candidate conversion command")
    elif name == "candidate_raw_optional_schema_audit":
        if argv[:3] != [sys.executable, "-m", "scripts.validation.audit_enriched_raw_optional_schemas"]:
            failures.append("optional schema audit module mismatch")
        if _arg_value(argv, "--json-out") is None:
            failures.append("--json-out missing")
        if _arg_value(argv, "--md-out") is None:
            failures.append("--md-out missing")
    else:
        failures.append(f"unexpected command family: {name}")
    return failures


def _validate_expected_outputs(repo_root: Path, expected_paths: list[Path], candidate_raw_root: Path) -> list[str]:
    failures: list[str] = []
    for path in expected_paths:
        if not path.is_file() or path.stat().st_size <= 0:
            failures.append(f"missing or empty expected output: {rel(path, repo_root)}")
    parquet_path = candidate_raw_root / "ES" / "2026.parquet"
    if parquet_path not in expected_paths:
        failures.append("expected output list is missing candidate ES 2026 parquet")
    audit_json = next((path for path in expected_paths if path.name == "ES_2026_optional_schema_audit.json"), None)
    if audit_json is None or not audit_json.exists():
        failures.append("optional schema audit JSON missing")
        return failures
    try:
        audit_payload = json.loads(audit_json.read_text(encoding="utf-8"))
    except Exception as exc:
        failures.append(f"optional schema audit JSON unreadable: {type(exc).__name__}: {exc}")
        return failures
    if not isinstance(audit_payload, Mapping):
        failures.append("optional schema audit JSON is not an object")
        return failures
    if audit_payload.get("status") != "PASS":
        failures.append(f"optional schema audit status is not PASS: {audit_payload.get('status')!r}")
    if audit_payload.get("raw_root") != candidate_raw_root.as_posix():
        failures.append("optional schema audit raw_root mismatch")
    verdicts = audit_payload.get("verdicts")
    if not isinstance(verdicts, Mapping):
        failures.append("optional schema audit verdicts missing")
        return failures
    if verdicts.get("optional_status_readiness") != "PASS":
        failures.append("optional status readiness is not PASS")
    if verdicts.get("optional_statistics_readiness") != "PASS":
        failures.append("optional statistics readiness is not PASS")
    return failures


def _recommended_next(status: str, *, execute: bool) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 candidate conversion execution checks, then rerun this guarded wrapper."
    if execute:
        return (
            "Run the console-only ES 2026 candidate conversion review gate, then separately approve or "
            "reject candidate raw-alignment and readiness-only rerun planning."
        )
    return (
        "Approve or reject executing this guarded ES 2026 candidate conversion wrapper; do not rerun "
        "readiness, build causal data, labels, or features without separate approval."
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
    command_runner: CommandRunner = _default_command_runner,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths_before = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
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
        staged_generated_paths=staged_paths_before,
        ignored_generated_paths=ignored_generated_paths,
    )
    plan_summary = plan["summary"]
    families = [
        dict(family)
        for family in plan.get("command_families", [])
        if isinstance(family, Mapping)
    ]
    planned_paths = _planned_paths(repo_root, families)
    conversion_reports_root = repair_reports_root / "candidate_raw_conversion"
    audit_reports_root = repair_reports_root / "candidate_raw_optional_schema_audit"
    stale_candidate_files = _existing_tree_files(repo_root, candidate_raw_root, "data")
    stale_report_files = [
        *_existing_tree_files(repo_root, conversion_reports_root, "reports"),
        *_existing_tree_files(repo_root, audit_reports_root, "reports"),
    ]
    existing_planned_paths = [rel(path, repo_root) for path in planned_paths if path.exists()]
    planned_rel_paths = [rel(path, repo_root) for path in planned_paths]
    ignored_planned_paths = (
        _filter_ignored_expected_paths(planned_rel_paths, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _ignored_generated_paths(repo_root, planned_paths)
    )
    unignored_planned_paths = sorted(set(planned_rel_paths) - set(ignored_planned_paths))

    command_bound_failures: dict[str, list[str]] = {}
    for family in families:
        argv = _command_to_argv(str(family.get("command", "")))
        failures = _command_bound_failures(argv, family)
        if failures:
            command_bound_failures[str(family.get("name"))] = failures

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="candidate_conversion_plan_ready",
        passed=plan_summary.get("status") == plan_gate.STATUS_READY,
        observed=plan_summary.get("status"),
        expected=plan_gate.STATUS_READY,
        detail="Candidate conversion execution must start from a ready console-only plan.",
    )
    _check(
        checks,
        name="approval_token_required_for_execution",
        passed=not execute or approval_token == APPROVAL_TOKEN,
        observed="provided" if approval_token else "missing",
        expected=f"execute requires approval token {APPROVAL_TOKEN}",
        detail="Candidate raw writes require explicit approval.",
    )
    _check(
        checks,
        name="candidate_command_families_bounded",
        passed=not command_bound_failures and len(families) == len(REQUIRED_COMMAND_NAMES),
        observed=command_bound_failures,
        expected="bounded candidate conversion and optional schema audit commands only",
        detail="This wrapper may only execute the ES 2026 candidate conversion and optional schema audit commands.",
    )
    _check(
        checks,
        name="planned_outputs_under_data_or_reports",
        passed=all(
            _path_under(repo_root, path, "data") or _path_under(repo_root, path, "reports")
            for path in planned_paths
        ),
        observed=planned_rel_paths,
        expected="all expected outputs under data/ or reports/",
        detail="Candidate conversion outputs must stay in generated artifact roots.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_planned_paths and len(ignored_planned_paths) == len(planned_rel_paths),
        observed=unignored_planned_paths,
        expected=[],
        detail="Candidate conversion outputs must be ignored generated artifacts before execution.",
    )
    _check(
        checks,
        name="planned_outputs_absent_before_execution",
        passed=not existing_planned_paths,
        observed=existing_planned_paths,
        expected=[],
        detail="The wrapper should not overwrite existing planned outputs.",
    )
    _check(
        checks,
        name="candidate_raw_root_empty_before_execution",
        passed=not stale_candidate_files,
        observed=stale_candidate_files,
        expected=[],
        detail="Candidate raw conversion should start from an empty generated candidate root.",
    )
    _check(
        checks,
        name="candidate_report_roots_empty_before_execution",
        passed=not stale_report_files,
        observed=stale_report_files,
        expected=[],
        detail="Candidate conversion and optional schema audit report roots should not contain stale files.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths_before,
        observed=staged_paths_before,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged before candidate conversion.",
    )

    command_results: list[dict[str, Any]] = []
    output_failures: list[str] = []
    unexpected_generated_outputs: list[str] = []
    staged_paths_after: list[str] = []
    failures = [check for check in checks if check["status"] == "FAIL"]
    commands_executed = 0
    if execute and not failures:
        for family in families:
            argv = _command_to_argv(str(family.get("command", "")))
            timeout_seconds = int(family.get("timeout_seconds") or 900)
            try:
                result = command_runner(argv, repo_root, timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                command_results.append(
                    {
                        "name": family.get("name"),
                        "argv": argv,
                        "returncode": "TIMEOUT",
                        "stdout_tail": "",
                        "stderr_tail": str(exc),
                    }
                )
                break
            commands_executed += 1
            command_results.append(
                {
                    "name": family.get("name"),
                    "argv": argv,
                    "returncode": result.returncode,
                    "stdout_tail": (result.stdout or "")[-2000:],
                    "stderr_tail": (result.stderr or "")[-2000:],
                }
            )
            if result.returncode != 0:
                break
        output_failures = _validate_expected_outputs(repo_root, planned_paths, candidate_raw_root)
        expected_path_set = {rel(path, repo_root) for path in planned_paths}
        actual_generated = [
            *_existing_tree_files(repo_root, candidate_raw_root, "data"),
            *_existing_tree_files(repo_root, conversion_reports_root, "reports"),
            *_existing_tree_files(repo_root, audit_reports_root, "reports"),
        ]
        unexpected_generated_outputs = sorted(path for path in actual_generated if path not in expected_path_set)
        staged_paths_after = _git_staged_generated_paths(repo_root)
        _check(
            checks,
            name="candidate_commands_succeeded",
            passed=commands_executed == len(families)
            and all(result.get("returncode") == 0 for result in command_results),
            observed=[result.get("returncode") for result in command_results],
            expected="both candidate conversion commands return 0 without timeout",
            detail="Stop after the first candidate conversion timeout or nonzero exit.",
        )
        _check(
            checks,
            name="expected_generated_outputs_valid",
            passed=not output_failures,
            observed=output_failures,
            expected="candidate ES 2026 parquet plus PASS optional schema audit outputs",
            detail="Generated outputs must prove the candidate raw conversion and optional audit succeeded.",
        )
        _check(
            checks,
            name="unexpected_generated_outputs_absent",
            passed=not unexpected_generated_outputs,
            observed=unexpected_generated_outputs,
            expected=[],
            detail="Execution may only create the planned bounded candidate conversion outputs.",
        )
        _check(
            checks,
            name="post_execution_staged_generated_artifacts_absent",
            passed=not staged_paths_after,
            observed=staged_paths_after,
            expected=[],
            detail="Generated data/** and reports/** artifacts must remain unstaged after candidate conversion.",
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

    generated_outputs = [
        rel(path, repo_root) for path in planned_paths if execute and path.exists()
    ]
    executed = status == STATUS_EXECUTED
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": decision,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "execute_requested": execute,
            "commands_planned": len(families),
            "commands_executed": commands_executed,
            "command_failure_count": sum(
                1 for result in command_results if result.get("returncode") != 0
            ),
            "output_failure_count": len(output_failures),
            "expected_generated_output_count": len(planned_paths),
            "ignored_expected_generated_output_count": len(ignored_planned_paths),
            "unignored_expected_generated_output_count": len(unignored_planned_paths),
            "generated_output_count": len(generated_outputs),
            "unexpected_generated_output_count": len(unexpected_generated_outputs),
            "staged_generated_path_count": len(staged_paths_before),
            "post_execution_staged_generated_path_count": len(staged_paths_after),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status, execute=execute),
            **_approval_flags(executed=executed),
        },
        "checks": checks,
        "planned_commands": [
            {
                "name": family.get("name"),
                "command_family": family.get("command_family"),
                "command": family.get("command"),
                "timeout_seconds": family.get("timeout_seconds"),
                "expected_generated_artifacts": [
                    rel(path, repo_root) for path in _expected_paths(repo_root, family)
                ],
            }
            for family in families
        ],
        "command_results": command_results,
        "generated_outputs": generated_outputs,
        "unexpected_generated_outputs": unexpected_generated_outputs,
        "plan_summary": plan_summary,
        "plan_checks": plan.get("checks", []),
        "non_approval": {
            "scope": "ES 2026 P1 candidate conversion execution wrapper",
            "executes_only_with_approval_token": APPROVAL_TOKEN,
            **_approval_flags(executed=executed),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-order-report", default=str(repair_plan_gate.DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--drilldown-report", default=str(repair_plan_gate.DEFAULT_DRILLDOWN_REPORT))
    parser.add_argument("--checkpoint-jsonl", default=str(repair_plan_gate.DEFAULT_CHECKPOINT_JSONL))
    parser.add_argument("--repair-reports-root", default=str(repair_plan_gate.DEFAULT_REPAIR_REPORTS_ROOT))
    parser.add_argument("--candidate-raw-root", default=str(repair_plan_gate.DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--output-root", default=str(repair_plan_gate.DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(repair_plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT))
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
            execute=bool(args.execute),
            approval_token=args.approval_token,
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
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
        f"post_execution_staged_generated_paths={summary['post_execution_staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
