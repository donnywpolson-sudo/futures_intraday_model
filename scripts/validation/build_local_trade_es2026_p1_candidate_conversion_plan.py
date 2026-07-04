#!/usr/bin/env python3
"""Build a console-only ES 2026 P1 candidate raw conversion plan."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_es2026_p1_optional_archive_availability as availability_gate  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_candidate_conversion_plan"
STATUS_READY = "REVIEW_READY_ES2026_P1_CANDIDATE_CONVERSION_PLAN"
STATUS_NO_GO = "NO_GO_ES2026_P1_CANDIDATE_CONVERSION_PLAN"
DECISION_PLAN_ONLY = "es2026_p1_candidate_conversion_plan_only_no_execution"
DECISION_BLOCKED = "es2026_p1_candidate_conversion_plan_blocked"

TARGET_MARKET = plan_gate.TARGET_MARKET
TARGET_YEAR = plan_gate.TARGET_YEAR
DEFAULT_REPAIR_REPORTS_ROOT = plan_gate.DEFAULT_REPAIR_REPORTS_ROOT
FALSE_APPROVAL_FLAGS = plan_gate.FALSE_APPROVAL_FLAGS
REQUIRED_COMMAND_NAMES = (
    "candidate_raw_convert_with_required_optional_enrichment",
    "candidate_raw_optional_schema_audit",
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


def _path_under(repo_root: Path, path: Path, prefix: str) -> bool:
    try:
        path.resolve().relative_to((repo_root / prefix).resolve())
    except ValueError:
        return False
    return True


def _command_families(plan_report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    families: list[Mapping[str, Any]] = []
    for item in plan_report.get("plan_items", []):
        if not isinstance(item, Mapping):
            continue
        raw_families = item.get("command_families")
        if isinstance(raw_families, list):
            families.extend(family for family in raw_families if isinstance(family, Mapping))
    return families


def _selected_families(plan_report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    names = set(REQUIRED_COMMAND_NAMES)
    return [family for family in _command_families(plan_report) if family.get("name") in names]


def _approval_required_count(families: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for family in families if family.get("approval_required_before_execution") is True)


def _expected_generated_paths(repo_root: Path, families: Iterable[Mapping[str, Any]]) -> list[str]:
    paths: list[str] = []
    for family in families:
        raw_paths = family.get("expected_generated_artifacts")
        if isinstance(raw_paths, list):
            paths.extend(rel(resolve_path(repo_root, str(path)), repo_root) for path in raw_paths if str(path))
    return sorted(set(paths))


def _ignored_generated_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    return availability_gate._ignored_generated_paths(repo_root, paths)  # noqa: SLF001


def _recommended_next(status: str, *, availability_summary: Mapping[str, Any]) -> str:
    if status == STATUS_READY:
        return (
            "Approve or reject bounded ES 2026 candidate raw conversion plus optional schema audit execution; "
            "do not rerun readiness, build causal data, labels, or features without separate approval."
        )
    if availability_summary.get("status") != availability_gate.STATUS_READY:
        return "Generate and review exact ES 2026 status/statistics dry-run plans before candidate conversion planning."
    if not availability_summary.get("all_optional_archives_reusable"):
        return (
            "Resolve missing or invalid local ES 2026 optional archives before candidate conversion planning; "
            "provider downloads or cost diagnostics require separate approval."
        )
    return "Resolve failed candidate conversion planning checks before execution approval."


def build_report(
    *,
    repo_root: Path,
    work_order_report: Path,
    drilldown_report: Path,
    checkpoint_jsonl: Path,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    output_root: Path,
    raw_alignment_report: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    availability_report = availability_gate.build_report(
        repo_root=repo_root,
        repair_reports_root=repair_reports_root,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_paths,
        ignored_generated_paths=ignored_generated_paths,
    )
    availability_summary = availability_report["summary"]
    repair_plan_report = plan_gate.build_report(
        repo_root=repo_root,
        work_order_report=work_order_report,
        drilldown_report=drilldown_report,
        checkpoint_jsonl=checkpoint_jsonl,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc=generated_at_utc,
        staged_generated_paths=staged_paths,
    )
    repair_plan_summary = repair_plan_report["summary"]
    families = _selected_families(repair_plan_report)
    family_names = sorted(str(family.get("name")) for family in families)
    expected_paths = _expected_generated_paths(repo_root, families)
    ignored_paths = (
        _filter_ignored_expected_paths(expected_paths, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _ignored_generated_paths(repo_root, expected_paths)
    )
    unignored_paths = sorted(set(expected_paths) - set(ignored_paths))

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="repair_plan_ready",
        passed=repair_plan_summary.get("status") == plan_gate.STATUS_READY,
        observed=repair_plan_summary.get("status"),
        expected=plan_gate.STATUS_READY,
        detail="Candidate conversion planning must start from the ES 2026 P1 repair plan gate.",
    )
    _check(
        checks,
        name="optional_archives_reusable",
        passed=availability_summary.get("status") == availability_gate.STATUS_READY
        and availability_summary.get("all_optional_archives_reusable") is True,
        observed={
            "status": availability_summary.get("status"),
            "all_optional_archives_reusable": availability_summary.get("all_optional_archives_reusable"),
            "missing_archive_count": availability_summary.get("missing_archive_count"),
            "missing_manifest_count": availability_summary.get("missing_manifest_count"),
            "invalid_manifest_count": availability_summary.get("invalid_manifest_count"),
        },
        expected="reviewed local ES 2026 status/statistics archives and manifests are reusable",
        detail="Candidate raw conversion is only plan-ready when local optional DBN archives are already valid.",
    )
    _check(
        checks,
        name="candidate_conversion_command_families_present",
        passed=set(REQUIRED_COMMAND_NAMES) <= set(family_names),
        observed=family_names,
        expected=list(REQUIRED_COMMAND_NAMES),
        detail="The repair plan must expose both candidate conversion and optional schema audit command families.",
    )
    _check(
        checks,
        name="candidate_commands_remain_approval_required",
        passed=_approval_required_count(families) == len(REQUIRED_COMMAND_NAMES),
        observed=_approval_required_count(families),
        expected=len(REQUIRED_COMMAND_NAMES),
        detail="This gate may plan candidate conversion only; execution remains approval-gated.",
    )
    _check(
        checks,
        name="candidate_raw_root_under_data",
        passed=_path_under(repo_root, candidate_raw_root, "data"),
        observed=rel(candidate_raw_root, repo_root),
        expected="data/**",
        detail="Candidate conversion output must stay under data/ and remain generated.",
    )
    _check(
        checks,
        name="repair_reports_root_under_reports",
        passed=_path_under(repo_root, repair_reports_root, "reports"),
        observed=rel(repair_reports_root, repo_root),
        expected="reports/**",
        detail="Candidate conversion audit reports must stay under reports/.",
    )
    _check(
        checks,
        name="candidate_expected_outputs_ignored_by_git",
        passed=not unignored_paths and len(ignored_paths) == len(expected_paths),
        observed=unignored_paths,
        expected=[],
        detail="Planned candidate raw conversion outputs must be ignored generated artifacts.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while planning candidate conversion.",
    )
    _check(
        checks,
        name="candidate_conversion_plan_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate intentionally exposes no generated report output arguments.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_PLAN_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "repair_reports_root": rel(repair_reports_root, repo_root),
            "candidate_raw_root": rel(candidate_raw_root, repo_root),
            "selected_command_family_count": len(families),
            "approval_required_command_count": _approval_required_count(families),
            "expected_generated_output_count": len(expected_paths),
            "ignored_expected_generated_output_count": len(ignored_paths),
            "unignored_expected_generated_output_count": len(unignored_paths),
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(
                status,
                availability_summary=availability_summary,
            ),
            **_approval_flags(),
        },
        "checks": checks,
        "command_families": families if not failures else [],
        "expected_generated_artifacts": expected_paths,
        "unignored_expected_generated_artifacts": unignored_paths,
        "availability_summary": availability_summary,
        "availability_items": availability_report.get("availability_items", []),
        "repair_plan_summary": repair_plan_summary,
        "non_approval": {
            "scope": "ES 2026 P1 candidate raw conversion plan only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-order-report", default=str(plan_gate.DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--drilldown-report", default=str(plan_gate.DEFAULT_DRILLDOWN_REPORT))
    parser.add_argument("--checkpoint-jsonl", default=str(plan_gate.DEFAULT_CHECKPOINT_JSONL))
    parser.add_argument("--repair-reports-root", default=str(DEFAULT_REPAIR_REPORTS_ROOT))
    parser.add_argument("--candidate-raw-root", default=str(plan_gate.DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--output-root", default=str(plan_gate.DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            work_order_report=resolve_path(repo_root, args.work_order_report),
            drilldown_report=resolve_path(repo_root, args.drilldown_report),
            checkpoint_jsonl=resolve_path(repo_root, args.checkpoint_jsonl),
            repair_reports_root=resolve_path(repo_root, args.repair_reports_root),
            candidate_raw_root=resolve_path(repo_root, args.candidate_raw_root),
            output_root=resolve_path(repo_root, args.output_root),
            raw_alignment_report=resolve_path(repo_root, args.raw_alignment_report),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"command_families={summary['selected_command_family_count']} "
        f"approval_required_commands={summary['approval_required_command_count']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"ignored_expected_generated_outputs={summary['ignored_expected_generated_output_count']} "
        f"unignored_expected_generated_outputs={summary['unignored_expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
