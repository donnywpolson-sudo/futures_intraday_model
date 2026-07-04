#!/usr/bin/env python3
"""Run the approved ES 2026 downstream Phase 5 WFA split build."""

from __future__ import annotations

import argparse
import csv
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

from scripts.validation import build_local_trade_es2026_p1_downstream_wfa_split_gate as gate  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_wfa_split_build_execution"
STATUS_DRY_RUN_READY = "DRY_RUN_READY_ES2026_P1_DOWNSTREAM_WFA_SPLIT_BUILD"
STATUS_EXECUTED = "EXECUTED_ES2026_P1_DOWNSTREAM_WFA_SPLIT_BUILD"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_WFA_SPLIT_BUILD_EXECUTION"
DECISION_DRY_RUN = "es2026_p1_downstream_wfa_split_build_execution_dry_run_only"
DECISION_APPROVED = "human_approved_es2026_p1_downstream_wfa_split_build_execution"
DECISION_BLOCKED = "es2026_p1_downstream_wfa_split_build_execution_blocked"
APPROVAL_TOKEN = gate.APPROVAL_TOKEN

TARGET_MARKET = gate.TARGET_MARKET
TARGET_YEAR = gate.TARGET_YEAR
TARGET_PROFILE = gate.TARGET_PROFILE
FALSE_APPROVAL_FLAGS = gate.FALSE_APPROVAL_FLAGS

