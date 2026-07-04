#!/usr/bin/env python3
"""Build a console-only downstream Phase 6 model approval gate for ES 2026."""

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

from scripts.phase7_wfa import run_wfa as phase6_wfa  # noqa: E402
from scripts.profile_scope import load_profile_scope  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_wfa_split_gate as split_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_model_gate"
STATUS_READY = "REVIEW_READY_ES2026_P1_DOWNSTREAM_MODEL_GATE"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_MODEL_GATE"
DECISION_GATE_ONLY = "es2026_p1_downstream_model_gate_only_no_execution"
DECISION_BLOCKED = "es2026_p1_downstream_model_gate_blocked"
APPROVAL_TOKEN = "APPROVE_ES2026_P1_PHASE6_MODEL_SMOKE_V1"

TARGET_MARKET = split_gate.TARGET_MARKET
TARGET_YEAR = split_gate.TARGET_YEAR
DEFAULT_PROFILE = split_gate.TARGET_PROFILE
DEFAULT_MATRIX = "baseline"
DEFAULT_RUN = "local_trade_es2026_p1_model_smoke"
DEFAULT_FEATURE_OUTPUT_ROOT = split_gate.DEFAULT_FEATURE_OUTPUT_ROOT
DEFAULT_FEATURE_REPORTS_ROOT = split_gate.DEFAULT_FEATURE_REPORTS_ROOT
DEFAULT_WFA_SPLIT_REPORTS_ROOT = split_gate.DEFAULT_WFA_REPORTS_ROOT
DEFAULT_PREDICTIONS_ROOT = Path("data/predictions/local_trade_es2026_p1_candidate")
DEFAULT_MODEL_REPORTS_ROOT = Path("reports/wfa/local_trade_es2026_p1_candidate_model")
DEFAULT_PROFILE_CONFIG = split_gate.DEFAULT_PROFILE_CONFIG
DEFAULT_MODELS_CONFIG = split_gate.DEFAULT_MODELS_CONFIG
DEFAULT_PHASE6_SCRIPT = Path("scripts/phase7_wfa/run_wfa.py")
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_MAX_FOLDS = 1

