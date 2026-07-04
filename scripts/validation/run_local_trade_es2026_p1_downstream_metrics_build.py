#!/usr/bin/env python3
"""Run the approved ES 2026 downstream Phase 8 metrics/model-selection build."""

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

from scripts.validation import build_local_trade_es2026_p1_downstream_metrics_gate as gate  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_metrics_build_execution"
STATUS_DRY_RUN_READY = "DRY_RUN_READY_ES2026_P1_DOWNSTREAM_METRICS_BUILD"
STATUS_EXECUTED = "EXECUTED_ES2026_P1_DOWNSTREAM_METRICS_BUILD"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_METRICS_BUILD_EXECUTION"
DECISION_DRY_RUN = "es2026_p1_downstream_metrics_build_execution_dry_run_only"
DECISION_APPROVED = "human_approved_es2026_p1_downstream_metrics_build_execution"
DECISION_BLOCKED = "es2026_p1_downstream_metrics_build_execution_blocked"
APPROVAL_TOKEN = gate.APPROVAL_TOKEN

TARGET_MARKET = gate.TARGET_MARKET
TARGET_YEAR = gate.TARGET_YEAR
DEFAULT_PROFILE = gate.DEFAULT_PROFILE
DEFAULT_MATRIX = gate.DEFAULT_MATRIX
DEFAULT_RUN = gate.DEFAULT_RUN

