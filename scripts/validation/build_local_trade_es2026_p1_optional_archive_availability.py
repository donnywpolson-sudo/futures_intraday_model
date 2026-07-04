#!/usr/bin/env python3
"""Review local optional DBN archive availability from ES 2026 P1 dry-run plans."""

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

from scripts.phase1A_download.download_databento_raw import (  # noqa: E402
    raw_file_manifest_path,
    validate_raw_file_manifest,
)
from scripts.validation import build_local_trade_es2026_p1_dry_run_review as dry_run_review  # noqa: E402


STAGE = "local_trade_es2026_p1_optional_archive_availability"
STATUS_READY = "REVIEW_READY_ES2026_P1_OPTIONAL_ARCHIVE_AVAILABILITY"
STATUS_NO_GO = "NO_GO_ES2026_P1_OPTIONAL_ARCHIVE_AVAILABILITY"
DECISION_DIAGNOSTIC_ONLY = "es2026_p1_optional_archive_availability_diagnostic_only"
DECISION_BLOCKED = "es2026_p1_optional_archive_availability_blocked"

TARGET_MARKET = dry_run_review.TARGET_MARKET
TARGET_YEAR = dry_run_review.TARGET_YEAR
TARGET_SCHEMAS = dry_run_review.TARGET_SCHEMAS
DEFAULT_REPAIR_REPORTS_ROOT = dry_run_review.DEFAULT_REPAIR_REPORTS_ROOT
FALSE_APPROVAL_FLAGS = dry_run_review.FALSE_APPROVAL_FLAGS


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return dry_run_review.rel(path, repo_root)


def _normalize_artifact_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _filter_ignored_expected_paths(expected_paths: Iterable[str], ignored_paths: Iterable[str]) -> list[str]:
    ignored = {_normalize_artifact_path(path) for path in ignored_paths}
    return sorted(path for path in expected_paths if _normalize_artifact_path(path) in ignored)


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


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


