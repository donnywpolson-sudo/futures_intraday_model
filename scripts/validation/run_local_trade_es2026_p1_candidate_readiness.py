#!/usr/bin/env python3
"""Run the approved ES 2026 P1 candidate readiness diagnostics."""

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

from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_plan as plan_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_candidate_readiness_execution"
STATUS_DRY_RUN_READY = "DRY_RUN_READY_ES2026_P1_CANDIDATE_READINESS_EXECUTION"
STATUS_EXECUTED = "EXECUTED_ES2026_P1_CANDIDATE_READINESS"
STATUS_NO_GO = "NO_GO_ES2026_P1_CANDIDATE_READINESS_EXECUTION"
DECISION_DRY_RUN = "es2026_p1_candidate_readiness_execution_dry_run_only"
DECISION_APPROVED = "human_approved_es2026_p1_candidate_readiness_execution"
DECISION_BLOCKED = "es2026_p1_candidate_readiness_execution_blocked"
APPROVAL_TOKEN = "APPROVE_ES2026_P1_CANDIDATE_READINESS_V1"

TARGET_MARKET = plan_gate.TARGET_MARKET
TARGET_YEAR = plan_gate.TARGET_YEAR
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
        flags["readiness_rerun_approved"] = True
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


def _exact_include_payload() -> dict[str, list[dict[str, int | str]]]:
    return {"market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}]}


def _write_json_if_absent(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_pre_run_artifacts(repo_root: Path, family: Mapping[str, Any], argv: Sequence[str]) -> list[str]:
    written: list[str] = []
    artifacts = family.get("pre_run_artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                continue
            path_value = artifact.get("path")
            if not path_value:
                continue
            path = resolve_path(repo_root, str(path_value))
            _write_json_if_absent(path, artifact.get("content", _exact_include_payload()))
            written.append(rel(path, repo_root))
    include_value = _arg_value(argv, "--market-year-include-list")
    if include_value:
        path = resolve_path(repo_root, include_value)
        if rel(path, repo_root) not in written:
            _write_json_if_absent(path, _exact_include_payload())
            written.append(rel(path, repo_root))
    return written


def _argv_bound_failures(argv: Sequence[str], family: Mapping[str, Any], *, candidate_raw_root: Path, raw_alignment_report: Path) -> list[str]:
    name = str(family.get("name"))
    failures: list[str] = []
    argv_set = set(argv)
    forbidden_flags = {
        "--accepted-readiness-exceptions",
        "--allow-broad-build-after-readiness-pass",
        "--build-max-market-years",
        "--overwrite",
    }
    for flag in sorted(forbidden_flags):
        if flag in argv_set:
            failures.append(f"forbidden argument present: {flag}")
    if name == "candidate_raw_quality_drilldown":
        expected = {
            "--raw-root": candidate_raw_root.as_posix(),
            "--profile": repair_plan_gate.DEFAULT_PROFILE,
            "--markets": TARGET_MARKET,
            "--years": str(TARGET_YEAR),
            "--max-selected-market-years": "1",
        }
        for flag, value in expected.items():
            observed = _arg_value(argv, flag)
            if observed != value:
                failures.append(f"{flag}={observed!r} != {value!r}")
        if _arg_value(argv, "--json-out") is None:
            failures.append("--json-out missing")
    elif name == "candidate_raw_dbn_alignment_audit":
        expected = {
            "--profile": repair_plan_gate.DEFAULT_PROFILE,
            "--dbn-root": "data/dbn",
            "--raw-root": candidate_raw_root.as_posix(),
            "--json-out": raw_alignment_report.as_posix(),
            "--md-out": raw_alignment_report.with_suffix(".md").as_posix(),
        }
        for flag, value in expected.items():
            observed = _arg_value(argv, flag)
            if observed != value:
                failures.append(f"{flag}={observed!r} != {value!r}")
        if "--expected-only" not in argv_set:
            failures.append("--expected-only missing")
        if _arg_value(argv, "--market-year-include-list") is None:
            failures.append("--market-year-include-list missing")
    elif name == "candidate_readiness_only_rerun_after_repair":
        expected = {
            "--profile": repair_plan_gate.DEFAULT_PROFILE,
            "--raw-root": candidate_raw_root.as_posix(),
            "--raw-alignment-report": raw_alignment_report.as_posix(),
            "--readiness-max-market-years": "1",
            "--readiness-stop-after-blockers": "1",
        }
        for flag, value in expected.items():
            observed = _arg_value(argv, flag)
            if observed != value:
                failures.append(f"{flag}={observed!r} != {value!r}")
        required_flags = {
            "--readiness-only",
            "--market-year-include-list",
            "--readiness-json-out",
            "--readiness-md-out",
            "--readiness-checkpoint-jsonl",
            "--readiness-progress",
        }
        for flag in sorted(required_flags):
            if flag not in argv_set:
                failures.append(f"{flag} missing")
    else:
        failures.append(f"unexpected command family: {name}")
    return failures


def _read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing JSON: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive detail comes from runtime exception.
        return {}, f"unreadable JSON: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"JSON is not an object: {path.as_posix()}"
    return payload, None


def _include_failures(path: Path) -> list[str]:
    payload, error = _read_json_object(path)
    if error is not None:
        return [error]
    if payload != _exact_include_payload():
        return [f"include-list payload mismatch: {path.as_posix()}"]
    return []


def _validate_outputs(
    *,
    repo_root: Path,
    expected_paths: list[Path],
    candidate_raw_root: Path,
    raw_alignment_report: Path,
) -> list[str]:
    failures: list[str] = []
    for path in expected_paths:
        if not path.is_file() or path.stat().st_size <= 0:
            failures.append(f"missing or empty expected output: {rel(path, repo_root)}")
    for path in expected_paths:
        if path.name.startswith("include_ES_2026") and path.suffix == ".json":
            failures.extend(_include_failures(path))

    raw_quality_json = next((path for path in expected_paths if path.name == "ES_2026_candidate_raw_quality_drilldown.json"), None)
    if raw_quality_json is not None and raw_quality_json.exists():
        payload, error = _read_json_object(raw_quality_json)
        if error is not None:
            failures.append(error)
        elif payload.get("selected_market_year_count") not in (None, 1):
            failures.append("raw-quality drilldown selected_market_year_count is not 1")

    alignment_payload, alignment_error = _read_json_object(raw_alignment_report)
    if alignment_error is not None:
        failures.append(alignment_error)
    else:
        if alignment_payload.get("status") != "PASS":
            failures.append(f"candidate raw-alignment status is not PASS: {alignment_payload.get('status')!r}")
        observed_raw_root = str(alignment_payload.get("raw_root") or "").replace("\\", "/")
        expected_raw_roots = {
            candidate_raw_root.as_posix(),
            rel(candidate_raw_root, repo_root),
        }
        if observed_raw_root not in expected_raw_roots:
            failures.append("candidate raw-alignment raw_root mismatch")
        if alignment_payload.get("market_year_include_list_applied") is not True:
            failures.append("candidate raw-alignment include-list was not applied")

    readiness_json = next((path for path in expected_paths if path.name == "phase2_readiness_summary.json"), None)
    if readiness_json is not None and readiness_json.exists():
        payload, error = _read_json_object(readiness_json)
        if error is not None:
            failures.append(error)
        else:
            if payload.get("status") != "PASS":
                failures.append(f"candidate readiness status is not PASS: {payload.get('status')!r}")
            if payload.get("selected_market_year_count") != 1:
                failures.append(
                    "candidate readiness selected_market_year_count is not 1: "
                    f"{payload.get('selected_market_year_count')!r}"
                )
    return failures


def _recommended_next(status: str, *, execute: bool) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 candidate readiness execution checks, then rerun this guarded wrapper."
    if execute:
        return (
            "Run the console-only ES 2026 candidate readiness review gate; do not build causal data, "
            "labels, or features without separate approval."
        )
    return (
        "Approve or reject executing this guarded ES 2026 candidate readiness wrapper; do not build "
        "causal data, labels, or features without separate approval."
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
    families = [dict(family) for family in plan.get("command_families", []) if isinstance(family, Mapping)]
    planned_paths = _planned_paths(repo_root, families)
    planned_rel_paths = [rel(path, repo_root) for path in planned_paths]
    ignored_planned_paths = (
        _filter_ignored_expected_paths(planned_rel_paths, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _git_ignored_generated_paths(repo_root, planned_rel_paths)
    )
    unignored_planned_paths = sorted(set(planned_rel_paths) - set(ignored_planned_paths))
    existing_planned_paths = [rel(path, repo_root) for path in planned_paths if path.exists()]
    stale_alignment_files = _existing_tree_files(repo_root, repair_reports_root / "candidate_raw_alignment", "reports")
    stale_readiness_files = _existing_tree_files(repo_root, repair_reports_root / "candidate_readiness", "reports")

    argv_failures: dict[str, list[str]] = {}
    argv_by_family: list[list[str]] = []
    for family in families:
        argv = _command_to_argv(str(family.get("command", "")))
        argv_by_family.append(argv)
        failures = _argv_bound_failures(
            argv,
            family,
            candidate_raw_root=candidate_raw_root,
            raw_alignment_report=raw_alignment_report,
        )
        if failures:
            argv_failures[str(family.get("name"))] = failures

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="candidate_readiness_plan_ready",
        passed=plan_summary.get("status") == plan_gate.STATUS_READY,
        observed=plan_summary.get("status"),
        expected=plan_gate.STATUS_READY,
        detail="Candidate readiness execution must start from a ready console-only plan.",
    )
    _check(
        checks,
        name="execution_approval_token_present_when_execute",
        passed=not execute or approval_token == APPROVAL_TOKEN,
        observed="provided" if approval_token else None,
        expected=f"{APPROVAL_TOKEN} when --execute is used",
        detail="Generated candidate readiness artifacts require explicit approval.",
    )
    _check(
        checks,
        name="bounded_candidate_readiness_commands_only",
        passed=not argv_failures and len(families) == 3,
        observed=argv_failures,
        expected="bounded raw-quality drilldown, raw-alignment audit, and readiness-only rerun commands",
        detail="Execution must remain bounded to ES 2026 candidate diagnostics.",
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
        detail="Candidate readiness artifacts must stay in generated artifact roots.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_planned_paths and len(ignored_planned_paths) == len(planned_rel_paths),
        observed=unignored_planned_paths,
        expected=[],
        detail="Candidate readiness outputs must be ignored generated artifacts before execution.",
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
        name="candidate_diagnostic_roots_empty_before_execution",
        passed=not stale_alignment_files and not stale_readiness_files,
        observed=[*stale_alignment_files, *stale_readiness_files],
        expected=[],
        detail="Candidate raw-alignment and readiness report roots should not contain stale files.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths_before,
        observed=staged_paths_before,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged before candidate readiness.",
    )

    command_results: list[dict[str, Any]] = []
    written_pre_run_artifacts: list[str] = []
    output_failures: list[str] = []
    unexpected_outputs: list[str] = []
    staged_paths_after: list[str] = []
    failures = [check for check in checks if check["status"] == "FAIL"]
    if execute and not failures:
        for family, argv in zip(families, argv_by_family):
            written_pre_run_artifacts.extend(_write_pre_run_artifacts(repo_root, family, argv))
            timeout_seconds = int(family.get("timeout_seconds") or 900)
            try:
                result = command_runner(argv, repo_root, timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                command_results.append(
                    {
                        "name": family.get("name"),
                        "returncode": None,
                        "timed_out": True,
                        "stdout": exc.stdout,
                        "stderr": exc.stderr,
                        "argv": list(argv),
                    }
                )
                break
            command_results.append(
                {
                    "name": family.get("name"),
                    "returncode": result.returncode,
                    "timed_out": False,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "argv": list(argv),
                }
            )
            if result.returncode != 0:
                break
        output_failures = _validate_outputs(
            repo_root=repo_root,
            expected_paths=planned_paths,
            candidate_raw_root=candidate_raw_root,
            raw_alignment_report=raw_alignment_report,
        )
        expected_set = {rel(path, repo_root) for path in planned_paths}
        actual_files = sorted(
            {
                *[rel(path, repo_root) for path in planned_paths if path.exists()],
                *_existing_tree_files(repo_root, repair_reports_root / "candidate_raw_alignment", "reports"),
                *_existing_tree_files(repo_root, repair_reports_root / "candidate_readiness", "reports"),
            }
        )
        unexpected_outputs = sorted(path for path in actual_files if path not in expected_set)
        staged_paths_after = _git_staged_generated_paths(repo_root)
        _check(
            checks,
            name="candidate_readiness_commands_completed",
            passed=len(command_results) == len(families)
            and all(result.get("returncode") == 0 and not result.get("timed_out") for result in command_results),
            observed=[
                {"name": result.get("name"), "returncode": result.get("returncode"), "timed_out": result.get("timed_out")}
                for result in command_results
            ],
            expected="all candidate readiness commands return 0 without timeout",
            detail="Stop after the first timeout or nonzero exit.",
        )
        _check(
            checks,
            name="candidate_readiness_outputs_valid",
            passed=not output_failures,
            observed=output_failures,
            expected="exact include lists, PASS candidate raw-alignment, and PASS readiness summary",
            detail="Generated outputs must prove exact-scope candidate diagnostics and readiness PASS.",
        )
        _check(
            checks,
            name="unexpected_candidate_readiness_outputs_absent",
            passed=not unexpected_outputs,
            observed=unexpected_outputs,
            expected=[],
            detail="Execution may only create the planned candidate readiness artifacts.",
        )
        _check(
            checks,
            name="post_execution_staged_generated_artifacts_absent",
            passed=not staged_paths_after,
            observed=staged_paths_after,
            expected=[],
            detail="Generated data/** and reports/** artifacts must remain unstaged after candidate readiness.",
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
    generated_outputs = [rel(path, repo_root) for path in planned_paths if execute and path.exists()]
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
            "commands_executed": len(command_results),
            "command_failure_count": sum(
                1
                for result in command_results
                if result.get("timed_out") or result.get("returncode") != 0
            ),
            "output_failure_count": len(output_failures),
            "pre_run_artifacts_written": len(written_pre_run_artifacts),
            "expected_generated_output_count": len(planned_paths),
            "ignored_expected_generated_output_count": len(ignored_planned_paths),
            "unignored_expected_generated_output_count": len(unignored_planned_paths),
            "generated_output_count": len(generated_outputs),
            "unexpected_generated_output_count": len(unexpected_outputs),
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
        "written_pre_run_artifacts": written_pre_run_artifacts,
        "generated_outputs": generated_outputs,
        "unexpected_generated_outputs": unexpected_outputs,
        "plan_summary": plan_summary,
        "plan_checks": plan.get("checks", []),
        "non_approval": {
            "scope": "ES 2026 P1 candidate readiness execution wrapper",
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