FALSE_APPROVAL_FLAGS = split_gate.FALSE_APPROVAL_FLAGS + (
    "wfa_model_training_approved",
    "wfa_prediction_write_approved",
)
REQUIRED_PHASE6_FLAGS = {
    "--profile",
    "--matrix",
    "--run",
    "--input-root",
    "--split-plan",
    "--predictions-root",
    "--reports-root",
    "--models-config",
    "--profile-config",
    "--feature-cols",
    "--feature-set",
    "--max-folds",
    "--markets",
    "--fold-shard-count",
    "--fold-shard-index",
    "--write-predictions",
    "--no-predictions",
    "--report-only",
}
FORBIDDEN_ACTIONS = (
    "phase6_wfa_model_execution_without_approval",
    "phase5_wfa_split_build_or_rerun",
    "feature_build_or_rerun",
    "label_build_or_rerun",
    "causal_base_build_or_rerun",
    "provider_download_or_cost_diagnostic",
    "metrics_or_model_selection",
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
    return split_gate.rel(path, repo_root)


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


def _expected_model_artifacts(
    *,
    predictions_root: Path,
    reports_root: Path,
    run: str,
) -> list[Path]:
    return [
        predictions_root / run / "oos_predictions.parquet",
        reports_root / f"{run}_wfa_report.json",
        reports_root / f"{run}_predictions_manifest.json",
    ]


def _phase6_command(
    *,
    profile: str,
    matrix: str,
    run: str,
    input_root: Path,
    split_plan: Path,
    predictions_root: Path,
    reports_root: Path,
    models_config: Path,
    profile_config: Path,
    feature_cols: Path,
    max_folds: int,
) -> str:
    return (
        "python -m scripts.phase6_wfa.run_wfa "
        f"--profile {profile} "
        f"--matrix {matrix} "
        f"--run {run} "
        f"--input-root {input_root.as_posix()} "
        f"--split-plan {split_plan.as_posix()} "
        f"--predictions-root {predictions_root.as_posix()} "
        f"--reports-root {reports_root.as_posix()} "
        f"--models-config {models_config.as_posix()} "
        f"--profile-config {profile_config.as_posix()} "
        f"--feature-cols {feature_cols.as_posix()} "
        f"--markets {TARGET_MARKET} "
        f"--max-folds {max_folds} "
        "--write-predictions"
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
    profile: str,
    matrix: str,
    run: str,
    input_root: Path,
    split_plan: Path,
    predictions_root: Path,
    reports_root: Path,
    models_config: Path,
    profile_config: Path,
    feature_cols: Path,
    max_folds: int,
) -> list[str]:
    failures: list[str] = []
    argv = shlex.split(command)
    argv_set = set(argv)
    if argv[:3] != ["python", "-m", "scripts.phase6_wfa.run_wfa"]:
        failures.append("command does not invoke Phase 6 WFA runner")
    if "--write-predictions" not in argv_set:
        failures.append("Phase 6 command must explicitly use --write-predictions")
    for flag in ("--report-only", "--no-predictions"):
        if flag in argv_set:
            failures.append(f"forbidden model gate command argument present: {flag}")
    expected = {
        "--profile": profile,
        "--matrix": matrix,
        "--run": run,
        "--input-root": input_root.as_posix(),
        "--split-plan": split_plan.as_posix(),
        "--predictions-root": predictions_root.as_posix(),
        "--reports-root": reports_root.as_posix(),
        "--models-config": models_config.as_posix(),
        "--profile-config": profile_config.as_posix(),
        "--feature-cols": feature_cols.as_posix(),
        "--markets": TARGET_MARKET,
        "--max-folds": str(max_folds),
    }
    for flag, value in expected.items():
        observed = _arg_value(argv, flag)
        if observed != value:
            failures.append(f"{flag}={observed!r} != {value!r}")
    return failures


def _profile_evidence(*, profile: str, profile_config: Path) -> dict[str, Any]:
    try:
        plan = load_profile_scope(profile, profile_config)
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
        config = phase6_wfa._read_yaml(profile_config)
    except Exception:
        config = {}
    profiles = config.get("profiles", {})
    entry = profiles.get(plan.resolved_profile, {}) if isinstance(profiles, Mapping) else {}
    entry = entry if isinstance(entry, Mapping) else {}
    forbid_research_use = bool(entry.get("forbid_research_use", False))
    failures: list[str] = []
    if plan.markets != [TARGET_MARKET]:
        failures.append(f"profile markets are {plan.markets!r}, not {[TARGET_MARKET]!r}")
    if plan.years != [TARGET_YEAR]:
        failures.append(f"profile years are {plan.years!r}, not {[TARGET_YEAR]!r}")
    if forbid_research_use:
        failures.append("profile forbids research/model training use")
    return {
        "status": "FAIL" if failures else "PASS",
        "profile": plan.requested_profile,
        "resolved_profile": plan.resolved_profile,
        "profile_config": profile_config.as_posix(),
        "markets": plan.markets,
        "years": plan.years,
        "settings_profile": entry.get("settings_profile"),
        "forbid_research_use": forbid_research_use,
        "failures": failures,
    }


def _feature_evidence(*, input_root: Path, feature_cols: Path) -> dict[str, Any]:
    try:
        feature_set = phase6_wfa.resolve_feature_set(
            input_root,
            feature_cols_path=feature_cols,
            feature_set_path=None,
        )
    except SystemExit as exc:
        return {"status": "FAIL", "feature_cols": feature_cols.as_posix(), "failures": [str(exc)]}
    except Exception as exc:
        return {
            "status": "FAIL",
            "feature_cols": feature_cols.as_posix(),
            "failures": [f"{type(exc).__name__}: {exc}"],
        }
    return {
        "status": "PASS",
        "feature_cols": feature_cols.as_posix(),
        "feature_count": len(feature_set.feature_cols),
        "config_path": feature_set.config_path.as_posix(),
        "failures": [],
    }


def _models_evidence(*, models_config: Path) -> dict[str, Any]:
    try:
        model_specs, _config = phase6_wfa.load_model_specs(models_config)
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
        "model_count": len(model_specs),
        "model_ids": [spec.model_id for spec in model_specs],
        "targets": [spec.target for spec in model_specs],
        "failures": [],
    }