def _first_task(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1:
        return {}
    task = tasks[0]
    return task if isinstance(task, Mapping) else {}


def _plan_path(repair_reports_root: Path, schema: str) -> Path:
    return repair_reports_root / f"phase1a_{schema}" / "databento_download_plan_dry_run.json"


def _path_under(repo_root: Path, path: Path, prefix: str) -> bool:
    try:
        path.resolve().relative_to((repo_root / prefix).resolve())
    except ValueError:
        return False
    return True


def _non_empty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _read_manifest_payload(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(raw_file_manifest_path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _archive_status(*, archive_present: bool, manifest_present: bool, manifest_failures: list[str]) -> str:
    if not archive_present:
        return "LOCAL_ARCHIVE_MISSING"
    if not manifest_present:
        return "LOCAL_MANIFEST_MISSING"
    if manifest_failures:
        return "LOCAL_MANIFEST_INVALID"
    return "LOCAL_ARCHIVE_AND_MANIFEST_READY"


def _availability_items(
    *,
    repo_root: Path,
    repair_reports_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    failures: list[str] = []
    for schema in TARGET_SCHEMAS:
        task = _first_task(payloads[schema])
        output_value = task.get("output_path")
        if not output_value:
            failures.append(f"{schema} dry-run task missing output_path")
            continue
        archive_path = resolve_path(repo_root, str(output_value))
        if not _path_under(repo_root, archive_path, "data"):
            failures.append(f"{schema} planned archive path is outside data/: {archive_path.as_posix()}")
            continue
        manifest_path = raw_file_manifest_path(archive_path)
        archive_present = _non_empty_file(archive_path)
        manifest_present = _non_empty_file(manifest_path)
        manifest_failures = (
            validate_raw_file_manifest(
                archive_path,
                expected_schema=schema,
                expected_market=TARGET_MARKET,
                expected_year=TARGET_YEAR,
            )
            if archive_present and manifest_present
            else []
        )
        if (
            "manifest path mismatch" in manifest_failures
            and _read_manifest_payload(archive_path).get("path") == rel(archive_path, repo_root)
        ):
            manifest_failures.remove("manifest path mismatch")
        items.append(
            {
                "schema": schema,
                "market": TARGET_MARKET,
                "year": TARGET_YEAR,
                "plan_path": rel(_plan_path(repair_reports_root, schema), repo_root),
                "archive_path": rel(archive_path, repo_root),
                "manifest_path": rel(manifest_path, repo_root),
                "archive_present": archive_present,
                "archive_size_bytes": archive_path.stat().st_size if archive_present else 0,
                "manifest_present": manifest_present,
                "manifest_valid": manifest_present and not manifest_failures,
                "manifest_failures": manifest_failures,
                "availability_status": _archive_status(
                    archive_present=archive_present,
                    manifest_present=manifest_present,
                    manifest_failures=manifest_failures,
                ),
            }
        )
    return items, failures


def _ignored_generated_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    return dry_run_review._git_ignored_generated_paths(repo_root, paths)  # noqa: SLF001


def _recommended_next(status: str, *, ready_count: int, planned_count: int) -> str:
    if status == STATUS_NO_GO:
        return "Generate and review exact ES 2026 status/statistics dry-run plans before archive availability diagnostics."
    if ready_count == planned_count:
        return (
            "Run the console-only ES 2026 candidate raw conversion plan gate using local optional "
            "archives only; do not write candidate raw or rerun readiness without separate approval."
        )
    return (
        "Approve or reject a bounded ES 2026 optional archive acquisition or provider-cost diagnostic; "
        "do not download providers, mutate data, convert candidate raw, or rerun readiness without approval."
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
    dry_run_report = dry_run_review.build_report(
        repo_root=repo_root,
        repair_reports_root=repair_reports_root,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_paths,
        ignored_generated_paths=ignored_generated_paths,
    )
    dry_run_summary = dry_run_report["summary"]

    payloads: dict[str, Mapping[str, Any]] = {}
    read_errors: dict[str, str] = {}
    if dry_run_summary.get("status") == dry_run_review.STATUS_READY:
        for schema in TARGET_SCHEMAS:
            payload, error = _read_json_object(_plan_path(repair_reports_root, schema))
            if error is not None:
                read_errors[schema] = error
                continue
            payloads[schema] = payload

    availability_items, item_failures = (
        _availability_items(
            repo_root=repo_root,
            repair_reports_root=repair_reports_root,
            payloads=payloads,
        )
        if len(payloads) == len(TARGET_SCHEMAS)
        else ([], [])
    )
    ready_count = sum(
        1
        for item in availability_items
        if item["availability_status"] == "LOCAL_ARCHIVE_AND_MANIFEST_READY"
    )
    missing_archive_count = sum(
        1 for item in availability_items if item["availability_status"] == "LOCAL_ARCHIVE_MISSING"
    )
    missing_manifest_count = sum(
        1 for item in availability_items if item["availability_status"] == "LOCAL_MANIFEST_MISSING"
    )
    invalid_manifest_count = sum(
        1 for item in availability_items if item["availability_status"] == "LOCAL_MANIFEST_INVALID"
    )
    planned_generated_paths = sorted(
        {
            path
            for item in availability_items
            for path in (str(item.get("archive_path") or ""), str(item.get("manifest_path") or ""))
            if path
        }
    )
    ignored_paths = (
        _filter_ignored_expected_paths(planned_generated_paths, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _ignored_generated_paths(repo_root, planned_generated_paths)
    )
    unignored_paths = sorted(set(planned_generated_paths) - set(ignored_paths))

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="dry_run_review_ready",
        passed=dry_run_summary.get("status") == dry_run_review.STATUS_READY,
        observed=dry_run_summary.get("status"),
        expected=dry_run_review.STATUS_READY,
        detail="Optional archive availability diagnostics must start from reviewed exact ES 2026 dry-run plans.",
    )
    _check(
        checks,
        name="dry_run_plans_reloaded",
        passed=not read_errors and len(payloads) == len(TARGET_SCHEMAS),
        observed=read_errors,
        expected="readable status/statistics dry-run plans",
        detail="The diagnostic must inspect the same generated dry-run plan files it is reviewing.",
    )
    _check(
        checks,
        name="planned_archive_paths_under_data",
        passed=not item_failures and len(availability_items) == len(TARGET_SCHEMAS),
        observed=item_failures,
        expected="status/statistics planned output_path entries under data/",
        detail="Planned optional DBN archive paths must come from exact dry-run tasks and stay under data/.",
    )
    _check(
        checks,
        name="planned_archive_artifacts_ignored_by_git",
        passed=not unignored_paths and len(ignored_paths) == len(planned_generated_paths),
        observed=unignored_paths,
        expected=[],
        detail="Planned optional DBN archive and manifest paths must be ignored generated artifacts.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while checking availability.",
    )
    _check(
        checks,
        name="availability_gate_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally exposes no generated report output arguments.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    failure_names = [str(check["name"]) for check in failures]
    status = STATUS_NO_GO if failures else STATUS_READY
    planned_count = len(availability_items)
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_DIAGNOSTIC_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "repair_reports_root": rel(repair_reports_root, repo_root),
            "planned_archive_count": planned_count,
            "planned_generated_artifact_count": len(planned_generated_paths),
            "ignored_planned_generated_artifact_count": len(ignored_paths),
            "unignored_planned_generated_artifact_count": len(unignored_paths),
            "local_archive_ready_count": ready_count,
            "missing_archive_count": missing_archive_count,
            "missing_manifest_count": missing_manifest_count,
            "invalid_manifest_count": invalid_manifest_count,
            "all_optional_archives_reusable": status == STATUS_READY and ready_count == planned_count,
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "failure_names": failure_names,
            "recommended_next_action": _recommended_next(
                status,
                ready_count=ready_count,
                planned_count=planned_count,
            ),
            **_approval_flags(),
        },
        "checks": checks,
        "availability_items": availability_items,
        "planned_generated_artifacts": planned_generated_paths,
        "unignored_planned_generated_artifacts": unignored_paths,
        "dry_run_review_summary": dry_run_summary,
        "dry_run_review_checks": dry_run_report.get("checks", []),
        "non_approval": {
            "scope": "ES 2026 P1 optional archive availability diagnostic only",
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
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"planned_archives={summary['planned_archive_count']} "
        f"planned_generated_artifacts={summary['planned_generated_artifact_count']} "
        f"ignored_planned_generated_artifacts={summary['ignored_planned_generated_artifact_count']} "
        f"unignored_planned_generated_artifacts={summary['unignored_planned_generated_artifact_count']} "
        f"local_ready={summary['local_archive_ready_count']} "
        f"missing_archives={summary['missing_archive_count']} "
        f"missing_manifests={summary['missing_manifest_count']} "
        f"invalid_manifests={summary['invalid_manifest_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']} "
        f"failure_names={','.join(summary['failure_names']) or 'none'} "
        f"recommended_next_action={summary['recommended_next_action']!r}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
