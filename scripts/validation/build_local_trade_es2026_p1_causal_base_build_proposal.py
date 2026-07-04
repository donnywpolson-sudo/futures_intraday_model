#!/usr/bin/env python3
"""Build a console-only ES 2026 P1 causal-base repair/build proposal."""

from __future__ import annotations

import argparse
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

from scripts.phase2_causal_base import build_causal_base_data as phase2_causal_base  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_review as readiness_review  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_causal_base_build_proposal"
STATUS_READY = "REVIEW_READY_ES2026_P1_CAUSAL_BASE_BUILD_PROPOSAL"
STATUS_NO_GO = "NO_GO_ES2026_P1_CAUSAL_BASE_BUILD_PROPOSAL"
DECISION_PROPOSAL_ONLY = "es2026_p1_causal_base_build_proposal_only_no_execution"
DECISION_BLOCKED = "es2026_p1_causal_base_build_proposal_blocked"

TARGET_MARKET = repair_plan_gate.TARGET_MARKET
TARGET_YEAR = repair_plan_gate.TARGET_YEAR
TARGET_PROFILE = repair_plan_gate.DEFAULT_PROFILE
DEFAULT_REPAIR_REPORTS_ROOT = repair_plan_gate.DEFAULT_REPAIR_REPORTS_ROOT
DEFAULT_CANDIDATE_RAW_ROOT = repair_plan_gate.DEFAULT_CANDIDATE_RAW_ROOT
DEFAULT_OUTPUT_ROOT = repair_plan_gate.DEFAULT_OUTPUT_ROOT
DEFAULT_RAW_ALIGNMENT_REPORT = repair_plan_gate.DEFAULT_RAW_ALIGNMENT_REPORT
DEFAULT_BUILD_REPORTS_ROOT = Path(
    "reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1"
)
DEFAULT_PROFILE_CONFIG = phase2_causal_base.DEFAULT_PROFILE_CONFIG
DEFAULT_SESSION_CONFIG = phase2_causal_base.DEFAULT_SESSION_CONFIG
EXPECTED_WARNING_PREFIX = "statistics enrichment sparse: missing_rows=6 stale_rows=6"
EXPECTED_EXCEPTION_CATEGORY = "statistics_enrichment_sparse"
COMMAND_TIMEOUT_SECONDS = 1800
FALSE_APPROVAL_FLAGS = repair_plan_gate.FALSE_APPROVAL_FLAGS
EXPECTED_VENDOR_BACKED_STATUS = "synthetic_thresholds_diagnostic_vendor_backed_provenance"

