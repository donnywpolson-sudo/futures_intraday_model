#!/usr/bin/env python3
"""Read-only current-baseline trust check for the Phase 2 manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import check_phase2_460_audit_readiness as scope_gate


STATUS_GO = "TRUSTED_CURRENT_BASELINE_BY_MATERIAL_HASHES"
STATUS_NO_GO = "NO_GO_MATERIAL_HASH_MISMATCH"
WARN_GIT_COMMIT_STALE = "WARN_GIT_COMMIT_STALE_BUT_MATERIAL_HASHES_MATCH"


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


def _warn(
    warnings: list[dict[str, Any]],
    *,
    name: str,
    code: str,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    warnings.append(
        {
            "name": name,
            "code": code,
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _hash_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(path): str(digest).lower()
        for path, digest in value.items()
        if isinstance(path, str) and isinstance(digest, str)
    }


def _manifest_outputs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _output_paths(outputs: Iterable[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for output in outputs:
        output_path = output.get("output_path")
        if isinstance(output_path, str):
            paths.add(output_path)
    return paths


def _input_paths(outputs: Iterable[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for output in outputs:
        input_path = output.get("input_path")
        if isinstance(input_path, str):
            paths.add(input_path)
    return paths


def _hash_failures(repo_root: Path, hash_map: dict[str, str]) -> tuple[list[str], list[dict[str, str]]]:
    missing: list[str] = []
    mismatches: list[dict[str, str]] = []
    for rel_path, expected_hash in sorted(hash_map.items()):
        path = scope_gate.resolve_path(repo_root, rel_path)
        if not path.exists():
            missing.append(rel_path)
            continue
        observed_hash = scope_gate.sha256_file(path)
        if observed_hash.lower() != expected_hash.lower():
            mismatches.append(
                {
                    "path": rel_path,
                    "observed": observed_hash.lower(),
                    "expected": expected_hash.lower(),
                }
            )
    return missing, mismatches


def evaluate_trust(
    *,
    repo_root: Path,
    data_manifest_path: Path,
    canonical_root: Path,
    reports_root: Path,
    phase2_manifest_path: Path,
    phase2_validation_path: Path,
    profile_config_path: Path,
    build_script_path: Path,
    expected_count: int = scope_gate.EXPECTED_CANONICAL_COUNT,
    feature_cols: Iterable[str] | None = None,
    git_head: str | None = None,
    staged_names: list[str] | None = None,
    scoped_status_lines: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    phase2_manifest = scope_gate.read_json(phase2_manifest_path)
    phase2_validation = scope_gate.read_json(phase2_validation_path)
    scope_report = scope_gate.evaluate_readiness(
        repo_root=repo_root,
        data_manifest_path=data_manifest_path,
        canonical_root=canonical_root,
        reports_root=reports_root,
        phase2_manifest_path=phase2_manifest_path,
        phase2_validation_path=phase2_validation_path,
        profile_config_path=profile_config_path,
        build_script_path=build_script_path,
        expected_count=expected_count,
        feature_cols=feature_cols,
        git_head=git_head,
        staged_names=staged_names,
        scoped_status_lines=scoped_status_lines,
        generated_at_utc=generated_at_utc,
    )

    current_head = git_head or scope_gate.run_git(repo_root, ["rev-parse", "HEAD"])[0]
    current_script_hash = scope_gate.sha256_file(build_script_path) if build_script_path.exists() else None
    current_config_hash = scope_gate.sha256_file(profile_config_path) if profile_config_path.exists() else None
    input_hashes = _hash_map(phase2_manifest.get("input_file_hashes"))
    output_hashes = _hash_map(phase2_manifest.get("output_file_hashes"))
    outputs = _manifest_outputs(phase2_manifest.get("outputs"))
    output_paths = _output_paths(outputs)
    input_paths = _input_paths(outputs)
    validation_summary = (
        phase2_validation.get("summary")
        if isinstance(phase2_validation.get("summary"), dict)
        else {}
    )
    validation_file_count = len(phase2_validation.get("files") or []) if isinstance(phase2_validation.get("files"), list) else None

    input_missing, input_mismatches = _hash_failures(repo_root, input_hashes)
    output_missing, output_mismatches = _hash_failures(repo_root, output_hashes)
    canonical_root_rel = scope_gate.rel(canonical_root, repo_root)
    filesystem_output_paths = {
        scope_gate.rel(path, repo_root)
        for path in sorted(canonical_root.rglob("*.parquet"))
    } if canonical_root.exists() else set()

    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    _check(
        checks,
        name="scope_gate_passed",
        passed=scope_report["summary"]["status"] == scope_gate.STATUS_GO,
        observed=scope_report["summary"]["status"],
        expected=scope_gate.STATUS_GO,
        detail="Trust reconciliation is valid only when the approved 460-row scope gate passes.",
    )
    _check(
        checks,
        name="manifest_script_hash_matches_current",
        passed=phase2_manifest.get("script_hash") == current_script_hash,
        observed=phase2_manifest.get("script_hash"),
        expected=current_script_hash,
        detail="Builder script must match the script hash recorded in the Phase 2 manifest.",
    )
    _check(
        checks,
        name="manifest_config_hash_matches_current",
        passed=phase2_manifest.get("config_hash") == current_config_hash,
        observed=phase2_manifest.get("config_hash"),
        expected=current_config_hash,
        detail="Profile config must match the config hash recorded in the Phase 2 manifest.",
    )
    _check(
        checks,
        name="manifest_input_hash_count",
        passed=len(input_hashes) == expected_count,
        observed=len(input_hashes),
        expected=expected_count,
        detail="Manifest must provide exactly one raw input hash for each approved canonical file.",
    )
    _check(
        checks,
        name="manifest_output_hash_count",
        passed=len(output_hashes) == expected_count,
        observed=len(output_hashes),
        expected=expected_count,
        detail="Manifest must provide exactly one output hash for each approved canonical file.",
    )
    _check(
        checks,
        name="manifest_outputs_have_input_hashes",
        passed=input_paths == set(input_hashes),
        observed={
            "outputs_without_input_hash": sorted(input_paths - set(input_hashes))[:20],
            "input_hashes_without_output": sorted(set(input_hashes) - input_paths)[:20],
        },
        expected="manifest outputs input paths match input_file_hashes keys",
        detail="The manifest hash set must reconcile to the included output rows, not unrelated raw files.",
    )
    _check(
        checks,
        name="manifest_outputs_have_output_hashes",
        passed=output_paths == set(output_hashes),
        observed={
            "outputs_without_output_hash": sorted(output_paths - set(output_hashes))[:20],
            "output_hashes_without_output": sorted(set(output_hashes) - output_paths)[:20],
        },
        expected="manifest outputs output paths match output_file_hashes keys",
        detail="The output hash set must reconcile to the included 460 canonical outputs.",
    )
    _check(
        checks,
        name="filesystem_outputs_match_manifest_hash_paths",
        passed=filesystem_output_paths == set(output_hashes),
        observed={
            "filesystem_only": sorted(filesystem_output_paths - set(output_hashes))[:20],
            "manifest_only": sorted(set(output_hashes) - filesystem_output_paths)[:20],
        },
        expected="filesystem canonical parquet paths match output_file_hashes keys",
        detail="The current canonical filesystem must match the manifest hash paths.",
    )
    _check(
        checks,
        name="input_paths_under_raw_root",
        passed=all(path.startswith("data/raw/") for path in input_hashes),
        observed=sorted(path for path in input_hashes if not path.startswith("data/raw/"))[:20],
        expected=[],
        detail="Manifest input hash paths must stay inside data/raw.",
    )
    _check(
        checks,
        name="output_paths_under_canonical_root",
        passed=all(path.startswith(f"{scope_gate.CANONICAL_ROOT_REL}/") for path in output_hashes),
        observed=sorted(path for path in output_hashes if not path.startswith(f"{scope_gate.CANONICAL_ROOT_REL}/"))[:20],
        expected=[],
        detail="Manifest output hash paths must stay inside the approved canonical root.",
    )
    _check(
        checks,
        name="current_input_hashes_match_manifest",
        passed=not input_missing and not input_mismatches,
        observed={"missing": input_missing[:20], "mismatches": input_mismatches[:20]},
        expected={"missing": [], "mismatches": []},
        detail="Current raw input files must match manifest input hashes.",
    )
    _check(
        checks,
        name="current_output_hashes_match_manifest",
        passed=not output_missing and not output_mismatches,
        observed={"missing": output_missing[:20], "mismatches": output_mismatches[:20]},
        expected={"missing": [], "mismatches": []},
        detail="Current canonical output files must match manifest output hashes.",
    )
    _check(
        checks,
        name="market_year_include_count",
        passed=phase2_manifest.get("market_year_include_count") == expected_count,
        observed=phase2_manifest.get("market_year_include_count"),
        expected=expected_count,
        detail="Manifest included market-year count must equal the approved 460-row scope.",
    )
    _check(
        checks,
        name="validation_count_consistency",
        passed=(
            validation_file_count == expected_count
            and validation_summary.get("file_count") == expected_count
            and validation_summary.get("pass_count") == expected_count
            and validation_summary.get("fail_count") == 0
        ),
        observed={
            "files": validation_file_count,
            "file_count": validation_summary.get("file_count"),
            "pass_count": validation_summary.get("pass_count"),
            "fail_count": validation_summary.get("fail_count"),
        },
        expected={
            "files": expected_count,
            "file_count": expected_count,
            "pass_count": expected_count,
            "fail_count": 0,
        },
        detail="Validation report must still claim exactly 460 passing files and zero failures.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    if phase2_manifest.get("git_commit") != current_head:
        _warn(
            warnings,
            name="manifest_git_commit_stale",
            code=WARN_GIT_COMMIT_STALE,
            observed=phase2_manifest.get("git_commit"),
            expected=current_head,
            detail="Manifest commit is stale; material trust depends on script/config/input/output hashes and counts.",
        )

    status = STATUS_GO if not failures else STATUS_NO_GO
    return {
        "summary": {
            "stage": "phase2_manifest_trust_reconciliation",
            "generated_at_utc": generated_at_utc or scope_gate.utc_now(),
            "status": status,
            "approved_scope": "promoted canonical broad_manifest_527_rebuild_v1 460-row Phase 2 only",
            "canonical_root": canonical_root_rel,
            "expected_count": expected_count,
            "current_git_head": current_head,
            "manifest_git_commit": phase2_manifest.get("git_commit"),
            "manifest_generated_at": phase2_manifest.get("generated_at"),
            "script_hash_match": phase2_manifest.get("script_hash") == current_script_hash,
            "config_hash_match": phase2_manifest.get("config_hash") == current_config_hash,
            "input_hash_count": len(input_hashes),
            "input_hash_mismatch_count": len(input_mismatches),
            "input_hash_missing_count": len(input_missing),
            "output_hash_count": len(output_hashes),
            "output_hash_mismatch_count": len(output_mismatches),
            "output_hash_missing_count": len(output_missing),
            "validation_file_count": validation_file_count,
            "validation_summary_file_count": validation_summary.get("file_count"),
            "validation_pass_count": validation_summary.get("pass_count"),
            "validation_fail_count": validation_summary.get("fail_count"),
            "scope_gate_status": scope_report["summary"]["status"],
            "scope_gate_warning_count": scope_report["summary"]["warning_count"],
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "data_mutation_performed": False,
            "reports_refreshed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "live_or_paper_execution_approved": False,
        },
        "checks": checks,
        "warnings": warnings,
    }


def render_console(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "phase2_manifest_trust "
        f"status={summary['status']} "
        f"input_hashes={summary['input_hash_count']}/{summary['expected_count']} "
        f"output_hashes={summary['output_hash_count']}/{summary['expected_count']} "
        f"input_mismatches={summary['input_hash_mismatch_count']} "
        f"output_mismatches={summary['output_hash_mismatch_count']} "
        f"validation_pass_count={summary['validation_pass_count']} "
        f"failure_count={summary['failure_count']} "
        f"warning_count={summary['warning_count']}",
    ]
    for check in report["checks"]:
        if check["status"] == "FAIL":
            lines.append(
                f"FAIL {check['name']}: observed={check['observed']!r} expected={check['expected']!r}"
            )
    for warning in report["warnings"]:
        lines.append(
            f"WARN {warning['name']} {warning['code']}: "
            f"observed={warning['observed']!r} expected={warning['expected']!r}"
        )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--data-manifest", default=str(scope_gate.DEFAULT_DATA_MANIFEST))
    parser.add_argument("--canonical-root", default=str(scope_gate.DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--reports-root", default=str(scope_gate.DEFAULT_REPORTS_ROOT))
    parser.add_argument("--phase2-manifest", default=str(scope_gate.DEFAULT_PHASE2_MANIFEST))
    parser.add_argument("--phase2-validation", default=str(scope_gate.DEFAULT_PHASE2_VALIDATION))
    parser.add_argument("--profile-config", default=str(scope_gate.DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--build-script", default=str(scope_gate.DEFAULT_BUILD_SCRIPT))
    parser.add_argument("--expected-count", type=int, default=scope_gate.EXPECTED_CANONICAL_COUNT)
    parser.add_argument("--json", action="store_true", help="Print the read-only report JSON to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    report = evaluate_trust(
        repo_root=repo_root,
        data_manifest_path=scope_gate.resolve_path(repo_root, args.data_manifest),
        canonical_root=scope_gate.resolve_path(repo_root, args.canonical_root),
        reports_root=scope_gate.resolve_path(repo_root, args.reports_root),
        phase2_manifest_path=scope_gate.resolve_path(repo_root, args.phase2_manifest),
        phase2_validation_path=scope_gate.resolve_path(repo_root, args.phase2_validation),
        profile_config_path=scope_gate.resolve_path(repo_root, args.profile_config),
        build_script_path=scope_gate.resolve_path(repo_root, args.build_script),
        expected_count=args.expected_count,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_console(report))
    return 0 if report["summary"]["status"] == STATUS_GO else 1


if __name__ == "__main__":
    raise SystemExit(main())
