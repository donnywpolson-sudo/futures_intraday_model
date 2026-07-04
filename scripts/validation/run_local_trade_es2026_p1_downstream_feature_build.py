#!/usr/bin/env python3
"""Run the approved ES 2026 downstream Phase 4 feature build."""

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

from scripts.pipeline_gates import file_sha256  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_feature_gate as gate  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_feature_build_execution"
STATUS_DRY_RUN_READY = "DRY_RUN_READY_ES2026_P1_DOWNSTREAM_FEATURE_BUILD"
STATUS_EXECUTED = "EXECUTED_ES2026_P1_DOWNSTREAM_FEATURE_BUILD"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_FEATURE_BUILD_EXECUTION"
DECISION_DRY_RUN = "es2026_p1_downstream_feature_build_execution_dry_run_only"
DECISION_APPROVED = "human_approved_es2026_p1_downstream_feature_build_execution"
DECISION_BLOCKED = "es2026_p1_downstream_feature_build_execution_blocked"
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
        flags["feature_matrix_build_approved"] = True
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


def _read_json_list(path: Path) -> tuple[list[Any], str | None]:
    if not path.exists():
        return [], f"missing JSON list: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], f"unreadable JSON list: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, list):
        return [], f"JSON is not a list: {path.as_posix()}"
    return payload, None


def _validate_feature_audit_file(
    *,
    feature_audit_path: Path,
    feature_cols: list[Any],
) -> list[str]:
    audit_records, error = _read_json_list(feature_audit_path)
    if error is not None:
        return [error]
    failures: list[str] = []
    by_feature: dict[str, Mapping[str, Any]] = {}
    for record in audit_records:
        if not isinstance(record, Mapping):
            failures.append("feature_audit.json records must be objects")
            continue
        feature = record.get("feature")
        if not isinstance(feature, str):
            failures.append("feature_audit.json record missing feature")
            continue
        by_feature[feature] = record
    expected_features = [str(feature) for feature in feature_cols]
    missing_records = [feature for feature in expected_features if feature not in by_feature]
    extra_records = sorted(set(by_feature) - set(expected_features))
    if missing_records:
        failures.append(f"feature_audit.json missing records: {missing_records}")
    if extra_records:
        failures.append(f"feature_audit.json unexpected records: {extra_records}")
    return failures


def _report_scope_matches(report: Mapping[str, Any]) -> bool:
    if report.get("markets") == [TARGET_MARKET] and report.get("years") == [TARGET_YEAR]:
        return True
    selection = report.get("input_selection")
    if isinstance(selection, Mapping) and selection.get("selected_markets") == [
        TARGET_MARKET
    ] and selection.get("selected_years") == [TARGET_YEAR]:
        return True
    files = report.get("files")
    if isinstance(files, list) and len(files) == 1:
        row = files[0]
        if isinstance(row, Mapping):
            return row.get("market") == TARGET_MARKET and row.get("year") == TARGET_YEAR
    return False


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


def _matching_output_hash(manifest: Mapping[str, Any], output_path: Path, repo_root: Path) -> str | None:
    hash_map = manifest.get("output_file_hashes")
    if not isinstance(hash_map, Mapping):
        return None
    expected_rel = rel(output_path, repo_root)
    expected_abs = output_path.as_posix()
    for raw_path, raw_hash in hash_map.items():
        raw_text = str(raw_path).replace("\\", "/")
        if raw_text in {expected_rel, expected_abs}:
            return str(raw_hash)
        try:
            if resolve_path(repo_root, raw_text).resolve() == output_path.resolve():
                return str(raw_hash)
        except (OSError, ValueError):
            continue
    return None


def _expected_paths_from_gate(repo_root: Path, approval_gate: Mapping[str, Any]) -> list[Path]:
    values = approval_gate.get("expected_ignored_artifacts")
    if not isinstance(values, list):
        return []
    return [resolve_path(repo_root, str(value)) for value in values]


