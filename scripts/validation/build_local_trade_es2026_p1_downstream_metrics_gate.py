#!/usr/bin/env python3
"""Build a console-only downstream Phase 8 metrics approval gate for ES 2026."""

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

from scripts.phase8_model_selection import evaluate_predictions as phase8  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_downstream_model_gate as model_gate  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_model_build as model_runner  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_metrics_gate"
STATUS_READY = "REVIEW_READY_ES2026_P1_DOWNSTREAM_METRICS_GATE"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_METRICS_GATE"
DECISION_GATE_ONLY = "es2026_p1_downstream_metrics_gate_only_no_execution"
DECISION_BLOCKED = "es2026_p1_downstream_metrics_gate_blocked"
APPROVAL_TOKEN = "APPROVE_ES2026_P1_PHASE8_METRICS_V1"

TARGET_MARKET = model_gate.TARGET_MARKET
TARGET_YEAR = model_gate.TARGET_YEAR
DEFAULT_PROFILE = model_gate.DEFAULT_PROFILE
DEFAULT_MATRIX = model_gate.DEFAULT_MATRIX
DEFAULT_RUN = model_gate.DEFAULT_RUN
DEFAULT_FEATURE_OUTPUT_ROOT = model_gate.DEFAULT_FEATURE_OUTPUT_ROOT
DEFAULT_FEATURE_REPORTS_ROOT = model_gate.DEFAULT_FEATURE_REPORTS_ROOT
DEFAULT_WFA_SPLIT_REPORTS_ROOT = model_gate.DEFAULT_WFA_SPLIT_REPORTS_ROOT
DEFAULT_PREDICTIONS_ROOT = model_gate.DEFAULT_PREDICTIONS_ROOT
DEFAULT_MODEL_REPORTS_ROOT = model_gate.DEFAULT_MODEL_REPORTS_ROOT
DEFAULT_PROFILE_CONFIG = model_gate.DEFAULT_PROFILE_CONFIG
DEFAULT_MODELS_CONFIG = model_gate.DEFAULT_MODELS_CONFIG
DEFAULT_COSTS_CONFIG = phase8.DEFAULT_COSTS_CONFIG
DEFAULT_METRICS_ROOT = Path("reports/metrics/local_trade_es2026_p1_candidate_model")
DEFAULT_MODEL_SELECTION_ROOT = Path("reports/model_selection/local_trade_es2026_p1_candidate_model")
DEFAULT_PHASE8_ROOT = Path("reports/phase8/local_trade_es2026_p1_candidate_model")
DEFAULT_PHASE8_SCRIPT = Path("scripts/phase8_model_selection/evaluate_predictions.py")
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_MAX_FOLDS = model_gate.DEFAULT_MAX_FOLDS

DEFAULT_POLICY_ARGS: dict[str, str] = {
    "--long-short-margin": "0.05",
    "--min-fade-success": "0.50",
    "--max-trend-danger": "0.50",
    "--min-gross-return-dollars": "1.0",
    "--min-net-return-dollars": "1.0",
    "--min-net-sharpe-like": "0.0",
    "--max-cost-drag-to-abs-gross": "1.0",
    "--max-turnover-per-bar": "0.10",
    "--min-trade-count": "100",
    "--min-market-count": "2",
    "--min-traded-market-count": "2",
    "--min-fold-count": "4",
    "--min-traded-fold-count": "4",
    "--min-oos-span-days": "30.0",
    "--max-single-market-trade-share": "0.75",
    "--max-single-fold-trade-share": "0.50",
}