CommandRunner = Callable[[Sequence[str], Path, int], subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return gate.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return gate.rel(path, repo_root)


def _approval_flags(*, executed: bool) -> dict[str, bool]:
    flags = {flag: False for flag in gate.FALSE_APPROVAL_FLAGS}
    if executed:
        flags["phase8_metrics_approved"] = True
        flags["model_selection_approved"] = True
        flags["model_promotion_approved"] = False
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
    gate._check(
        checks,
        name=name,
        passed=passed,
        observed=observed,
        expected=expected,
        detail=detail,
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
    return gate._git_staged_generated_paths(repo_root)


def _git_ignored_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    return gate._git_ignored_paths(repo_root, paths)


def _normalize(path: str | Path) -> str:
    return str(path).replace("\\", "/")


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
    run: str,
    predictions_path: Path,
    predictions_manifest: Path,
    costs_config: Path,
    models_config: Path,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
    repo_root: Path,
) -> list[str]:
    failures: list[str] = []
    argv_set = set(argv)
    executable_tail = list(argv[1:3]) if argv and argv[0] == sys.executable else list(argv[:2])
    if executable_tail != ["-m", "scripts.phase8_model_selection.evaluate_predictions"]:
        failures.append("command does not invoke scripts.phase8_model_selection.evaluate_predictions")
    for flag in gate.FORBIDDEN_PHASE8_COMMAND_FLAGS:
        if flag in argv_set:
            failures.append(f"forbidden Phase 8 command flag present: {flag}")
    expected_values = {
        "--predictions": rel(predictions_path, repo_root),
        "--predictions-manifest": rel(predictions_manifest, repo_root),
        "--costs-config": rel(costs_config, repo_root),
        "--models-config": rel(models_config, repo_root),
        "--metrics-root": rel(metrics_root, repo_root),
        "--model-selection-root": rel(model_selection_root, repo_root),
        "--phase8-root": rel(phase8_root, repo_root),
        "--run": run,
        **gate.DEFAULT_POLICY_ARGS,
    }
    for flag, expected in expected_values.items():
        observed = _arg_value(argv, flag)
        if observed != expected:
            failures.append(f"{flag}={observed!r} != {expected!r}")
    return failures


def _payload_failures(
    payload: Mapping[str, Any],
    *,
    label: str,
    run: str,
    predictions_path: Path,
    predictions_manifest: Path | None,
    costs_config: Path | None,
    models_config: Path | None,
    repo_root: Path,
) -> list[str]:
    failures: list[str] = []
    if payload.get("run") != run:
        failures.append(f"{label}: run={payload.get('run')!r} != {run!r}")
    if not _path_matches(payload.get("prediction_path"), predictions_path, repo_root):
        failures.append(f"{label}: prediction_path does not match exact ES 2026 predictions")
    if predictions_manifest is not None and not _path_matches(
        payload.get("predictions_manifest_path", payload.get("prediction_manifest_path")),
        predictions_manifest,
        repo_root,
    ):
        failures.append(f"{label}: predictions_manifest_path does not match exact ES 2026 manifest")
    if costs_config is not None and not _path_matches(payload.get("costs_config"), costs_config, repo_root):
        failures.append(f"{label}: costs_config does not match approval gate")
    if models_config is not None and not _path_matches(payload.get("models_config"), models_config, repo_root):
        failures.append(f"{label}: models_config does not match approval gate")
    if int(payload.get("failure_count") or 0) != 0:
        failures.append(f"{label}: failure_count is nonzero")
    if payload.get("failures") not in ([], None):
        failures.append(f"{label}: failures is nonempty")
    return failures


def _validate_metrics_outputs(
    *,
    repo_root: Path,
    expected_paths: Sequence[Path],
    run: str,
    predictions_path: Path,
    predictions_manifest: Path,
    costs_config: Path,
    models_config: Path,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
) -> list[str]:
    failures: list[str] = []
    for path in expected_paths:
        if not path.is_file():
            failures.append(f"missing expected Phase 8 output: {rel(path, repo_root)}")
        elif path.stat().st_size <= 0:
            failures.append(f"empty expected Phase 8 output: {rel(path, repo_root)}")

    metrics_json, error = _read_json_object(metrics_root / f"{run}_metrics.json")
    if error:
        failures.append(error)
    phase8_metrics, error = _read_json_object(phase8_root / "metrics.json")
    if error:
        failures.append(error)
    selection_report, error = _read_json_object(model_selection_root / "model_selection_report.json")
    if error:
        failures.append(error)
    calibration_report, error = _read_json_object(model_selection_root / "calibration_report.json")
    if error:
        failures.append(error)
    alpha_decision, error = _read_json_object(phase8_root / "alpha_promotion_decision.json")
    if error:
        failures.append(error)

    for label, payload in (
        ("metrics_json", metrics_json),
        ("phase8_metrics_json", phase8_metrics),
    ):
        failures.extend(
            _payload_failures(
                payload,
                label=label,
                run=run,
                predictions_path=predictions_path,
                predictions_manifest=predictions_manifest,
                costs_config=costs_config,
                models_config=models_config,
                repo_root=repo_root,
            )
        )
        expected_values = {
            "research_policy_metrics_ready": True,
            "final_holdout_touched": False,
            "trading_semantics_changed": False,
            "live_execution_ready": False,
        }
        for field, expected in expected_values.items():
            if payload.get(field) is not expected:
                failures.append(f"{label}: {field}={payload.get(field)!r} != {expected!r}")

    failures.extend(
        _payload_failures(
            selection_report,
            label="model_selection_report",
            run=run,
            predictions_path=predictions_path,
            predictions_manifest=predictions_manifest,
            costs_config=None,
            models_config=models_config,
            repo_root=repo_root,
        )
    )
    selection_expected = {
        "selection_status": "NOT_SELECTED_BASELINE_DIAGNOSTICS_ONLY",
        "selected_model_id": None,
        "final_holdout_excluded_from_selection": True,
        "live_execution_ready": False,
    }
    for field, expected in selection_expected.items():
        if selection_report.get(field) is not expected and selection_report.get(field) != expected:
            failures.append(f"model_selection_report: {field}={selection_report.get(field)!r} != {expected!r}")

    failures.extend(
        _payload_failures(
            calibration_report,
            label="calibration_report",
            run=run,
            predictions_path=predictions_path,
            predictions_manifest=None,
            costs_config=None,
            models_config=None,
            repo_root=repo_root,
        )
    )

    alpha_expected = {
        "final_holdout_touched": False,
        "used_final_holdout_for_tuning": False,
        "trading_semantics_changed": False,
    }
    if alpha_decision.get("run") != run:
        failures.append(f"alpha_promotion_decision: run={alpha_decision.get('run')!r} != {run!r}")
    if int(alpha_decision.get("failure_count") or 0) != 0:
        failures.append("alpha_promotion_decision: failure_count is nonzero")
    if alpha_decision.get("failures") not in ([], None):
        failures.append("alpha_promotion_decision: failures is nonempty")
    for field, expected in alpha_expected.items():
        if alpha_decision.get(field) is not expected:
            failures.append(f"alpha_promotion_decision: {field}={alpha_decision.get(field)!r} != {expected!r}")
    return failures


def _recommended_next(status: str, *, execute: bool) -> str:
    if status == STATUS_NO_GO:
        return (
            "Complete the missing upstream gate evidence and rerun this dry-run wrapper before "
            "requesting Phase 8 metrics execution approval."
        )
    if status == STATUS_EXECUTED:
        return (
            "Review the generated Phase 8 diagnostics; do not promote, freeze, tune, trade, "
            "or run proof scans without a separate bounded approval gate."
        )
    if execute:
        return (
            "Execution was requested but not performed; inspect failed checks and do not rerun "
            "without the exact approval token."
        )
    return (
        "Approve or leave pending this guarded ES 2026 Phase 8 metrics wrapper; "
        "do not promote, freeze, tune, proof-scan, or trade without separate approval."
    )


def build_report(
    *,
    repo_root: Path,
    profile: str,
    matrix: str,
    run: str,
    feature_output_root: Path,
    feature_reports_root: Path,
    wfa_split_reports_root: Path,
    predictions_root: Path,
    model_reports_root: Path,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
    profile_config: Path,
    models_config: Path,
    costs_config: Path,
    phase8_script: Path,
    max_folds: int = gate.DEFAULT_MAX_FOLDS,
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
            profile=profile,
            matrix=matrix,
            run=run,
            feature_output_root=feature_output_root,
            feature_reports_root=feature_reports_root,
            wfa_split_reports_root=wfa_split_reports_root,
            predictions_root=predictions_root,
            model_reports_root=model_reports_root,
            metrics_root=metrics_root,
            model_selection_root=model_selection_root,
            phase8_root=phase8_root,
            profile_config=profile_config,
            models_config=models_config,
            costs_config=costs_config,
            phase8_script=phase8_script,
            max_folds=max_folds,
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
        expected_paths = gate._expected_metrics_artifacts(
            metrics_root=metrics_root,
            model_selection_root=model_selection_root,
            phase8_root=phase8_root,
            run=run,
        )
    expected_rel_paths = [rel(path, repo_root) for path in expected_paths]
    ignored_expected_paths = (
        _filter_ignored_paths(expected_rel_paths, ignored_generated_paths)
        if ignored_generated_paths is not None
        else _git_ignored_paths(repo_root, expected_rel_paths)
    )
    unignored_expected_paths = sorted(set(expected_rel_paths) - set(ignored_expected_paths))
    existing_expected_paths = sorted(rel(path, repo_root) for path in expected_paths if path.exists())
    stale_root_files = sorted(
        {
            *_existing_tree_files(repo_root, metrics_root, "reports"),
            *_existing_tree_files(repo_root, model_selection_root, "reports"),
            *_existing_tree_files(repo_root, phase8_root, "reports"),
        }
    )
    predictions_path = predictions_root / run / "oos_predictions.parquet"
    predictions_manifest = model_reports_root / f"{run}_predictions_manifest.json"
    command_failures = (
        _command_bound_failures(
            argv,
            run=run,
            predictions_path=predictions_path,
            predictions_manifest=predictions_manifest,
            costs_config=costs_config,
            models_config=models_config,
            metrics_root=metrics_root,
            model_selection_root=model_selection_root,
            phase8_root=phase8_root,
            repo_root=repo_root,
        )
        if argv
        else ["missing exact Phase 8 metrics command"]
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="downstream_metrics_gate_ready",
        passed=gate_summary.get("status") == gate.STATUS_READY,
        observed=gate_summary.get("status"),
        expected=gate.STATUS_READY,
        detail="Execution must start from the console-only downstream metrics approval gate.",
    )
    _check(
        checks,
        name="execution_approval_token_present_when_execute",
        passed=not execute or approval_token == APPROVAL_TOKEN,
        observed="provided" if approval_token else None,
        expected=f"{APPROVAL_TOKEN} when --execute is used",
        detail="Generated metrics and model-selection artifacts require explicit approval.",
    )
    _check(
        checks,
        name="bounded_phase8_metrics_command_only",
        passed=not command_failures,
        observed=command_failures,
        expected="exact ES 2026 Phase 8 metrics/model-selection command from the approval gate",
        detail="Execution must remain bounded to ES 2026 candidate metrics/model-selection scope.",
    )
    _check(
        checks,
        name="planned_outputs_under_reports",
        passed=bool(expected_paths) and all(_path_under(repo_root, path, "reports") for path in expected_paths),
        observed=expected_rel_paths,
        expected="all expected outputs under reports/",
        detail="Phase 8 metrics artifacts must stay in generated report roots.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="Phase 8 outputs must be ignored generated artifacts before execution.",
    )
    _check(
        checks,
        name="planned_outputs_absent_before_execution",
        passed=not existing_expected_paths,
        observed=existing_expected_paths,
        expected=[],
        detail="The wrapper should not overwrite existing planned Phase 8 outputs.",
    )
    _check(
        checks,
        name="candidate_metrics_roots_empty_before_execution",
        passed=not stale_root_files,
        observed=stale_root_files,
        expected=[],
        detail="Candidate metrics/model-selection roots should not contain stale files.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths_before,
        observed=staged_paths_before,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged before metrics execution.",
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
                    "name": "phase8_metrics_model_selection_exact_es2026_candidate",
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
                    "name": "phase8_metrics_model_selection_exact_es2026_candidate",
                    "returncode": result.returncode,
                    "timed_out": False,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "argv": list(argv),
                }
            )
        if command_results and command_results[-1].get("returncode") == 0:
            output_failures = _validate_metrics_outputs(
                repo_root=repo_root,
                expected_paths=expected_paths,
                run=run,
                predictions_path=predictions_path,
                predictions_manifest=predictions_manifest,
                costs_config=costs_config,
                models_config=models_config,
                metrics_root=metrics_root,
                model_selection_root=model_selection_root,
                phase8_root=phase8_root,
            )
            expected_set = {rel(path, repo_root) for path in expected_paths}
            actual_files = sorted(
                {
                    *_existing_tree_files(repo_root, metrics_root, "reports"),
                    *_existing_tree_files(repo_root, model_selection_root, "reports"),
                    *_existing_tree_files(repo_root, phase8_root, "reports"),
                }
            )
            unexpected_outputs = sorted(path for path in actual_files if path not in expected_set)
            staged_paths_after = _git_staged_generated_paths(repo_root)
        _check(
            checks,
            name="phase8_metrics_command_completed",
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
            expected="Phase 8 metrics command returns 0 without timeout",
            detail="Stop on timeout, traceback, nonzero structural evaluation exit, or nonzero Phase 8 failure_count.",
        )
        _check(
            checks,
            name="phase8_metrics_outputs_valid",
            passed=not output_failures,
            observed=output_failures,
            expected="valid ES 2026 Phase 8 metrics/model-selection diagnostics without promotion approval",
            detail="Generated outputs must prove exact-scope ES 2026 metrics diagnostics only.",
        )
        _check(
            checks,
            name="unexpected_phase8_outputs_absent",
            passed=not unexpected_outputs,
            observed=unexpected_outputs,
            expected=[],
            detail="Execution may only create the planned ES 2026 metrics/model-selection artifacts.",
        )
        _check(
            checks,
            name="post_execution_staged_generated_artifacts_absent",
            passed=not staged_paths_after,
            observed=staged_paths_after,
            expected=[],
            detail="Generated data/** and reports/** artifacts must remain unstaged after metrics execution.",
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
            "profile": profile,
            "matrix": matrix,
            "run": run,
            "execute_requested": execute,
            "commands_planned": 1 if exact_command else 0,
            "commands_executed": len(command_results),
            "command_failure_count": sum(
                1
                for result in command_results
                if result.get("timed_out") or result.get("returncode") != 0
            ),
            "output_failure_count": len(output_failures),
            "model_output_status": gate_summary.get("model_output_status"),
            "phase8_config_status": gate_summary.get("phase8_config_status"),
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
            "scope": "ES 2026 downstream Phase 8 metrics/model-selection wrapper",
            "executes_only_with_approval_token": APPROVAL_TOKEN,
            **_approval_flags(executed=executed),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--matrix", default=DEFAULT_MATRIX)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--feature-output-root", default=str(gate.DEFAULT_FEATURE_OUTPUT_ROOT))
    parser.add_argument("--feature-reports-root", default=str(gate.DEFAULT_FEATURE_REPORTS_ROOT))
    parser.add_argument("--wfa-split-reports-root", default=str(gate.DEFAULT_WFA_SPLIT_REPORTS_ROOT))
    parser.add_argument("--predictions-root", default=str(gate.DEFAULT_PREDICTIONS_ROOT))
    parser.add_argument("--model-reports-root", default=str(gate.DEFAULT_MODEL_REPORTS_ROOT))
    parser.add_argument("--metrics-root", default=str(gate.DEFAULT_METRICS_ROOT))
    parser.add_argument("--model-selection-root", default=str(gate.DEFAULT_MODEL_SELECTION_ROOT))
    parser.add_argument("--phase8-root", default=str(gate.DEFAULT_PHASE8_ROOT))
    parser.add_argument("--profile-config", default=str(gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--models-config", default=str(gate.DEFAULT_MODELS_CONFIG))
    parser.add_argument("--costs-config", default=str(gate.DEFAULT_COSTS_CONFIG))
    parser.add_argument("--phase8-script", default=str(gate.DEFAULT_PHASE8_SCRIPT))
    parser.add_argument("--max-folds", type=int, default=gate.DEFAULT_MAX_FOLDS)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            profile=args.profile,
            matrix=args.matrix,
            run=args.run,
            feature_output_root=resolve_path(repo_root, args.feature_output_root),
            feature_reports_root=resolve_path(repo_root, args.feature_reports_root),
            wfa_split_reports_root=resolve_path(repo_root, args.wfa_split_reports_root),
            predictions_root=resolve_path(repo_root, args.predictions_root),
            model_reports_root=resolve_path(repo_root, args.model_reports_root),
            metrics_root=resolve_path(repo_root, args.metrics_root),
            model_selection_root=resolve_path(repo_root, args.model_selection_root),
            phase8_root=resolve_path(repo_root, args.phase8_root),
            profile_config=resolve_path(repo_root, args.profile_config),
            models_config=resolve_path(repo_root, args.models_config),
            costs_config=resolve_path(repo_root, args.costs_config),
            phase8_script=resolve_path(repo_root, args.phase8_script),
            max_folds=int(args.max_folds),
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