PLAN_ARTIFACTS = (
    "scripts/validation/build_local_trade_es2026_p1_causal_base_build_proposal.py",
    "tests/validation/test_build_local_trade_es2026_p1_causal_base_build_proposal.py",
    "PROJECT_OUTLINE.md",
    "CODEX_HANDOFF.md",
)
FORBIDDEN_ARG_FLAGS = (
    "--readiness-only",
    "--accepted-readiness-exceptions",
    "--allow-broad-build-after-readiness-pass",
    "--broad-build-approval-token",
    "--write-es-development-lineage-sidecars",
    "--lineage-command-ref",
)
FORBIDDEN_ACTIONS = (
    "canonical_data_mutation",
    "candidate_raw_rewrite",
    "provider_download_or_cost_diagnostic",
    "accepted_warning_packet_write",
    "es2026_exclusion",
    "labels_or_features",
    "wfa_or_modeling",
    "metrics_or_predictions",
    "proof_scan",
    "staging_commit_push",
    "live_or_paper_execution",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return repair_plan_gate.rel(path, repo_root)


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


def _summary(report: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = report.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _path_under(repo_root: Path, path: Path, prefix: str) -> bool:
    try:
        path.resolve().relative_to((repo_root / prefix).resolve())
    except ValueError:
        return False
    return True


def _expected_include_payload() -> dict[str, list[dict[str, int | str]]]:
    return {"market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}]}


def _expected_build_artifacts(
    *,
    output_root: Path,
    build_reports_root: Path,
    include_local_trade_gap_reports: bool,
) -> list[str]:
    artifacts = {
        (build_reports_root / "include_ES_2026.json").as_posix(),
        (output_root / TARGET_MARKET / f"{TARGET_YEAR}.parquet").as_posix(),
        (build_reports_root / "phase2_build.progress.jsonl").as_posix(),
        (build_reports_root / "causal_base_validation.json").as_posix(),
        (build_reports_root / "causal_base_validation.csv").as_posix(),
        (build_reports_root / "causal_base_manifest.json").as_posix(),
    }
    if include_local_trade_gap_reports:
        artifacts.update(
            {
                (build_reports_root / "local_trade_ohlcv_gap_crosscheck_2025_2026.json").as_posix(),
                (build_reports_root / "local_trade_ohlcv_gap_crosscheck_2025_2026.md").as_posix(),
            }
        )
    return sorted(artifacts)


def _build_command(
    *,
    candidate_raw_root: Path,
    output_root: Path,
    build_reports_root: Path,
    raw_alignment_report: Path,
    profile_config: Path,
    session_config: Path,
) -> str:
    include_list = build_reports_root / "include_ES_2026.json"
    progress = build_reports_root / "phase2_build.progress.jsonl"
    return (
        "python -m scripts.phase2_causal_base.build_causal_base_data "
        f"--profile {TARGET_PROFILE} "
        f"--raw-root {candidate_raw_root.as_posix()} "
        f"--output-root {output_root.as_posix()} "
        f"--reports-root {build_reports_root.as_posix()} "
        f"--profile-config {profile_config.as_posix()} "
        f"--session-config {session_config.as_posix()} "
        f"--raw-alignment-report {raw_alignment_report.as_posix()} "
        f"--market-year-include-list {include_list.as_posix()} "
        "--build-max-market-years 1 "
        f"--build-progress-checkpoint-jsonl {progress.as_posix()}"
    )


def _command_bound_failures(
    command: str,
    *,
    candidate_raw_root: Path,
    output_root: Path,
    build_reports_root: Path,
    raw_alignment_report: Path,
    profile_config: Path,
    session_config: Path,
) -> list[str]:
    failures: list[str] = []
    argv = shlex.split(command)
    argv_set = set(argv)
    if argv[:3] != ["python", "-m", "scripts.phase2_causal_base.build_causal_base_data"]:
        failures.append("command does not invoke the Phase 2 causal-base builder")
    for flag in FORBIDDEN_ARG_FLAGS:
        if flag in argv_set:
            failures.append(f"forbidden argument present: {flag}")
    expected = {
        "--profile": TARGET_PROFILE,
        "--raw-root": candidate_raw_root.as_posix(),
        "--output-root": output_root.as_posix(),
        "--reports-root": build_reports_root.as_posix(),
        "--profile-config": profile_config.as_posix(),
        "--session-config": session_config.as_posix(),
        "--raw-alignment-report": raw_alignment_report.as_posix(),
        "--market-year-include-list": (build_reports_root / "include_ES_2026.json").as_posix(),
        "--build-max-market-years": "1",
        "--build-progress-checkpoint-jsonl": (
            build_reports_root / "phase2_build.progress.jsonl"
        ).as_posix(),
    }
    for flag, value in expected.items():
        try:
            observed = argv[argv.index(flag) + 1]
        except (ValueError, IndexError):
            failures.append(f"{flag} missing")
            continue
        if observed != value:
            failures.append(f"{flag}={observed!r} != {value!r}")
    return failures


def _profile_exception_evidence(*, profile_config: Path) -> dict[str, Any]:
    try:
        config = phase2_causal_base.load_causal_base_config(
            profile_config_path=profile_config,
            profile=TARGET_PROFILE,
        )
    except Exception as exc:  # pragma: no cover - runtime error text is the useful output.
        return {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
    exceptions = list(config.accepted_readiness_exceptions)
    matching = [
        exception
        for exception in exceptions
        if exception.market == TARGET_MARKET
        and exception.year == TARGET_YEAR
        and exception.category == EXPECTED_EXCEPTION_CATEGORY
    ]
    selected = matching[0] if len(matching) == 1 else None
    return {
        "status": "PASS" if selected is not None else "FAIL",
        "exception_count": len(exceptions),
        "matching_exception_count": len(matching),
        "market": getattr(selected, "market", None),
        "year": getattr(selected, "year", None),
        "category": getattr(selected, "category", None),
        "reason": getattr(selected, "reason", None),
        "warning_prefixes": list(getattr(selected, "warning_prefixes", tuple())),
        "evidence_paths": list(getattr(selected, "evidence_paths", tuple())),
        "source": getattr(selected, "source", None),
    }


def _local_trade_gap_gate_postcondition(*, profile_config: Path) -> dict[str, Any]:
    try:
        requires_gate = phase2_causal_base.profile_requires_local_trade_gap_gate(
            TARGET_PROFILE,
            profile_config,
        )
    except Exception as exc:  # pragma: no cover - runtime error text is the useful output.
        return {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
    mandatory_profiles = list(phase2_causal_base.MANDATORY_LOCAL_TRADE_GAP_AUDIT_PROFILES)
    audit_profiles = list(phase2_causal_base.LOCAL_TRADE_GAP_AUDIT_PROFILES)
    if requires_gate:
        return {
            "status": "PASS",
            "profile": TARGET_PROFILE,
            "requires_local_trade_gap_gate": True,
            "expected_status": "PASS",
            "expected_reason": None,
            "expected_report_count": 2,
            "expected_report_paths": [
                (
                    DEFAULT_BUILD_REPORTS_ROOT
                    / phase2_causal_base.LOCAL_TRADE_GAP_AUDIT_JSON
                ).as_posix(),
                (
                    DEFAULT_BUILD_REPORTS_ROOT
                    / phase2_causal_base.LOCAL_TRADE_GAP_AUDIT_MD
                ).as_posix(),
            ],
            "expected_vendor_backed_status": None,
            "mandatory_local_trade_gap_audit_profiles": mandatory_profiles,
            "local_trade_gap_audit_profiles": audit_profiles,
            "policy_basis": "mandatory_local_trade_gap_audit",
        }
    return {
        "status": "PASS",
        "profile": TARGET_PROFILE,
        "requires_local_trade_gap_gate": False,
        "expected_status": phase2_causal_base.LOCAL_TRADE_GAP_SKIPPED_STATUS,
        "expected_reason": "profile_not_required",
        "expected_report_count": 0,
        "expected_report_paths": [],
        "expected_vendor_backed_status": EXPECTED_VENDOR_BACKED_STATUS,
        "mandatory_local_trade_gap_audit_profiles": mandatory_profiles,
        "local_trade_gap_audit_profiles": audit_profiles,
        "policy_basis": "vendor_backed_ohlcv_provenance_policy",
    }


def _gap_gate_validation_expectations(
    gap_gate_postcondition: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "local_trade_ohlcv_gap_gate.status": gap_gate_postcondition.get("expected_status"),
        "local_trade_ohlcv_gap_gate.selected_markets": [TARGET_MARKET],
    }
    if gap_gate_postcondition.get("expected_reason"):
        expected["local_trade_ohlcv_gap_gate.reason"] = gap_gate_postcondition.get(
            "expected_reason"
        )
    if gap_gate_postcondition.get("expected_vendor_backed_status"):
        expected["files[0].vendor_trusted_ohlcv_no_trade_status"] = gap_gate_postcondition.get(
            "expected_vendor_backed_status"
        )
    return expected


def _validation_checks(
    *,
    build_reports_root: Path,
    output_root: Path,
    gap_gate_postcondition: Mapping[str, Any],
) -> list[dict[str, Any]]:
    manifest = build_reports_root / "causal_base_manifest.json"
    validation = build_reports_root / "causal_base_validation.json"
    gap_gate_expectations = _gap_gate_validation_expectations(gap_gate_postcondition)
    return [
        {
            "name": "pre_execution_review_packet",
            "expected": STATUS_READY,
            "detail": "Review this proposal packet before approving any build execution.",
        },
        {
            "name": "build_process_result",
            "expected": "exit code 0 before external timeout",
            "timeout_seconds": COMMAND_TIMEOUT_SECONDS,
            "detail": "Stop on timeout, Python traceback, nonzero exit, or readiness preflight failure.",
        },
        {
            "name": "expected_artifacts_exist_and_nonempty",
            "expected": _expected_build_artifacts(
                output_root=output_root,
                build_reports_root=build_reports_root,
                include_local_trade_gap_reports=bool(
                    gap_gate_postcondition.get("expected_report_count")
                ),
            ),
            "detail": "Every expected output must exist and be non-empty; no extra files are allowed under the build reports root or ES candidate output path.",
        },
        {
            "name": "manifest_exact_scope_pass",
            "expected": {
                "path": manifest.as_posix(),
                "status": "PASS",
                "processed_market_year_count": 1,
                "processed_market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
                "output_path": (output_root / TARGET_MARKET / f"{TARGET_YEAR}.parquet").as_posix(),
                "accepted_exception_count": 1,
                "accepted_exception_category": EXPECTED_EXCEPTION_CATEGORY,
                "accepted_exception_failure_count": 0,
            },
            "detail": "Manifest must remain exact ES 2026 and record the configured statistics sparse exception without failures.",
        },
        {
            "name": "validation_exact_scope_pass",
            "expected": {
                "path": validation.as_posix(),
                "status": "PASS",
                "summary.file_count": 1,
                "summary.fail_count": 0,
                **gap_gate_expectations,
            },
            "detail": "Validation JSON must pass the Phase 2 build and match the current ES local-trade gap-gate policy for ES only.",
        },
        {
            "name": "generated_artifacts_unstaged",
            "command": "git diff --cached --name-only -- data reports",
            "expected": [],
            "detail": "Generated data/** and reports/** artifacts must remain unstaged after the build.",
        },
    ]


def _stop_conditions(gap_gate_postcondition: Mapping[str, Any]) -> list[str]:
    if gap_gate_postcondition.get("requires_local_trade_gap_gate"):
        gap_gate_stop = "Stop if the local-trade OHLCV gap gate is not PASS for ES."
    else:
        gap_gate_stop = (
            "Stop if the local-trade OHLCV gap gate is not SKIPPED/profile_not_required "
            "for ES under the current vendor-backed OHLCV provenance policy."
        )
    return [
        "Do not execute until this source/tests/docs-only proposal is reviewed.",
        "Stop before execution if any expected build artifact already exists.",
        "Stop on external timeout, Python traceback, nonzero exit, readiness preflight failure, or output-root guard failure.",
        "Stop if the command selects any market-year other than ES 2026 or writes outside the candidate output/report roots.",
        "Stop if the Phase 2 manifest or validation report is not PASS for exactly one ES 2026 output.",
        "Stop if the configured statistics_enrichment_sparse accepted exception is missing, mismatched, or records any exception failure.",
        gap_gate_stop,
        "Stop if expected artifacts are missing, empty, unignored, unexpectedly staged, or accompanied by unexpected files.",
        "Do not run labels, features, WFA/modeling, proof scans, promotion, staging, commits, pushes, or live/paper execution from this proposal.",
    ]


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed ES 2026 causal-base build proposal preconditions, then rerun this console-only gate."
    return (
        "Review the ES 2026 causal-base repair/build proposal; do not execute the build "
        "until the proposal is explicitly reviewed and approved."
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
    build_reports_root: Path,
    profile_config: Path,
    session_config: Path,
    workflow_status_report: Mapping[str, Any] | None = None,
    candidate_readiness_review_report: Mapping[str, Any] | None = None,
    profile_exception_evidence: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    common_kwargs = {
        "repo_root": repo_root,
        "work_order_report": work_order_report,
        "drilldown_report": drilldown_report,
        "checkpoint_jsonl": checkpoint_jsonl,
        "repair_reports_root": repair_reports_root,
        "candidate_raw_root": candidate_raw_root,
        "output_root": output_root,
        "raw_alignment_report": raw_alignment_report,
        "generated_at_utc": generated_at_utc,
        "staged_generated_paths": staged_paths,
    }
    if ignored_generated_paths is not None:
        common_kwargs["ignored_generated_paths"] = ignored_generated_paths

    from scripts.validation import build_local_trade_es2026_p1_workflow_status as workflow_status

    workflow_report = workflow_status_report or workflow_status.build_report(**common_kwargs)
    readiness_report = candidate_readiness_review_report or readiness_review.build_report(**common_kwargs)
    workflow_summary = _summary(workflow_report)
    readiness_summary = _summary(readiness_report)
    profile_exception = dict(
        profile_exception_evidence
        if profile_exception_evidence is not None
        else _profile_exception_evidence(profile_config=profile_config)
    )
    gap_gate_postcondition = _local_trade_gap_gate_postcondition(profile_config=profile_config)

    expected_artifacts = _expected_build_artifacts(
        output_root=output_root,
        build_reports_root=build_reports_root,
        include_local_trade_gap_reports=bool(
            gap_gate_postcondition.get("expected_report_count")
        ),
    )
    expected_paths = [resolve_path(repo_root, artifact) for artifact in expected_artifacts]
    expected_rel_paths = [rel(path, repo_root) for path in expected_paths]
    ignored_expected_paths = (
        _filter_ignored_expected_paths(expected_rel_paths, ignored_generated_paths or [])
        if ignored_generated_paths is not None
        else _git_ignored_generated_paths(repo_root, expected_rel_paths)
    )
    unignored_expected_paths = sorted(set(expected_rel_paths) - set(ignored_expected_paths))
    existing_expected_paths = sorted(
        rel(path, repo_root) for path in expected_paths if path.exists()
    )
    command = _build_command(
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        build_reports_root=build_reports_root,
        raw_alignment_report=raw_alignment_report,
        profile_config=profile_config,
        session_config=session_config,
    )
    command_failures = _command_bound_failures(
        command,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        build_reports_root=build_reports_root,
        raw_alignment_report=raw_alignment_report,
        profile_config=profile_config,
        session_config=session_config,
    )

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="workflow_status_review_ready",
        passed=(
            workflow_summary.get("status") == workflow_status.STATUS_REVIEW_READY
            and workflow_summary.get("current_gate") == "candidate_readiness_review"
            and workflow_summary.get("next_action_kind")
            == "separate_causal_base_repair_proposal_decision"
        ),
        observed={
            "status": workflow_summary.get("status"),
            "current_gate": workflow_summary.get("current_gate"),
            "next_action_kind": workflow_summary.get("next_action_kind"),
        },
        expected="workflow review-ready at candidate_readiness_review with separate build proposal decision",
        detail="Causal-base build proposal must start from the reviewed candidate readiness boundary.",
    )
    _check(
        checks,
        name="candidate_readiness_review_ready",
        passed=readiness_summary.get("status") == readiness_review.STATUS_READY,
        observed=readiness_summary.get("status"),
        expected=readiness_review.STATUS_READY,
        detail="Build proposal requires exact-scope PASS candidate readiness evidence.",
    )
    _check(
        checks,
        name="profile_exception_exact_es2026",
        passed=(
            profile_exception.get("status") == "PASS"
            and profile_exception.get("matching_exception_count") == 1
            and profile_exception.get("category") == EXPECTED_EXCEPTION_CATEGORY
            and EXPECTED_WARNING_PREFIX in (profile_exception.get("warning_prefixes") or [])
        ),
        observed=profile_exception,
        expected={
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "category": EXPECTED_EXCEPTION_CATEGORY,
            "warning_prefix": EXPECTED_WARNING_PREFIX,
        },
        detail="The existing profile config must carry the exact ES 2026 statistics sparse exception.",
    )
    _check(
        checks,
        name="local_trade_gap_gate_postcondition_known",
        passed=(
            gap_gate_postcondition.get("status") == "PASS"
            and gap_gate_postcondition.get("expected_status")
            in {"PASS", phase2_causal_base.LOCAL_TRADE_GAP_SKIPPED_STATUS}
            and (
                gap_gate_postcondition.get("requires_local_trade_gap_gate") is True
                or gap_gate_postcondition.get("expected_vendor_backed_status")
                == EXPECTED_VENDOR_BACKED_STATUS
            )
        ),
        observed=gap_gate_postcondition,
        expected=(
            "PASS local-trade gap gate when source policy requires it, or "
            "SKIPPED/profile_not_required with vendor-backed OHLCV provenance when it does not"
        ),
        detail="The build proposal must expose the same gap-gate policy that Phase 2 will apply.",
    )
    _check(
        checks,
        name="candidate_output_root_under_data",
        passed=_path_under(repo_root, output_root, "data"),
        observed=rel(output_root, repo_root),
        expected="data/** candidate output root",
        detail="Causal parquet output must stay in a generated candidate data root.",
    )
    _check(
        checks,
        name="build_reports_root_under_reports",
        passed=_path_under(repo_root, build_reports_root, "reports"),
        observed=rel(build_reports_root, repo_root),
        expected="reports/** candidate build reports root",
        detail="Build diagnostics and manifests must stay in ignored reports/.",
    )
    _check(
        checks,
        name="build_command_exact_and_bounded",
        passed=not command_failures,
        observed=command_failures,
        expected="non-readiness Phase 2 build command scoped to ES 2026 with max 1 market-year",
        detail="The proposal must expose a bounded build command without readiness-only, accepted-exception override, or broad-build flags.",
    )
    _check(
        checks,
        name="expected_build_artifacts_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="All planned build outputs must be ignored generated artifacts before execution.",
    )
    _check(
        checks,
        name="expected_build_artifacts_absent_before_execution",
        passed=not existing_expected_paths,
        observed=existing_expected_paths,
        expected=[],
        detail="Proposal review must not overwrite an existing ES 2026 candidate build artifact.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while proposing the build.",
    )
    _check(
        checks,
        name="causal_base_build_proposal_console_only_default",
        passed=True,
        observed="no output writer and no subprocess execution",
        expected="proposal only",
        detail="This gate intentionally writes no reports, creates no include-list file, and runs no build command.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    proposal = {
        "proposal": "es2026_p1_causal_base_repair_build",
        "proposal_status": "READY_FOR_REVIEW_NOT_EXECUTED" if not failures else "BLOCKED",
        "human_review_required": True,
        "market": TARGET_MARKET,
        "year": TARGET_YEAR,
        "profile": TARGET_PROFILE,
        "command_family": "phase2_causal_base_non_readiness_build_exact_scope",
        "exact_command": command,
        "timeout_seconds": COMMAND_TIMEOUT_SECONDS,
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "profile": TARGET_PROFILE,
            "candidate_raw_root": rel(candidate_raw_root, repo_root),
            "candidate_output_root": rel(output_root, repo_root),
            "build_reports_root": rel(build_reports_root, repo_root),
            "raw_alignment_report": rel(raw_alignment_report, repo_root),
            "network": False,
            "canonical_data_mutation": False,
            "build_max_market_years": 1,
        },
        "pre_run_artifacts": [
            {
                "path": rel(build_reports_root / "include_ES_2026.json", repo_root),
                "content": _expected_include_payload(),
            }
        ],
        "expected_ignored_artifacts": expected_rel_paths,
        "validation_checks": _validation_checks(
            build_reports_root=build_reports_root,
            output_root=output_root,
            gap_gate_postcondition=gap_gate_postcondition,
        ),
        "local_trade_gap_gate_postcondition": gap_gate_postcondition,
        "stop_conditions": _stop_conditions(gap_gate_postcondition),
        "forbidden_actions_without_separate_approval": list(FORBIDDEN_ACTIONS),
        "forbidden_argument_flags": list(FORBIDDEN_ARG_FLAGS),
    }
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_PROPOSAL_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "profile": TARGET_PROFILE,
            "workflow_status": workflow_summary.get("status"),
            "current_gate": workflow_summary.get("current_gate"),
            "current_gate_status": workflow_summary.get("current_gate_status"),
            "candidate_readiness_review_status": readiness_summary.get("status"),
            "local_trade_gap_gate_postcondition_status": gap_gate_postcondition.get(
                "expected_status"
            ),
            "source_requires_local_trade_gap_gate": gap_gate_postcondition.get(
                "requires_local_trade_gap_gate"
            ),
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
        "proposal": {} if failures else proposal,
        "expected_generated_artifacts": expected_rel_paths,
        "unignored_expected_generated_artifacts": unignored_expected_paths,
        "existing_expected_generated_artifacts": existing_expected_paths,
        "source_evidence": {
            "workflow_status": {
                "status": workflow_summary.get("status"),
                "current_gate": workflow_summary.get("current_gate"),
                "current_gate_status": workflow_summary.get("current_gate_status"),
                "next_action_kind": workflow_summary.get("next_action_kind"),
            },
            "candidate_readiness_review": {
                "status": readiness_summary.get("status"),
                "review_detail": readiness_report.get("review_detail", {}),
            },
            "profile_exception": profile_exception,
            "local_trade_gap_gate_postcondition": gap_gate_postcondition,
        },
        "non_approval": {
            "scope": "ES 2026 P1 causal-base repair/build proposal only",
            "generated_report_written": False,
            "generated_output_count": 0,
            "commands_executed": 0,
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
    parser.add_argument("--candidate-raw-root", default=str(DEFAULT_CANDIDATE_RAW_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(DEFAULT_RAW_ALIGNMENT_REPORT))
    parser.add_argument("--build-reports-root", default=str(DEFAULT_BUILD_REPORTS_ROOT))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--session-config", default=str(DEFAULT_SESSION_CONFIG))
    parser.add_argument("--print-proposal-json", action="store_true")
    return parser


def proposal_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "stage": STAGE,
        "status": summary.get("status"),
        "market": summary.get("market"),
        "year": summary.get("year"),
        "profile": summary.get("profile"),
        "proposal": report.get("proposal", {}),
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
            build_reports_root=resolve_path(repo_root, args.build_reports_root),
            profile_config=resolve_path(repo_root, args.profile_config),
            session_config=resolve_path(repo_root, args.session_config),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"current_gate={summary['current_gate']} "
        f"candidate_readiness_review_status={summary['candidate_readiness_review_status']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"ignored_expected_generated_outputs={summary['ignored_expected_generated_output_count']} "
        f"unignored_expected_generated_outputs={summary['unignored_expected_generated_output_count']} "
        f"existing_expected_generated_outputs={summary['existing_expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"commands_executed={summary['commands_executed']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_proposal_json:
        print(json.dumps(proposal_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