FALSE_APPROVAL_FLAGS = model_gate.FALSE_APPROVAL_FLAGS + (
    "phase8_metrics_approved",
    "model_selection_approved",
    "model_promotion_approved",
)
REQUIRED_PHASE8_FLAGS = {
    "--predictions",
    "--predictions-manifest",
    "--costs-config",
    "--models-config",
    "--metrics-root",
    "--model-selection-root",
    "--phase8-root",
    "--run",
    "--long-short-margin",
    "--min-fade-success",
    "--max-trend-danger",
    "--min-gross-return-dollars",
    "--min-net-return-dollars",
    "--min-net-sharpe-like",
    "--max-cost-drag-to-abs-gross",
    "--max-turnover-per-bar",
    "--min-trade-count",
    "--min-market-count",
    "--min-traded-market-count",
    "--min-fold-count",
    "--min-traded-fold-count",
    "--min-oos-span-days",
    "--max-single-market-trade-share",
    "--max-single-fold-trade-share",
    "--allow-negative-net-market",
    "--allow-negative-net-fold",
    "--require-promotion-ready",
}
FORBIDDEN_PHASE8_COMMAND_FLAGS = {
    "--allow-negative-net-market",
    "--allow-negative-net-fold",
    "--require-promotion-ready",
}
FORBIDDEN_ACTIONS = (
    "phase8_metrics_execution_without_approval",
    "model_training_or_prediction_rerun",
    "wfa_split_build_or_rerun",
    "feature_build_or_rerun",
    "label_build_or_rerun",
    "causal_base_build_or_rerun",
    "provider_download_or_cost_diagnostic",
    "proof_scan",
    "model_promotion_or_artifact_freeze",
    "staging_commit_push",
    "live_or_paper_execution",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return model_gate.rel(path, repo_root)


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


def _expected_metrics_artifacts(
    *,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
    run: str,
) -> list[Path]:
    return [
        metrics_root / f"{run}_metrics.json",
        metrics_root / f"{run}_metrics.csv",
        metrics_root / "turnover_diagnostics.csv",
        model_selection_root / "model_comparison.csv",
        model_selection_root / "model_selection_report.json",
        model_selection_root / "calibration_report.json",
        phase8_root / "metrics.json",
        phase8_root / "alpha_promotion_decision.json",
    ]


def _phase8_command(
    *,
    run: str,
    predictions: Path,
    predictions_manifest: Path,
    costs_config: Path,
    models_config: Path,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
) -> str:
    parts = [
        "python -m scripts.phase8_model_selection.evaluate_predictions",
        f"--predictions {predictions.as_posix()}",
        f"--predictions-manifest {predictions_manifest.as_posix()}",
        f"--costs-config {costs_config.as_posix()}",
        f"--models-config {models_config.as_posix()}",
        f"--metrics-root {metrics_root.as_posix()}",
        f"--model-selection-root {model_selection_root.as_posix()}",
        f"--phase8-root {phase8_root.as_posix()}",
        f"--run {run}",
    ]
    parts.extend(f"{flag} {value}" for flag, value in DEFAULT_POLICY_ARGS.items())
    return " ".join(parts)


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
    run: str,
    predictions: Path,
    predictions_manifest: Path,
    costs_config: Path,
    models_config: Path,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
) -> list[str]:
    failures: list[str] = []
    argv = shlex.split(command)
    argv_set = set(argv)
    if argv[:3] != ["python", "-m", "scripts.phase8_model_selection.evaluate_predictions"]:
        failures.append("command does not invoke Phase 8 evaluator")
    for flag in FORBIDDEN_PHASE8_COMMAND_FLAGS:
        if flag in argv_set:
            failures.append(f"forbidden Phase 8 command flag present: {flag}")
    expected = {
        "--predictions": predictions.as_posix(),
        "--predictions-manifest": predictions_manifest.as_posix(),
        "--costs-config": costs_config.as_posix(),
        "--models-config": models_config.as_posix(),
        "--metrics-root": metrics_root.as_posix(),
        "--model-selection-root": model_selection_root.as_posix(),
        "--phase8-root": phase8_root.as_posix(),
        "--run": run,
        **DEFAULT_POLICY_ARGS,
    }
    for flag, value in expected.items():
        observed = _arg_value(argv, flag)
        if observed != value:
            failures.append(f"{flag}={observed!r} != {value!r}")
    return failures


def _model_output_evidence(
    *,
    repo_root: Path,
    profile: str,
    matrix: str,
    run: str,
    feature_output_root: Path,
    wfa_split_reports_root: Path,
    predictions_root: Path,
    model_reports_root: Path,
    profile_config: Path,
    models_config: Path,
    max_folds: int,
) -> dict[str, Any]:
    expected_paths = model_gate._expected_model_artifacts(
        predictions_root=predictions_root,
        reports_root=model_reports_root,
        run=run,
    )
    failures = model_runner._validate_model_outputs(
        repo_root=repo_root,
        expected_paths=expected_paths,
        profile=profile,
        matrix=matrix,
        run=run,
        feature_output_root=feature_output_root,
        wfa_split_reports_root=wfa_split_reports_root,
        predictions_root=predictions_root,
        model_reports_root=model_reports_root,
        models_config=models_config,
        profile_config=profile_config,
        max_folds=max_folds,
    )
    return {
        "status": "FAIL" if failures else "PASS",
        "run": run,
        "prediction_path": rel(predictions_root / run / "oos_predictions.parquet", repo_root),
        "prediction_manifest": rel(model_reports_root / f"{run}_predictions_manifest.json", repo_root),
        "wfa_report": rel(model_reports_root / f"{run}_wfa_report.json", repo_root),
        "expected_model_artifacts": [rel(path, repo_root) for path in expected_paths],
        "failure_count": len(failures),
        "failures": failures,
    }


