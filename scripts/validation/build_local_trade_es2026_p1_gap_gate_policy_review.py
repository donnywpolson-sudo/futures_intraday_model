#!/usr/bin/env python3
"""Review the ES 2026 P1 local-trade gap-gate policy mismatch."""

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

from scripts.phase2_causal_base import build_causal_base_data as phase2_causal_base  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_causal_base_build_proposal as build_proposal  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_gap_gate_policy_review"
STATUS_READY = "REVIEW_READY_ES2026_P1_GAP_GATE_POLICY_REVIEW"
STATUS_NO_GO = "NO_GO_ES2026_P1_GAP_GATE_POLICY_REVIEW"
DECISION_REVIEW_ONLY = "es2026_p1_gap_gate_policy_review_only_no_execution"
DECISION_BLOCKED = "es2026_p1_gap_gate_policy_review_blocked"

TARGET_MARKET = repair_plan_gate.TARGET_MARKET
TARGET_YEAR = repair_plan_gate.TARGET_YEAR
TARGET_PROFILE = repair_plan_gate.DEFAULT_PROFILE
DEFAULT_BUILD_REPORTS_ROOT = build_proposal.DEFAULT_BUILD_REPORTS_ROOT
DEFAULT_OUTPUT_ROOT = build_proposal.DEFAULT_OUTPUT_ROOT
DEFAULT_PROFILE_CONFIG = phase2_causal_base.DEFAULT_PROFILE_CONFIG
EXPECTED_GAP_STATUS = "PASS"
EXPECTED_VENDOR_BACKED_STATUS = build_proposal.EXPECTED_VENDOR_BACKED_STATUS
OBSERVED_MISMATCH_STATUS = phase2_causal_base.LOCAL_TRADE_GAP_SKIPPED_STATUS
OBSERVED_MISMATCH_REASON = "profile_not_required"
FALSE_APPROVAL_FLAGS = repair_plan_gate.FALSE_APPROVAL_FLAGS

