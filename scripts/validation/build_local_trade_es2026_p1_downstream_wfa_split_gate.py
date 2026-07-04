#!/usr/bin/env python3
"""Build a console-only downstream Phase 5 WFA split approval gate for ES 2026."""

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

from scripts.phase5_wfa import build_wfa_splits as wfa_splits  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_feature_gate as feature_gate  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_feature_build as feature_runner  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_wfa_split_gate"
STATUS_READY = "REVIEW_READY_ES2026_P1_DOWNSTREAM_WFA_SPLIT_GATE"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_WFA_SPLIT_GATE"
DECISION_GATE_ONLY = "es2026_p1_downstream_wfa_split_gate_only_no_execution"
DECISION_BLOCKED = "es2026_p1_downstream_wfa_split_gate_blocked"
APPROVAL_TOKEN = "APPROVE_ES2026_P1_PHASE5_WFA_SPLIT_BUILD_V1"

TARGET_MARKET = feature_gate.TARGET_MARKET
TARGET_YEAR = feature_gate.TARGET_YEAR
FEATURE_MANIFEST_PROFILE = feature_gate.TARGET_PROFILE
TARGET_PROFILE = "local_trade_es2026_p1_research_smoke"
DEFAULT_LABEL_OUTPUT_ROOT = feature_gate.DEFAULT_LABEL_OUTPUT_ROOT
DEFAULT_LABEL_REPORTS_ROOT = feature_gate.DEFAULT_LABEL_REPORTS_ROOT
DEFAULT_FEATURE_OUTPUT_ROOT = feature_gate.DEFAULT_FEATURE_OUTPUT_ROOT
DEFAULT_FEATURE_REPORTS_ROOT = feature_gate.DEFAULT_FEATURE_REPORTS_ROOT
DEFAULT_WFA_REPORTS_ROOT = Path("reports/wfa/local_trade_es2026_p1_candidate")
DEFAULT_PROFILE_CONFIG = feature_gate.DEFAULT_PROFILE_CONFIG
DEFAULT_MODELS_CONFIG = wfa_splits.DEFAULT_MODELS_CONFIG
DEFAULT_WFA_SCRIPT = Path("scripts/phase5_wfa/build_wfa_splits.py")
DEFAULT_TIMEOUT_SECONDS = 900