def _command_bound_failures(
    argv: Sequence[str],
    *,
    label_output_root: Path,
    feature_output_root: Path,
    feature_reports_root: Path,
    label_reports_root: Path,
    profile_config: Path,
    costs_config: Path,
    repo_root: Path,
) -> list[str]:
    failures: list[str] = []
    argv_set = set(argv)
    executable_tail = list(argv[1:3]) if argv and argv[0] == sys.executable else list(argv[:2])
    if executable_tail != ["-m", "scripts.phase4_features.build_baseline_features"]:
        failures.append("command does not invoke scripts.phase4_features.build_baseline_features")
    for flag in gate.FORBIDDEN_FEATURE_FLAGS:
        if flag in argv_set:
            failures.append(f"forbidden feature argument present: {flag}")
    expected_values = {
        "--profile": TARGET_PROFILE,
        "--input-root": rel(label_output_root, repo_root),
        "--output-root": rel(feature_output_root, repo_root),
        "--reports-root": rel(feature_reports_root, repo_root),
        "--costs-config": rel(costs_config, repo_root),
        "--profile-config": rel(profile_config, repo_root),
        "--label-manifest": rel(label_reports_root / "label_manifest.json", repo_root),
        "--markets": TARGET_MARKET,
        "--years": str(TARGET_YEAR),
    }
    for flag, expected in expected_values.items():
        observed = _arg_value(argv, flag)
        if observed != expected:
            failures.append(f"{flag}={observed!r} != {expected!r}")
    return failures


def _validate_registry_files(*, output_root: Path, repo_root: Path) -> list[str]:
    failures: list[str] = []
    feature_cols, error = _read_json_list(output_root / "feature_cols.json")
    if error is not None:
        failures.append(error)
    elif not feature_cols or any(not str(col).startswith("feature_") for col in feature_cols):
        failures.append("feature_cols.json must contain only feature_ columns")
    for name in ("target_cols.json", "metadata_cols.json", "excluded_cols.json"):
        _, error = _read_json_list(output_root / name)
        if error is not None:
            failures.append(error)
    if failures:
        return [failure.replace(repo_root.as_posix(), ".") for failure in failures]
    return failures