def _split_plan_evidence(
    *,
    repo_root: Path,
    split_plan: Path,
    profile: str,
    profile_config: Path,
    models_config: Path,
    feature_output_root: Path,
    feature_reports_root: Path,
    wfa_reports_root: Path,
) -> dict[str, Any]:
    manifest, error = _read_json_object(split_plan)
    if error is not None:
        return {
            "status": "FAIL",
            "split_plan": rel(split_plan, repo_root),
            "selectable_research_fold_count": 0,
            "failures": [error],
        }
    failures: list[str] = []
    try:
        profile_plan = load_profile_scope(profile, profile_config)
        phase6_wfa._validate_split_plan_scope(
            split_manifest=manifest,
            plan=profile_plan,
            profile_config=profile_config,
            models_config=models_config,
        )
    except SystemExit as exc:
        failures.append(str(exc))
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")

    if int(manifest.get("failure_count") or 0) != 0:
        failures.append("WFA split manifest failure_count is not 0")
    if manifest.get("failures") not in ([], None):
        failures.append("WFA split manifest failures are non-empty")
    if int(manifest.get("fold_count") or 0) <= 0:
        failures.append("WFA split manifest fold_count is not positive")
    if manifest.get("markets") != [TARGET_MARKET]:
        failures.append(f"WFA split manifest markets mismatch: {manifest.get('markets')!r}")
    if manifest.get("years") != [TARGET_YEAR]:
        failures.append(f"WFA split manifest years mismatch: {manifest.get('years')!r}")
    if not _path_matches(manifest.get("input_root"), feature_output_root, repo_root):
        failures.append("WFA split manifest input_root mismatch")
    if not _path_matches(manifest.get("reports_root"), wfa_reports_root, repo_root):
        failures.append("WFA split manifest reports_root mismatch")

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

    selectable_research_folds: list[str] = []
    non_research_selectable_folds: list[str] = []
    skipped_folds: list[dict[str, Any]] = []
    folds = manifest.get("folds")
    if not isinstance(folds, list) or not folds:
        failures.append("WFA split manifest folds missing")
    else:
        for index, fold in enumerate(folds):
            if not isinstance(fold, Mapping):
                failures.append(f"fold {index} is not an object")
                continue
            fold_failures = phase6_wfa._validate_fold_fields(fold)
            failures.extend(fold_failures)
            fold_id = str(fold.get("fold_id", f"fold_{index}"))
            split_group = str(fold.get("split_group", ""))
            if fold.get("selection_allowed") is True and split_group == "research":
                selectable_research_folds.append(fold_id)
            elif fold.get("selection_allowed") is True:
                non_research_selectable_folds.append(fold_id)
            else:
                skipped_folds.append(
                    {
                        "fold_id": fold_id,
                        "split_group": split_group,
                        "reason": "selection_allowed is false",
                    }
                )
    if non_research_selectable_folds:
        failures.append(f"non-research folds marked selection_allowed: {non_research_selectable_folds}")

    return {
        "status": "FAIL" if failures else "PASS",
        "split_plan": rel(split_plan, repo_root),
        "profile": manifest.get("profile"),
        "resolved_profile": manifest.get("resolved_profile"),
        "markets": manifest.get("markets"),
        "years": manifest.get("years"),
        "fold_count": manifest.get("fold_count"),
        "selectable_research_fold_count": len(selectable_research_folds),
        "selectable_research_folds": selectable_research_folds[:10],
        "non_research_selectable_folds": non_research_selectable_folds[:10],
        "skipped_fold_count": len(skipped_folds),
        "skipped_folds": skipped_folds[:10],
        "failures": failures,
    }


