#!/usr/bin/env python3
"""Report-only gate for Phase 2 canonical promotion readiness."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "configs/data_manifest.yaml"
DEFAULT_CANDIDATE_ROOT = REPO_ROOT / "data/causal_base_candidates/broad_manifest_527_rebuild_v1"
DEFAULT_REPORTS_ROOT = REPO_ROOT / "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1"
DEFAULT_CANDIDATE_MANIFEST = DEFAULT_REPORTS_ROOT / "causal_base_manifest.json"
DEFAULT_CANDIDATE_VALIDATION = DEFAULT_REPORTS_ROOT / "causal_base_validation.json"
DEFAULT_MASTER_MATRIX = REPO_ROOT / "reports/data_manifest/master_data_health_matrix.json"
DEFAULT_JSON_OUT = (
    REPO_ROOT
    / "reports/data_audit/phase2_canonical_promotion_gate/"
    / "broad_manifest_527_rebuild_v1_promotion_gate.json"
)
DEFAULT_MARKDOWN_OUT = DEFAULT_JSON_OUT.with_suffix(".md")

STAGE = "phase2_canonical_promotion_gate"
CONDITIONAL_GO = "CONDITIONAL_GO_CONFIG_PROMOTION_CANDIDATE_460_ONLY"
PROMOTED_GO = "CONDITIONAL_GO_CANONICAL_PHASE2_460_ONLY"
NO_GO = "NO_GO_CANONICAL_PROMOTION"
EXPECTED_CANDIDATE_COUNT = 460
TARGET_CANONICAL_PATTERN = (
    "data/causal_base_candidates/broad_manifest_527_rebuild_v1/{market}/{year}.parquet"
)
FORBIDDEN_PAIR = ("6M", 2012)
FORBIDDEN_YEARS = (2025, 2026)
FALSE_APPROVAL_FLAGS = (
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "research_use_allowed",
    "live_or_paper_execution_approved",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


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


def _parquet_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("*.parquet"))


def _count_list(value: Any) -> int | None:
    if isinstance(value, list):
        return len(value)
    return None


def _git_status_lines(repo_root: Path, paths: Iterable[str]) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short", "--", *paths],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def evaluate_gate(
    *,
    repo_root: Path,
    manifest_path: Path,
    candidate_root: Path,
    reports_root: Path,
    candidate_manifest_path: Path,
    candidate_validation_path: Path,
    master_matrix_path: Path,
    expected_candidate_count: int = EXPECTED_CANDIDATE_COUNT,
    git_status_lines: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    manifest = read_yaml(manifest_path)
    candidate_manifest = read_json(candidate_manifest_path)
    candidate_validation = read_json(candidate_validation_path)
    master_matrix = read_json(master_matrix_path)

    checks: list[dict[str, Any]] = []
    candidate_root_rel = rel(candidate_root, repo_root)
    reports_root_rel = rel(reports_root, repo_root)
    canonical_pattern = str(
        ((manifest.get("canonical_paths") or {}).get("causal_parquet_pattern") or "")
    )
    canonical_config_promoted = canonical_pattern == TARGET_CANONICAL_PATTERN
    summary = master_matrix.get("summary") if isinstance(master_matrix.get("summary"), dict) else {}
    current_canonical = (
        summary.get("current_canonical_causal")
        if isinstance(summary.get("current_canonical_causal"), dict)
        else {}
    )

    parquet_paths = _parquet_paths(candidate_root)
    manifest_output_count = _count_list(candidate_manifest.get("outputs"))
    validation_file_count = _count_list(candidate_validation.get("files"))
    forbidden_pair_path = candidate_root / FORBIDDEN_PAIR[0] / f"{FORBIDDEN_PAIR[1]}.parquet"
    forbidden_year_counts = {
        str(year): len(list(candidate_root.rglob(f"{year}.parquet"))) if candidate_root.exists() else 0
        for year in FORBIDDEN_YEARS
    }
    status_paths = [
        candidate_root_rel,
        reports_root_rel,
        "data/raw",
        "data/dbn",
    ]
    status_lines = (
        list(git_status_lines)
        if git_status_lines is not None
        else _git_status_lines(repo_root, status_paths)
    )

    _check(
        checks,
        name="candidate_root_exists",
        passed=candidate_root.exists(),
        observed=candidate_root_rel,
        expected="existing directory",
        detail="Candidate Phase 2 output root must exist.",
    )
    _check(
        checks,
        name="reports_root_exists",
        passed=reports_root.exists(),
        observed=reports_root_rel,
        expected="existing directory",
        detail="Paired candidate reports root must exist.",
    )
    _check(
        checks,
        name="candidate_parquet_count",
        passed=len(parquet_paths) == expected_candidate_count,
        observed=len(parquet_paths),
        expected=expected_candidate_count,
        detail="Candidate root must contain exactly the approved built-not-promoted rows.",
    )
    _check(
        checks,
        name="manifest_status",
        passed=candidate_manifest.get("status") == "PASS",
        observed=candidate_manifest.get("status"),
        expected="PASS",
        detail="Candidate manifest must be PASS.",
    )
    _check(
        checks,
        name="validation_status",
        passed=candidate_validation.get("status") == "PASS",
        observed=candidate_validation.get("status"),
        expected="PASS",
        detail="Candidate validation must be PASS.",
    )
    _check(
        checks,
        name="manifest_output_count",
        passed=manifest_output_count == expected_candidate_count,
        observed=manifest_output_count,
        expected=expected_candidate_count,
        detail="Candidate manifest output list must match the approved row count.",
    )
    _check(
        checks,
        name="validation_file_count",
        passed=validation_file_count == expected_candidate_count,
        observed=validation_file_count,
        expected=expected_candidate_count,
        detail="Candidate validation file list must match the approved row count.",
    )
    _check(
        checks,
        name="forbidden_6m_2012_absent",
        passed=not forbidden_pair_path.exists(),
        observed=forbidden_pair_path.exists(),
        expected=False,
        detail="6M:2012 must remain fail-closed/excluded.",
    )
    for year, count in forbidden_year_counts.items():
        _check(
            checks,
            name=f"forbidden_{year}_absent",
            passed=count == 0,
            observed=count,
            expected=0,
            detail=f"{year} rows must remain holdout/forward only.",
        )
    _check(
        checks,
        name="candidate_paths_git_clean",
        passed=not status_lines,
        observed=status_lines,
        expected=[],
        detail="Candidate, paired reports, raw, and DBN artifact paths must have no tracked git changes.",
    )
    _check(
        checks,
        name="canonical_config_state_valid",
        passed=bool(canonical_pattern),
        observed=canonical_pattern,
        expected=f"{TARGET_CANONICAL_PATTERN} or pre-promotion alternate canonical path",
        detail="Canonical config path must be present; it may be pre-promotion or already promoted.",
    )

    failures = [check for check in checks if check["status"] != "PASS"]
    status = (PROMOTED_GO if canonical_config_promoted else CONDITIONAL_GO) if not failures else NO_GO
    output = {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": (
                "canonical_config_promoted_candidate_460_confirmed"
                if status == PROMOTED_GO
                else "candidate_ready_for_separate_config_promotion_review"
                if status == CONDITIONAL_GO
                else "canonical_promotion_blocked"
            ),
            "candidate_root": candidate_root_rel,
            "candidate_reports_root": reports_root_rel,
            "candidate_expected_count": expected_candidate_count,
            "candidate_parquet_count": len(parquet_paths),
            "candidate_manifest_status": candidate_manifest.get("status"),
            "candidate_validation_status": candidate_validation.get("status"),
            "manifest_output_count": manifest_output_count,
            "validation_file_count": validation_file_count,
            "forbidden_6m_2012_present": forbidden_pair_path.exists(),
            "forbidden_year_counts": forbidden_year_counts,
            "canonical_config_pattern": canonical_pattern,
            "target_canonical_pattern": TARGET_CANONICAL_PATTERN,
            "canonical_config_promoted": canonical_config_promoted,
            "current_canonical_causal_present": current_canonical.get("present_count"),
            "current_canonical_causal_missing": current_canonical.get("missing_count"),
            "current_canonical_causal_pattern": current_canonical.get("pattern"),
            "expected_rows": summary.get("expected_rows"),
            "git_status_paths": status_paths,
            "git_status_lines": status_lines,
            "git_status_clean": not status_lines,
            "data_mutation_performed": False,
            "config_mutation_performed": False,
            "reports_generated_only": True,
            "promotion_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "research_use_allowed": False,
            "live_or_paper_execution_approved": False,
            "failure_count": len(failures),
            "failures": [check["detail"] for check in failures],
        },
        "checks": checks,
    }
    return output


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Phase 2 Canonical Promotion Gate",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Status: `{summary['status']}`.",
        f"- Decision: `{summary['decision']}`.",
        f"- Candidate root: `{summary['candidate_root']}`.",
        f"- Candidate reports root: `{summary['candidate_reports_root']}`.",
        f"- Candidate parquet count: {summary['candidate_parquet_count']}/{summary['candidate_expected_count']}.",
        f"- Candidate manifest status: `{summary['candidate_manifest_status']}`.",
        f"- Candidate validation status: `{summary['candidate_validation_status']}`.",
        f"- Manifest output count: {summary['manifest_output_count']}.",
        f"- Validation file count: {summary['validation_file_count']}.",
        f"- Forbidden `6M:2012` present: `{str(summary['forbidden_6m_2012_present']).lower()}`.",
        f"- Forbidden year counts: `{json.dumps(summary['forbidden_year_counts'], sort_keys=True)}`.",
        "",
        "## Canonical Config Context",
        "",
        f"- Current config causal pattern: `{summary['canonical_config_pattern']}`.",
        f"- Candidate target pattern: `{summary['target_canonical_pattern']}`.",
        f"- Current canonical causal coverage: {summary['current_canonical_causal_present']}/{summary['expected_rows']}.",
        "- Config mutation performed: `false`.",
        "- Promotion performed: `false`.",
        "",
        "## Non-Approval Flags",
        "",
    ]
    for flag in FALSE_APPROVAL_FLAGS:
        lines.append(f"- `{flag}`: `{str(summary[flag]).lower()}`.")
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    for check in report["checks"]:
        lines.append(
            f"- `{check['name']}`: `{check['status']}` "
            f"(observed `{check['observed']}`, expected `{check['expected']}`)."
        )
    if summary["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in summary["failures"])
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--candidate-root", default=str(DEFAULT_CANDIDATE_ROOT))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    parser.add_argument("--candidate-manifest", default=str(DEFAULT_CANDIDATE_MANIFEST))
    parser.add_argument("--candidate-validation", default=str(DEFAULT_CANDIDATE_VALIDATION))
    parser.add_argument("--master-matrix", default=str(DEFAULT_MASTER_MATRIX))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--expected-candidate-count", type=int, default=EXPECTED_CANDIDATE_COUNT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    report = evaluate_gate(
        repo_root=repo_root,
        manifest_path=resolve_path(repo_root, args.manifest),
        candidate_root=resolve_path(repo_root, args.candidate_root),
        reports_root=resolve_path(repo_root, args.reports_root),
        candidate_manifest_path=resolve_path(repo_root, args.candidate_manifest),
        candidate_validation_path=resolve_path(repo_root, args.candidate_validation),
        master_matrix_path=resolve_path(repo_root, args.master_matrix),
        expected_candidate_count=args.expected_candidate_count,
    )
    write_report(
        report,
        resolve_path(repo_root, args.json_out),
        resolve_path(repo_root, args.markdown_out),
    )
    summary = report["summary"]
    print(
        "phase2_canonical_promotion_gate "
        f"status={summary['status']} "
        f"candidate_parquet_count={summary['candidate_parquet_count']} "
        f"manifest_status={summary['candidate_manifest_status']} "
        f"validation_status={summary['candidate_validation_status']} "
        f"failure_count={summary['failure_count']}"
    )
    return 0 if summary["status"] in {CONDITIONAL_GO, PROMOTED_GO} else 1


if __name__ == "__main__":
    raise SystemExit(main())