def _validate_feature_outputs(
    *,
    repo_root: Path,
    expected_paths: list[Path],
    label_output_root: Path,
    feature_output_root: Path,
    feature_reports_root: Path,
    label_reports_root: Path,
) -> list[str]:
    failures: list[str] = []
    for path in expected_paths:
        if not path.is_file() or path.stat().st_size <= 0:
            failures.append(f"missing or empty expected output: {rel(path, repo_root)}")

    manifest_path = feature_reports_root / "baseline_feature_manifest.json"
    report_path = feature_reports_root / "baseline_feature_report.json"
    feature_audit_path = feature_reports_root / "feature_audit.json"
    output_path = feature_output_root / TARGET_MARKET / f"{TARGET_YEAR}.parquet"
    manifest, manifest_error = _read_json_object(manifest_path)
    report, report_error = _read_json_object(report_path)
    feature_cols, feature_cols_error = _read_json_list(feature_output_root / "feature_cols.json")
    if manifest_error is not None:
        failures.append(manifest_error)
    if report_error is not None:
        failures.append(report_error)
    if feature_cols_error is not None:
        failures.append(feature_cols_error)
    failures.extend(_validate_registry_files(output_root=feature_output_root, repo_root=repo_root))
    failures.extend(
        _validate_feature_audit_file(
            feature_audit_path=feature_audit_path,
            feature_cols=feature_cols,
        )
    )
    if manifest_error is not None:
        return failures

    if manifest.get("status") not in {"PASS", "WARN"}:
        failures.append(f"feature manifest status is not PASS/WARN: {manifest.get('status')!r}")
    if manifest.get("profile") != TARGET_PROFILE:
        failures.append(f"feature manifest profile mismatch: {manifest.get('profile')!r}")
    if manifest.get("resolved_profile") != TARGET_PROFILE:
        failures.append(
            f"feature manifest resolved_profile mismatch: {manifest.get('resolved_profile')!r}"
        )
    if manifest.get("markets") != [TARGET_MARKET]:
        failures.append(f"feature manifest markets mismatch: {manifest.get('markets')!r}")
    if manifest.get("years") != [TARGET_YEAR]:
        failures.append(f"feature manifest years mismatch: {manifest.get('years')!r}")
    if not _path_matches(manifest.get("input_root"), label_output_root, repo_root):
        failures.append("feature manifest input_root mismatch")
    if not _path_matches(manifest.get("output_root"), feature_output_root, repo_root):
        failures.append("feature manifest output_root mismatch")
    if not _path_matches(manifest.get("reports_root"), feature_reports_root, repo_root):
        failures.append("feature manifest reports_root mismatch")
    if int(manifest.get("failure_count") or 0) != 0:
        failures.append("feature manifest failure_count is not 0")
    if manifest.get("failures") not in ([], None):
        failures.append("feature manifest failures are non-empty")
    if manifest.get("forbidden_feature_leakage_failures") not in ([], None):
        failures.append("feature manifest forbidden leakage failures are non-empty")
    if int(manifest.get("feature_count") or 0) <= 0:
        failures.append("feature manifest feature_count is not positive")

    selection = manifest.get("input_selection")
    if not isinstance(selection, Mapping):
        failures.append("feature manifest input_selection missing")
    else:
        expected_selection = {
            "selected_input_count": 1,
            "requested_markets": [TARGET_MARKET],
            "requested_years": [TARGET_YEAR],
            "selected_markets": [TARGET_MARKET],
            "selected_years": [TARGET_YEAR],
        }
        for key, expected in expected_selection.items():
            if selection.get(key) != expected:
                failures.append(f"feature manifest input_selection.{key} mismatch")

    label_gate = manifest.get("label_manifest_gate")
    if not isinstance(label_gate, Mapping):
        failures.append("feature manifest label_manifest_gate missing")
    else:
        if label_gate.get("status") != "PASS":
            failures.append(
                f"feature manifest label_manifest_gate.status is not PASS: {label_gate.get('status')!r}"
            )
        if not _path_matches(
            label_gate.get("manifest_path"),
            label_reports_root / "label_manifest.json",
            repo_root,
        ):
            failures.append("feature manifest label_manifest_gate.manifest_path mismatch")
        nested = label_gate.get("label_manifest_causal_base_manifest_gate")
        if isinstance(nested, Mapping) and nested.get("status") != "PASS":
            failures.append("feature manifest nested causal gate is not PASS")

    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 1:
        failures.append("feature manifest outputs must contain exactly one ES 2026 row")
    else:
        row = outputs[0]
        if not isinstance(row, Mapping):
            failures.append("feature manifest output row is not an object")
        else:
            if row.get("market") != TARGET_MARKET or row.get("year") != TARGET_YEAR:
                failures.append("feature manifest output row market/year mismatch")
            if row.get("status") not in {"PASS", "WARN"}:
                failures.append(f"feature output status is not PASS/WARN: {row.get('status')!r}")
            if int(row.get("failure_count") or 0) != 0:
                failures.append("feature output failure_count is not 0")
            if row.get("failures") not in ([], None):
                failures.append("feature output failures are non-empty")
            if not _path_matches(row.get("output_path"), output_path, repo_root):
                failures.append("feature output path mismatch")

    expected_hash = _matching_output_hash(manifest, output_path, repo_root)
    if expected_hash is None:
        failures.append("feature manifest output hash missing")
    elif output_path.exists() and file_sha256(output_path) != expected_hash:
        failures.append("feature manifest output hash stale")

    if report_error is None:
        if report.get("status") not in {"PASS", "WARN"}:
            failures.append(f"feature report status is not PASS/WARN: {report.get('status')!r}")
        if not _report_scope_matches(report):
            failures.append("feature report market/year scope mismatch")
    return failures


def _recommended_next(status: str, *, execute: bool) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 downstream feature build wrapper checks, then rerun this guarded wrapper."
    if execute:
        return (
            "Review generated ES 2026 feature evidence, then prepare a separate bounded WFA/modeling gate; "
            "do not run WFA or modeling without separate approval."
        )
    return (
        "Approve or leave pending this guarded ES 2026 Phase 4 feature wrapper; do not run features "
        "or modeling without explicit approval."
    )