CommandRunner = Callable[[Sequence[str], Path, int], subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return gate.rel(path, repo_root)


def _normalize(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _approval_flags(*, executed: bool) -> dict[str, bool]:
    flags = {flag: False for flag in FALSE_APPROVAL_FLAGS}
    if executed:
        flags["wfa_split_plan_approved"] = True
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


def _git_ignored_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
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


def _filter_ignored_paths(expected_paths: Iterable[str], ignored_paths: Iterable[str]) -> list[str]:
    ignored = {_normalize(path) for path in ignored_paths}
    return sorted(path for path in expected_paths if _normalize(path) in ignored)


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


def _read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing JSON: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"unreadable JSON: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"JSON is not an object: {path.as_posix()}"
    return payload, None


def _command_to_argv(command: str) -> list[str]:
    argv = shlex.split(command)
    if argv and argv[0] == "python":
        argv[0] = sys.executable
    return argv


def _arg_value(argv: Sequence[str], flag: str) -> str | None:
    try:
        index = list(argv).index(flag)
    except ValueError:
        return None
    value_index = index + 1
    return str(argv[value_index]) if value_index < len(argv) else None


def _path_matches(actual: object, expected: Path, repo_root: Path) -> bool:
    if actual is None:
        return False
    actual_text = str(actual).replace("\\", "/")
    expected_rel = rel(expected, repo_root).replace("\\", "/")
    if actual_text == expected_rel or actual_text == expected.as_posix():
        return True
    try:
        return resolve_path(repo_root, actual_text).resolve() == expected.resolve()
    except (OSError, ValueError):
        return False


def _expected_paths_from_gate(repo_root: Path, approval_gate: Mapping[str, Any]) -> list[Path]:
    values = approval_gate.get("expected_ignored_artifacts")
    if not isinstance(values, list):
        return []
    return [resolve_path(repo_root, str(value)) for value in values]


def _command_bound_failures(
    argv: Sequence[str],
    *,
    feature_output_root: Path,
    feature_reports_root: Path,
    wfa_reports_root: Path,
    profile_config: Path,
    models_config: Path,
    repo_root: Path,
) -> list[str]:
    failures: list[str] = []
    argv_set = set(argv)
    executable_tail = list(argv[1:3]) if argv and argv[0] == sys.executable else list(argv[:2])
    if executable_tail != ["-m", "scripts.phase5_wfa.build_wfa_splits"]:
        failures.append("command does not invoke scripts.phase5_wfa.build_wfa_splits")
    for flag in gate.FORBIDDEN_WFA_FLAGS:
        if flag in argv_set:
            failures.append(f"forbidden WFA argument present: {flag}")
    expected_values = {
        "--profile": TARGET_PROFILE,
        "--input-root": rel(feature_output_root, repo_root),
        "--reports-root": rel(wfa_reports_root, repo_root),
        "--profile-config": rel(profile_config, repo_root),
        "--models-config": rel(models_config, repo_root),
        "--feature-manifest": rel(
            feature_reports_root / "baseline_feature_manifest.json",
            repo_root,
        ),
        "--markets": TARGET_MARKET,
        "--years": str(TARGET_YEAR),
    }
    for flag, expected in expected_values.items():
        observed = _arg_value(argv, flag)
        if observed != expected:
            failures.append(f"{flag}={observed!r} != {expected!r}")
    return failures


def _validate_wfa_outputs(
    *,
    repo_root: Path,
    expected_paths: list[Path],
    feature_output_root: Path,
    feature_reports_root: Path,
    wfa_reports_root: Path,
) -> list[str]:
    failures: list[str] = []
    for path in expected_paths:
        if not path.is_file() or path.stat().st_size <= 0:
            failures.append(f"missing or empty expected output: {rel(path, repo_root)}")

    manifest_path = wfa_reports_root / "split_plan.json"
    csv_path = wfa_reports_root / "split_plan.csv"
    manifest, manifest_error = _read_json_object(manifest_path)
    if manifest_error is not None:
        failures.append(manifest_error)
        return failures

    if int(manifest.get("failure_count") or 0) != 0:
        failures.append("WFA split manifest failure_count is not 0")
    if manifest.get("failures") not in ([], None):
        failures.append("WFA split manifest failures are non-empty")
    if int(manifest.get("fold_count") or 0) <= 0:
        failures.append("WFA split manifest fold_count is not positive")
    if manifest.get("profile") != TARGET_PROFILE:
        failures.append(f"WFA split manifest profile mismatch: {manifest.get('profile')!r}")
    if manifest.get("resolved_profile") != TARGET_PROFILE:
        failures.append(
            f"WFA split manifest resolved_profile mismatch: {manifest.get('resolved_profile')!r}"
        )
    if manifest.get("markets") != [TARGET_MARKET]:
        failures.append(f"WFA split manifest markets mismatch: {manifest.get('markets')!r}")
    if manifest.get("years") != [TARGET_YEAR]:
        failures.append(f"WFA split manifest years mismatch: {manifest.get('years')!r}")
    if not _path_matches(manifest.get("input_root"), feature_output_root, repo_root):
        failures.append("WFA split manifest input_root mismatch")
    if not _path_matches(manifest.get("reports_root"), wfa_reports_root, repo_root):
        failures.append("WFA split manifest reports_root mismatch")
    if not _path_matches(manifest.get("output_root"), wfa_reports_root, repo_root):
        failures.append("WFA split manifest output_root mismatch")

    policy = manifest.get("purge_policy")
    if not isinstance(policy, Mapping):
        failures.append("WFA split manifest purge_policy missing")
    else:
        if int(policy.get("resolved_purge_bars") or 0) <= 0:
            failures.append("WFA split manifest resolved purge is not positive")
        if int(policy.get("embargo_bars") or 0) <= 0:
            failures.append("WFA split manifest embargo is not positive")

    final_holdout = manifest.get("final_holdout_policy")
    if not isinstance(final_holdout, Mapping):
        failures.append("WFA split manifest final_holdout_policy missing")
    else:
        if final_holdout.get("final_holdout_tuning_allowed") is not False:
            failures.append("WFA final-holdout tuning is not disabled")
        if final_holdout.get("final_holdout_excluded_from_selection") is not True:
            failures.append("WFA final-holdout exclusion is not enabled")

    feature_manifest_gate = manifest.get("feature_manifest_gate")
    if not isinstance(feature_manifest_gate, Mapping):
        failures.append("WFA split manifest feature_manifest_gate missing")
    else:
        if feature_manifest_gate.get("status") != "PASS":
            failures.append("WFA split manifest feature_manifest_gate.status is not PASS")
        if not _path_matches(
            feature_manifest_gate.get("manifest_path"),
            feature_reports_root / "baseline_feature_manifest.json",
            repo_root,
        ):
            failures.append("WFA split manifest feature_manifest_gate.manifest_path mismatch")
        if not _path_matches(
            feature_manifest_gate.get("expected_output_root"),
            feature_output_root,
            repo_root,
        ):
            failures.append("WFA split manifest feature_manifest_gate expected_output_root mismatch")

    fold_count_by_market = manifest.get("fold_count_by_market")
    if not isinstance(fold_count_by_market, Mapping) or set(fold_count_by_market) != {TARGET_MARKET}:
        failures.append("WFA split manifest fold_count_by_market must contain only ES")

    folds = manifest.get("folds")
    if not isinstance(folds, list) or not folds:
        failures.append("WFA split manifest folds missing")
    else:
        invalid_folds: list[str] = []
        for index, fold in enumerate(folds):
            if not isinstance(fold, Mapping):
                invalid_folds.append(f"fold {index} is not an object")
                continue
            if fold.get("market") != TARGET_MARKET:
                invalid_folds.append(f"fold {index} market mismatch")
            if int(fold.get("year") or 0) != TARGET_YEAR:
                invalid_folds.append(f"fold {index} year mismatch")
            if int(fold.get("train_rows_after_purge") or 0) <= 0:
                invalid_folds.append(f"fold {index} has no train rows after purge")
            if int(fold.get("test_rows") or 0) <= 0:
                invalid_folds.append(f"fold {index} has no test rows")
            if int(fold.get("resolved_purge_bars") or 0) <= 0:
                invalid_folds.append(f"fold {index} resolved purge is not positive")
            if fold.get("split_group") != "research":
                invalid_folds.append(f"fold {index} split_group is not research")
            if fold.get("selection_allowed") is not True:
                invalid_folds.append(f"fold {index} selection_allowed is not True")
        failures.extend(invalid_folds[:5])

    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                row_count = sum(1 for _ in csv.DictReader(handle))
        except Exception as exc:
            failures.append(f"unreadable WFA split CSV: {type(exc).__name__}: {exc}")
        else:
            if row_count != int(manifest.get("fold_count") or -1):
                failures.append("WFA split CSV row count does not match manifest fold_count")
    return failures


def _recommended_next(status: str, *, execute: bool) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 downstream WFA split wrapper checks, then rerun this guarded wrapper."
    if execute:
        return (
            "Review generated ES 2026 WFA split evidence; do not run model training, "
            "selection, metrics, predictions, or proof scans without separate approval."
        )
    return (
        "Approve or leave pending this guarded ES 2026 Phase 5 WFA split wrapper; "
        "do not run WFA/modeling without explicit approval."
    )


def build_report(
    *,
    repo_root: Path,
    label_output_root: Path,
    label_reports_root: Path,
    feature_output_root: Path,
    feature_reports_root: Path,
    wfa_reports_root: Path,
    profile_config: Path,
    models_config: Path,
    wfa_script: Path,
    execute: bool = False,
    approval_token: str | None = None,
    command_runner: CommandRunner = _default_command_runner,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
    gate_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    staged_paths_before = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    report = dict(
        gate_report
        if gate_report is not None
        else gate.build_report(
            repo_root=repo_root,
            label_output_root=label_output_root,
            label_reports_root=label_reports_root,
            feature_output_root=feature_output_root,
            feature_reports_root=feature_reports_root,
            wfa_reports_root=wfa_reports_root,
            profile_config=profile_config,
            models_config=models_config,
            wfa_script=wfa_script,
            generated_at_utc=generated_at_utc,
            staged_generated_paths=staged_paths_before,
            ignored_generated_paths=ignored_generated_paths,
        )
    )
    gate_summary = report.get("summary")
    gate_summary = gate_summary if isinstance(gate_summary, Mapping) else {}
    approval_gate = report.get("approval_gate")
    approval_gate = approval_gate if isinstance(approval_gate, Mapping) else {}
    exact_command = str(approval_gate.get("exact_command") or "")
    argv = _command_to_argv(exact_command) if exact_command else []
    expected_paths = _expected_paths_from_gate(repo_root, approval_gate)
    if not expected_paths:
        expected_paths = gate._expected_wfa_artifacts(reports_root=wfa_reports_root)
    expected_rel_paths = [rel(path, repo_root) for path in expected_paths]
    ignored_expected_paths = (
        _filter_ignored_paths(expected_rel_paths, ignored_generated_paths)
        if ignored_generated_paths is not None
        else _git_ignored_paths(repo_root, expected_rel_paths)
    )
    unignored_expected_paths = sorted(set(expected_rel_paths) - set(ignored_expected_paths))
    existing_expected_paths = sorted(rel(path, repo_root) for path in expected_paths if path.exists())
    stale_output_evidence = gate._stale_failed_wfa_artifact_evidence(
        repo_root=repo_root,
        reports_root=wfa_reports_root,
        expected_paths=expected_paths,
    )
    stale_root_files = _existing_tree_files(repo_root, wfa_reports_root, "reports")
    command_failures = (
        _command_bound_failures(
            argv,
            feature_output_root=feature_output_root,
            feature_reports_root=feature_reports_root,
            wfa_reports_root=wfa_reports_root,
            profile_config=profile_config,
            models_config=models_config,
            repo_root=repo_root,
        )
        if argv
        else ["missing exact WFA split command"]
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="downstream_wfa_split_gate_ready",
        passed=gate_summary.get("status") == gate.STATUS_READY,
        observed=gate_summary.get("status"),
        expected=gate.STATUS_READY,
        detail="Execution must start from the console-only downstream WFA split approval gate.",
    )
    _check(
        checks,
        name="execution_approval_token_present_when_execute",
        passed=not execute or approval_token == APPROVAL_TOKEN,
        observed="provided" if approval_token else None,
        expected=f"{APPROVAL_TOKEN} when --execute is used",
        detail="Generated WFA split artifacts require explicit approval.",
    )
    _check(
        checks,
        name="bounded_phase5_wfa_split_command_only",
        passed=not command_failures,
        observed=command_failures,
        expected="exact ES 2026 Phase 5 WFA split command from the approval gate",
        detail="Execution must remain bounded to ES 2026 candidate WFA splits.",
    )
    _check(
        checks,
        name="planned_outputs_under_reports",
        passed=bool(expected_paths) and all(_path_under(repo_root, path, "reports") for path in expected_paths),
        observed=expected_rel_paths,
        expected="all expected outputs under reports/",
        detail="WFA split artifacts must stay in generated report roots.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="WFA split outputs must be ignored generated artifacts before execution.",
    )
    _check(
        checks,
        name="planned_outputs_absent_or_stale_failed_before_execution",
        passed=not existing_expected_paths or stale_output_evidence.get("status") == "PASS",
        observed=stale_output_evidence,
        expected="no existing artifacts or known failed zero-fold ES 2026 split outputs only",
        detail=(
            "The wrapper should not overwrite usable planned WFA split outputs; only the "
            "known failed candidate split outputs may be replaced."
        ),
    )
    _check(
        checks,
        name="candidate_wfa_reports_root_empty_before_execution",
        passed=not stale_root_files or sorted(stale_root_files) == sorted(existing_expected_paths),
        observed=stale_root_files,
        expected="empty root or the known failed expected split artifacts only",
        detail="Candidate WFA reports root should not contain unrelated stale files.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths_before,
        observed=staged_paths_before,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged before WFA split execution.",
    )

    command_results: list[dict[str, Any]] = []
    output_failures: list[str] = []
    unexpected_outputs: list[str] = []
    staged_paths_after: list[str] = []
    failures = [check for check in checks if check["status"] == "FAIL"]
    if execute and not failures:
        timeout_seconds = int(approval_gate.get("timeout_seconds") or gate.DEFAULT_TIMEOUT_SECONDS)
        try:
            result = command_runner(argv, repo_root, timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            command_results.append(
                {
                    "name": "phase5_wfa_split_plan_exact_es2026_candidate",
                    "returncode": None,
                    "timed_out": True,
                    "stdout": exc.stdout,
                    "stderr": exc.stderr,
                    "argv": list(argv),
                }
            )
        else:
            command_results.append(
                {
                    "name": "phase5_wfa_split_plan_exact_es2026_candidate",
                    "returncode": result.returncode,
                    "timed_out": False,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "argv": list(argv),
                }
            )
        if command_results and command_results[-1].get("returncode") == 0:
            output_failures = _validate_wfa_outputs(
                repo_root=repo_root,
                expected_paths=expected_paths,
                feature_output_root=feature_output_root,
                feature_reports_root=feature_reports_root,
                wfa_reports_root=wfa_reports_root,
            )
            expected_set = {rel(path, repo_root) for path in expected_paths}
            actual_files = _existing_tree_files(repo_root, wfa_reports_root, "reports")
            unexpected_outputs = sorted(path for path in actual_files if path not in expected_set)
            staged_paths_after = _git_staged_generated_paths(repo_root)
        _check(
            checks,
            name="phase5_wfa_split_command_completed",
            passed=len(command_results) == 1
            and command_results[0].get("returncode") == 0
            and not command_results[0].get("timed_out"),
            observed=[
                {
                    "returncode": result.get("returncode"),
                    "timed_out": result.get("timed_out"),
                }
                for result in command_results
            ],
            expected="Phase 5 WFA split command returns 0 without timeout",
            detail="Stop on timeout, traceback, nonzero exit, feature-manifest-gate failure, or split failure.",
        )
        _check(
            checks,
            name="phase5_wfa_split_outputs_valid",
            passed=not output_failures,
            observed=output_failures,
            expected="PASS WFA split manifest/CSV for exactly ES 2026 with zero failures",
            detail="Generated outputs must prove exact-scope ES 2026 chronological split construction.",
        )
        _check(
            checks,
            name="unexpected_wfa_split_outputs_absent",
            passed=not unexpected_outputs,
            observed=unexpected_outputs,
            expected=[],
            detail="Execution may only create the planned ES 2026 WFA split artifacts.",
        )
        _check(
            checks,
            name="post_execution_staged_generated_artifacts_absent",
            passed=not staged_paths_after,
            observed=staged_paths_after,
            expected=[],
            detail="Generated data/** and reports/** artifacts must remain unstaged after WFA split execution.",
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
    executed = status == STATUS_EXECUTED
    generated_outputs = [rel(path, repo_root) for path in expected_paths if execute and path.exists()]
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": decision,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "profile": TARGET_PROFILE,
            "execute_requested": execute,
            "commands_planned": 1 if exact_command else 0,
            "commands_executed": len(command_results),
            "command_failure_count": sum(
                1
                for result in command_results
                if result.get("timed_out") or result.get("returncode") != 0
            ),
            "output_failure_count": len(output_failures),
            "expected_generated_output_count": len(expected_paths),
            "ignored_expected_generated_output_count": len(ignored_expected_paths),
            "unignored_expected_generated_output_count": len(unignored_expected_paths),
            "existing_expected_generated_output_count": len(existing_expected_paths),
            "generated_output_count": len(generated_outputs),
            "unexpected_generated_output_count": len(unexpected_outputs),
            "staged_generated_path_count": len(staged_paths_before),
            "post_execution_staged_generated_path_count": len(staged_paths_after),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status, execute=execute),
            **_approval_flags(executed=executed),
        },
        "checks": checks,
        "planned_command": {
            "command_family": approval_gate.get("command_family"),
            "command": exact_command,
            "timeout_seconds": approval_gate.get("timeout_seconds"),
            "expected_generated_artifacts": expected_rel_paths,
        },
        "command_results": command_results,
        "generated_outputs": generated_outputs,
        "unexpected_generated_outputs": unexpected_outputs,
        "gate_summary": dict(gate_summary),
        "gate_checks": report.get("checks", []),
        "non_approval": {
            "scope": "ES 2026 downstream Phase 5 WFA split build wrapper",
            "executes_only_with_approval_token": APPROVAL_TOKEN,
            **_approval_flags(executed=executed),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--label-output-root", default=str(gate.DEFAULT_LABEL_OUTPUT_ROOT))
    parser.add_argument("--label-reports-root", default=str(gate.DEFAULT_LABEL_REPORTS_ROOT))
    parser.add_argument("--feature-output-root", default=str(gate.DEFAULT_FEATURE_OUTPUT_ROOT))
    parser.add_argument("--feature-reports-root", default=str(gate.DEFAULT_FEATURE_REPORTS_ROOT))
    parser.add_argument("--wfa-reports-root", default=str(gate.DEFAULT_WFA_REPORTS_ROOT))
    parser.add_argument("--profile-config", default=str(gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--models-config", default=str(gate.DEFAULT_MODELS_CONFIG))
    parser.add_argument("--wfa-script", default=str(gate.DEFAULT_WFA_SCRIPT))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            label_output_root=resolve_path(repo_root, args.label_output_root),
            label_reports_root=resolve_path(repo_root, args.label_reports_root),
            feature_output_root=resolve_path(repo_root, args.feature_output_root),
            feature_reports_root=resolve_path(repo_root, args.feature_reports_root),
            wfa_reports_root=resolve_path(repo_root, args.wfa_reports_root),
            profile_config=resolve_path(repo_root, args.profile_config),
            models_config=resolve_path(repo_root, args.models_config),
            wfa_script=resolve_path(repo_root, args.wfa_script),
            execute=bool(args.execute),
            approval_token=args.approval_token,
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"commands_planned={summary['commands_planned']} "
        f"commands_executed={summary['commands_executed']} "
        f"command_failures={summary['command_failure_count']} "
        f"output_failures={summary['output_failure_count']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"ignored_expected_generated_outputs={summary['ignored_expected_generated_output_count']} "
        f"unignored_expected_generated_outputs={summary['unignored_expected_generated_output_count']} "
        f"existing_expected_generated_outputs={summary['existing_expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"unexpected_generated_outputs={summary['unexpected_generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"post_execution_staged_generated_paths={summary['post_execution_staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