FALSE_APPROVAL_FLAGS = feature_gate.FALSE_APPROVAL_FLAGS + ("wfa_split_plan_approved",)
REQUIRED_WFA_FLAGS = {
    "--profile",
    "--input-root",
    "--reports-root",
    "--profile-config",
    "--models-config",
    "--feature-manifest",
    "--markets",
    "--years",
}
FORBIDDEN_WFA_FLAGS = {
    "--allow-final-holdout",
    "--data-audit-universe-json",
}
FORBIDDEN_ACTIONS = (
    "phase5_wfa_split_execution_without_approval",
    "feature_build_or_rerun",
    "label_build_or_rerun",
    "causal_base_build_or_rerun",
    "provider_download_or_cost_diagnostic",
    "model_training_or_selection",
    "metrics_or_predictions",
    "proof_scan",
    "staging_commit_push",
    "live_or_paper_execution",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return feature_gate.rel(path, repo_root)


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


def _expected_wfa_artifacts(*, reports_root: Path) -> list[Path]:
    return [reports_root / "split_plan.csv", reports_root / "split_plan.json"]


def _stale_failed_wfa_artifact_evidence(
    *,
    repo_root: Path,
    reports_root: Path,
    expected_paths: list[Path],
) -> dict[str, Any]:
    existing = sorted(rel(path, repo_root) for path in expected_paths if path.exists())
    if not existing:
        return {
            "status": "PASS",
            "existing_expected_artifacts": [],
            "overwrite_allowed": False,
            "reason": "no existing split artifacts",
            "failures": [],
        }

    manifest, error = _read_json_object(reports_root / "split_plan.json")
    failures: list[str] = []
    if error is not None:
        failures.append(error)
    if sorted(existing) != sorted(rel(path, repo_root) for path in expected_paths):
        failures.append("only a partial expected WFA artifact set exists")
    if manifest.get("markets") != [TARGET_MARKET]:
        failures.append(f"existing split manifest markets mismatch: {manifest.get('markets')!r}")
    if manifest.get("years") != [TARGET_YEAR]:
        failures.append(f"existing split manifest years mismatch: {manifest.get('years')!r}")
    if int(manifest.get("fold_count") or 0) > 0 and int(manifest.get("failure_count") or 0) == 0:
        failures.append("existing split manifest appears usable, not stale-failed")
    if int(manifest.get("failure_count") or 0) <= 0:
        failures.append("existing split manifest failure_count is not positive")

    return {
        "status": "FAIL" if failures else "PASS",
        "existing_expected_artifacts": existing,
        "overwrite_allowed": not failures,
        "reason": "known failed split outputs may be overwritten" if not failures else None,
        "existing_profile": manifest.get("profile"),
        "existing_resolved_profile": manifest.get("resolved_profile"),
        "existing_fold_count": manifest.get("fold_count"),
        "existing_failure_count": manifest.get("failure_count"),
        "existing_failures": manifest.get("failures"),
        "failures": failures,
    }


def _wfa_command(
    *,
    profile: str,
    input_root: Path,
    reports_root: Path,
    profile_config: Path,
    models_config: Path,
    feature_manifest: Path,
) -> str:
    return (
        "python -m scripts.phase5_wfa.build_wfa_splits "
        f"--profile {profile} "
        f"--input-root {input_root.as_posix()} "
        f"--reports-root {reports_root.as_posix()} "
        f"--profile-config {profile_config.as_posix()} "
        f"--models-config {models_config.as_posix()} "
        f"--feature-manifest {feature_manifest.as_posix()} "
        f"--markets {TARGET_MARKET} "
        f"--years {TARGET_YEAR}"
    )


def _arg_value(argv: list[str], flag: str) -> str | None:
    try:
        index = argv.index(flag)
    except ValueError:
        return None
    value_index = index + 1
    return argv[value_index] if value_index < len(argv) else None


def _command_failures(
    command: str,
    *,
    input_root: Path,
    reports_root: Path,
    profile_config: Path,
    models_config: Path,
    feature_manifest: Path,
) -> list[str]:
    failures: list[str] = []
    argv = shlex.split(command)
    argv_set = set(argv)
    if argv[:3] != ["python", "-m", "scripts.phase5_wfa.build_wfa_splits"]:
        failures.append("command does not invoke Phase 5 WFA split builder")
    for flag in FORBIDDEN_WFA_FLAGS:
        if flag in argv_set:
            failures.append(f"forbidden WFA argument present: {flag}")
    expected = {
        "--profile": TARGET_PROFILE,
        "--input-root": input_root.as_posix(),
        "--reports-root": reports_root.as_posix(),
        "--profile-config": profile_config.as_posix(),
        "--models-config": models_config.as_posix(),
        "--feature-manifest": feature_manifest.as_posix(),
        "--markets": TARGET_MARKET,
        "--years": str(TARGET_YEAR),
    }
    for flag, value in expected.items():
        observed = _arg_value(argv, flag)
        if observed != value:
            failures.append(f"{flag}={observed!r} != {value!r}")
    return failures


def _profile_scope_evidence(*, profile_config: Path, profile: str) -> dict[str, Any]:
    try:
        plan = wfa_splits.load_profile_plan(profile, profile_config)
    except SystemExit as exc:
        return {
            "status": "FAIL",
            "profile": profile,
            "profile_config": profile_config.as_posix(),
            "failures": [str(exc)],
        }
    except Exception as exc:
        return {
            "status": "FAIL",
            "profile": profile,
            "profile_config": profile_config.as_posix(),
            "failures": [f"{type(exc).__name__}: {exc}"],
        }
    try:
        plan = wfa_splits.filter_profile_plan(
            plan,
            markets=[TARGET_MARKET],
            years=[TARGET_YEAR],
        )
    except SystemExit as exc:
        return {
            "status": "FAIL",
            "profile": profile,
            "profile_config": profile_config.as_posix(),
            "failures": [str(exc)],
        }
    failures: list[str] = []
    if plan.markets != [TARGET_MARKET]:
        failures.append(f"profile markets are {plan.markets!r}, not {[TARGET_MARKET]!r}")
    if plan.years != [TARGET_YEAR]:
        failures.append(f"profile years are {plan.years!r}, not {[TARGET_YEAR]!r}")
    if set(plan.years) & set(plan.final_holdout_years):
        failures.append("target year is configured as final holdout")
    if plan.forbid_research_use:
        failures.append("profile forbids research/model training use")
    if "forward" in plan.intent:
        failures.append("profile intent is forward validation, not research smoke")
    return {
        "status": "FAIL" if failures else "PASS",
        "profile": plan.requested_profile,
        "resolved_profile": plan.resolved_profile,
        "profile_config": profile_config.as_posix(),
        "markets": plan.markets,
        "years": plan.years,
        "settings_profile": plan.settings_profile,
        "intent": plan.intent,
        "final_holdout_years": plan.final_holdout_years,
        "forbid_research_use": plan.forbid_research_use,
        "failures": failures,
    }


def _wfa_policy_evidence(*, models_config: Path) -> dict[str, Any]:
    try:
        policy = wfa_splits.load_wfa_policy(models_config)
    except SystemExit as exc:
        return {"status": "FAIL", "models_config": models_config.as_posix(), "failures": [str(exc)]}
    except Exception as exc:
        return {
            "status": "FAIL",
            "models_config": models_config.as_posix(),
            "failures": [f"{type(exc).__name__}: {exc}"],
        }
    return {
        "status": "PASS",
        "models_config": models_config.as_posix(),
        "purge_bars": policy.purge_bars,
        "resolved_purge_bars": policy.resolved_purge_bars,
        "embargo_bars": policy.embargo_bars,
        "final_holdout_tuning_allowed": policy.final_holdout_tuning_allowed,
        "final_holdout_excluded_from_selection": policy.final_holdout_excluded_from_selection,
        "failures": [],
    }


def _feature_unavailable_warning_failures(feature_manifest: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(feature_manifest, Mapping):
        return ["feature manifest unavailable-warning policy cannot be evaluated"]
    warnings: list[str] = []
    raw_warnings = feature_manifest.get("warnings")
    if isinstance(raw_warnings, list):
        warnings.extend(str(item) for item in raw_warnings)
    outputs = feature_manifest.get("outputs")
    if isinstance(outputs, list):
        for row in outputs:
            if not isinstance(row, Mapping):
                continue
            row_warnings = row.get("warnings")
            if isinstance(row_warnings, list):
                warnings.extend(str(item) for item in row_warnings)
    accepted_warnings = set(
        wfa_splits.accepted_phase4_feature_warning_messages([TARGET_MARKET])
    )
    return [
        warning
        for warning in warnings
        if warning.startswith("features fully unavailable:")
        and warning not in accepted_warnings
    ]


def _stop_conditions() -> list[str]:
    return [
        "Do not execute until the ES 2026 Phase 4 feature wrapper has been approved and feature evidence exists.",
        "Stop if the ES-only feature manifest contains fully unavailable feature warnings outside the accepted split-planning policy.",
        "Stop before execution if any planned split-plan report already exists, unless it is the known failed zero-fold ES 2026 candidate output set.",
        "Stop if the WFA command is not filtered to exactly ES 2026 or if the Phase 5 CLI cannot bind explicit roots and feature manifest.",
        "Stop on external timeout, Python traceback, nonzero exit, feature-manifest-gate failure, missing ES 2026 feature input, or split output outside the candidate WFA reports root.",
        "Stop if Phase 5 writes anything other than the planned split_plan.csv and split_plan.json reports.",
        "Do not run model training, selection, metrics, predictions, proof scans, provider actions, staging, commit, push, or live/paper execution from this gate.",
    ]


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return (
            "Resolve ES-only fully unavailable feature warnings and add an explicitly bounded "
            "ES 2026 WFA profile or CLI filter before requesting WFA split approval."
        )
    return "Review and separately approve the bounded ES 2026 Phase 5 WFA split command, or leave it pending."


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
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    feature_expected_paths = [
        resolve_path(repo_root, artifact)
        for artifact in feature_gate._expected_feature_artifacts(
            output_root=feature_output_root,
            reports_root=feature_reports_root,
        )
    ]
    feature_failures = feature_runner._validate_feature_outputs(
        repo_root=repo_root,
        expected_paths=feature_expected_paths,
        label_output_root=label_output_root,
        feature_output_root=feature_output_root,
        feature_reports_root=feature_reports_root,
        label_reports_root=label_reports_root,
    )
    feature_manifest, feature_manifest_error = _read_json_object(
        feature_reports_root / "baseline_feature_manifest.json"
    )
    profile_evidence = _profile_scope_evidence(profile_config=profile_config, profile=TARGET_PROFILE)
    policy_evidence = _wfa_policy_evidence(models_config=models_config)
    unavailable_warning_failures = _feature_unavailable_warning_failures(feature_manifest)
    wfa_flags = _declared_cli_flags(wfa_script) if wfa_script.exists() else set()

    command_input_root = command_path(feature_output_root, repo_root)
    command_reports_root = command_path(wfa_reports_root, repo_root)
    command_profile_config = command_path(profile_config, repo_root)
    command_models_config = command_path(models_config, repo_root)
    command_feature_manifest = command_path(
        feature_reports_root / "baseline_feature_manifest.json",
        repo_root,
    )
    wfa_command = _wfa_command(
        profile=TARGET_PROFILE,
        input_root=command_input_root,
        reports_root=command_reports_root,
        profile_config=command_profile_config,
        models_config=command_models_config,
        feature_manifest=command_feature_manifest,
    )
    command_failures = _command_failures(
        wfa_command,
        input_root=command_input_root,
        reports_root=command_reports_root,
        profile_config=command_profile_config,
        models_config=command_models_config,
        feature_manifest=command_feature_manifest,
    )
    expected_paths = _expected_wfa_artifacts(reports_root=wfa_reports_root)
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
    stale_output_evidence = _stale_failed_wfa_artifact_evidence(
        repo_root=repo_root,
        reports_root=wfa_reports_root,
        expected_paths=expected_paths,
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="feature_outputs_exact_es2026_pass",
        passed=not feature_failures,
        observed=feature_failures,
        expected="PASS/WARN Phase 4 feature artifacts for exactly ES 2026 with matching hashes",
        detail="WFA split planning must start from verified ES 2026 feature evidence.",
    )
    _check(
        checks,
        name="feature_fully_unavailable_warnings_resolved",
        passed=not unavailable_warning_failures,
        observed=unavailable_warning_failures,
        expected=[],
        detail=(
            "ES-only WFA approval must not proceed with all-NaN intermarket/Tier 1 "
            "features unless they are removed, rebuilt from full inputs, or separately "
            "accepted with downstream model-handling evidence."
        ),
    )
    _check(
        checks,
        name="phase5_wfa_profile_scope_exact_es2026",
        passed=profile_evidence.get("status") == "PASS",
        observed=profile_evidence,
        expected={"markets": [TARGET_MARKET], "years": [TARGET_YEAR]},
        detail="The current Phase 5 CLI has no market/year filters, so the selected profile must be exact.",
    )
    _check(
        checks,
        name="phase5_wfa_policy_safe",
        passed=policy_evidence.get("status") == "PASS",
        observed=policy_evidence,
        expected="WFA policy with random splits disabled, purge resolved, and final holdout excluded",
        detail="WFA split plans must preserve purge/embargo and no-random-split policy.",
    )
    _check(
        checks,
        name="phase5_wfa_cli_has_required_controls",
        passed=REQUIRED_WFA_FLAGS <= wfa_flags,
        observed=sorted(wfa_flags),
        expected=sorted(REQUIRED_WFA_FLAGS),
        detail="The Phase 5 command must support explicit roots, config paths, and feature manifest gating.",
    )
    _check(
        checks,
        name="phase5_wfa_command_exact_and_bounded",
        passed=not command_failures,
        observed=command_failures,
        expected="exact ES 2026 WFA split-plan command with no final-holdout or audit-universe override",
        detail="The approval packet must expose one exact bounded WFA split command.",
    )
    _check(
        checks,
        name="expected_wfa_artifacts_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="Planned WFA split outputs must be ignored generated reports before execution.",
    )
    _check(
        checks,
        name="expected_wfa_artifacts_absent_or_stale_failed_before_execution",
        passed=not existing_expected_paths or stale_output_evidence.get("status") == "PASS",
        observed=stale_output_evidence,
        expected="no existing artifacts or known failed zero-fold ES 2026 split outputs only",
        detail=(
            "The gate must not overwrite usable ES 2026 WFA split evidence; only the "
            "known failed candidate split outputs may be replaced."
        ),
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while proposing WFA splits.",
    )
    _check(
        checks,
        name="downstream_wfa_split_gate_console_only_default",
        passed=True,
        observed="no output writer and no subprocess execution",
        expected="gate only",
        detail="This gate writes no reports, creates no split plan, and runs no build command.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    approval_gate = {
        "approval_required": True,
        "approval_token": APPROVAL_TOKEN,
        "command_family": "phase5_wfa_split_plan_exact_es2026_candidate",
        "exact_command": wfa_command,
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "profile": TARGET_PROFILE,
            "input_root": rel(feature_output_root, repo_root),
            "reports_root": rel(wfa_reports_root, repo_root),
            "feature_manifest": rel(
                feature_reports_root / "baseline_feature_manifest.json",
                repo_root,
            ),
            "profile_config": rel(profile_config, repo_root),
            "models_config": rel(models_config, repo_root),
            "network": False,
            "data_mutation": False,
            "reports_mutation": True,
            "modeling": False,
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
            "feature_manifest_status": feature_manifest.get("status"),
            "feature_manifest_error": feature_manifest_error,
            "wfa_profile_status": profile_evidence.get("status"),
            "wfa_profile_market_count": len(profile_evidence.get("markets") or []),
            "wfa_profile_year_count": len(profile_evidence.get("years") or []),
            "wfa_policy_status": policy_evidence.get("status"),
            "expected_generated_output_count": len(expected_rel_paths),
            "ignored_expected_generated_output_count": len(ignored_expected_paths),
            "unignored_expected_generated_output_count": len(unignored_expected_paths),
            "existing_expected_generated_output_count": len(existing_expected_paths),
            "generated_report_written": False,
            "generated_output_count": 0,
            "commands_executed": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "approval_gate": {} if failures else approval_gate,
        "source_evidence": {
            "feature_manifest": feature_manifest,
            "feature_output_failures": feature_failures,
            "phase5_wfa_cli_flags": sorted(wfa_flags),
            "phase5_profile_scope": profile_evidence,
            "phase5_wfa_policy": policy_evidence,
            "stale_wfa_outputs": stale_output_evidence,
        },
        "expected_generated_artifacts": expected_rel_paths,
        "unignored_expected_generated_artifacts": unignored_expected_paths,
        "existing_expected_generated_artifacts": existing_expected_paths,
        "non_approval": {
            "scope": "ES 2026 downstream WFA split approval gate only",
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
    parser.add_argument("--wfa-reports-root", default=str(DEFAULT_WFA_REPORTS_ROOT))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--models-config", default=str(DEFAULT_MODELS_CONFIG))
    parser.add_argument("--wfa-script", default=str(DEFAULT_WFA_SCRIPT))
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
            wfa_reports_root=resolve_path(repo_root, args.wfa_reports_root),
            profile_config=resolve_path(repo_root, args.profile_config),
            models_config=resolve_path(repo_root, args.models_config),
            wfa_script=resolve_path(repo_root, args.wfa_script),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"feature_manifest_status={summary['feature_manifest_status']} "
        f"wfa_profile_status={summary['wfa_profile_status']} "
        f"wfa_profile_market_count={summary['wfa_profile_market_count']} "
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