def _phase8_config_evidence(*, costs_config: Path, models_config: Path) -> dict[str, Any]:
    failures: list[str] = []
    if not costs_config.is_file():
        failures.append(f"missing costs config: {costs_config.as_posix()}")
    if not models_config.is_file():
        failures.append(f"missing models config: {models_config.as_posix()}")
    return {
        "status": "FAIL" if failures else "PASS",
        "costs_config": costs_config.as_posix(),
        "models_config": models_config.as_posix(),
        "failures": failures,
    }


def _stop_conditions() -> list[str]:
    return [
        "Do not execute until exact ES 2026 Phase 6 model-smoke prediction evidence exists.",
        "Stop before execution if any planned metrics/model-selection artifact already exists.",
        "Stop if prediction manifest artifact evidence is not ready, prediction hash is stale, or final-holdout predictions are present.",
        "Stop on external timeout, Python traceback, nonzero structural evaluation exit, nonzero Phase 8 failure_count, or generated outputs outside the planned reports roots.",
        "Treat promotion output as diagnostics only; do not freeze, promote, trade, or tune without a separate approval gate.",
        "Do not run provider actions, proof scans, staging, commit, push, or live/paper execution from this gate.",
    ]


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return (
            "Complete and verify the guarded ES 2026 Phase 6 model smoke wrapper before "
            "requesting Phase 8 metrics approval."
        )
    return "Review and separately approve the bounded ES 2026 Phase 8 metrics command, or leave it pending."


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
    predictions_path = predictions_root / run / "oos_predictions.parquet"
    predictions_manifest = model_reports_root / f"{run}_predictions_manifest.json"
    model_evidence = _model_output_evidence(
        repo_root=repo_root,
        profile=profile,
        matrix=matrix,
        run=run,
        feature_output_root=feature_output_root,
        wfa_split_reports_root=wfa_split_reports_root,
        predictions_root=predictions_root,
        model_reports_root=model_reports_root,
        profile_config=profile_config,
        models_config=models_config,
        max_folds=max_folds,
    )
    phase8_flags = _declared_cli_flags(phase8_script) if phase8_script.exists() else set()
    config_evidence = _phase8_config_evidence(
        costs_config=costs_config,
        models_config=models_config,
    )
    command = _phase8_command(
        run=run,
        predictions=command_path(predictions_path, repo_root),
        predictions_manifest=command_path(predictions_manifest, repo_root),
        costs_config=command_path(costs_config, repo_root),
        models_config=command_path(models_config, repo_root),
        metrics_root=command_path(metrics_root, repo_root),
        model_selection_root=command_path(model_selection_root, repo_root),
        phase8_root=command_path(phase8_root, repo_root),
    )
    command_failures = _command_failures(
        command,
        run=run,
        predictions=command_path(predictions_path, repo_root),
        predictions_manifest=command_path(predictions_manifest, repo_root),
        costs_config=command_path(costs_config, repo_root),
        models_config=command_path(models_config, repo_root),
        metrics_root=command_path(metrics_root, repo_root),
        model_selection_root=command_path(model_selection_root, repo_root),
        phase8_root=command_path(phase8_root, repo_root),
    )
    expected_paths = _expected_metrics_artifacts(
        metrics_root=metrics_root,
        model_selection_root=model_selection_root,
        phase8_root=phase8_root,
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

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="phase6_model_outputs_exact_es2026_ready",
        passed=model_evidence.get("status") == "PASS",
        observed=model_evidence,
        expected="valid ES 2026 model-smoke prediction parquet, manifest, and WFA report",
        detail="Phase 8 must start from verified ES 2026 prediction evidence.",
    )
    _check(
        checks,
        name="phase8_cli_has_required_controls",
        passed=REQUIRED_PHASE8_FLAGS <= phase8_flags,
        observed=sorted(phase8_flags),
        expected=sorted(REQUIRED_PHASE8_FLAGS),
        detail="The Phase 8 command must support explicit inputs, roots, policy thresholds, and promotion guard switches.",
    )
    _check(
        checks,
        name="phase8_configs_present",
        passed=config_evidence.get("status") == "PASS",
        observed=config_evidence,
        expected="existing costs and models config files",
        detail="Phase 8 metrics require explicit cost and model policy configs.",
    )
    _check(
        checks,
        name="phase8_metrics_command_exact_and_bounded",
        passed=not command_failures,
        observed=command_failures,
        expected="exact ES 2026 Phase 8 metrics/model-selection command with fixed policy thresholds",
        detail="The approval packet must expose one bounded metrics command.",
    )
    _check(
        checks,
        name="expected_metrics_artifacts_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="Planned metrics and model-selection reports must be ignored generated artifacts before execution.",
    )
    _check(
        checks,
        name="expected_metrics_artifacts_absent_before_execution",
        passed=not existing_expected_paths,
        observed=existing_expected_paths,
        expected=[],
        detail="The gate must not overwrite existing ES 2026 metrics/model-selection artifacts.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while proposing metrics work.",
    )
    _check(
        checks,
        name="downstream_metrics_gate_console_only_default",
        passed=True,
        observed="no output writer and no subprocess execution",
        expected="gate only",
        detail="This gate writes no reports, creates no metrics, and runs no Phase 8 command.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    approval_gate = {
        "approval_required": True,
        "approval_token": APPROVAL_TOKEN,
        "command_family": "phase8_metrics_model_selection_exact_es2026_candidate",
        "exact_command": command,
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "profile": profile,
            "matrix": matrix,
            "run": run,
            "predictions": rel(predictions_path, repo_root),
            "predictions_manifest": rel(predictions_manifest, repo_root),
            "metrics_root": rel(metrics_root, repo_root),
            "model_selection_root": rel(model_selection_root, repo_root),
            "phase8_root": rel(phase8_root, repo_root),
            "costs_config": rel(costs_config, repo_root),
            "models_config": rel(models_config, repo_root),
            "network": False,
            "data_mutation": False,
            "reports_mutation": True,
            "model_training": False,
            "promotion_or_freeze": False,
            "live_or_paper_execution": False,
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
            "model_output_status": model_evidence.get("status"),
            "phase8_config_status": config_evidence.get("status"),
            "phase8_cli_required_control_count": len(REQUIRED_PHASE8_FLAGS),
            "phase8_cli_observed_control_count": len(phase8_flags),
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
            "model_outputs": model_evidence,
            "phase8_configs": config_evidence,
            "phase8_cli_flags": sorted(phase8_flags),
        },
        "expected_generated_artifacts": expected_rel_paths,
        "unignored_expected_generated_artifacts": unignored_expected_paths,
        "existing_expected_generated_artifacts": existing_expected_paths,
        "non_approval": {
            "scope": "ES 2026 downstream Phase 8 metrics approval gate only",
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
        "model_output_status": summary.get("model_output_status"),
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
    parser.add_argument("--metrics-root", default=str(DEFAULT_METRICS_ROOT))
    parser.add_argument("--model-selection-root", default=str(DEFAULT_MODEL_SELECTION_ROOT))
    parser.add_argument("--phase8-root", default=str(DEFAULT_PHASE8_ROOT))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--models-config", default=str(DEFAULT_MODELS_CONFIG))
    parser.add_argument("--costs-config", default=str(DEFAULT_COSTS_CONFIG))
    parser.add_argument("--phase8-script", default=str(DEFAULT_PHASE8_SCRIPT))
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
            metrics_root=resolve_path(repo_root, args.metrics_root),
            model_selection_root=resolve_path(repo_root, args.model_selection_root),
            phase8_root=resolve_path(repo_root, args.phase8_root),
            profile_config=resolve_path(repo_root, args.profile_config),
            models_config=resolve_path(repo_root, args.models_config),
            costs_config=resolve_path(repo_root, args.costs_config),
            phase8_script=resolve_path(repo_root, args.phase8_script),
            max_folds=int(args.max_folds),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"model_output_status={summary['model_output_status']} "
        f"phase8_config_status={summary['phase8_config_status']} "
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