def build_report(
    *,
    repo_root: Path,
    label_output_root: Path,
    label_reports_root: Path,
    feature_output_root: Path,
    feature_reports_root: Path,
    profile_config: Path,
    costs_config: Path,
    feature_script: Path,
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
            profile_config=profile_config,
            costs_config=costs_config,
            feature_script=feature_script,
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
            *_existing_tree_files(repo_root, feature_output_root, "data"),
            *_existing_tree_files(repo_root, feature_reports_root, "reports"),
        }
    )
    command_failures = (
        _command_bound_failures(
            argv,
            label_output_root=label_output_root,
            feature_output_root=feature_output_root,
            feature_reports_root=feature_reports_root,
            label_reports_root=label_reports_root,
            profile_config=profile_config,
            costs_config=costs_config,
            repo_root=repo_root,
        )
        if argv
        else ["missing exact feature command"]
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="downstream_feature_gate_ready",
        passed=gate_summary.get("status") == gate.STATUS_READY,
        observed=gate_summary.get("status"),
        expected=gate.STATUS_READY,
        detail="Execution must start from the console-only downstream feature approval gate.",
    )
    _check(
        checks,
        name="execution_approval_token_present_when_execute",
        passed=not execute or approval_token == APPROVAL_TOKEN,
        observed="provided" if approval_token else None,
        expected=f"{APPROVAL_TOKEN} when --execute is used",
        detail="Generated feature artifacts require explicit approval.",
    )
    _check(
        checks,
        name="bounded_phase4_feature_command_only",
        passed=not command_failures,
        observed=command_failures,
        expected="exact ES 2026 Phase 4 feature command from the approval gate",
        detail="Execution must remain bounded to ES 2026 candidate features.",
    )
    _check(
        checks,
        name="planned_outputs_under_data_or_reports",
        passed=bool(expected_paths)
        and all(
            _path_under(repo_root, path, "data") or _path_under(repo_root, path, "reports")
            for path in expected_paths
        ),
        observed=expected_rel_paths,
        expected="all expected outputs under data/ or reports/",
        detail="Feature artifacts must stay in generated artifact roots.",
    )
    _check(
        checks,
        name="planned_outputs_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="Feature outputs must be ignored generated artifacts before execution.",
    )
    _check(
        checks,
        name="planned_outputs_absent_before_execution",
        passed=not existing_expected_paths,
        observed=existing_expected_paths,
        expected=[],
        detail="The wrapper should not overwrite existing planned feature outputs.",
    )
    _check(
        checks,
        name="candidate_feature_roots_empty_before_execution",
        passed=not stale_root_files,
        observed=stale_root_files,
        expected=[],
        detail="Candidate feature output/report roots should not contain stale files.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths_before,
        observed=staged_paths_before,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged before feature execution.",
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
                    "name": "phase4_feature_build_exact_es2026_candidate",
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
                    "name": "phase4_feature_build_exact_es2026_candidate",
                    "returncode": result.returncode,
                    "timed_out": False,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "argv": list(argv),
                }
            )
        if command_results and command_results[-1].get("returncode") == 0:
            output_failures = _validate_feature_outputs(
                repo_root=repo_root,
                expected_paths=expected_paths,
                label_output_root=label_output_root,
                feature_output_root=feature_output_root,
                feature_reports_root=feature_reports_root,
                label_reports_root=label_reports_root,
            )
            expected_set = {rel(path, repo_root) for path in expected_paths}
            actual_files = sorted(
                {
                    *_existing_tree_files(repo_root, feature_output_root, "data"),
                    *_existing_tree_files(repo_root, feature_reports_root, "reports"),
                }
            )
            unexpected_outputs = sorted(path for path in actual_files if path not in expected_set)
            staged_paths_after = _git_staged_generated_paths(repo_root)
        _check(
            checks,
            name="phase4_feature_command_completed",
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
            expected="Phase 4 feature command returns 0 without timeout",
            detail="Stop on timeout, traceback, nonzero exit, label-manifest-gate failure, or cost/config failure.",
        )
        _check(
            checks,
            name="phase4_feature_outputs_valid",
            passed=not output_failures,
            observed=output_failures,
            expected="PASS/WARN feature manifest/report for exactly ES 2026 with zero failures",
            detail="Generated outputs must prove exact-scope ES 2026 feature construction.",
        )
        _check(
            checks,
            name="unexpected_feature_outputs_absent",
            passed=not unexpected_outputs,
            observed=unexpected_outputs,
            expected=[],
            detail="Execution may only create the planned ES 2026 feature artifacts.",
        )
        _check(
            checks,
            name="post_execution_staged_generated_artifacts_absent",
            passed=not staged_paths_after,
            observed=staged_paths_after,
            expected=[],
            detail="Generated data/** and reports/** artifacts must remain unstaged after feature execution.",
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
            "scope": "ES 2026 downstream Phase 4 feature build wrapper",
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
    parser.add_argument("--profile-config", default=str(gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--costs-config", default=str(gate.DEFAULT_COSTS_CONFIG))
    parser.add_argument("--feature-script", default=str(gate.DEFAULT_FEATURE_SCRIPT))
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
            profile_config=resolve_path(repo_root, args.profile_config),
            costs_config=resolve_path(repo_root, args.costs_config),
            feature_script=resolve_path(repo_root, args.feature_script),
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
