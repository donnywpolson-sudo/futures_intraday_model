#!/usr/bin/env python3
"""Review ES 2026 P1 candidate raw conversion outputs without executing repairs."""

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

from scripts.validation import build_local_trade_es2026_p1_candidate_conversion_plan as conversion_plan  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_candidate_conversion_review"
STATUS_READY = "REVIEW_READY_ES2026_P1_CANDIDATE_CONVERSION_REVIEW"
STATUS_NO_GO = "NO_GO_ES2026_P1_CANDIDATE_CONVERSION_REVIEW"
DECISION_REVIEW_ONLY = "es2026_p1_candidate_conversion_review_only_no_execution"
DECISION_BLOCKED = "es2026_p1_candidate_conversion_review_blocked"

TARGET_MARKET = conversion_plan.TARGET_MARKET
TARGET_YEAR = conversion_plan.TARGET_YEAR
DEFAULT_REPAIR_REPORTS_ROOT = conversion_plan.DEFAULT_REPAIR_REPORTS_ROOT
FALSE_APPROVAL_FLAGS = conversion_plan.FALSE_APPROVAL_FLAGS
NEXT_COMMAND_NAMES = (
    "candidate_raw_quality_drilldown",
    "candidate_readiness_only_rerun_after_repair",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return conversion_plan.rel(path, repo_root)


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


def _expected_paths(repo_root: Path, families: Iterable[Mapping[str, Any]]) -> list[Path]:
    paths: list[Path] = []
    for family in families:
        raw_paths = family.get("expected_generated_artifacts")
        if isinstance(raw_paths, list):
            paths.extend(resolve_path(repo_root, str(path)) for path in raw_paths)
    return sorted(paths, key=lambda path: path.as_posix())


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
    except Exception as exc:  # pragma: no cover - defensive detail comes from runtime exception.
        return {}, f"unreadable JSON: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"JSON is not an object: {path.as_posix()}"
    return payload, None


def _next_families(repair_plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    names = set(NEXT_COMMAND_NAMES)
    families: list[Mapping[str, Any]] = []
    for item in repair_plan.get("plan_items", []):
        if not isinstance(item, Mapping):
            continue
        raw_families = item.get("command_families")
        if isinstance(raw_families, list):
            families.extend(
                family
                for family in raw_families
                if isinstance(family, Mapping) and family.get("name") in names
            )
    return families


def _conversion_review_failures(
    *,
    repo_root: Path,
    expected_paths: list[Path],
    candidate_raw_root: Path,
    repair_reports_root: Path,
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    detail: dict[str, Any] = {}
    expected_path_set = {rel(path, repo_root) for path in expected_paths}
    missing = [
        rel(path, repo_root)
        for path in expected_paths
        if not path.is_file() or path.stat().st_size <= 0
    ]
    if missing:
        failures.append("missing or empty expected outputs: " + ",".join(missing))
    parquet_path = candidate_raw_root / "ES" / "2026.parquet"
    if rel(parquet_path, repo_root) not in expected_path_set:
        failures.append("expected outputs do not include candidate ES 2026 parquet")
    audit_json_path = repair_reports_root / "candidate_raw_optional_schema_audit" / "ES_2026_optional_schema_audit.json"
    audit_payload, audit_error = _read_json_object(audit_json_path)
    if audit_error is not None:
        failures.append(audit_error)
    else:
        detail["audit_status"] = audit_payload.get("status")
        detail["audit_raw_root"] = audit_payload.get("raw_root")
        verdicts = audit_payload.get("verdicts")
        detail["audit_verdicts"] = verdicts if isinstance(verdicts, Mapping) else {}
        if audit_payload.get("status") != "PASS":
            failures.append(f"optional schema audit status is not PASS: {audit_payload.get('status')!r}")
        if audit_payload.get("raw_root") != candidate_raw_root.as_posix():
            failures.append("optional schema audit raw_root mismatch")
        if not isinstance(verdicts, Mapping):
            failures.append("optional schema audit verdicts missing")
        else:
            if verdicts.get("optional_status_readiness") != "PASS":
                failures.append("optional status readiness is not PASS")
            if verdicts.get("optional_statistics_readiness") != "PASS":
                failures.append("optional statistics readiness is not PASS")
    conversion_report_files = _existing_tree_files(
        repo_root,
        repair_reports_root / "candidate_raw_conversion",
        "reports",
    )
    audit_report_files = _existing_tree_files(
        repo_root,
        repair_reports_root / "candidate_raw_optional_schema_audit",
        "reports",
    )
    candidate_files = _existing_tree_files(repo_root, candidate_raw_root, "data")
    actual_files = sorted([*candidate_files, *conversion_report_files, *audit_report_files])
    unexpected = sorted(path for path in actual_files if path not in expected_path_set)
    if unexpected:
        failures.append("unexpected candidate conversion outputs: " + ",".join(unexpected))
    detail["expected_outputs"] = sorted(expected_path_set)
    detail["actual_outputs"] = actual_files
    detail["unexpected_outputs"] = unexpected
    return failures, detail


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Generate and review ES 2026 candidate conversion outputs before raw-quality or readiness planning."
    return (
        "Run the console-only ES 2026 candidate readiness plan gate, then approve or reject bounded "
        "candidate raw-quality drilldown and raw-alignment/readiness execution; "
        "do not rerun readiness, build causal data, labels, or features without separate approval."
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
    conversion_report = conversion_plan.build_report(
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
    conversion_summary = conversion_report["summary"]
    repair_report = repair_plan_gate.build_report(
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
    repair_summary = repair_report["summary"]
    conversion_families = [
        family for family in conversion_report.get("command_families", []) if isinstance(family, Mapping)
    ]
    expected_paths = _expected_paths(repo_root, conversion_families)
    expected_rel_paths = [rel(path, repo_root) for path in expected_paths]
    ignored_expected_paths = (
        _filter_ignored_expected_paths(expected_rel_paths, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _git_ignored_generated_paths(repo_root, expected_rel_paths)
    )
    unignored_expected_paths = sorted(set(expected_rel_paths) - set(ignored_expected_paths))
    review_failures, review_detail = (
        _conversion_review_failures(
            repo_root=repo_root,
            expected_paths=expected_paths,
            candidate_raw_root=candidate_raw_root,
            repair_reports_root=repair_reports_root,
        )
        if conversion_summary.get("status") == conversion_plan.STATUS_READY
        else (["candidate conversion plan is not ready"], {})
    )
    next_families = _next_families(repair_report)

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="candidate_conversion_plan_ready",
        passed=conversion_summary.get("status") == conversion_plan.STATUS_READY,
        observed=conversion_summary.get("status"),
        expected=conversion_plan.STATUS_READY,
        detail="Candidate conversion review must start from a ready candidate conversion plan.",
    )
    _check(
        checks,
        name="candidate_conversion_outputs_valid",
        passed=not review_failures,
        observed=review_failures,
        expected="candidate ES 2026 parquet and PASS optional schema audit outputs",
        detail="Review requires the bounded candidate conversion outputs and PASS optional schema audit.",
    )
    _check(
        checks,
        name="candidate_conversion_outputs_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="Reviewed candidate conversion outputs must remain ignored generated artifacts.",
    )
    _check(
        checks,
        name="next_repair_command_families_present",
        passed=len(next_families) == len(NEXT_COMMAND_NAMES),
        observed=sorted(str(family.get("name")) for family in next_families),
        expected=list(NEXT_COMMAND_NAMES),
        detail="The next raw-quality/readiness command families must remain available but not executed.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while reviewing candidate conversion.",
    )
    _check(
        checks,
        name="candidate_conversion_review_console_only_default",
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
            "decision": DECISION_BLOCKED if failures else DECISION_REVIEW_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "candidate_raw_root": rel(candidate_raw_root, repo_root),
            "repair_reports_root": rel(repair_reports_root, repo_root),
            "expected_candidate_output_count": len(expected_paths),
            "ignored_expected_candidate_output_count": len(ignored_expected_paths),
            "unignored_expected_candidate_output_count": len(unignored_expected_paths),
            "next_command_family_count": len(next_families),
            "generated_report_written": False,
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "expected_candidate_outputs": expected_rel_paths,
        "unignored_expected_candidate_outputs": unignored_expected_paths,
        "review_detail": review_detail,
        "next_command_families": next_families if not failures else [],
        "candidate_conversion_plan_summary": conversion_summary,
        "repair_plan_summary": repair_summary,
        "non_approval": {
            "scope": "ES 2026 P1 candidate conversion review only",
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
        f"expected_candidate_outputs={summary['expected_candidate_output_count']} "
        f"ignored_expected_candidate_outputs={summary['ignored_expected_candidate_output_count']} "
        f"unignored_expected_candidate_outputs={summary['unignored_expected_candidate_output_count']} "
        f"next_command_families={summary['next_command_family_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
