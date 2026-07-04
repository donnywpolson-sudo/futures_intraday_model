#!/usr/bin/env python3
"""Build a console-only downstream Phase 4 feature approval gate for ES 2026."""

from __future__ import annotations

import argparse
import ast
import json
import shlex
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_gates import file_sha256  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_label_gate as label_gate  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_label_build as label_runner  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_feature_gate"
STATUS_READY = "REVIEW_READY_ES2026_P1_DOWNSTREAM_FEATURE_GATE"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_FEATURE_GATE"
DECISION_GATE_ONLY = "es2026_p1_downstream_feature_gate_only_no_execution"
DECISION_BLOCKED = "es2026_p1_downstream_feature_gate_blocked"
APPROVAL_TOKEN = "APPROVE_ES2026_P1_PHASE4_FEATURE_BUILD_V1"

TARGET_MARKET = label_gate.TARGET_MARKET
TARGET_YEAR = label_gate.TARGET_YEAR
TARGET_PROFILE = label_gate.TARGET_PROFILE
DEFAULT_LABEL_OUTPUT_ROOT = label_gate.DEFAULT_LABEL_OUTPUT_ROOT
DEFAULT_LABEL_REPORTS_ROOT = label_gate.DEFAULT_LABEL_REPORTS_ROOT
DEFAULT_FEATURE_OUTPUT_ROOT = Path("data/feature_matrices/local_trade_es2026_p1_candidate")
DEFAULT_FEATURE_REPORTS_ROOT = Path("reports/features_baseline/local_trade_es2026_p1_candidate")
DEFAULT_PROFILE_CONFIG = label_gate.DEFAULT_PROFILE_CONFIG
DEFAULT_COSTS_CONFIG = label_gate.DEFAULT_COSTS_CONFIG
DEFAULT_FEATURE_SCRIPT = Path("scripts/phase4_features/build_baseline_features.py")
DEFAULT_TIMEOUT_SECONDS = 900
FALSE_APPROVAL_FLAGS = label_gate.FALSE_APPROVAL_FLAGS + (
    "label_build_approved",
    "feature_matrix_build_approved",
)
REQUIRED_FEATURE_FLAGS = {
    "--profile",
    "--input-root",
    "--output-root",
    "--reports-root",
    "--costs-config",
    "--profile-config",
    "--label-manifest",
    "--markets",
    "--years",
}
FORBIDDEN_FEATURE_FLAGS = {
    "--shard-count",
    "--shard-index",
}
FORBIDDEN_ACTIONS = (
    "phase4_feature_execution_without_approval",
    "wfa_or_modeling",
    "metrics_or_predictions",
    "proof_scan",
    "provider_download_or_cost_diagnostic",
    "canonical_data_mutation",
    "candidate_raw_rewrite",
    "causal_base_build_or_rerun",
    "label_build_or_rerun",
    "staging_commit_push",
    "live_or_paper_execution",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return label_gate.rel(path, repo_root)


def command_path(path: Path, repo_root: Path) -> Path:
    return Path(rel(path, repo_root))


def _normalize(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


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


def _summary_int(summary: Mapping[str, Any], key: str) -> int:
    try:
        return int(summary.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _failed_check_names(report: Mapping[str, Any]) -> set[str]:
    checks = report.get("checks")
    if not isinstance(checks, list):
        return set()
    return {
        str(check.get("name"))
        for check in checks
        if isinstance(check, Mapping) and check.get("status") == "FAIL" and check.get("name")
    }


def _check_observed_paths(report: Mapping[str, Any], name: str) -> set[str]:
    checks = report.get("checks")
    if not isinstance(checks, list):
        return set()
    for check in checks:
        if not isinstance(check, Mapping) or check.get("name") != name:
            continue
        observed = check.get("observed")
        if not isinstance(observed, list):
            return set()
        return {_normalize(str(path)) for path in observed}
    return set()


def _label_wrapper_expected_artifacts(report: Mapping[str, Any]) -> set[str]:
    planned_command = report.get("planned_command")
    if not isinstance(planned_command, Mapping):
        return set()
    paths = planned_command.get("expected_generated_artifacts")
    if not isinstance(paths, list):
        return set()
    return {_normalize(str(path)) for path in paths}


def _label_manifest_is_exact_pass(label_manifest: Mapping[str, Any]) -> bool:
    return label_manifest.get("status") == "PASS" and label_manifest.get("manifest_status") == "PASS"


def _label_wrapper_supports_feature_gate(
    *,
    label_runner_result: Mapping[str, Any],
    label_runner_summary: Mapping[str, Any],
    label_manifest: Mapping[str, Any],
) -> bool:
    status = label_runner_summary.get("status")
    if status == label_runner.STATUS_DRY_RUN_READY:
        return True
    if status == label_runner.STATUS_EXECUTED:
        return (
            _summary_int(label_runner_summary, "command_failure_count") == 0
            and _summary_int(label_runner_summary, "output_failure_count") == 0
            and _summary_int(label_runner_summary, "post_execution_staged_generated_path_count") == 0
        )
    if not _label_manifest_is_exact_pass(label_manifest):
        return False

    allowed_failures = {
        "planned_outputs_absent_before_execution",
        "candidate_label_roots_empty_before_execution",
    }
    failed_checks = _failed_check_names(label_runner_result)
    if not failed_checks or not failed_checks <= allowed_failures:
        return False

    expected_artifacts = _label_wrapper_expected_artifacts(label_runner_result)
    existing_artifacts = _check_observed_paths(
        label_runner_result,
        "planned_outputs_absent_before_execution",
    )
    stale_artifacts = _check_observed_paths(
        label_runner_result,
        "candidate_label_roots_empty_before_execution",
    )
    return (
        bool(expected_artifacts)
        and existing_artifacts == expected_artifacts
        and stale_artifacts <= expected_artifacts
        and _summary_int(label_runner_summary, "expected_generated_output_count")
        == len(expected_artifacts)
        and _summary_int(label_runner_summary, "ignored_expected_generated_output_count")
        == len(expected_artifacts)
        and _summary_int(label_runner_summary, "unignored_expected_generated_output_count") == 0
        and _summary_int(label_runner_summary, "existing_expected_generated_output_count")
        == len(expected_artifacts)
        and _summary_int(label_runner_summary, "staged_generated_path_count") == 0
        and _summary_int(label_runner_summary, "post_execution_staged_generated_path_count") == 0
    )


def _read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing JSON report: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"unreadable JSON report {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"JSON report must be an object: {path.as_posix()}"
    return payload, None


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


def _declared_cli_flags(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    flags: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "add_argument":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("--"):
                flags.add(arg.value)
    return flags


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


def _expected_feature_artifacts(*, output_root: Path, reports_root: Path) -> list[str]:
    return sorted(
        {
            (output_root / TARGET_MARKET / f"{TARGET_YEAR}.parquet").as_posix(),
            (output_root / "feature_cols.json").as_posix(),
            (output_root / "target_cols.json").as_posix(),
            (output_root / "metadata_cols.json").as_posix(),
            (output_root / "excluded_cols.json").as_posix(),
            (reports_root / "feature_registry.json").as_posix(),
            (reports_root / "feature_audit.json").as_posix(),
            (reports_root / "feature_correlation_report.csv").as_posix(),
            (reports_root / "baseline_feature_manifest.json").as_posix(),
            (reports_root / "baseline_feature_report.json").as_posix(),
        }
    )


def _feature_command(
    *,
    input_root: Path,
    output_root: Path,
    reports_root: Path,
    label_manifest: Path,
    profile_config: Path,
    costs_config: Path,
) -> str:
    return (
        "python -m scripts.phase4_features.build_baseline_features "
        f"--profile {TARGET_PROFILE} "
        f"--input-root {input_root.as_posix()} "
        f"--output-root {output_root.as_posix()} "
        f"--reports-root {reports_root.as_posix()} "
        f"--costs-config {costs_config.as_posix()} "
        f"--profile-config {profile_config.as_posix()} "
        f"--label-manifest {label_manifest.as_posix()} "
        f"--markets {TARGET_MARKET} "
        f"--years {TARGET_YEAR}"
    )


def _command_failures(
    command: str,
    *,
    input_root: Path,
    output_root: Path,
    reports_root: Path,
    label_manifest: Path,
    profile_config: Path,
    costs_config: Path,
) -> list[str]:
    failures: list[str] = []
    argv = shlex.split(command)
    argv_set = set(argv)
    if argv[:3] != ["python", "-m", "scripts.phase4_features.build_baseline_features"]:
        failures.append("command does not invoke Phase 4 baseline features")
    for flag in FORBIDDEN_FEATURE_FLAGS:
        if flag in argv_set:
            failures.append(f"forbidden feature argument present: {flag}")
    expected = {
        "--profile": TARGET_PROFILE,
        "--input-root": input_root.as_posix(),
        "--output-root": output_root.as_posix(),
        "--reports-root": reports_root.as_posix(),
        "--costs-config": costs_config.as_posix(),
        "--profile-config": profile_config.as_posix(),
        "--label-manifest": label_manifest.as_posix(),
        "--markets": TARGET_MARKET,
        "--years": str(TARGET_YEAR),
    }
    for flag, value in expected.items():
        try:
            observed = argv[argv.index(flag) + 1]
        except (ValueError, IndexError):
            failures.append(f"{flag} missing")
            continue
        if observed != value:
            failures.append(f"{flag}={observed!r} != {value!r}")
    return failures


def _label_manifest_evidence(
    *,
    repo_root: Path,
    manifest_path: Path,
    label_output_root: Path,
) -> dict[str, Any]:
    manifest, error = _read_json_object(manifest_path)
    if error or manifest is None:
        return {"status": "FAIL", "error": error, "path": rel(manifest_path, repo_root)}
    output_path = label_output_root / TARGET_MARKET / f"{TARGET_YEAR}.parquet"
    output_hash = _matching_output_hash(manifest, output_path, repo_root)
    actual_hash = file_sha256(output_path) if output_path.exists() else None
    outputs = manifest.get("outputs")
    first_output = outputs[0] if isinstance(outputs, list) and outputs and isinstance(outputs[0], Mapping) else {}
    input_selection = manifest.get("input_selection")
    input_selection = input_selection if isinstance(input_selection, Mapping) else {}
    causal_gate = manifest.get("causal_base_manifest_gate")
    causal_gate = causal_gate if isinstance(causal_gate, Mapping) else {}
    return {
        "status": "PASS",
        "path": rel(manifest_path, repo_root),
        "manifest_status": manifest.get("status"),
        "stage": manifest.get("stage"),
        "profile": manifest.get("profile"),
        "resolved_profile": manifest.get("resolved_profile"),
        "markets": manifest.get("markets"),
        "years": manifest.get("years"),
        "failure_count": manifest.get("failure_count"),
        "failures": manifest.get("failures"),
        "output_root_matches": _path_matches(manifest.get("output_root"), label_output_root, repo_root),
        "output_path": rel(output_path, repo_root),
        "output_exists": output_path.exists(),
        "manifest_output_hash": output_hash,
        "actual_output_hash": actual_hash,
        "input_selection": dict(input_selection),
        "causal_base_manifest_gate_status": causal_gate.get("status"),
        "causal_base_manifest_gate_expected_market_year_count": causal_gate.get(
            "expected_market_year_count"
        ),
        "output_row": {
            "market": first_output.get("market"),
            "year": first_output.get("year"),
            "status": first_output.get("status"),
            "failure_count": first_output.get("failure_count"),
            "failures": first_output.get("failures"),
        },
    }


def _stop_conditions() -> list[str]:
    return [
        "Do not execute until the ES 2026 label wrapper has been approved, labels exist, and this feature gate is separately approved.",
        "Stop before execution if any expected feature artifact already exists.",
        "Stop on external timeout, Python traceback, nonzero exit, label-manifest-gate failure, missing ES 2026 label input, placeholder/provisional cost failure, or output/report path outside the candidate feature roots.",
        "Stop if Phase 4 writes anything other than the expected ES 2026 feature parquet, registry JSONs, baseline feature reports, and correlation CSV.",
        "Stop if the baseline feature manifest is not exact-scope PASS/WARN for ES 2026 or records forbidden feature leakage failures.",
        "Do not run WFA/modeling, metrics, predictions, proof scans, provider actions, staging, commit, push, or live/paper execution from this gate.",
    ]


def _recommended_next(status: str, *, label_wrapper_status: object = None) -> str:
    if status == STATUS_NO_GO:
        if label_wrapper_status == label_runner.STATUS_NO_GO:
            return (
                "Resolve the guarded ES 2026 Phase 3 label wrapper no-go and verify exact "
                "ES 2026 labels before rerunning this console-only feature gate."
            )
        return (
            "Approve and verify the guarded ES 2026 Phase 3 label wrapper first, then rerun "
            "this console-only feature gate."
        )
    return (
        "Review and separately approve the bounded ES 2026 Phase 4 feature command, or leave it pending."
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
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
    label_runner_report: Mapping[str, Any] | None = None,
    label_manifest_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    label_runner_result = dict(
        label_runner_report
        if label_runner_report is not None
        else label_runner.build_report(
            repo_root=repo_root,
            candidate_causal_root=resolve_path(repo_root, label_gate.DEFAULT_CANDIDATE_CAUSAL_ROOT),
            label_output_root=label_output_root,
            label_reports_root=label_reports_root,
            build_reports_root=resolve_path(repo_root, label_gate.DEFAULT_BUILD_REPORTS_ROOT),
            profile_config=profile_config,
            costs_config=costs_config,
            label_script=resolve_path(repo_root, label_gate.DEFAULT_LABEL_SCRIPT),
            generated_at_utc=generated_at_utc,
            staged_generated_paths=staged_paths,
            ignored_generated_paths=ignored_generated_paths,
        )
    )
    label_runner_summary = label_runner_result.get("summary")
    label_runner_summary = (
        label_runner_summary if isinstance(label_runner_summary, Mapping) else {}
    )
    label_manifest_path = label_reports_root / "label_manifest.json"
    label_manifest = dict(
        label_manifest_evidence
        if label_manifest_evidence is not None
        else _label_manifest_evidence(
            repo_root=repo_root,
            manifest_path=label_manifest_path,
            label_output_root=label_output_root,
        )
    )
    feature_flags = _declared_cli_flags(feature_script) if feature_script.exists() else set()
    command_label_output_root = command_path(label_output_root, repo_root)
    command_feature_output_root = command_path(feature_output_root, repo_root)
    command_feature_reports_root = command_path(feature_reports_root, repo_root)
    command_label_manifest = command_path(label_manifest_path, repo_root)
    command_profile_config = command_path(profile_config, repo_root)
    command_costs_config = command_path(costs_config, repo_root)
    feature_command = _feature_command(
        input_root=command_label_output_root,
        output_root=command_feature_output_root,
        reports_root=command_feature_reports_root,
        label_manifest=command_label_manifest,
        profile_config=command_profile_config,
        costs_config=command_costs_config,
    )
    command_failures = _command_failures(
        feature_command,
        input_root=command_label_output_root,
        output_root=command_feature_output_root,
        reports_root=command_feature_reports_root,
        label_manifest=command_label_manifest,
        profile_config=command_profile_config,
        costs_config=command_costs_config,
    )
    expected_artifacts = _expected_feature_artifacts(
        output_root=feature_output_root,
        reports_root=feature_reports_root,
    )
    expected_paths = [resolve_path(repo_root, artifact) for artifact in expected_artifacts]
    expected_rel_paths = [rel(path, repo_root) for path in expected_paths]
    ignored_expected_paths = (
        sorted(
            path
            for path in expected_rel_paths
            if _normalize(path) in {_normalize(item) for item in ignored_generated_paths}
        )
        if ignored_generated_paths is not None
        else _git_ignored_paths(repo_root, expected_rel_paths)
    )
    unignored_expected_paths = sorted(set(expected_rel_paths) - set(ignored_expected_paths))
    existing_expected_paths = sorted(rel(path, repo_root) for path in expected_paths if path.exists())

    expected_selection = {
        "selected_input_count": 1,
        "requested_markets": [TARGET_MARKET],
        "requested_years": [TARGET_YEAR],
        "selected_markets": [TARGET_MARKET],
        "selected_years": [TARGET_YEAR],
    }
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="label_wrapper_guarded_or_completed",
        passed=_label_wrapper_supports_feature_gate(
            label_runner_result=label_runner_result,
            label_runner_summary=label_runner_summary,
            label_manifest=label_manifest,
        ),
        observed=label_runner_summary.get("status"),
        expected="guarded label wrapper dry-run ready, executed cleanly, or exact completed label artifacts verified",
        detail="Feature planning starts from the guarded label wrapper and exact label output proof, not a raw label command.",
    )
    _check(
        checks,
        name="label_manifest_exact_es2026_pass",
        passed=(
            label_manifest.get("status") == "PASS"
            and label_manifest.get("manifest_status") == "PASS"
            and label_manifest.get("stage") == "labels"
            and label_manifest.get("profile") == TARGET_PROFILE
            and label_manifest.get("resolved_profile") == TARGET_PROFILE
            and label_manifest.get("markets") == [TARGET_MARKET]
            and label_manifest.get("years") == [TARGET_YEAR]
            and label_manifest.get("failure_count") in (0, None)
            and label_manifest.get("failures") in ([], None)
            and label_manifest.get("output_root_matches") is True
            and label_manifest.get("output_exists") is True
            and label_manifest.get("manifest_output_hash") == label_manifest.get("actual_output_hash")
            and all(
                label_manifest.get("input_selection", {}).get(key) == value
                for key, value in expected_selection.items()
            )
            and label_manifest.get("causal_base_manifest_gate_status") == "PASS"
            and label_manifest.get("causal_base_manifest_gate_expected_market_year_count") == 1
            and label_manifest.get("output_row")
            == {
                "market": TARGET_MARKET,
                "year": TARGET_YEAR,
                "status": "PASS",
                "failure_count": 0,
                "failures": [],
            }
        ),
        observed=label_manifest,
        expected="PASS label manifest for exactly ES 2026 with matching output hash",
        detail="Feature generation must trace to the approved ES 2026 labels.",
    )
    _check(
        checks,
        name="phase4_feature_cli_has_bounded_controls",
        passed=REQUIRED_FEATURE_FLAGS <= feature_flags,
        observed=sorted(feature_flags),
        expected=sorted(REQUIRED_FEATURE_FLAGS),
        detail="The Phase 4 command must support bounded market/year filters and explicit manifest/config paths.",
    )
    _check(
        checks,
        name="phase4_feature_command_exact_and_bounded",
        passed=not command_failures,
        observed=command_failures,
        expected="exact ES 2026 Phase 4 feature command with no sharding",
        detail="The approval packet must expose one exact bounded feature command.",
    )
    _check(
        checks,
        name="expected_feature_artifacts_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="All planned feature outputs must be ignored generated artifacts before execution.",
    )
    _check(
        checks,
        name="expected_feature_artifacts_absent_before_execution",
        passed=not existing_expected_paths,
        observed=existing_expected_paths,
        expected=[],
        detail="The gate must not overwrite an existing ES 2026 feature artifact.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while proposing features.",
    )
    _check(
        checks,
        name="downstream_feature_gate_console_only_default",
        passed=True,
        observed="no output writer and no subprocess execution",
        expected="gate only",
        detail="This gate writes no reports, creates no feature matrices, and runs no build command.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    approval_gate = {
        "approval_required": True,
        "approval_token": APPROVAL_TOKEN,
        "command_family": "phase4_feature_build_exact_es2026_candidate",
        "exact_command": feature_command,
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "profile": TARGET_PROFILE,
            "input_root": rel(label_output_root, repo_root),
            "output_root": rel(feature_output_root, repo_root),
            "reports_root": rel(feature_reports_root, repo_root),
            "label_manifest": rel(label_manifest_path, repo_root),
            "network": False,
            "canonical_data_mutation": False,
        },
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "expected_ignored_artifacts": expected_rel_paths,
        "forbidden_actions_without_separate_approval": list(FORBIDDEN_ACTIONS),
        "stop_conditions": _stop_conditions(),
    }
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_GATE_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "profile": TARGET_PROFILE,
            "label_wrapper_status": label_runner_summary.get("status"),
            "label_manifest_status": label_manifest.get("manifest_status"),
            "expected_generated_output_count": len(expected_rel_paths),
            "ignored_expected_generated_output_count": len(ignored_expected_paths),
            "unignored_expected_generated_output_count": len(unignored_expected_paths),
            "existing_expected_generated_output_count": len(existing_expected_paths),
            "generated_report_written": False,
            "generated_output_count": 0,
            "commands_executed": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(
                status,
                label_wrapper_status=label_runner_summary.get("status"),
            ),
            **_approval_flags(),
        },
        "checks": checks,
        "approval_gate": {} if failures else approval_gate,
        "source_evidence": {
            "label_wrapper_summary": dict(label_runner_summary),
            "label_manifest": label_manifest,
            "phase4_feature_cli_flags": sorted(feature_flags),
        },
        "expected_generated_artifacts": expected_rel_paths,
        "unignored_expected_generated_artifacts": unignored_expected_paths,
        "existing_expected_generated_artifacts": existing_expected_paths,
        "non_approval": {
            "scope": "ES 2026 downstream feature approval gate only",
            "generated_report_written": False,
            "generated_output_count": 0,
            "commands_executed": 0,
            **_approval_flags(),
        },
    }


def gate_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    return {
        "stage": STAGE,
        "status": summary.get("status"),
        "market": summary.get("market"),
        "year": summary.get("year"),
        "profile": summary.get("profile"),
        "approval_gate": report.get("approval_gate", {}),
        "generated_artifact_hygiene": {
            "expected_generated_output_count": summary.get("expected_generated_output_count"),
            "ignored_expected_generated_output_count": summary.get(
                "ignored_expected_generated_output_count"
            ),
            "unignored_expected_generated_output_count": summary.get(
                "unignored_expected_generated_output_count"
            ),
            "existing_expected_generated_output_count": summary.get(
                "existing_expected_generated_output_count"
            ),
            "generated_output_count": summary.get("generated_output_count"),
            "staged_generated_path_count": summary.get("staged_generated_path_count"),
        },
        "recommended_next_action": summary.get("recommended_next_action"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--label-output-root", default=str(DEFAULT_LABEL_OUTPUT_ROOT))
    parser.add_argument("--label-reports-root", default=str(DEFAULT_LABEL_REPORTS_ROOT))
    parser.add_argument("--feature-output-root", default=str(DEFAULT_FEATURE_OUTPUT_ROOT))
    parser.add_argument("--feature-reports-root", default=str(DEFAULT_FEATURE_REPORTS_ROOT))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--costs-config", default=str(DEFAULT_COSTS_CONFIG))
    parser.add_argument("--feature-script", default=str(DEFAULT_FEATURE_SCRIPT))
    parser.add_argument("--print-gate-json", action="store_true")
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
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"label_wrapper_status={summary['label_wrapper_status']} "
        f"label_manifest_status={summary['label_manifest_status']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"ignored_expected_generated_outputs={summary['ignored_expected_generated_output_count']} "
        f"unignored_expected_generated_outputs={summary['unignored_expected_generated_output_count']} "
        f"existing_expected_generated_outputs={summary['existing_expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"commands_executed={summary['commands_executed']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_gate_json:
        print(json.dumps(gate_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
