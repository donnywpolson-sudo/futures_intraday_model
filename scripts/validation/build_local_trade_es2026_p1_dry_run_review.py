#!/usr/bin/env python3
"""Review generated ES 2026 P1 optional status/statistics dry-run plans."""

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

from scripts.validation import build_local_trade_es2026_p1_repair_plan as plan_gate


STAGE = "local_trade_es2026_p1_dry_run_review"
STATUS_READY = "REVIEW_READY_ES2026_P1_DRY_RUN_REVIEW"
STATUS_NO_GO = "NO_GO_ES2026_P1_DRY_RUN_REVIEW"
DECISION_REVIEW_ONLY = "es2026_p1_dry_run_review_only_no_execution"
DECISION_BLOCKED = "es2026_p1_dry_run_review_blocked"

TARGET_MARKET = plan_gate.TARGET_MARKET
TARGET_YEAR = plan_gate.TARGET_YEAR
TARGET_START = plan_gate.TARGET_START
TARGET_END = plan_gate.TARGET_END
TARGET_SCHEMAS = ("statistics", "status")
DEFAULT_REPAIR_REPORTS_ROOT = plan_gate.DEFAULT_REPAIR_REPORTS_ROOT

FALSE_APPROVAL_FLAGS = (
    "provider_download_approved",
    "cost_estimate_approved",
    "candidate_raw_write_approved",
    "readiness_rerun_approved",
    "accepted_warning_packet_approved",
    "exclusion_approved",
    "causal_base_repair_approved",
    "label_build_approved",
    "feature_matrix_build_approved",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "proof_scan_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "live_or_paper_execution_approved",
)


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


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


def _expected_plan_path(repair_reports_root: Path, schema: str) -> Path:
    return repair_reports_root / f"phase1a_{schema}" / "databento_download_plan_dry_run.json"


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
    if not (repo_root / ".git").exists():
        return candidates
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


