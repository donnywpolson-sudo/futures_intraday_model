#!/usr/bin/env python3
"""Review completed ES 2026 downstream Phase 8 metrics without approving promotion."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_es2026_p1_downstream_metrics_gate as gate  # noqa: E402
from scripts.validation import run_local_trade_es2026_p1_downstream_metrics_build as metrics_runner  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_metrics_review"
STATUS_READY = "REVIEW_READY_ES2026_P1_DOWNSTREAM_METRICS_REVIEW"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_METRICS_REVIEW"
DECISION_REVIEW_ONLY = "es2026_p1_downstream_metrics_review_only_no_execution"
DECISION_BLOCKED = "es2026_p1_downstream_metrics_review_blocked"

TARGET_MARKET = gate.TARGET_MARKET
TARGET_YEAR = gate.TARGET_YEAR
DEFAULT_PROFILE = gate.DEFAULT_PROFILE
DEFAULT_MATRIX = gate.DEFAULT_MATRIX
DEFAULT_RUN = gate.DEFAULT_RUN
FALSE_APPROVAL_FLAGS = gate.FALSE_APPROVAL_FLAGS


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return gate.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return gate.rel(path, repo_root)


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
    gate._check(
        checks,
        name=name,
        passed=passed,
        observed=observed,
        expected=expected,
        detail=detail,
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
    return gate._git_ignored_paths(repo_root, paths)


def _filter_ignored_paths(expected_paths: Iterable[str], ignored_paths: Iterable[str]) -> list[str]:
    ignored = {_normalize(path) for path in ignored_paths}
    return sorted(path for path in expected_paths if _normalize(path) in ignored)


def _read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    return metrics_runner._read_json_object(path)


def _expected_metrics_artifacts(
    *,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
    run: str,
) -> list[Path]:
    return gate._expected_metrics_artifacts(
        metrics_root=metrics_root,
        model_selection_root=model_selection_root,
        phase8_root=phase8_root,
        run=run,
    )


def _existing_tree_files(repo_root: Path, root: Path, prefix: str) -> list[str]:
    return metrics_runner._existing_tree_files(repo_root, root, prefix)


def _review_detail(
    *,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
    run: str,
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    metrics_json, error = _read_json_object(metrics_root / f"{run}_metrics.json")
    if error:
        failures.append(error)
    selection_report, error = _read_json_object(model_selection_root / "model_selection_report.json")
    if error:
        failures.append(error)
    alpha_decision, error = _read_json_object(phase8_root / "alpha_promotion_decision.json")
    if error:
        failures.append(error)

    promotion_gate = metrics_json.get("promotion_gate")
    promotion_gate = promotion_gate if isinstance(promotion_gate, Mapping) else {}
    return (
        {
            "run": run,
            "research_policy_metrics_ready": metrics_json.get("research_policy_metrics_ready"),
            "research_alpha_ready": metrics_json.get("research_alpha_ready"),
            "model_promotion_allowed": metrics_json.get("model_promotion_allowed"),
            "promotion_blockers": promotion_gate.get("promotion_blockers"),
            "selection_status": selection_report.get("selection_status"),
            "selected_model_id": selection_report.get("selected_model_id"),
            "final_holdout_excluded_from_selection": selection_report.get(
                "final_holdout_excluded_from_selection"
            ),
            "alpha_promoted": alpha_decision.get("promoted"),
            "alpha_model_promotion_allowed": alpha_decision.get("model_promotion_allowed"),
            "alpha_used_final_holdout_for_tuning": alpha_decision.get(
                "used_final_holdout_for_tuning"
            ),
            "alpha_trading_semantics_changed": alpha_decision.get("trading_semantics_changed"),
        },
        failures,
    )


def _recommended_next(status: str, detail: Mapping[str, Any]) -> str:
    if status == STATUS_NO_GO:
        return (
            "Complete and verify the guarded ES 2026 Phase 8 metrics wrapper before "
            "reviewing promotion or proof decisions."
        )
    if detail.get("model_promotion_allowed") is True:
        return (
            "Review the completed ES 2026 Phase 8 diagnostics; any promotion, artifact freeze, "
            "proof scan, staging, commit, push, or live/paper action still requires a separate "
            "bounded approval gate."
        )
    return (
        "Review the completed ES 2026 Phase 8 diagnostics and blockers; do not promote, "
        "freeze artifacts, proof-scan, stage, commit, push, or run live/paper paths without "
        "a separate bounded approval gate."
    )


def build_report(
    *,
    repo_root: Path,
    profile: str,
    matrix: str,
    run: str,
    feature_output_root: Path,
    wfa_split_reports_root: Path,
    predictions_root: Path,
    model_reports_root: Path,
    metrics_root: Path,
    model_selection_root: Path,
    phase8_root: Path,
    profile_config: Path,
    models_config: Path,
    costs_config: Path,
    max_folds: int = gate.DEFAULT_MAX_FOLDS,
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
    expected_paths = _expected_metrics_artifacts(
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
    model_evidence = gate._model_output_evidence(
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
    output_failures = metrics_runner._validate_metrics_outputs(
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
    detail, detail_failures = _review_detail(
        metrics_root=metrics_root,
        model_selection_root=model_selection_root,
        phase8_root=phase8_root,
        run=run,
    )
    output_failures = [*output_failures, *detail_failures]

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="phase6_model_outputs_exact_es2026_ready",
        passed=model_evidence.get("status") == "PASS",
        observed=model_evidence,
        expected="valid ES 2026 model-smoke prediction parquet, manifest, and WFA report",
        detail="Metrics review must remain tied to the exact upstream model-smoke evidence.",
    )
    _check(
        checks,
        name="expected_metrics_artifacts_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="Reviewed metrics/model-selection reports must be ignored generated artifacts.",
    )
    _check(
        checks,
        name="expected_metrics_artifacts_present_for_review",
        passed=len(existing_expected_paths) == len(expected_rel_paths),
        observed=existing_expected_paths,
        expected=expected_rel_paths,
        detail="Review requires the full Phase 8 metrics/model-selection artifact set.",
    )
    _check(
        checks,
        name="phase8_metrics_outputs_valid",
        passed=not output_failures,
        observed=output_failures,
        expected="valid ES 2026 Phase 8 metrics/model-selection diagnostics",
        detail="Outputs must be exact-scope diagnostics with no final-holdout tuning or semantic changes.",
    )
    _check(
        checks,
        name="unexpected_phase8_outputs_absent",
        passed=not unexpected_outputs,
        observed=unexpected_outputs,
        expected=[],
        detail="Review may cover only the planned ES 2026 metrics/model-selection artifacts.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged during metrics review.",
    )
    _check(
        checks,
        name="downstream_metrics_review_console_only_default",
        passed=True,
        observed="no output writer and no subprocess execution",
        expected="review only",
        detail="This gate writes no reports, creates no metrics, and runs no Phase 8/proof/promotion command.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_REVIEW_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "profile": profile,
            "matrix": matrix,
            "run": run,
            "model_output_status": model_evidence.get("status"),
            "metrics_output_status": "FAIL" if output_failures else "PASS",
            "expected_generated_output_count": len(expected_rel_paths),
            "ignored_expected_generated_output_count": len(ignored_expected_paths),
            "unignored_expected_generated_output_count": len(unignored_expected_paths),
            "existing_expected_generated_output_count": len(existing_expected_paths),
            "generated_report_written": False,
            "generated_output_count": 0,
            "unexpected_generated_output_count": len(unexpected_outputs),
            "commands_executed": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status, detail),
            "research_policy_metrics_ready": detail.get("research_policy_metrics_ready"),
            "research_alpha_ready": detail.get("research_alpha_ready"),
            "model_promotion_allowed": detail.get("model_promotion_allowed"),
            "alpha_promoted": detail.get("alpha_promoted"),
            **_approval_flags(),
        },
        "checks": checks,
        "review_detail": detail,
        "source_evidence": {
            "model_outputs": model_evidence,
        },
        "expected_generated_artifacts": expected_rel_paths,
        "existing_expected_generated_artifacts": existing_expected_paths,
        "unignored_expected_generated_artifacts": unignored_expected_paths,
        "unexpected_generated_outputs": unexpected_outputs,
        "non_approval": {
            "scope": "ES 2026 downstream Phase 8 metrics review only",
            "generated_report_written": False,
            "generated_output_count": 0,
            "commands_executed": 0,
            "promotion_or_freeze_approved": False,
            "proof_scan_approved": False,
            **_approval_flags(),
        },
    }


def review_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    return {
        "stage": STAGE,
        "status": summary.get("status"),
        "market": summary.get("market"),
        "year": summary.get("year"),
        "profile": summary.get("profile"),
        "run": summary.get("run"),
        "model_output_status": summary.get("model_output_status"),
        "metrics_output_status": summary.get("metrics_output_status"),
        "research_policy_metrics_ready": summary.get("research_policy_metrics_ready"),
        "research_alpha_ready": summary.get("research_alpha_ready"),
        "model_promotion_allowed": summary.get("model_promotion_allowed"),
        "alpha_promoted": summary.get("alpha_promoted"),
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
            "unexpected_generated_output_count": summary.get("unexpected_generated_output_count"),
            "staged_generated_path_count": summary.get("staged_generated_path_count"),
        },
        "review_detail": report.get("review_detail", {}),
        "approval_gate": {},
        "non_approval": report.get("non_approval", {}),
        "recommended_next_action": summary.get("recommended_next_action"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--matrix", default=DEFAULT_MATRIX)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--feature-output-root", default=str(gate.DEFAULT_FEATURE_OUTPUT_ROOT))
    parser.add_argument("--wfa-split-reports-root", default=str(gate.DEFAULT_WFA_SPLIT_REPORTS_ROOT))
    parser.add_argument("--predictions-root", default=str(gate.DEFAULT_PREDICTIONS_ROOT))
    parser.add_argument("--model-reports-root", default=str(gate.DEFAULT_MODEL_REPORTS_ROOT))
    parser.add_argument("--metrics-root", default=str(gate.DEFAULT_METRICS_ROOT))
    parser.add_argument("--model-selection-root", default=str(gate.DEFAULT_MODEL_SELECTION_ROOT))
    parser.add_argument("--phase8-root", default=str(gate.DEFAULT_PHASE8_ROOT))
    parser.add_argument("--profile-config", default=str(gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--models-config", default=str(gate.DEFAULT_MODELS_CONFIG))
    parser.add_argument("--costs-config", default=str(gate.DEFAULT_COSTS_CONFIG))
    parser.add_argument("--max-folds", type=int, default=gate.DEFAULT_MAX_FOLDS)
    parser.add_argument("--print-review-json", action="store_true")
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
            wfa_split_reports_root=resolve_path(repo_root, args.wfa_split_reports_root),
            predictions_root=resolve_path(repo_root, args.predictions_root),
            model_reports_root=resolve_path(repo_root, args.model_reports_root),
            metrics_root=resolve_path(repo_root, args.metrics_root),
            model_selection_root=resolve_path(repo_root, args.model_selection_root),
            phase8_root=resolve_path(repo_root, args.phase8_root),
            profile_config=resolve_path(repo_root, args.profile_config),
            models_config=resolve_path(repo_root, args.models_config),
            costs_config=resolve_path(repo_root, args.costs_config),
            max_folds=int(args.max_folds),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"model_output_status={summary['model_output_status']} "
        f"metrics_output_status={summary['metrics_output_status']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"ignored_expected_generated_outputs={summary['ignored_expected_generated_output_count']} "
        f"unignored_expected_generated_outputs={summary['unignored_expected_generated_output_count']} "
        f"existing_expected_generated_outputs={summary['existing_expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"unexpected_generated_outputs={summary['unexpected_generated_output_count']} "
        f"commands_executed={summary['commands_executed']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_review_json:
        print(json.dumps(review_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
