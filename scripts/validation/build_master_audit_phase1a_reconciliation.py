#!/usr/bin/env python3
"""Build the report-only Master Audit Phase 1A reconciliation.

This command consumes existing local evidence only. It does not run provider
downloads, DBN placement, raw conversion, Phase 2 builds, data/model commands,
WFA/modeling, prediction generation, Phase 8 refresh, promotion, freeze,
holdout, paper/live, cleanup, staging, commit, or push.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import phase1a_acquisition_registry as acquisition_registry


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_phase1a_reconciliation"
PASS_STATUS = "PASS_MASTER_AUDIT_PHASE1A_RECONCILIATION_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_PHASE1A_RECONCILIATION_REPORT_ONLY"

EXPECTED_ARCHIVE_COUNT = 2108

DEFAULT_REPORTS_ROOT = Path("reports/master_audit/master_audit_phase1a_reconciliation_20260710")
REPORT_JSON = "master_audit_phase1a_reconciliation.json"
REPORT_MD = "master_audit_phase1a_reconciliation.md"

PHASE1AB_ROOT = Path(
    "reports/data_audit/current_state/"
    "phase1ab_33markets_2010_2026_post_status_placement_refresh_20260706_rerun1"
)
PHASE1AB_SUMMARY = PHASE1AB_ROOT / "phase1ab_post_status_placement_refresh_summary.json"
PHASE1A_COVERAGE = PHASE1AB_ROOT / "phase1a_dbn_archive_coverage_to_2026_06_13.json"
PHASE1A_REGISTRY = Path("manifests/phase1a_acquisition_registry.jsonl")
REQUIRED_EXCEPTIONS_CONFIG = Path("configs/phase1a_required_schema_exceptions.yaml")

REQUIRED_INPUTS = {
    "phase1a_registry": PHASE1A_REGISTRY,
    "phase1ab_summary": PHASE1AB_SUMMARY,
    "phase1a_archive_coverage": PHASE1A_COVERAGE,
    "required_schema_exceptions_config": REQUIRED_EXCEPTIONS_CONFIG,
}

NON_APPROVAL = {
    "phase_audits_executed": False,
    "phase1a_provider_download_executed": False,
    "phase1a_request_plan_generated": False,
    "phase1a_registry_rebuilt": False,
    "dbn_placement_executed": False,
    "phase1b_conversion_executed": False,
    "phase1b_alignment_executed": False,
    "phase2_readiness_or_build_executed": False,
    "data_model_commands_executed": False,
    "dbn_read_executed": False,
    "raw_parquet_read_executed": False,
    "causal_parquet_read_executed": False,
    "label_parquet_read_executed": False,
    "feature_parquet_read_executed": False,
    "prediction_parquet_read_executed": False,
    "wfa_modeling_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "freeze_executed": False,
    "holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "staging_commit_push_executed": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    failure: str,
    evidence: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "failure": None if passed else failure,
            "evidence": list(evidence),
            "details": dict(details or {}),
        }
    )
    if not passed:
        failures.append(failure)


def input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields = {
        "phase1ab_summary": {
            "status": "status",
            "phase1a_status": "phase1a.status",
            "expected_archives": "phase1a.expected_archives",
            "missing_archives": "phase1a.missing_archives",
            "missing_manifests": "phase1a.missing_manifests",
            "invalid_manifests": "phase1a.invalid_manifests",
            "required_exceptions": "phase1a.required_exceptions",
            "exception_failures": "phase1a.exception_failures",
        },
        "phase1a_archive_coverage": {
            "status": "status",
            "expected_archive_count": "expected_archive_count",
            "missing_archive_count": "missing_archive_count",
            "missing_manifest_count": "missing_manifest_count",
            "invalid_manifest_count": "invalid_manifest_count",
            "required_schema_exception_count": "required_schema_exception_count",
            "required_schema_exception_failure_count": "required_schema_exception_failure_count",
            "profile": "profile",
            "audit_end": "audit_end",
        },
    }
    return [
        inventory.evidence_file(
            repo_root=repo_root,
            relative_path=relative_path,
            json_fields=json_fields.get(name),
            dirty_map=dirty_map,
        )
        for name, relative_path in paths.items()
    ]


def load_payloads(
    *,
    repo_root: Path,
    paths: Mapping[str, Path],
) -> tuple[dict[str, dict[str, Any] | None], list[str]]:
    payloads: dict[str, dict[str, Any] | None] = {}
    failures: list[str] = []
    for name, relative_path in paths.items():
        if Path(relative_path).suffix.lower() != ".json":
            continue
        payload, error = read_json_object(resolve_path(repo_root, relative_path))
        payloads[name] = payload
        if error:
            failures.append(f"{name}: {error}")
    return payloads, failures


def load_registry_rows(registry_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not registry_path.is_file():
        return [], [f"missing Phase 1A acquisition registry: {registry_path.as_posix()}"]
    try:
        rows = acquisition_registry.read_jsonl(registry_path)
    except Exception as exc:
        return [], [f"unreadable Phase 1A acquisition registry {registry_path.as_posix()}: {exc}"]
    failures = acquisition_registry.validation_failures(rows)
    return rows, failures


def summarize_registry(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    provenance_counts = Counter(str(row.get("provenance_status") or "unknown") for row in rows)
    reproducibility_counts = Counter(
        str(row.get("reproducibility_status") or "unknown") for row in rows
    )
    validity_counts = Counter(str(row.get("validity_status") or "unknown") for row in rows)
    rows_with_current_hash = sum(1 for row in rows if row.get("current_file_sha256"))
    rows_with_original_hash = sum(1 for row in rows if row.get("original_file_sha256"))
    original_delivery_ready = len(rows) > 0 and rows_with_original_hash == len(rows)
    post_transfer_only = rows_with_original_hash == 0 and rows_with_current_hash > 0
    return {
        "row_count": len(rows),
        "rows_with_current_file_sha256": rows_with_current_hash,
        "rows_with_original_file_sha256": rows_with_original_hash,
        "provenance_status_counts": dict(sorted(provenance_counts.items())),
        "reproducibility_status_counts": dict(sorted(reproducibility_counts.items())),
        "validity_status_counts": dict(sorted(validity_counts.items())),
        "original_delivery_reproducibility_ready": original_delivery_ready,
        "post_transfer_hash_only_evidence": post_transfer_only,
    }


def build_checks(
    *,
    evidence: Sequence[Mapping[str, Any]],
    payloads: Mapping[str, Mapping[str, Any] | None],
    registry_rows: Sequence[Mapping[str, Any]],
    registry_failures: Sequence[str],
    registry_summary: Mapping[str, Any],
    output_rel: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    evidence_by_path = {str(item.get("path")): item for item in evidence}
    required_paths = {path.as_posix() for path in REQUIRED_INPUTS.values()}

    missing_inputs = [
        str(item.get("path"))
        for item in evidence
        if str(item.get("path")) in required_paths
        and (not item.get("exists") or item.get("read_error"))
    ]
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_inputs,
        failure=f"required Phase 1A input files missing or unreadable: {missing_inputs}",
        evidence=sorted(required_paths),
        details={"missing_or_unreadable": missing_inputs},
    )
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel.startswith("reports/master_audit/") and not output_rel.endswith("/"),
        failure=f"invalid report output root for Phase 1A reconciliation: {output_rel}",
        details={"reports_root": output_rel},
    )
    check(
        checks,
        failures,
        name="phase1a_registry_validate_only_passes",
        passed=len(registry_rows) > 0 and not registry_failures,
        failure="Phase 1A acquisition registry validation failed",
        evidence=[PHASE1A_REGISTRY.as_posix()],
        details={
            "row_count": len(registry_rows),
            "validation_failure_count": len(registry_failures),
            "validation_failures": list(registry_failures[:50]),
        },
    )

    coverage = payloads.get("phase1a_archive_coverage")
    summary = payloads.get("phase1ab_summary")
    coverage_fields = coverage or {}
    summary_phase1a = dotted_get(summary, "phase1a")
    summary_phase1a = summary_phase1a if isinstance(summary_phase1a, Mapping) else {}
    check(
        checks,
        failures,
        name="phase1a_archive_coverage_passes",
        passed=coverage_fields.get("status") == "PASS",
        failure="Phase 1A archive coverage status is not PASS",
        evidence=[PHASE1A_COVERAGE.as_posix()],
        details={"coverage_status": None if coverage is None else coverage.get("status")},
    )
    check(
        checks,
        failures,
        name="phase1a_expected_archive_count_is_2108",
        passed=coverage_fields.get("expected_archive_count") == EXPECTED_ARCHIVE_COUNT,
        failure=f"Phase 1A expected archive count is not {EXPECTED_ARCHIVE_COUNT}",
        evidence=[PHASE1A_COVERAGE.as_posix()],
        details={"expected_archive_count": coverage_fields.get("expected_archive_count")},
    )
    check(
        checks,
        failures,
        name="phase1a_missing_and_invalid_counts_zero",
        passed=coverage_fields.get("missing_archive_count") == 0
        and coverage_fields.get("missing_manifest_count") == 0
        and coverage_fields.get("invalid_manifest_count") == 0,
        failure="Phase 1A archive coverage has missing or invalid archive/manifest rows",
        evidence=[PHASE1A_COVERAGE.as_posix()],
        details={
            "missing_archive_count": coverage_fields.get("missing_archive_count"),
            "missing_manifest_count": coverage_fields.get("missing_manifest_count"),
            "invalid_manifest_count": coverage_fields.get("invalid_manifest_count"),
        },
    )
    check(
        checks,
        failures,
        name="phase1a_required_schema_exceptions_clean",
        passed=coverage_fields.get("required_schema_exception_failure_count") == 0,
        failure="Phase 1A required-schema exception failures are nonzero",
        evidence=[PHASE1A_COVERAGE.as_posix(), REQUIRED_EXCEPTIONS_CONFIG.as_posix()],
        details={
            "required_schema_exception_count": coverage_fields.get(
                "required_schema_exception_count"
            ),
            "required_schema_exception_failure_count": coverage_fields.get(
                "required_schema_exception_failure_count"
            ),
        },
    )
    check(
        checks,
        failures,
        name="phase1ab_summary_matches_phase1a_coverage",
        passed=summary is not None
        and summary.get("status") == "PASS"
        and summary_phase1a.get("status") == "PASS"
        and summary_phase1a.get("expected_archives") == coverage_fields.get("expected_archive_count")
        and summary_phase1a.get("missing_archives") == coverage_fields.get("missing_archive_count")
        and summary_phase1a.get("missing_manifests") == coverage_fields.get("missing_manifest_count")
        and summary_phase1a.get("invalid_manifests") == coverage_fields.get("invalid_manifest_count")
        and summary_phase1a.get("exception_failures")
        == coverage_fields.get("required_schema_exception_failure_count"),
        failure="Phase 1AB summary does not match Phase 1A coverage evidence",
        evidence=[PHASE1AB_SUMMARY.as_posix(), PHASE1A_COVERAGE.as_posix()],
        details={
            "summary_status": None if summary is None else summary.get("status"),
            "summary_phase1a": dict(summary_phase1a),
            "coverage_status": None if coverage is None else coverage.get("status"),
        },
    )
    check(
        checks,
        failures,
        name="original_delivery_reproducibility_caveat_preserved",
        passed=registry_summary.get("row_count", 0) > 0
        and registry_summary.get("original_delivery_reproducibility_ready") is False,
        failure="Phase 1A registry caveat is not preserved as original-delivery-not-ready",
        evidence=[PHASE1A_REGISTRY.as_posix()],
        details=dict(registry_summary),
    )
    check(
        checks,
        failures,
        name="non_approval_flags_all_false",
        passed=all(value is False for value in NON_APPROVAL.values()),
        failure="one or more Phase 1A reconciliation non-approval flags is true",
        details={"non_approval": dict(NON_APPROVAL)},
    )

    for path, item in evidence_by_path.items():
        if path in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))

    derived = {
        "archive_coverage_status": coverage_fields.get("status"),
        "expected_archive_count": coverage_fields.get("expected_archive_count"),
        "missing_archive_count": coverage_fields.get("missing_archive_count"),
        "missing_manifest_count": coverage_fields.get("missing_manifest_count"),
        "invalid_manifest_count": coverage_fields.get("invalid_manifest_count"),
        "required_schema_exception_count": coverage_fields.get(
            "required_schema_exception_count"
        ),
        "required_schema_exception_failure_count": coverage_fields.get(
            "required_schema_exception_failure_count"
        ),
        "registry_validation_failure_count": len(registry_failures),
        "registry_summary": dict(registry_summary),
    }
    return checks, failures, derived


def finding_counts(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("severity")) for item in findings).items()))


def build_findings(derived: Mapping[str, Any]) -> list[dict[str, Any]]:
    registry_summary = derived.get("registry_summary")
    registry_summary = registry_summary if isinstance(registry_summary, Mapping) else {}
    return [
        {
            "finding_id": "phase1a-001-source-lineage-accepted-report-only",
            "severity": "Info",
            "finding": "Phase 1A source acquisition lineage is accepted as report-only local evidence for the current 33-market 2010-2026 scope.",
            "verified_facts": [
                f"archive_coverage_status={derived.get('archive_coverage_status')}",
                f"expected_archive_count={derived.get('expected_archive_count')}",
                f"registry_validation_failure_count={derived.get('registry_validation_failure_count')}",
            ],
            "limitation": "This does not run providers or prove original delivery hashes for every registry row.",
            "evidence_paths": [PHASE1A_COVERAGE.as_posix(), PHASE1A_REGISTRY.as_posix()],
        },
        {
            "finding_id": "phase1a-002-original-delivery-caveat-preserved",
            "severity": "High",
            "finding": "Original-delivery reproducibility is not upgraded because the registry still relies on post-transfer local artifact hashes for at least some rows.",
            "verified_facts": [
                "original_delivery_reproducibility_ready=False",
                "rows_with_original_file_sha256="
                f"{registry_summary.get('rows_with_original_file_sha256')}",
                "rows_with_current_file_sha256="
                f"{registry_summary.get('rows_with_current_file_sha256')}",
            ],
            "limitation": "This is source-lineage evidence, not a vendor re-download or original delivery attestation.",
            "evidence_paths": [PHASE1A_REGISTRY.as_posix()],
        },
        {
            "finding_id": "phase1a-003-no-downstream-actions-authorized",
            "severity": "Info",
            "finding": "No Phase 1B, Phase 2, data/model, provider, promotion, holdout, paper/live, cleanup, staging, commit, or push action is authorized.",
            "verified_facts": ["All non-approval flags are false."],
            "limitation": "The report only remediates the Phase 1A source-lineage evidence gap.",
            "evidence_paths": [],
        },
    ]


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_input_overrides: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = resolve_path(repo_root, reports_root).resolve()
    paths = dict(REQUIRED_INPUTS)
    if required_input_overrides:
        paths.update(required_input_overrides)
    if git_status_lines is None:
        git_status = inventory.collect_git_status(repo_root)
        status_lines = list(git_status["status_lines"])
        git_error = git_status["error"]
        git_returncode = git_status["returncode"]
    else:
        status_lines = list(git_status_lines)
        git_error = None
        git_returncode = 0
    dirty_map = inventory.build_dirty_path_map(status_lines)
    evidence = input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, input_failures = load_payloads(repo_root=repo_root, paths=paths)
    registry_rows, registry_failures = load_registry_rows(
        resolve_path(repo_root, paths["phase1a_registry"])
    )
    registry_summary = summarize_registry(registry_rows)
    output_rel = rel(reports_root, repo_root)
    checks, check_failures, derived = build_checks(
        evidence=evidence,
        payloads=payloads,
        registry_rows=registry_rows,
        registry_failures=registry_failures,
        registry_summary=registry_summary,
        output_rel=output_rel,
    )
    failures = input_failures + registry_failures + check_failures
    status = PASS_STATUS if not failures else FAIL_STATUS
    findings = build_findings(derived)
    passed_checks = sum(1 for item in checks if item["status"] == "PASS")
    failed_checks = sum(1 for item in checks if item["status"] == "FAIL")
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_phase1a_reconciliation_report_only",
            "phase": "Phase 1A",
            "phase_name": "provider/source acquisition lineage",
            "reports_root": output_rel,
            "accepted_scope": "33-market 2010-2026 current horizon ending 2026-06-13",
            "data_model_scope": "none",
            "provider_scope": "none",
            "allowed_inputs": [rel(resolve_path(repo_root, path), repo_root) for path in paths.values()],
        },
        "summary": {
            "status": status,
            "failure_count": len(failures),
            "passed_check_count": passed_checks,
            "failed_check_count": failed_checks,
            "phase1a_source_lineage_ready": status == PASS_STATUS,
            "archive_coverage_status": derived.get("archive_coverage_status"),
            "expected_archive_count": derived.get("expected_archive_count"),
            "missing_archive_count": derived.get("missing_archive_count"),
            "missing_manifest_count": derived.get("missing_manifest_count"),
            "invalid_manifest_count": derived.get("invalid_manifest_count"),
            "required_schema_exception_count": derived.get("required_schema_exception_count"),
            "required_schema_exception_failure_count": derived.get(
                "required_schema_exception_failure_count"
            ),
            "registry_row_count": registry_summary["row_count"],
            "registry_validation_failure_count": len(registry_failures),
            "original_delivery_reproducibility_ready": registry_summary[
                "original_delivery_reproducibility_ready"
            ],
            "post_transfer_hash_only_evidence": registry_summary[
                "post_transfer_hash_only_evidence"
            ],
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
            "current_git_status_short_count": len(status_lines),
            "git_status_error": git_error,
            "git_status_returncode": git_returncode,
            "finding_counts": finding_counts(findings),
        },
        "checks": checks,
        "findings": findings,
        "input_evidence": evidence,
        "registry_summary": dict(registry_summary),
        "non_approval": dict(NON_APPROVAL),
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "failures": failures,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Phase 1A Reconciliation",
        "",
        f"- Status: `{report['status']}`",
        f"- Phase 1A source-lineage ready: `{summary['phase1a_source_lineage_ready']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Archive coverage status: `{summary['archive_coverage_status']}`",
        f"- Expected archives: `{summary['expected_archive_count']}`",
        f"- Missing archives: `{summary['missing_archive_count']}`",
        f"- Missing manifests: `{summary['missing_manifest_count']}`",
        f"- Invalid manifests: `{summary['invalid_manifest_count']}`",
        f"- Registry rows: `{summary['registry_row_count']}`",
        f"- Registry validation failures: `{summary['registry_validation_failure_count']}`",
        f"- Original-delivery reproducibility ready: `{summary['original_delivery_reproducibility_ready']}`",
        f"- Post-transfer hash-only evidence: `{summary['post_transfer_hash_only_evidence']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Failure |",
        "| --- | --- | --- |",
    ]
    for check_row in report["checks"]:
        lines.append(
            "| `{name}` | `{status}` | {failure} |".format(
                name=check_row["name"],
                status=check_row["status"],
                failure=check_row.get("failure") or "",
            )
        )
    lines.extend(["", "## Findings", ""])
    for finding in report["findings"]:
        lines.append(
            "- `{severity}` `{finding_id}`: {finding_text}".format(
                severity=finding["severity"],
                finding_id=finding["finding_id"],
                finding_text=finding["finding"],
            )
        )
    lines.extend(["", "## Failures", ""])
    if report["failures"]:
        for failure in report["failures"]:
            lines.append(f"- {failure}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This reconciliation did not run provider downloads, DBN placement, raw conversion, Phase 2 readiness/build, data/model commands, WFA/modeling, prediction generation/materialization, Phase 8 refresh, promotion, artifact freeze, final holdout, paper/live, cleanup, staging, commit, or push.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / REPORT_JSON
    md_path = reports_root / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(repo_root=repo_root, reports_root=reports_root)
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"phase1a_source_lineage_ready={report['summary']['phase1a_source_lineage_ready']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