FORBIDDEN_ACTIONS = (
    "gap_gate_policy_change_without_explicit_approval",
    "standalone_proof_or_gap_scan",
    "causal_base_build_or_rerun",
    "canonical_data_mutation",
    "candidate_raw_rewrite",
    "provider_download_or_cost_diagnostic",
    "es2026_exclusion",
    "labels_or_features",
    "wfa_or_modeling",
    "metrics_or_predictions",
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


def _read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing JSON report: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"unreadable JSON report {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"JSON report must be an object: {path.as_posix()}"
    return payload, None


def _summary(report: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(report, Mapping):
        return {}
    summary = report.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _gap_gate(report: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(report, Mapping):
        return {}
    gate = report.get("local_trade_ohlcv_gap_gate")
    return gate if isinstance(gate, Mapping) else {}


def _first_file_or_output(report: Mapping[str, Any] | None, key: str) -> Mapping[str, Any]:
    if not isinstance(report, Mapping):
        return {}
    rows = report.get(key)
    if isinstance(rows, list) and rows and isinstance(rows[0], Mapping):
        return rows[0]
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


def _proposal_gap_gate_postcondition(*, profile_config: Path) -> dict[str, Any]:
    return build_proposal._local_trade_gap_gate_postcondition(
        profile_config=profile_config,
    )


def _expected_gap_report_paths(build_reports_root: Path) -> list[Path]:
    return [
        build_reports_root / phase2_causal_base.LOCAL_TRADE_GAP_AUDIT_JSON,
        build_reports_root / phase2_causal_base.LOCAL_TRADE_GAP_AUDIT_MD,
    ]


def _profile_policy_evidence(*, profile_config: Path) -> dict[str, Any]:
    try:
        requires_gate = phase2_causal_base.profile_requires_local_trade_gap_gate(
            TARGET_PROFILE,
            profile_config,
        )
    except Exception as exc:  # pragma: no cover - runtime error text is the evidence.
        return {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
    mandatory_profiles = list(phase2_causal_base.MANDATORY_LOCAL_TRADE_GAP_AUDIT_PROFILES)
    audit_profiles = list(phase2_causal_base.LOCAL_TRADE_GAP_AUDIT_PROFILES)
    return {
        "status": "PASS",
        "profile": TARGET_PROFILE,
        "requires_local_trade_gap_gate": requires_gate,
        "mandatory_local_trade_gap_audit_profiles": mandatory_profiles,
        "local_trade_gap_audit_profiles": audit_profiles,
        "target_profile_in_mandatory_profiles": TARGET_PROFILE in mandatory_profiles,
        "target_profile_in_audit_profiles": TARGET_PROFILE in audit_profiles,
    }


def _postcondition_review() -> dict[str, Any]:
    return {
        "gap_gate_policy_blocker_resolved": True,
        "current_candidate_gap_gate_postcondition_satisfied": True,
        "downstream_execution_requires_separate_bounded_approval": True,
        "bounded_next_gate": {
            "command_family": "downstream_readiness_or_label_feature_gate_requires_separate_approval",
            "maximum_scope": {
                "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
                "profile": TARGET_PROFILE,
                "candidate_output_root": "data/causally_gated_normalized/local_trade_es2026_p1_candidate",
                "build_reports_root": "reports/pipeline_audit/local_trade_es2026_p1_causal_base_build_v1",
                "network": "separate_approval_required",
                "data_or_report_generation": "separate_approval_required",
            },
            "forbidden_actions": list(FORBIDDEN_ACTIONS),
            "stop_condition": (
                "Stop until the next downstream step is separately bounded and approved; "
                "this review does not approve labels, features, WFA/modeling, proof scans, "
                "provider actions, staging, commit, push, or live/paper execution."
            ),
        },
    }


def _recommended_next(status: str) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed gap-gate policy review evidence, then rerun this console-only gate."
    return (
        "Gap-gate postcondition is source-aligned for ES 2026; any downstream use still "
        "requires a separate bounded approval gate."
    )


def build_report(
    *,
    repo_root: Path,
    build_reports_root: Path,
    output_root: Path,
    profile_config: Path,
    manifest_report: Mapping[str, Any] | None = None,
    validation_report: Mapping[str, Any] | None = None,
    profile_policy_evidence: Mapping[str, Any] | None = None,
    proposal_gap_gate_postcondition: Mapping[str, Any] | None = None,
    proposal_expected_gap_gate_status: str | None = None,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    manifest_path = build_reports_root / "causal_base_manifest.json"
    validation_path = build_reports_root / "causal_base_validation.json"
    manifest_error = None
    validation_error = None
    if manifest_report is None:
        manifest_report, manifest_error = _read_json_object(manifest_path)
    if validation_report is None:
        validation_report, validation_error = _read_json_object(validation_path)

    manifest_summary = _summary(manifest_report)
    validation_summary = _summary(validation_report)
    manifest_gate = _gap_gate(manifest_report)
    validation_gate = _gap_gate(validation_report)
    manifest_output = _first_file_or_output(manifest_report, "outputs")
    validation_file = _first_file_or_output(validation_report, "files")
    policy_evidence = dict(
        profile_policy_evidence
        if profile_policy_evidence is not None
        else _profile_policy_evidence(profile_config=profile_config)
    )
    proposal_postcondition = dict(
        proposal_gap_gate_postcondition
        if proposal_gap_gate_postcondition is not None
        else _proposal_gap_gate_postcondition(profile_config=profile_config)
    )
    expected_gap_gate_status = (
        proposal_expected_gap_gate_status
        if proposal_expected_gap_gate_status is not None
        else proposal_postcondition.get("expected_status")
    )
    expected_gap_gate_reason = proposal_postcondition.get("expected_reason")
    expected_vendor_backed_status = proposal_postcondition.get(
        "expected_vendor_backed_status"
    )
    expected_report_count = int(proposal_postcondition.get("expected_report_count") or 0)
    expected_gap_paths = _expected_gap_report_paths(build_reports_root)
    existing_gap_paths = sorted(rel(path, repo_root) for path in expected_gap_paths if path.exists())
    missing_gap_paths = sorted(rel(path, repo_root) for path in expected_gap_paths if not path.exists())

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="manifest_report_readable",
        passed=manifest_error is None and isinstance(manifest_report, Mapping),
        observed=manifest_error,
        expected="readable causal_base_manifest.json object",
        detail="The review starts from the generated ES 2026 build manifest.",
    )
    _check(
        checks,
        name="validation_report_readable",
        passed=validation_error is None and isinstance(validation_report, Mapping),
        observed=validation_error,
        expected="readable causal_base_validation.json object",
        detail="The review starts from the generated ES 2026 build validation report.",
    )
    _check(
        checks,
        name="manifest_exact_es2026_pass",
        passed=(
            manifest_report is not None
            and manifest_report.get("status") == "PASS"
            and manifest_report.get("processed_market_year_count") == 1
            and manifest_report.get("processed_market_years")
            == [{"market": TARGET_MARKET, "year": TARGET_YEAR}]
            and manifest_output.get("market") == TARGET_MARKET
            and manifest_output.get("year") == TARGET_YEAR
            and manifest_output.get("status") == "PASS"
        ),
        observed={
            "status": getattr(manifest_report, "get", lambda _key, _default=None: None)("status"),
            "processed_market_year_count": getattr(
                manifest_report,
                "get",
                lambda _key, _default=None: None,
            )("processed_market_year_count"),
            "processed_market_years": getattr(
                manifest_report,
                "get",
                lambda _key, _default=None: None,
            )("processed_market_years"),
            "output": {
                "market": manifest_output.get("market"),
                "year": manifest_output.get("year"),
                "status": manifest_output.get("status"),
            },
        },
        expected="manifest PASS for exactly ES 2026",
        detail="The mismatch review is valid only for the approved exact-scope candidate build.",
    )
    _check(
        checks,
        name="validation_exact_es2026_pass",
        passed=(
            validation_report is not None
            and validation_report.get("status") == "PASS"
            and validation_summary.get("file_count") == 1
            and validation_summary.get("fail_count") == 0
            and validation_file.get("market") == TARGET_MARKET
            and validation_file.get("year") == TARGET_YEAR
            and validation_file.get("status") == "PASS"
        ),
        observed={
            "status": getattr(validation_report, "get", lambda _key, _default=None: None)(
                "status"
            ),
            "summary": {
                "file_count": validation_summary.get("file_count"),
                "fail_count": validation_summary.get("fail_count"),
            },
            "file": {
                "market": validation_file.get("market"),
                "year": validation_file.get("year"),
                "status": validation_file.get("status"),
            },
        },
        expected="validation PASS for exactly one ES 2026 file",
        detail="The Phase 2 build itself must be exact-scope PASS before reviewing the gap-gate mismatch.",
    )
    _check(
        checks,
        name="accepted_exception_exact_statistics_sparse",
        passed=(
            manifest_report is not None
            and manifest_report.get("accepted_exception_count") == 1
            and manifest_report.get("accepted_exception_failure_count") == 0
            and validation_report is not None
            and validation_report.get("accepted_exception_count") == 1
            and validation_report.get("accepted_exception_failure_count") == 0
        ),
        observed={
            "manifest": {
                "accepted_exception_count": getattr(
                    manifest_report,
                    "get",
                    lambda _key, _default=None: None,
                )("accepted_exception_count"),
                "accepted_exception_failure_count": getattr(
                    manifest_report,
                    "get",
                    lambda _key, _default=None: None,
                )("accepted_exception_failure_count"),
            },
            "validation": {
                "accepted_exception_count": getattr(
                    validation_report,
                    "get",
                    lambda _key, _default=None: None,
                )("accepted_exception_count"),
                "accepted_exception_failure_count": getattr(
                    validation_report,
                    "get",
                    lambda _key, _default=None: None,
                )("accepted_exception_failure_count"),
            },
        },
        expected="one accepted statistics sparse exception and zero exception failures",
        detail="The existing ES 2026 build may be reviewed only if the accepted warning packet stayed exact.",
    )
    _check(
        checks,
        name="proposal_expected_gap_gate_matches_source_policy",
        passed=(
            proposal_postcondition.get("status") == "PASS"
            and expected_gap_gate_status
            in {EXPECTED_GAP_STATUS, phase2_causal_base.LOCAL_TRADE_GAP_SKIPPED_STATUS}
            and proposal_postcondition.get("requires_local_trade_gap_gate")
            == policy_evidence.get("requires_local_trade_gap_gate")
            and (
                policy_evidence.get("requires_local_trade_gap_gate") is True
                or expected_vendor_backed_status == EXPECTED_VENDOR_BACKED_STATUS
            )
        ),
        observed={
            "proposal_postcondition": proposal_postcondition,
            "source_policy": policy_evidence,
        },
        expected="proposal postcondition derived from current Phase 2 gap-gate policy",
        detail="The proposal must not require a gap-gate status that current Phase 2 policy will not produce.",
    )
    _check(
        checks,
        name="observed_gap_gate_matches_policy_postcondition",
        passed=(
            manifest_gate.get("status") == expected_gap_gate_status
            and validation_gate.get("status") == expected_gap_gate_status
            and (
                not expected_gap_gate_reason
                or (
                    manifest_gate.get("reason") == expected_gap_gate_reason
                    and validation_gate.get("reason") == expected_gap_gate_reason
                )
            )
            and manifest_gate.get("selected_markets") == [TARGET_MARKET]
            and validation_gate.get("selected_markets") == [TARGET_MARKET]
            and (
                not expected_vendor_backed_status
                or validation_file.get("vendor_trusted_ohlcv_no_trade_status")
                == expected_vendor_backed_status
            )
        ),
        observed={
            "manifest_gate": {
                "status": manifest_gate.get("status"),
                "reason": manifest_gate.get("reason"),
                "selected_markets": manifest_gate.get("selected_markets"),
            },
            "validation_gate": {
                "status": validation_gate.get("status"),
                "reason": validation_gate.get("reason"),
                "selected_markets": validation_gate.get("selected_markets"),
            },
            "file_vendor_trusted_ohlcv_no_trade_status": validation_file.get(
                "vendor_trusted_ohlcv_no_trade_status"
            ),
        },
        expected={
            "status": expected_gap_gate_status,
            "reason": expected_gap_gate_reason,
            "vendor_trusted_ohlcv_no_trade_status": expected_vendor_backed_status,
        },
        detail="The generated build evidence must match the source-aligned proposal postcondition.",
    )
    _check(
        checks,
        name="source_policy_matches_target_profile_postcondition",
        passed=(
            policy_evidence.get("status") == "PASS"
            and policy_evidence.get("requires_local_trade_gap_gate")
            == proposal_postcondition.get("requires_local_trade_gap_gate")
            and policy_evidence.get("target_profile_in_audit_profiles") is True
        ),
        observed=policy_evidence,
        expected={
            "requires_local_trade_gap_gate": proposal_postcondition.get(
                "requires_local_trade_gap_gate"
            ),
            "target_profile_in_audit_profiles": True,
        },
        detail="The source keeps the diagnostic available but does not make it mandatory for tier_3_forward.",
    )
    _check(
        checks,
        name="expected_gap_reports_match_postcondition",
        passed=(
            (expected_report_count == 0 and not existing_gap_paths)
            or (
                expected_report_count == len(expected_gap_paths)
                and len(existing_gap_paths) == expected_report_count
            )
        ),
        observed={"existing": existing_gap_paths, "missing": missing_gap_paths},
        expected={"expected_report_count": expected_report_count},
        detail="Gap report artifacts must match whether the source policy requires the local-trade gate.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must remain unstaged during review.",
    )
    _check(
        checks,
        name="gap_gate_policy_review_console_only_default",
        passed=True,
        observed="no output writer and no subprocess execution",
        expected="review only",
        detail="This gate intentionally writes no reports, changes no policy, and runs no proof/build command.",
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
            "profile": TARGET_PROFILE,
            "proposal_expected_gap_gate_status": expected_gap_gate_status,
            "proposal_expected_gap_gate_reason": expected_gap_gate_reason,
            "observed_gap_gate_status": validation_gate.get("status") or manifest_gate.get("status"),
            "observed_gap_gate_reason": validation_gate.get("reason") or manifest_gate.get("reason"),
            "source_requires_local_trade_gap_gate": policy_evidence.get(
                "requires_local_trade_gap_gate"
            ),
            "postcondition_alignment_status": "ALIGNED" if not failures else "NOT_ALIGNED",
            "mandatory_local_trade_gap_audit_profile_count": len(
                policy_evidence.get("mandatory_local_trade_gap_audit_profiles") or []
            ),
            "expected_gap_report_count": expected_report_count,
            "missing_expected_gap_report_count": len(missing_gap_paths),
            "existing_expected_gap_report_count": len(existing_gap_paths),
            "generated_report_written": False,
            "generated_output_count": 0,
            "commands_executed": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": _recommended_next(status),
            **_approval_flags(),
        },
        "checks": checks,
        "source_evidence": {
            "manifest_path": rel(manifest_path, repo_root),
            "validation_path": rel(validation_path, repo_root),
            "manifest_summary": {
                "status": getattr(manifest_report, "get", lambda _key, _default=None: None)(
                    "status"
                ),
                "processed_market_year_count": getattr(
                    manifest_report,
                    "get",
                    lambda _key, _default=None: None,
                )("processed_market_year_count"),
                "processed_market_years": getattr(
                    manifest_report,
                    "get",
                    lambda _key, _default=None: None,
                )("processed_market_years"),
                "local_trade_ohlcv_gap_gate": dict(manifest_gate),
            },
            "validation_summary": {
                "status": getattr(validation_report, "get", lambda _key, _default=None: None)(
                    "status"
                ),
                "summary": dict(validation_summary),
                "local_trade_ohlcv_gap_gate": dict(validation_gate),
            },
            "profile_policy": policy_evidence,
            "proposal_gap_gate_postcondition": proposal_postcondition,
            "expected_gap_reports": [rel(path, repo_root) for path in expected_gap_paths],
            "missing_expected_gap_reports": missing_gap_paths,
        },
        "postcondition_review": {} if failures else _postcondition_review(),
        "non_approval": {
            "scope": "ES 2026 P1 gap-gate policy review only",
            "generated_report_written": False,
            "generated_output_count": 0,
            "commands_executed": 0,
            "changed_gap_gate_policy": False,
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--build-reports-root", default=str(DEFAULT_BUILD_REPORTS_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--print-review-json", action="store_true")
    return parser


def review_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "stage": STAGE,
        "status": summary.get("status"),
        "market": summary.get("market"),
        "year": summary.get("year"),
        "profile": summary.get("profile"),
        "proposal_expected_gap_gate_status": summary.get(
            "proposal_expected_gap_gate_status"
        ),
        "proposal_expected_gap_gate_reason": summary.get(
            "proposal_expected_gap_gate_reason"
        ),
        "observed_gap_gate_status": summary.get("observed_gap_gate_status"),
        "observed_gap_gate_reason": summary.get("observed_gap_gate_reason"),
        "source_requires_local_trade_gap_gate": summary.get(
            "source_requires_local_trade_gap_gate"
        ),
        "postcondition_alignment_status": summary.get("postcondition_alignment_status"),
        "gap_report_hygiene": {
            "expected_gap_report_count": summary.get("expected_gap_report_count"),
            "missing_expected_gap_report_count": summary.get(
                "missing_expected_gap_report_count"
            ),
            "existing_expected_gap_report_count": summary.get(
                "existing_expected_gap_report_count"
            ),
        },
        "generated_artifact_hygiene": {
            "generated_output_count": summary.get("generated_output_count"),
            "staged_generated_path_count": summary.get("staged_generated_path_count"),
        },
        "recommended_next_action": summary.get("recommended_next_action"),
        "postcondition_review": report.get("postcondition_review", {}),
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            build_reports_root=resolve_path(repo_root, args.build_reports_root),
            output_root=resolve_path(repo_root, args.output_root),
            profile_config=resolve_path(repo_root, args.profile_config),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"proposal_expected_gap_gate_status={summary['proposal_expected_gap_gate_status']} "
        f"proposal_expected_gap_gate_reason={summary['proposal_expected_gap_gate_reason']} "
        f"observed_gap_gate_status={summary['observed_gap_gate_status']} "
        f"observed_gap_gate_reason={summary['observed_gap_gate_reason']} "
        f"postcondition_alignment_status={summary['postcondition_alignment_status']} "
        f"source_requires_local_trade_gap_gate={summary['source_requires_local_trade_gap_gate']} "
        f"missing_expected_gap_reports={summary['missing_expected_gap_report_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"commands_executed={summary['commands_executed']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_review_json:
        print(json.dumps(review_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