def _stop_conditions() -> list[str]:
    return [
        "Do not execute until an exact ES 2026 research-eligible WFA split plan exists.",
        "Stop before execution if any planned prediction or WFA model report artifact already exists.",
        "Stop if the profile forbids research use, if no research fold is selectable, or if any non-research fold is selectable.",
        "Stop on external timeout, Python traceback, nonzero exit, no prediction rows, duplicate predictions, stale prediction output, or manifest failure_count above 0.",
        "Stop if Phase 6 writes anything outside the planned prediction parquet and model report artifacts.",
        "Do not run metrics, model selection, proof scans, provider actions, staging, commit, push, or live/paper execution from this gate.",
    ]


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return (
            "Complete and verify a separate ES 2026 research-eligible WFA split plan before "
            "requesting Phase 6 model approval; do not train on forward/restricted folds."
        )
    return "Review and separately approve the bounded ES 2026 Phase 6 model smoke command, or leave it pending."


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
    profile_config: Path,
    models_config: Path,
    phase6_script: Path,
    max_folds: int = DEFAULT_MAX_FOLDS,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    feature_cols = feature_output_root / "feature_cols.json"
    split_plan = wfa_split_reports_root / "split_plan.json"
    profile_evidence = _profile_evidence(profile=profile, profile_config=profile_config)
    feature_evidence = _feature_evidence(input_root=feature_output_root, feature_cols=feature_cols)
    models_evidence = _models_evidence(models_config=models_config)
    split_evidence = _split_plan_evidence(
        repo_root=repo_root,
        split_plan=split_plan,
        profile=profile,
        profile_config=profile_config,
        models_config=models_config,
        feature_output_root=feature_output_root,
        feature_reports_root=feature_reports_root,
        wfa_reports_root=wfa_split_reports_root,
    )
    phase6_flags = _declared_cli_flags(phase6_script) if phase6_script.exists() else set()

    command = _phase6_command(
        profile=profile,
        matrix=matrix,
        run=run,
        input_root=command_path(feature_output_root, repo_root),
        split_plan=command_path(split_plan, repo_root),
        predictions_root=command_path(predictions_root, repo_root),
        reports_root=command_path(model_reports_root, repo_root),
        models_config=command_path(models_config, repo_root),
        profile_config=command_path(profile_config, repo_root),
        feature_cols=command_path(feature_cols, repo_root),
        max_folds=max_folds,
    )
    command_failures = _command_failures(
        command,
        profile=profile,
        matrix=matrix,
        run=run,
        input_root=command_path(feature_output_root, repo_root),
        split_plan=command_path(split_plan, repo_root),
        predictions_root=command_path(predictions_root, repo_root),
        reports_root=command_path(model_reports_root, repo_root),
        models_config=command_path(models_config, repo_root),
        profile_config=command_path(profile_config, repo_root),
        feature_cols=command_path(feature_cols, repo_root),
        max_folds=max_folds,
    )
    expected_paths = _expected_model_artifacts(
        predictions_root=predictions_root,
        reports_root=model_reports_root,
        run=run,
    )
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

    selectable_research_fold_count = int(split_evidence.get("selectable_research_fold_count") or 0)
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="phase6_profile_research_eligible_exact_es2026",
        passed=profile_evidence.get("status") == "PASS",
        observed=profile_evidence,
        expected={
            "markets": [TARGET_MARKET],
            "years": [TARGET_YEAR],
            "forbid_research_use": False,
        },
        detail="Phase 6 model training must not use locked holdout or forward-validation profiles.",
    )
    _check(
        checks,
        name="feature_registry_valid_for_phase6",
        passed=feature_evidence.get("status") == "PASS",
        observed=feature_evidence,
        expected="valid feature column registry for ES 2026 candidate features",
        detail="Phase 6 must start from explicit feature columns, not implicit schema guesses.",
    )
    _check(
        checks,
        name="models_config_safe_for_phase6",
        passed=models_evidence.get("status") == "PASS",
        observed=models_evidence,
        expected="enabled Phase 7A baseline models with random/final-holdout tuning disabled",
        detail="Model config must keep random splits and initial/final-holdout tuning disabled.",
    )
    _check(
        checks,
        name="wfa_split_plan_exact_es2026_valid",
        passed=split_evidence.get("status") == "PASS",
        observed=split_evidence,
        expected="valid exact ES 2026 split plan with zero failures",
        detail="Phase 6 must start from verified WFA split evidence.",
    )
    _check(
        checks,
        name="wfa_split_plan_has_selectable_research_folds",
        passed=selectable_research_fold_count > 0,
        observed=selectable_research_fold_count,
        expected="at least one research split with selection_allowed=true",
        detail="Forward/restricted folds are validation evidence only and must not be fit by this gate.",
    )
    _check(
        checks,
        name="phase6_cli_has_required_controls",
        passed=REQUIRED_PHASE6_FLAGS <= phase6_flags,
        observed=sorted(phase6_flags),
        expected=sorted(REQUIRED_PHASE6_FLAGS),
        detail="The Phase 6 command must support explicit roots, split plan, model config, features, filters, and prediction-write controls.",
    )
    _check(
        checks,
        name="phase6_model_command_exact_and_bounded",
        passed=not command_failures,
        observed=command_failures,
        expected="exact ES 2026 Phase 6 model smoke command with --max-folds 1 and --write-predictions",
        detail="The approval packet must expose one bounded model/prediction command.",
    )
    _check(
        checks,
        name="expected_model_artifacts_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="Planned prediction and WFA model report artifacts must be ignored before execution.",
    )
    _check(
        checks,
        name="expected_model_artifacts_absent_before_execution",
        passed=not existing_expected_paths,
        observed=existing_expected_paths,
        expected=[],
        detail="The gate must not overwrite an existing ES 2026 model/prediction artifact.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while proposing model work.",
    )
    _check(
        checks,
        name="downstream_model_gate_console_only_default",
        passed=True,
        observed="no output writer and no subprocess execution",
        expected="gate only",
        detail="This gate writes no reports, creates no predictions, and runs no model command.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    approval_gate = {
        "approval_required": True,
        "approval_token": APPROVAL_TOKEN,
        "command_family": "phase6_wfa_model_smoke_exact_es2026_candidate",
        "exact_command": command,
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "profile": profile,
            "matrix": matrix,
            "run": run,
            "max_folds": max_folds,
            "input_root": rel(feature_output_root, repo_root),
            "split_plan": rel(split_plan, repo_root),
            "predictions_root": rel(predictions_root, repo_root),
            "reports_root": rel(model_reports_root, repo_root),
            "models_config": rel(models_config, repo_root),
            "profile_config": rel(profile_config, repo_root),
            "feature_cols": rel(feature_cols, repo_root),
            "network": False,
            "data_mutation": True,
            "reports_mutation": True,
            "model_training": True,
            "metrics_or_model_selection": False,
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
            "profile": profile,
            "matrix": matrix,
            "run": run,
            "profile_status": profile_evidence.get("status"),
            "feature_registry_status": feature_evidence.get("status"),
            "models_config_status": models_evidence.get("status"),
            "wfa_split_plan_status": split_evidence.get("status"),
            "selectable_research_fold_count": selectable_research_fold_count,
            "phase6_cli_required_control_count": len(REQUIRED_PHASE6_FLAGS),
            "phase6_cli_observed_control_count": len(phase6_flags),
            "max_folds": max_folds,
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
            "profile": profile_evidence,
            "feature_registry": feature_evidence,
            "models_config": models_evidence,
            "wfa_split_plan": split_evidence,
            "phase6_cli_flags": sorted(phase6_flags),
        },
        "expected_generated_artifacts": expected_rel_paths,
        "unignored_expected_generated_artifacts": unignored_expected_paths,
        "existing_expected_generated_artifacts": existing_expected_paths,
        "non_approval": {
            "scope": "ES 2026 downstream Phase 6 model approval gate only",
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
        "selectable_research_fold_count": summary.get("selectable_research_fold_count"),
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
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--matrix", default=DEFAULT_MATRIX)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--feature-output-root", default=str(DEFAULT_FEATURE_OUTPUT_ROOT))
    parser.add_argument("--feature-reports-root", default=str(DEFAULT_FEATURE_REPORTS_ROOT))
    parser.add_argument("--wfa-split-reports-root", default=str(DEFAULT_WFA_SPLIT_REPORTS_ROOT))
    parser.add_argument("--predictions-root", default=str(DEFAULT_PREDICTIONS_ROOT))
    parser.add_argument("--model-reports-root", default=str(DEFAULT_MODEL_REPORTS_ROOT))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--models-config", default=str(DEFAULT_MODELS_CONFIG))
    parser.add_argument("--phase6-script", default=str(DEFAULT_PHASE6_SCRIPT))
    parser.add_argument("--max-folds", type=int, default=DEFAULT_MAX_FOLDS)
    parser.add_argument("--print-gate-json", action="store_true")
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
            profile_config=resolve_path(repo_root, args.profile_config),
            models_config=resolve_path(repo_root, args.models_config),
            phase6_script=resolve_path(repo_root, args.phase6_script),
            max_folds=int(args.max_folds),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"profile_status={summary['profile_status']} "
        f"feature_registry_status={summary['feature_registry_status']} "
        f"models_config_status={summary['models_config_status']} "
        f"wfa_split_plan_status={summary['wfa_split_plan_status']} "
        f"selectable_research_folds={summary['selectable_research_fold_count']} "
        f"max_folds={summary['max_folds']} "
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
