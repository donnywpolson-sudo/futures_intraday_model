#!/usr/bin/env python3
"""Build a console-only ES 2026 P1 candidate readiness plan."""

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

from scripts.validation import build_local_trade_es2026_p1_candidate_conversion_review as conversion_review  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_candidate_readiness_plan"
STATUS_READY = "REVIEW_READY_ES2026_P1_CANDIDATE_READINESS_PLAN"
STATUS_NO_GO = "NO_GO_ES2026_P1_CANDIDATE_READINESS_PLAN"
DECISION_PLAN_ONLY = "es2026_p1_candidate_readiness_plan_only_no_execution"
DECISION_BLOCKED = "es2026_p1_candidate_readiness_plan_blocked"

TARGET_MARKET = conversion_review.TARGET_MARKET
TARGET_YEAR = conversion_review.TARGET_YEAR
DEFAULT_REPAIR_REPORTS_ROOT = conversion_review.DEFAULT_REPAIR_REPORTS_ROOT
DEFAULT_PROFILE = repair_plan_gate.DEFAULT_PROFILE
FALSE_APPROVAL_FLAGS = conversion_review.FALSE_APPROVAL_FLAGS


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return conversion_review.rel(path, repo_root)


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


def _git_ignored_generated_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
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


def _repair_next_families(review_report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    families: dict[str, Mapping[str, Any]] = {}
    for family in review_report.get("next_command_families", []):
        if isinstance(family, Mapping):
            name = str(family.get("name"))
            families[name] = family
    return families


def _candidate_raw_alignment_family(
    *,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    raw_alignment_report: Path,
) -> dict[str, Any]:
    reports_root = repair_reports_root / "candidate_raw_alignment"
    include_list = reports_root / "include_ES_2026.json"
    md_out = raw_alignment_report.with_suffix(".md")
    return {
        "name": "candidate_raw_dbn_alignment_audit",
        "command_family": "phase1c_raw_dbn_alignment_expected_only",
        "pre_run_artifacts": [
            {
                "path": include_list.as_posix(),
                "content": {"market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}]},
            }
        ],
        "command": (
            "python -m scripts.validation.audit_raw_dbn_alignment "
            f"--profile {DEFAULT_PROFILE} --dbn-root data/dbn "
            f"--raw-root {candidate_raw_root.as_posix()} --expected-only "
            f"--market-year-include-list {include_list.as_posix()} "
            f"--json-out {raw_alignment_report.as_posix()} "
            f"--md-out {md_out.as_posix()}"
        ),
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "raw_root": candidate_raw_root.as_posix(),
            "expected_only": True,
            "profile": DEFAULT_PROFILE,
        },
        "timeout_seconds": 180,
        "expected_generated_artifacts": [
            include_list.as_posix(),
            raw_alignment_report.as_posix(),
            md_out.as_posix(),
        ],
        "forbidden_patterns": list(repair_plan_gate.FORBIDDEN_PATTERNS),
        "stop_condition": (
            "Stop unless the include list is exactly ES 2026, the raw-alignment audit returns PASS, "
            "raw_root matches the candidate raw root, and generated artifacts remain unstaged."
        ),
        "approval_required_before_execution": True,
    }


def _readiness_family_with_alignment(
    family: Mapping[str, Any],
    *,
    raw_alignment_report: Path,
) -> dict[str, Any]:
    command_parts = str(family.get("command", "")).split()
    try:
        flag_index = command_parts.index("--raw-alignment-report")
    except ValueError:
        flag_index = -1
    if flag_index >= 0 and flag_index + 1 < len(command_parts):
        command_parts[flag_index + 1] = raw_alignment_report.as_posix()
    command = " ".join(command_parts)
    updated = dict(family)
    updated["command"] = command
    updated["required_preconditions"] = [
        "candidate raw ES 2026 exists and passed optional schema audit",
        "candidate raw-alignment report exists, is exact-scope ES 2026, and status is PASS",
        "no ES 2026 exclusion or accepted-warning packet has been applied",
    ]
    return updated


def _planned_families(
    *,
    review_report: Mapping[str, Any],
    repair_reports_root: Path,
    candidate_raw_root: Path,
    raw_alignment_report: Path,
) -> list[dict[str, Any]]:
    repair_families = _repair_next_families(review_report)
    families: list[dict[str, Any]] = []
    raw_quality = repair_families.get("candidate_raw_quality_drilldown")
    if raw_quality is not None:
        families.append(dict(raw_quality))
    families.append(
        _candidate_raw_alignment_family(
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            raw_alignment_report=raw_alignment_report,
        )
    )
    readiness = repair_families.get("candidate_readiness_only_rerun_after_repair")
    if readiness is not None:
        families.append(_readiness_family_with_alignment(readiness, raw_alignment_report=raw_alignment_report))
    return families


def _expected_generated_paths(repo_root: Path, families: Iterable[Mapping[str, Any]]) -> list[str]:
    paths: list[str] = []
    for family in families:
        raw_paths = family.get("expected_generated_artifacts")
        if isinstance(raw_paths, list):
            paths.extend(
                rel(resolve_path(repo_root, str(path)), repo_root)
                for path in raw_paths
                if str(path)
            )
    return sorted(set(paths))


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Generate and review ES 2026 candidate conversion outputs before candidate readiness planning."
    return (
        "Run the guarded ES 2026 candidate readiness wrapper, then review generated raw-quality, "
        "raw-alignment, and readiness outputs; do not build causal data, labels, or features without separate approval."
    )


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
    review_report = conversion_review.build_report(
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
        ignored_generated_paths=ignored_generated_paths,
    )
    review_summary = review_report["summary"]
    families = _planned_families(
        review_report=review_report,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    family_names = sorted(str(family.get("name")) for family in families)
    expected_paths = _expected_generated_paths(repo_root, families)
    ignored_paths = (
        _filter_ignored_expected_paths(expected_paths, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _git_ignored_generated_paths(repo_root, expected_paths)
    )
    unignored_paths = sorted(set(expected_paths) - set(ignored_paths))

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="candidate_conversion_review_ready",
        passed=review_summary.get("status") == conversion_review.STATUS_READY,
        observed=review_summary.get("status"),
        expected=conversion_review.STATUS_READY,
        detail="Candidate readiness planning must start from reviewed candidate conversion outputs.",
    )
    _check(
        checks,
        name="candidate_readiness_command_families_present",
        passed=set(family_names)
        == {
            "candidate_raw_quality_drilldown",
            "candidate_raw_dbn_alignment_audit",
            "candidate_readiness_only_rerun_after_repair",
        },
        observed=family_names,
        expected=[
            "candidate_raw_quality_drilldown",
            "candidate_raw_dbn_alignment_audit",
            "candidate_readiness_only_rerun_after_repair",
        ],
        detail="The plan must include raw-quality drilldown, candidate raw alignment, and readiness-only rerun steps.",
    )
    _check(
        checks,
        name="candidate_raw_root_under_data",
        passed=_path_under(repo_root, candidate_raw_root, "data"),
        observed=rel(candidate_raw_root, repo_root),
        expected="data/**",
        detail="Candidate raw inputs remain generated data artifacts.",
    )
    _check(
        checks,
        name="repair_reports_root_under_reports",
        passed=_path_under(repo_root, repair_reports_root, "reports"),
        observed=rel(repair_reports_root, repo_root),
        expected="reports/**",
        detail="Candidate readiness diagnostics must write only under reports/.",
    )
    _check(
        checks,
        name="candidate_readiness_expected_outputs_ignored_by_git",
        passed=not unignored_paths and len(ignored_paths) == len(expected_paths),
        observed=unignored_paths,
        expected=[],
        detail="Planned candidate readiness outputs must be ignored generated artifacts.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while planning candidate readiness.",
    )
    _check(
        checks,
        name="candidate_readiness_plan_console_only_default",
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
            "candidate_raw_root": rel(candidate_raw_root, repo_root),
            "repair_reports_root": rel(repair_reports_root, repo_root),
            "command_family_count": len(families),
            "expected_generated_output_count": len(expected_paths),
            "ignored_expected_generated_output_count": len(ignored_paths),
            "unignored_expected_generated_output_count": len(unignored_paths),
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "command_families": families if not failures else [],
        "expected_generated_artifacts": expected_paths,
        "unignored_expected_generated_artifacts": unignored_paths,
        "candidate_conversion_review_summary": review_summary,
        "non_approval": {
            "scope": "ES 2026 P1 candidate readiness plan only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-order-report", default=str(repair_plan_gate.DEFAULT_WORK_ORDER_REPORT))
    parser.add_argument("--drilldown-report", default=str(repair_plan_gate.DEFAULT_DRILLDOWN_REPORT))
    parser.add_argument("--checkpoint-jsonl", default=str(repair_plan_gate.DEFAULT_CHECKPOINT_JSONL))
    parser.add_argument("--repair-reports-root", default=str(DEFAULT_REPAIR_REPORTS_ROOT))
    parser.add_argument("--candidate-raw-root", default=str(repair_plan_gate.DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--output-root", default=str(repair_plan_gate.DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(repair_plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT))
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
        f"command_families={summary['command_family_count']} "
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