def _read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing dry-run plan: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive detail comes from runtime exception.
        return {}, f"unreadable dry-run plan: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"dry-run plan is not a JSON object: {path.as_posix()}"
    return payload, None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _first_task(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    tasks = payload.get("tasks")
    if isinstance(tasks, list) and len(tasks) == 1 and isinstance(tasks[0], Mapping):
        return tasks[0]
    return {}


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


def _scope_failures(payload: Mapping[str, Any], schema: str) -> list[str]:
    failures: list[str] = []
    expected = {
        "run_kind": "dry_run",
        "mode": "download-dbn",
        "schema": schema,
        "start": TARGET_START,
        "end": TARGET_END,
        "universe": "custom",
        "product_count": 1,
        "task_count": 1,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            failures.append(f"{key}={payload.get(key)!r} != {expected_value!r}")
    if payload.get("products") != [TARGET_MARKET]:
        failures.append(f"products={payload.get('products')!r} != [{TARGET_MARKET!r}]")
    if payload.get("schemas") != [schema]:
        failures.append(f"schemas={payload.get('schemas')!r} != [{schema!r}]")
    task = _first_task(payload)
    if not task:
        failures.append("tasks must contain exactly one JSON object")
        return failures
    task_expected = {
        "product": TARGET_MARKET,
        "year": TARGET_YEAR,
        "schema": schema,
        "start": TARGET_START,
        "end": TARGET_END,
    }
    for key, expected_value in task_expected.items():
        if task.get(key) != expected_value:
            failures.append(f"task.{key}={task.get(key)!r} != {expected_value!r}")
    return failures


def _review_items(
    *,
    repo_root: Path,
    repair_reports_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for schema in TARGET_SCHEMAS:
        payload = payloads[schema]
        task = _first_task(payload)
        items.append(
            {
                "schema": schema,
                "market": TARGET_MARKET,
                "year": TARGET_YEAR,
                "plan_path": rel(_expected_plan_path(repair_reports_root, schema), repo_root),
                "run_kind": payload.get("run_kind"),
                "task_count": _as_int(payload.get("task_count")),
                "tasks": [
                    {
                        "product": task.get("product"),
                        "year": task.get("year"),
                        "schema": task.get("schema"),
                        "start": task.get("start"),
                        "end": task.get("end"),
                    }
                ],
                "review_status": "APPROVAL_REQUIRED_NOT_EXECUTED",
                "next_repair_use": (
                    "Use this dry-run plan only as bounded scope evidence before separately "
                    "approving any optional archive download, candidate raw conversion, or readiness rerun."
                ),
            }
        )
    return items


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Generate or repair the bounded ES 2026 status/statistics dry-run plans, then rerun this review gate."
    return (
        "Run the console-only ES 2026 optional archive availability diagnostic, then approve or reject "
        "the next bounded repair step; do not download providers, mutate data, convert candidate raw, "
        "or rerun readiness without approval."
    )


def build_report(
    *,
    repo_root: Path,
    repair_reports_root: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    payloads: dict[str, Mapping[str, Any]] = {}
    read_errors: dict[str, str] = {}
    scope_errors: dict[str, list[str]] = {}
    paths = {schema: _expected_plan_path(repair_reports_root, schema) for schema in TARGET_SCHEMAS}
    rel_paths = {schema: rel(path, repo_root) for schema, path in paths.items()}
    ignored_plan_paths = (
        _filter_ignored_expected_paths(rel_paths.values(), ignored_generated_paths)
        if ignored_generated_paths is not None
        else _git_ignored_generated_paths(repo_root, rel_paths.values())
    )
    unignored_plan_paths = sorted(set(rel_paths.values()) - set(ignored_plan_paths))
    for schema, path in paths.items():
        payload, error = _read_json_object(path)
        if error is not None:
            read_errors[schema] = error
            continue
        payloads[schema] = payload
        failures = _scope_failures(payload, schema)
        if failures:
            scope_errors[schema] = failures

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="expected_dry_run_plans_readable",
        passed=not read_errors and len(payloads) == len(TARGET_SCHEMAS),
        observed=read_errors,
        expected="readable status/statistics dry-run plan JSON files",
        detail="Dry-run review requires both generated dry-run plan files from the guarded wrapper.",
    )
    _check(
        checks,
        name="dry_run_plans_exact_es2026_scope",
        passed=not scope_errors and len(payloads) == len(TARGET_SCHEMAS),
        observed=scope_errors,
        expected="exact ES 2026 status/statistics one-task dry-run plans",
        detail="Dry-run plans must prove exact ES 2026 optional status/statistics scope before repair planning.",
    )
    _check(
        checks,
        name="dry_run_plans_ignored_by_git",
        passed=not unignored_plan_paths and len(ignored_plan_paths) == len(TARGET_SCHEMAS),
        observed=unignored_plan_paths,
        expected=[],
        detail="Generated dry-run plans must be ignored by git before review can pass.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while reviewing dry-run plans.",
    )
    _check(
        checks,
        name="review_gate_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally exposes no generated report output arguments.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    review_items = (
        _review_items(repo_root=repo_root, repair_reports_root=repair_reports_root, payloads=payloads)
        if not failures
        else []
    )
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_REVIEW_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "repair_reports_root": rel(repair_reports_root, repo_root),
            "expected_plan_count": len(TARGET_SCHEMAS),
            "readable_plan_count": len(payloads),
            "ignored_plan_count": len(ignored_plan_paths),
            "unignored_plan_count": len(unignored_plan_paths),
            "review_item_count": len(review_items),
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "review_items": review_items,
        "expected_plan_paths": rel_paths,
        "non_approval": {
            "scope": "ES 2026 P1 dry-run plan review only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--repair-reports-root", default=str(DEFAULT_REPAIR_REPORTS_ROOT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            repair_reports_root=resolve_path(repo_root, args.repair_reports_root),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"readable_plans={summary['readable_plan_count']} "
        f"ignored_plans={summary['ignored_plan_count']} "
        f"unignored_plans={summary['unignored_plan_count']} "
        f"review_items={summary['review_item_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
